import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { formatDateTime } from "./utils/dateUtils";

// ─── constants ───────────────────────────────────────────────────────────────

const DOCUMENT_TYPES = [
  { value: "general", label: "General / other" },
  { value: "lecture_slide", label: "Lecture slides" },
  { value: "lecture_note", label: "Lecture notes" },
  { value: "discussion_note", label: "Discussion notes" },
  { value: "reading", label: "Reading" },
  { value: "hw_instruction", label: "Homework instructions" },
  { value: "hw_solution", label: "Homework solutions" },
  { value: "quiz", label: "Quiz" },
  { value: "exam", label: "Exam" },
  { value: "coding_spec", label: "Coding project spec" },
  { value: "code_file", label: "Code file" },
];

const ACCEPTED_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/svg+xml",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/csv",
]);

const TYPE_META = {
  "application/pdf": {
    label: "PDF",
    color: "text-red-600",
    bg: "bg-red-50",
    border: "border-red-200",
    accent: "bg-red-500",
  },
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
    label: "DOCX",
    color: "text-blue-600",
    bg: "bg-blue-50",
    border: "border-blue-200",
    accent: "bg-blue-500",
  },
  "text/plain": {
    label: "TXT",
    color: "text-gray-600",
    bg: "bg-gray-50",
    border: "border-gray-200",
    accent: "bg-gray-400",
  },
  "image/jpeg": {
    label: "JPG",
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    accent: "bg-emerald-500",
  },
  "image/png": {
    label: "PNG",
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    accent: "bg-emerald-500",
  },
  "image/gif": {
    label: "GIF",
    color: "text-purple-600",
    bg: "bg-purple-50",
    border: "border-purple-200",
    accent: "bg-purple-500",
  },
  "image/svg+xml": {
    label: "SVG",
    color: "text-orange-600",
    bg: "bg-orange-50",
    border: "border-orange-200",
    accent: "bg-orange-500",
  },
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
    label: "XLSX",
    color: "text-teal-600",
    bg: "bg-teal-50",
    border: "border-teal-200",
    accent: "bg-teal-500",
  },
  "text/csv": {
    label: "CSV",
    color: "text-teal-600",
    bg: "bg-teal-50",
    border: "border-teal-200",
    accent: "bg-teal-500",
  },
};

function getMeta(type) {
  return (
    TYPE_META[type] ?? {
      label: "FILE",
      color: "text-gray-500",
      bg: "bg-gray-50",
      border: "border-gray-200",
      accent: "bg-gray-400",
    }
  );
}

function fmtSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

let _seq = 0;
function uid() {
  return ++_seq;
}

// ─── small shared pieces ─────────────────────────────────────────────────────

function FileTypeIcon({ type, large = false }) {
  const { label, color, bg, border } = getMeta(type);
  const w = large ? 52 : 40;
  const h = large ? 62 : 48;
  return (
    <div
      className={`flex flex-col items-center justify-between rounded border ${bg} ${border} shrink-0`}
      style={{ width: w, height: h, padding: "4px 3px 3px" }}
    >
      <svg
        width={large ? 22 : 18}
        height={large ? 26 : 21}
        viewBox="0 0 20 24"
        fill="none"
        className={color}
      >
        <path
          d="M2 0C.9 0 0 .9 0 2v20c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V7L13 0H2Z"
          fill="currentColor"
          opacity=".12"
        />
        <path d="M13 0v7h7L13 0Z" fill="currentColor" opacity=".35" />
        <rect
          x="3"
          y="11"
          width="14"
          height="1.5"
          rx=".75"
          fill="currentColor"
          opacity=".45"
        />
        <rect
          x="3"
          y="14"
          width="9"
          height="1.5"
          rx=".75"
          fill="currentColor"
          opacity=".45"
        />
        <rect
          x="3"
          y="17"
          width="11"
          height="1.5"
          rx=".75"
          fill="currentColor"
          opacity=".45"
        />
      </svg>
      <span
        className={`font-bold leading-none ${color}`}
        style={{ fontSize: large ? 10 : 8 }}
      >
        {label}
      </span>
    </div>
  );
}

function Spinner({ size = 16, className = "text-indigo-500" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={`animate-spin ${className}`}
      style={{ animationDuration: "0.75s" }}
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray="42 14"
      />
    </svg>
  );
}

function VisibilityToggle({
  isPublic,
  onChange,
  disabled = false,
  size = "md",
}) {
  const track = size === "sm" ? "h-4 w-7" : "h-5 w-9";
  const knob =
    size === "sm"
      ? `h-3 w-3 ${isPublic ? "translate-x-[14px]" : "translate-x-0.5"}`
      : `h-3.5 w-3.5 ${isPublic ? "translate-x-[18px]" : "translate-x-0.5"}`;

  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!isPublic)}
      disabled={disabled}
      title={
        isPublic
          ? "Public — click to make private"
          : "Private — click to make public"
      }
      className={`relative inline-flex shrink-0 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-1 ${track} ${
        isPublic ? "bg-indigo-500" : "bg-gray-300"
      } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span
        className={`inline-block rounded-full bg-white shadow-sm transform transition-transform duration-200 ${knob}`}
      />
    </button>
  );
}

function TrashIcon({ size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4h6v2" />
    </svg>
  );
}

// ─── upload drop zone ────────────────────────────────────────────────────────

function UploadZone({ onFiles, disabled }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const files = [...e.dataTransfer.files].filter((f) =>
        ACCEPTED_TYPES.has(f.type),
      );
      if (files.length) onFiles(files);
    },
    [onFiles, disabled],
  );

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!disabled) setDragging(true);
  };
  const handleDragLeave = () => setDragging(false);

  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold text-gray-800">Upload Files</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          PDF, DOCX, TXT, JPEG, PNG, GIF, SVG, XLSX, CSV
        </p>
      </div>

      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed py-10 transition-all cursor-pointer select-none
          ${
            dragging
              ? "border-indigo-400 bg-indigo-50"
              : "border-gray-200 bg-gray-50/60 hover:border-indigo-300 hover:bg-indigo-50/30"
          }
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <div
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
            dragging ? "bg-indigo-200" : "bg-gray-200/80"
          }`}
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={dragging ? "text-indigo-600" : "text-gray-500"}
          >
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </div>
        <p className="text-sm text-gray-500">
          <span className="text-indigo-600 font-medium">Browse</span> or drag
          files here
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={[...ACCEPTED_TYPES].join(",")}
          className="sr-only"
          onChange={(e) => {
            const files = [...e.target.files].filter((f) =>
              ACCEPTED_TYPES.has(f.type),
            );
            if (files.length) onFiles(files);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}

// ─── upload item row ──────────────────────────────────────────────────────────

function UploadItemRow({ item, onVisibilityChange, onDismiss }) {
  const isLoading = item.status === "uploading";
  const isDone = item.status === "done";
  const isError = item.status === "error";

  return (
    <div
      className={`rounded-lg border bg-white transition-all ${
        isError ? "border-red-200 bg-red-50/40" : "border-gray-200"
      }`}
    >
      {/* Main row */}
      <div className="flex items-center gap-3 px-3 py-2.5">
        <FileTypeIcon type={item.file.type} />

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate">
            {item.file.name}
          </p>
          <p className="text-xs text-gray-400">{fmtSize(item.file.size)}</p>
        </div>

        {/* State indicator */}
        <div className="flex items-center gap-2 shrink-0">
          {isLoading && (
            <span className="flex items-center gap-1.5 text-xs text-indigo-500 font-medium">
              <Spinner size={13} />
              Uploading…
            </span>
          )}
          {isDone && (
            <span className="text-xs text-emerald-600 font-medium">✓ Done</span>
          )}
          {isError && (
            <span
              className="text-xs text-red-500 font-medium"
              title={item.error}
            >
              Failed
            </span>
          )}

          <button
            type="button"
            onClick={() => onDismiss(item.id)}
            className="p-1 rounded text-gray-300 hover:text-gray-500 transition-colors"
            title="Dismiss"
          >
            <TrashIcon size={14} />
          </button>
        </div>
      </div>

      {/* Loading progress banner — shown while uploading */}
      {isLoading && (
        <div className="mx-3 mb-2.5 h-1 rounded-full bg-gray-100 overflow-hidden">
          <div
            className="h-full bg-indigo-400 rounded-full animate-[loading-bar_1.6s_ease-in-out_infinite]"
            style={{ width: "60%" }}
          />
        </div>
      )}

      {/* Visibility toggle row — shown only after confirmed done */}
      {isDone && (
        <div className="flex items-center justify-between px-3 pb-2.5">
          <span className="text-xs text-gray-400">
            {item.visibilityUpdating
              ? "Saving…"
              : item.isPublic
                ? "Public"
                : "Private"}
          </span>
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-gray-400">Private</span>
            <VisibilityToggle
              isPublic={item.isPublic}
              onChange={(val) => onVisibilityChange(item.id, val)}
              disabled={item.visibilityUpdating}
              size="sm"
            />
            <span className="text-[11px] text-gray-400">Public</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── staging item row (pre-upload, doc type selection) ───────────────────────

function StagingItemRow({ item, onDocTypeChange, onUpload, onRemove }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-indigo-100 bg-indigo-50/30 px-3 py-2.5">
      <FileTypeIcon type={item.file.type} />

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">
          {item.file.name}
        </p>
        <p className="text-xs text-gray-400">{fmtSize(item.file.size)}</p>
      </div>

      <select
        value={item.docType}
        onChange={(e) => onDocTypeChange(item.id, e.target.value)}
        className="text-xs rounded border border-gray-200 bg-white px-2 py-1 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 shrink-0"
      >
        {DOCUMENT_TYPES.map((dt) => (
          <option key={dt.value} value={dt.value}>
            {dt.label}
          </option>
        ))}
      </select>

      <button
        type="button"
        onClick={() => onUpload(item)}
        disabled={!item.docType}
        className="shrink-0 px-3 py-1 rounded text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Upload
      </button>

      <button
        type="button"
        onClick={() => onRemove(item.id)}
        className="p-1 rounded text-gray-300 hover:text-gray-500 transition-colors shrink-0"
        title="Remove"
      >
        <TrashIcon size={14} />
      </button>
    </div>
  );
}

function normalizeSyncRows(provider, rawFiles) {
  const sourceType = provider === "notion" ? "notion" : "gdrive";
  return (Array.isArray(rawFiles) ? rawFiles : [])
    .filter((row) => row?.external_id)
    .map((row) => ({
      external_id: row.external_id,
      name: row.name || row.external_id,
      mime_type: row.mime_type || "application/pdf",
      sync: row.sync ?? null,
      doc_type: row.doc_type ?? null,
      source_type: sourceType,
    }));
}

function SyncModal({
  provider,
  sourcePointTitle,
  rows,
  page,
  hasMore,
  loading,
  toggles,
  docTypes = {},
  error,
  onToggle,
  onDocTypeChange,
  onPrevPage,
  onNextPage,
  onSync,
  onClose,
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Sync Modal</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {provider === "notion" ? "Notion" : "Google Drive"} ·{" "}
            {sourcePointTitle || "Source point"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Close
        </button>
      </div>

      {error && <p className="text-xs text-red-500">{error}</p>}

      {loading ? (
        <div className="py-8 flex items-center justify-center">
          <Spinner size={22} className="text-indigo-400" />
        </div>
      ) : rows.length === 0 ? (
        <p className="text-sm text-gray-500 py-6">
          No files found for this source point.
        </p>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => {
            const enabled = toggles[row.external_id] ?? row.sync !== false;
            return (
              <div
                key={row.external_id}
                className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-3 py-2.5"
              >
                <FileTypeIcon type={row.mime_type} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-800 truncate">
                    {row.name}
                  </p>
                  <p className="text-xs text-gray-400 truncate">
                    {row.external_id}
                  </p>
                </div>
                <select
                  value={
                    docTypes[row.external_id] ?? row.doc_type ?? "general"
                  }
                  onChange={(e) =>
                    onDocTypeChange(row.external_id, e.target.value)
                  }
                  className="text-xs rounded border border-gray-200 bg-white px-2 py-1 text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-400 shrink-0"
                >
                  {DOCUMENT_TYPES.map((dt) => (
                    <option key={dt.value} value={dt.value}>
                      {dt.label}
                    </option>
                  ))}
                </select>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-medium ${enabled ? "text-emerald-600" : "text-gray-400"}`}
                  >
                    {enabled ? "Sync ON" : "Sync OFF"}
                  </span>
                  <VisibilityToggle
                    isPublic={enabled}
                    onChange={(next) => onToggle(row.external_id, next)}
                    size="sm"
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="flex items-center justify-between pt-1">
        <div className="text-xs text-gray-400">Page {page}</div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onPrevPage}
            disabled={page <= 1 || loading}
            className="px-2.5 py-1 rounded border border-gray-200 text-xs text-gray-600 disabled:opacity-40 hover:bg-gray-50"
          >
            Prev
          </button>
          <button
            type="button"
            onClick={onNextPage}
            disabled={!hasMore || loading}
            className="px-2.5 py-1 rounded border border-gray-200 text-xs text-gray-600 disabled:opacity-40 hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      </div>

      <div className="pt-1">
        <button
          type="button"
          onClick={onSync}
          disabled={loading || rows.length === 0}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          Sync
        </button>
      </div>
    </div>
  );
}

// ─── source type badge ───────────────────────────────────────────────────────

const SOURCE_TYPE_META = {
  notion: {
    label: "Notion",
    className: "text-purple-600 bg-purple-50 border-purple-200",
  },
  gdrive: {
    label: "Drive",
    className: "text-green-600 bg-green-50 border-green-200",
  },
  upload: {
    label: "Upload",
    className: "text-blue-500 bg-blue-50 border-blue-200",
  },
  generated: {
    label: "Generated",
    className: "text-indigo-600 bg-indigo-50 border-indigo-200",
  },
};

function SourceTypeBadge({ sourceType }) {
  const meta = SOURCE_TYPE_META[sourceType];
  if (!meta) return null;
  return (
    <span
      className={`inline-flex items-center text-[10px] font-medium border rounded-full px-1.5 py-0.5 leading-none ${meta.className}`}
    >
      {meta.label}
    </span>
  );
}

// ─── embed status badge ───────────────────────────────────────────────────────

function EmbedStatusBadge({ status, sourceType }) {
  // Integration-sourced material with no embed job yet: the poller is still
  // generating + uploading before it can enqueue the embed step.
  if (!status && sourceType === "notion") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-purple-600 bg-purple-50 border border-purple-200 rounded-full px-1.5 py-0.5 leading-none">
        <Spinner size={9} className="text-purple-500" />
        Syncing…
      </span>
    );
  }

  if (!status || status === "done") return null;

  if (status === "pending" || status === "processing") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-600 bg-amber-50 border border-amber-200 rounded-full px-1.5 py-0.5 leading-none">
        <Spinner size={9} className="text-amber-500" />
        {status === "processing" ? "Indexing…" : "Queued"}
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-red-500 bg-red-50 border border-red-200 rounded-full px-1.5 py-0.5 leading-none">
        ✕ Index failed
      </span>
    );
  }
  if (status === "skipped") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-gray-400 bg-gray-50 border border-gray-200 rounded-full px-1.5 py-0.5 leading-none">
        — Not indexed
      </span>
    );
  }
  return null;
}

// ─── progress panel ───────────────────────────────────────────────────────────

function ProgressPanel({ syncJobs, uploadItems, embedStatusMap, onClearDone }) {
  function deriveSyncStatus(item) {
    const status = embedStatusMap[item.external_id];
    if (!status) return { label: "Syncing…", spinner: true, color: "indigo" };
    switch (status) {
      case "pending":
        return { label: "Queued", spinner: true, color: "amber" };
      case "processing":
        return { label: "Indexing…", spinner: true, color: "amber" };
      case "done":
        return { label: "Done", spinner: false, color: "emerald" };
      case "failed":
        return { label: "Failed", spinner: false, color: "red" };
      case "skipped":
        return { label: "Skipped", spinner: false, color: "gray" };
      default:
        return { label: "Syncing…", spinner: true, color: "indigo" };
    }
  }

  const colorClasses = {
    indigo: "text-indigo-600 bg-indigo-50 border-indigo-200",
    amber: "text-amber-600 bg-amber-50 border-amber-200",
    emerald: "text-emerald-600 bg-emerald-50 border-emerald-200",
    red: "text-red-500 bg-red-50 border-red-200",
    gray: "text-gray-400 bg-gray-50 border-gray-200",
  };

  const uploadStatusLabel = (status) => {
    switch (status) {
      case "uploading":
      case "confirming":
        return { label: status === "uploading" ? "Uploading…" : "Confirming…", spinner: true, color: "indigo" };
      case "done":
        return { label: "Done", spinner: false, color: "emerald" };
      case "error":
        return { label: "Failed", spinner: false, color: "red" };
      default:
        return { label: status, spinner: false, color: "gray" };
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">Processing</h3>
        <button
          type="button"
          onClick={onClearDone}
          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
        >
          Clear done
        </button>
      </div>

      {syncJobs.map((job) => (
        <div key={job.jobId} className="space-y-1.5">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide truncate">
            {job.provider === "notion" ? "Notion" : "Google Drive"} · {job.label}
          </p>
          {job.items.map((item) => {
            const st = deriveSyncStatus(item);
            return (
              <div
                key={item.external_id}
                className="flex items-center gap-2.5 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-gray-700 truncate">{item.name}</p>
                </div>
                <span
                  className={`inline-flex items-center gap-1 text-[10px] font-medium border rounded-full px-1.5 py-0.5 leading-none shrink-0 ${colorClasses[st.color]}`}
                >
                  {st.spinner && <Spinner size={9} className="opacity-80" />}
                  {st.label}
                </span>
              </div>
            );
          })}
        </div>
      ))}

      {uploadItems.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Uploads
          </p>
          {uploadItems.map((item) => {
            const st =
              item.status === "indexing"
                ? deriveSyncStatus({ external_id: String(item.materialId) })
                : uploadStatusLabel(item.status);
            return (
              <div
                key={item.id}
                className="flex items-center gap-2.5 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-gray-700 truncate">
                    {item.file?.name || item.id}
                  </p>
                </div>
                <span
                  className={`inline-flex items-center gap-1 text-[10px] font-medium border rounded-full px-1.5 py-0.5 leading-none shrink-0 ${colorClasses[st.color]}`}
                >
                  {st.spinner && <Spinner size={9} className="opacity-80" />}
                  {st.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── material grid card (existing materials) ──────────────────────────────────

function MaterialCard({
  material,
  courseId,
  onVisibilityChange,
  onDelete,
  isOwner,
}) {
  const [deleting, setDeleting] = useState(false);
  const navigate = useNavigate();

  const quizGenMatch = material?.file_url?.match(
    /^quiz:\/\/generation\/(\d+)$/,
  );
  const quizGenerationId = quizGenMatch ? quizGenMatch[1] : null;
  const flashcardsGenMatch = material?.file_url?.match(
    /^flashcards:\/\/generation\/(\d+)$/,
  );
  const flashcardsGenerationId = flashcardsGenMatch
    ? flashcardsGenMatch[1]
    : null;
  const reportGenMatch = material?.file_url?.match(
    /^report:\/\/generation\/(\d+)$/,
  );
  const reportGenerationId = reportGenMatch ? reportGenMatch[1] : null;
  const driveFallbackUrl = material?.external_id
    ? `https://drive.google.com/file/d/${material.external_id}/view`
    : null;
  const materialOpenUrl =
    material?.source_type === "gdrive"
      ? material?.outsourced_url || driveFallbackUrl || material?.download_url
      : material?.source_type !== "upload" && material?.outsourced_url
        ? material.outsourced_url
        : material?.download_url;
  const isIntegrationMaterial =
    material?.source_type === "gdrive" || material?.source_type === "notion";
  const lastEditedAt = isIntegrationMaterial
    ? formatDateTime(material?.external_last_edited)
    : "";
  const lastUpdatedAt = isIntegrationMaterial
    ? formatDateTime(material?.updated_at)
    : "";

  return (
    <div className="flex rounded-lg border border-gray-200 bg-white overflow-hidden hover:shadow-md transition-shadow group">
      {/* Blue left accent matching PDF_modal_ex.png */}
      <div className={`w-1 shrink-0 ${getMeta(material.file_type).accent}`} />

      {/* Icon area */}
      <div className="flex items-center justify-center px-4 py-4 bg-gray-50/70 border-r border-gray-100">
        <FileTypeIcon type={material.file_type} large />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 px-4 py-3 flex flex-col justify-center gap-0.5">
        {quizGenerationId ? (
          <button
            type="button"
            onClick={() =>
              navigate(`/course/${courseId}/quiz/${quizGenerationId}`)
            }
            className="text-sm font-bold text-gray-900 hover:text-indigo-700 hover:underline underline-offset-2 line-clamp-2 leading-snug text-left"
          >
            {material.name}
          </button>
        ) : flashcardsGenerationId ? (
          <button
            type="button"
            onClick={() =>
              navigate(
                `/course/${courseId}/flashcards/${flashcardsGenerationId}`,
              )
            }
            className="text-sm font-bold text-gray-900 hover:text-indigo-700 hover:underline underline-offset-2 line-clamp-2 leading-snug text-left"
          >
            {material.name}
          </button>
        ) : reportGenerationId ? (
          <button
            type="button"
            onClick={() =>
              navigate(`/course/${courseId}/reports/${reportGenerationId}`)
            }
            className="text-sm font-bold text-gray-900 hover:text-indigo-700 hover:underline underline-offset-2 line-clamp-2 leading-snug text-left"
          >
            {material.name}
          </button>
        ) : (
          <a
            href={materialOpenUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-bold text-gray-900 hover:text-indigo-700 hover:underline underline-offset-2 line-clamp-2 leading-snug"
          >
            {material.name}
          </a>
        )}
        <div className="flex items-center gap-1.5 flex-wrap">
          <p className="text-xs text-gray-400">
            {getMeta(material.file_type).label}
            {material.visibility === "public" ? " · Public" : " · Private"}
          </p>
          <SourceTypeBadge sourceType={material.source_type} />
        </div>
        {lastEditedAt && (
          <p className="text-xs text-gray-400">
            Last Edited At: {lastEditedAt}
          </p>
        )}
        {lastUpdatedAt && (
          <p className="text-xs text-gray-400">
            Last Updated At: {lastUpdatedAt}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col items-end justify-between px-3 py-3 shrink-0">
        {isOwner && (
          <button
            type="button"
            onClick={async () => {
              setDeleting(true);
              await onDelete(material);
            }}
            disabled={deleting}
            className="p-1 rounded text-gray-300 hover:text-red-500 transition-colors"
            title="Delete material"
          >
            {deleting ? (
              <Spinner size={14} className="text-gray-400" />
            ) : (
              <TrashIcon size={14} />
            )}
          </button>
        )}

        {isOwner && (
          <div className="flex items-center gap-1 mt-auto">
            <VisibilityToggle
              isPublic={material.visibility === "public"}
              onChange={(val) => onVisibilityChange(material.id, val)}
              disabled={material.updating}
              size="sm"
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

// ─── filter pill bar ──────────────────────────────────────────────────────────

function FilterBar({ ownerFilter, setOwnerFilter, typeFilter, setTypeFilter }) {
  const ownerPills = [
    { id: "all", label: "All materials" },
    { id: "mine", label: "My materials" },
  ];
  const typePills = [
    { id: "all", label: "All types", prefix: null },
    { id: "uploaded", label: "Uploaded", prefix: "↑" },
    { id: "generated", label: "Generated", prefix: "✦" },
  ];

  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-full bg-white border border-gray-200 shadow-sm w-fit flex-wrap">
      {/* Owner group */}
      <div className="flex items-center gap-0.5">
        {ownerPills.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setOwnerFilter(p.id)}
            className={`px-3.5 py-1 rounded-full text-sm font-medium transition-colors duration-150 focus:outline-none ${
              ownerFilter === p.id
                ? "bg-indigo-600 text-white"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-gray-200" />

      {/* Type group label */}
      <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest select-none pl-1">
        Show
      </span>

      {/* Type group */}
      <div className="flex items-center gap-0.5">
        {typePills.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setTypeFilter(p.id)}
            className={`flex items-center gap-1 px-3.5 py-1 rounded-full text-sm font-medium transition-colors duration-150 focus:outline-none ${
              typeFilter === p.id
                ? "bg-indigo-600 text-white"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {p.prefix && <span className="text-xs">{p.prefix}</span>}
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function MaterialsPage({ courseId, userId }) {
  const [materials, setMaterials] = useState([]);
  const [loadingMats, setLoadingMats] = useState(true);
  const [stagingItems, setStagingItems] = useState([]);
  const [uploadItems, setUploadItems] = useState([]);
  const [ownerFilter, setOwnerFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [syncJobs, setSyncJobs] = useState([]);
  const [embedStatusMap, setEmbedStatusMap] = useState({});
  const [panelDismissed, setPanelDismissed] = useState(
    () => localStorage.getItem("coursemate_progress_dismissed") === "true",
  );

  const [sourcePoints, setSourcePoints] = useState({ gdrive: [], notion: [] });
  const [sourcePointsLoading, setSourcePointsLoading] = useState(false);
  const [syncProvider, setSyncProvider] = useState("gdrive");
  const [selectedSourcePointId, setSelectedSourcePointId] = useState("");

  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [syncRows, setSyncRows] = useState([]);
  const [syncRowsLoading, setSyncRowsLoading] = useState(false);
  const [syncRowsError, setSyncRowsError] = useState("");
  const [syncPage, setSyncPage] = useState(1);
  const [syncHasMore, setSyncHasMore] = useState(false);
  const [syncToggles, setSyncToggles] = useState({});
  const [syncDocTypes, setSyncDocTypes] = useState({});
  const [sourceSearch, setSourceSearch] = useState("");
  const [sourceSearchResults, setSourceSearchResults] = useState([]);
  const [sourceSearching, setSourceSearching] = useState(false);
  const [confirmRemoveId, setConfirmRemoveId] = useState(null);
  const [addError, setAddError] = useState("");

  const selectedSourcePoint = useMemo(
    () =>
      sourcePoints[syncProvider]?.find(
        (sp) => String(sp.id) === String(selectedSourcePointId),
      ) || null,
    [sourcePoints, syncProvider, selectedSourcePointId],
  );

  const fetchSourcePoints = useCallback(async () => {
    if (!courseId) return;
    setSourcePointsLoading(true);
    try {
      const [gdriveRes, notionRes] = await Promise.all([
        fetch(`/api/gdrive?action=list_source_points&course_id=${courseId}`, {
          credentials: "include",
        }),
        fetch(`/api/notion?action=list_source_points&course_id=${courseId}`, {
          credentials: "include",
        }),
      ]);
      const [gdriveData, notionData] = await Promise.all([
        gdriveRes.json(),
        notionRes.json(),
      ]);
      const next = {
        gdrive: Array.isArray(gdriveData?.source_points)
          ? gdriveData.source_points
          : [],
        notion: Array.isArray(notionData?.source_points)
          ? notionData.source_points
          : [],
      };
      setSourcePoints(next);
      const currentList = next[syncProvider] || [];
      if (
        !currentList.some(
          (sp) => String(sp.id) === String(selectedSourcePointId),
        )
      ) {
        setSelectedSourcePointId(
          currentList[0]?.id ? String(currentList[0].id) : "",
        );
      }
    } catch {
      setSourcePoints({ gdrive: [], notion: [] });
      setSelectedSourcePointId("");
    } finally {
      setSourcePointsLoading(false);
    }
  }, [courseId, syncProvider, selectedSourcePointId]);

  const fetchSyncRowsPage = useCallback(
    async (page) => {
      if (!selectedSourcePointId) return;
      const endpoint =
        syncProvider === "notion" ? "/api/notion" : "/api/gdrive";
      setSyncRowsLoading(true);
      setSyncRowsError("");
      try {
        const res = await fetch(
          `${endpoint}?action=list_source_point_files&id=${selectedSourcePointId}&page=${page}`,
          { credentials: "include" },
        );
        const data = await res.json();
        if (!res.ok)
          throw new Error(data?.error || "Failed to load source point files");
        const rows = normalizeSyncRows(syncProvider, data.files);
        const nextToggles = {};
        const nextDocTypes = {};
        rows.forEach((row) => {
          nextToggles[row.external_id] = row.sync !== false;
          if (row.doc_type != null)
            nextDocTypes[row.external_id] = row.doc_type;
        });
        setSyncRows(rows);
        setSyncToggles(nextToggles);
        setSyncDocTypes(nextDocTypes);
        setSyncPage(page);
        setSyncHasMore(Boolean(data.has_more));
      } catch (err) {
        setSyncRows([]);
        setSyncHasMore(false);
        setSyncRowsError(err?.message || "Failed to load source point files");
      } finally {
        setSyncRowsLoading(false);
      }
    },
    [selectedSourcePointId, syncProvider],
  );

  // ── fetch existing materials ──────────────────────────────────────────────
  const fetchMaterials = useCallback(async () => {
    setLoadingMats(true);
    try {
      const res = await fetch(`/api/material?course_id=${courseId}`, {
        credentials: "include",
      });
      const data = await res.json();
      const mappedMaterials = (data.materials || []).map((material) =>
        material?.embed_status === "up_to_date"
          ? { ...material, embed_status: "done" }
          : material,
      );
      setMaterials(mappedMaterials);
    } catch {
      // silently fail — UI will show empty state
    } finally {
      setLoadingMats(false);
    }
  }, [courseId]);

  // Lightweight poll — updates only embedStatusMap, not the full materials grid
  const pollEmbedStatuses = useCallback(async () => {
    try {
      const res = await fetch(`/api/material?course_id=${courseId}`, {
        credentials: "include",
      });
      const data = await res.json();
      const map = {};
      for (const m of data.materials || []) {
        const status = m.embed_status === "up_to_date" ? "done" : m.embed_status;
        if (m.external_id) map[m.external_id] = status;
        map[String(m.id)] = status;
      }
      setEmbedStatusMap(map);
    } catch {
      // silently fail
    }
  }, [courseId]);

  useEffect(() => {
    fetchMaterials();
  }, [fetchMaterials]);
  useEffect(() => {
    fetchSourcePoints();
  }, [fetchSourcePoints]);

  useEffect(() => {
    const list = sourcePoints[syncProvider] || [];
    if (!list.some((sp) => String(sp.id) === String(selectedSourcePointId))) {
      setSelectedSourcePointId(list[0]?.id ? String(list[0].id) : "");
    }
  }, [sourcePoints, syncProvider, selectedSourcePointId]);

  // ── poll at 2 s while any job is active ──────────────────────────────────
  const hasActiveJobs =
    syncJobs.some((job) =>
      job.items.some(
        (item) => embedStatusMap[item.external_id] !== "done" && embedStatusMap[item.external_id] !== "failed" && embedStatusMap[item.external_id] !== "skipped",
      ),
    ) ||
    uploadItems.some(
      (i) =>
        i.status === "uploading" ||
        i.status === "confirming" ||
        (i.status === "indexing" &&
          embedStatusMap[String(i.materialId)] !== "done" &&
          embedStatusMap[String(i.materialId)] !== "failed" &&
          embedStatusMap[String(i.materialId)] !== "skipped"),
    );

  // Poll embed statuses every 2 s (lightweight — does not touch the materials grid)
  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = setTimeout(pollEmbedStatuses, 2000);
    return () => clearTimeout(timer);
  }, [embedStatusMap, hasActiveJobs, pollEmbedStatuses]);

  // When all jobs finish, do one final materials refresh so the grid reflects latest state
  const prevHadActiveJobs = useRef(false);
  useEffect(() => {
    if (prevHadActiveJobs.current && !hasActiveJobs && (syncJobs.length > 0 || uploadItems.length > 0)) {
      fetchMaterials();
    }
    prevHadActiveJobs.current = hasActiveJobs;
  }, [hasActiveJobs, syncJobs.length, uploadItems.length, fetchMaterials]);

  // ── search for source points to add ──────────────────────────────────────
  useEffect(() => {
    const q = sourceSearch.trim();
    if (!q) {
      setSourceSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSourceSearching(true);
      try {
        const url =
          syncProvider === "notion"
            ? `/api/notion?action=search&q=${encodeURIComponent(q)}&filter_type=database`
            : `/api/gdrive?action=search&q=${encodeURIComponent(q)}`;
        const res = await fetch(url, { credentials: "include" });
        const data = await res.json();
        setSourceSearchResults(Array.isArray(data.results) ? data.results : []);
      } catch {
        setSourceSearchResults([]);
      } finally {
        setSourceSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [sourceSearch, syncProvider]);

  // ── upload one file ──────────────────────────────────────────────────────
  const uploadOne = useCallback(
    async (item) => {
      const update = (patch) =>
        setUploadItems((prev) =>
          prev.map((i) => (i.id === item.id ? { ...i, ...patch } : i)),
        );

      update({ status: "uploading" });

      try {
        // 1. Request presigned URL(s)
        const r1 = await fetch("/api/material", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            action: "request_upload",
            course_id: courseId,
            filename: item.file.name,
            file_type: item.file.type,
            visibility: "private",
            file_size: item.file.size,
          }),
        });
        if (!r1.ok) throw new Error("Failed to get upload URL");
        const uploadMeta = await r1.json();
        const { s3_key } = uploadMeta;

        // 2. Upload to S3
        let confirmExtra = {};
        if (uploadMeta.multipart) {
          // Large file: PUT each part, collect ETags
          const { upload_id, parts, part_size } = uploadMeta;
          const etags = await Promise.all(
            parts.map(async ({ part_number, upload_url }) => {
              const start = (part_number - 1) * part_size;
              const chunk = item.file.slice(start, start + part_size);
              const resp = await fetch(upload_url, {
                method: "PUT",
                body: chunk,
              });
              if (!resp.ok)
                throw new Error(`Part ${part_number} upload failed`);
              return { part_number, etag: resp.headers.get("ETag") };
            }),
          );
          confirmExtra = { upload_id, parts: etags };
        } else {
          // Small file: single presigned POST
          const form = new FormData();
          Object.entries(uploadMeta.fields).forEach(([k, v]) =>
            form.append(k, v),
          );
          form.append("file", item.file); // must be last
          const r2 = await fetch(uploadMeta.upload_url, {
            method: "POST",
            body: form,
          });
          if (!r2.ok && r2.status !== 204) throw new Error("S3 upload failed");
        }

        // 3. Confirm upload — creates DB record
        const r3 = await fetch("/api/material", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            action: "confirm_upload",
            s3_key,
            course_id: courseId,
            filename: item.file.name,
            file_type: item.file.type,
            visibility: "private",
            source_type: item.docType || "general",
            ...confirmExtra,
          }),
        });
        if (!r3.ok) throw new Error("Upload confirmation failed");
        const { material } = await r3.json();

        update({
          status: "indexing",
          materialId: material.id,
          isPublic: false,
          visibilityUpdating: false,
        });
      } catch (e) {
        update({ status: "error", error: e.message });
      }
    },
    [courseId],
  );

  // ── stage files (no upload yet) ──────────────────────────────────────────
  const handleFiles = useCallback((files) => {
    const items = files.map((f) => ({
      id: uid(),
      file: f,
      docType: "general",
    }));
    setStagingItems((prev) => [...prev, ...items]);
  }, []);

  // ── update doc type for a staging item ───────────────────────────────────
  const handleStagingDocType = useCallback((id, docType) => {
    setStagingItems((prev) =>
      prev.map((i) => (i.id === id ? { ...i, docType } : i)),
    );
  }, []);

  // ── upload a single staged item ───────────────────────────────────────────
  const handleStagingUpload = useCallback(
    async (stagingItem) => {
      // Move from staging to upload queue
      setStagingItems((prev) => prev.filter((i) => i.id !== stagingItem.id));
      const uploadItem = {
        id: stagingItem.id,
        file: stagingItem.file,
        docType: stagingItem.docType,
        status: "queued",
        materialId: null,
        isPublic: false,
        visibilityUpdating: false,
        error: null,
      };
      setUploadItems((prev) => [...prev, uploadItem]);
      setPanelDismissed(false);
      localStorage.removeItem("coursemate_progress_dismissed");
      await uploadOne(uploadItem);
    },
    [uploadOne],
  );

  // ── remove a staging item ─────────────────────────────────────────────────
  const removeStagingItem = useCallback((id) => {
    setStagingItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  // ── visibility toggle for upload items ───────────────────────────────────
  const handleUploadItemVisibility = useCallback(
    async (id, isPublic) => {
      const item = uploadItems.find((i) => i.id === id);
      if (!item?.materialId) return;

      setUploadItems((prev) =>
        prev.map((i) =>
          i.id === id ? { ...i, isPublic, visibilityUpdating: true } : i,
        ),
      );
      try {
        await fetch("/api/material", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            action: "update_visibility",
            material_id: item.materialId,
            visibility: isPublic ? "public" : "private",
          }),
        });
        // Refresh materials grid so visibility badge stays in sync
        setMaterials((prev) =>
          prev.map((m) =>
            m.id === item.materialId
              ? { ...m, visibility: isPublic ? "public" : "private" }
              : m,
          ),
        );
      } catch {
        // revert on failure
        setUploadItems((prev) =>
          prev.map((i) => (i.id === id ? { ...i, isPublic: !isPublic } : i)),
        );
      } finally {
        setUploadItems((prev) =>
          prev.map((i) =>
            i.id === id ? { ...i, visibilityUpdating: false } : i,
          ),
        );
      }
    },
    [uploadItems],
  );

  // ── visibility toggle for existing materials ──────────────────────────────
  const handleMaterialVisibility = useCallback(async (materialId, isPublic) => {
    setMaterials((prev) =>
      prev.map((m) =>
        m.id === materialId
          ? {
              ...m,
              visibility: isPublic ? "public" : "private",
              updating: true,
            }
          : m,
      ),
    );
    try {
      await fetch("/api/material", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          action: "update_visibility",
          material_id: materialId,
          visibility: isPublic ? "public" : "private",
        }),
      });
    } catch {
      // revert
      setMaterials((prev) =>
        prev.map((m) =>
          m.id === materialId
            ? { ...m, visibility: isPublic ? "private" : "public" }
            : m,
        ),
      );
    } finally {
      setMaterials((prev) =>
        prev.map((m) => (m.id === materialId ? { ...m, updating: false } : m)),
      );
    }
  }, []);

  const handleSyncToggle = useCallback((externalId, next) => {
    setSyncToggles((prev) => ({ ...prev, [externalId]: next }));
  }, []);

  const handleSyncDocTypeChange = useCallback((externalId, docType) => {
    setSyncDocTypes((prev) => ({ ...prev, [externalId]: docType }));
  }, []);

  const handleSyncConfirm = useCallback(async () => {
    if (!selectedSourcePointId || syncRows.length === 0) return;
    setSyncRowsLoading(true);
    setSyncRowsError("");
    try {
      const filesPayload = syncRows.map((row) => ({
        external_id: row.external_id,
        name: row.name,
        sync: syncToggles[row.external_id] ?? row.sync !== false,
        doc_type: syncDocTypes[row.external_id] ?? row.doc_type ?? "general",
      }));
      const res = await fetch("/api/material", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          action: "bulk_upsert_sync",
          course_id: courseId,
          source_point_id: Number(selectedSourcePointId),
          source_type: syncProvider,
          files: filesPayload,
        }),
      });
      let data = {};
      let rawText = "";
      try {
        rawText = await res.text();
        data = rawText ? JSON.parse(rawText) : {};
      } catch {
        data = {};
      }
      if (!res.ok) {
        const detail =
          data?.detail ||
          data?.error ||
          (rawText ? rawText.slice(0, 2000) : "");
        const msg = `Failed to sync file selections (HTTP ${res.status}${detail ? `): ${detail}` : ")"}`;
        console.error("[materials] bulk_upsert_sync failed", {
          status: res.status,
          payload: {
            action: "bulk_upsert_sync",
            course_id: courseId,
            source_point_id: Number(selectedSourcePointId),
            source_type: syncProvider,
            files_count: filesPayload.length,
          },
          response_json: data,
          response_text: rawText,
        });
        throw new Error(msg);
      }

      const confirmedIds = new Set(
        filesPayload.filter((row) => row.sync).map((row) => row.external_id),
      );
      setMaterials((prev) =>
        prev.map((m) =>
          confirmedIds.has(m.external_id) && m.source_type === syncProvider
            ? { ...m, embed_status: "syncing" }
            : m,
        ),
      );
      const syncedFiles = filesPayload
        .filter((row) => row.sync)
        .map((row) => ({ external_id: row.external_id, name: row.name || row.external_id }));
      setSyncJobs((prev) => [
        ...prev,
        {
          jobId: `${Date.now()}-${Math.random()}`,
          label:
            selectedSourcePoint?.external_title ||
            selectedSourcePoint?.external_id ||
            "Source point",
          provider: syncProvider,
          items: syncedFiles,
        },
      ]);
      setPanelDismissed(false);
      localStorage.removeItem("coursemate_progress_dismissed");
      setSyncModalOpen(false);
      await fetchMaterials();
    } catch (err) {
      setSyncRowsError(err?.message || "Failed to sync file selections");
    } finally {
      setSyncRowsLoading(false);
    }
  }, [
    courseId,
    fetchMaterials,
    selectedSourcePoint,
    selectedSourcePointId,
    syncDocTypes,
    syncProvider,
    syncRows,
    syncToggles,
  ]);

  const handleAddSourcePoint = useCallback(
    async (result) => {
      const alreadyExists = (sourcePoints[syncProvider] || []).find(
        (sp) => String(sp.external_id) === String(result.id),
      );
      if (alreadyExists) {
        setSelectedSourcePointId(String(alreadyExists.id));
        setSourceSearch("");
        setSourceSearchResults([]);
        return;
      }
      const endpoint =
        syncProvider === "notion" ? "/api/notion" : "/api/gdrive";
      const externalTitle =
        syncProvider === "notion"
          ? result.title || result.name || ""
          : result.name || "";
      try {
        const res = await fetch(`${endpoint}?action=add_source_point`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            course_id: courseId,
            provider: syncProvider,
            external_id: result.id,
            external_title: externalTitle,
          }),
        });
        const data = await res.json();
        if (res.status === 409) {
          setAddError(data?.error || "Already added");
          return;
        }
        if (!res.ok) return;
        setSourceSearch("");
        setSourceSearchResults([]);
        setAddError("");
        await fetchSourcePoints();
        const newId = data?.source_point?.id;
        if (newId) setSelectedSourcePointId(String(newId));
      } catch {
        /* ignore */
      }
    },
    [courseId, syncProvider, sourcePoints, fetchSourcePoints],
  );

  const handleRemoveSourcePoint = useCallback(
    async (id) => {
      const endpoint =
        syncProvider === "notion" ? "/api/notion" : "/api/gdrive";
      try {
        await fetch(
          `${endpoint}?action=remove_source_point&id=${encodeURIComponent(id)}`,
          {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ source_point_id: id }),
          },
        );
        setSourcePoints((prev) => ({
          ...prev,
          [syncProvider]: prev[syncProvider].filter((sp) => sp.id !== id),
        }));
        if (String(selectedSourcePointId) === String(id)) {
          const remaining = (sourcePoints[syncProvider] || []).filter(
            (sp) => sp.id !== id,
          );
          setSelectedSourcePointId(
            remaining[0]?.id ? String(remaining[0].id) : "",
          );
        }
        setConfirmRemoveId(null);
      } catch {
        /* ignore */
      }
    },
    [syncProvider, selectedSourcePointId, sourcePoints],
  );

  const handleToggleSourcePoint = useCallback(
    async (id, currentActive) => {
      const endpoint =
        syncProvider === "notion" ? "/api/notion" : "/api/gdrive";
      try {
        const res = await fetch(
          `${endpoint}?action=toggle_source_point&id=${encodeURIComponent(id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ source_point_id: id }),
          },
        );
        const data = await res.json();
        if (!res.ok) return;
        setSourcePoints((prev) => ({
          ...prev,
          [syncProvider]: prev[syncProvider].map((sp) =>
            sp.id === id
              ? {
                  ...sp,
                  is_active: data?.source_point?.is_active ?? !currentActive,
                }
              : sp,
          ),
        }));
      } catch {
        /* ignore */
      }
    },
    [syncProvider],
  );

  const openSyncModalForId = useCallback(
    async (id) => {
      const endpoint =
        syncProvider === "notion" ? "/api/notion" : "/api/gdrive";
      setSelectedSourcePointId(String(id));
      setSyncModalOpen(true);
      setSyncRowsLoading(true);
      setSyncRowsError("");
      try {
        const res = await fetch(
          `${endpoint}?action=list_source_point_files&id=${id}&page=1`,
          { credentials: "include" },
        );
        const data = await res.json();
        if (!res.ok)
          throw new Error(data?.error || "Failed to load source point files");
        const rows = normalizeSyncRows(syncProvider, data.files);
        const nextToggles = {};
        const nextDocTypes = {};
        rows.forEach((row) => {
          nextToggles[row.external_id] = row.sync !== false;
          if (row.doc_type != null)
            nextDocTypes[row.external_id] = row.doc_type;
        });
        setSyncRows(rows);
        setSyncToggles(nextToggles);
        setSyncDocTypes(nextDocTypes);
        setSyncPage(1);
        setSyncHasMore(Boolean(data.has_more));
      } catch (err) {
        setSyncRows([]);
        setSyncHasMore(false);
        setSyncRowsError(err?.message || "Failed to load source point files");
      } finally {
        setSyncRowsLoading(false);
      }
    },
    [syncProvider],
  );

  const closeSyncModal = useCallback(() => {
    setSyncModalOpen(false);
    setSyncRows([]);
    setSyncRowsError("");
    setSyncToggles({});
    setSyncDocTypes({});
  }, []);

  // ── delete material ──────────────────────────────────────────────────────
  const handleDelete = useCallback(
    async (material) => {
      try {
        await fetch("/api/material", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            material_id: material.id,
            course_id: courseId,
            tombstone: Boolean(material.integration_source_point_id),
          }),
        });
        setMaterials((prev) => prev.filter((m) => m.id !== material.id));
      } catch {
        // ignore
      }
    },
    [courseId],
  );

  const dismissItem = (id) =>
    setUploadItems((prev) => prev.filter((i) => i.id !== id));

  const isTerminalUpload = (i) => i.status === "done" || i.status === "error";
  const isTerminalSyncItem = (item) => {
    const status = embedStatusMap[item.external_id];
    return (
      status === "done" ||
      status === "failed" ||
      status === "skipped"
    );
  };

  const handleClearDone = useCallback(() => {
    setSyncJobs((prev) =>
      prev.filter((job) => !job.items.every(isTerminalSyncItem)),
    );
    setUploadItems((prev) => prev.filter((i) => !isTerminalUpload(i)));
    // If after clearing nothing active remains, dismiss the panel
    const remainingSync = syncJobs.filter(
      (job) => !job.items.every(isTerminalSyncItem),
    );
    const remainingUploads = uploadItems.filter((i) => !isTerminalUpload(i));
    if (remainingSync.length === 0 && remainingUploads.length === 0) {
      setPanelDismissed(true);
      localStorage.setItem("coursemate_progress_dismissed", "true");
    }
  }, [syncJobs, uploadItems, embedStatusMap]);
  const providerSourcePoints = sourcePoints[syncProvider] || [];

  const visibleMaterials = materials.filter((m) => {
    if (ownerFilter === "mine" && m.uploaded_by !== userId) return false;
    if (typeFilter === "uploaded" && m.source_type !== "upload") return false;
    if (typeFilter === "generated" && m.source_type !== "generated")
      return false;
    return true;
  });

  return (
    <div className="space-y-8 pb-4">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="flex border-b border-gray-100">
          {["gdrive", "notion"].map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => {
                setSyncProvider(p);
                setSourceSearch("");
                setSourceSearchResults([]);
                setConfirmRemoveId(null);
                setAddError("");
              }}
              className={`flex-1 py-2.5 text-xs font-medium transition-colors ${
                syncProvider === p
                  ? "bg-indigo-50 text-indigo-700 border-b-2 border-indigo-500"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
              }`}
            >
              {p === "gdrive" ? "Google Drive" : "Notion"}
            </button>
          ))}
        </div>
        <div className="p-4 space-y-3">
          {/* Search to add a new source point */}
          <div className="relative">
            <input
              type="text"
              value={sourceSearch}
              onChange={(e) => {
                setSourceSearch(e.target.value);
                setAddError("");
              }}
              placeholder={
                syncProvider === "notion"
                  ? "Search Notion databases to add…"
                  : "Search Drive folders to add…"
              }
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
            />
            {sourceSearching && (
              <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
                <Spinner size={14} />
              </div>
            )}
          </div>
          {sourceSearch.trim() !== "" && sourceSearchResults.length > 0 && (
            <div className="border border-gray-100 rounded-lg overflow-hidden max-h-44 overflow-y-auto">
              {sourceSearchResults.map((r) => {
                const isDuplicate = providerSourcePoints.some(
                  (sp) => String(sp.external_id) === String(r.id),
                );
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => {
                      if (!isDuplicate) handleAddSourcePoint(r);
                    }}
                    disabled={isDuplicate}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm border-b border-gray-50 last:border-0 transition-colors ${
                      isDuplicate
                        ? "text-gray-400 bg-gray-50 cursor-default"
                        : "text-gray-800 hover:bg-indigo-50 hover:text-indigo-700"
                    }`}
                  >
                    <span className="flex-1 truncate">
                      {syncProvider === "notion"
                        ? r.title || "Untitled"
                        : r.name || "Untitled"}
                    </span>
                    {isDuplicate ? (
                      <span className="ml-2 text-xs text-gray-400 shrink-0">
                        Already added
                      </span>
                    ) : (
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${syncProvider === "notion" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}
                      >
                        {syncProvider === "notion" ? "DB" : "Folder"}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
          {addError && <p className="text-xs text-red-500">{addError}</p>}
          <div className="space-y-2">
            {sourcePointsLoading ? (
              <div className="flex justify-center py-4">
                <Spinner size={20} />
              </div>
            ) : providerSourcePoints.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-4">
                No source points added yet.
              </p>
            ) : (
              providerSourcePoints.map((sp) => (
                <div
                  key={sp.id}
                  className="flex items-center gap-2 p-2.5 rounded-lg border border-gray-100 bg-gray-50 group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">
                      {sp.external_title || sp.external_id}
                    </p>
                    {sp.last_synced_at && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        Last synced {formatDateTime(sp.last_synced_at)}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      handleToggleSourcePoint(sp.id, sp.is_active !== false)
                    }
                    title={
                      sp.is_active !== false
                        ? "Pause ingestion"
                        : "Resume ingestion"
                    }
                    className={`px-2 py-1 text-xs rounded border transition-colors shrink-0 ${
                      sp.is_active !== false
                        ? "border-green-200 bg-green-50 text-green-700 hover:bg-red-50 hover:text-red-600 hover:border-red-200"
                        : "border-gray-200 bg-gray-100 text-gray-500 hover:bg-green-50 hover:text-green-600 hover:border-green-200"
                    }`}
                  >
                    {sp.is_active !== false ? "Active" : "Paused"}
                  </button>
                  <button
                    type="button"
                    onClick={() => openSyncModalForId(sp.id)}
                    className="px-2 py-1 text-xs rounded border border-gray-200 text-gray-600 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200 transition-colors shrink-0"
                  >
                    Sync
                  </button>
                  {confirmRemoveId === sp.id ? (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => handleRemoveSourcePoint(sp.id)}
                        className="px-2 py-1 text-xs rounded bg-red-600 text-white hover:bg-red-700"
                      >
                        Remove
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmRemoveId(null)}
                        className="px-2 py-1 text-xs rounded border border-gray-200 text-gray-500 hover:bg-gray-100"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmRemoveId(sp.id)}
                      className="p-1.5 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                      title="Remove source point"
                    >
                      <TrashIcon size={14} />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Upload section */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
        <UploadZone onFiles={handleFiles} disabled={false} />

        {/* Staging queue — doc type selection before upload starts */}
        {stagingItems.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Ready to upload
            </p>
            {stagingItems.map((item) => (
              <StagingItemRow
                key={item.id}
                item={item}
                onDocTypeChange={handleStagingDocType}
                onUpload={handleStagingUpload}
                onRemove={removeStagingItem}
              />
            ))}
          </div>
        )}
      </div>

      {/* Sync Modal (overlay-style card, rendered when open) */}
      {syncModalOpen && (
        <SyncModal
          provider={syncProvider}
          sourcePointTitle={
            selectedSourcePoint?.external_title ||
            selectedSourcePoint?.external_id
          }
          rows={syncRows}
          page={syncPage}
          hasMore={syncHasMore}
          loading={syncRowsLoading}
          toggles={syncToggles}
          docTypes={syncDocTypes}
          error={syncRowsError}
          onToggle={handleSyncToggle}
          onDocTypeChange={handleSyncDocTypeChange}
          onPrevPage={() => fetchSyncRowsPage(Math.max(1, syncPage - 1))}
          onNextPage={() => fetchSyncRowsPage(syncPage + 1)}
          onSync={handleSyncConfirm}
          onClose={closeSyncModal}
        />
      )}

      {/* Progress panel — between upload section and materials grid */}
      {(syncJobs.length > 0 || uploadItems.length > 0) && !panelDismissed && (
        <ProgressPanel
          syncJobs={syncJobs}
          uploadItems={uploadItems}
          embedStatusMap={embedStatusMap}
          onClearDone={handleClearDone}
        />
      )}

      {/* Materials grid */}
      <div>
        {/* Header + filter bar */}
        <div className="flex flex-col gap-3 mb-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-800">
              Course Materials
            </h2>
            {!loadingMats && (
              <span className="text-xs text-gray-400">
                {visibleMaterials.length} file
                {visibleMaterials.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <FilterBar
            ownerFilter={ownerFilter}
            setOwnerFilter={setOwnerFilter}
            typeFilter={typeFilter}
            setTypeFilter={setTypeFilter}
          />
        </div>

        {loadingMats ? (
          <div className="flex items-center justify-center py-16">
            <Spinner size={28} className="text-indigo-400" />
          </div>
        ) : visibleMaterials.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="mb-3 opacity-40"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <p className="text-sm">
              {materials.length === 0
                ? "No materials yet — upload your first file above."
                : "No materials match the current filter."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {visibleMaterials.map((m) => (
              <MaterialCard
                key={m.id}
                material={m}
                courseId={courseId}
                onVisibilityChange={handleMaterialVisibility}
                onDelete={handleDelete}
                isOwner={m.uploaded_by === userId}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
