## MODIFIED Requirements

### Requirement: Presigned download URLs generated at message load time
When loading message history, the system SHALL generate a fresh presigned S3 download URL for each key in `image_s3_keys`. The API response SHALL include both `image_download_urls: [{filename, url}]` AND `image_s3_keys: [string]` for each message. The two arrays SHALL be in the same order — `image_s3_keys[i]` corresponds to `image_download_urls[i]`. URLs SHALL NOT be stored in the database.

#### Scenario: Presigned URL freshness
- **WHEN** a user loads a chat conversation with image-bearing messages
- **THEN** the API response includes freshly-generated presigned download URLs for each image key

#### Scenario: Response includes image_s3_keys alongside download URLs
- **WHEN** a user message with `image_s3_keys = ["chat-images/42/abc.png"]` is returned in the message list
- **THEN** the response includes both `image_download_urls: [{filename: "abc.png", url: "<presigned>"}]` and `image_s3_keys: ["chat-images/42/abc.png"]` in the same element, in matching order

#### Scenario: Message with no images returns empty arrays
- **WHEN** a message has `image_s3_keys = '{}'`
- **THEN** the response includes `image_download_urls: []` and `image_s3_keys: []`
