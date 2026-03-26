# OneShotCourseMate

CourseMate is live at [https://coursemate-public.vercel.app/](https://coursemate-public.vercel.app/) with the core product flows implemented: Google OAuth (server-side sessions) and a learning assistant that can chat with retrieval-augmented generation over your uploaded course materials, plus async generation of quizzes, flashcards, and reports.

## What’s implemented (now)

- Google OAuth login/logout with server-side sessions and CSRF protection.
- Streaming chat that retrieves relevant course-material chunks before calling the selected LLM provider (hybrid vector retrieval over pgvector).
- Course materials ingestion + embeddings via AWS Lambda workers (S3-triggered indexing, Lambda-based embedding for queries).
- Async generation of `quiz`, `flashcards`, and `reports` using SQS + Lambda workers with a `estimate -> draft -> queued -> ready/failed` lifecycle.

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

# 4. Run locally
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and click "Sign in with Google".

## Architecture

CourseMate is built as:

- **Frontend**: React + Vite + Tailwind.
- **Backend**: Python serverless request handlers running on Vercel (the `api/` modules).
- **Data layer**: Neon-hosted PostgreSQL (via `psycopg3` + connection pooling) with `pgvector`.
- **Workers**: AWS Lambda functions + SQS queues for long-running generation tasks.

### High-level request flow (chat + RAG)

1. **Chat requests** hit `api/chat.py` (supports both non-streaming and streaming responses via SSE).
2. The backend performs **hybrid retrieval** over course materials:
  - Query embeddings are produced by invoking the `**embed_query` Lambda** (`api/rag.py`).
  - Retrieval runs in `services/query/retrieval.py`, combining dual-modality hits from the `chunks` table.
3. The retrieved context is then passed to the selected LLM provider through `api/llm.py` to synthesize the final answer.
4. The backend persists both the user message and assistant response into Postgres, including grounding metadata (and optionally embeddings for message content).

### Agentic RAG + web search (Tavily)

In addition to retrieval over your private course materials, the backend supports an **agentic loop** (toggleable via environment flags) that can:

- run a cached **web search tool** backed by **Tavily** (`api/tools.py`, `web_cache` table)
- rerank retrieved chunks via Voyage (when enabled)

This is used to augment responses when the course corpus is missing key facts or when the query is better answered with live web context.

### Course materials ingestion + embeddings

- Uploading/confirming a material creates a row in the `materials` table.
- `**lambda/embed_materials`** is triggered by **S3 ObjectCreated** events (prefix `materials/`), fetches the uploaded document from S3, extracts content, and writes chunk embeddings into Postgres (pgvector).

### Async generation (quiz / flashcards / reports)

For all three generation modes, the API layer is lightweight and queue-backed:

- `api/quiz.py`, `api/flashcards.py`, `api/reports.py` implement actions like:
  - `action=estimate` (create a draft row + token estimates)
  - `action=generate` (transition draft to `queued` and enqueue an SQS job, returning `202`)
  - polling and viewer payload retrieval (e.g. `get_generation_status` and `get_generation`)
  - saving generated output as course “materials” artifacts when applicable
- Worker Lambdas (`lambda/quiz_generate`, `lambda/flashcards_generate`, `lambda/reports_generate`) consume SQS jobs, perform the provider calls, normalize output, persist results/versioning, and set status to `ready` or `failed`.
- The frontend polls `get_generation_status`, then fetches the viewer payload when ready.

## Future Implementations

Planned next improvements, focused on user experience and sharing:

- **Chat smart search lookup**: richer in-app “find this in my chat/course” that goes beyond keyword search by leveraging retrieval + chat context.
- **Bookmarking LLM responses**: let users save valuable answers (per chat/message) and revisit them quickly.
- **Sharing generated resources and courses cross users**: production-ready sharing that enables viewing/generating resources across users (not just a local UI stub).

## Environment Variables


| Variable                          | Required | Description                                           |
| --------------------------------- | -------- | ----------------------------------------------------- |
| `VITE_GOOGLE_CLIENT_ID`           | Yes      | Google OAuth Client ID (frontend)                     |
| `GOOGLE_CLIENT_ID`                | Yes      | Google OAuth Client ID (backend verification)         |
| `DATABASE_URL`                    | Yes      | Neon Postgres connection string                       |
| `SESSION_SECRET`                  | Yes      | Secret for CSRF token signing                         |
| `ALLOWED_ORIGIN`                  | Yes      | Frontend URL for CORS (e.g., `http://localhost:5173`) |
| `RATE_LIMIT_RPM`                  | No       | Max requests per minute per IP (default: 30)          |
| `QUIZ_GENERATION_QUEUE_URL`       | No*      | SQS queue URL for `quiz_generate` async jobs          |
| `FLASHCARDS_GENERATION_QUEUE_URL` | No*      | SQS queue URL for `flashcards_generate` async jobs    |
| `REPORTS_GENERATION_QUEUE_URL`    | No*      | SQS queue URL for `reports_generate` async jobs       |
| `TAVILY_API_KEY`                  | No*      | Tavily API key for agentic web search                 |
| `AGENTIC_WEB_SEARCH_ENABLED`      | No       | Enable Tavily-backed web search tool (`true`/`false`) |
| `AGENTIC_RERANK_ENABLED`          | No       | Enable Voyage rerank tool (`true`/`false`)            |
| `AGENTIC_LOOP_ENABLED`            | No       | Enable agentic loop in chat (`true`/`false`)          |


## API Endpoints


| Method   | Endpoint                                       | Auth             | Description                                                                   |
| -------- | ---------------------------------------------- | ---------------- | ----------------------------------------------------------------------------- |
| POST     | `/api/oauth`                                   | None             | Login — verify Google JWT, create user + session                              |
| POST     | `/api/logout`                                  | Bearer token     | Logout — revoke server-side session                                           |
| POST     | `/api/update_address`                          | Bearer + CSRF    | Update authenticated user's address                                           |
| GET/POST | `/api/chat`                                    | Bearer (session) | Streaming chat + message management (includes retrieval + provider synthesis) |
| GET/POST | `/api/quiz`, `/api/flashcards`, `/api/reports` | Bearer (session) | Async estimate/generate/poll flows backed by SQS + Lambda workers             |


## Security Features

- **Server-side sessions** — sessions stored in DB with expiration and revocation
- **CSRF protection** — HMAC-based tokens tied to sessions for state-changing requests
- **Rate limiting** — per-IP rate limiting on all endpoints
- **Restricted CORS** — configurable allowed origin (not wildcard)
- **Input validation** — sanitization of user inputs with length limits
- **No token leakage** — session tokens stored in React state (not localStorage), filtered from JSON viewer
- **Secure headers** — HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **Connection pooling** — psycopg connection pool for database efficiency
- **Authenticated endpoints** — user identity derived from session, not request body

## Deployment

At a high level, production deploy is:

- **Frontend + API**: Vercel (Vite + Python serverless in `api/`)
- **Database**: Neon Postgres (pooler connection string recommended for serverless)
- **Indexing + generation workers**: AWS Lambda (S3-triggered indexing + SQS-triggered generators), AWS ECR (containerizations of code ran by Lambda)

## Tech Stack

- **Frontend**: React 19, Vite 7, Tailwind CSS 4
- **Backend**: Python serverless functions (Vercel)
- **Database**: PostgreSQL with psycopg3 + connection pooling
- **Auth**: Google Identity Services (GIS)

