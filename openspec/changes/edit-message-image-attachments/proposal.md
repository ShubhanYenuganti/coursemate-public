## Why

When a user edits a message that originally had image attachments, the images silently disappear — the edit textarea shows only text, and the edited send does not propagate the original images to the LLM. This makes image-bearing messages effectively uneditable in any meaningful way.

## What Changes

- The message API response includes `image_s3_keys` alongside `image_download_urls` so the frontend can reconstruct the staging state on edit
- Entering edit mode on a message with images pre-populates a fully mutable staging strip (thumbnails with × dismiss; + add button for new images)
- `handleEditMessage` uploads any newly added images before sending, then includes all final `image_s3_keys` in the `stream_edit` payload
- `stream_edit` / `_edit_message` backend accepts `image_attachments`, embeds newly added images, deletes embedding rows for removed images, and passes final keys to `synthesize()`

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `chat-image-input`: Edit mode pre-populates the staging strip from existing message images; mutable (add/remove) during edit; edited send clears strip on success
- `chat-image-upload`: Message responses include `image_s3_keys` alongside presigned download URLs; `stream_edit` accepts `image_attachments` and updates persisted `image_s3_keys` on the message row
- `chat-image-message-display`: Message API response shape extended with `image_s3_keys` field
- `chat-image-embeddings`: `stream_edit` embeds only newly added images; deletes `chat_image_embeddings` rows for s3_keys removed during edit
- `chat-image-llm-integration`: `_edit_message` / `stream_edit` passes final `image_s3_keys` to `synthesize()`, same as `stream_send`

## Impact

- `src/ChatTab.jsx`: edit state, `handleEditMessage`, message bubble component
- `api/chat.py`: `_edit_message`, message history response serialization
- `api/llm.py`: `synthesize()` call site in `_edit_message` (already accepts `image_s3_keys`)
- No schema migration needed — `image_s3_keys` column and `chat_image_embeddings` table already exist
