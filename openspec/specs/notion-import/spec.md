# notion-import Specification

## Purpose
TBD - created by archiving change integration-sync-staging. Update Purpose after archive.
## Requirements
### Requirement: Lambda poller ingests Notion database pages as course materials with sync gate
The system SHALL poll active Notion database source points, query each database for recently edited pages, and for each page consult the `sync` field in the materials table before any PDF conversion work begins. Pages with `sync = false` SHALL be skipped. Pages with `sync = true` or no existing row SHALL proceed through the existing ingestion pipeline (blocks → ReportLab PDF → S3 upload → embed). The sync check SHALL occur before block fetching and PDF generation.

#### Scenario: New Notion database ingested for the first time
- **WHEN** the integration Lambda polls an active Notion source point for the first time
- **THEN** the system queries the database for all pages, checks each page's sync state, and for pages with no existing materials row proceeds to fetch blocks, generate PDF via ReportLab, upload to S3, create a materials record with `sync = true`, and enqueue an embed job

#### Scenario: Previously excluded page is skipped by poller
- **WHEN** the integration Lambda polls a Notion source point and a page's corresponding materials row has `sync = false`
- **THEN** the poller SHALL skip that page before fetching its blocks or generating a PDF, and SHALL NOT enqueue an embed job

#### Scenario: Sync check precedes block fetching and PDF generation
- **WHEN** the poller processes a batch of pages from a Notion source point
- **THEN** the system SHALL batch-query `sync` values (by `external_id` = page ID) before initiating any Notion block fetch or ReportLab PDF generation call

#### Scenario: New page added to Notion database
- **WHEN** the integration Lambda polls a Notion database and finds a page with no corresponding materials row
- **THEN** the system ingests it as a new material and inserts the row with `sync = true`

#### Scenario: Unchanged page skipped
- **WHEN** the integration Lambda polls a Notion database and a page's `last_edited_time` matches its material's `external_last_edited`
- **THEN** the system SHALL skip re-ingestion for that page (existing behavior, unaffected by sync gate)

#### Scenario: Changed page re-ingested
- **WHEN** the integration Lambda polls a Notion database and a page's `last_edited_time` is newer than its material's `external_last_edited`, and `sync = true`
- **THEN** the system re-fetches blocks, regenerates PDF, replaces the S3 object, updates the materials record, deletes old embedding chunks, and enqueues a fresh embed job

#### Scenario: Stuck placeholder row not confused with sync = false
- **WHEN** a materials row exists with a placeholder `file_url` (pattern `notion/<page_id>.pdf`) and `sync = true`
- **THEN** the poller SHALL treat it as an incomplete ingest (retry upload) and SHALL NOT skip it as if sync were false

