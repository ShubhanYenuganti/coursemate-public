# Legacy Chunk/Vector RAG Retirement — Design

**Date:** 2026-06-10
**Status:** Design approved
**Roadmap:** 1.6 (incomplete: legacy path lingers untested)
**Scope:** `api/rag.py` (`retrieve_chunks` and helpers used only by it), `tests/pageindex_eval/eval_runner.py`. The live embedding helpers stay put.

## Findings (current state)

The codebase has **already** mostly retired the legacy path:
- `api/llm.py:315` comment: "PageIndex is now the only retrieval path… the
  `PAGEINDEX_RAG_ENABLED` / `PAGEINDEX_RETRIEVAL_ENABLED` env toggles no longer apply."
- `migrations/002_retire_legacy_chat_rag_tables.sql` retired the legacy chat RAG tables.

What still lingers in production code:
- `api/rag.py::retrieve_chunks` (line 123) — the legacy hybrid chunk/vector text search. It has
  **zero production callers** (`rg retrieve_chunks api src` shows only its own definition). Its only
  live references are:
  - `tests/pageindex_eval/eval_runner.py:89` — imports it as a comparison baseline.
  - `tests/test_chat_search_snippets.py:37` — stubs it to `None`.

What must stay (still live, do not touch):
- `api/rag.py::_invoke_embed_query` and `_search_chat_images` — imported by `api/llm.py:104` for
  prior-image recall. These are part of the PageIndex era, not the legacy chunk path.

## Goal

Eliminate the risk that `retrieve_chunks` silently drifts as untested production surface, **without
breaking the QASPER eval baseline** that legitimately uses it.

## Decision

**Lock the boundary, don't relocate.** Relocating `retrieve_chunks` is risky because it shares the
private helper `_invoke_embed_query` with live code; duplicating that helper is worse. Instead:

1. Mark `retrieve_chunks` explicitly **eval-only** with a docstring stating it has no production
   caller and exists solely as the eval comparison baseline.
2. Add a **regression guard test** that fails if any production module (`api/chat.py`, `api/llm.py`,
   or anything else under `api/` except `api/rag.py` itself) references `retrieve_chunks`. This makes
   accidental re-introduction into the live path a CI failure.
3. Confirm and remove the now-obsolete legacy "exact-chunk replay" comment/branch in
   `api/chat.py` around line 2119 **only if** inspection shows it is dead (it references hydrating
   vector chunk IDs from a retired table). If it is still reachable, leave it and note it in the
   plan — do not guess.

Rejected alternative: an env-flag gate. There is no production caller to gate, so a flag would gate
nothing; the guard test is the correct lock.

## Verification

- New `tests/test_no_legacy_rag_in_production.py` passes (no production import of `retrieve_chunks`).
- `tests/pageindex_eval/eval_runner.py` still imports and runs `retrieve_chunks` as a baseline.
- Full backend suite green (no behavioral change to the live path).
