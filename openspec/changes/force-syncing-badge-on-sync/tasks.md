## 1. Optimistic Badge Update in handleSyncConfirm

- [x] 1.1 In `handleSyncConfirm` (MaterialsPage.jsx ~line 1074), after the `bulk_upsert_sync` POST succeeds and before `setSyncModalMode('progress')`, build a lookup Set of confirmed-sync `external_id|source_type` pairs from `syncRows` filtered by the active toggle state
- [x] 1.2 Call `setMaterials(prev => prev.map(m => confirmedSet.has(key(m)) ? { ...m, embed_status: 'syncing' } : m))` to optimistically patch the badge for all matching materials
- [ ] 1.3 Verify in the browser that clicking Sync immediately shows the "Syncing" badge on matched cards with no empty-badge frame visible

## 2. Verification

- [ ] 2.1 Confirm unmatched material cards (manual uploads, different source type) are unaffected by the optimistic update
- [ ] 2.2 Confirm the badge transitions correctly from "Syncing" to the real server status once the polling cycle returns (e.g. "Queued" or "Ready")
