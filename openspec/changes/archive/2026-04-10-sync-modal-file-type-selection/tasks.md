## 1. Backend — list_source_point_files returns doc_type

- [x] 1.1 In `api/gdrive.py` `_handle_list_source_point_files`: extend the cross-reference SQL query from `SELECT external_id, sync` to `SELECT external_id, sync, doc_type`; update the `sync_rows` dict to `{r["external_id"]: {"sync": r["sync"], "doc_type": r["doc_type"]} for r in ...}`; add `"doc_type": sync_rows.get(f["id"], {}).get("doc_type")` to each entry in `files_out`
- [x] 1.2 In `api/notion.py` find the equivalent `list_source_point_files` handler and apply the identical SQL and response change so Notion source points return `doc_type` as well

## 2. Backend — bulk_upsert_sync persists doc_type

- [x] 2.1 In `api/material.py` `_bulk_upsert_sync`: inside the per-file loop, read `doc_type = f.get('doc_type', DEFAULT_DOC_TYPE)` and validate it against `VALID_DOC_TYPES` (default to `DEFAULT_DOC_TYPE` if invalid)
- [x] 2.2 Add `doc_type` to the `INSERT` column list and `VALUES` tuple in the `bulk_upsert_sync` SQL; add `doc_type = EXCLUDED.doc_type` to the `ON CONFLICT DO UPDATE SET` clause

## 3. Frontend — normalizeSyncRows includes doc_type

- [x] 3.1 In `normalizeSyncRows` add `doc_type: row.doc_type ?? null` to the mapped object so the field is available on each row

## 4. Frontend — syncDocTypes state

- [x] 4.1 Add `const [syncDocTypes, setSyncDocTypes] = useState({})` alongside `syncToggles` in `MaterialsPage`
- [x] 4.2 In `openSyncModalForId`: after loading rows, initialise `syncDocTypes` from rows that have a non-null `doc_type` (mirrors how `syncToggles` is initialised from `row.sync`)
- [x] 4.3 In `closeSyncModal` and the polling-completion `useEffect` that closes the modal: reset `syncDocTypes` to `{}` alongside `syncToggles`
- [x] 4.4 Add handler `handleSyncDocTypeChange = (externalId, docType) => setSyncDocTypes(prev => ({...prev, [externalId]: docType}))` and wire it to `SyncModal` as an `onDocTypeChange` prop

## 5. Frontend — SyncModal renders doc_type dropdown

- [x] 5.1 Add `onDocTypeChange` and `docTypes` props to `SyncModal`
- [x] 5.2 In the staging rows `map`, resolve effective doc type: `const docType = docTypes[row.external_id] ?? row.doc_type ?? 'general'`
- [x] 5.3 Render a `<select>` with `DOCUMENT_TYPES` options after the file name, identical in style to `StagingItemRow`'s dropdown (`text-xs rounded border border-gray-200 bg-white px-2 py-1 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 shrink-0`)
- [x] 5.4 Pass `docTypes={syncDocTypes}` and `onDocTypeChange={handleSyncDocTypeChange}` from the `SyncModal` usage site in `MaterialsPage`

## 6. Frontend — handleSyncConfirm includes doc_type

- [x] 6.1 In `handleSyncConfirm`, add `doc_type: syncDocTypes[row.external_id] ?? row.doc_type ?? 'general'` to each entry in `filesPayload`
- [x] 6.2 Add `syncDocTypes` to the `useCallback` dependency array of `handleSyncConfirm`
