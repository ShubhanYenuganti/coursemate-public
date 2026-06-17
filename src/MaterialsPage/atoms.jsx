import { getMeta, SOURCE_TYPE_META } from "./constants";

// ─── small shared pieces ─────────────────────────────────────────────────────

export function FileTypeIcon({ type, large = false }) {
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

export function Spinner({ size = 16, className = "text-indigo-500" }) {
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

export function VisibilityToggle({
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

export function TrashIcon({ size = 16 }) {
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

// ─── source type badge ───────────────────────────────────────────────────────

export function SourceTypeBadge({ sourceType }) {
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

export function EmbedStatusBadge({ status, sourceType }) {
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
