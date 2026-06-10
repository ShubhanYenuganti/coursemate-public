import { describe, expect, it } from "vitest";
import {
  buildBulkSyncDocTypes,
  buildBulkSyncToggles,
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
});
