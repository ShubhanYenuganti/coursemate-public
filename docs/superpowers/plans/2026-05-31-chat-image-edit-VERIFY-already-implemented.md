# Chat Image Edit — Verification Plan (Feature Already Implemented)

> **Status: NOT a build plan.** Code inspection on 2026-05-31 shows this P0 item is **already fully implemented** in both backend and frontend. The roadmap and session handoff incorrectly listed it as unbuilt. This document is a verification + archive checklist, not an implementation plan.

**Spec/source:** `openspec/changes/edit-message-image-attachments/` (proposal, design, 5 spec deltas, tasks.md — all tasks `[x]`).

## Evidence it is implemented

Backend — `api/chat.py`:
- Message serialization returns `image_s3_keys` alongside `image_download_urls` (lines ~251–282, SELECTs at 644/659).
- `_edit_message` accepts `image_attachments` (line 1311), reads `original_keys` (1402), computes `final_keys` (1404), `added_keys`/`removed_keys` (1410–1411).
- Deletes `chat_image_embeddings` for removed keys (1413–1420).
- Embeds added keys via `embed_and_store_chat_images` (1422–1428).
- Passes `image_s3_keys=list(final_keys)` to `synthesize()` (1462).

Frontend — `src/ChatTab.jsx`:
- Edit staging supports `{ kind: 'existing', s3_key, filename, url }` (comment line 1329).
- `onEditStart` pre-populates existing entries from `msg.image_s3_keys` (lines 2834–2840).
- Edit send includes `image_attachments` in the `stream_edit` payload (line 2148).
- New images staged as `{ kind: 'new', file }` (line 1879).

This covers openspec tasks 1.1–5.5.

## Verification checklist (do this instead of building)

- [ ] **Backend test exists?** Run `cd /Users/shubhan/OneShotCourseMate && rg -n "image_attachments|added_keys|removed_keys" tests/`. If no test covers the edit diff logic, add one: send an edit with one removed + one added key and assert the embedding rows and `image_s3_keys` column update correctly.
- [ ] **Manual flow:** Send a chat message with 2 images → edit it → remove one image, add one new image, change the text → send. Confirm: (a) the assistant reply reflects the final image set, (b) the message now shows the new image set, (c) `chat_image_embeddings` has rows for the kept + added keys and none for the removed key.
- [ ] **Non-vision model gating:** With a non-vision model selected, editing a message that has images shows the gating banner (task 5.1).
- [ ] **Archive the openspec change** once verified:
  - Use the openspec workflow: `Skill openspec-verify-change` then `openspec-archive-change` for `edit-message-image-attachments`.

## Recommendation

Reprioritize: this P0 is effectively done. Spend the effort on the genuinely-unbuilt items (flashcard Play/rating, PageIndex Claude/Gemini, etc.). If verification surfaces a real gap, convert the failing case into a TDD task at that point.
```
