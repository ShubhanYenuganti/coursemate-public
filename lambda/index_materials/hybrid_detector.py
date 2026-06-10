import json
import re
import statistics
from dataclasses import dataclass, field

try:
    from llm_client import summarize
except ImportError:
    summarize = None

CONFIDENT_THRESHOLD = 0.6
MIN_SECTIONS = 2
MAX_HEADING_CHARS = 120
LLM_PAGE_PREVIEW_CHARS = 200
LLM_MAX_PAGES = 30
LLM_MAX_AMBIGUOUS = 20

_REGEX_PATTERNS = {
    "lecture_slide":   re.compile(r'^#{1,3}\s+(.+)$', re.MULTILINE),
    "lecture_note":    re.compile(r'^#{1,3}\s+(.+)$', re.MULTILINE),
    "reading":         re.compile(r'^#{1,3}\s+(.+)$', re.MULTILINE),
    "discussion_note": re.compile(r'^#{1,3}\s+(.+)$', re.MULTILINE),
    "general":         re.compile(r'^#{1,3}\s+(.+)$', re.MULTILINE),
}


@dataclass
class CandidateHeading:
    page_num: int
    text: str
    font_size: float
    is_bold: bool
    y_position: float
    score: float = 0.0
    source: str = ""


def _score_candidate(
    c: CandidateHeading,
    size_delta_sigma: float,
    regex_corroborated: bool,
) -> float:
    score = 0.0
    if size_delta_sigma >= 1.5:
        score += 0.4
    elif size_delta_sigma >= 1.0:
        score += 0.25
    if c.is_bold:
        score += 0.15
    if c.y_position < 0.25:
        score += 0.1
    if regex_corroborated:
        score += 0.2
    if len(c.text) > MAX_HEADING_CHARS:
        score -= 0.2
    return min(max(score, 0.0), 1.0)


class HybridSectionDetector:
    def __init__(self, doc_type: str = "general", max_pages_per_node: int = 10):
        self.doc_type = doc_type
        self.max_pages_per_node = max_pages_per_node

    def detect(
        self,
        pdf_path: str,
        page_texts: list[str],
        api_key: str | None = None,
    ) -> list[CandidateHeading]:
        font_cands, median_size, stdev_size = self._extract_font_signals(pdf_path)
        regex_cands = self._extract_regex_signals(page_texts)
        merged = self._merge_and_score(font_cands, regex_cands, median_size, stdev_size)

        confident = [c for c in merged if c.score >= CONFIDENT_THRESHOLD]
        ambiguous = [c for c in merged if c.score < CONFIDENT_THRESHOLD]

        if len(confident) < MIN_SECTIONS:
            resolved = self._llm_resolve(ambiguous[:LLM_MAX_AMBIGUOUS], page_texts, api_key)
            confident = sorted(confident + resolved, key=lambda c: c.page_num)

        return confident

    def _extract_font_signals(self, pdf_path: str) -> tuple[list[CandidateHeading], float, float]:
        try:
            import fitz
        except ImportError:
            return [], 12.0, 0.0

        try:
            doc = fitz.open(pdf_path)
        except Exception:
            return [], 12.0, 0.0

        all_sizes = []
        spans_data = []

        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("dict").get("blocks", [])
            page_height = page.rect.height or 1.0
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size", 0.0)
                        text = span.get("text", "").strip()
                        if not text or size < 4:
                            continue
                        all_sizes.append(size)
                        spans_data.append({
                            "page_num": page_num,
                            "text": text,
                            "size": size,
                            "bold": bool(span.get("flags", 0) & 16),
                            "y_rel": span.get("origin", [0, 0])[1] / page_height,
                        })

        doc.close()

        if len(all_sizes) < 3:
            return [], 12.0, 0.0

        median_size = statistics.median(all_sizes)
        stdev_size = statistics.stdev(all_sizes) if len(all_sizes) > 1 else 1.0

        candidates = []
        for s in spans_data:
            delta = s["size"] - median_size
            if delta < stdev_size * 0.5:
                continue
            if len(s["text"]) > MAX_HEADING_CHARS:
                continue
            candidates.append(CandidateHeading(
                page_num=s["page_num"],
                text=s["text"],
                font_size=s["size"],
                is_bold=s["bold"],
                y_position=s["y_rel"],
                source="font",
            ))

        return candidates, median_size, stdev_size

    def _extract_regex_signals(self, page_texts: list[str]) -> list[CandidateHeading]:
        pattern = _REGEX_PATTERNS.get(self.doc_type)
        if not pattern:
            return []
        candidates = []
        for page_num, page_md in enumerate(page_texts, start=1):
            for m in pattern.finditer(page_md):
                groups = [g for g in m.groups() if g]
                title = groups[0].strip() if groups else m.group(0).lstrip("#").strip()
                if not title or len(title) > MAX_HEADING_CHARS:
                    continue
                candidates.append(CandidateHeading(
                    page_num=page_num,
                    text=title,
                    font_size=0.0,
                    is_bold=False,
                    y_position=0.0,
                    source="regex",
                ))
        return candidates

    def _merge_and_score(
        self,
        font_cands: list[CandidateHeading],
        regex_cands: list[CandidateHeading],
        median_size: float,
        stdev_size: float,
    ) -> list[CandidateHeading]:
        regex_by_page: dict[int, set[str]] = {}
        for c in regex_cands:
            regex_by_page.setdefault(c.page_num, set()).add(c.text.lower())

        scored_font = []
        seen_pages = set()
        for c in font_cands:
            corroborated = c.text.lower() in regex_by_page.get(c.page_num, set())
            delta_sigma = (c.font_size - median_size) / (stdev_size or 1.0)
            c.score = _score_candidate(c, delta_sigma, corroborated)
            scored_font.append(c)
            seen_pages.add(c.page_num)

        result = list(scored_font)
        for c in regex_cands:
            if c.page_num not in seen_pages:
                c.score = 0.5
                result.append(c)

        result.sort(key=lambda c: c.page_num)
        return result

    def _llm_resolve(
        self,
        ambiguous: list[CandidateHeading],
        page_texts: list[str],
        api_key: str | None,
    ) -> list[CandidateHeading]:
        if not api_key:
            return []

        if summarize is None:
            return []

        previews = []
        for i, text in enumerate(page_texts[:LLM_MAX_PAGES], start=1):
            preview = text[:LLM_PAGE_PREVIEW_CHARS].replace("\n", " ")
            previews.append(f"Page {i}: {preview}")

        ambiguous_str = "\n".join(
            f"  page={c.page_num} text={c.text!r} score={c.score:.2f}"
            for c in ambiguous[:LLM_MAX_AMBIGUOUS]
        )

        prompt = (
            f"You are identifying section headings in a {self.doc_type} document.\n\n"
            f"Page previews:\n" + "\n".join(previews) + "\n\n"
            f"Ambiguous candidates (may or may not be headings):\n{ambiguous_str}\n\n"
            "Return a JSON array of confirmed headings: "
            '[{"page_num": int, "title": str}, ...]\n'
            "Only include entries you are confident are section headings. "
            "Output only the JSON array, nothing else."
        )

        try:
            raw = summarize(prompt, api_key)
            m = re.search(r'\[.*\]', raw, re.DOTALL)
            if not m:
                return []
            resolved = json.loads(m.group(0))
            return [
                CandidateHeading(
                    page_num=int(r["page_num"]),
                    text=str(r["title"]),
                    font_size=0.0,
                    is_bold=False,
                    y_position=0.0,
                    score=0.8,
                    source="llm",
                )
                for r in resolved
                if "page_num" in r and "title" in r
            ]
        except Exception:
            return []
