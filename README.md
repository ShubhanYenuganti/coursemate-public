# OneShotCourseMate

Google OAuth login/logout with server-side session management, built with React + Vite and Python serverless functions on Vercel.

## Quick Start

```bash
# 1. Install dependencies
npm install
pip install -r requirements.txt

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env — see CLOUD_SETUP.md for how to get each value

# 3. Initialize database
cd api && python create_db.py && cd ..
cd api && DATABASE_URL init_db.py && cd ..

# 4. Run locally
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and click "Sign in with Google".

## Architecture

```
Frontend (React + Vite)          Backend (Python Serverless)       Database (PostgreSQL)
┌─────────────────────┐          ┌──────────────────────┐          ┌──────────────┐
│  App.jsx            │──POST──▶ │  /api/oauth          │──────▶   │  users       │
│  Google Sign-In     │          │  Verify Google JWT   │          │  sessions    │
│  Session in memory  │◀─────── │  Create session      │◀──────   │              │
│                     │          ├──────────────────────┤          └──────────────┘
│  Sign Out button    │──POST──▶ │  /api/logout         │
│                     │          │  Revoke session      │
│                     │          ├──────────────────────┤
│                     │──POST──▶ │  /api/update_address │
│                     │          │  Auth + CSRF required│
└─────────────────────┘          └──────────────────────┘
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_GOOGLE_CLIENT_ID` | Yes | Google OAuth Client ID (frontend) |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth Client ID (backend verification) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SESSION_SECRET` | Yes | Secret for CSRF token signing |
| `ALLOWED_ORIGIN` | Yes | Frontend URL for CORS (e.g., `http://localhost:5173`) |
| `RATE_LIMIT_RPM` | No | Max requests per minute per IP (default: 30) |

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/oauth` | None | Login — verify Google JWT, create user + session |
| POST | `/api/logout` | Bearer token | Logout — revoke server-side session |
| POST | `/api/update_address` | Bearer + CSRF | Update authenticated user's address |

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

See [CLOUD_SETUP.md](./CLOUD_SETUP.md) for detailed instructions on:
- Google Cloud Console (OAuth Client ID)
- AWS RDS (PostgreSQL)
- Vercel deployment

## Tech Stack

- **Frontend**: React 19, Vite 7, Tailwind CSS 4
- **Backend**: Python serverless functions (Vercel)
- **Database**: PostgreSQL with psycopg3 + connection pooling
- **Auth**: Google Identity Services (GIS)

## Claude Code Task Spec (DB + Migration Only)

Use this section as the implementation contract. Scope is intentionally limited to:
- `api/db.py` (schema changes in `init_db()`)
- new migration script `api/migrate_roles.py`

Do **not** implement API endpoints in this task.

### Existing schema context (already in production)

#### `courses`
- `id` integer PK
- `title` text not null
- `description` text nullable
- `material_ids` jsonb not null default `[]`
- `co_creator_ids` jsonb not null default `[]`
- `primary_creator` integer not null
- `status` varchar(20) not null default `'draft'`
- `visibility` varchar(20) not null default `'private'`
- `tags` jsonb not null default `[]`
- `cover_image_url` text nullable
- `created_at` timestamp not null default `CURRENT_TIMESTAMP`
- `updated_at` timestamp not null default `CURRENT_TIMESTAMP`

#### `materials`
- `id` integer PK
- `name` text not null
- `file_url` text not null
- `file_type` varchar(50) nullable
- `source_type` varchar(20) not null default `'upload'`
- `uploaded_by` integer not null
- `course_id` integer nullable
- `created_at` timestamp not null default `CURRENT_TIMESTAMP`

### Role model to implement

There are exactly 3 roles:
- `owner`
- `admin`
- `creator`

Permission intent (for future API enforcement):
- `owner`: can manage all permissions/roles; can do all admin actions; **cannot** view other users' private materials/generations.
- `admin`: can do all content actions but **cannot** manage other users' roles/permissions.
- `creator`: can generate own material and view public material; **cannot view any chat logs** (public chat is owner/admin-only).

### Visibility model to persist in DB

Use `public` / `private` flags at the record level for:
- chat logs
- material uploads
- material generations

Semantics for future reads:
- Public materials/generations: visible to course members.
- Private materials/generations: visible only to the creator/uploader.
- Chat logs (both public and private): only owner/admin can read.

### Required changes in `api/db.py`

Update `init_db()` to be idempotent and include the following.

1) Create `course_members` table if not exists:
- `id SERIAL PRIMARY KEY`
- `course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE`
- `user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `role VARCHAR(20) NOT NULL CHECK (role IN ('owner','admin','creator'))`
- `invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL`
- `joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- `last_active_at TIMESTAMP`
- `UNIQUE(course_id, user_id)`

Indexes:
- `idx_course_members_course_id` on `(course_id)`
- `idx_course_members_user_id` on `(user_id)`
- `idx_course_members_course_role` on `(course_id, role)`

2) Alter existing `materials` table:
- Add column `visibility VARCHAR(20) NOT NULL DEFAULT 'private' CHECK (visibility IN ('public','private'))` if missing
- Add column `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP` if missing

Indexes:
- `idx_materials_course_visibility` on `(course_id, visibility)`
- `idx_materials_uploader_visibility` on `(course_id, uploaded_by, visibility)`

3) Create `chat_messages` table if not exists:
- `id SERIAL PRIMARY KEY`
- `course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE`
- `user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `message_text TEXT NOT NULL`
- `ai_response TEXT`
- `visibility VARCHAR(20) NOT NULL DEFAULT 'private' CHECK (visibility IN ('public','private'))`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

Indexes:
- `idx_chat_course_created` on `(course_id, created_at DESC)`
- `idx_chat_user_course` on `(user_id, course_id)`
- `idx_chat_course_visibility_created` on `(course_id, visibility, created_at DESC)`

4) Create `material_generations` table if not exists:
- `id SERIAL PRIMARY KEY`
- `course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE`
- `generated_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `title TEXT NOT NULL`
- `content TEXT NOT NULL`
- `generation_type VARCHAR(50)`
- `visibility VARCHAR(20) NOT NULL DEFAULT 'private' CHECK (visibility IN ('public','private'))`
- `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

Indexes:
- `idx_generations_course_visibility` on `(course_id, visibility)`
- `idx_generations_creator_course_visibility` on `(generated_by, course_id, visibility)`

### Required new script: `api/migrate_roles.py`

Script behavior:
1. Ensure schema exists by calling `init_db()` first.
2. For every course, insert owner membership from `courses.primary_creator`:
	- Insert into `course_members` with role `owner`.
	- Use conflict-safe logic so reruns are safe.
3. Migrate `courses.co_creator_ids` JSONB entries into `course_members` as role `creator`:
	- one row per `(course_id, user_id)`.
	- skip duplicates.
4. Backfill visibility on legacy data:
	- set `materials.visibility = 'public'` for existing rows where null/empty or where column was newly added.
5. Print migration summary counts:
	- owners inserted
	- creators migrated from `co_creator_ids`
	- materials backfilled
6. Add basic integrity checks and print warnings:
	- courses without exactly one owner
	- `co_creator_ids` values that are invalid user ids

Implementation constraints:
- idempotent (safe to run multiple times)
- fail-fast on DB errors with non-zero exit
- no API-layer logic in this script

### Acceptance criteria

After running `python api/migrate_roles.py`:
- every course has one `owner` row in `course_members`
- historical `co_creator_ids` are represented as `creator` rows in `course_members`
- `materials` has `visibility` + `updated_at`
- `chat_messages` and `material_generations` exist with `public/private` visibility checks
- all new constraints/indexes exist

### Optional cleanup (do not execute in this task)

- Keep `courses.co_creator_ids` and `courses.material_ids` for backward compatibility now.
- Consider deprecating JSONB relationship columns only after API and reads fully migrate to relational tables.
