# chat-image-upload Specification

## Purpose
Defines how users upload images to S3 before sending a chat message, covering the presigned URL generation endpoint, direct S3 upload from the frontend, image S3 key persistence in chat_messages, and parallel upload coordination.

## Requirements

### Requirement: Upload image action returns presigned PUT URL
The `/api/chat` endpoint SHALL support `action: "upload_image"` requests. Given a `filename` and `content_type` (`image/png` or `image/jpeg`), the system SHALL generate a presigned S3 PUT URL for a key under `chat-images/{user_id}/{uuid}.{ext}` and return both the `upload_url` and the `s3_key`.

#### Scenario: Request upload URL for PNG
- **WHEN** an authenticated user POSTs `{ action: "upload_image", filename: "slide.png", content_type: "image/png" }`
- **THEN** the response is `200` with `{ upload_url: "<presigned S3 PUT>", s3_key: "chat-images/{user_id}/{uuid}.png" }`

#### Scenario: Unauthenticated upload request
- **WHEN** an unauthenticated request is made with `action: "upload_image"`
- **THEN** the response is `401`

#### Scenario: Invalid content_type
- **WHEN** `content_type` is not `image/png` or `image/jpeg`
- **THEN** the response is `400` with an error message

### Requirement: Frontend uploads image directly to S3
After receiving the presigned PUT URL, the frontend SHALL PUT the image file bytes directly to S3. The frontend SHALL include the `Content-Type` header matching the image type in the PUT request.

#### Scenario: Successful direct S3 upload
- **WHEN** the frontend PUTs the image bytes to the presigned URL with the correct `Content-Type`
- **THEN** S3 stores the image at the specified key and returns `200`

#### Scenario: Upload fails
- **WHEN** the S3 PUT request fails
- **THEN** the frontend SHALL surface an error and the message SHALL NOT be sent

### Requirement: S3 keys persisted in chat_messages
The `chat_messages` table SHALL have an `image_s3_keys TEXT[]` column (default `'{}'`). When a message with images is sent, the array of S3 keys SHALL be stored in this column for that message row.

#### Scenario: Message with images stores keys
- **WHEN** `stream_send` is called with `image_s3_keys: ["chat-images/42/abc.png"]`
- **THEN** the inserted `chat_messages` row has `image_s3_keys = ARRAY['chat-images/42/abc.png']`

#### Scenario: Message without images stores empty array
- **WHEN** `stream_send` is called without `image_s3_keys`
- **THEN** the inserted row has `image_s3_keys = '{}'`

### Requirement: Images uploaded in parallel before send
The frontend SHALL initiate S3 uploads for all staged images in parallel before calling `stream_send`. The `stream_send` call SHALL only be made after all uploads complete successfully.

#### Scenario: Parallel uploads
- **WHEN** 3 images are staged and the user clicks send
- **THEN** all 3 S3 PUT requests are initiated simultaneously; `stream_send` is called only after all 3 return `200`
