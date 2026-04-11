# material-card-last-edited-at Specification

## Purpose
TBD - created by archiving change sync-status-ui-improvements. Update Purpose after archive.
## Requirements
### Requirement: Integration material cards display a persistent Last Edited At timestamp
`MaterialCard` SHALL display a "Last Edited At: {timestamp}" line for materials where `source_type` is `'gdrive'` or `'notion'` AND `external_last_edited` is non-null. The line SHALL appear persistently (not session-scoped), below the source type and embed status badges.

#### Scenario: Last Edited At shown for gdrive material with timestamp
- **WHEN** a material has `source_type = 'gdrive'` and a non-null `external_last_edited`
- **THEN** the card SHALL display "Last Edited At: {formatted timestamp}" using the locale-aware format including month, day, year, hour, and minutes (e.g., "Apr 9, 2026, 10:30 AM")

#### Scenario: Last Edited At shown for notion material with timestamp
- **WHEN** a material has `source_type = 'notion'` and a non-null `external_last_edited`
- **THEN** the card SHALL display "Last Edited At: {formatted timestamp}" in the same format

#### Scenario: Last Edited At hidden for materials with null external_last_edited
- **WHEN** `external_last_edited` is null (e.g., material failed mid-upload and was never successfully ingested)
- **THEN** the "Last Edited At" line SHALL NOT appear

#### Scenario: Last Edited At hidden for non-integration materials
- **WHEN** `source_type` is not `'gdrive'` or `'notion'` (e.g., manually uploaded files)
- **THEN** the "Last Edited At" line SHALL NOT appear regardless of `external_last_edited`

### Requirement: Last Edited At timestamp includes hours and minutes
The formatted timestamp SHALL include hour and minute components in addition to date components, using the browser's locale for formatting.

#### Scenario: Timestamp format includes time of day
- **WHEN** `external_last_edited` is `"2026-04-09T10:30:00Z"`
- **THEN** the displayed string SHALL include both the date (e.g., "Apr 9, 2026") and the time (e.g., "10:30 AM") in the user's local timezone

