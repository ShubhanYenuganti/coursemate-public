## ADDED Requirements

### Requirement: User connects Notion workspace via OAuth
The system SHALL initiate a Notion OAuth 2.0 flow when the user clicks "Connect Notion" in ProfilePage. The `/api/notion?action=auth` endpoint SHALL redirect the browser to Notion's authorization URL with `client_id`, `redirect_uri`, `response_type=code`, and a random `state` value. The `state` SHALL be stored in a signed cookie (`notion_oauth_state`) to validate on callback.

#### Scenario: Successful OAuth initiation
- **WHEN** the user clicks "Connect Notion" on ProfilePage
- **THEN** the browser is redirected to Notion's OAuth authorization page
- **AND** a `notion_oauth_state` cookie is set on the response

#### Scenario: Unauthenticated initiation attempt
- **WHEN** an unauthenticated request reaches `GET /api/notion?action=auth`
- **THEN** the system returns 401 Unauthorized

### Requirement: OAuth callback stores connection
The `/api/notion?action=callback` endpoint SHALL exchange the authorization `code` for an access token by calling Notion's token endpoint. It SHALL validate the `state` parameter against the cookie value. On success it SHALL store the `encrypted_token` and `metadata` (workspace_id, workspace_name, workspace_icon, bot_id) in the `user_integrations` table using an upsert (UNIQUE on user_id + provider). It SHALL then redirect the browser to `/profile` with a `notion_connected=1` query param.

#### Scenario: Successful callback
- **WHEN** Notion redirects to `/api/notion?action=callback&code=abc&state=xyz`
- **AND** state matches the cookie
- **THEN** the system exchanges the code for a token
- **AND** inserts or updates the row in `user_integrations` for provider='notion'
- **AND** redirects to `/profile?notion_connected=1`

#### Scenario: State mismatch (CSRF attempt)
- **WHEN** the `state` param does not match the `notion_oauth_state` cookie
- **THEN** the system returns 400 Bad Request and does NOT store any token

#### Scenario: Notion returns an error code
- **WHEN** Notion redirects with `error=access_denied`
- **THEN** the system redirects to `/profile?notion_error=access_denied` without storing a token

### Requirement: User can revoke Notion connection
The `DELETE /api/notion?action=revoke` endpoint SHALL delete the row in `user_integrations` for the authenticated user and provider='notion'. After revocation, all sticky targets in `notion_course_targets` for this user SHALL also be deleted.

#### Scenario: Successful revocation
- **WHEN** the user clicks "Disconnect" on ProfilePage
- **AND** the system calls `DELETE /api/notion?action=revoke`
- **THEN** the `user_integrations` row is deleted
- **AND** all `notion_course_targets` rows for that user are deleted
- **AND** ProfilePage shows the "Connect Notion" button again

#### Scenario: Revoke when no connection exists
- **WHEN** `DELETE /api/notion?action=revoke` is called but no row exists
- **THEN** the system returns 404 Not Found

### Requirement: ProfilePage displays Notion connection status
ProfilePage SHALL display a "Connected Apps" section. When Notion is connected it SHALL show the workspace name and icon from `metadata`, plus a "Disconnect" button. When not connected it SHALL show a "Connect Notion" button.

#### Scenario: Connected state display
- **WHEN** the user has a row in `user_integrations` for provider='notion'
- **THEN** ProfilePage shows the workspace name and a "Disconnect" button
- **AND** does NOT show the "Connect Notion" button

#### Scenario: Disconnected state display
- **WHEN** no row exists for the user in `user_integrations` for provider='notion'
- **THEN** ProfilePage shows a "Connect Notion" button
- **AND** does NOT show a "Disconnect" button

### Requirement: Connection status API
`GET /api/notion?action=status` SHALL return whether the user has an active Notion connection and, if so, the workspace metadata (workspace_id, workspace_name, workspace_icon). It SHALL NOT return the token.

#### Scenario: Connected user queries status
- **WHEN** an authenticated user with a stored Notion token calls `GET /api/notion?action=status`
- **THEN** the response includes `{ "connected": true, "workspace_name": "...", "workspace_icon": "..." }`

#### Scenario: Disconnected user queries status
- **WHEN** an authenticated user without a stored token calls `GET /api/notion?action=status`
- **THEN** the response includes `{ "connected": false }`
