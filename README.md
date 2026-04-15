# OneShotCourseMate

CourseMate is live at [https://coursemate-public.vercel.app/](https://coursemate-public.vercel.app/).

OneShotCourseMate is an AI-assisted study platform that lets students and instructors turn their existing course materials into interactive learning sessions. Users connect their Notion workspaces or Google Drive folders, select the files they want to study, and the platform indexes those materials so a course-aware AI chat assistant can answer questions, generate flashcards and quizzes, and produce study reports — all grounded in the actual content of those documents.

The backend is written in Python and runs on AWS, with PostgreSQL as the primary datastore. File indexing and embedding are handled by AWS Lambda functions triggered on a schedule by Amazon EventBridge, and on-demand via direct invocation from the API. The frontend is a single-page React application.

## Quick Start

```bash
# 1. Install dependencies
npm install
pip install -r requirements.txt

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env — see the Environment Variables section below

# 3. Initialize database
cd api && python create_db.py && cd ..
cd api && DATABASE_URL init_db.py && cd ..

# 4. Run locally (frontend + Python API together)
vercel dev

# Or run them separately:
npm run dev          # Vite frontend on :5173
vercel dev --listen 3000  # Python API on :3000
```

Open [http://localhost:3000](http://localhost:3000) and click "Sign in with Google".

## Architecture

- **Frontend**: React + Vite + Tailwind.
- **Backend**: Python serverless request handlers running on Vercel (the `api/` modules).
- **Data layer**: Neon-hosted PostgreSQL (via `psycopg3` + connection pooling) with `pgvector`.
- **Workers**: AWS Lambda functions + SQS queues for long-running generation tasks.

### Authentication (HttpOnly Cookie + CSRF)

CourseMate uses **server-side sessions** backed by a database session table, with the session token stored in an **HttpOnly cookie** named `cm_session`.

- **Session cookie is HttpOnly**: the browser never exposes `cm_session` to JavaScript; all `/api/*` requests rely on cookie forwarding (`fetch(..., { credentials: 'include' })`).
- **CSRF token is the only auth primitive exposed to the frontend**: issued via `/api/auth`, stored in React state, and sent as `X-CSRF-Token` on state-changing requests.

Login flows:
1. **App restore (page load)**: `GET /api/auth` validates the existing `cm_session` cookie and returns `{ user, csrf_token }`.
2. **Login (Google OAuth)**: `POST /api/auth` verifies the Google ID token, creates/updates the user, and sets a fresh `cm_session` cookie alongside `{ user, csrf_token }`.
3. **Logout**: `DELETE /api/auth` revokes the server-side session and clears the cookie.

### Chat + RAG Request Flow

1. **Chat requests** hit `api/chat.py` (streaming responses via SSE).
2. The backend performs **hybrid retrieval** over course materials: query embeddings are produced by the `embed_query` Lambda (`api/rag.py`), then retrieval runs in `services/query/retrieval.py` combining dual-modality hits from the `chunks` table.
3. The retrieved context is passed to the selected LLM provider via `api/llm.py` to synthesize the final answer.
4. Both the user message and assistant response are persisted to Postgres with grounding metadata.

### Agentic RAG + Web Search (Tavily)

The backend supports an optional **agentic loop** that can run a cached web search tool backed by **Tavily** (`api/tools.py`, `web_cache` table) and rerank retrieved chunks via Voyage. This augments responses when the course corpus is missing key facts or when the query is better answered with live web context.

### Async Generation (Quiz / Flashcards / Reports)

All three generation modes are queue-backed:
- API handlers (`api/quiz.py`, `api/flashcards.py`, `api/reports.py`) accept `action=estimate` (draft + token count) and `action=generate` (enqueue SQS job, return `202`).
- Worker Lambdas consume SQS jobs, call the LLM, normalize output, and set status to `ready` or `failed`.
- The frontend polls `get_generation_status`, then fetches the viewer payload when ready.

---

## Integrations — Connecting Notion & Google Drive

Users connect Notion and Google Drive from the **Profile** page via standard OAuth 2.0. The flow is secured with a short-lived state cookie (CSRF guard); tokens are stored encrypted in `user_integrations` and never exposed to the client. Each collaborator can connect independent workspaces or Drive folders to the same shared course. Disconnecting revokes the token and removes all associated course targets for that user.

---

## Integrations — Synchronization

### Invoked Sync (Sync Now)

When a user selects a source point for the first time, or clicks **Sync Now**, a staging modal lists all files from the integration. Toggles default to **ON**; the user may opt files out and assign a `doc_type` (e.g. Lecture, Reading). Confirming writes per-file sync state to the database via `bulk_upsert_sync` and immediately invokes the Lambda poller for those files with an explicit list of `external_ids`, bypassing the database work-list query.

### Asynchronous Sync (EventBridge)

Amazon EventBridge triggers the same Lambda on a schedule (~every 2 hours). In this path the Lambda derives its work list by querying `materials WHERE sync = TRUE` — no external file listing is performed. For each file it checks whether the source has a newer version than the database record, and ingests only files that have changed.

The ingestion pipelines:
- **Notion**: `pages API last_edited_time` → blocks fetch → ReportLab PDF → S3 → materials row → embed job
- **GDrive**: `Drive modifiedTime` → export as PDF (Docs/Sheets/Slides) or direct download (native PDF, with a 50 MB split guard) → S3 → materials row → embed job

---

## Integrations — Progress Panel

The Progress Panel is an inline surface on the Materials page showing per-file sync status, polled every **2 seconds** during active jobs.

| Status | Meaning |
|--------|---------|
| Syncing | Lambda is fetching and uploading the file |
| Queued | Embed job created; worker has not yet picked it up |
| Indexing | Embedding worker is processing the file |
| Done | File is fully indexed and available in chat |

---

## Integrations — Exporting Generated Content

Flashcards, quizzes, and reports generated by the AI can be exported back to **Notion** or **Google Drive** directly from the chat panel. Each export target is remembered per user × course × generation type, so repeat exports pre-fill the last-used destination.

---

## Chat — Search

The search modal operates in two modes:

- **Empty query**: reads from the in-memory chat list already loaded in the sidebar, sorted by `last_message_at DESC`. No network request.
- **Non-empty query**: debounced 300 ms, then `GET /api/chat?resource=chat_search`. Results are returned in two labeled sections — **TITLE MATCHES** and **IN CONVERSATION**.

Search uses PostgreSQL full-text search (`tsvector`/`tsquery`). Title matches apply prefix matching on the last token (`:*`) and receive a **≥ 3× `ts_rank` boost**; a chat appearing in title results is excluded from content results. Content matches use log-damped scoring — `(1 + ln(hit_count)) × best_message_rank` — so a chat with many weak hits does not outrank one with fewer, highly relevant hits. Each section is capped at 20 results; archived chats are excluded.

---

## Chat — Pinned Responses

Users can pin any AI message by clicking the **pin icon** on the message bubble (it replaces the earlier thumbs-up/down reaction). Pins are stored in the `pinned_messages` table in PostgreSQL — not in localStorage — with ownership enforced server-side on every write and delete.

When the model returns a reply it also returns a `summary` field: a 5–6 word distillation of the answer stored in `chat_messages.summary`. The **PinsPanel** surfaces all pins for the current chat, sorted by latest pin time, with each row headed by this LLM-generated summary. Rows are expandable to show the full user + AI exchange, and a trash icon permanently deletes the pin. Pin state is preserved through message revert and restore operations.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `VITE_GOOGLE_CLIENT_ID` | Yes | Google OAuth Client ID (frontend) |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth Client ID (backend verification) |
| `DATABASE_URL` | Yes | Neon Postgres connection string |
| `SESSION_SECRET` | Yes | Secret for CSRF token signing |
| `ALLOWED_ORIGIN` | Yes | Frontend URL for CORS (e.g. `http://localhost:5173`) |
| `NOTION_CLIENT_ID` | Yes* | Notion OAuth client ID |
| `NOTION_CLIENT_SECRET` | Yes* | Notion OAuth client secret |
| `NOTION_REDIRECT_URI` | Yes* | OAuth callback URL for `/api/notion?action=callback` |
| `RATE_LIMIT_RPM` | No | Max requests per minute per IP (default: 30) |
| `QUIZ_GENERATION_QUEUE_URL` | No* | SQS queue URL for `quiz_generate` async jobs |
| `FLASHCARDS_GENERATION_QUEUE_URL` | No* | SQS queue URL for `flashcards_generate` async jobs |
| `REPORTS_GENERATION_QUEUE_URL` | No* | SQS queue URL for `reports_generate` async jobs |
| `TAVILY_API_KEY` | No* | Tavily API key for agentic web search |
| `AGENTIC_WEB_SEARCH_ENABLED` | No | Enable Tavily-backed web search tool (`true`/`false`) |
| `AGENTIC_RERANK_ENABLED` | No | Enable Voyage rerank tool (`true`/`false`) |
| `AGENTIC_LOOP_ENABLED` | No | Enable agentic loop in chat (`true`/`false`) |

`*` Required when enabling the respective integration.

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/auth` | `cm_session` cookie | Validate existing session and return `{ user, csrf_token }` |
| POST | `/api/auth` | None | Login — verify Google credential, create session |
| DELETE | `/api/auth` | `cm_session` cookie | Logout — revoke session and clear cookie |
| GET/POST | `/api/course` | `cm_session` cookie | Course creation / list / detail |
| GET/POST | `/api/chat` | `cm_session` cookie | Streaming chat + retrieval + provider synthesis |
| GET/POST | `/api/material` | `cm_session` cookie | Material ingestion, indexing pipeline hooks, listing/polling |
| GET/POST | `/api/quiz`, `/api/flashcards`, `/api/reports` | `cm_session` cookie | Async estimate/generate/poll flows backed by SQS + Lambda |
| GET/POST | `/api/user` | `cm_session` cookie | Profile + API key management (CSRF required for state changes) |

## Security Features

- **Server-side sessions** — stored in DB with expiration and revocation
- **CSRF protection** — HMAC-based tokens tied to sessions for state-changing requests
- **Rate limiting** — per-IP rate limiting on all endpoints
- **Restricted CORS** — configurable allowed origin (not wildcard)
- **Input validation** — sanitization of user inputs with length limits
- **No token leakage** — session token in an HttpOnly cookie (`cm_session`); only `csrf_token` is exposed to the frontend
- **Secure headers** — HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **Authenticated endpoints** — user identity derived from session, not request body

## Deployment

- **Frontend + API**: Vercel (Vite + Python serverless in `api/`)
- **Database**: Neon Postgres (pooler connection string recommended for serverless)
- **Workers**: AWS Lambda + AWS ECR (S3-triggered indexing, SQS-triggered generators)

## Tech Stack

- **Frontend**: React 19, Vite 7, Tailwind CSS 4
- **Backend**: Python serverless functions (Vercel)
- **Database**: PostgreSQL with psycopg3 + pgvector
- **Auth**: Google Identity Services (GIS)
