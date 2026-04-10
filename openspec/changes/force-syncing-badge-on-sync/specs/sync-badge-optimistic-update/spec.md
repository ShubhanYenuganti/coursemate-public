## ADDED Requirements

### Requirement: Material badges optimistically show syncing after sync confirmation
After the user confirms a sync in the sync modal, the system SHALL immediately force `embed_status` to `'syncing'` for all materials whose `external_id` and `source_type` match a row in the confirmed-sync set — before the first polling cycle returns.

#### Scenario: Badge shows syncing immediately after clicking Sync
- **WHEN** the user clicks the Sync button in the sync modal (confirming file selections)
- **THEN** material cards for all confirmed-sync files SHALL display the "Syncing" badge immediately, without waiting for a polling response

#### Scenario: Badge updates to real status after polling
- **WHEN** the polling cycle returns updated material data from the server
- **THEN** the badge SHALL transition from "Syncing" to the server-returned `embed_status` value (e.g. "Queued", "Ready", or an error state)

#### Scenario: Unmatched materials are unaffected
- **WHEN** the sync confirmation is processed
- **THEN** materials whose `external_id` + `source_type` do not match any confirmed-sync row SHALL retain their existing `embed_status` unchanged
