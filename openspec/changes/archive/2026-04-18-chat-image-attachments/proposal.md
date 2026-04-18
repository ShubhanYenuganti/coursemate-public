## Why

Users need to share lecture slides, whiteboard photos, and problem screenshots directly in chat to get visual understanding from the AI — text-only input forces lossy workarounds like manually transcribing image content. Vision-capable models already support this; the product just hasn't exposed it yet.

## What Changes

- Add a file picker (attachment icon) and clipboard paste handler to the chat input bar for PNG/JPEG images
- Show image thumbnails in a preview strip above the textarea while images are staged (pre-send)
- Upload staged images to S3 under `chat-images/{user_id}/{uuid}.{ext}` via a new upload action on `/api/chat`
- Persist S3 keys in a new `image_s3_keys TEXT[]` column on `chat_messages`
- Render a compact attachment bar in user message bubbles (filename links → presigned S3 download URLs)
- Gate model selection: block send and show a top banner when a non-vision model is selected with images staged
- Extend the LLM synthesis layer to build multimodal content blocks (base64 from S3) for Anthropic, OpenAI, and Gemini
- Embed each uploaded image synchronously via `voyage-multimodal-3.5` (using the existing `embed_query` Lambda, extended with `image_base64` input) and store in a new `chat_image_embeddings` table before synthesis begins
- At synthesis time, all stored image embeddings for the current chat are retrieved as candidates in the same unified vector search as material chunks, with a +0.20 score boost so they rank above material content — no separate retrieval step or similarity threshold

## Capabilities

### New Capabilities

- `chat-image-input`: Attach up to 5 images (PNG/JPEG, ≤10MB each) to a chat message via file picker or clipboard paste when the textarea is focused; preview strip shows thumbnails with dismiss controls; send button active with images even without text
- `chat-image-upload`: Pre-send S3 upload flow for chat images; new `upload_image` action on `/api/chat` returns a presigned PUT URL; keys stored in `chat_messages.image_s3_keys`
- `chat-image-llm-integration`: Multimodal content block construction for vision-capable providers (Anthropic, OpenAI, Gemini) using base64-encoded image bytes fetched from S3 at call time
- `chat-image-message-display`: Compact attachment bar in user message bubbles showing image filenames as presigned download links; replaces the staging preview after send
- `chat-image-model-gating`: Non-vision models (Deep Research variants) blocked when images are staged; top-of-screen banner shown on blocked send attempt; user re-selects a vision model manually
- `chat-image-embeddings`: Each uploaded image is embedded synchronously using `voyage-multimodal-3.5` via the extended `embed_query` Lambda before synthesis begins; embeddings stored in `chat_image_embeddings`; all images from the current chat are included as ranked candidates in every subsequent `retrieve_chunks` call with a +0.20 score boost, making them rank above material chunks

### Modified Capabilities

- `chat-image-llm-integration`: Extended to inject past conversation images into the LLM context; images surface through the unified `retrieve_chunks` pipeline (not a separate lookup) and are included as base64 image blocks when retrieved
- `follow-up-chips`: No requirement changes — implementation unaffected

## Impact

- **Frontend**: `src/ChatTab.jsx` — input bar, message bubble renderer, model selection UI
- **API**: `api/chat.py` — new `upload_image` action, `stream_send` extended with `image_s3_keys`
- **LLM layer**: `api/llm.py` — `synthesize()` and `synthesize_with_clarification()` signatures extended; per-provider multimodal block construction
- **DB**: `chat_messages` table — new `image_s3_keys TEXT[]` column; new `chat_image_embeddings` table with `VECTOR(1024)` and `ivfflat` index
- **S3**: New key prefix `chat-images/` alongside existing `materials/`
- **Lambda**: `embed_query` extended with optional `image_base64` input path using the same `voyage-multimodal-3.5` model already used by `embed_materials`
- **Dependencies**: No new packages — uses existing `boto3`, `voyageai`, `Pillow` (already in `embed_query` requirements)
