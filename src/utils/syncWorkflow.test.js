import { describe, expect, it } from "vitest";
import {
  buildBulkSyncDocTypes,
  buildBulkSyncToggles,
  buildCancelledEmbedStatusMap,
  removeSyncJob,
  buildSyncFilesPayload,
} from "./syncWorkflow";

describe("sync workflow helpers", () => {
  const rows = [
    { external_id: "a", name: "A", sync: false, doc_type: "reading" },
    { external_id: "b", name: "B", sync: true, doc_type: null },
  ];

  it("preserves per-row sync choices for normal sync", () => {
    expect(buildSyncFilesPayload(rows, { b: false }, { a: "exam" })).toEqual([
      { external_id: "a", name: "A", sync: false, doc_type: "exam" },
      { external_id: "b", name: "B", sync: false, doc_type: "general" },
    ]);
  });

  it("forces every visible row on for sync all", () => {
    expect(
      buildSyncFilesPayload(rows, { a: false, b: false }, {}, { forceAll: true }),
    ).toEqual([
      { external_id: "a", name: "A", sync: true, doc_type: "reading" },
      { external_id: "b", name: "B", sync: true, doc_type: "general" },
    ]);
  });

  it("builds bulk row updates for visible sync rows", () => {
    expect(buildBulkSyncToggles(rows, true)).toEqual({ a: true, b: true });
    expect(buildBulkSyncDocTypes(rows, "lecture_note")).toEqual({
      a: "lecture_note",
      b: "lecture_note",
    });
  });

  it("removes cancelled sync jobs and marks their items skipped locally", () => {
    const jobs = [
      { jobId: "keep", items: [{ external_id: "a" }] },
      { jobId: "cancel", items: [{ external_id: "b" }, { external_id: "c" }] },
    ];

    expect(removeSyncJob(jobs, "cancel")).toEqual([jobs[0]]);
    expect(buildCancelledEmbedStatusMap({ a: "processing" }, jobs[1])).toEqual({
      a: "processing",
      b: "skipped",
      c: "skipped",
    });
  });
});
