"""
Passes 2–4 of the chunking pipeline, applied after format-specific extraction.

Pass 2 — Size normalization
    Merge chunks < 100 tokens with the next chunk of the same type.
    Split chunks > 500 tokens at sentence boundaries (nltk).
    cell and ocr types bypass this pass entirely.
    heading types are never split.

Pass 3 — Overlap stitching
    Prepend the last 50 tokens of the prior chunk to each non-heading,
    non-cell, non-ocr chunk to preserve cross-boundary context.

Pass 4 — Summary chunk (PDF / DOCX only, i.e. has_headings=True)
    Concatenate all heading texts into a single 'summary' chunk prepended
    to the list, giving a fast document-level match for broad queries.
"""
import os
import nltk
from typing import List, Dict, Any

# Download punkt to /tmp so it works inside Lambda's read-only filesystem
_NLTK_DATA = '/tmp/nltk_data'
os.makedirs(_NLTK_DATA, exist_ok=True)
nltk.data.path.append(_NLTK_DATA)


def _ensure_punkt():
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', download_dir=_NLTK_DATA, quiet=True)


# ── constants ──────────────────────────────────────────────────────────────────
TARGET_MIN = 100       # tokens — merge below this
TARGET_MAX = 500       # tokens — split above this
OVERLAP_TOKENS = 50    # tokens of prior chunk prepended in Pass 3

BYPASS_NORM    = {'cell', 'ocr'}          # skip Pass 2
BYPASS_OVERLAP = {'cell', 'ocr', 'heading'}  # skip Pass 3


def _tok(text: str) -> int:
    return len(text.split())


# ── Pass 2 ─────────────────────────────────────────────────────────────────────

def _split_by_sentences(chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
    _ensure_punkt()
    sentences = nltk.sent_tokenize(chunk['text'])
    result: List[Dict[str, Any]] = []
    buf: List[str] = []
    buf_tokens = 0

    for sent in sentences:
        st = _tok(sent)
        if buf_tokens + st > TARGET_MAX and buf:
            text = ' '.join(buf)
            result.append({**chunk, 'text': text, 'token_count': _tok(text)})
            buf = [sent]
            buf_tokens = st
        else:
            buf.append(sent)
            buf_tokens += st

    if buf:
        text = ' '.join(buf)
        result.append({**chunk, 'text': text, 'token_count': _tok(text)})

    return result or [chunk]


def normalize_size(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    i = 0
    while i < len(chunks):
        chunk = dict(chunks[i])

        # headings and bypass types are kept as-is
        if chunk['chunk_type'] in BYPASS_NORM or chunk['chunk_type'] == 'heading':
            result.append(chunk)
            i += 1
            continue

        # Merge small chunks forward (same type only)
        while (
            chunk['token_count'] < TARGET_MIN
            and i + 1 < len(chunks)
            and chunks[i + 1]['chunk_type'] == chunk['chunk_type']
            and chunks[i + 1]['chunk_type'] not in BYPASS_NORM
        ):
            i += 1
            next_text = chunks[i]['text']
            chunk['text'] = chunk['text'].rstrip() + ' ' + next_text.lstrip()
            chunk['token_count'] = _tok(chunk['text'])

        # Split oversized chunks
        if chunk['token_count'] > TARGET_MAX:
            result.extend(_split_by_sentences(chunk))
        else:
            result.append(chunk)

        i += 1

    return result


# ── Pass 3 ─────────────────────────────────────────────────────────────────────

def add_overlap(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        if chunk['chunk_type'] in BYPASS_OVERLAP or i == 0:
            result.append(chunk)
            continue

        prior = chunks[i - 1]
        if prior['chunk_type'] in BYPASS_OVERLAP:
            result.append(chunk)
            continue

        prior_words = prior['text'].split()
        overlap = ' '.join(prior_words[-OVERLAP_TOKENS:])
        new_chunk = dict(chunk)
        new_chunk['text'] = overlap + ' ' + chunk['text']
        new_chunk['token_count'] = _tok(new_chunk['text'])
        result.append(new_chunk)

    return result


# ── Pass 4 ─────────────────────────────────────────────────────────────────────

def add_summary_chunk(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    headings = [c for c in chunks if c['chunk_type'] == 'heading']
    if not headings:
        return chunks

    summary_text = ' | '.join(h['text'] for h in headings)
    summary = {
        'text': summary_text,
        'chunk_type': 'summary',
        'page_number': None,
        'token_count': _tok(summary_text),
    }
    return [summary] + chunks


# ── public entry point ─────────────────────────────────────────────────────────

def process_chunks(
    chunks: List[Dict[str, Any]],
    has_headings: bool = True,
) -> List[Dict[str, Any]]:
    chunks = normalize_size(chunks)
    chunks = add_overlap(chunks)
    if has_headings:
        chunks = add_summary_chunk(chunks)
    return chunks
