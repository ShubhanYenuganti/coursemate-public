## 1. Backend — Upload Endpoint

- [x] 1.1 Add `upload_image` action handler to `api/chat.py` that validates `filename` and `content_type` (must be `image/png` or `image/jpeg`)
- [x] 1.2 Generate a presigned S3 PUT URL for `chat-images/{user_id}/{uuid}.{ext}` using `s3_utils`
- [x] 1.3 Return `{ upload_url, s3_key }` JSON response from the upload action

## 2. Backend — stream_send Extension

- [x] 2.1 Accept `image_attachments: list[{s3_key, filename}]` in `stream_send` handler in `api/chat.py`; extract `image_s3_keys` for persistence and pass `(s3_key, filename)` pairs to the embedding pipeline
- [x] 2.2 Persist `image_s3_keys` into the `chat_messages` INSERT
- [x] 2.3 Generate presigned download URLs for `image_s3_keys` when loading message history (chat list and message fetch responses)
- [x] 2.4 Pass `image_s3_keys` through to `synthesize()` and `synthesize_with_clarification()` calls

## 3. Backend — LLM Multimodal Integration

- [x] 3.1 Add `image_s3_keys: list[str] = None` parameter to `synthesize()` signature
- [x] 3.2 Implement S3 fetch + base64 encoding helper for a list of S3 keys
- [x] 3.3 Build Anthropic multimodal content block: image blocks (`type: image, source: {type: base64, ...}`) followed by text block
- [x] 3.4 Build OpenAI multimodal content block: image_url blocks (`data:<mime>;base64,...`) followed by text block
- [x] 3.5 Build Gemini multimodal parts: `inline_data` blocks followed by text part
- [x] 3.6 Add `image_s3_keys` parameter to `synthesize_with_clarification()` and propagate to all internal synthesize calls

## 4. Frontend — Model Gating

- [x] 4.1 Define `NON_VISION_MODEL_IDS` Set in `ChatTab.jsx` with the three non-vision model IDs
- [x] 4.2 In `handleSend`, check if images are staged and selected model is in `NON_VISION_MODEL_IDS`; abort send and show banner if so
- [x] 4.3 Implement top-of-screen dismissible banner component showing `"<model label> does not support image inputs. Please select a different model."`

## 5. Frontend — Image Staging UI

- [x] 5.1 Add `images` state (`useState([])`) to hold staged `File` objects
- [x] 5.2 Add hidden `<input type="file" accept="image/png,image/jpeg" multiple>` triggered by an attachment icon button in the input bar
- [x] 5.3 Implement file picker `onChange` handler: filter by size (≤10MB), enforce 5-image cap, add to `images` state
- [x] 5.4 Add `onPaste` handler on the textarea: intercept `ClipboardEvent`, extract `image/*` items via `FileReader`, apply same size/cap limits
- [x] 5.5 Render preview strip above the textarea when `images.length > 0`: thumbnail (`URL.createObjectURL`), filename, and `×` dismiss button per image
- [x] 5.6 Enable send button when `images.length > 0` even if textarea is empty

## 6. Frontend — Send Flow with Images

- [x] 6.1 In `handleSend`, before calling the API, upload all staged images in parallel via the `upload_image` action and collect `s3_keys`
- [x] 6.2 Include `image_attachments: [{s3_key, filename}]` array in the `stream_send` POST payload, using the original `File.name` as `filename`
- [x] 6.3 Show per-image upload progress state in the preview strip (e.g., spinner overlay on thumbnail) during the upload phase
- [x] 6.4 Clear `images` state and preview strip after successful send
- [x] 6.5 On upload failure, surface an error and abort send (do not partially send)

## 7. Lambda — embed_query Extension

- [x] 7.1 Add `image_base64` input path to `lambda/embed_query/handler.py`: decode base64 → PIL Image → `vo.multimodal_embed(inputs=[[img]], model='voyage-multimodal-3.5', input_type='document')` → return `{ visual_embedding, dim }`
- [x] 7.2 Add `Pillow` to `lambda/embed_query/requirements.txt` if not already present
- [x] 7.3 Add `embed_image_via_lambda(image_bytes: bytes) -> list | None` helper to `services/query/persistence.py` that base64-encodes bytes and invokes `embed_query` with `image_base64`

## 8. Backend — Image Embedding Pipeline

- [x] 8.1 Add `embed_and_store_chat_images(conn, chat_id, message_id, image_s3_keys_with_filenames: list[tuple[str, str]])` function in `api/chat.py`: for each `(s3_key, filename)` pair, fetch bytes from S3, call `embed_image_via_lambda`, insert row into `chat_image_embeddings`
- [x] 8.2 In `stream_send` handler, call `embed_and_store_chat_images` **synchronously** after storing the user message and before calling `synthesize()` — no background thread

## 9. Backend — Retrieval Integration

- [x] 9.1 In `api/rag.py`, add `chat_id: int = None` parameter to `retrieve_chunks()`; when provided, after computing `vis_emb` call `_search_chat_images(conn, vis_emb, chat_id)` (new helper) and merge results into the ranked candidate pool before the top-K slice
- [x] 9.2 Add `_search_chat_images(conn, emb, chat_id)` helper in `api/rag.py` (or `services/query/retrieval.py`): fetches ALL rows from `chat_image_embeddings` WHERE `chat_id = %s`, computes cosine similarity against `emb` for each, applies a `+0.20` score boost, and returns list of dicts with `s3_key`, `filename`, `chunk_type: "chat_image"`, `similarity` (boosted); no threshold filtering
- [x] 9.3 In `api/tools.py`, add `chat_id: int = None` parameter to `execute_search_materials()` and pass it through to `retrieve_chunks()`
- [x] 9.4 In `api/llm.py`, pass `chat_id` to `execute_search_materials()` in the initial search call inside `run_agent_openai()`
- [x] 9.5 In `api/llm.py`, after the initial `execute_search_materials` call in `run_agent_openai()`, extract any `chunk_type: "chat_image"` rows from the returned context; for each, fetch S3 bytes and base64-encode using the helper from task 3.2; append as image blocks to `messages[0]["content"]` after current-message image blocks and before the text block

## 10. Frontend — Message History Display

- [x] 10.1 Extend user message bubble renderer to accept `image_download_urls` (array of `{filename, url}` objects from the API)
- [x] 10.2 Render compact attachment bar above message text when `image_download_urls` is non-empty: paperclip icon + filename links
- [x] 10.3 Each filename link SHALL use `<a href={url} download>` to trigger browser download on click
- [x] 10.4 Apply subdued styling to the attachment bar (small font, muted color, single line wrapping)
