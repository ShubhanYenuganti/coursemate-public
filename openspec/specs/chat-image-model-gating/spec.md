# chat-image-model-gating Specification

## Purpose
Defines how the system prevents sending image-bearing messages with models that do not support vision inputs, including the gating logic, banner display, and the explicit non-switching policy.

## Requirements

### Requirement: Non-vision models are blocked when images are staged
The system SHALL define `NON_VISION_MODEL_IDS` as a Set of model IDs that do not support image inputs: `deep-research-pro-preview-12-2025`, `o3-deep-research`, `o4-mini-deep-research`. When the user attempts to send a message with staged images and the selected model is in this set, the send SHALL be aborted and a banner SHALL be displayed at the top of the screen.

#### Scenario: Send blocked with non-vision model and staged images
- **WHEN** the user has images staged and the selected model ID is in `NON_VISION_MODEL_IDS` and clicks send
- **THEN** the send is aborted, no API call is made, and a banner appears at the top of the screen

#### Scenario: Send proceeds with vision model and staged images
- **WHEN** the user has images staged and the selected model is NOT in `NON_VISION_MODEL_IDS` and clicks send
- **THEN** the message is sent normally with images

#### Scenario: Send proceeds normally with no images regardless of model
- **WHEN** no images are staged
- **THEN** model gating is not applied and the send proceeds normally for any model

### Requirement: Banner names the blocked model
The blocking banner SHALL display a message identifying the specific model that does not support images, e.g. `"<model label> does not support image inputs. Please select a different model."` The banner SHALL be dismissible.

#### Scenario: Banner content
- **WHEN** a send is blocked due to model gating
- **THEN** the banner text includes the human-readable label of the selected model

#### Scenario: Banner is dismissible
- **WHEN** the blocking banner is visible
- **THEN** the user can dismiss it manually; it does not auto-dismiss

### Requirement: No model auto-switching
The system SHALL NOT automatically change the selected model when images are staged. The user is responsible for selecting a vision-capable model.

#### Scenario: Model selector unchanged on image attach
- **WHEN** the user attaches images while a non-vision model is selected
- **THEN** the model selector still shows the non-vision model; no automatic switch occurs
