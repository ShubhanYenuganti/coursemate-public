# Sync Transparency + Freshness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a clear per-file sync status with a Retry button on failures (Phase 1), then add Drive push-based freshness (Phase 2).

**Architecture:** A pure `derive_sync_status` from existing material/job state, exposed through the materials list API and rendered as status pills + retry in `MaterialsPage`; Phase 2 adds Drive Changes watch channels feeding the existing poller.

**Tech Stack:** Python serverless, AWS Lambda poller, Neon Postgres, pytest, React.

**Spec:** `docs/superpowers/specs/2026-06-10-sync-transparency-design.md`

---

### Task 1: Pure `derive_sync_status`

**Files:**
- Modify: `api/material.py` (add helper) — or a small `api/services/sync_status.py`
- Test: `tests/test_sync_status.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync_status.py
from api.material import derive_sync_status

def test_unsupported():
    assert derive_sync_status({'unsupported': True, 'sync_error': 'pptx'}, None)['status'] == 'unsupported'

def test_syncing_when_job_running():
    assert derive_sync_status({}, {'status': 'running'})['status'] == 'syncing'

def test_failed_carries_error():
    s = derive_sync_status({}, {'status': 'failed', 'error': 'export 403'})
    assert s['status'] == 'failed' and s['error'] == 'export 403'

def test_synced_when_last_synced_present():
    assert derive_sync_status({'last_synced_at': '2026-06-10T00:00:00'}, None)['status'] == 'synced'

def test_pending_default():
    assert derive_sync_status({}, None)['status'] == 'pending'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sync_status.py -v` — FAIL.

- [ ] **Step 3: Implement**

Add to `api/material.py` (the function body from the spec). Verify the real column names
(`last_synced_at`, an unsupported flag, job `status`/`error`) by inspecting the materials/job queries
already in this file and the poller; adjust keys to match.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sync_status.py -v` — PASS.

- [ ] **Step 5: Commit**

```bash
git add api/material.py tests/test_sync_status.py
git commit -m "feat: derive per-file sync status from material/job state"
```

---

### Task 2: Include sync status in the materials list API

**Files:**
- Modify: `api/material.py` (the materials-list GET response builder)
- Test: extend `tests/test_sync_status.py` or add `tests/test_material_list_status.py`

- [ ] **Step 1: Identify the list endpoint + latest-job lookup**

Run: `rg -n "def do_GET|list|get_by_course|jobs" api/material.py | head`
Find where each material is serialized for the list. You will attach `derive_sync_status` output as a
`sync` field, joining the latest job row per material.

- [ ] **Step 2: Add the `sync` field**

In the serializer, for each material look up its latest sync/embed job (reuse the poller's job table
query already present) and set:

```python
material_out["sync"] = derive_sync_status(material, latest_job)
```

- [ ] **Step 3: Verify the field appears**

Run the existing material/poller tests: `pytest tests/test_integration_poller_deletions.py tests/test_material_cancel_sync_jobs.py -v` — PASS, and manually confirm `/api/material` list responses now carry `sync`.

- [ ] **Step 4: Commit**

```bash
git add api/material.py
git commit -m "feat: expose per-material sync status in materials list"
```

---

### Task 3: Status pills + Retry in MaterialsPage

**Files:**
- Modify: `src/MaterialsPage.jsx`

- [ ] **Step 1: Render a status pill per material**

Where each material row renders, add:

```jsx
{m.sync && (
  <span className={
    'text-[11px] px-2 py-0.5 rounded-full ' + {
      synced: 'bg-green-50 text-green-700',
      syncing: 'bg-blue-50 text-blue-700 animate-pulse',
      failed: 'bg-red-50 text-red-700',
      unsupported: 'bg-gray-100 text-gray-500',
      pending: 'bg-gray-50 text-gray-400',
    }[m.sync.status]
  } title={m.sync.error || ''}>
    {m.sync.status}
  </span>
)}
```

- [ ] **Step 2: Add a Retry button for failed materials**

```jsx
{m.sync?.status === 'failed' && (
  <button onClick={() => retrySync(m)} className="text-[11px] text-indigo-600 hover:underline">Retry</button>
)}
```

```jsx
async function retrySync(m) {
  await fetch('/api/material', {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
    body: JSON.stringify({ action: 'retry_sync', material_id: m.id, external_id: m.external_id }),
  });
  // refresh the materials list (reuse the existing fetch)
}
```

- [ ] **Step 3: Implement `action=retry_sync` in `api/material.py`**

Add a POST branch that validates ownership and re-invokes the poller for the single `external_id`,
reusing the invoked-sync route the "Sync Now" flow already uses (search for where `bulk_upsert_sync`
/ the poller invoke happens). Scope it to one file.

- [ ] **Step 4: Manually verify**

Run: `npm run dev`. Trigger a failed sync (unsupported file) → red `failed` pill with tooltip + Retry;
click Retry → pill goes `syncing` then `synced`.

- [ ] **Step 5: Commit**

```bash
git add src/MaterialsPage.jsx api/material.py
git commit -m "feat: per-file sync status pills and retry in MaterialsPage"
```

---

### Task 4 (Phase 2): Drive Changes watch channel

**Files:**
- Modify: `lambda/integration_poller/` (register/renew watch channels; handle change webhook) + a new API route to receive the webhook
- Create: migration for `drive_watch_channels` (channel_id, resource_id, folder, expiry, user)

- [ ] **Step 1: Register a watch channel when a Drive folder is connected**

Using the Drive `changes.watch` API, register a channel for the connected folder; persist
`channel_id`, `resource_id`, and `expiration`. Reuse the existing Drive client/auth in
`api/services/providers/gdrive.py`.

- [ ] **Step 2: Receive change notifications**

Add an endpoint (e.g. `api/drive_webhook.py`) that, on a Drive push, enqueues the poller for the
changed files (same path as Sync Now), validating the channel token.

- [ ] **Step 3: Renew before expiry**

In the existing EventBridge poller run, renew channels nearing `expiration`. Keep the 2-hour poll as
the backstop.

- [ ] **Step 4: Manually verify**

Edit a Drive doc → confirm a re-sync occurs within minutes (not 2h), and the materials list status
reflects it.

- [ ] **Step 5: Commit**

```bash
git add lambda/integration_poller api/drive_webhook.py migrations/0XX_drive_watch_channels.sql
git commit -m "feat: Drive Changes watch channels for near-real-time sync"
```

> Phase 2 is intentionally coarser-grained than Phase 1 — it depends on Google API specifics
> (channel TTLs, domain verification for push endpoints). Treat Task 4 as its own mini-project; ship
> Phase 1 (Tasks 1–3) independently.

---

## Self-Review

- **Spec coverage:** status derivation (T1), API exposure (T2), UI pills + retry (T3), Drive push
  (T4). ✓
- **Surgical/Phase split:** Phase 1 mostly exposes existing state; Phase 2 is isolated and gated so
  Phase 1 ships alone. ✓
- **Anchors:** plan repeatedly points to existing job queries, the Sync Now invoke path, and the
  Drive provider client rather than inventing them. ✓
