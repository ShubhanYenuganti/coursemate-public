# chat-image-message-display Specification

## Purpose
Defines how image attachments are rendered in chat message history: compact attachment bar on user messages, presigned download URL generation at message load time, and visual styling requirements for the bar.

## Requirements

### Requirement: User messages with images show a compact attachment bar
User message bubbles in chat history SHALL display a compact attachment bar above the message text when `image_s3_keys` is non-empty. The bar SHALL list each image as a clickable filename link. Clicking a link SHALL download the image via a presigned S3 URL.

#### Scenario: Message with images shows attachment bar
- **WHEN** a user message is rendered that has one or more image S3 keys
- **THEN** a compact bar appears above the message text showing each image filename as a download link

#### Scenario: Message without images shows no bar
- **WHEN** a user message is rendered with an empty `image_s3_keys`
- **THEN** no attachment bar is rendered

#### Scenario: Click attachment link downloads image
- **WHEN** the user clicks a filename link in the attachment bar
- **THEN** the browser downloads the image using a presigned S3 URL

### Requirement: Presigned download URLs generated at message load time
When loading message history, the system SHALL generate a fresh presigned S3 download URL for each key in `image_s3_keys`. URLs SHALL NOT be stored in the database.

#### Scenario: Presigned URL freshness
- **WHEN** a user loads a chat conversation with image-bearing messages
- **THEN** the API response includes freshly-generated presigned download URLs for each image key

### Requirement: Attachment bar style is compact and non-intrusive
The attachment bar SHALL use a subdued visual treatment (small font, muted color, paperclip icon prefix) that does not compete visually with the message text. It SHALL appear on a single line with filenames separated by spacing, wrapping if needed.

#### Scenario: Multiple attachments on one line
- **WHEN** a message has 3 image attachments
- **THEN** all three filenames appear in the attachment bar, wrapping to a second line if the container is narrow
