## Context

The chat image attachments feature (`chat-image-attachments`, archived 2026-04-18) built a complete send-time image pipeline: S3 upload → persist `image_s3_keys` → embed → synthesize. The edit path (`_edit_message` / `stream_edit`) was explicitly out of scope. As a result, editing a message with images silently drops them: the edit textarea is text-only, `stream_edit` sends no images, and `synthesize()` receives no `image_s3_keys`.

The infrastructure needed is already present: `image_s3_keys` is persisted on the message row, `chat_image_embeddings` rows exist, and `synthesize()` already accepts `image_s3_keys`. This change wires the edit path through that same infrastructure.

## Goals / Non-Goals

**Goals:**
- Entering edit mode on a message pre-populates a fully mutable staging strip from the message's existing images
- Users can dismiss (remove) existing images and add new ones during edit
- On send, newly added images are uploaded to S3 and embedded; removed images have their `chat_image_embeddings` rows deleted; the message row's `image_s3_keys` is updated
- The edited send delivers the final image set to the LLM via `synthesize()`, identical to the original send

**Non-Goals:**
- Drag-and-drop image reordering during edit
- Image replacement (remove + add is sufficient)
- Retroactive embedding of images on messages created before this feature shipped (those have no `image_s3_keys`)

## Decisions

### D1: Add `image_s3_keys` to message API response

**Decision:** Extend the message serialization to return `image_s3_keys: string[]` alongside `image_download_urls`. The frontend uses `image_s3_keys[i]` paired with `image_download_urls[i].filename` to reconstruct the `{s3_key, filename}` pairs needed for the edit payload. Index correspondence is guaranteed because both arrays are generated together in the same serialization loop.

**Alternative considered:** Parse the s3_key out of the presigned download URL. Rejected — presigned URL format is an S3 implementation detail; parsing it creates fragile coupling.

### D2: Staged image type split — `existing` vs `new`

**Decision:** The frontend staging state holds entries of two kinds:
- `existing`: pre-populated on edit start from `image_s3_keys` + `image_download_urls`. No `File` object. Thumbnail src = presigned download URL from the message. No upload needed on send.
- `new`: created via file picker or paste, same as today. Thumbnail src = `URL.createObjectURL(file)`. Requires upload before send.

On send, both kinds contribute `{s3_key, filename}` to `image_attachments`. The backend does not distinguish them.

**Alternative considered:** Convert existing images back to `File` objects by fetching them from S3. Rejected — unnecessary network round-trip; we already have all the information we need (s3_key, filename, presigned URL for display).

### D3: Backend embedding diff by s3_key

**Decision:** `_edit_message` computes:
```
original_keys = set(msg['image_s3_keys'] or [])
final_keys    = {a['s3_key'] for a in image_attachments}  (from request, or original if not provided)
added_keys    = final_keys - original_keys
removed_keys  = original_keys - final_keys
```
Only `added_keys` are embedded. `chat_image_embeddings` rows for `removed_keys` are deleted (WHERE `message_id = %s AND s3_key = ANY(%s)`). The message row is updated: `UPDATE chat_messages SET image_s3_keys = %s WHERE id = %s`.

**Alternative considered:** Re-embed all images on every edit. Rejected — wasteful; embeddings for unchanged images already exist and are correct.

### D4: Model gating applies during edit

**Decision:** If the user adds new images (or retains existing ones) in the edit staging strip and the selected model is in `NON_VISION_MODEL_IDS`, the same banner fires and the edited send is aborted. Same logic as `handleSend`.

**Rationale:** Consistency. The LLM call in `_edit_message` routes through the same `synthesize()` path as `stream_send`; non-vision models will fail the same way.

### D5: Presigned URL expiry on existing image thumbnails during edit

**Decision:** Accept that presigned download URLs used as thumbnail src during edit may expire (TTL = S3 presigned URL expiry, typically 1 hour). An expired URL means a broken `<img>` during editing — cosmetic only; the `s3_key` is what matters for the send payload.

**Rationale:** The TTL is long enough that it will not affect normal usage. Adding a re-fetch mechanism adds complexity for a rare edge case. The user can always remove and re-add an image if they need a fresh thumbnail.

## Risks / Trade-offs

- **index correspondence assumption (D1)** → `image_s3_keys[i]` and `image_download_urls[i]` must be generated in the same order in the API. Risk: future refactoring of the serialization loop breaks the pairing. Mitigation: this is a simple constraint to document and enforce in the serialization code.
- **Concurrent edits** → Two simultaneous edit requests for the same message could produce a conflicting `image_s3_keys` update. Risk is low (unlikely in practice); no pessimistic locking is added.
- **Orphaned S3 objects** → When an image is removed during edit, the S3 object under `chat-images/` is not deleted (only the `chat_image_embeddings` row is). This is consistent with the original design (no S3 lifecycle cleanup is in scope).

## Migration Plan

No schema migration required — `image_s3_keys TEXT[]` and `chat_image_embeddings` already exist from the prior change.

Deploy order:
1. Backend: extend message serialization to include `image_s3_keys`; extend `_edit_message` to accept and process `image_attachments`
2. Frontend: add edit-mode staging strip pre-population and mutable controls; extend `handleEditMessage` to upload new images and include `image_attachments` in the payload

Rollback: backend changes are additive (new field in response, new optional field in request); frontend changes are isolated to edit mode. Rolling back either side independently leaves the other side gracefully no-op.

## Open Questions

_(none — all decisions resolved in exploration)_
