## Purpose

Define Google Drive OAuth connection behavior for CourseMate, including connect, callback/finalize handling, token refresh, connection status, and disconnect.

## Requirements

### Requirement: User can connect Google Drive account
The system SHALL provide a Google OAuth 2.0 authorization flow that grants CourseMate read and write access to the user's Google Drive. The connection SHALL be initiated from the user's Profile page and SHALL store an encrypted access token and refresh token in `user_integrations` with `provider = "gdrive"`.

#### Scenario: User initiates connection
- **WHEN** user clicks "Connect Google Drive" on the Profile page
- **THEN** the system redirects the user to the Google OAuth consent screen requesting `drive.readonly` and `drive.file` scopes

#### Scenario: Successful OAuth callback
- **WHEN** Google redirects back with a valid authorization code and matching state token
- **THEN** the system exchanges the code for access and refresh tokens, encrypts them as JSON, stores them in `user_integrations`, and redirects to `/profile`

#### Scenario: SameSite cookie finalize
- **WHEN** the OAuth callback cannot access the session cookie due to cross-site redirect restrictions
- **THEN** the system stores an encrypted `gdrive_pending_token` cookie and redirects to `/profile?gdrive_pending=1`, where the frontend calls the `finalize_connection` endpoint to complete storage

#### Scenario: State token mismatch
- **WHEN** the OAuth callback receives a `state` parameter that does not match the stored session state
- **THEN** the system SHALL reject the callback and return an error page

### Requirement: System auto-refreshes expired access tokens
The system SHALL automatically refresh Google access tokens before making Drive API calls if the token is within 5 minutes of its expiry time. The refreshed token SHALL be re-encrypted and stored, replacing the previous value.

#### Scenario: Token near expiry
- **WHEN** a Drive API call is about to be made and the stored access token expires within 5 minutes
- **THEN** the system calls the Google token refresh endpoint, stores the new access token, and proceeds with the original API call

#### Scenario: Refresh token revoked
- **WHEN** the Google token refresh endpoint returns an error indicating the refresh token is invalid
- **THEN** the system SHALL return a 401 response to the frontend, which SHALL prompt the user to reconnect Google Drive

### Requirement: User can view Google Drive connection status
The system SHALL display the current Google Drive connection status on the Profile page, including the connected Google account email when connected.

#### Scenario: Drive connected
- **WHEN** user visits the Profile page and has a valid Google Drive integration
- **THEN** the system displays "Connected" with the Google account email and a "Disconnect" button

#### Scenario: Drive not connected
- **WHEN** user visits the Profile page and has no Google Drive integration
- **THEN** the system displays a "Connect Google Drive" button

### Requirement: User can disconnect Google Drive
The system SHALL allow users to revoke CourseMate's Google Drive access. Upon disconnection, the stored tokens SHALL be deleted from `user_integrations`.

#### Scenario: Successful disconnection
- **WHEN** user clicks "Disconnect" on the Profile page for Google Drive
- **THEN** the system deletes the `user_integrations` row for that user and provider, and the Profile page shows the "Connect Google Drive" button
