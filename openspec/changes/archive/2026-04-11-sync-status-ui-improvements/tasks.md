## 1. EmbedStatusBadge — up_to_date state

- [x] 1.1 In `src/MaterialsPage.jsx`, locate `EmbedStatusBadge` and add a branch for `status === 'up_to_date'` that renders a gray "No changes detected" badge (match the visual style of the existing `'skipped'` gray badge)

## 2. Session-scoped badge — page-load mapping

- [x] 2.1 In `src/MaterialsPage.jsx`, find where the materials API response is stored into React state; add a mapping step that replaces `embed_status === 'up_to_date'` with `'done'` for each row before storing — ensuring the badge only appears in the session that triggered the sync, not on subsequent page loads

## 3. MaterialCard — Last Edited At timestamp

- [x] 3.1 In `src/MaterialsPage.jsx`, locate `MaterialCard` and add a "Last Edited At: {timestamp}" line below the badge row; render it only when `material.source_type === 'gdrive' || material.source_type === 'notion'` AND `material.external_last_edited` is non-null
- [x] 3.2 Format `external_last_edited` using `new Date(material.external_last_edited).toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })` to produce locale-aware output including hours and minutes (e.g., "Apr 9, 2026, 10:30 AM")

## 4. Verification

- [ ] 4.1 Trigger "Sync Now" on a GDrive file that has not changed — confirm "No changes detected" badge appears on the card in the same session
- [ ] 4.2 Reload the page after step 4.1 — confirm the badge is gone (replaced by nothing / normal done state)
- [ ] 4.3 Trigger "Sync Now" on a GDrive file that has changed — confirm the badge shows syncing/processing then disappears (no "No changes detected")
- [x] 4.4 On a material with a non-null `external_last_edited` and `source_type = 'gdrive'`, confirm "Last Edited At: {date + time}" line is visible with correct formatting including hours and minutes
- [x] 4.5 Confirm "Last Edited At" line is absent for manually uploaded materials (no `source_type` of gdrive/notion)
- [x] 4.6 Confirm "Last Edited At" line is absent for integration materials where `external_last_edited` is null (e.g., never successfully ingested)
