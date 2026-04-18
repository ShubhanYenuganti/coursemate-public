## ADDED Requirements

### Requirement: User can attach images via file picker
The chat input bar SHALL include an attachment icon button that opens a file picker accepting `image/png` and `image/jpeg` files. The user MAY select multiple files in a single pick operation. The system SHALL reject files that are not PNG or JPEG and SHALL reject files exceeding 10MB. The system SHALL enforce a maximum of 5 images per message across all attachment methods combined.

#### Scenario: Attach valid images via file picker
- **WHEN** the user clicks the attachment icon and selects 1–5 PNG or JPEG files each ≤10MB
- **THEN** a preview strip appears above the textarea showing a thumbnail and filename for each image

#### Scenario: Picker rejects non-image files
- **WHEN** the user attempts to select a file that is not PNG or JPEG
- **THEN** the file picker input's `accept` attribute prevents the file from being selectable

#### Scenario: File exceeds 10MB limit
- **WHEN** the user selects a file exceeding 10MB
- **THEN** the file is silently ignored and does not appear in the preview strip

#### Scenario: Exceed 5-image cap via file picker
- **WHEN** the user already has images staged and attempts to add more that would exceed 5 total
- **THEN** only images up to the 5-image cap are added; the rest are ignored

---

### Requirement: User can paste images from clipboard
The system SHALL intercept `paste` events on the chat textarea when the textarea is focused. If the clipboard contains one or more `image/png` or `image/jpeg` items, those images SHALL be added to the staged image list subject to the same 10MB-per-image and 5-image-total limits. Text content in the clipboard SHALL be pasted normally into the textarea.

#### Scenario: Paste image while textarea is focused
- **WHEN** the textarea is focused and the user pastes an image from the clipboard (e.g., via Cmd+V after copying a screenshot)
- **THEN** the image is added to the preview strip above the textarea

#### Scenario: Paste text while images are staged
- **WHEN** the textarea is focused and the user pastes text
- **THEN** the text is inserted into the textarea normally; staged images are unaffected

#### Scenario: Paste image while textarea is not focused
- **WHEN** the textarea is not focused and the user pastes an image
- **THEN** the image is NOT added to the preview strip

---

### Requirement: Preview strip shows staged images
While images are staged (before send), the chat input bar SHALL display a preview strip above the textarea showing a thumbnail and filename for each staged image. Each thumbnail SHALL have a dismiss button (×) to remove that image from the staged list.

#### Scenario: Preview strip visible with staged images
- **WHEN** one or more images are staged
- **THEN** the preview strip is visible above the textarea with a thumbnail and filename for each image

#### Scenario: Preview strip hidden when no images staged
- **WHEN** no images are staged
- **THEN** the preview strip is not rendered

#### Scenario: Dismiss a staged image
- **WHEN** the user clicks the × on a staged image thumbnail
- **THEN** that image is removed from the staged list and its thumbnail disappears from the preview strip

---

### Requirement: Send button active with images and no text
The send button SHALL be enabled when at least one image is staged, even if the textarea is empty.

#### Scenario: Send enabled with only images
- **WHEN** the textarea is empty and at least one image is staged
- **THEN** the send button is enabled

#### Scenario: Send disabled with no text and no images
- **WHEN** the textarea is empty and no images are staged
- **THEN** the send button is disabled

---

### Requirement: Staged images cleared after send
After a successful send, the staged image list SHALL be cleared and the preview strip SHALL disappear.

#### Scenario: Preview strip clears on send
- **WHEN** the user sends a message with staged images
- **THEN** the preview strip disappears and `images` state resets to empty
