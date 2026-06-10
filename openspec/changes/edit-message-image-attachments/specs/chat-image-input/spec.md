## ADDED Requirements

### Requirement: Edit mode pre-populates staging strip from existing message images
When the user enters edit mode on a message that has `image_s3_keys`, the staging strip SHALL be pre-populated with one entry per existing image using the message's `image_download_urls` for thumbnail display and `image_s3_keys` for the send payload. These entries are of kind `existing` — they have no `File` object and require no upload before send.

#### Scenario: Edit mode shows existing image thumbnails
- **WHEN** the user clicks the edit button on a message that has two image attachments
- **THEN** the staging strip appears pre-populated with two thumbnails (using the presigned download URLs) and filenames from `image_download_urls`

#### Scenario: Edit mode on message with no images
- **WHEN** the user clicks the edit button on a message with no image attachments
- **THEN** the staging strip is not shown and the edit textarea is empty as today

### Requirement: Staging strip is fully mutable during edit
While in edit mode, the user SHALL be able to dismiss any staged image (existing or new) using the × button, and SHALL be able to add new images via the file picker or paste, subject to the same 5-image cap and 10MB-per-file limits as new sends.

#### Scenario: Dismiss existing image during edit
- **WHEN** the user clicks × on a pre-populated existing image thumbnail in edit mode
- **THEN** that image is removed from the staging strip and will not be included in the edited send payload

#### Scenario: Add new image during edit
- **WHEN** the user is in edit mode and uses the file picker or paste to add a new image
- **THEN** the new image is appended to the staging strip alongside any retained existing images, subject to the 5-image cap

#### Scenario: Cap enforced across existing and new during edit
- **WHEN** the user is in edit mode with 4 existing images staged and attempts to add 2 new images
- **THEN** only 1 new image is added (reaching the cap of 5); the second is ignored

### Requirement: Edit send clears staging strip on success
After a successful edited send, the staging strip in edit mode SHALL be cleared, matching the behavior of new send.

#### Scenario: Strip clears after successful edit send
- **WHEN** the user submits an edited message with staged images and the send succeeds
- **THEN** the staging strip disappears and the edit-mode image state resets to empty

## MODIFIED Requirements

### Requirement: Send button active with images and no text
The send button SHALL be enabled when at least one image is staged, even if the textarea is empty. This applies to both new sends and edits.

#### Scenario: Send enabled with only images (new send)
- **WHEN** the textarea is empty and at least one image is staged during a new send
- **THEN** the send button is enabled

#### Scenario: Send (edit) enabled with only images and no text
- **WHEN** the user is in edit mode, has cleared the text field, but has at least one image staged
- **THEN** the edit send button is enabled

#### Scenario: Send disabled with no text and no images
- **WHEN** the textarea is empty and no images are staged
- **THEN** the send button is disabled
