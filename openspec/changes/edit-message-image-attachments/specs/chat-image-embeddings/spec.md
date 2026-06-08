## ADDED Requirements

### Requirement: stream_edit embeds only newly added images
When `_edit_message` receives `image_attachments`, it SHALL compute the set of added keys (`final_keys - original_keys`) and embed only those. For each added key: fetch bytes from S3, base64-encode, invoke `embed_query` with `image_base64`, insert result into `chat_image_embeddings` with `chat_id`, `message_id`, `s3_key`, `filename`, and `embedding`. This runs synchronously before `synthesize()` is called, consistent with the `stream_send` path.

#### Scenario: Only new images are embedded on edit
- **WHEN** a message had `image_s3_keys = ["chat-images/42/a.png"]` and `stream_edit` is called with `image_attachments: [{s3_key: "chat-images/42/a.png", ...}, {s3_key: "chat-images/42/b.png", ...}]`
- **THEN** only `chat-images/42/b.png` is sent to `embed_query`; no new embedding row is inserted for `a.png`

#### Scenario: No added images means no embedding calls on edit
- **WHEN** `stream_edit` is called with the same `image_attachments` as the original `image_s3_keys` (no additions)
- **THEN** no `embed_query` invocations are made and no new rows are inserted into `chat_image_embeddings`

#### Scenario: All new images in an edit are embedded
- **WHEN** a message had no images and `stream_edit` is called with two new `image_attachments`
- **THEN** both images are embedded and inserted into `chat_image_embeddings` before `synthesize()` is called

### Requirement: stream_edit deletes chat_image_embeddings rows for removed images
When `_edit_message` receives `image_attachments`, it SHALL compute the set of removed keys (`original_keys - final_keys`) and DELETE the corresponding rows from `chat_image_embeddings` WHERE `message_id = <message_id> AND s3_key = ANY(<removed_keys>)`.

#### Scenario: Removed image's embedding row is deleted
- **WHEN** a message had `image_s3_keys = ["chat-images/42/a.png", "chat-images/42/b.png"]` and `stream_edit` is called with `image_attachments: [{s3_key: "chat-images/42/a.png", ...}]`
- **THEN** the `chat_image_embeddings` row for `chat-images/42/b.png` with this `message_id` is deleted

#### Scenario: Retained images' embedding rows are not deleted
- **WHEN** a message had one image and `stream_edit` retains it unchanged
- **THEN** the `chat_image_embeddings` row for that image is not deleted

#### Scenario: All images removed clears all embedding rows for the message
- **WHEN** `stream_edit` is called with `image_attachments: []` on a message with two images
- **THEN** both `chat_image_embeddings` rows for that `message_id` are deleted

#### Scenario: No removed images means no deletions
- **WHEN** `stream_edit` is called with the same or a superset of `image_attachments` vs original keys
- **THEN** no rows are deleted from `chat_image_embeddings`
