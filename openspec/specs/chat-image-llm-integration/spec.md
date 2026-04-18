# chat-image-llm-integration Specification

## Purpose
Defines how image S3 keys are passed through the synthesis layer to each LLM provider (Anthropic, OpenAI, Gemini), how retrieved past chat images are injected into the LLM context, and how chat_id propagates from the agentic loop to retrieve_chunks for image retrieval.

## Requirements

### Requirement: synthesize() accepts image S3 keys
The `synthesize()` function in `api/llm.py` SHALL accept an optional `image_s3_keys: list[str]` parameter. When provided, the function SHALL fetch each image from S3, base64-encode the bytes, and include them in the provider-specific multimodal content block ahead of the text content.

#### Scenario: Synthesis with images
- **WHEN** `synthesize()` is called with `image_s3_keys=["chat-images/42/abc.png"]`
- **THEN** the image is fetched from S3, base64-encoded, and included in the LLM request content block before the user text

#### Scenario: Synthesis without images
- **WHEN** `synthesize()` is called without `image_s3_keys` or with an empty list
- **THEN** behavior is identical to the current text-only path

### Requirement: Anthropic multimodal content block format
For the Anthropic provider, the system SHALL construct the `messages[0].content` field as a list where each image appears as `{"type": "image", "source": {"type": "base64", "media_type": "<mime>", "data": "<b64>"}}` followed by `{"type": "text", "text": "<user_message>"}`.

#### Scenario: Anthropic request with two images
- **WHEN** two images are provided and the provider is `claude`
- **THEN** the request body `messages[0].content` is a list: `[image_block_1, image_block_2, text_block]`

### Requirement: OpenAI multimodal content block format
For the OpenAI provider, the system SHALL construct the user message `content` field as a list where each image appears as `{"type": "image_url", "image_url": {"url": "data:<mime>;base64,<b64>"}}` followed by `{"type": "text", "text": "<user_message>"}`.

#### Scenario: OpenAI request with one image
- **WHEN** one image is provided and the provider is `openai`
- **THEN** the request body user content is `[image_url_block, text_block]`

### Requirement: Gemini multimodal content block format
For the Gemini provider, the system SHALL construct the user parts as a list where each image appears as `{"inline_data": {"mime_type": "<mime>", "data": "<b64>"}}` followed by `{"text": "<user_message>"}`.

#### Scenario: Gemini request with images
- **WHEN** images are provided and the provider is `gemini`
- **THEN** the request parts list contains inline_data blocks followed by the text part

### Requirement: synthesize_with_clarification() propagates images
The `synthesize_with_clarification()` function SHALL accept and propagate `image_s3_keys` to all internal `synthesize()` calls it delegates to.

#### Scenario: Clarification path with images
- **WHEN** `synthesize_with_clarification()` is called with `image_s3_keys`
- **THEN** images are included in the LLM call within the clarification flow

### Requirement: Image embeddings stored synchronously on send
The `stream_send` handler in `api/chat.py` SHALL embed each uploaded image synchronously via the `embed_query` Lambda (`image_base64` path) and persist the resulting 1024-dim vector to `chat_image_embeddings` **before** the synthesis call begins. No background thread is used.

#### Scenario: Images sent with message
- **WHEN** `stream_send` receives `image_s3_keys=["chat-images/42/abc.png"]`
- **THEN** each image is fetched from S3, base64-encoded, sent to `embed_query` Lambda via `image_base64`, and the resulting embedding is inserted into `chat_image_embeddings` before `synthesize()` is called

#### Scenario: No images sent
- **WHEN** `stream_send` receives an empty `image_s3_keys`
- **THEN** no embedding calls are made; behavior is unchanged

### Requirement: retrieve_chunks() includes all chat image candidates with a score boost
The `retrieve_chunks()` function in `api/rag.py` SHALL accept an optional `chat_id: int = None` parameter. When provided, after computing `vis_emb` via `_invoke_embed_query`, it SHALL cosine-search **all** `chat_image_embeddings` rows for that `chat_id` (no threshold) and include them in the merged ranking with a score boost of `+0.20` applied to their raw cosine similarity before merge. When `chat_id` is absent, behavior is unchanged.

#### Scenario: Past images always recalled when chat_id provided
- **WHEN** `retrieve_chunks(conn, query, material_ids, chat_id=7)` is called and chat 7 has 3 stored image embeddings
- **THEN** all 3 are scored (raw cosine similarity + 0.20 boost), merged into the ranked candidate pool alongside material chunks, and the top-K results returned

#### Scenario: chat_id absent
- **WHEN** `retrieve_chunks(conn, query, material_ids)` is called without `chat_id`
- **THEN** only `chunks` table is searched; behavior is identical to current

### Requirement: execute_search_materials() and run_agent_openai() propagate chat_id to retrieve_chunks
The `execute_search_materials()` function in `api/tools.py` SHALL accept an optional `chat_id: int = None` parameter and pass it through to `retrieve_chunks()`. The `run_agent_openai()` function in `api/llm.py` already holds `chat_id`; it SHALL pass it to `execute_search_materials()` on the initial search call.

#### Scenario: Agentic loop with chat_id
- **WHEN** `run_agent_openai` is called with `chat_id=7`
- **THEN** `execute_search_materials(..., chat_id=7)` → `retrieve_chunks(..., chat_id=7)` is called, and any matching image candidates are returned alongside text chunks

### Requirement: LLM layer handles chat_image context rows
The `run_agent_openai()` function in `api/llm.py` SHALL inspect the context returned from the initial `execute_search_materials` call for rows with `chunk_type: "chat_image"`. For each such row, it SHALL fetch the image bytes from S3 using the row's `s3_key`, base64-encode them, and prepend them as image blocks to `messages[0]["content"]`. Current-message images are prepended before retrieved past images; the text block is always last.

#### Scenario: Retrieved past image injected into context
- **WHEN** `retrieve_chunks` returns a row with `chunk_type: "chat_image"` and `s3_key: "chat-images/42/abc.png"`
- **THEN** the LLM receives that image as a base64 image block in `messages[0].content` before the user text

#### Scenario: No chat_image rows
- **WHEN** no `chunk_type: "chat_image"` rows are present in context
- **THEN** `messages[0].content` remains a plain string — identical to today's behavior
