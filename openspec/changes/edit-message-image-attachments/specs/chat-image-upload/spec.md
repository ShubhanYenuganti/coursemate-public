## ADDED Requirements

### Requirement: stream_edit accepts image_attachments and updates persisted image_s3_keys
The `_edit_message` handler SHALL accept an optional `image_attachments: list[{s3_key, filename}]` field in the request payload. When provided, this list represents the final image set for the edited message. The handler SHALL update the message row: `UPDATE chat_messages SET image_s3_keys = <final_keys> WHERE id = <message_id>`. When not provided, the original `image_s3_keys` from the message row are used unchanged.

#### Scenario: Edit with modified image set updates persisted keys
- **WHEN** `stream_edit` is called with `image_attachments: [{s3_key: "chat-images/42/new.png", filename: "new.png"}]` on a message that previously had `image_s3_keys = ["chat-images/42/old.png"]`
- **THEN** the message row's `image_s3_keys` is updated to `["chat-images/42/new.png"]`

#### Scenario: Edit with no image_attachments field leaves keys unchanged
- **WHEN** `stream_edit` is called without an `image_attachments` field
- **THEN** the message row's `image_s3_keys` is unchanged

#### Scenario: Edit removing all images clears image_s3_keys
- **WHEN** `stream_edit` is called with `image_attachments: []`
- **THEN** the message row's `image_s3_keys` is updated to `'{}'`

### Requirement: New images added during edit are uploaded to S3 before stream_edit
When the user adds new images in edit mode, the frontend SHALL upload them to S3 via the existing `upload_image` action before calling `stream_edit`, in parallel with any other new images. The `stream_edit` call SHALL include the resulting `s3_key` values in `image_attachments` alongside retained existing image s3_keys.

#### Scenario: New image uploaded before edit send
- **WHEN** the user adds one new image in edit mode and clicks send
- **THEN** the frontend PUTs the image to S3 first, then includes its `s3_key` in `image_attachments` in the `stream_edit` payload

## MODIFIED Requirements

### Requirement: S3 keys persisted in chat_messages
The `chat_messages` table SHALL have an `image_s3_keys TEXT[]` column (default `'{}'`). When a message with images is sent via `stream_send`, the array of S3 keys SHALL be stored in this column. When a message is edited via `stream_edit` with an `image_attachments` payload, the column SHALL be updated to reflect the final image set.

#### Scenario: New message with images stores keys
- **WHEN** `stream_send` is called with `image_s3_keys: ["chat-images/42/abc.png"]`
- **THEN** the inserted `chat_messages` row has `image_s3_keys = ARRAY['chat-images/42/abc.png']`

#### Scenario: Message without images stores empty array
- **WHEN** `stream_send` is called without `image_s3_keys`
- **THEN** the inserted row has `image_s3_keys = '{}'`

#### Scenario: Edited message with updated images persists new keys
- **WHEN** `stream_edit` is called with `image_attachments: [{s3_key: "chat-images/42/b.png", filename: "b.png"}]` on a message that had `image_s3_keys = ["chat-images/42/a.png"]`
- **THEN** the message row's `image_s3_keys` is updated to `ARRAY['chat-images/42/b.png']`
