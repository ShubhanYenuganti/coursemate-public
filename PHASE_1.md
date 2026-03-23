# Phase 1: Embedding Upgrade + Multi-Provider LLM Synthesis

## Context

The current chat system returns raw chunk text as the "assistant response" — no LLM call is made. `api/chat.py _send_message()` calls `retrieve_chunks()`, formats the results as similarity-scored excerpts, and stores that string as `assistant_content`. The `user_api_keys` table holds encrypted Claude/OpenAI/Gemini keys and `api/crypto_utils.py` has a working `decrypt_api_key()`, but neither is ever invoked during chat.

Additionally, embeddings use `all-MiniLM-L6-v2` (384D) via sentence-transformers in both Lambda functions, with no asymmetric query/doc modes and a small dimension that limits retrieval quality.

Phase 1 delivers:
1. **Cohere Embed v3.5** replacing sentence-transformers in both Lambda functions (1024D, asymmetric `input_type`)
2. **Schema migration** from AWS RDS → **Neon Postgres**, including dimension change `vector(384)` → `vector(1024)`
3. **Multi-provider LLM synthesis** (Claude, OpenAI, Gemini) replacing the raw chunk dump in `_send_message()`

---

## Database: Migrate to Neon PostgreSQL

### Why Neon (aligned with AGENTIC_RAG_PLAN.md)

- pgvector pre-installed on all Neon instances — no `CREATE EXTENSION` setup needed
- **Database branching**: safely test the `vector(384)→1024` schema migration on a branch before applying to the main branch
- Built-in PgBouncer connection pooler — Vercel's serverless functions benefit from the pooler endpoint
- Autoscale-to-zero (set `min_compute_units=0.25` at ~$2/mo to keep partially warm and avoid 1–3s cold-start latency on the first request)

### Neon Connection Strings

Two endpoints are provided by Neon per project:

| Purpose | Endpoint type | Who uses it |
|---|---|---|
| Vercel serverless functions | **Pooler** (`pooler.neon.tech`) | `api/db.py` `DATABASE_URL` |
| Lambda functions + migrations | **Direct** (`neon.tech`) | `lambda/*/db.py` `DATABASE_URL`, migration scripts |

The pooler handles connection multiplexing across concurrent Vercel invocations. Lambdas are short-lived and issue few connections — they use the direct endpoint.

### Setup Steps

1. Create a Neon project at [neon.tech](https://neon.tech)
2. Set `min_compute_units=0.25` on the compute endpoint (Settings → Compute)
3. Copy the **pooler** connection string to Vercel's `DATABASE_URL` environment variable
4. Copy the **direct** connection string to both Lambda functions' `DATABASE_URL` environment variable

### Update `api/db.py` — connection pool size

Neon's free tier has a connection limit of ~100. Reduce `min_size` to avoid holding idle connections:

```python
# Change min_size from 2 → 1 to be friendly to Neon connection limits
_pool = ConnectionPool(
    conninfo=database_url,
    min_size=1,      # was 2
    max_size=10,
    kwargs={"row_factory": psycopg.rows.dict_row},
)
```

No other changes to `api/db.py` or `lambda/embed_materials/db.py` — both already read `DATABASE_URL` from the environment.

---

## Schema Migration

> Status: Historical migration notes for the pre-consolidation phase.  
> Current consolidation drops legacy `messages` and `material_chunks` after cutover; use
> `chat_messages.message_embedding` and `documents` + `chunks` as canonical runtime tables.

### Step 1: Create a Neon branch for safe migration

```bash
# Via Neon CLI or dashboard:
neon branches create --name phase-1-migration
# Connect to the branch and run migration SQL to verify before applying to main
```

### Step 2: Migration SQL (run on Neon direct connection)

```sql
-- Drop old 384D IVFFlat index
DROP INDEX IF EXISTS idx_chunks_embedding;

-- Change embedding dimension (destructive — existing embeddings must be re-ingested)
ALTER TABLE material_chunks ALTER COLUMN embedding TYPE vector(1024);

-- Recreate IVFFlat index at new dimension
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON material_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Invalidate all existing chunks so they get re-embedded on next material trigger
DELETE FROM material_chunks;
UPDATE material_embed_jobs
    SET status      = 'pending',
        started_at  = NULL,
        completed_at = NULL,
        error_message = NULL,
        chunks_created = NULL;

-- Phase 2 prep: conversation grounding via message embeddings
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_embedding vector(1024);
CREATE INDEX IF NOT EXISTS idx_messages_embedding
    ON chat_messages USING ivfflat (message_embedding vector_cosine_ops)
    WITH (lists = 50);

-- Phase 2 prep: web search cache (Tavily results with TTL)
CREATE TABLE IF NOT EXISTS web_cache (
    id           SERIAL PRIMARY KEY,
    query_hash   TEXT        NOT NULL UNIQUE,
    url          TEXT        NOT NULL,
    snippet      TEXT        NOT NULL,
    embedding    vector(1024),
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ttl_seconds  INT         NOT NULL DEFAULT 3600
);
CREATE INDEX IF NOT EXISTS idx_web_cache_hash ON web_cache(query_hash);
```

### Step 3: Update `api/db.py` `init_db()` for fresh installs

Update the `material_chunks` CREATE TABLE statement to use `vector(1024)` and the updated default model name. Add the `web_cache` table and `message_embedding` column so fresh Neon installs are correct without needing to run the migration SQL.

```python
# In material_chunks CREATE TABLE:
embedding   vector(1024)  NOT NULL,            # was vector(384)
model_name  VARCHAR(100)  NOT NULL DEFAULT 'cohere-embed-english-v3.0',  # was 'all-MiniLM-L6-v2'

# Add after chat_messages table definition:
cursor.execute("""
    ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_embedding vector(1024);
""")

# Add web_cache table:
cursor.execute("""
    CREATE TABLE IF NOT EXISTS web_cache (
        id          SERIAL PRIMARY KEY,
        query_hash  TEXT        NOT NULL UNIQUE,
        url         TEXT        NOT NULL,
        snippet     TEXT        NOT NULL,
        embedding   vector(1024),
        fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        ttl_seconds INT         NOT NULL DEFAULT 3600
    );
    CREATE INDEX IF NOT EXISTS idx_web_cache_hash ON web_cache(query_hash);
""")
```

---

## Lambda: `embed_query` — 3 files

### `lambda/embed_query/handler.py`

Replace the entire file:

```python
import json
import os
import cohere

_co = None

def _get_client():
    global _co
    if _co is None:
        _co = cohere.Client(os.environ['COHERE_API_KEY'])
    return _co

def lambda_handler(event, context):
    body = event if isinstance(event, dict) and 'query' in event \
           else json.loads(event.get('body', '{}'))
    query = body.get('query', '')
    if not query:
        return {'statusCode': 400, 'body': json.dumps({'error': 'query required'})}

    response = _get_client().embed(
        texts=[query],
        model='embed-english-v3.0',
        input_type='search_query',
    )
    embedding = response.embeddings[0]
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'embedding': embedding, 'dim': len(embedding)}),
    }
```

### `lambda/embed_query/requirements.txt`

```
cohere>=5.0.0
```

### `lambda/embed_query/Dockerfile`

Remove the sentence-transformers model bake-in line:

```dockerfile
# REMOVE:
RUN pip install --no-cache-dir awslambdaric -r requirements.txt && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# REPLACE WITH:
RUN pip install --no-cache-dir awslambdaric -r requirements.txt
```

---

## Lambda: `embed_materials` — 3 files

### `lambda/embed_materials/embedder.py`

Replace the entire file:

```python
"""
Cohere Embed v3.5 document embedder for the embed_materials Lambda.
Uses input_type='search_document' for asymmetric retrieval alignment.
"""
import os
import cohere
from typing import List, Dict, Any

_co = None

def _get_client() -> cohere.Client:
    global _co
    if _co is None:
        _co = cohere.Client(os.environ['COHERE_API_KEY'])
    return _co

def embed_chunks(chunks: List[Dict[str, Any]], batch_size: int = 96) -> List[Dict[str, Any]]:
    """
    Add an 'embedding' key (list[float], length 1024) to every chunk dict.
    Processes in batches of 96 (Cohere API maximum per call).
    Returns the same list mutated in-place.
    """
    client = _get_client()
    texts = [c['text'] for c in chunks]

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embed(
            texts=batch,
            model='embed-english-v3.0',
            input_type='search_document',
        )
        for chunk, vec in zip(chunks[i:i + batch_size], response.embeddings):
            chunk['embedding'] = vec

    return chunks
```

### `lambda/embed_materials/requirements.txt`

Replace `sentence-transformers==3.0.1` with `cohere>=5.0.0`:

```
cohere>=5.0.0
pymupdf==1.24.0
python-docx==1.1.2
openpyxl==3.1.5
Pillow==10.4.0
pytesseract==0.3.13
lxml==5.2.2
nltk==3.8.1
psycopg[binary]==3.3.3
boto3>=1.35.0
```

### `lambda/embed_materials/Dockerfile`

Remove the sentence-transformers bake-in line (same pattern as embed_query):

```dockerfile
# REMOVE:
RUN pip install --no-cache-dir awslambdaric -r requirements.txt && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# REPLACE WITH:
RUN pip install --no-cache-dir awslambdaric -r requirements.txt
```

---

## New file: `api/llm.py`

Multi-provider synthesis dispatcher. Phase 1 is single-turn (no tool use — that's Phase 2). All three provider SDKs are supported via the user's stored BYOK key.

```python
"""
Multi-provider LLM synthesis for OneShotCourseMate.

Phase 1: Single-turn synthesis — retrieved chunks injected as system context.
Phase 2 (agentic loop): Each provider's tool-calling format will be implemented here:
  - Claude:  Anthropic tool_use / tool_result blocks
  - OpenAI:  tools + tool_calls function calling format
  - Gemini:  tools with function_declarations + FunctionCall/FunctionResponse
"""
import json
from .crypto_utils import decrypt_api_key

SYSTEM_PROMPT = (
    "You are a helpful course assistant. Answer the user's question using the "
    "provided course material excerpts. Cite excerpt numbers (e.g. [1]) when "
    "referencing specific content. If the materials don't contain enough "
    "information to answer fully, say so clearly."
)


def _get_api_key(conn, user_id: int, provider: str) -> str:
    """Fetch and decrypt the user's stored API key for the given provider."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT encrypted_key FROM user_api_keys WHERE user_id = %s AND provider = %s",
        (user_id, provider),
    )
    row = cursor.fetchone()
    cursor.close()
    if not row:
        raise ValueError(
            f"No {provider} API key found. Add your key in Settings."
        )
    return decrypt_api_key(row['encrypted_key'])


def _format_context(chunks: list) -> str:
    """Format retrieved chunks into a numbered context block for the system prompt."""
    if not chunks:
        return "No relevant course material was found for this query."
    parts = []
    for i, c in enumerate(chunks, 1):
        header = f"[{i}] (type={c['chunk_type']}"
        if c.get('page_number'):
            header += f", page {c['page_number']}"
        header += f", similarity={c['similarity']:.3f})"
        parts.append(f"{header}\n{c['chunk_text']}")
    return "\n\n---\n\n".join(parts)


def _synthesize_claude(context: str, user_message: str, model: str, api_key: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=f"{SYSTEM_PROMPT}\n\nCourse material excerpts:\n{context}",
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def _synthesize_openai(context: str, user_message: str, model: str, api_key: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": f"{SYSTEM_PROMPT}\n\nCourse material excerpts:\n{context}",
            },
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content


def _synthesize_gemini(context: str, user_message: str, model: str, api_key: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    llm = genai.GenerativeModel(
        model_name=model,
        system_instruction=f"{SYSTEM_PROMPT}\n\nCourse material excerpts:\n{context}",
    )
    response = llm.generate_content(user_message)
    return response.text


_PROVIDERS = {
    'claude': _synthesize_claude,
    'openai': _synthesize_openai,
    'gemini': _synthesize_gemini,
}


def synthesize(
    conn,
    user_id: int,
    ai_provider: str,
    ai_model: str,
    user_message: str,
    chunks: list,
) -> tuple[str, list]:
    """
    Synthesize an LLM response using the user's chosen provider and model.

    Returns:
        (synthesized_text, chunk_ids_used)

    Raises:
        ValueError: if no API key is stored for the provider, or unsupported provider.
    """
    if ai_provider not in _PROVIDERS:
        raise ValueError(f"Unsupported provider: {ai_provider}")

    api_key = _get_api_key(conn, user_id, ai_provider)
    context = _format_context(chunks)
    fn = _PROVIDERS[ai_provider]
    text = fn(context, user_message, ai_model, api_key)
    chunk_ids = [c['id'] for c in chunks]
    return text, chunk_ids
```

---

## Modify `api/chat.py` `_send_message()`

### Add import at top of file

```python
from .llm import synthesize
```

### Replace the raw chunk formatting block (~lines 479–493)

```python
# RAG retrieval
chunks = retrieve_chunks(conn, content, context_material_ids)

# LLM synthesis (multi-provider via user's stored BYOK key)
try:
    assistant_content, retrieved_ids = synthesize(
        conn, user['id'], ai_provider, ai_model, content, chunks
    )
except ValueError as e:
    # No API key stored for this provider, or unsupported provider
    send_json(self, 400, {'error': str(e)})
    return
```

### In the assistant message DB INSERT — store retrieved chunk IDs

Find the existing `json.dumps([])` placeholder for `retrieved_chunk_ids` in the INSERT and replace with `json.dumps(retrieved_ids)`.

---

## Vercel Python Dependencies

Check for a `requirements.txt` at the repo root (Vercel auto-detects it for Python functions). Add:

```
anthropic>=0.20.0
openai>=1.0.0
google-generativeai>=0.8.0
```

Cohere is **not** needed on Vercel for Phase 1 — embedding still goes through the Lambda via boto3.

---

## Environment Variables

| Location | Key | Value |
|---|---|---|
| **Vercel** | `DATABASE_URL` | Neon **pooler** connection string |
| **Lambda `embed_query`** | `DATABASE_URL` | Neon **direct** connection string |
| **Lambda `embed_query`** | `COHERE_API_KEY` | Cohere API key |
| **Lambda `embed_materials`** | `DATABASE_URL` | Neon **direct** connection string |
| **Lambda `embed_materials`** | `COHERE_API_KEY` | Cohere API key |

Set Lambda env vars via AWS console or append `--environment Variables={COHERE_API_KEY=...,DATABASE_URL=...}` to the `aws lambda update-function-configuration` call in each `build.sh`.

Remove `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` from Vercel env once the Neon migration is complete and RDS is decommissioned (these are only needed for the Lambda invoke and S3 — S3 still uses them).

---

## Execution Order

1. **Get credentials**: Cohere API key (cohere.com) + Neon project (neon.tech)
2. **Create Neon branch** `phase-1-migration` via dashboard or CLI
3. **Run migration SQL** on the branch's direct connection — verify no errors
4. **Merge branch to main** in Neon dashboard
5. **Update Vercel** `DATABASE_URL` → Neon pooler string
6. **Update Lambda** `DATABASE_URL` → Neon direct string (both functions)
7. **Update Lambda `embed_query`**: edit 3 files → `./build.sh` → set `COHERE_API_KEY` env var in AWS console
8. **Update Lambda `embed_materials`**: edit 3 files → `./build.sh` → set `COHERE_API_KEY` env var in AWS console
9. **Create `api/llm.py`**
10. **Modify `api/chat.py`** (add import + replace chunk-dump block)
11. **Update `api/db.py`** `init_db()` schema definitions (vector(1024), web_cache, message_embedding)
12. **Update `api/db.py`** connection pool `min_size=1`
13. **Add Python dependencies** to root `requirements.txt`
14. **Deploy**: `git push` → Vercel auto-deploys
15. **Re-trigger ingestion**: re-upload one test material to S3 to verify end-to-end 1024D embedding

---

## Critical Files

| File | Action |
|---|---|
| `api/db.py` | Update pool `min_size=1`; update CREATE TABLE to `vector(1024)`, new default `model_name`; add `web_cache` table and `message_embedding` column |
| `api/llm.py` | **New file** — multi-provider synthesis dispatcher |
| `api/chat.py` → `_send_message()` | Add `synthesize` import; replace raw chunk dump with `synthesize()` call; store `retrieved_ids` |
| Root `requirements.txt` | Add `anthropic>=0.20.0`, `openai>=1.0.0`, `google-generativeai>=0.8.0` |
| `lambda/embed_query/handler.py` | Replace SentenceTransformer with Cohere client |
| `lambda/embed_query/requirements.txt` | `cohere>=5.0.0` only |
| `lambda/embed_query/Dockerfile` | Remove sentence-transformers bake-in line |
| `lambda/embed_materials/embedder.py` | Replace SentenceTransformer with Cohere client, batches of 96 |
| `lambda/embed_materials/requirements.txt` | Replace `sentence-transformers==3.0.1` with `cohere>=5.0.0` |
| `lambda/embed_materials/Dockerfile` | Remove sentence-transformers bake-in line |

## Reused Without Changes

| File | Role |
|---|---|
| `api/crypto_utils.py` → `decrypt_api_key()` | Called inside `api/llm.py` `_get_api_key()` |
| `api/rag.py` → `retrieve_chunks()` | Unchanged — still calls embed_query Lambda via boto3; Lambda now uses Cohere internally |
| `lambda/embed_materials/db.py` | Unchanged — already reads `DATABASE_URL` |
| `lambda/embed_query/build.sh` | Unchanged — rebuild and push as-is after editing the 3 source files |

---

## Verification

1. **Neon connection**: `psql $DATABASE_URL -c "SELECT version();"` — confirm Neon Postgres responds
2. **Schema**: `SELECT pg_typeof(embedding) FROM material_chunks LIMIT 1;` → should be `vector` with dim 1024 after migration
3. **Embedding Lambda**: Upload a test material → check `material_embed_jobs` shows `status='completed'` → `SELECT array_length(embedding::float[], 1) FROM material_chunks LIMIT 1;` → `1024`
4. **Query embedding**: Check Vercel function logs for `[DEBUG] Lambda StatusCode: 200` and `dim: 1024`
5. **LLM synthesis (Claude)**: Send a chat message with Claude selected → `chat_messages.content` should contain a coherent synthesized paragraph, not raw similarity-scored excerpts
6. **LLM synthesis (OpenAI)**: Repeat with OpenAI model selected
7. **LLM synthesis (Gemini)**: Repeat with Gemini model selected
8. **No API key error**: Select a provider with no stored key → 400 response with `"No <provider> API key found. Add your key in Settings."`
9. **Retrieved chunk IDs persisted**: `SELECT retrieved_chunk_ids FROM chat_messages WHERE role='assistant' LIMIT 5;` → non-empty JSON arrays
