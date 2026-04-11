## Context

CourseMate is a Vercel-hosted app with Python serverless functions in `/api/`. Users already connect AI providers (Gemini, OpenAI, Claude) via encrypted keys stored in `user_api_keys`. The app generates study materials (flashcards, quiz, reports) that users currently save as course materials or export as PDFs. There is no third-party OAuth integration today.

Notion uses OAuth 2.0 (public integration model): the app holds a `client_id` + `client_secret`, users authorize via Notion's hosted consent page, and the app receives an `access_token` + workspace metadata. Notion access tokens do not expire (they are revoked only explicitly), which eliminates refresh token complexity.

## Goals / Non-Goals

**Goals:**
- Users connect their Notion workspace once via OAuth; connection persists across sessions
- Users can revoke access from ProfilePage, which deletes the stored token
- Per (user, course, provider, generation_type) sticky export target — remembers the last chosen destination
- Flashcards export as Notion Database rows (Front, Back, Hint properties)
- Quiz exports as a Notion page with heading/toggle block structure
- Reports export as a Notion page mirroring the sections array
- All Notion backend in a single `/api/notion.py` handler, routing on `action` query param
- Provider-agnostic block exporter in `api/services/export_blocks.py` with `providers/notion.py` submodule
- Per-user per-course Notion database source points; new and updated pages auto-ingested as course materials
- Target picker supports creating new Notion pages or databases directly from the picker
- Material selections persisted in DB per user/context; default to own materials; collaborator materials opt-in
- Schema generalised across providers so Google Drive (and others) can be added without migrations

**Non-Goals:**
- Chat pin export (architecture must accommodate it, but not implemented now)
- Google Drive or other provider implementation (schema supports it; implementation deferred)
- Per-card/per-question edit before export
- Notion webhooks or real-time sync (polling only)

## Decisions

### D1: Single `/api/notion.py` file routing on `action`

**Decision**: All Notion operations — OAuth initiation, callback, revocation, page search, and all exports — live in one serverless function.

**Rationale**: Matches existing patterns in `flashcards.py`, `reports.py`, and `quiz.py` which all route on `action`. Vercel routes by filename; a single file avoids route proliferation for what is logically one integration domain. The file dispatches via `action` query param for GET and `action` in body for POST.

**Alternative considered**: Separate files (`/api/notion/auth.py`, `/api/notion/export.py`). Rejected because it requires nested Vercel routing config and splits a cohesive domain across files.

### D2: `user_integrations` table (not extending `user_api_keys`)

**Decision**: New table with JSONB `metadata` column.

```sql
CREATE TABLE user_integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    encrypted_token TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, provider)
);
```

**Rationale**: Notion OAuth tokens carry structured metadata (workspace_id, workspace_name, workspace_icon, bot_id) that is user-visible in ProfilePage. Storing this in a JSONB column is more natural than a single opaque `encrypted_key` string. The UNIQUE(user_id, provider) constraint supports upsert on re-auth. JSONB metadata stays schema-flexible for future providers (Google Drive, Slack) without migrations.

**Token encryption**: Reuse `crypto_utils.encrypt_api_key` / `decrypt_api_key` — same Fernet key, same pattern.

### D3: `course_export_targets` table for sticky targeting (provider-agnostic)

**Decision**: Single table covering all providers rather than separate per-provider tables.

```sql
CREATE TABLE course_export_targets (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    course_id             INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    provider              VARCHAR(50) NOT NULL,      -- 'notion', 'google_drive', etc.
    generation_type       VARCHAR(30) NOT NULL,      -- 'flashcards', 'quiz', 'report', 'chat_pin'
    external_target_id    TEXT NOT NULL,
    external_target_title TEXT,
    external_target_type  VARCHAR(20),               -- 'page' | 'database' | 'folder' | etc.
    metadata              JSONB NOT NULL DEFAULT '{}',
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id, provider, generation_type)
);
```

**Rationale**: Keeps target preferences per-user and per-provider. Adding Google Drive later requires no migration — just new rows with `provider='google_drive'`. The `generation_type` string is open-ended; `'chat_pin'` can be added with no schema change. `metadata` absorbs provider-specific fields (e.g. Notion workspace_id, Drive shared drive id).

### D4: Flashcards → Notion Database rows (not toggle blocks)

**Decision**: Flashcards export as toggle blocks appended to a user-selected Notion **page**. Each card becomes one toggle block: the toggle heading = card `front`, the expanded body = card `back` and card `hint`. The picker is filtered to `allowedTypes: ['page']` so databases are never selectable. The backend verifies the target is a page before appending.

**Rationale**: Simplified from the original database-row approach during spec refinement. Toggle blocks on a page keep all three content types (flashcards, quiz, report) consistent — page-only targets — and avoid the complexity of Notion database property schemas and row creation. The backend enforces this with a `GET /pages/{id}` check before export.

**Alternative previously considered**: Flashcards as database rows (Front/Back/Hint properties) — rejected in favour of toggle blocks for consistency and simpler implementation.

### D5: Quiz and Reports → Notion pages with block hierarchy

**Decision**: Both export as Notion child pages under the chosen parent page target.

- **Quiz**: `heading_2` for each question, `bulleted_list_item` for options, `toggle` block containing the correct answer.
- **Report**: `heading_1` for title, `heading_2` for each section, `paragraph` blocks for content.

**Rationale**: Pages with heading hierarchy are the natural Notion representation for documents. The report `sections[]` array maps directly to headings + paragraphs.

### D6: OAuth state parameter for CSRF protection

**Decision**: Generate a random `state` value, store it in a short-lived session/cookie (or as a signed query param), validate on callback.

**Rationale**: Required by OAuth 2.0 spec to prevent CSRF on the callback. The callback handler rejects any request where `state` does not match.

**Implementation**: Store `state` in a signed cookie (`notion_oauth_state`) set on the `/api/notion?action=auth` redirect, validated and cleared on `/api/notion?action=callback`.

### D7: No Notion SDK — raw `requests`

**Decision**: Use `requests` (already available in the Python environment) rather than `notion-client` SDK.

**Rationale**: The Notion REST API is simple and well-documented. Adding an SDK dependency on Vercel serverless adds cold-start overhead and package complexity. The integration only needs: token exchange, search, append block children, and create page — all simple POST/GET calls.

## Risks / Trade-offs

- **Notion rate limits** → The Notion API allows 3 requests/second per integration. Export calls are user-initiated (not bulk), so this is unlikely to be a problem. Log 429 responses and surface them as user-facing errors.
- **Database property mismatch** (flashcards) → If the user selects a Notion database with incompatible properties, the export will fail. Mitigation: validate the database schema on target selection; surface a clear error message.
- **Token revoked externally** → If the user revokes the integration from Notion's side, subsequent export calls will receive 401. Mitigation: detect 401, clear the stored token, and prompt re-authentication.
- **Large flashcard decks** → Notion API limits page content. A 100-card deck means 100 `create_page` (or `append_blocks`) calls. Mitigation: batch with `append_block_children` which accepts up to 100 blocks per call.

## Migration Plan

1. Run two `CREATE TABLE` statements (provided in chat — no migration file needed per project conventions)
2. Deploy `api/notion.py` and `api/services/notion_blocks.py`
3. Set env vars: `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`, `NOTION_REDIRECT_URI`
4. Register redirect URI in Notion developer portal
5. Deploy frontend changes to ProfilePage, Flashcards, Quiz, Reports

Rollback: drop the two tables, remove the env vars, undeploy the new files. No existing tables are modified.

## Open Questions

- Should the Notion page picker show a flat search or a tree browser? (Decision: flat search via Notion's `/search` API — simpler, no tree traversal needed)
- Should we validate flashcard database properties before exporting or fail gracefully? (Decision: validate on target selection, show error if required properties are missing)

---

### D8: `integration_source_points` table (provider-agnostic source watchers)

**Decision**: Single generalised table for all provider source points.

```sql
CREATE TABLE integration_source_points (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    course_id      INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    provider       VARCHAR(50) NOT NULL,        -- 'notion', 'google_drive', etc.
    external_id    TEXT NOT NULL,               -- Notion DB id, Drive folder id, etc.
    external_title TEXT,
    metadata       JSONB NOT NULL DEFAULT '{}', -- provider-specific extras
    last_synced_at TIMESTAMP,
    is_active      BOOLEAN NOT NULL DEFAULT true,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id, provider, external_id)
);
```

**Rationale**: Source points are per-user even within a shared course — collaborators each manage their own feeds independently. `UNIQUE(user_id, course_id, provider, external_id)` prevents duplicate watchers. `metadata` stores provider-specific data without schema changes (e.g. Notion workspace_id for token resolution).

### D9: `material_selections` table for persistent per-user context selections

**Decision**: DB-persisted selections with FK cascade, replacing any localStorage approach.

```sql
CREATE TABLE material_selections (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id)      ON DELETE CASCADE,
    course_id   INTEGER NOT NULL REFERENCES courses(id)    ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES materials(id)  ON DELETE CASCADE,
    context     VARCHAR(30) NOT NULL,   -- 'chat' | 'quiz' | 'flashcards' | 'report'
    provider    VARCHAR(50),            -- NULL = manual upload, 'notion', 'google_drive'
    selected    BOOLEAN NOT NULL DEFAULT true,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, course_id, material_id, context)
);
```

**Default selection logic** (when no row exists for a material):
- `materials.uploaded_by = current_user` → treated as selected
- `materials.uploaded_by ≠ current_user` → treated as unselected

On explicit toggle, a row is upserted. FK `ON DELETE CASCADE` on `material_id` means removed materials drop from selections automatically — no stale IDs.

**`provider` column rationale**: Enables bulk operations (e.g. "deselect all Notion materials for this course") without a join to `materials`.

### D10: Notion-sourced materials are private by default

**Decision**: Materials created by the integration poller (`source_type = 'notion'`) are inserted with `visibility = 'private'`.

**Rationale**: In multi-collaborator courses, auto-public materials from each collaborator's Notion feed would immediately flood every other user's context. Private-by-default means only the owner's materials are auto-selected. The owner can set `visibility = 'public'` to make materials available in other users' opt-in pool.

### D11: Notion → PDF conversion preserves dual embedding pathway

**Decision**: Notion page blocks are extracted via the Notion API and rendered to PDF using `reportlab` before being uploaded to S3. The existing `embed_materials` Step Function runs unchanged.

**Rationale**: The `embed_materials` pipeline has two pathways — Voyage text embeddings and Voyage multimodal (visual) embeddings of PDF page images. Converting Notion content to PDF preserves both pathways, including image blocks embedded inline. Alternative approaches (plain text extraction, direct chunk injection) would bypass the visual pathway and lose screenshot-level embeddings.

**Image handling**: Notion image blocks contain CDN URLs. The poller downloads each image before PDF generation so the PDF is self-contained and not dependent on Notion CDN availability.

**Update path**: When a Notion page already has a corresponding `materials` row (`external_id` match):
1. Delete old S3 PDF
2. Delete `chunks` rows for that `material_id` (clears stale embeddings)
3. Regenerate PDF from current Notion blocks
4. Upload to S3 (same key pattern: `notion/{page_id}.pdf`)
5. Trigger `embed_materials` Step Function (identical to new-page path)

**Note for implementation**: Verify whether `embed_materials` worker appends or replaces chunks for a given `material_id`. If it appends, the explicit `DELETE chunks` in step 2 is load-bearing.

### D12: `integration_poller` Lambda with provider dispatch

**Decision**: Single Lambda function (`lambda/integration_poller/`) with provider-specific handler modules. Triggered by EventBridge Scheduler every 2 hours. Manual sync calls the same Lambda via direct invocation from the API.

```
EventBridge Scheduler (cron: every 2h)  ──OR──  POST /api/notion?action=sync (direct invoke)
       │
       ▼
integration_poller Lambda
  SELECT * FROM integration_source_points WHERE is_active = true
       │
       ├─ provider = 'notion'       → handlers/notion.py
       │    blocks → PDF (reportlab) → S3 → embed_materials Step Function
       │
       └─ provider = 'google_drive' → handlers/gdrive.py  (future)
            native PDF export → S3 → embed_materials Step Function
```

**Rationale**: Single Lambda avoids infrastructure duplication. Provider modules are independent — adding Google Drive adds one file, no changes to the dispatcher or existing handlers.

### D13: Target picker "Create New" flow

**Decision**: The target picker gains a `+` button that opens a sub-form: choose Page or Database, enter name, pick parent page (via search). CourseMate calls the Notion API to create the resource, then auto-selects it as the sticky target.

- **Page creation**: `POST /v1/pages` with `parent.page_id` and `properties.title`
- **Database creation**: `POST /v1/databases` with `parent.page_id`, `title`, and hardcoded property schema: `Front` (title), `Back` (rich_text), `Hint` (rich_text) — matching the flashcard export format

**Rationale**: Removes the friction of requiring users to pre-create destinations in Notion before exporting. The hardcoded database schema is intentional — we know the exact shape needed for flashcard export.

### D14: Collaborator material hover tooltip

**Decision**: In the opt-in "from collaborators" section of material pickers, hovering over a material shows a 3-line tooltip:
```
Alice Kim
Notion: Week 3 Dynamics Notes
alice@university.edu
```
Line 1: collaborator display name. Line 2: full material title (useful when truncated in the narrow sidebar). Line 3: collaborator email.

**Rationale**: The sidebar is narrow — inline metadata would require truncation. A hover tooltip surfaces full context without cluttering the list.
