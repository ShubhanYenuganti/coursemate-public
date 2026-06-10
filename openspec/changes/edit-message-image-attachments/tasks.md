## 1. Backend — Message Response

- [x] 1.1 Add `image_s3_keys` to the SELECT in the message history serialization in `api/chat.py` so the field is returned alongside `image_download_urls` in all message list and fetch responses
- [x] 1.2 In the serialization loop that generates `image_download_urls`, ensure `image_s3_keys` is included in the same response object and in the same index order as `image_download_urls`

## 2. Backend — stream_edit Extension

- [x] 2.1 Add `image_s3_keys` to the SELECT in `_edit_message` so the original keys are available for diff computation
- [x] 2.2 Accept `image_attachments: list[{s3_key, filename}]` from the request payload in `_edit_message`; if absent, default to the original `image_s3_keys` as the final set
- [x] 2.3 Compute `added_keys = final_keys - original_keys` and `removed_keys = original_keys - final_keys`
- [x] 2.4 DELETE from `chat_image_embeddings` WHERE `message_id = <id> AND s3_key = ANY(<removed_keys>)` when `removed_keys` is non-empty
- [x] 2.5 Embed each key in `added_keys` synchronously: fetch S3 bytes → base64 → invoke `embed_query(image_base64=...)` → insert row into `chat_image_embeddings` with `chat_id`, `message_id`, `s3_key`, `filename`, `embedding`; log and skip on Lambda failure (do not abort)
- [x] 2.6 UPDATE `chat_messages SET image_s3_keys = <final_keys_array> WHERE id = <message_id>`
- [x] 2.7 Pass `image_s3_keys=list(final_keys)` to the `synthesize()` call in `_edit_message`

## 3. Frontend — Staged Image Type

- [x] 3.1 Extend the staging state entry type to support `kind: 'existing'` entries with `{s3_key, filename, url}` (presigned download URL as thumbnail src) alongside the existing `kind: 'new'` `File`-based entries
- [x] 3.2 Update thumbnail rendering in the preview strip to use `entry.url` as `<img src>` for `existing` entries (instead of `URL.createObjectURL`)

## 4. Frontend — Edit Mode Pre-Population

- [x] 4.1 In `onEditStart`, if the target message has `image_s3_keys` and `image_download_urls`, initialise the edit staging state with one `existing` entry per image (index-paired: `image_s3_keys[i]` + `image_download_urls[i].filename` + `image_download_urls[i].url`)
- [x] 4.2 Show the staging strip in edit mode when the pre-populated entry list is non-empty
- [x] 4.3 Wire the × dismiss button to remove entries from the edit staging state (works for both `existing` and `new` entries)
- [x] 4.4 Wire the file picker and paste handler to append `new` entries during edit, subject to the 5-image cap across all entries (existing retained + new)

## 5. Frontend — Edit Send Flow

- [x] 5.1 Apply model gating in `handleEditMessage`: if any images are staged (existing or new) and the selected model is in `NON_VISION_MODEL_IDS`, abort and show the banner
- [x] 5.2 In `handleEditMessage`, upload all `new` entries in parallel via `upload_image` before calling `stream_edit`; collect their `s3_key` values
- [x] 5.3 Build `image_attachments` as `[...existingEntries.map(e => ({s3_key: e.s3_key, filename: e.filename})), ...newlyUploadedEntries]` and include in the `stream_edit` payload
- [x] 5.4 Clear the edit staging state after a successful edited send
- [x] 5.5 On upload failure for a new image during edit, surface an error and abort (do not partially send)
