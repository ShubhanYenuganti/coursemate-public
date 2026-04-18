## Context

The chat input bar today accepts only text. The LLM synthesis layer (`api/llm.py`) passes `user_message: str` to each provider function — no multimodal surface exists anywhere in the stack. All three supported provider families (Anthropic, OpenAI, Gemini) offer vision APIs that accept base64-encoded images inline in the message payload.

The product already has S3 infrastructure (used for material uploads), presigned URL generation utilities in `api/s3_utils.py`, and a `chat_messages` table in Postgres. The embedding pipeline uses two Voyage AI models: `voyage-3.5` (text-only) and `voyage-multimodal-3.5` (images + text in the same vector space). The `embed_materials` Lambda already embeds document page images via `voyage-multimodal-3.5` using PIL Image inputs. The `embed_query` Lambda already returns a `visual_embedding` from text queries via `voyage-multimodal-3.5` — this creates a shared embedding space between text queries and images. The goal is to wire images through the existing stack with minimal new infrastructure, and to use the existing Voyage multimodal model for cross-modal retrieval of past conversation images.

## Goals / Non-Goals

**Goals:**
- Allow up to 5 PNG/JPEG images (≤10MB each) per chat message via file picker or focused-textarea paste
- Persist images in S3 (`chat-images/` prefix); store S3 keys in `chat_messages`
- Display a compact attachment bar in message history with presigned download links
- Deliver images to vision-capable LLMs as base64 inline blocks
- Gate non-vision models with a banner warning; never silently drop images
- Embed each uploaded image synchronously with `voyage-multimodal-3.5` and store in `chat_image_embeddings` before synthesis begins
- Include all stored chat image embeddings as ranked candidates in every `retrieve_chunks` call scoped to the conversation, with a +0.20 score boost over material chunks

**Non-Goals:**
- Drag-and-drop onto the page (only file picker + focused paste)
- Image editing, annotation, or cropping
- OCR / text extraction fallback for non-vision models
- Image display inline in the assistant response
- Auto-switching to a vision model when a non-vision model is selected

## Decisions

### D1: S3 pre-upload before send (not base64-direct)

**Decision:** Upload images to S3 before calling `stream_send`; store S3 keys permanently; fetch and base64-encode at LLM call time.

**Rationale:** Images must persist for the chat history attachment bar. Sending raw base64 directly without storage means history loses the images on reload. S3 keys don't expire; presigned download URLs are generated on-demand.

**Alternative considered:** Embed base64 in the `stream_send` payload and store bytes in Postgres. Rejected — large binary blobs in Postgres slow down message queries and increase backup size.

### D2: Separate `chat-images/` S3 prefix, not the materials table

**Decision:** Images live at `chat-images/{user_id}/{uuid}.{ext}` in S3 and are referenced only from `chat_messages.image_s3_keys`. They are not registered in the `materials` table.

**Rationale:** Chat images are ephemeral conversation context, not course content. Adding them to the materials pipeline would expose them in the materials list, trigger unnecessary ingestion/embedding, and pollute material search. A simple S3 key reference is sufficient.

**Alternative considered:** Reuse `request_upload` / `confirm_upload` with a special `source_type`. Rejected for the reasons above.

### D3: New `upload_image` action on `/api/chat`

**Decision:** Add `action: "upload_image"` to `/api/chat` rather than creating a new endpoint.

**Rationale:** Consistent with the existing chat resource pattern (`create`, `stream_send`, etc.). Avoids new routing configuration.

**Response:** `{ upload_url: <presigned PUT>, s3_key: <key> }` — frontend PUTs directly to S3, then includes `s3_key` in `stream_send`.

### D4: Base64 delivery to LLM (not URL-based)

**Decision:** At LLM call time, fetch each image from S3 and pass as base64 inline in the content block.

**Rationale:** Anthropic's vision API supports URL-based images only for public URLs; our S3 URLs are presigned with short TTLs. OpenAI supports `data:` URLs. Gemini uses `inline_data`. Base64 is the common denominator across all three providers.

**Alternative considered:** Generate a fresh presigned URL and pass it directly to the LLM. Rejected — Anthropic doesn't support presigned S3 URLs; TTL race conditions on slow connections are unpredictable.

### D5: Non-vision blocklist (not allowlist)

**Decision:** Define `NON_VISION_MODEL_IDS` as a Set of known non-vision model IDs; everything else is treated as vision-capable.

**Rationale:** New models added to `PROVIDER_MODELS` default to vision-capable, which is the correct assumption for modern models. A blocklist requires fewer updates as the model roster grows.

**Blocked models:** `deep-research-pro-preview-12-2025`, `o3-deep-research`, `o4-mini-deep-research`.

### D6: DB column `image_s3_keys TEXT[]`

**Decision:** Add `image_s3_keys TEXT[]` to `chat_messages`. Store the S3 key (not the presigned URL). Generate presigned download URLs at message-load time.

**Rationale:** Presigned URLs expire; keys do not. Generating fresh presigned URLs at load time ensures download links always work regardless of when the message was sent.

## Risks / Trade-offs

### D7: Voyage multimodal-3.5 for image embeddings (not LLM captioning)

**Decision:** Embed images using `voyage-multimodal-3.5` directly (PIL Image → vector) rather than first captioning with a vision LLM and then embedding the caption text.

**Rationale:** `embed_materials` already uses this exact approach for document page images. The `embed_query` Lambda already returns a `visual_embedding` from text queries using the same model — so text queries and image embeddings live in the same 1024-dim space. Cross-modal cosine search works without any intermediate text step. Captioning would add an extra vision LLM call per image with no benefit.

**Alternative considered:** Caption via vision LLM → embed caption text with `voyage-3.5`. Rejected — unnecessary round-trip, caption quality introduces noise, and the multimodal vector space already handles text-to-image matching.

### D8: Extend `embed_query` Lambda with `image_base64` path

**Decision:** Add an `image_base64` input path to the existing `embed_query` Lambda rather than creating a new Lambda.

**Rationale:** The exact same `voyage-multimodal-3.5` call pattern used in `embed_materials/embedder.py:embed_visual()` applies here. Reusing the Lambda keeps operational surface small. The extension is ~10 lines following the existing pattern.

**New behavior:** When `image_base64` is present in the request, decode → PIL Image → `multimodal_embed` → return `{ visual_embedding, dim }`. When absent, existing text path is unchanged.

### D9: Synchronous embedding before synthesis

**Decision:** Image embedding runs synchronously in the `stream_send` handler after the user message is stored and before `synthesize()` is called. No background thread.

**Rationale:** For each image: fetch bytes from S3, base64-encode, invoke `embed_query` Lambda with `image_base64`, insert result into `chat_image_embeddings`. This takes ~1–2s for 1–5 images but ensures the embeddings are available as candidates in the very synthesis call that follows — including for retrieval in the current message's context window. A background approach would require a separate retrieval path or a race-condition-prone delay.

**Alternative considered:** Background thread after streaming begins. Rejected — the current message's synthesis call cannot include image candidates it hasn't embedded yet, and a race condition on rapid follow-ups creates inconsistent retrieval behavior.

### D10: New `chat_image_embeddings` table (not chunks table)

**Decision:** Store image embeddings in a dedicated `chat_image_embeddings` table, not in the existing `chunks` table.

**Rationale:** `chunks` is scoped to course material documents and participates in `retrieve_chunks` with `material_ids` filtering. Chat images are conversation-scoped, not material-scoped. A separate table keeps the schema clean while allowing `retrieve_chunks` to query both tables and merge results in a single ranked pass. At retrieval time, all rows for a given `chat_id` are fetched and cosine similarity is computed in Python — the number of images per chat is small enough that an ANN index adds no benefit. A btree index on `chat_id` is sufficient.

**Schema:**
```sql
CREATE TABLE chat_image_embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    s3_key      TEXT NOT NULL,
    chat_id     INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    message_id  INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    embedding   VECTOR(1024) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON chat_image_embeddings (chat_id);
```

### D11: All chat image embeddings merged into unified `retrieve_chunks` ranking with score boost

**Decision:** `retrieve_chunks()` in `api/rag.py` is extended with an optional `chat_id: int = None` parameter. When provided, after computing `vis_emb` via `_invoke_embed_query`, it fetches **all** rows from `chat_image_embeddings` for that `chat_id`, computes cosine similarity against `vis_emb` in Python, applies a **+0.20 flat score boost**, and merges these candidates into the same ranked pool as material chunks before the top-K slice. No similarity threshold is applied — every image the user sent in this chat is a candidate.

**Rationale:** Chat images occupy the same 1024-dim `voyage-multimodal-3.5` vector space as material chunk visual embeddings — they can be directly compared and merged without any intermediate step. Images the user explicitly attached are high-prior context; the +0.20 boost ensures a moderately relevant chat image (0.50 raw → 0.70 boosted) outranks a well-matched material chunk (0.65). Fetching all images per chat is cheap in practice — a conversation might have 10–20 images at most.

**Alternative considered:** Separate `retrieve_chat_images()` function with threshold=0.65 and top-K=2. Rejected — a separate retrieval path duplicates the embedding call, bypasses the unified ranking, and silently drops images below the threshold that the user may expect to be recalled.

---

- **Base64 payload size** → Each 3MB image becomes ~4MB base64. Five images = ~20MB in a single LLM API call. Mitigation: hard cap at 5 images × 10MB each; in practice, screenshots are 1–3MB.
- **S3 upload latency before send** → User perceives a delay between clicking send and message appearing. Mitigation: show per-image upload progress in the preview strip; uploads happen in parallel.
- **Synchronous embedding latency** → Embedding 1–5 images (S3 fetch + Lambda invoke) adds ~1–2s before streaming begins. Mitigation: this is a one-time cost per send; the embedding completes well within the LLM's TTFT window; users are accustomed to a brief pause after clicking send.
- **S3 cost for abandoned images** → User stages images but never sends. Mitigation: only upload on send (not on stage); staged images stay as `File` objects in browser memory.
- **Non-vision model confusion** → User selects a non-vision model, stages images, clicks send, sees a banner. The UX is intentionally blocking rather than auto-switching. Mitigation: the banner names the specific model that blocked the send.

## Migration Plan

Run the following SQL against the database before deploying backend changes:

```sql
ALTER TABLE chat_messages ADD COLUMN image_s3_keys TEXT[] DEFAULT '{}';

CREATE TABLE chat_image_embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    s3_key      TEXT NOT NULL,
    chat_id     INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    message_id  INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    embedding   VECTOR(1024) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON chat_image_embeddings (chat_id);
```

Then:

1. Deploy backend changes (new upload action, extended stream_send, LLM layer)
2. Deploy frontend changes
3. No rollback complexity — existing messages have `image_s3_keys = '{}'`; the column is additive; `chat_image_embeddings` starts empty

## Open Questions

- Should the presigned download URL TTL match the existing material download TTL, or be longer (images are conversation artifacts, not frequently re-accessed)?
- Should there be a lifecycle policy on `chat-images/` S3 prefix (e.g., delete after 90 days)?
