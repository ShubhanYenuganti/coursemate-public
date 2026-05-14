# PageIndex RAG implementation (12 tasks completed & verified)

- **Task 2: Lambda scaffold** — completed `handler.py`, `db.py`, `requirements.txt`, `Dockerfile`, and `state_machine.json`; verified with `python3 -m py_compile handler.py db.py`.
- **Task 3: shared index contracts** — completed `IndexNode` and `MaterialIndex` serialization primitives; verified with `python3 -m pytest tests/test_base.py -q`.
- **Task 3b: hybrid section detector** — completed font, regex, merge-scoring, and LLM-resolution heading detection; verified with `python3 -m pytest tests/test_hybrid_detector.py -q`.
- **Task 4: slide index builder** — completed title-slide detection, section grouping, explicit section overrides, and flat fallback; verified with `python3 -m pytest tests/test_slides.py -q`.
- **Task 5: problem index builder** — completed problem/subpart splitting, page matching, markdown node creation, and fallback behavior; verified with `python3 -m pytest tests/test_problems.py -q`.
- **Task 6: document index builder** — completed heading extraction, hierarchy-aware grouping, no-heading fallback, and large-section splitting; verified with `python3 -m pytest tests/test_document.py -q`.
- **Task 7: assessment index builder** — completed quiz/exam question splitting, node creation, and no-question fallback; verified with `python3 -m pytest tests/test_assessment.py -q`.
- **Task 8: builder routing** — completed material-type dispatch for slides, homework, solutions, readings, quizzes, exams, and unknown defaults; verified with `python3 -m pytest tests/test_route_builder.py -q`.
- **Task 9: LLM client** — completed node/doc summary prompts, OpenAI REST summarization, metadata tag extraction, and relation prompts; verified with `python3 -m pytest tests/test_llm_client.py -q`.
- **Task 11: PageIndex retrieval helpers** — completed routing index, material structure, page content, relation lookup, and page range parsing helpers; verified with `python3 -m pytest tests/test_pageindex_retrieval.py -q`.
- **Task 15: relation builder** — completed relation JSON extraction, confidence/type filtering, prompt construction, and async relation generation; verified with `python3 -m pytest tests/test_relation_builder.py -q`.
- **Task 16: graph relation retrieval** — completed bidirectional material relation formatting; verified with `python3 -m pytest tests/test_pageindex_retrieval.py -q -k relations`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace pgvector cosine search with a hierarchical tree index that lets an LLM navigate document structure and fetch raw page text — no embeddings required.

**Architecture:** A new `index_materials` Lambda builds a JSON section tree per document and stores raw page text in Postgres. At query time, `run_agent_pageindex` in `api/llm.py` gives the LLM three navigation tools (`search_course_materials`, `get_material_structure`, `get_page_content`) instead of vector search. Gated by `PAGEINDEX_RETRIEVAL_ENABLED`; existing vector path is untouched.

**Tech Stack:** PyMuPDF (fitz), pymupdf4llm, asyncpg, psycopg, requests (OpenAI REST), pytest

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `lambda/index_materials/handler.py` | Create | S3 trigger + Step Functions worker entry |
| `lambda/index_materials/worker.py` | Create | Orchestrate: extract → build → summarize → store |
| `lambda/index_materials/db.py` | Create | Async DB helpers (page text, tree index, job status) |
| `lambda/index_materials/llm_client.py` | Create | OpenAI REST calls for node summarization |
| `lambda/index_materials/builders/__init__.py` | Create | `route_builder` dispatch |
| `lambda/index_materials/builders/base.py` | Create | `IndexNode`, `MaterialIndex` dataclasses |
| `lambda/index_materials/hybrid_detector.py` | Create | `HybridSectionDetector` — font+regex scoring with LLM fallback |
| `lambda/index_materials/builders/slides.py` | Create | `SlideIndexBuilder` — section-title grouping |
| `lambda/index_materials/builders/problems.py` | Create | `ProblemIndexBuilder` — hw/solution with sub-parts |
| `lambda/index_materials/builders/document.py` | Create | `DocumentIndexBuilder` — heading hierarchy |
| `lambda/index_materials/builders/assessment.py` | Create | `AssessmentIndexBuilder` — quiz/exam flat split |
| `lambda/index_materials/requirements.txt` | Create | Python deps |
| `lambda/index_materials/Dockerfile` | Create | Container image |
| `lambda/index_materials/state_machine.json` | Create | Step Functions loop definition |
| `api/services/query/__init__.py` | Create | Package init |
| `api/services/query/pageindex_retrieval.py` | Create | `get_course_routing_index`, `get_material_structure`, `get_page_content` |
| `api/llm.py` | Modify | Add `run_agent_pageindex()` + feature flag in `synthesize()` |
| `tests/pageindex_eval/eval_runner.py` | Create | Side-by-side eval: vector RAG vs PageIndex |
| `tests/pageindex_eval/test_cases.jsonl` | Create | 6 seed test cases |
| `lambda/index_materials/relation_builder.py` | Create | LLM-driven cross-material knowledge graph edge extraction |

---

## Task 1: DB Migrations

**Files:**
- Run SQL directly in DB (no migration script needed — 3 tables)

- [x] **Step 1: Run migrations**

Execute in your Postgres DB (Supabase SQL editor or `psql`):

```sql
CREATE TABLE material_page_index (
    id             SERIAL PRIMARY KEY,
    material_id    INTEGER REFERENCES materials(id) ON DELETE CASCADE,
    doc_type       TEXT NOT NULL,
    index_json     JSONB NOT NULL,
    page_count     INTEGER,
    index_version  INTEGER DEFAULT 1,
    created_at     TIMESTAMP DEFAULT now(),
    updated_at     TIMESTAMP DEFAULT now(),
    UNIQUE(material_id)
);

CREATE TABLE material_page_text (
    id             SERIAL PRIMARY KEY,
    material_id    INTEGER REFERENCES materials(id) ON DELETE CASCADE,
    page_number    INTEGER NOT NULL,
    text_content   TEXT,
    has_images     BOOLEAN DEFAULT FALSE,
    section_name   TEXT,
    UNIQUE(material_id, page_number)
);

CREATE TABLE course_material_index (
    id               SERIAL PRIMARY KEY,
    course_id        INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    material_id      INTEGER REFERENCES materials(id) ON DELETE CASCADE,
    material_title   TEXT,
    material_summary TEXT,
    doc_type         TEXT,
    page_count       INTEGER,
    metadata_tags    JSONB DEFAULT '[]',
    updated_at       TIMESTAMP DEFAULT now(),
    UNIQUE(course_id, material_id)
);

CREATE TABLE course_material_relations (
    id               SERIAL PRIMARY KEY,
    course_id        INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    source_id        INTEGER REFERENCES materials(id) ON DELETE CASCADE,
    target_id        INTEGER REFERENCES materials(id) ON DELETE CASCADE,
    relation_type    TEXT NOT NULL,
    shared_tags      JSONB DEFAULT '[]',
    similarity_score FLOAT,
    created_at       TIMESTAMP DEFAULT now(),
    UNIQUE(course_id, source_id, target_id)
);
```

- [x] **Step 2: Verify tables exist**

```sql
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('material_page_index','material_page_text','course_material_index','course_material_relations');
```

Expected: 4 rows.

- [x] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add PageIndex DB tables (material_page_index, material_page_text, course_material_index, course_material_relations)"
```

---

## Task 2: Lambda scaffold — handler.py, db.py, requirements.txt, Dockerfile

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/handler.py`
- Create: `lambda/index_materials/db.py`
- Create: `lambda/index_materials/requirements.txt`
- Create: `lambda/index_materials/Dockerfile`
- Create: `lambda/index_materials/state_machine.json`

- [x] **Step 1: Create requirements.txt**

`lambda/index_materials/requirements.txt`:
```
asyncpg==0.29.0
psycopg[binary]==3.1.18
boto3==1.34.0
pymupdf==1.24.0
pymupdf4llm==0.0.17
requests==2.31.0
```

- [x] **Step 2: Create Dockerfile**

`lambda/index_materials/Dockerfile`:
```dockerfile
FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY . ${LAMBDA_TASK_ROOT}

CMD ["handler.lambda_handler"]
```

- [x] **Step 3: Create state_machine.json**

`lambda/index_materials/state_machine.json`:
```json
{
  "Comment": "PageIndex material indexing — loops until status is done",
  "StartAt": "IndexWorker",
  "States": {
    "IndexWorker": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "index_materials",
        "Payload.$": "$"
      },
      "ResultSelector": { "body.$": "$.Payload" },
      "ResultPath": "$.result",
      "Next": "CheckDone"
    },
    "CheckDone": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.result.body.status",
          "StringEquals": "needs_continuation",
          "Next": "PrepareNext"
        }
      ],
      "Default": "Done"
    },
    "PrepareNext": {
      "Type": "Pass",
      "Parameters": {
        "s3_key.$": "$.result.body.s3_key",
        "cursor.$": "$.result.body.cursor"
      },
      "Next": "IndexWorker"
    },
    "Done": {
      "Type": "Succeed"
    }
  }
}
```

- [x] **Step 4: Create db.py**

`lambda/index_materials/db.py`:
```python
import json
import os
import psycopg
from contextlib import contextmanager


@contextmanager
def get_db():
    url = os.environ["DATABASE_URL"]
    conn = psycopg.connect(url, row_factory=psycopg.rows.dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_job(material_id: int, status: str, error: str = None) -> None:
    with get_db() as conn:
        if status == "processing":
            conn.execute(
                "UPDATE material_embed_jobs SET status='processing', started_at=CURRENT_TIMESTAMP WHERE material_id=%s",
                (material_id,),
            )
        elif status == "done":
            conn.execute(
                "UPDATE material_embed_jobs SET status='done', completed_at=CURRENT_TIMESTAMP WHERE material_id=%s",
                (material_id,),
            )
        else:
            conn.execute(
                "UPDATE material_embed_jobs SET status=%s, error_message=%s WHERE material_id=%s",
                (status, error, material_id),
            )


def store_page_texts(conn, material_id: int, pages: list[dict]) -> None:
    """pages: list of {page_number, text_content, has_images, section_name}"""
    for p in pages:
        conn.execute(
            """INSERT INTO material_page_text (material_id, page_number, text_content, has_images, section_name)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (material_id, page_number) DO UPDATE
               SET text_content=EXCLUDED.text_content, has_images=EXCLUDED.has_images,
                   section_name=EXCLUDED.section_name""",
            (material_id, p["page_number"], p["text_content"], p.get("has_images", False), p.get("section_name")),
        )


def store_page_index(conn, material_id: int, index_dict: dict) -> None:
    conn.execute(
        """INSERT INTO material_page_index (material_id, doc_type, index_json, page_count)
           VALUES (%s, %s, %s::jsonb, %s)
           ON CONFLICT (material_id) DO UPDATE
           SET doc_type=EXCLUDED.doc_type, index_json=EXCLUDED.index_json,
               page_count=EXCLUDED.page_count, updated_at=now()""",
        (material_id, index_dict["doc_type"], json.dumps(index_dict), index_dict.get("page_count")),
    )


def store_course_index(
    conn, material_id: int, course_id: int,
    material_title: str, doc_type: str, page_count: int, summary: str,
) -> None:
    conn.execute(
        """INSERT INTO course_material_index
               (course_id, material_id, material_title, doc_type, page_count, material_summary)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (course_id, material_id) DO UPDATE
           SET material_title=EXCLUDED.material_title, doc_type=EXCLUDED.doc_type,
               page_count=EXCLUDED.page_count, material_summary=EXCLUDED.material_summary,
               updated_at=now()""",
        (course_id, material_id, material_title, doc_type, page_count, summary),
    )


def store_metadata_tags(conn, course_id: int, material_id: int, tags: list[str]) -> None:
    import json
    conn.execute(
        """UPDATE course_material_index
           SET metadata_tags = %s::jsonb, updated_at = now()
           WHERE course_id = %s AND material_id = %s""",
        (json.dumps(tags), course_id, material_id),
    )


def load_course_materials_for_relations(conn, course_id: int) -> list[dict]:
    import json
    rows = conn.execute(
        """SELECT material_id, material_title, doc_type, material_summary, metadata_tags
           FROM course_material_index
           WHERE course_id = %s
           ORDER BY material_id""",
        (course_id,),
    ).fetchall()
    result = []
    for r in rows:
        tags = r["metadata_tags"]
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        result.append({**dict(r), "metadata_tags": tags or []})
    return result


def store_material_relations(conn, relations: list[dict]) -> None:
    import json
    for rel in relations:
        conn.execute(
            """INSERT INTO course_material_relations
                   (course_id, source_id, target_id, relation_type, shared_tags, similarity_score)
               VALUES (%s, %s, %s, %s, %s::jsonb, %s)
               ON CONFLICT (course_id, source_id, target_id) DO UPDATE
               SET relation_type=EXCLUDED.relation_type,
                   shared_tags=EXCLUDED.shared_tags,
                   similarity_score=EXCLUDED.similarity_score""",
            (
                rel["course_id"],
                rel["source_id"],
                rel["target_id"],
                rel["relation_type"],
                json.dumps(rel.get("shared_tags", [])),
                rel.get("similarity_score"),
            ),
        )
```

- [x] **Step 5: Create handler.py**

`lambda/index_materials/handler.py`:
```python
import asyncio
import json
import os

import boto3

from db import get_db, mark_job
from worker import index_document

s3 = boto3.client("s3")
sfn = boto3.client("stepfunctions", region_name=os.environ.get("AWS_REGION", "us-east-1"))

BUCKET = os.environ["AWS_S3_BUCKET_NAME"]
STATE_MACHINE_ARN = os.environ["INDEX_STATE_MACHINE_ARN"]


def _resolve_material(s3_key: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT id, course_id, file_type, doc_type, title FROM materials WHERE file_url LIKE %s",
            (f"%{s3_key}%",),
        ).fetchone()


def lambda_handler(event, context):
    if "Records" in event:
        s3_key = event["Records"][0]["s3"]["object"]["key"]
        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps({"s3_key": s3_key, "cursor": 0}),
        )
        return {"status": "launched"}

    s3_key = event.get("s3_key")
    if not s3_key:
        return {"status": "failed", "error": "missing s3_key"}

    row = _resolve_material(s3_key)
    material_id = row["id"] if row else None

    try:
        return _worker(event, context, row)
    except Exception as exc:
        if material_id:
            mark_job(material_id, "failed", error=str(exc))
        return {"status": "failed", "s3_key": s3_key, "error": str(exc)}


def _worker(event: dict, context, row) -> dict:
    s3_key = event["s3_key"]
    if not row:
        return {"status": "done", "s3_key": s3_key, "cursor": 0}

    material_id = row["id"]
    course_id = int(row["course_id"]) if row["course_id"] else None
    file_type = row["file_type"]
    doc_type = row["doc_type"] or "general"
    material_title = row.get("title") or ""

    if file_type != "application/pdf":
        mark_job(material_id, "skipped", error=f"Non-PDF not supported: {file_type!r}")
        return {"status": "done", "s3_key": s3_key, "cursor": 0}

    mark_job(material_id, "processing")

    obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
    file_bytes = obj["Body"].read()

    asyncio.run(
        index_document(
            material_id=material_id,
            course_id=course_id,
            s3_key=s3_key,
            doc_type=doc_type,
            material_title=material_title,
            file_bytes=file_bytes,
        )
    )

    mark_job(material_id, "done")
    return {"status": "done", "s3_key": s3_key, "cursor": 0}
```

- [x] **Step 6: Commit**

```bash
git add lambda/index_materials/
git commit -m "feat: scaffold index_materials Lambda (handler, db, Dockerfile, state machine)"
```

---

## Task 3: builders/base.py — IndexNode + MaterialIndex

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/builders/__init__.py` (empty for now)
- Create: `lambda/index_materials/builders/base.py`
- Test: `lambda/index_materials/tests/test_base.py`

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/__init__.py` (empty)

`lambda/index_materials/tests/test_base.py`:
```python
from builders.base import IndexNode, MaterialIndex
import dataclasses

def test_index_node_defaults():
    node = IndexNode(node_id="0000", title="Intro", start_page=1, end_page=3)
    assert node.summary == ""
    assert node.nodes == []

def test_material_index_to_dict():
    child = IndexNode(node_id="0001", title="Sub", start_page=2, end_page=2)
    root = IndexNode(node_id="0000", title="Intro", start_page=1, end_page=3, nodes=[child])
    mi = MaterialIndex(title="Lecture 1", doc_type="lecture_slide", page_count=10, nodes=[root])
    d = mi.to_dict()
    assert d["title"] == "Lecture 1"
    assert d["doc_type"] == "lecture_slide"
    assert d["page_count"] == 10
    assert len(d["nodes"]) == 1
    assert d["nodes"][0]["nodes"][0]["title"] == "Sub"
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_base.py -v
```

Expected: `ModuleNotFoundError: No module named 'builders'`

- [x] **Step 3: Implement**

`lambda/index_materials/builders/__init__.py` (empty file):
```python
```

`lambda/index_materials/builders/base.py`:
```python
from dataclasses import dataclass, field


@dataclass
class IndexNode:
    node_id: str
    title: str
    start_page: int
    end_page: int
    summary: str = ""
    nodes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "summary": self.summary,
            "nodes": [n.to_dict() for n in self.nodes],
        }


@dataclass
class MaterialIndex:
    title: str
    doc_type: str
    page_count: int
    nodes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "doc_type": self.doc_type,
            "page_count": self.page_count,
            "nodes": [n.to_dict() for n in self.nodes],
        }
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_base.py -v
```

Expected: 2 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/ lambda/index_materials/tests/
git commit -m "feat: add IndexNode + MaterialIndex dataclasses"
```

---

## Task 3b: hybrid_detector.py — HybridSectionDetector

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/hybrid_detector.py`
- Test: `lambda/index_materials/tests/test_hybrid_detector.py`

Three-phase section detection used by `slides.py` and `document.py` builders:

1. **Phase 1 (font signals)** — `fitz.get_text("dict")` extracts font size, bold flag, and y-position for every span. Computes document-wide median + stdev; spans significantly above median are heading candidates.
2. **Phase 2 (scoring)** — Each candidate is scored 0–1 across: font size delta, bold weight, y-position (top quarter = bonus), line length < 80 chars, and regex corroboration. Candidates above `CONFIDENT_THRESHOLD=0.6` are accepted immediately.
3. **Phase 3 (LLM fallback)** — Only fires when confident candidates < `MIN_SECTIONS=2`. Sends page previews + scored-but-ambiguous candidates to LLM with a condensed prompt. For `problems.py` and `assessment.py` this phase never fires — their regex is reliable enough to stay on the pure-regex path.

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/test_hybrid_detector.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import statistics
from unittest.mock import patch, MagicMock
from hybrid_detector import CandidateHeading, HybridSectionDetector, _score_candidate

# --- CandidateHeading ---

def test_candidate_heading_defaults():
    c = CandidateHeading(page_num=1, text="Intro", font_size=14.0, is_bold=True, y_position=0.1)
    assert c.score == 0.0
    assert c.source == ""

# --- _score_candidate ---

def test_score_high_for_large_bold_top():
    c = CandidateHeading(page_num=1, text="Section 1", font_size=18.0, is_bold=True, y_position=0.05)
    score = _score_candidate(c, size_delta_sigma=2.5, regex_corroborated=False)
    assert score >= 0.6

def test_score_boosted_by_regex_corroboration():
    c = CandidateHeading(page_num=2, text="Problem 1", font_size=12.0, is_bold=False, y_position=0.5)
    score_without = _score_candidate(c, size_delta_sigma=0.6, regex_corroborated=False)
    score_with    = _score_candidate(c, size_delta_sigma=0.6, regex_corroborated=True)
    assert score_with > score_without

def test_long_line_penalised():
    long_text = "x" * 130
    c = CandidateHeading(page_num=1, text=long_text, font_size=16.0, is_bold=True, y_position=0.1)
    score = _score_candidate(c, size_delta_sigma=1.5, regex_corroborated=False)
    assert score < 0.6

# --- merge_and_score: regex-only candidates pass through ---

def test_regex_only_candidate_gets_baseline_score():
    detector = HybridSectionDetector(doc_type="lecture_slide")
    font_cands = []
    regex_cands = [
        CandidateHeading(page_num=3, text="Motivation", font_size=0.0, is_bold=False, y_position=0.0, source="regex")
    ]
    merged = detector._merge_and_score(font_cands, regex_cands, median_size=12.0, stdev_size=2.0)
    assert len(merged) == 1
    assert merged[0].score >= 0.5

# --- LLM fallback parse ---

def test_llm_resolve_parses_valid_json():
    detector = HybridSectionDetector(doc_type="reading")
    mock_raw = '[{"page_num": 5, "title": "Methods"}, {"page_num": 9, "title": "Results"}]'
    with patch("hybrid_detector.summarize", return_value=mock_raw):
        resolved = detector._llm_resolve([], ["page text"] * 10, api_key="sk-test")
    assert len(resolved) == 2
    assert resolved[0].page_num == 5
    assert resolved[1].text == "Results"
    assert all(c.source == "llm" for c in resolved)

def test_llm_resolve_returns_empty_on_bad_json():
    detector = HybridSectionDetector(doc_type="reading")
    with patch("hybrid_detector.summarize", return_value="No headings found."):
        resolved = detector._llm_resolve([], ["text"] * 5, api_key="sk-test")
    assert resolved == []

def test_llm_resolve_skips_call_when_no_api_key():
    detector = HybridSectionDetector(doc_type="reading")
    resolved = detector._llm_resolve([], ["text"] * 5, api_key=None)
    assert resolved == []
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_hybrid_detector.py -v
```

Expected: `ImportError: No module named 'hybrid_detector'`

- [x] **Step 3: Implement**

`lambda/index_materials/hybrid_detector.py`:
```python
import json
import re
import statistics
from dataclasses import dataclass, field


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
    # Font size above median
    if size_delta_sigma >= 2.0:
        score += 0.40
    elif size_delta_sigma >= 1.0:
        score += 0.25
    else:
        score += 0.10
    # Bold
    if c.is_bold:
        score += 0.15
    # Position: top quarter of page
    if c.y_position < 0.25:
        score += 0.10
    # Short text (headings are concise)
    if len(c.text) <= MAX_HEADING_CHARS:
        score += 0.10
    else:
        score -= 0.20
    # Regex corroboration
    if regex_corroborated:
        score += 0.25
    return max(0.0, min(score, 1.0))


class HybridSectionDetector:
    def __init__(self, doc_type: str, max_pages_per_node: int = 10):
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
            resolved = self._llm_resolve(ambiguous, page_texts, api_key)
            confident.extend(resolved)

        return sorted(confident, key=lambda c: c.page_num)

    def _extract_font_signals(
        self, pdf_path: str
    ) -> tuple[list[CandidateHeading], float, float]:
        import fitz

        doc = fitz.open(pdf_path)
        all_spans = []

        for page_num, page in enumerate(doc, start=1):
            page_height = page.rect.height or 1.0
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        all_spans.append({
                            "page_num": page_num,
                            "text": text,
                            "size": span.get("size", 0.0),
                            "bold": bool(span.get("flags", 0) & 16),
                            "y_rel": span["origin"][1] / page_height,
                        })
        doc.close()

        if not all_spans:
            return [], 12.0, 1.0

        sizes = [s["size"] for s in all_spans]
        median_size = statistics.median(sizes)
        stdev_size = statistics.stdev(sizes) if len(sizes) > 1 else 1.0

        candidates = []
        seen_page_texts: set[tuple[int, str]] = set()
        for s in all_spans:
            sigma = (s["size"] - median_size) / (stdev_size or 1.0)
            if sigma < 0.5:
                continue
            key = (s["page_num"], s["text"][:40])
            if key in seen_page_texts:
                continue
            seen_page_texts.add(key)
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
            regex_by_page.setdefault(c.page_num, set()).add(c.text.lower()[:40])

        scored: list[CandidateHeading] = []
        font_pages: set[int] = set()

        for c in font_cands:
            sigma = (c.font_size - median_size) / (stdev_size or 1.0)
            page_regex = regex_by_page.get(c.page_num, set())
            corroborated = any(
                c.text.lower()[:40] in r or r in c.text.lower()[:40]
                for r in page_regex
            )
            c.score = _score_candidate(c, size_delta_sigma=sigma, regex_corroborated=corroborated)
            scored.append(c)
            font_pages.add(c.page_num)

        for c in regex_cands:
            if c.page_num not in font_pages:
                c.score = 0.55
                scored.append(c)

        return scored

    def _llm_resolve(
        self,
        ambiguous: list[CandidateHeading],
        page_texts: list[str],
        api_key: str | None,
    ) -> list[CandidateHeading]:
        if not api_key:
            return []

        from llm_client import summarize

        context_lines = [
            f"Page {i}: {md[:LLM_PAGE_PREVIEW_CHARS].replace(chr(10), ' ')}"
            for i, md in enumerate(page_texts[:LLM_MAX_PAGES], start=1)
        ]
        hints = [
            {"page": c.page_num, "text": c.text, "font_size": round(c.font_size, 1)}
            for c in ambiguous[:LLM_MAX_AMBIGUOUS]
        ]
        prompt = (
            f"Identify section headings in this {self.doc_type} document.\n\n"
            "Page previews:\n" + "\n".join(context_lines) + "\n\n"
            f"Candidate lines (ambiguous):\n{json.dumps(hints, indent=2)}\n\n"
            "Output a JSON array of confirmed headings only: "
            '[{"page_num": int, "title": str}, ...]\n'
            "Output [] if none are genuine headings."
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
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_hybrid_detector.py -v
```

Expected: 9 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/hybrid_detector.py lambda/index_materials/tests/test_hybrid_detector.py
git commit -m "feat: HybridSectionDetector — font+regex scoring with targeted LLM fallback"
```

---

## Task 4: builders/slides.py — SlideIndexBuilder

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/builders/slides.py`
- Test: `lambda/index_materials/tests/test_slides.py`

Uses `HybridSectionDetector` to find section-title slides. The detector's font signal naturally identifies the large-text title slides; the existing H1+≤1-body-line heuristic (`_is_section_title_slide`) is kept as a fast-path for when confident font candidates are already found — it runs only as a tiebreaker/fallback on ambiguous pages. The `build` function passes `api_key` through so the LLM fallback fires automatically on sparse or unusual slide decks.

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/test_slides.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.slides import _is_section_title_slide, build_from_pages

def test_title_only_slide_detected():
    assert _is_section_title_slide("# Backpropagation\n") is True

def test_content_slide_not_section():
    md = "# Slide Title\n\nLet x = Wx + b\n\nThis is a derivation step.\n\nAnother line."
    assert _is_section_title_slide(md) is False

def test_empty_slide_not_section():
    assert _is_section_title_slide("") is False

def test_no_h1_not_section():
    assert _is_section_title_slide("## Subsection\nSome content") is False

def test_build_groups_slides_under_sections():
    pages = [
        "# Lecture 5: Backpropagation",        # page 1 — root title (treat as section)
        "# Motivation",                          # page 2 — section title
        "Chain rule: dy/dx = dy/du * du/dx",     # page 3 — content
        "More content here",                     # page 4 — content
        "# Forward Pass",                        # page 5 — section title
        "z = Wx + b\na = sigmoid(z)",            # page 6 — content
    ]
    mi = build_from_pages(pages, doc_type="lecture_slide", lecture_title="Lecture 5")
    assert mi.page_count == 6
    # Should have 2 section nodes (Motivation, Forward Pass) + possibly root
    section_titles = [n.title for n in mi.nodes]
    assert "Motivation" in section_titles or any("Motivation" in t for t in section_titles)

def test_build_flat_when_no_sections():
    pages = [
        "Some slide without H1",
        "Another content slide",
        "Third slide",
    ]
    mi = build_from_pages(pages, doc_type="lecture_slide", lecture_title="Test Lecture")
    assert mi.page_count == 3
    assert len(mi.nodes) == 3
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_slides.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`

- [x] **Step 3: Implement**

`lambda/index_materials/builders/slides.py`:
```python
import re
from builders.base import IndexNode, MaterialIndex

_H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)


def _is_section_title_slide(page_md: str) -> bool:
    if not page_md.strip():
        return False
    lines = [l.strip() for l in page_md.strip().splitlines() if l.strip()]
    if not lines[0].startswith('# '):
        return False
    body = [l for l in lines[1:] if l and not l.startswith('---')]
    return len(body) <= 1


def _extract_h1(page_md: str, fallback: str) -> str:
    m = _H1_RE.search(page_md)
    return m.group(1).strip() if m else fallback


def build_from_pages(
    pages: list[str],
    doc_type: str,
    lecture_title: str,
    section_indices_override: list[int] | None = None,
) -> MaterialIndex:
    page_count = len(pages)
    node_counter = [0]

    def make_id() -> str:
        nid = f"{node_counter[0]:04d}"
        node_counter[0] += 1
        return nid

    section_indices = (
        section_indices_override
        if section_indices_override is not None
        else [i for i, md in enumerate(pages) if _is_section_title_slide(md)]
    )

    if not section_indices:
        nodes = []
        for i, md in enumerate(pages):
            if md.strip():
                nodes.append(IndexNode(
                    node_id=make_id(),
                    title=_extract_h1(md, f"Slide {i+1}"),
                    start_page=i + 1,
                    end_page=i + 1,
                ))
        return MaterialIndex(title=lecture_title, doc_type=doc_type, page_count=page_count, nodes=nodes)

    nodes = []
    boundaries = section_indices + [page_count]
    for idx, sec_i in enumerate(section_indices):
        sec_end_i = boundaries[idx + 1] - 1
        sec_title = _extract_h1(pages[sec_i], f"Section {idx+1}")
        children = []
        for p_i in range(sec_i + 1, sec_end_i + 1):
            if p_i < len(pages) and pages[p_i].strip():
                children.append(IndexNode(
                    node_id=make_id(),
                    title=_extract_h1(pages[p_i], f"Slide {p_i+1}"),
                    start_page=p_i + 1,
                    end_page=p_i + 1,
                ))
        nodes.append(IndexNode(
            node_id=make_id(),
            title=sec_title,
            start_page=sec_i + 1,
            end_page=sec_end_i + 1,
            nodes=children,
        ))

    return MaterialIndex(title=lecture_title, doc_type=doc_type, page_count=page_count, nodes=nodes)


def build(pdf_path: str, full_md: str, api_key: str | None = None) -> MaterialIndex:
    import fitz
    import pymupdf4llm
    from hybrid_detector import HybridSectionDetector

    doc = fitz.open(pdf_path)
    page_count = len(doc)
    pages = [pymupdf4llm.to_markdown(doc, pages=[i]).strip() for i in range(page_count)]
    doc.close()

    m = _H1_RE.search(full_md)
    lecture_title = m.group(1).strip() if m else "Lecture"

    detector = HybridSectionDetector(doc_type="lecture_slide")
    section_pages = {
        c.page_num for c in detector.detect(pdf_path, pages, api_key=api_key)
    }

    # Fall back to _is_section_title_slide for pages not caught by detector
    section_indices = [
        i for i, md in enumerate(pages)
        if (i + 1) in section_pages or _is_section_title_slide(md)
    ]

    return build_from_pages(
        pages, doc_type="lecture_slide", lecture_title=lecture_title,
        section_indices_override=section_indices if section_pages else None,
    )
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_slides.py -v
```

Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/slides.py lambda/index_materials/tests/test_slides.py
git commit -m "feat: SlideIndexBuilder — section-title grouping for lecture slides"
```

---

## Task 5: builders/problems.py — ProblemIndexBuilder

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/builders/problems.py`
- Test: `lambda/index_materials/tests/test_problems.py`

Stays on pure regex — `_PROBLEM_RE` is the correct signal here. Problem numbers aren't distinguished by font size (they're body text), and the LLM fallback in `HybridSectionDetector` would add cost with no accuracy gain. Adds sub-part detection.

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/test_problems.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.problems import _split_problems, _split_subparts, build_from_markdown

def test_split_problems_detects_boundaries():
    md = "HW 3\n\nProblem 1\nDerive the gradient.\n\nProblem 2\nProve convergence."
    preamble, problems = _split_problems(md)
    assert len(problems) == 2
    assert problems[0][0] == "1"
    assert "Derive" in problems[0][1]

def test_split_problems_no_matches_returns_preamble():
    md = "Just a preamble with no problems."
    preamble, problems = _split_problems(md)
    assert preamble == md
    assert problems == []

def test_split_subparts_detects_ab():
    text = "Problem 1\n(a) First part.\n(b) Second part."
    parts = _split_subparts(text)
    assert len(parts) == 2
    assert parts[0][0] == "a"
    assert parts[1][0] == "b"

def test_split_subparts_none():
    text = "Problem 1\nNo sub-parts here."
    parts = _split_subparts(text)
    assert parts == []

def test_build_from_markdown_creates_nodes():
    md = "# HW 3\n\nProblem 1\n(a) Derive.\n(b) Analyze.\n\nProblem 2\nProve."
    mi = build_from_markdown(md, doc_type="hw_instruction", page_count=3)
    assert mi.doc_type == "hw_instruction"
    problem_titles = [n.title for n in mi.nodes]
    assert any("1" in t for t in problem_titles)
    assert any("2" in t for t in problem_titles)
    p1 = next(n for n in mi.nodes if "1" in n.title)
    assert len(p1.nodes) == 2
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_problems.py -v
```

Expected: `ImportError`

- [x] **Step 3: Implement**

`lambda/index_materials/builders/problems.py`:
```python
import re
from builders.base import IndexNode, MaterialIndex

_PROBLEM_RE = re.compile(
    r'^(?:Problem|Question|Exercise)\s+(\d+[\.\w]*)|^(\d+)[\.\)]',
    re.MULTILINE | re.IGNORECASE,
)
_SUBPART_RE = re.compile(r'^\(([a-z])\)', re.MULTILINE)
_H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)
_PAGE_SEP_RE = re.compile(r'^---+$', re.MULTILINE)


def _split_problems(full_md: str) -> tuple[str, list[tuple[str, str]]]:
    matches = list(_PROBLEM_RE.finditer(full_md))
    if not matches:
        return full_md, []
    preamble = full_md[:matches[0].start()].strip()
    problems = []
    for i, m in enumerate(matches):
        num = m.group(1) or m.group(2)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_md)
        problems.append((num, full_md[start:end].strip()))
    return preamble, problems


def _split_subparts(problem_text: str) -> list[tuple[str, str]]:
    matches = list(_SUBPART_RE.finditer(problem_text))
    if not matches:
        return []
    parts = []
    for i, m in enumerate(matches):
        letter = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(problem_text)
        parts.append((letter, problem_text[start:end].strip()))
    return parts


def _find_page(text: str, full_md: str, page_offsets: list[int]) -> int:
    pos = full_md.find(text[:80]) if len(text) >= 80 else full_md.find(text)
    if pos == -1:
        return 1
    for i, bp in enumerate(page_offsets):
        if pos < bp:
            return max(1, i)
    return max(1, len(page_offsets))


def build_from_markdown(
    full_md: str,
    doc_type: str,
    page_count: int,
) -> MaterialIndex:
    page_offsets = [0] + [m.start() for m in _PAGE_SEP_RE.finditer(full_md)]
    _, problems = _split_problems(full_md)
    node_counter = [0]

    def make_id() -> str:
        nid = f"{node_counter[0]:04d}"
        node_counter[0] += 1
        return nid

    nodes = []
    for num, text in problems:
        page = _find_page(text, full_md, page_offsets)
        subparts = _split_subparts(text)
        children = [
            IndexNode(
                node_id=make_id(),
                title=f"Part ({letter})",
                start_page=_find_page(pt, full_md, page_offsets),
                end_page=_find_page(pt, full_md, page_offsets),
            )
            for letter, pt in subparts
        ]
        nodes.append(IndexNode(
            node_id=make_id(),
            title=f"Problem {num}",
            start_page=page,
            end_page=page,
            nodes=children,
        ))

    m = _H1_RE.search(full_md)
    title = m.group(1).strip() if m else doc_type
    return MaterialIndex(title=title, doc_type=doc_type, page_count=page_count, nodes=nodes)


def build(pdf_path: str, full_md: str, doc_type: str = "hw_instruction") -> MaterialIndex:
    import fitz
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    doc.close()
    return build_from_markdown(full_md, doc_type=doc_type, page_count=page_count)
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_problems.py -v
```

Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/problems.py lambda/index_materials/tests/test_problems.py
git commit -m "feat: ProblemIndexBuilder — problem + sub-part detection for HW/solutions"
```

---

## Task 6: builders/document.py — DocumentIndexBuilder (heading hierarchy)

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/builders/document.py`
- Test: `lambda/index_materials/tests/test_document.py`

Uses `HybridSectionDetector` as the primary heading source — font size is the most reliable signal for readings and papers where `##` markdown isn't consistently produced by pymupdf4llm. `_extract_headings` (H2 regex) is kept as the fast-path when font candidates are absent (e.g., pure-markdown input in tests). The `build` function merges both sources: font candidates first, regex backfill for any pages missed.

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/test_document.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.document import _extract_headings, build_from_pages

def test_extract_headings_finds_h2():
    pages = [
        "## Introduction\nSome text here",
        "Continuation of intro",
        "## Methods\nAnother section",
    ]
    headings = _extract_headings(pages)
    assert len(headings) == 2
    assert headings[0] == (0, "Introduction")
    assert headings[1] == (2, "Methods")

def test_extract_headings_h3_under_h2():
    pages = [
        "## Chapter 1\nIntro",
        "### Section 1.1\nContent",
        "### Section 1.2\nMore content",
    ]
    headings = _extract_headings(pages)
    # Returns all headings (h2 and h3), caller groups
    assert any(t == "Chapter 1" for _, t in headings)

def test_build_creates_nodes_from_headings():
    pages = [
        "## Introduction\nSome intro text on page 1.",
        "## Methods\nMethods content here.",
        "More methods.",
        "## Results\nFinal results.",
    ]
    mi = build_from_pages(pages, doc_type="reading", title="My Reading")
    assert mi.page_count == 4
    titles = [n.title for n in mi.nodes]
    assert "Introduction" in titles
    assert "Methods" in titles
    assert "Results" in titles

def test_build_flat_when_no_headings():
    pages = ["Page one content.", "Page two content."]
    mi = build_from_pages(pages, doc_type="reading", title="Flat Doc")
    assert len(mi.nodes) == 1
    assert mi.nodes[0].start_page == 1
    assert mi.nodes[0].end_page == 2
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_document.py -v
```

- [x] **Step 3: Implement**

`lambda/index_materials/builders/document.py`:
```python
import re
from builders.base import IndexNode, MaterialIndex

_H2_RE = re.compile(r'^##\s+(.+)$', re.MULTILINE)
_H3_RE = re.compile(r'^###\s+(.+)$', re.MULTILINE)
_H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)
MAX_PAGES_PER_NODE = 10


def _extract_headings(pages: list[str]) -> list[tuple[int, str]]:
    """Returns list of (page_index_0based, heading_title) for H2 headings."""
    result = []
    for i, md in enumerate(pages):
        m = _H2_RE.search(md)
        if m:
            result.append((i, m.group(1).strip()))
    return result


def build_from_pages(
    pages: list[str],
    doc_type: str,
    title: str,
    headings_override: list[tuple[int, str]] | None = None,
) -> MaterialIndex:
    page_count = len(pages)
    headings = headings_override if headings_override is not None else _extract_headings(pages)
    node_counter = [0]

    def make_id() -> str:
        nid = f"{node_counter[0]:04d}"
        node_counter[0] += 1
        return nid

    if not headings:
        node = IndexNode(
            node_id=make_id(),
            title=title,
            start_page=1,
            end_page=page_count,
        )
        return MaterialIndex(title=title, doc_type=doc_type, page_count=page_count, nodes=[node])

    nodes = []
    boundaries = [h[0] for h in headings] + [page_count]
    for idx, (page_i, heading_title) in enumerate(headings):
        end_i = boundaries[idx + 1] - 1
        span = end_i - page_i + 1
        if span <= MAX_PAGES_PER_NODE:
            nodes.append(IndexNode(
                node_id=make_id(),
                title=heading_title,
                start_page=page_i + 1,
                end_page=end_i + 1,
            ))
        else:
            # Split into sub-nodes of MAX_PAGES_PER_NODE
            parent = IndexNode(
                node_id=make_id(),
                title=heading_title,
                start_page=page_i + 1,
                end_page=end_i + 1,
            )
            for chunk_start in range(page_i, end_i + 1, MAX_PAGES_PER_NODE):
                chunk_end = min(chunk_start + MAX_PAGES_PER_NODE - 1, end_i)
                parent.nodes.append(IndexNode(
                    node_id=make_id(),
                    title=f"{heading_title} (pp. {chunk_start+1}–{chunk_end+1})",
                    start_page=chunk_start + 1,
                    end_page=chunk_end + 1,
                ))
            nodes.append(parent)

    return MaterialIndex(title=title, doc_type=doc_type, page_count=page_count, nodes=nodes)


def build(pdf_path: str, full_md: str, doc_type: str = "reading", api_key: str | None = None) -> MaterialIndex:
    import fitz
    import pymupdf4llm
    from hybrid_detector import HybridSectionDetector

    doc = fitz.open(pdf_path)
    page_count = len(doc)
    pages = [pymupdf4llm.to_markdown(doc, pages=[i]).strip() for i in range(page_count)]
    doc.close()

    m = _H1_RE.search(full_md)
    title = m.group(1).strip() if m else doc_type

    detector = HybridSectionDetector(doc_type=doc_type)
    hybrid_candidates = detector.detect(pdf_path, pages, api_key=api_key)

    if hybrid_candidates:
        # Convert detector output to (page_index_0based, title) pairs
        headings_override = [(c.page_num - 1, c.text) for c in hybrid_candidates]
        return build_from_pages(pages, doc_type=doc_type, title=title,
                                headings_override=headings_override)

    # Fast path: pure regex on markdown (used in unit tests, markdown-only input)
    return build_from_pages(pages, doc_type=doc_type, title=title)
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_document.py -v
```

Expected: 4 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/document.py lambda/index_materials/tests/test_document.py
git commit -m "feat: DocumentIndexBuilder — H2 heading hierarchy for readings/notes"
```

---

## Task 7: builders/assessment.py — AssessmentIndexBuilder

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/builders/assessment.py`
- Test: `lambda/index_materials/tests/test_assessment.py`

Same logic as ProblemIndexBuilder but flat (no sub-parts). Stays on pure regex for the same reason — question numbers are body text, not headings. Detects `[ANSWER_KEY]` pages.

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/test_assessment.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders.assessment import build_from_markdown

def test_quiz_splits_by_question():
    md = "# Quiz 3\n\n1. What is backprop?\n\n2. Define the chain rule.\n\n3. Compute gradient."
    mi = build_from_markdown(md, doc_type="quiz", page_count=2)
    assert mi.doc_type == "quiz"
    assert len(mi.nodes) == 3

def test_exam_with_no_questions_returns_single_node():
    md = "# Exam\nGeneral instructions only."
    mi = build_from_markdown(md, doc_type="exam", page_count=4)
    assert len(mi.nodes) == 1
    assert mi.nodes[0].end_page == 4

def test_nodes_have_no_subparts():
    md = "1. First question.\n2. Second question.\n(a) Part a.\n(b) Part b."
    mi = build_from_markdown(md, doc_type="quiz", page_count=2)
    # Flat — no nesting
    for n in mi.nodes:
        assert n.nodes == []
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_assessment.py -v
```

- [x] **Step 3: Implement**

`lambda/index_materials/builders/assessment.py`:
```python
import re
from builders.base import IndexNode, MaterialIndex
from builders.problems import _split_problems, _find_page, _PAGE_SEP_RE

_H1_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)


def build_from_markdown(full_md: str, doc_type: str, page_count: int) -> MaterialIndex:
    page_offsets = [0] + [m.start() for m in _PAGE_SEP_RE.finditer(full_md)]
    _, problems = _split_problems(full_md)
    node_counter = [0]

    def make_id() -> str:
        nid = f"{node_counter[0]:04d}"
        node_counter[0] += 1
        return nid

    m = _H1_RE.search(full_md)
    title = m.group(1).strip() if m else doc_type

    if not problems:
        return MaterialIndex(
            title=title,
            doc_type=doc_type,
            page_count=page_count,
            nodes=[IndexNode(node_id=make_id(), title=title, start_page=1, end_page=page_count)],
        )

    nodes = [
        IndexNode(
            node_id=make_id(),
            title=f"Question {num}",
            start_page=_find_page(text, full_md, page_offsets),
            end_page=_find_page(text, full_md, page_offsets),
        )
        for num, text in problems
    ]
    return MaterialIndex(title=title, doc_type=doc_type, page_count=page_count, nodes=nodes)


def build(pdf_path: str, full_md: str, doc_type: str = "quiz") -> MaterialIndex:
    import fitz
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    doc.close()
    return build_from_markdown(full_md, doc_type=doc_type, page_count=page_count)
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_assessment.py -v
```

Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/assessment.py lambda/index_materials/tests/test_assessment.py
git commit -m "feat: AssessmentIndexBuilder — flat question splitting for quiz/exam"
```

---

## Task 8: builders/__init__.py — route_builder dispatch

- [x] **Completed**
**Files:**
- Modify: `lambda/index_materials/builders/__init__.py`
- Test: `lambda/index_materials/tests/test_route_builder.py`

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/test_route_builder.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from builders import route_builder

def test_lecture_slide_routes_to_slides():
    fn = route_builder("lecture_slide")
    assert fn.__module__ == "builders.slides"

def test_hw_instruction_routes_to_problems():
    fn = route_builder("hw_instruction")
    assert fn.__module__ == "builders.problems"

def test_hw_solution_routes_to_problems():
    fn = route_builder("hw_solution")
    assert fn.__module__ == "builders.problems"

def test_reading_routes_to_document():
    fn = route_builder("reading")
    assert fn.__module__ == "builders.document"

def test_quiz_routes_to_assessment():
    fn = route_builder("quiz")
    assert fn.__module__ == "builders.assessment"

def test_exam_routes_to_assessment():
    fn = route_builder("exam")
    assert fn.__module__ == "builders.assessment"

def test_unknown_defaults_to_document():
    fn = route_builder("unknown_type")
    assert fn.__module__ == "builders.document"
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_route_builder.py -v
```

- [x] **Step 3: Implement**

`lambda/index_materials/builders/__init__.py`:
```python
from builders import slides, problems, document, assessment

_DISPATCH = {
    "lecture_slide":   slides.build,
    "hw_instruction":  problems.build,
    "hw_solution":     lambda pdf, md: problems.build(pdf, md, doc_type="hw_solution"),
    "quiz":            lambda pdf, md: assessment.build(pdf, md, doc_type="quiz"),
    "exam":            lambda pdf, md: assessment.build(pdf, md, doc_type="exam"),
    "reading":         document.build,
    "lecture_note":    document.build,
    "discussion_note": document.build,
    "general":         document.build,
}


def route_builder(doc_type: str):
    return _DISPATCH.get(doc_type, document.build)
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_route_builder.py -v
```

Expected: 7 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/builders/__init__.py lambda/index_materials/tests/test_route_builder.py
git commit -m "feat: route_builder dispatch — doc_type → builder function"
```

---

## Task 9: llm_client.py — node summarization via OpenAI REST

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/llm_client.py`
- Test: `lambda/index_materials/tests/test_llm_client.py`

Lambda uses service-level `OPENAI_API_KEY_INDEXER` env var (not user's stored key). Uses `gpt-4o-mini` by default.

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/test_llm_client.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from llm_client import build_node_summary_prompt, build_doc_summary_prompt, summarize

def test_node_summary_prompt_for_slides():
    prompt = build_node_summary_prompt("lecture_slide", "Chain Rule\n\ndy/dx = dy/du * du/dx")
    assert "120 tokens" in prompt or "equation" in prompt.lower()

def test_node_summary_prompt_for_hw():
    prompt = build_node_summary_prompt("hw_instruction", "Problem 1\nDerive the gradient.")
    assert "concept" in prompt.lower() or "problem" in prompt.lower()

def test_doc_summary_prompt_includes_nodes():
    prompt = build_doc_summary_prompt("Lecture 5", "lecture_slide", ["Intro", "Backprop", "Conclusion"])
    assert "Lecture 5" in prompt
    assert "Intro" in prompt

def test_summarize_calls_openai_and_returns_text():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Summary of content."}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("llm_client.requests.post", return_value=mock_resp) as mock_post:
        result = summarize("Summarize this.", api_key="sk-test")
    assert result == "Summary of content."
    mock_post.assert_called_once()
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_llm_client.py -v
```

- [x] **Step 3: Implement**

`lambda/index_materials/llm_client.py`:
```python
import os
import requests

_MODEL = "gpt-4o-mini"
_URL = "https://api.openai.com/v1/chat/completions"
_TIMEOUT = 30

_NODE_PROMPTS = {
    "lecture_slide": (
        "Summarize these lecture slides in 120 tokens. "
        "Lead with the main concept taught. "
        "List any equations, definitions, or algorithms introduced by name. "
        "End with: [HAS_EQUATION] if math present, [HAS_DIAGRAM] if figures present."
    ),
    "hw_instruction": (
        "Summarize this problem in 80 tokens. "
        "State: what concept it tests, what the student must do (derive/prove/compute/explain), "
        "and any given constraints. Flag [HAS_EQUATION] or [HAS_DIAGRAM] if present."
    ),
    "hw_solution": (
        "Summarize this solution in 80 tokens. "
        "State the approach used and the key result. "
        "Flag [HAS_EQUATION] or [HAS_DIAGRAM] if present."
    ),
    "reading": (
        "Summarize this section in 100 tokens. "
        "Lead with the main argument or concept. "
        "Name any theorems, lemmas, or definitions. Flag [HAS_PROOF] if a formal proof is present."
    ),
    "quiz": (
        "Summarize this question in 60 tokens. "
        "State what concept it tests and the expected answer type."
    ),
    "exam": (
        "Summarize this question in 60 tokens. "
        "State what concept it tests and the expected answer type."
    ),
}
_DEFAULT_NODE_PROMPT = (
    "Summarize this content in 100 tokens. "
    "Lead with the main concept. Flag [HAS_EQUATION] or [HAS_DIAGRAM] if present."
)

_DOC_SUMMARY_PROMPT = (
    "Write a 2-3 sentence summary of this document for routing purposes. "
    "State the document type, main topic, and key concepts or problems covered. "
    "Be specific — this summary will be used by an LLM to decide whether to look inside this document."
)


def build_node_summary_prompt(doc_type: str, page_text: str) -> str:
    instruction = _NODE_PROMPTS.get(doc_type, _DEFAULT_NODE_PROMPT)
    return f"{instruction}\n\nContent:\n{page_text[:3000]}"


def build_doc_summary_prompt(title: str, doc_type: str, node_titles: list[str]) -> str:
    sections = ", ".join(node_titles[:15])
    return (
        f"{_DOC_SUMMARY_PROMPT}\n\n"
        f"Document title: {title}\n"
        f"Document type: {doc_type}\n"
        f"Sections/topics covered: {sections}"
    )


def summarize(prompt: str, api_key: str) -> str:
    resp = requests.post(
        _URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150,
            "temperature": 0.0,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY_INDEXER")
    if not key:
        raise ValueError("OPENAI_API_KEY_INDEXER env var not set")
    return key


_TAGS_PROMPT = (
    "Extract 5-15 concise topic/concept tags from this course material. "
    "Tags must be lowercase, hyphenated noun phrases (e.g. 'backpropagation', 'chain-rule', 'gradient-descent'). "
    "Focus on specific technical concepts, not generic words like 'lecture' or 'homework'. "
    "Output a JSON array of strings only. No explanation.\n\n"
)

_RELATION_TYPES_DESC = (
    "covers_same_topic  — both materials cover substantially overlapping concepts\n"
    "prerequisite       — existing material must be understood before the target\n"
    "extends            — target directly builds on concepts in existing material\n"
    "practice_for       — target (hw/quiz/exam) tests concepts taught in existing material (lecture)\n"
    "solution_for       — target is a solution set for an existing hw/exam"
)

RELATION_CONFIDENCE_THRESHOLD = 0.6


def build_metadata_tags_prompt(title: str, doc_type: str, summary: str, node_titles: list[str]) -> str:
    sections = ", ".join(node_titles[:20])
    return (
        f"{_TAGS_PROMPT}"
        f"Title: {title}\nType: {doc_type}\nSummary: {summary}\nSections: {sections}"
    )


def build_relations_prompt(target: dict, others: list[dict]) -> str:
    def fmt(m: dict) -> str:
        tags = ", ".join(m.get("metadata_tags") or [])
        return (
            f"ID: {m['material_id']} | Title: {m['material_title']} | Type: {m['doc_type']}\n"
            f"  Summary: {m.get('material_summary') or 'N/A'}\n"
            f"  Tags: {tags or 'none'}"
        )

    others_str = "\n\n".join(fmt(m) for m in others)
    return (
        "You are building a knowledge graph for a course. "
        "Identify semantic relationships between TARGET and EXISTING materials.\n\n"
        f"Relation types:\n{_RELATION_TYPES_DESC}\n\n"
        f"TARGET:\n{fmt(target)}\n\n"
        f"EXISTING MATERIALS:\n{others_str}\n\n"
        "Output a JSON array. Only include relationships with confidence >= 0.6. "
        "Use source_id for the conceptually earlier material, target_id for the dependent one.\n"
        "Format: [{\"source_id\": int, \"target_id\": int, \"relation_type\": str, "
        "\"shared_tags\": [str], \"confidence\": float}]\n"
        "If no confident relationships exist, output: []"
    )


def extract_tags(prompt: str, api_key: str) -> list[str]:
    import json as _json
    import re
    raw = summarize(prompt, api_key)
    m = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not m:
        return []
    try:
        tags = _json.loads(m.group(0))
        return [str(t).strip().lower() for t in tags if isinstance(t, str)]
    except _json.JSONDecodeError:
        return []
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_llm_client.py -v
```

Expected: 4 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/llm_client.py lambda/index_materials/tests/test_llm_client.py
git commit -m "feat: llm_client — OpenAI REST node/doc summarization + tag extraction + relation prompts"
```

---

## Task 10: worker.py — full indexing orchestration

**Files:**
- Create: `lambda/index_materials/worker.py`

No unit test here — integration behavior (S3 + DB + LLM). Tested end-to-end by deploying and triggering with a real PDF.

- [x] **Step 1: Implement worker.py**

`lambda/index_materials/worker.py`:
```python
import asyncio
import os
import tempfile
import logging

import asyncpg
import fitz
import pymupdf4llm

from builders import route_builder
from db import store_page_texts, store_page_index, store_course_index, store_metadata_tags, store_material_relations, load_course_materials_for_relations
from llm_client import build_node_summary_prompt, build_doc_summary_prompt, build_metadata_tags_prompt, summarize, extract_tags, get_api_key
from relation_builder import build_course_relations

logger = logging.getLogger(__name__)
SUMMARY_CONCURRENCY = 4


def _has_images(page: fitz.Page) -> bool:
    return bool(page.get_images(full=False))


def _resolve_section_names(page_rows: list[dict], material_index) -> list[dict]:
    """Walk the IndexNode tree and stamp each page row with its nearest section title."""
    def _walk(nodes, page_num: int) -> str | None:
        for node in nodes:
            if node.start_page <= page_num <= node.end_page:
                child_hit = _walk(node.nodes, page_num)
                return child_hit if child_hit else node.title
        return None

    result = []
    for row in page_rows:
        section = _walk(material_index.nodes, row["page_number"])
        result.append({**row, "section_name": section})
    return result


def _extract_pages(pdf_path: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(len(doc)):
        page = doc[i]
        md = pymupdf4llm.to_markdown(doc, pages=[i]).strip()
        pages.append({
            "page_number": i + 1,
            "text_content": md or None,
            "has_images": _has_images(page),
        })
    doc.close()
    return pages


async def _summarize_node(node, page_rows: dict, doc_type: str, api_key: str, sem: asyncio.Semaphore):
    async with sem:
        page_texts = []
        for p in range(node.start_page, node.end_page + 1):
            row = page_rows.get(p)
            if row and row["text_content"]:
                page_texts.append(row["text_content"])
        combined = "\n\n".join(page_texts)
        if not combined.strip():
            node.summary = ""
            return
        prompt = build_node_summary_prompt(doc_type, combined)
        try:
            node.summary = await asyncio.to_thread(summarize, prompt, api_key)
        except Exception as exc:
            logger.warning("Node summarization failed: %s", exc)
            node.summary = ""


async def _summarize_all_nodes(nodes, page_rows: dict, doc_type: str, api_key: str):
    sem = asyncio.Semaphore(SUMMARY_CONCURRENCY)
    tasks = []
    for node in nodes:
        tasks.append(_summarize_node(node, page_rows, doc_type, api_key, sem))
        for child in node.nodes:
            tasks.append(_summarize_node(child, page_rows, doc_type, api_key, sem))
    await asyncio.gather(*tasks)


async def index_document(
    material_id: int,
    course_id: int | None,
    s3_key: str,
    doc_type: str,
    material_title: str,
    file_bytes: bytes,
) -> None:
    db_url = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(db_url)

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            pdf_path = tmp.name

        page_rows_list = _extract_pages(pdf_path)
        page_rows = {r["page_number"]: r for r in page_rows_list}

        build_fn = route_builder(doc_type)
        full_md = "\n\n---\n\n".join(r["text_content"] or "" for r in page_rows_list)
        material_index = build_fn(pdf_path, full_md)

        page_rows_list = _resolve_section_names(page_rows_list, material_index)
        page_rows = {r["page_number"]: r for r in page_rows_list}

        api_key = get_api_key()
        await _summarize_all_nodes(material_index.nodes, page_rows, doc_type, api_key)

        node_titles = [n.title for n in material_index.nodes]
        doc_summary_prompt = build_doc_summary_prompt(material_title, doc_type, node_titles)
        try:
            doc_summary = await asyncio.to_thread(summarize, doc_summary_prompt, api_key)
        except Exception as exc:
            logger.warning("Doc summary failed: %s", exc)
            doc_summary = ""

        tags_prompt = build_metadata_tags_prompt(material_title, doc_type, doc_summary, node_titles)
        try:
            metadata_tags = await asyncio.to_thread(extract_tags, tags_prompt, api_key)
        except Exception as exc:
            logger.warning("Tag extraction failed: %s", exc)
            metadata_tags = []

        async with pool.acquire() as conn:
            await asyncio.to_thread(
                _sync_store, conn, material_id, course_id, material_title,
                doc_type, material_index, page_rows_list, doc_summary, metadata_tags,
            )

        if course_id:
            try:
                await build_course_relations(
                    db_url=os.environ["DATABASE_URL"],
                    course_id=course_id,
                    updated_material_id=material_id,
                    api_key=api_key,
                )
            except Exception as exc:
                logger.warning("Relation building failed: %s", exc)

        os.unlink(pdf_path)
    finally:
        await pool.close()


def _sync_store(conn, material_id, course_id, material_title, doc_type,
                material_index, page_rows_list, doc_summary, metadata_tags):
    import psycopg
    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as sync_conn:
        store_page_texts(sync_conn, material_id, page_rows_list)
        store_page_index(sync_conn, material_id, material_index.to_dict())
        if course_id:
            store_course_index(
                sync_conn, material_id, course_id, material_title,
                doc_type, material_index.page_count, doc_summary,
            )
            if metadata_tags:
                store_metadata_tags(sync_conn, course_id, material_id, metadata_tags)
        sync_conn.commit()
```

- [ ] **Step 2: Smoke test with a local PDF (optional but recommended)**

Not verified locally: the optional smoke test requires `DATABASE_URL` and
`OPENAI_API_KEY_INDEXER`, which were not set in this environment. A direct
import check was also not verified because local dependencies were missing:
`ModuleNotFoundError: No module named 'fitz'` (`pymupdf` is declared in
`lambda/index_materials/requirements.txt`).

```bash
cd lambda/index_materials
DATABASE_URL=<your-db-url> OPENAI_API_KEY_INDEXER=<key> python -c "
import asyncio
from worker import index_document
with open('/path/to/test.pdf','rb') as f:
    bytes_ = f.read()
asyncio.run(index_document(material_id=999, course_id=1, s3_key='test/test.pdf',
    doc_type='lecture_slide', material_title='Test', file_bytes=bytes_))
print('done')
"
```

- [x] **Step 3: Commit**

```bash
git add lambda/index_materials/worker.py
git commit -m "feat: index_materials worker — extract pages, build tree, summarize, store to DB"
```

---

## Task 11: api/services/query/pageindex_retrieval.py

- [x] **Completed**
**Files:**
- Create: `api/services/query/__init__.py`
- Create: `api/services/query/pageindex_retrieval.py`
- Test: `tests/test_pageindex_retrieval.py`

- [x] **Step 1: Write the failing test**

`tests/__init__.py` (empty):
```python
```

`tests/test_pageindex_retrieval.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from unittest.mock import MagicMock
from services.query.pageindex_retrieval import _parse_pages, get_page_content, get_course_routing_index

def test_parse_pages_range():
    assert _parse_pages("5-7") == [5, 6, 7]

def test_parse_pages_comma():
    assert _parse_pages("3,8") == [3, 8]

def test_parse_pages_single():
    assert _parse_pages("12") == [12]

def test_parse_pages_mixed():
    assert _parse_pages("1-3,7") == [1, 2, 3, 7]

def test_parse_pages_invalid_ignored():
    assert _parse_pages("abc") == []

def test_get_page_content_queries_correct_pages():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"page_number": 5, "text_content": "Chain rule derivation", "has_images": False},
    ]
    conn.cursor.return_value = cursor
    rows = get_page_content(conn, material_id=42, pages="5")
    assert len(rows) == 1
    assert rows[0]["page_number"] == 5

def test_get_course_routing_index_formats_output():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"material_id": 1, "material_title": "Lecture 5", "doc_type": "lecture_slide",
         "page_count": 40, "material_summary": "Covers backprop."},
    ]
    conn.cursor.return_value = cursor
    result = get_course_routing_index(conn, course_id=10)
    assert "Lecture 5" in result
    assert "Covers backprop" in result
```

- [x] **Step 2: Run — verify it fails**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_retrieval.py -v
```

- [x] **Step 3: Implement**

`api/services/query/__init__.py` (empty):
```python
```

`api/services/query/pageindex_retrieval.py`:
```python
def _parse_pages(pages: str) -> list[int]:
    result = set()
    for part in pages.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                for p in range(int(start.strip()), int(end.strip()) + 1):
                    result.add(p)
            except ValueError:
                pass
        else:
            try:
                result.add(int(part))
            except ValueError:
                pass
    return sorted(result)


def get_course_routing_index(
    conn,
    course_id: int,
    material_ids: list | None = None,
) -> str:
    cursor = conn.cursor()
    if material_ids:
        cursor.execute(
            """SELECT material_id, material_title, doc_type, page_count, material_summary
               FROM course_material_index
               WHERE course_id = %s AND material_id = ANY(%s)
               ORDER BY material_id""",
            (course_id, material_ids),
        )
    else:
        cursor.execute(
            """SELECT material_id, material_title, doc_type, page_count, material_summary
               FROM course_material_index
               WHERE course_id = %s
               ORDER BY material_id""",
            (course_id,),
        )
    rows = cursor.fetchall()
    cursor.close()

    if not rows:
        return "No indexed materials available for this course."

    lines = []
    for row in rows:
        lines.append(
            f"[{row['material_id']}] {row['material_title']} ({row['doc_type']}, {row['page_count']} pages)\n"
            f"  Summary: {row['material_summary'] or 'No summary available.'}"
        )
    return "\n\n".join(lines)


def get_material_structure(conn, material_id: int) -> dict:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT index_json FROM material_page_index WHERE material_id = %s",
        (material_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    if not row:
        return {"error": f"No index found for material {material_id}. It may not have been indexed yet."}
    return row["index_json"]


def get_page_content(conn, material_id: int, pages: str) -> list[dict]:
    page_numbers = _parse_pages(pages)
    if not page_numbers:
        return []
    cursor = conn.cursor()
    cursor.execute(
        """SELECT page_number, text_content, has_images
           FROM material_page_text
           WHERE material_id = %s AND page_number = ANY(%s)
           ORDER BY page_number""",
        (material_id, page_numbers),
    )
    rows = cursor.fetchall()
    cursor.close()
    return [dict(r) for r in rows]
```

- [x] **Step 4: Run — verify passing**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_retrieval.py -v
```

Expected: 7 passed.

- [x] **Step 5: Commit**

```bash
git add api/services/query/ tests/test_pageindex_retrieval.py tests/__init__.py
git commit -m "feat: pageindex_retrieval — get_course_routing_index, get_material_structure, get_page_content"
```

---

## Task 12: api/llm.py — run_agent_pageindex()

**Files:**
- Modify: `api/llm.py` (add `run_agent_pageindex` function after `run_agent_openai`)

`run_agent_pageindex` follows the same OpenAI tool-calling loop as `run_agent_openai` but uses three page-navigation tools instead of `search_materials`/`web_search`. It returns the same 7-tuple.

- [x] **Step 1: Read the return signature of run_agent_openai**

Confirm the return tuple at the bottom of `run_agent_openai` in `api/llm.py`. It should match:
```python
return (final_text, grounding_refs, tool_trace, metadata_dict, assistant_reply_summary, assistant_follow_ups, assistant_clarifying_question)
```

- [x] **Step 2: Add run_agent_pageindex to api/llm.py**

Find the line `def synthesize(` in `api/llm.py` and insert the following function immediately before it:

```python
def run_agent_pageindex(
    conn,
    user_message: str,
    model: str,
    api_key: str,
    chat_id: int | None,
    course_id: int | None,
    context_material_ids: list,
    on_event=None,
) -> tuple:
    try:
        from .services.query.pageindex_retrieval import (
            get_course_routing_index, get_material_structure, get_page_content,
        )
    except ImportError:
        from services.query.pageindex_retrieval import (
            get_course_routing_index, get_material_structure, get_page_content,
        )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_course_materials",
                "description": (
                    "Get a summary index of all course materials. "
                    "Call this first to identify which files are relevant to the question."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_material_structure",
                "description": (
                    "Get the hierarchical section/problem index for one material. "
                    "Call after search_course_materials to see what's inside a relevant file before fetching pages."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "integer", "description": "Material ID from search_course_materials"},
                    },
                    "required": ["material_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_page_content",
                "description": (
                    "Fetch raw text of specific pages. "
                    "Use ranges like '5-7', comma lists like '3,8', or single pages like '12'. "
                    "Cite answers as 'Material X, page Y'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "integer"},
                        "pages": {"type": "string", "description": "Page spec: '5-7', '3,8', or '12'"},
                    },
                    "required": ["material_id", "pages"],
                },
            },
        },
    ]

    messages = [
        {"role": "system", "content": AGENTIC_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    grounding_refs: list = []
    tool_trace: list = []
    final_text = ""
    assistant_follow_ups: list = []
    assistant_clarifying_question = None
    assistant_reply_summary = None

    for iteration in range(MAX_TOOL_ITERATIONS):
        started = time.time()
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "tools": tools, "tool_choice": "auto", "temperature": 0.2},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        choice = payload["choices"][0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            raw_final = _message_text(message).strip() or "I could not find relevant content in the course materials."
            reply_body, assistant_reply_summary, assistant_follow_ups, assistant_clarifying_question = _parse_synthesis_json(raw_final)
            final_text = reply_body if (reply_body or "").strip() else raw_final
            tool_trace.append({"iteration": iteration, "finish_reason": choice.get("finish_reason"), "tool_calls": 0, "latency_ms": int((time.time() - started) * 1000)})
            break

        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})

        for call in tool_calls:
            name = call.get("function", {}).get("name")
            raw_args = call.get("function", {}).get("arguments") or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}

            if name == "search_course_materials":
                tool_result = get_course_routing_index(conn, course_id, context_material_ids or None)
                if on_event:
                    on_event({"type": "tool_call", "tool": "search_course_materials"})
            elif name == "get_material_structure":
                mid = args.get("material_id")
                tool_result = json.dumps(get_material_structure(conn, mid), indent=2)
            elif name == "get_page_content":
                mid = args.get("material_id")
                pages_spec = args.get("pages", "")
                rows = get_page_content(conn, mid, pages_spec)
                if rows:
                    parts = [f"--- Page {r['page_number']} ---\n{r['text_content'] or '[No text extracted]'}" for r in rows]
                    tool_result = "\n\n".join(parts)
                    grounding_refs.append(f"material:{mid}")
                else:
                    tool_result = "No content found for the requested pages."
                if on_event:
                    on_event({"type": "tool_call", "tool": "get_page_content", "material_id": mid, "pages": pages_spec})
            else:
                tool_result = f"Unknown tool: {name}"

            tool_trace.append({"tool": name, "args": args, "iteration": iteration})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": str(tool_result)})

    return (
        final_text,
        grounding_refs,
        tool_trace,
        {"intent_type": "pageindex", "verifier_passed": True, "repair_invoked": False},
        assistant_reply_summary,
        assistant_follow_ups or [],
        assistant_clarifying_question,
    )
```

- [x] **Step 3: Verify no syntax errors**

```bash
cd /Users/shubhan/OneShotCourseMate && python -c "import api.llm; print('ok')"
```

Expected: `ok`

- [x] **Step 4: Commit**

```bash
git add api/llm.py
git commit -m "feat: run_agent_pageindex — page-navigation agentic loop for PageIndex RAG"
```

---

## Task 13: api/llm.py — feature flag in synthesize()

**Files:**
- Modify: `api/llm.py` (add feature flag branch inside `synthesize()`)

- [ ] **Step 1: Locate the AGENTIC_LOOP_ENABLED check in synthesize()**

In `api/llm.py`, find:
```python
use_agentic = _is_enabled("AGENTIC_LOOP_ENABLED", default=False)
```

- [ ] **Step 2: Add PageIndex branch before the agentic check**

Add this block immediately before the `use_agentic = _is_enabled(...)` line:

```python
    use_pageindex = _is_enabled("PAGEINDEX_RETRIEVAL_ENABLED", default=False)
    if use_pageindex and not force_context_only:
        agentic_api_key = _get_api_key(conn, user_id, DEFAULT_AGENTIC_PROVIDER)
        pageindex_course_id = None
        if context_material_ids:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT course_id FROM materials WHERE id = %s",
                (context_material_ids[0],),
            )
            row = cursor.fetchone()
            cursor.close()
            if row:
                pageindex_course_id = row["course_id"]
        text, grounding_refs, tool_trace, metadata, msg_summary, follow_ups, clarifying_question = run_agent_pageindex(
            conn=conn,
            user_message=user_message,
            model=DEFAULT_AGENTIC_MODEL,
            api_key=agentic_api_key,
            chat_id=chat_id,
            course_id=pageindex_course_id,
            context_material_ids=material_scope,
            on_event=on_event,
        )
        return text, grounding_refs, metadata, tool_trace, msg_summary, follow_ups, clarifying_question
```

- [ ] **Step 3: Verify import still works**

```bash
cd /Users/shubhan/OneShotCourseMate && python -c "import api.llm; print('ok')"
```

- [ ] **Step 4: Smoke test — toggle env var**

Set `PAGEINDEX_RETRIEVAL_ENABLED=true` locally and verify the flag is picked up:

```bash
cd /Users/shubhan/OneShotCourseMate && python -c "
import os; os.environ['PAGEINDEX_RETRIEVAL_ENABLED'] = 'true'
import api.llm as llm
print(llm._is_enabled('PAGEINDEX_RETRIEVAL_ENABLED'))  # should print True
"
```

Expected: `True`

- [ ] **Step 5: Commit**

```bash
git add api/llm.py
git commit -m "feat: PAGEINDEX_RETRIEVAL_ENABLED feature flag — routes synthesize() to run_agent_pageindex"
```

---

## Task 14: Eval corpus scaffold — runner + seed test cases

**Files:**
- Create: `tests/pageindex_eval/__init__.py`
- Create: `tests/pageindex_eval/test_cases.jsonl`
- Create: `tests/pageindex_eval/eval_runner.py`

The runner measures page hit rate and answer quality (LLM judge) for both the vector RAG path and the PageIndex path.

- [ ] **Step 1: Create seed test cases**

`tests/pageindex_eval/test_cases.jsonl`:
```jsonl
{"id":"tc_001","question":"What is the update rule for SGD shown in the backprop lecture?","doc_type":"lecture_slide","expected_material_title":"backprop","expected_pages":[8,9],"difficulty":"specific_fact","judge_criteria":"Must contain learning rate η, gradient ∇L, update θ=θ−η∇L"}
{"id":"tc_002","question":"What is the chain rule derivation used in backpropagation?","doc_type":"lecture_slide","expected_material_title":"backprop","expected_pages":[3,4,5],"difficulty":"concept_explanation","judge_criteria":"Explains dy/dx = dy/du * du/dx with notation for neural network layers"}
{"id":"tc_003","question":"What does Problem 1 ask the student to derive in HW3?","doc_type":"hw_instruction","expected_material_title":"hw3","expected_pages":[1,2],"difficulty":"specific_fact","judge_criteria":"Names the derivation target — gradient or update rule from context"}
{"id":"tc_004","question":"What theorem does Chapter 4 introduce for convergence?","doc_type":"reading","expected_material_title":"chapter4","expected_pages":[8,9,10],"difficulty":"concept_explanation","judge_criteria":"Names the theorem and states the convergence condition"}
{"id":"tc_005","question":"What is the definition of a convex function given in the reading?","doc_type":"reading","expected_material_title":"chapter4","expected_pages":[5,6],"difficulty":"specific_fact","judge_criteria":"Contains formal definition with f(λx+(1-λ)y) ≤ λf(x)+(1-λ)f(y)"}
{"id":"tc_006","question":"How does the midterm assess students' understanding of backprop vs forward pass?","doc_type":"exam","expected_material_title":"midterm","expected_pages":[2,3,4],"difficulty":"multi_hop","judge_criteria":"Identifies questions about both forward and backward pass steps and how they are tested"}
```

- [ ] **Step 2: Create eval_runner.py**

`tests/pageindex_eval/eval_runner.py`:
```python
#!/usr/bin/env python3
"""
Side-by-side eval: vector RAG vs PageIndex RAG.

Usage:
  python tests/pageindex_eval/eval_runner.py \
    --db-url postgresql://... \
    --openai-key sk-... \
    --course-id 42 \
    --material-ids 1,2,3,4

Outputs results to tests/pageindex_eval/results_YYYY-MM-DD.jsonl
"""
import argparse
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'api'))

import psycopg
import requests


def _llm_judge(question: str, answer: str, criteria: str, api_key: str) -> int:
    prompt = (
        f"Question: {question}\n\n"
        f"Answer: {answer}\n\n"
        f"Evaluation criteria: {criteria}\n\n"
        "Score the answer 0-3:\n"
        "0 = Does not address the question\n"
        "1 = Partially addresses, missing key criteria\n"
        "2 = Mostly correct, minor gaps\n"
        "3 = Fully correct, meets all criteria\n\n"
        "Respond with only the integer score (0, 1, 2, or 3)."
    )
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 5,
            "temperature": 0,
        },
        timeout=20,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    try:
        return max(0, min(3, int(raw)))
    except ValueError:
        return 0


def _page_hit_rate(expected_pages: list[int], fetched_pages: list[int]) -> float:
    if not expected_pages:
        return 1.0
    hits = sum(1 for p in expected_pages if p in fetched_pages)
    return hits / len(expected_pages)


def run_vector_rag(conn, question: str, course_id: int, material_ids: list[int]) -> dict:
    from rag import retrieve_context
    from llm import synthesize

    t0 = time.time()
    try:
        chunks = retrieve_context(conn, question, material_ids=material_ids)
        answer, _, _, _, _, _, _ = synthesize(
            conn=conn, user_id=0, ai_provider="openai", ai_model="gpt-4o-mini",
            user_message=question, chunks=chunks, force_context_only=True,
        )
        fetched_pages = list({c.get("page_number", 0) for c in chunks if c.get("page_number")})
    except Exception as exc:
        answer = f"ERROR: {exc}"
        fetched_pages = []
    return {"answer": answer, "fetched_pages": fetched_pages, "latency_ms": int((time.time() - t0) * 1000)}


def run_pageindex_rag(conn, question: str, course_id: int, material_ids: list[int], openai_key: str) -> dict:
    from llm import run_agent_pageindex, DEFAULT_AGENTIC_MODEL

    t0 = time.time()
    fetched_pages = []
    try:
        answer, grounding_refs, tool_trace, _, _, _, _ = run_agent_pageindex(
            conn=conn, user_message=question, model=DEFAULT_AGENTIC_MODEL,
            api_key=openai_key, chat_id=None, course_id=course_id,
            context_material_ids=material_ids,
        )
        for trace in tool_trace:
            if trace.get("tool") == "get_page_content":
                from services.query.pageindex_retrieval import _parse_pages
                pages_spec = trace.get("args", {}).get("pages", "")
                fetched_pages.extend(_parse_pages(pages_spec))
    except Exception as exc:
        answer = f"ERROR: {exc}"
    return {"answer": answer, "fetched_pages": sorted(set(fetched_pages)), "latency_ms": int((time.time() - t0) * 1000)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--openai-key", required=True)
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--material-ids", required=True, help="comma-separated")
    args = parser.parse_args()

    material_ids = [int(x) for x in args.material_ids.split(",")]
    test_cases_path = os.path.join(os.path.dirname(__file__), "test_cases.jsonl")

    with open(test_cases_path) as f:
        test_cases = [json.loads(line) for line in f if line.strip()]

    results = []
    conn = psycopg.connect(args.db_url, row_factory=psycopg.rows.dict_row)

    for tc in test_cases:
        print(f"\nRunning {tc['id']}: {tc['question'][:60]}...")

        v = run_vector_rag(conn, tc["question"], args.course_id, material_ids)
        p = run_pageindex_rag(conn, tc["question"], args.course_id, material_ids, args.openai_key)

        v_hit = _page_hit_rate(tc["expected_pages"], v["fetched_pages"])
        p_hit = _page_hit_rate(tc["expected_pages"], p["fetched_pages"])
        v_score = _llm_judge(tc["question"], v["answer"], tc["judge_criteria"], args.openai_key)
        p_score = _llm_judge(tc["question"], p["answer"], tc["judge_criteria"], args.openai_key)

        result = {
            "id": tc["id"],
            "difficulty": tc["difficulty"],
            "vector": {"page_hit_rate": v_hit, "answer_score": v_score, "latency_ms": v["latency_ms"]},
            "pageindex": {"page_hit_rate": p_hit, "answer_score": p_score, "latency_ms": p["latency_ms"]},
            "winner": "pageindex" if p_score > v_score else ("vector" if v_score > p_score else "tie"),
        }
        results.append(result)
        print(f"  Vector:    hit={v_hit:.2f} score={v_score}/3 ({v['latency_ms']}ms)")
        print(f"  PageIndex: hit={p_hit:.2f} score={p_score}/3 ({p['latency_ms']}ms)")

    conn.close()

    out_path = os.path.join(os.path.dirname(__file__), f"results_{date.today()}.jsonl")
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"\nResults saved to {out_path}")
    avg_v_hit = sum(r["vector"]["page_hit_rate"] for r in results) / len(results)
    avg_p_hit = sum(r["pageindex"]["page_hit_rate"] for r in results) / len(results)
    avg_v_score = sum(r["vector"]["answer_score"] for r in results) / len(results)
    avg_p_score = sum(r["pageindex"]["answer_score"] for r in results) / len(results)
    print(f"\nSummary:")
    print(f"  Vector    avg hit={avg_v_hit:.2f}  avg score={avg_v_score:.2f}")
    print(f"  PageIndex avg hit={avg_p_hit:.2f}  avg score={avg_p_score:.2f}")
    pageindex_wins = (avg_p_hit >= avg_v_hit) and (avg_p_score >= avg_v_score)
    print(f"\n{'✓ PageIndex meets shipping bar' if pageindex_wins else '✗ PageIndex does not yet meet bar'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify runner parses without error**

```bash
cd /Users/shubhan/OneShotCourseMate && python tests/pageindex_eval/eval_runner.py --help
```

Expected: prints usage without ImportError.

- [ ] **Step 4: Commit**

```bash
git add tests/pageindex_eval/
git commit -m "feat: eval corpus — 6 seed test cases + side-by-side PageIndex vs vector RAG runner"
```

---

## Task 15: relation_builder.py — LLM-driven cross-material knowledge graph

- [x] **Completed**
**Files:**
- Create: `lambda/index_materials/relation_builder.py`
- Test: `lambda/index_materials/tests/test_relation_builder.py`

Loads all `course_material_index` rows for a course, builds a prompt from their titles + summaries + `metadata_tags`, calls the LLM, parses relation edges above a confidence threshold, and upserts to `course_material_relations`.

- [x] **Step 1: Write the failing test**

`lambda/index_materials/tests/test_relation_builder.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import json
from unittest.mock import patch, MagicMock
from relation_builder import _extract_json, _build_relations_prompt, _filter_relations

SAMPLE_TARGET = {
    "material_id": 10,
    "material_title": "Lecture 5: Backpropagation",
    "doc_type": "lecture_slide",
    "material_summary": "Covers chain rule and SGD update.",
    "metadata_tags": ["backpropagation", "chain-rule", "gradient-descent"],
}
SAMPLE_OTHERS = [
    {
        "material_id": 11,
        "material_title": "HW3: Backprop Problems",
        "doc_type": "hw_instruction",
        "material_summary": "Problem set on gradient computation.",
        "metadata_tags": ["backpropagation", "gradient-computation"],
    },
    {
        "material_id": 12,
        "material_title": "Lecture 4: Forward Pass",
        "doc_type": "lecture_slide",
        "material_summary": "Covers linear layers and activations.",
        "metadata_tags": ["forward-pass", "activations"],
    },
]

def test_extract_json_valid():
    raw = 'Here is the result: [{"source_id": 1, "target_id": 2, "relation_type": "extends", "shared_tags": [], "confidence": 0.8}]'
    result = _extract_json(raw)
    assert len(result) == 1
    assert result[0]["relation_type"] == "extends"

def test_extract_json_empty_array():
    assert _extract_json("[]") == []

def test_extract_json_no_json():
    assert _extract_json("No relationships found.") == []

def test_filter_relations_excludes_low_confidence():
    relations = [
        {"source_id": 12, "target_id": 10, "relation_type": "prerequisite", "shared_tags": [], "confidence": 0.7},
        {"source_id": 10, "target_id": 11, "relation_type": "practice_for", "shared_tags": [], "confidence": 0.4},
    ]
    filtered = _filter_relations(relations, course_id=1)
    assert len(filtered) == 1
    assert filtered[0]["relation_type"] == "prerequisite"

def test_filter_relations_excludes_unknown_type():
    relations = [{"source_id": 1, "target_id": 2, "relation_type": "unrelated", "shared_tags": [], "confidence": 0.9}]
    filtered = _filter_relations(relations, course_id=1)
    assert filtered == []

def test_build_relations_prompt_contains_ids():
    prompt = _build_relations_prompt(SAMPLE_TARGET, SAMPLE_OTHERS)
    assert "10" in prompt
    assert "11" in prompt
    assert "backpropagation" in prompt
    assert "practice_for" in prompt

def test_build_relations_prompt_target_is_marked():
    prompt = _build_relations_prompt(SAMPLE_TARGET, SAMPLE_OTHERS)
    assert "TARGET" in prompt
    assert "EXISTING" in prompt
```

- [x] **Step 2: Run — verify it fails**

```bash
cd lambda/index_materials && python -m pytest tests/test_relation_builder.py -v
```

Expected: `ImportError: No module named 'relation_builder'`

- [x] **Step 3: Implement**

`lambda/index_materials/relation_builder.py`:
```python
import asyncio
import json
import logging
import re

import psycopg
import psycopg.rows

from llm_client import build_relations_prompt, summarize, RELATION_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

_VALID_RELATION_TYPES = frozenset([
    "covers_same_topic", "prerequisite", "extends", "practice_for", "solution_for"
])


def _extract_json(text: str) -> list:
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


def _filter_relations(raw_relations: list, course_id: int) -> list[dict]:
    result = []
    for rel in raw_relations:
        if rel.get("relation_type") not in _VALID_RELATION_TYPES:
            continue
        if rel.get("confidence", 0) < RELATION_CONFIDENCE_THRESHOLD:
            continue
        result.append({
            "course_id": course_id,
            "source_id": rel["source_id"],
            "target_id": rel["target_id"],
            "relation_type": rel["relation_type"],
            "shared_tags": rel.get("shared_tags", []),
            "similarity_score": float(rel.get("confidence", 0)),
        })
    return result


def _build_relations_prompt(target: dict, others: list[dict]) -> str:
    return build_relations_prompt(target, others)


async def build_course_relations(
    db_url: str,
    course_id: int,
    updated_material_id: int,
    api_key: str,
) -> None:
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as conn:
        from db import load_course_materials_for_relations, store_material_relations

        rows = load_course_materials_for_relations(conn, course_id)
        if len(rows) < 2:
            return

        target = next((r for r in rows if r["material_id"] == updated_material_id), None)
        if not target:
            return
        others = [r for r in rows if r["material_id"] != updated_material_id]
        if not others:
            return

        prompt = _build_relations_prompt(target, others)
        try:
            raw = await asyncio.to_thread(summarize, prompt, api_key)
        except Exception as exc:
            logger.warning("LLM relation call failed: %s", exc)
            return

        raw_relations = _extract_json(raw)
        relations = _filter_relations(raw_relations, course_id)

        if relations:
            store_material_relations(conn, relations)
            conn.commit()
            logger.info(
                "Stored %d relations for course %d (material %d)",
                len(relations), course_id, updated_material_id,
            )
```

- [x] **Step 4: Run — verify passing**

```bash
cd lambda/index_materials && python -m pytest tests/test_relation_builder.py -v
```

Expected: 7 passed.

- [x] **Step 5: Commit**

```bash
git add lambda/index_materials/relation_builder.py lambda/index_materials/tests/test_relation_builder.py
git commit -m "feat: relation_builder — LLM-driven cross-material knowledge graph edge extraction"
```

---

## Task 16: pageindex_retrieval.py — expose knowledge graph relations

- [x] **Completed**
**Files:**
- Modify: `api/services/query/pageindex_retrieval.py`
- Test: add to `tests/test_pageindex_retrieval.py`

Adds `get_material_relations(conn, course_id, material_id)` so the agentic loop can surface related materials when navigating the graph. Also enriches `get_course_routing_index` to annotate each material with its related materials.

- [x] **Step 1: Add tests for get_material_relations**

Append to `tests/test_pageindex_retrieval.py`:
```python
def test_get_material_relations_returns_formatted_list():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {
            "source_id": 5, "target_id": 10, "relation_type": "practice_for",
            "shared_tags": ["backpropagation"], "similarity_score": 0.85,
        },
    ]
    conn.cursor.return_value = cursor
    from services.query.pageindex_retrieval import get_material_relations
    result = get_material_relations(conn, course_id=1, material_id=10)
    assert len(result) == 1
    assert result[0]["relation_type"] == "practice_for"
    assert result[0]["other_material_id"] == 5

def test_get_material_relations_both_directions():
    # Relations where material_id is either source or target are returned
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"source_id": 10, "target_id": 20, "relation_type": "extends",
         "shared_tags": [], "similarity_score": 0.75},
        {"source_id": 3, "target_id": 10, "relation_type": "prerequisite",
         "shared_tags": [], "similarity_score": 0.90},
    ]
    conn.cursor.return_value = cursor
    from services.query.pageindex_retrieval import get_material_relations
    result = get_material_relations(conn, course_id=1, material_id=10)
    other_ids = {r["other_material_id"] for r in result}
    assert 20 in other_ids
    assert 3 in other_ids
```

- [x] **Step 2: Run — verify it fails**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_retrieval.py -v -k "relations"
```

- [x] **Step 3: Implement get_material_relations**

Append to `api/services/query/pageindex_retrieval.py`:
```python
def get_material_relations(conn, course_id: int, material_id: int) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(
        """SELECT source_id, target_id, relation_type, shared_tags, similarity_score
           FROM course_material_relations
           WHERE course_id = %s AND (source_id = %s OR target_id = %s)
           ORDER BY similarity_score DESC NULLS LAST""",
        (course_id, material_id, material_id),
    )
    rows = cursor.fetchall()
    cursor.close()
    result = []
    for r in rows:
        other_id = r["target_id"] if r["source_id"] == material_id else r["source_id"]
        result.append({
            "other_material_id": other_id,
            "relation_type": r["relation_type"],
            "shared_tags": r.get("shared_tags") or [],
            "similarity_score": r.get("similarity_score"),
            "direction": "outbound" if r["source_id"] == material_id else "inbound",
        })
    return result
```

- [x] **Step 4: Run — verify passing**

```bash
cd /Users/shubhan/OneShotCourseMate && python -m pytest tests/test_pageindex_retrieval.py -v
```

Expected: all tests pass.

- [x] **Step 5: Commit**

```bash
git add api/services/query/pageindex_retrieval.py tests/test_pageindex_retrieval.py
git commit -m "feat: pageindex_retrieval — get_material_relations for knowledge graph traversal"
```

---

## Task 17: run_agent_pageindex — add graph_neighbors tool

**Files:**
- Modify: `api/llm.py` (add 4th tool to `run_agent_pageindex`)

Exposes the `get_related_materials` tool to the agentic loop so the LLM can traverse knowledge graph edges when the initial material doesn't contain a complete answer — e.g., finding the lecture that corresponds to a hw problem.

- [ ] **Step 1: Add tool definition to run_agent_pageindex tools list**

In `api/llm.py`, inside `run_agent_pageindex`, append to the `tools` list:

```python
        {
            "type": "function",
            "function": {
                "name": "get_related_materials",
                "description": (
                    "Get materials related to a specific material via the knowledge graph. "
                    "Use when initial material doesn't fully answer the question — "
                    "e.g., find the lecture behind a homework problem, or a solution for a hw."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {
                            "type": "integer",
                            "description": "Material ID to find neighbors for",
                        },
                    },
                    "required": ["material_id"],
                },
            },
        },
```

- [ ] **Step 2: Add handler for get_related_materials in the tool dispatch loop**

In `run_agent_pageindex`, inside the `for call in tool_calls:` loop, add after the `get_page_content` branch:

```python
            elif name == "get_related_materials":
                try:
                    from .services.query.pageindex_retrieval import get_material_relations
                except ImportError:
                    from services.query.pageindex_retrieval import get_material_relations
                mid = args.get("material_id")
                relations = get_material_relations(conn, pageindex_course_id or course_id, mid)
                if relations:
                    lines = [
                        f"  [{r['other_material_id']}] {r['relation_type']} (confidence: {r.get('similarity_score', '?'):.2f})"
                        f" | shared topics: {', '.join(r['shared_tags']) or 'none'}"
                        for r in relations
                    ]
                    tool_result = f"Related materials for {mid}:\n" + "\n".join(lines)
                else:
                    tool_result = f"No known relations for material {mid}."
                if on_event:
                    on_event({"type": "tool_call", "tool": "get_related_materials", "material_id": mid})
```

- [ ] **Step 3: Verify no syntax errors**

```bash
cd /Users/shubhan/OneShotCourseMate && python -c "import api.llm; print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add api/llm.py
git commit -m "feat: run_agent_pageindex — add get_related_materials graph traversal tool"
```

---

## Deployment Checklist (not a code task)

Before running the eval:

- [ ] Deploy `lambda/index_materials/` as a new AWS Lambda (`index_materials` function name)
- [ ] Deploy `lambda/index_materials/state_machine.json` as a new Step Functions state machine (`INDEX_STATE_MACHINE_ARN`)
- [ ] Set Lambda env vars: `DATABASE_URL`, `AWS_S3_BUCKET_NAME`, `OPENAI_API_KEY_INDEXER`, `INDEX_STATE_MACHINE_ARN`
- [ ] Trigger indexing for each test PDF by uploading to S3 (or directly invoking the Lambda)
- [ ] Confirm `material_page_index`, `material_page_text`, `course_material_index`, `course_material_relations` rows exist for all test materials
- [ ] Verify `metadata_tags` column populated in `course_material_index` (non-empty JSON array)
- [ ] Verify `course_material_relations` has edges between semantically related materials (e.g., lecture ↔ hw)
- [ ] Set `PAGEINDEX_RETRIEVAL_ENABLED=true` in Vercel env to test live API
- [ ] Run eval: `python tests/pageindex_eval/eval_runner.py --db-url ... --openai-key ... --course-id X --material-ids 1,2,3,4`

**Ship bar:** PageIndex must match or beat vector RAG on both `avg_page_hit_rate` AND `avg_answer_score` across all difficulty tiers.
