# chat-image-embeddings Specification

## Purpose
Defines the embedding pipeline for chat-attached images: extending the embed_query Lambda to accept image input, the chat_image_embeddings table schema, synchronous embedding before synthesis, and image retrieval through the unified retrieve_chunks pipeline with a score boost.

## Requirements

### Requirement: embed_query Lambda accepts image_base64 input
The `embed_query` Lambda SHALL accept an optional `image_base64` field in its request body. When present, the Lambda SHALL decode the base64 string to bytes, open as a PIL Image, embed using `voyage-multimodal-3.5` with `input_type="document"`, and return `{ "visual_embedding": [...], "dim": 1024 }`. When absent, existing text embedding behavior SHALL be unchanged.

#### Scenario: Image embedding via Lambda
- **WHEN** the Lambda is invoked with `{ "image_base64": "<base64-encoded PNG or JPEG>" }`
- **THEN** the response is `{ "visual_embedding": [<1024 floats>], "dim": 1024 }` with status 200

#### Scenario: Text-only request unchanged
- **WHEN** the Lambda is invoked with `{ "query": "some text" }` and no `image_base64`
- **THEN** the response is identical to current behavior: `{ "text_embedding": [...], "visual_embedding": [...], "embedding": [...], "dim": 1024 }`

#### Scenario: Missing both query and image_base64
- **WHEN** the Lambda is invoked with neither `query` nor `image_base64`
- **THEN** the response is status 400 with an error message

### Requirement: chat_image_embeddings table stores per-image vectors
The database SHALL have a `chat_image_embeddings` table with columns: `id UUID`, `s3_key TEXT`, `chat_id INTEGER`, `message_id INTEGER`, `filename TEXT`, `embedding VECTOR(1024)`, `created_at TIMESTAMPTZ`. The table SHALL have an `ivfflat` index on `embedding` and a btree index on `chat_id`. Rows SHALL be cascade-deleted when the parent chat or message is deleted.

#### Scenario: Row inserted after image send
- **WHEN** a chat message with images is sent and embedding completes
- **THEN** one row per image exists in `chat_image_embeddings` with the correct `chat_id`, `message_id`, `s3_key`, and a non-null `embedding`

### Requirement: Image embedding runs synchronously before synthesis
After storing the user message and before calling `synthesize()`, the `stream_send` handler SHALL embed each image synchronously. For each image: fetch bytes from S3, base64-encode, invoke `embed_query` with `image_base64`, receive `visual_embedding`, insert into `chat_image_embeddings`. This ensures embeddings are available as candidates in the synthesis call that immediately follows. Embedding failures SHALL be logged but SHALL NOT abort the send — synthesis proceeds without the failed image as a retrieval candidate.

#### Scenario: Embedding completes before synthesis
- **WHEN** a message with 2 images is sent
- **THEN** both images are embedded and stored in `chat_image_embeddings` before `synthesize()` is called; synthesis can retrieve them as candidates in the same request

#### Scenario: Embedding Lambda failure
- **WHEN** the `embed_query` Lambda invocation fails for one image
- **THEN** the failure is logged; `synthesize()` is still called; the failed image is not available as a retrieval candidate but no error is shown to the user

### Requirement: Past conversation images retrieved through unified retrieve_chunks pipeline
All chat image embeddings for a given `chat_id` are candidates in every `retrieve_chunks()` call. When `retrieve_chunks(conn, query, material_ids, chat_id=<id>)` is called, the system SHALL fetch all rows from `chat_image_embeddings` WHERE `chat_id = <id>`, compute cosine similarity against the query's `visual_embedding` for each row, apply a **+0.20 flat score boost**, and merge these candidates into the same ranked pool as material chunks. No similarity threshold is applied. Retrieved image rows carry `chunk_type: "chat_image"` and `s3_key`; the LLM layer converts them to base64 image blocks before synthesis.

#### Scenario: Past image returned as top-ranked candidate
- **WHEN** `retrieve_chunks(conn, query, material_ids, chat_id=7)` is called and chat 7 has a stored image with cosine similarity 0.55 to the query
- **THEN** that image candidate receives a boosted score of 0.75 and ranks ahead of material chunks below 0.75; it is returned with `chunk_type: "chat_image"` and its `s3_key`

#### Scenario: All chat images included regardless of raw similarity
- **WHEN** `retrieve_chunks` is called and a chat image has cosine similarity 0.30 to the query
- **THEN** it is still included as a candidate with boosted score 0.50 and participates in the top-K merge

#### Scenario: Current-message images and retrieved past images combined in LLM context
- **WHEN** the current message has 1 attached image and 1 past image is returned by `retrieve_chunks`
- **THEN** both images appear as base64 image blocks in the LLM content block (current-message images first, then retrieved past images, then the text block)

#### Scenario: No chat_id provided
- **WHEN** `retrieve_chunks()` is called without `chat_id`
- **THEN** only the `chunks` table is searched; behavior is identical to current
