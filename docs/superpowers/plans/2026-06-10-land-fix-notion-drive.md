# Verify & Lock the `fix-notion-drive` Sync Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Confirm the merged `fix-notion-drive` sync-robustness work is intact on `main` and protected by regression tests, since the roadmap flagged this as "mid-fix."

**Architecture:** This is a verification/regression plan, not a feature build. `fix-notion-drive` was already merged (PR #15, commit `518014a`). The work here is to prove the five fixes hold and have test coverage, and to backfill any missing test.

**Tech Stack:** Python, pytest.

**Spec:** None — verification of already-merged work.

---

### Task 1: Confirm the merge is on main

**Files:** none (inspection)

- [ ] **Step 1: Verify the merge commit and its component fixes are present**

Run: `git log --oneline main | grep -iE "notion|drive|sync|poller|reingest|reconcile"`
Expected to include: `518014a Merge pull request #15 from ShubhanYenuganti/fix-notion-drive`,
`ad769b0 Reset poller embed jobs on reingest`, `ebea227 Allow cancelling stuck sync jobs`,
`6624229 Reconcile removed integration source files`, `2926e31 Filter unsupported Drive source files`.

- [ ] **Step 2: Record the result**

If all five are present, the branch is landed — proceed to coverage verification. If any is missing,
STOP: the merge is incomplete and must be re-landed before this plan continues.

---

### Task 2: Inventory existing coverage for each fix

**Files:** none (inspection)

- [ ] **Step 1: Map each fix to its test**

Run: `ls tests | grep -iE "poller|integration|material|sync|gdrive|notion"`
Expected existing tests:
- `tests/test_gdrive_poller_filtering.py` → "Filter unsupported Drive source files"
- `tests/test_integration_poller_deletions.py` → "Reconcile removed integration source files"
- `tests/test_integration_poller_enqueue_jobs.py` → poller enqueue (reingest embed jobs)
- `tests/test_material_cancel_sync_jobs.py` → "Allow cancelling stuck sync jobs"
- `tests/test_integration_source_point_access.py` → source-point access control

- [ ] **Step 2: Identify the gap**

The one fix without an obviously-named test is **"Reset poller embed jobs on reingest"** (`ad769b0`).
Verify whether `tests/test_integration_poller_enqueue_jobs.py` already covers the reset-on-reingest
behavior (search it for `reingest`/`reset`/`embed`). If covered, this plan ends at Task 3. If not,
Task 4 backfills it.

---

### Task 3: Run the full sync test suite green

**Files:** none

- [ ] **Step 1: Run all sync/poller tests**

Run: `pytest tests/test_gdrive_poller_filtering.py tests/test_integration_poller_deletions.py tests/test_integration_poller_enqueue_jobs.py tests/test_material_cancel_sync_jobs.py tests/test_integration_source_point_access.py -v`
Expected: all PASS.

- [ ] **Step 2: If any fail**, treat as a real regression: debug with the
  superpowers:systematic-debugging skill before claiming the branch is verified.

---

### Task 4 (conditional): Backfill the reingest-reset test

**Files:**
- Modify or create: `tests/test_integration_poller_enqueue_jobs.py` (add a reingest case) — only if Task 2 found no coverage.

- [ ] **Step 1: Write the failing test for reset-on-reingest**

Model it on the existing tests in the same file (reuse their fixtures/stubs). Assert that when a
material is re-ingested, its stale embed jobs are reset to a pending/queued state rather than left
in their prior terminal state. Use the exact function under test that `ad769b0` modified — locate it
with `git show ad769b0 --stat` and `git show ad769b0` to see which function changed.

```python
def test_reingest_resets_stale_embed_jobs(monkeypatch):
    # Arrange: a material with an embed job in a terminal/failed state.
    # Act: trigger the reingest path that ad769b0 introduced.
    # Assert: the embed job is reset to pending and re-enqueued exactly once.
    ...  # fill from the existing test patterns in this file + git show ad769b0
```

> This is the one place the plan cannot pre-write full code: the assertion shape depends on the
> internal job-state representation changed in `ad769b0`. Read that commit first, then mirror the
> sibling tests' structure.

- [ ] **Step 2: Run it**

Run: `pytest tests/test_integration_poller_enqueue_jobs.py -v`
Expected: the new test PASSES against the already-merged fix (it documents existing behavior).

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration_poller_enqueue_jobs.py
git commit -m "test: cover reset of stale embed jobs on reingest"
```

---

## Self-Review

- **Spec coverage:** verify merge (T1), inventory coverage (T2), green suite (T3), backfill the one
  likely gap (T4). ✓
- **Honesty:** the plan states up front the branch is already merged, so this is verification not a
  build — matching the actual repo state rather than the roadmap's "mid-fix" framing. ✓
- **No placeholders:** the single deferred code block (T4) explicitly explains why and how to derive
  it (`git show ad769b0` + sibling test patterns). ✓
