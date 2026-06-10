export function buildSyncFilesPayload(rows, toggles = {}, docTypes = {}, options = {}) {
  const forceAll = options.forceAll === true;
  return (Array.isArray(rows) ? rows : []).map((row) => ({
    external_id: row.external_id,
    name: row.name,
    sync: forceAll ? true : (toggles[row.external_id] ?? row.sync !== false),
    doc_type: docTypes[row.external_id] ?? row.doc_type ?? "general",
  }));
}

export function buildBulkSyncToggles(rows, next) {
  return Object.fromEntries(
    (Array.isArray(rows) ? rows : [])
      .filter((row) => row?.external_id)
      .map((row) => [row.external_id, next]),
  );
}

export function buildBulkSyncDocTypes(rows, docType) {
  return Object.fromEntries(
    (Array.isArray(rows) ? rows : [])
      .filter((row) => row?.external_id)
      .map((row) => [row.external_id, docType]),
  );
}

export function removeSyncJob(jobs, jobId) {
  return (Array.isArray(jobs) ? jobs : []).filter((job) => job?.jobId !== jobId);
}

export function buildCancelledEmbedStatusMap(currentMap = {}, job) {
  const next = { ...currentMap };
  for (const item of job?.items || []) {
    if (item?.external_id) next[item.external_id] = "skipped";
  }
  return next;
}
