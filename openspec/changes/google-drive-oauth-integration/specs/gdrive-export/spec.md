## ADDED Requirements

### Requirement: User can export generated content to Google Drive
The system SHALL allow users to export flashcards, quizzes, and reports as Google Docs to a selected Google Drive folder. Each export SHALL create a new Google Doc using the Google Docs API.

#### Scenario: Successful flashcard export
- **WHEN** user exports a flashcard set to a selected Drive folder
- **THEN** the system creates a new Google Doc in that folder with each flashcard formatted as a question/answer pair and returns the Doc URL

#### Scenario: Successful quiz export
- **WHEN** user exports a quiz to a selected Drive folder
- **THEN** the system creates a new Google Doc with each question formatted as a numbered item with answer options and returns the Doc URL

#### Scenario: Successful report export
- **WHEN** user exports a report to a selected Drive folder
- **THEN** the system creates a new Google Doc with report sections as headings and body text and returns the Doc URL

#### Scenario: Export with no Drive connection
- **WHEN** user attempts to export to Drive but has no connected Google Drive integration
- **THEN** the system SHALL return a 401 response prompting the user to connect Google Drive

### Requirement: User can select a sticky Drive export target
The system SHALL allow users to select a Google Drive folder as a persistent export destination per course and generation type. The selection SHALL be stored in `course_export_targets` with `provider = "gdrive"`.

#### Scenario: Saving an export target
- **WHEN** user selects a Drive folder and confirms export
- **THEN** the system stores the folder ID and name in `course_export_targets` and uses it for subsequent exports of the same type

#### Scenario: Loading a saved export target
- **WHEN** user opens the export UI for a course and generation type that has a saved target
- **THEN** the system pre-selects the saved Drive folder without requiring the user to search again

#### Scenario: Changing an export target
- **WHEN** user selects a different Drive folder for a course/generation type that already has a saved target
- **THEN** the system updates the `course_export_targets` record with the new folder

### Requirement: User can search and browse Drive folders for export target selection
The system SHALL provide a Drive folder picker that allows users to search their Drive for folders to use as export targets.

#### Scenario: Searching Drive folders
- **WHEN** user types in the Drive target picker search box
- **THEN** the system queries the Drive API for folders matching the search term and displays results with folder names

#### Scenario: Empty search shows recent folders
- **WHEN** user opens the Drive target picker with no search term
- **THEN** the system displays a list of the user's recently modified Drive folders
