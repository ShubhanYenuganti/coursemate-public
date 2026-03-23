# Hybrid RAG — Claude Code Implementation Spec
## Voyage multimodal-3.5 + voyage-3.5 · Neon Postgres + pgvector · GPT-4o-mini agent

> Status: Historical design reference.  
> Current production direction has consolidated away `messages`/`chat_sessions` and uses
> `chat_messages.message_embedding` for conversation embeddings, with retrieval on
> `documents` + `chunks` only.

---

## Context

This spec describes a complete implementation of an agentic RAG system with hybrid
visual + text retrieval. The codebase already has a Neon Postgres connection (pooler,
production branch). Everything below integrates into that existing setup.

**Do not create new infrastructure.** Work with the existing Neon DB, add tables/columns
as described, and wire up two new services (ingestion worker + query API).

---

## 2. Dependencies

```
# requirements.txt additions
voyageai>=0.3.0
openai>=1.0.0
pymupdf>=1.24.0          # fitz — PDF rendering and text extraction
pymupdf4llm>=0.0.17      # markdown + math-preserving text extraction
Pillow>=10.0.0
asyncpg>=0.29.0
httpx>=0.27.0
pgvector                 # psycopg2/asyncpg vector type support
```

---

## 3. Schema migrations

Run these against the existing Neon DB. If a `chunks` or `messages` table already
exists, apply only the `ALTER` and `CREATE INDEX` statements. If starting fresh,
run the full `CREATE TABLE` blocks.

```sql
-- Enable extensions (idempotent)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Documents: one row per source file
CREATE TABLE IF NOT EXISTS documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_uri   TEXT NOT NULL,
    modality     TEXT NOT NULL,   -- 'pdf' | 'image' | 'text' | 'table'
    raw_content  TEXT,
    metadata     JSONB DEFAULT '{}',
    ingested_at  TIMESTAMPTZ DEFAULT now()
);

-- Chunks: two rows per PDF page (retrieval_type = 'visual' | 'text')
-- Both use the same 1024-dim vector column — voyage-multimodal-3.5 and
-- voyage-3.5 both output 1024 dims by default, so no dimension mismatch.
CREATE TABLE IF NOT EXISTS chunks (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id    UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content        TEXT NOT NULL,
    retrieval_type TEXT NOT NULL DEFAULT 'visual',  -- 'visual' | 'text'
    embedding      VECTOR(1024) NOT NULL,
    chunk_index    INT NOT NULL,
    modal_meta     JSONB DEFAULT '{}'
);

-- Chat sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID,
    created_at    TIMESTAMPTZ DEFAULT now(),
    session_meta  JSONB DEFAULT '{}'
);

-- Messages: stores both user and assistant turns with embeddings for grounding
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content         TEXT NOT NULL,
    embedding       VECTOR(1024),
    tool_calls      JSONB DEFAULT '[]',
    grounding_refs  JSONB DEFAULT '[]',   -- chunk UUIDs that grounded this answer
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Web search cache (TTL-based, avoids re-querying Brave within a session)
CREATE TABLE IF NOT EXISTS web_cache (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash   TEXT NOT NULL UNIQUE,
    url          TEXT NOT NULL,
    snippet      TEXT NOT NULL,
    fetched_at   TIMESTAMPTZ DEFAULT now(),
    ttl_seconds  INT DEFAULT 3600
);

-- Indexes
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS chunks_doc_page_type_idx
    ON chunks (document_id, chunk_index, retrieval_type);
CREATE INDEX IF NOT EXISTS messages_session_idx
    ON messages (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS messages_embedding_idx
    ON messages USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX IF NOT EXISTS web_cache_hash_idx
    ON web_cache (query_hash);
```

---

## 4. Ingestion worker

**File:** `services/ingestion/worker.py`

Each PDF page produces exactly **two** chunk rows:
- `retrieval_type = 'visual'` — PNG rendered at 150 DPI, embedded with
  `voyage-multimodal-3.5`
- `retrieval_type = 'text'` — Markdown text extracted with `pymupdf4llm`
  (preserves math notation), embedded with `voyage-3.5`

Both embedding calls happen concurrently via `asyncio.gather`.

```python
import asyncio, base64, hashlib, json, os, uuid
import fitz                          # pymupdf
import pymupdf4llm
import asyncpg
import voyageai
from pathlib import Path

vo = voyageai.AsyncClient(api_key=os.environ["VOYAGE_API_KEY"])
DATABASE_URL = os.environ["DATABASE_URL"]


# ── Rendering helpers ────────────────────────────────────────────────────────

def render_page_png(pdf_path: str, page_num: int, dpi: int = 150) -> bytes:
    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    return doc[page_num].get_pixmap(matrix=mat).tobytes("png")


def extract_page_text(pdf_path: str, page_num: int) -> str:
    """
    pymupdf4llm produces Markdown with math fenced as $$...$$
    Falls back to plain get_text() if it returns nothing useful.
    """
    try:
        doc = fitz.open(pdf_path)
        md = pymupdf4llm.to_markdown(doc, pages=[page_num])
        return md.strip()
    except Exception:
        doc = fitz.open(pdf_path)
        return doc[page_num].get_text("text").strip()


# ── Embedding helpers ────────────────────────────────────────────────────────

async def embed_visual(png_bytes: bytes) -> list[float]:
    b64 = base64.standard_b64encode(png_bytes).decode()
    result = await vo.multimodal_embed(
        inputs=[[{"type": "image_base64",
                  "image_base64": f"data:image/png;base64,{b64}"}]],
        model="voyage-multimodal-3.5",
        input_type="document",
    )
    return result.embeddings[0]


async def embed_text(text: str) -> list[float] | None:
    if not text:
        return None
    result = await vo.embed(
        texts=[text],
        model="voyage-3.5",
        input_type="document",
    )
    return result.embeddings[0]


# ── Core ingestion ───────────────────────────────────────────────────────────

async def ingest_pdf(pdf_path: str, metadata: dict = {}):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        doc_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO documents (id, source_uri, modality, metadata)
               VALUES ($1, $2, 'pdf', $3)""",
            doc_id, pdf_path, json.dumps(metadata),
        )

        pdf = fitz.open(pdf_path)
        for page_num in range(len(pdf)):
            await process_page(conn, doc_id, pdf_path, page_num)
            print(f"  ingested page {page_num + 1}/{len(pdf)}")

    finally:
        await conn.close()


async def process_page(conn, doc_id: str, pdf_path: str, page_num: int):
    # Extract both representations
    png_bytes = render_page_png(pdf_path, page_num, dpi=150)
    text = extract_page_text(pdf_path, page_num)

    # Embed both concurrently
    visual_emb, text_emb = await asyncio.gather(
        embed_visual(png_bytes),
        embed_text(text),
    )

    rows = []

    # Visual chunk — always created
    rows.append((
        doc_id,
        page_num,
        "visual",
        f"[visual] page {page_num + 1}",   # content label; PNG not stored in DB
        json.dumps(visual_emb),
        json.dumps({"dpi": 150, "has_text": bool(text)}),
    ))

    # Text chunk — only if extraction yielded content
    if text_emb is not None:
        rows.append((
            doc_id,
            page_num,
            "text",
            text,
            json.dumps(text_emb),
            json.dumps({"char_count": len(text), "extractor": "pymupdf4llm"}),
        ))

    await conn.executemany(
        """INSERT INTO chunks
             (document_id, chunk_index, retrieval_type, content, embedding, modal_meta)
           VALUES ($1, $2, $3, $4, $5::vector, $6)""",
        rows,
    )
```

---

## 5. Query service

**File:** `services/query/retrieval.py`

### 5a. Embed query (both modalities)

```python
async def embed_query_visual(query: str) -> list[float]:
    result = await vo.multimodal_embed(
        inputs=[[query]],
        model="voyage-multimodal-3.5",
        input_type="query",
    )
    return result.embeddings[0]


async def embed_query_text(query: str) -> list[float]:
    result = await vo.embed(
        texts=[query],
        model="voyage-3.5",
        input_type="query",
    )
    return result.embeddings[0]
```

### 5b. ANN search per retrieval type

```python
async def search_chunks(
    conn, embedding: list[float], retrieval_type: str, top_k: int
) -> list[dict]:
    rows = await conn.fetch(
        """SELECT id, document_id, chunk_index, content,
                  retrieval_type, modal_meta,
                  embedding <=> $1::vector AS distance
           FROM chunks
           WHERE retrieval_type = $2
           ORDER BY distance ASC
           LIMIT $3""",
        json.dumps(embedding), retrieval_type, top_k,
    )
    return [dict(r) for r in rows]
```

### 5c. Reciprocal Rank Fusion (RRF)

Deduplication is by `(document_id, chunk_index)` — not chunk UUID — because the
same page has two different chunk rows.

```python
def reciprocal_rank_fusion(
    visual_hits: list[dict],
    text_hits: list[dict],
    visual_weight: float = 0.5,
    text_weight: float = 0.5,
    k: int = 60,
) -> list[dict]:
    scores: dict[str, float] = {}
    best_row: dict[str, dict] = {}

    def page_key(row):
        return f"{row['document_id']}:{row['chunk_index']}"

    for rank, row in enumerate(visual_hits):
        pk = page_key(row)
        scores[pk] = scores.get(pk, 0.0) + visual_weight / (k + rank + 1)
        best_row.setdefault(pk, row)

    for rank, row in enumerate(text_hits):
        pk = page_key(row)
        scores[pk] = scores.get(pk, 0.0) + text_weight / (k + rank + 1)
        # Prefer text row for context display — has actual extracted content
        if row["retrieval_type"] == "text":
            best_row[pk] = row

    return [
        best_row[pk]
        for pk, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ]
```

### 5d. Weight heuristic

Automatically shifts weight toward text search for math/definition queries,
toward visual for diagram/layout queries.

```python
_TEXT_SIGNALS  = {"equation","formula","proof","theorem","definition",
                  "variable","integral","derivative","matrix","algorithm",
                  "calculate","compute","syntax","step"}
_VISUAL_SIGNALS = {"diagram","figure","chart","graph","table","image",
                   "plot","illustration","slide","layout","arrow","label"}

def infer_weights(query: str) -> tuple[float, float]:
    q = set(query.lower().split())
    t = len(q & _TEXT_SIGNALS)
    v = len(q & _VISUAL_SIGNALS)
    if t > v:   return 0.25, 0.75   # lean text
    if v > t:   return 0.75, 0.25   # lean visual
    return 0.5, 0.5                 # balanced
```

### 5e. Main hybrid search entry point

```python
async def hybrid_vector_search(
    conn,
    query: str,
    top_k: int = 8,
    modality_hint: str = "balanced",   # 'text' | 'visual' | 'balanced'
) -> tuple[str, list[str]]:

    WEIGHT_MAP = {
        "text":     (0.25, 0.75),
        "visual":   (0.75, 0.25),
        "balanced": infer_weights(query),
    }
    vis_w, txt_w = WEIGHT_MAP[modality_hint]

    # Embed query for both models concurrently
    vis_emb, txt_emb = await asyncio.gather(
        embed_query_visual(query),
        embed_query_text(query),
    )

    # Search both indexes concurrently, fetch 2× top_k each for RRF headroom
    vis_hits, txt_hits = await asyncio.gather(
        search_chunks(conn, vis_emb, "visual", top_k * 2),
        search_chunks(conn, txt_emb, "text",   top_k * 2),
    )

    merged = reciprocal_rank_fusion(vis_hits, txt_hits, vis_w, txt_w)[:top_k]

    chunk_ids = [str(r["id"]) for r in merged]
    context = "\n\n---\n\n".join(
        f"[doc:{r['document_id']} page:{r['chunk_index'] + 1}]\n"
        f"{r['content'] if r['retrieval_type'] == 'text' else '[visual page]'}"
        for r in merged
    )
    return context, chunk_ids
```

---

## 6. Grounding context pull

Called before every agent invocation. Pulls two things from Postgres:
1. Cosine-similar messages from the current session (recent conversation context)
2. Chunk UUIDs recorded in `grounding_refs` of recent assistant turns (direct
   lookup of pages that grounded prior answers — not cosine-dependent)

```python
async def pull_grounding_context(
    conn, session_id: str, query_embedding: list[float]
) -> tuple[list[dict], list[dict]]:

    # 1 — similar messages in this session
    similar_msgs = await conn.fetch(
        """SELECT content, role, grounding_refs,
                  embedding <=> $1::vector AS distance
           FROM messages
           WHERE session_id = $2
           ORDER BY distance ASC
           LIMIT 5""",
        json.dumps(query_embedding), session_id,
    )

    # 2 — chunks cited in recent assistant turns
    cited_ids = []
    for msg in similar_msgs:
        refs = msg["grounding_refs"]
        if refs:
            cited_ids.extend(json.loads(refs) if isinstance(refs, str) else refs)

    cited_chunks = []
    if cited_ids:
        cited_chunks = await conn.fetch(
            """SELECT id, content, retrieval_type, modal_meta
               FROM chunks WHERE id = ANY($1::uuid[])""",
            list(set(cited_ids)),
        )

    return [dict(m) for m in similar_msgs], [dict(c) for c in cited_chunks]
```

---

## 7. GPT-4o-mini agent loop

**File:** `services/query/agent.py`

### 7a. Tool definitions

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "vector_search",
            "description": (
                "Hybrid visual + text search over ingested documents. "
                "Set modality_hint='text' for equations, definitions, proofs. "
                "Set 'visual' for diagrams, figures, layout questions. "
                "Leave as 'balanced' when unsure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query":         {"type": "string"},
                    "modality_hint": {"type": "string",
                                      "enum": ["text", "visual", "balanced"],
                                      "default": "balanced"},
                    "top_k":         {"type": "integer", "default": 8},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the live web for information not in the document corpus. "
                "Results are cached per session."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rerank",
            "description": (
                "Re-score retrieved chunks against the query using Voyage Rerank. "
                "Call when vector_search results look ambiguous or the query is "
                "very specific."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query":     {"type": "string"},
                    "chunk_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["query", "chunk_ids"],
            },
        },
    },
]
```

### 7b. Agent loop

```python
from openai import AsyncOpenAI

oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


async def run_agent(
    conn,
    session_id: str,
    user_message: str,
) -> tuple[str, list[str]]:
    """
    Returns (answer_text, grounding_refs).
    Caller is responsible for persisting both the user message and
    the assistant response to the messages table.
    """

    # 1. Embed query (text model — for grounding pull only)
    query_emb = await embed_query_text(user_message)

    # 2. Pull session grounding context
    similar_msgs, cited_chunks = await pull_grounding_context(
        conn, session_id, query_emb
    )

    # 3. Build system prompt with grounding context
    system = build_system_prompt(similar_msgs, cited_chunks)

    messages = [
        {"role": "system",  "content": system},
        {"role": "user",    "content": user_message},
    ]
    all_grounding_refs: list[str] = []

    # 4. Agentic tool-calling loop
    while True:
        response = await oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )
        choice = response.choices[0]

        if choice.finish_reason == "stop":
            return choice.message.content, all_grounding_refs

        if choice.finish_reason == "tool_calls":
            messages.append(choice.message)

            for tc in choice.message.tool_calls:
                args = json.loads(tc.function.arguments)
                name = tc.function.name

                if name == "vector_search":
                    result, refs = await hybrid_vector_search(
                        conn,
                        query=args["query"],
                        top_k=args.get("top_k", 8),
                        modality_hint=args.get("modality_hint", "balanced"),
                    )
                    all_grounding_refs.extend(refs)

                elif name == "web_search":
                    result = await execute_web_search(conn, args["query"])

                elif name == "rerank":
                    result = await execute_rerank(
                        args["query"], args["chunk_ids"], conn
                    )

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result,
                })


def build_system_prompt(
    similar_msgs: list[dict], cited_chunks: list[dict]
) -> str:
    parts = [
        "You are a helpful assistant. Answer questions using the retrieved "
        "document context below. Cite page numbers when referencing specific content."
    ]
    if cited_chunks:
        parts.append("\n[Previously retrieved pages that grounded recent answers]")
        for c in cited_chunks:
            parts.append(c["content"][:500])   # truncate long pages
    if similar_msgs:
        parts.append("\n[Recent relevant exchanges]")
        for m in similar_msgs:
            parts.append(f"{m['role'].upper()}: {m['content'][:300]}")
    return "\n".join(parts)
```

---

## 8. Web search tool with Postgres caching

```python
import hashlib, httpx

async def execute_web_search(conn, query: str) -> str:
    h = hashlib.sha256(query.encode()).hexdigest()

    cached = await conn.fetchrow(
        """SELECT snippet FROM web_cache
           WHERE query_hash = $1
             AND fetched_at + (ttl_seconds * interval '1 second') > now()""",
        h,
    )
    if cached:
        return cached["snippet"]

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json",
                     "X-Subscription-Token": os.environ["BRAVE_API_KEY"]},
            params={"q": query, "count": 5},
        )
    results = resp.json().get("web", {}).get("results", [])
    snippet = "\n\n".join(
        f"{r['title']}\n{r['url']}\n{r.get('description', '')}"
        for r in results
    )

    await conn.execute(
        """INSERT INTO web_cache (query_hash, url, snippet)
           VALUES ($1, $2, $3)
           ON CONFLICT (query_hash)
           DO UPDATE SET snippet = EXCLUDED.snippet, fetched_at = now()""",
        h,
        results[0]["url"] if results else "",
        snippet,
    )
    return snippet
```

---

## 9. Persist message after each turn

Call this after both the user message and the agent's final response to keep the
`messages` table current for future grounding pulls.

```python
async def persist_message(
    conn,
    session_id: str,
    role: str,
    content: str,
    tool_calls: list = [],
    grounding_refs: list[str] = [],
):
    emb = await embed_query_text(content)
    await conn.execute(
        """INSERT INTO messages
             (session_id, role, content, embedding, tool_calls, grounding_refs)
           VALUES ($1, $2, $3, $4::vector, $5, $6)""",
        session_id,
        role,
        content,
        json.dumps(emb),
        json.dumps(tool_calls),
        json.dumps(grounding_refs),
    )
```

---

## 10. Per-turn request handler (wire-up)

This is the entry point for the chat API endpoint. Wire this to your existing
FastAPI/Flask route or whatever HTTP layer you have.

```python
async def handle_chat_turn(
    session_id: str,
    user_message: str,
) -> str:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # Persist user message
        await persist_message(conn, session_id, "user", user_message)

        # Run agent
        answer, grounding_refs = await run_agent(conn, session_id, user_message)

        # Persist assistant response with grounding refs
        await persist_message(
            conn, session_id, "assistant", answer,
            grounding_refs=grounding_refs,
        )

        return answer
    finally:
        await conn.close()
```

---

## 11. File layout

```
project/
├── services/
│   ├── ingestion/
│   │   └── worker.py          # sections 4 — renders + embeds PDFs
│   └── query/
│       ├── retrieval.py       # sections 5–6 — hybrid search + grounding pull
│       ├── agent.py           # sections 7–8 — GPT-4o-mini loop + web search
│       └── persistence.py     # section 9 — persist_message
├── api/
│   └── chat.py                # section 10 — HTTP handler, wire to your router
├── migrations/
│   └── 001_rag_schema.sql     # section 3 — full schema
└── requirements.txt
```

---

## 12. Key implementation notes for Claude Code

1. **Dimension alignment** — `voyage-multimodal-3.5` and `voyage-3.5` both default
   to 1024-dim output. The `VECTOR(1024)` column accepts both without any casting.
   Do not change the output dimension unless you also change the column definition.

2. **Two chunk rows per page** — the ingestion worker always inserts a `visual` row
   and inserts a `text` row only when `pymupdf4llm` returns non-empty content.
   Expect pages with only graphics (full-bleed diagrams, cover pages) to have only
   a `visual` row.

3. **RRF deduplication key** — dedup is by `(document_id, chunk_index)`, not by
   chunk UUID. A page match from the visual index and a page match from the text
   index are the same page and must be merged into one result with a combined score.

4. **Grounding refs** — `grounding_refs` in the `messages` table stores chunk UUIDs
   (not page numbers). The grounding pull in section 6 fetches these by primary key.
   This is what allows the agent to stay anchored to specific previously-cited pages
   across multiple turns without re-doing cosine search.

5. **Neon pooler + asyncpg** — the existing Neon pooler connection is in transaction
   mode (PgBouncer default). Do not use session-level features: no `SET LOCAL`,
   no advisory locks, no `LISTEN/NOTIFY`, no prepared statements with
   `asyncpg.prepare()`. Use direct query execution only.

6. **Voyage async client** — use `voyageai.AsyncClient` (not `voyageai.Client`)
   throughout to avoid blocking the event loop during embed calls. Both
   `multimodal_embed` and `embed` are available on the async client.

7. **DPI for rendering** — 150 DPI is the default. For textbook pages with small
   body text, pass `dpi=200` to `render_page_png`. For slides with large fonts,
   120 DPI is sufficient. The DPI value is stored in `modal_meta` for each chunk.

8. **Handwritten content** — the ingestion worker as written will produce a poor
   `text` chunk for handwritten pages (pymupdf4llm will return little or nothing).
   The `visual` chunk will still be created. If handwritten notes are part of the
   corpus, add an OCR branch: detect low text-yield pages
   (`len(text) < 50`), run them through GPT-4o-mini vision to extract text,
   store the result as the `text` chunk's content, and embed with `voyage-3.5`.

9. **Batch size for ingestion** — Voyage rate limits on the free tier are
   8M TPM / 2000 RPM (tier 1 after adding a payment method). Each page makes
   two embed calls. For bulk ingestion of large corpora, add a semaphore:
   `asyncio.Semaphore(10)` around `process_page` calls to cap concurrency.

10. **pgvector IVFFlat index** — the `ivfflat` index requires the table to be
    populated before it's useful. Run `ANALYZE chunks;` after bulk ingestion
    to update statistics. For corpora under ~10K chunks, a sequential scan
    is faster than IVFFlat anyway; the index pays off above ~50K chunks.