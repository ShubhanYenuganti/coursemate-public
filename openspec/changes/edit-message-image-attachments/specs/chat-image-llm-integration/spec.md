## ADDED Requirements

### Requirement: _edit_message passes final image_s3_keys to synthesize()
The `_edit_message` handler SHALL pass the final `image_s3_keys` list to `synthesize()` using the same `image_s3_keys` parameter as `stream_send`. The final list is derived from `image_attachments` in the request (if provided) or from the original message row's `image_s3_keys` (if not). This ensures the LLM receives the correct image set for the edited message.

#### Scenario: Edit with images delivers images to LLM
- **WHEN** `stream_edit` is called with `image_attachments: [{s3_key: "chat-images/42/a.png", filename: "a.png"}]`
- **THEN** `synthesize()` is called with `image_s3_keys=["chat-images/42/a.png"]` and the LLM request includes that image as a base64 block

#### Scenario: Edit retaining original images delivers them to LLM
- **WHEN** `stream_edit` is called without `image_attachments` on a message that had `image_s3_keys = ["chat-images/42/a.png"]`
- **THEN** `synthesize()` is called with `image_s3_keys=["chat-images/42/a.png"]`

#### Scenario: Edit removing all images calls synthesize without images
- **WHEN** `stream_edit` is called with `image_attachments: []`
- **THEN** `synthesize()` is called with `image_s3_keys=[]` and the LLM request is text-only

#### Scenario: Edit on message with no original images and no new images
- **WHEN** `stream_edit` is called on a message with `image_s3_keys = '{}'` and no `image_attachments` field
- **THEN** `synthesize()` is called with `image_s3_keys=[]`; behavior is identical to today's edit path
