// ─── constants ───────────────────────────────────────────────────────────────

export const DOCUMENT_TYPES = [
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

export const ACCEPTED_TYPES = new Set([
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

export const TYPE_META = {
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

export function getMeta(type) {
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

export function fmtSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

let _seq = 0;
export function uid() {
  return ++_seq;
}

// ─── source type badge ───────────────────────────────────────────────────────

export const SOURCE_TYPE_META = {
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
