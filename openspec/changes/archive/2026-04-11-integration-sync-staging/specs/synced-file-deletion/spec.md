## ADDED Requirements

### Requirement: Deleting a synced material tombstones the row instead of removing it
When a user deletes a material that has an `integration_source_point_id` foreign key (i.e., was ingested from a third-party integration), the system SHALL remove the S3 object and set `sync = false` on the materials row, but SHALL NOT delete the row. This prevents the integration poller from re-discovering and re-ingesting the file on subsequent poll cycles.

#### Scenario: Deleting a synced material retains the row
- **WHEN** the user deletes a material that has a non-null `integration_source_point_id`
- **THEN** the system deletes the S3 object, sets `sync = false` on the materials row, and the row remains in the database

#### Scenario: Deleting a normal material removes the row
- **WHEN** the user deletes a material that has a null `integration_source_point_id`
- **THEN** the system deletes the S3 object and removes the materials row entirely (existing behavior)

#### Scenario: Poller skips tombstoned file after user deletes it
- **WHEN** the integration poller polls a source point and encounters a file whose materials row has `sync = false`
- **THEN** the poller skips that file and does not enqueue an embed job

#### Scenario: Tombstoned file can be re-enabled via Sync Now
- **WHEN** a user opens Sync Now on a source point and flips a previously deleted (sync = false) file's toggle to ON and clicks Upload
- **THEN** the system updates the materials row to `sync = true` and the file is eligible for ingestion on the next poll cycle
