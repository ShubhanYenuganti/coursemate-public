import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

// ─── icons ────────────────────────────────────────────────────────────────────

function PlusIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function ChatBubbleIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function ThumbsUpIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
      <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
    </svg>
  );
}

function ThumbsDownIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
      <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-4" />
    </svg>
  );
}

function RevertIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7v6h6" />
      <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13" />
    </svg>
  );
}

function RestoreIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 7v6h-6" />
      <path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13" />
    </svg>
  );
}

function MoreIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function SparkleIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
      fill="currentColor">
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

function ArchiveIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="21 8 21 21 3 21 3 8" />
      <rect x="1" y="3" width="22" height="5" />
      <line x1="10" y1="12" x2="14" y2="12" />
    </svg>
  );
}

function UnarchiveIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="21 8 21 21 3 21 3 8" />
      <rect x="1" y="3" width="22" height="5" />
      <polyline points="10 15 12 12 14 15" />
      <line x1="12" y1="12" x2="12" y2="17" />
    </svg>
  );
}

function ExternalLinkIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

const FILE_TYPE_MAP = {
  pdf:  { label: 'PDF', bg: 'bg-rose-100',   text: 'text-rose-600'   },
  doc:  { label: 'DOC', bg: 'bg-blue-100',   text: 'text-blue-600'   },
  docx: { label: 'DOC', bg: 'bg-blue-100',   text: 'text-blue-600'   },
  xls:  { label: 'XLS', bg: 'bg-green-100',  text: 'text-green-700'  },
  xlsx: { label: 'XLS', bg: 'bg-green-100',  text: 'text-green-700'  },
  csv:  { label: 'CSV', bg: 'bg-green-100',  text: 'text-green-700'  },
  png:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  jpg:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  jpeg: { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  gif:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  svg:  { label: 'SVG', bg: 'bg-orange-100', text: 'text-orange-600' },
  txt:  { label: 'TXT', bg: 'bg-gray-100',   text: 'text-gray-500'   },
};

function FileTypeBadge({ name }) {
  const ext = (name || '').split('.').pop().toLowerCase();
  const style = FILE_TYPE_MAP[ext] || { label: ext.slice(0, 3).toUpperCase() || 'DOC', bg: 'bg-gray-100', text: 'text-gray-500' };
  return (
    <span className={`flex-shrink-0 inline-flex items-center justify-center w-[22px] h-[16px] rounded text-[7px] font-bold tracking-tight ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

function MaterialCheckbox({ checked, onToggle }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
      className={`flex-shrink-0 w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-colors ${
        checked
          ? 'bg-indigo-500 border-indigo-500'
          : 'border-gray-300 hover:border-indigo-400'
      }`}
    >
      {checked && (
        <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24"
          fill="none" stroke="white" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
    </button>
  );
}

const MODEL_LABELS = {
  gemini: 'Gemini',
  openai: 'GPT',
  claude: 'Claude',
};

const PROVIDER_MODELS = {
  claude: [
    { label: 'Claude Opus 4.6',   id: 'claude-opus-4-6' },
    { label: 'Claude Sonnet 4.6', id: 'claude-sonnet-4-6' },
    { label: 'Claude Haiku 4.5',  id: 'claude-haiku-4-5-20251001' },
    { label: 'Claude Sonnet 4.5', id: 'claude-sonnet-4-5-20250929' },
    { label: 'Claude Sonnet 4',   id: 'claude-sonnet-4-20250514' },
    { label: 'Claude Opus 4',     id: 'claude-opus-4-20250514' },
  ],
  gemini: [
    { label: 'Gemini 3.1 Pro',        id: 'gemini-3.1-pro-preview' },
    { label: 'Gemini 3 Flash',        id: 'gemini-3-flash-preview' },
    { label: 'Gemini 2.5 Pro',        id: 'gemini-2.5-pro' },
    { label: 'Gemini 2.5 Flash',      id: 'gemini-2.5-flash' },
    { label: 'Gemini 2.5 Flash-Lite', id: 'gemini-2.5-flash-lite' },
    { label: 'Deep Research',         id: 'deep-research-pro-preview-12-2025' },
    { label: 'Gemini 2.0 Flash',      id: 'gemini-2.0-flash' },
    { label: 'Gemini 2.0 Flash-Lite', id: 'gemini-2.0-flash-lite' },
  ],
  openai: [
    { label: 'GPT-5.2',               id: 'gpt-5.2' },
    { label: 'GPT-5.1',               id: 'gpt-5.1' },
    { label: 'GPT-5 Mini',            id: 'gpt-5-mini' },
    { label: 'GPT-5 Nano',            id: 'gpt-5-nano' },
    { label: 'GPT-4.1',               id: 'gpt-4.1' },
    { label: 'GPT-4.1 mini',          id: 'gpt-4.1-mini' },
    { label: 'GPT-4.1 nano',          id: 'gpt-4.1-nano' },
    { label: 'GPT-4o',                id: 'gpt-4o' },
    { label: 'GPT-4o mini',           id: 'gpt-4o-mini' },
    { label: 'o3',                    id: 'o3' },
    { label: 'o3-mini',               id: 'o3-mini' },
    { label: 'o3-pro',                id: 'o3-pro' },
    { label: 'o4-mini',               id: 'o4-mini' },
    { label: 'o1',                    id: 'o1' },
    { label: 'o1-pro',                id: 'o1-pro' },
    { label: 'o3 Deep Research',      id: 'o3-deep-research' },
    { label: 'o4-mini Deep Research', id: 'o4-mini-deep-research' },
    { label: 'GPT-OSS 120B',          id: 'gpt-oss-120b' },
  ],
};

// ─── helpers ──────────────────────────────────────────────────────────────────

function groupChatsByDate(chats) {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const weekStart = new Date(todayStart.getTime() - 6 * 24 * 60 * 60 * 1000);
  const today = [], lastWeek = [], older = [];
  for (const chat of chats) {
    const d = new Date(chat.last_message_at || chat.created_at);
    if (d >= todayStart) today.push(chat);
    else if (d >= weekStart) lastWeek.push(chat);
    else older.push(chat);
  }
  return { today, lastWeek, older };
}

// ─── sub-components ───────────────────────────────────────────────────────────

function ConvItem({ conv, active, onClick, onDoubleClick, onArchive }) {
  return (
    <div className={`group w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs transition-colors ${
      active
        ? 'bg-indigo-50 text-indigo-700 font-medium'
        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
    }`}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onArchive(conv.id, !conv.is_archived); }}
        title={conv.is_archived ? 'Unarchive' : 'Archive'}
        className="flex-shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-all text-gray-400 hover:text-indigo-500 hover:bg-indigo-50"
      >
        {conv.is_archived ? <UnarchiveIcon /> : <ArchiveIcon />}
      </button>
      <button
        type="button"
        onClick={onClick}
        onDoubleClick={onDoubleClick}
        className="flex-1 flex items-center gap-2 min-w-0 text-left"
      >
        <span className={`flex-shrink-0 ${active ? 'text-indigo-500' : 'text-gray-400'}`}>
          <ChatBubbleIcon />
        </span>
        <span className="truncate">{conv.title}</span>
      </button>
    </div>
  );
}

function ArchivedConvItem({ conv, onDelete, onUnarchive }) {
  return (
    <div className="group w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
      <button
        type="button"
        onClick={() => onDelete(conv.id)}
        title="Delete permanently"
        className="flex-shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-all text-gray-400 hover:text-red-500 hover:bg-red-50"
      >
        <TrashIcon />
      </button>
      <button
        type="button"
        onClick={() => onUnarchive(conv.id)}
        title="Unarchive"
        className="flex-shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-all text-gray-400 hover:text-indigo-500 hover:bg-indigo-50"
      >
        <UnarchiveIcon />
      </button>
      <span className="flex-1 truncate min-w-0">{conv.title}</span>
    </div>
  );
}

function SourcesPanel({ open, chunks, focusIndex, onClose, materials }) {
  const focusRef = useRef(null);
  const materialMap = {};
  (materials || []).forEach((m) => { materialMap[m.id] = m; });

  useEffect(() => {
    if (open && focusRef.current) {
      focusRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [open, focusIndex]);

  return (
    <div className={`absolute right-0 top-0 h-full w-80 bg-white border-l border-gray-200 flex flex-col shadow-xl z-20 transition-transform duration-200 ${open ? 'translate-x-0' : 'translate-x-full'}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 flex-shrink-0">
        <span className="text-sm font-semibold text-gray-800">Sources ({chunks?.length || 0})</span>
        <button onClick={onClose} className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors">
          <XIcon />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {(chunks || []).map((chunk, idx) => {
          const n = idx + 1;
          const isFocused = n === focusIndex;
          const material = chunk.material_id != null ? materialMap[chunk.material_id] : null;
          const downloadUrl = material?.download_url || null;
          return (
            <div
              key={idx}
              ref={isFocused ? focusRef : null}
              className={`rounded-lg px-3 py-2.5 border text-xs transition-colors ${
                isFocused
                  ? 'border-l-4 border-indigo-400 bg-indigo-50'
                  : 'border-gray-100 bg-gray-50'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center w-4 h-4 rounded bg-indigo-100 text-indigo-600 font-semibold text-[10px] flex-shrink-0">
                  {n}
                </span>
                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium ${
                  chunk.chunk_type === 'visual' ? 'bg-orange-100 text-orange-600' : 'bg-blue-100 text-blue-600'
                }`}>
                  {chunk.chunk_type === 'visual' ? 'Slide' : 'Text'}
                </span>
                {material?.name && (
                  <span className="text-gray-500 truncate text-[9px]" title={material.name}>{material.name}</span>
                )}
                {chunk.page_number != null && (
                  <span className="text-gray-400">p.{chunk.page_number}</span>
                )}
                {chunk.similarity != null && (
                  <span className="text-gray-400 tabular-nums">{chunk.similarity}</span>
                )}
                <div className="flex-1" />
                {downloadUrl ? (
                  <a
                    href={downloadUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={material?.name || 'Open source'}
                    className="p-1 rounded text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors flex-shrink-0"
                  >
                    <ExternalLinkIcon />
                  </a>
                ) : (
                  <span className="p-1 text-gray-200 flex-shrink-0">
                    <ExternalLinkIcon />
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MessageBubble({
  msg,
  courseName,
  userPicture,
  onCiteClick,
  isEditing,
  editingContent,
  onEditStart,
  onEditChange,
  onEditSave,
  onEditCancel,
  canEdit,
  replyHistory,
  onRevert,
  onRestore,
  onRegenerate,
  availableModels,
}) {
  const isUser = msg.role === 'user';
  const [copied, setCopied] = useState(false);
  const [regenOpen, setRegenOpen] = useState(false);
  const [regenProvider, setRegenProvider] = useState(null);
  const regenRef = useRef(null);

  useEffect(() => {
    if (!regenOpen) return;
    function handleClickOutside(e) {
      if (regenRef.current && !regenRef.current.contains(e.target)) setRegenOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [regenOpen]);

  function processCitations(children) {
    const nodes = Array.isArray(children) ? children : [children];
    return nodes.flatMap((child, ci) => {
      if (typeof child !== 'string') return [child];
      // Only match [N] not immediately adjacent to another bracket group
      const parts = child.split(/(?<!\])(\[\d+\])(?!\[)/);
      return parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/);
        if (!m) return part;
        const n = Number(m[1]);
        return (
          <button
            key={`${ci}-${i}`}
            onClick={() => onCiteClick && onCiteClick(n)}
            className="inline-flex items-center justify-center w-4 h-4 rounded text-[10px] font-semibold bg-indigo-100 text-indigo-600 hover:bg-indigo-200 cursor-pointer align-super mx-0.5"
          >
            {n}
          </button>
        );
      });
    });
  }

  function renderContent(content) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          p: ({ children }) => (
            <p className="mt-1 first:mt-0">
              {onCiteClick ? processCitations(children) : children}
            </p>
          ),
          strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
          ol: ({ children }) => <ol className="list-decimal list-outside ml-5 mt-1 space-y-0.5">{children}</ol>,
          ul: ({ children }) => <ul className="list-disc list-outside ml-5 mt-1 space-y-0.5">{children}</ul>,
          li: ({ children }) => <li className="mt-0.5">{onCiteClick ? processCitations(children) : children}</li>,
          code: ({ inline, children }) => inline
            ? <code className="bg-gray-100 text-indigo-700 rounded px-1 py-0.5 text-xs font-mono">{children}</code>
            : <pre className="bg-gray-100 rounded-lg p-3 mt-2 overflow-x-auto text-xs font-mono">{children}</pre>,
        }}
      >
        {content}
      </ReactMarkdown>
    );
  }

  async function handleCopy() {
    if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(msg.content || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Ignore clipboard failures; keep UI responsive.
    }
  }

  function formatEditTime(raw) {
    if (!raw) return '';
    const dt = new Date(raw);
    if (Number.isNaN(dt.getTime())) return '';
    return dt.toLocaleString();
  }

  if (isUser) {
    return (
      <div className="group flex items-start gap-3">
        {userPicture ? (
          <img src={userPicture} alt="You" className="w-7 h-7 rounded-full border border-gray-200 flex-shrink-0 mt-0.5" />
        ) : (
          <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
            U
          </div>
        )}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="space-y-2">
              <textarea
                autoFocus
                value={editingContent}
                onChange={(e) => onEditChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    onEditSave();
                  } else if (e.key === 'Escape') {
                    e.preventDefault();
                    onEditCancel();
                  }
                }}
                rows={3}
                className="w-full rounded-lg border border-indigo-200 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 text-sm text-gray-800 leading-relaxed px-3 py-2 resize-y"
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onEditSave}
                  className="px-2.5 py-1 text-xs rounded-md bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={onEditCancel}
                  className="px-2.5 py-1 text-xs rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <p className="text-sm text-gray-800 leading-relaxed">{msg.content}</p>
              {msg.is_edited && (
                <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                  Edited
                </span>
              )}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={() => onEditStart(msg.id, msg.content)}
          disabled={!canEdit || isEditing}
          className="flex-shrink-0 mt-0.5 p-1.5 rounded-lg text-gray-300 hover:text-indigo-500 hover:bg-indigo-50 opacity-0 group-hover:opacity-100 transition-all"
          title="Edit message"
        >
          <EditIcon />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-start">
      <div className="w-10 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-indigo-600 uppercase tracking-wide">
            {courseName || 'CourseMate AI'}
          </span>
          {msg.ai_provider ? (
            <>
              <span className="w-1 h-1 rounded-full bg-indigo-300" />
              <span className="text-xs text-gray-400">
                {PROVIDER_MODELS[msg.ai_provider]?.find((m) => m.id === msg.ai_model)?.label || msg.ai_model || MODEL_LABELS[msg.ai_provider] || msg.ai_provider}
              </span>
            </>
          ) : (
            <span className="w-1 h-1 rounded-full bg-indigo-300" />
          )}
        </div>
        <div className="text-sm text-gray-700 leading-relaxed space-y-0.5">
          {renderContent(msg.content)}
        </div>
        <div className="flex items-center gap-1 mt-3">
          <button type="button" className="p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors" title="Helpful">
            <ThumbsUpIcon />
          </button>
          <button type="button" className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors" title="Not helpful">
            <ThumbsDownIcon />
          </button>
          <button
            type="button"
            onClick={handleCopy}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            title={copied ? 'Copied' : 'Copy'}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
          </button>
          <button type="button" className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors" title="More">
            <MoreIcon />
          </button>
          <div className="flex-1" />
          {onRegenerate && availableModels?.length > 0 && (
            <div className="relative" ref={regenRef}>
              <button
                type="button"
                onClick={() => { setRegenOpen((o) => !o); setRegenProvider(null); }}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors border border-gray-200 hover:border-indigo-200"
              >
                <RefreshIcon />
                Regenerate
              </button>
              {regenOpen && (
                <div className="absolute bottom-full right-0 mb-2 bg-gray-900 rounded-xl shadow-xl border border-gray-700/60 z-50 overflow-hidden min-w-[190px]">
                  {regenProvider === null ? (
                    /* Provider list */
                    <div className="py-1">
                      <p className="px-3 pt-1.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500">Choose model</p>
                      {availableModels.map((provider) => (
                        <button
                          key={provider}
                          type="button"
                          onClick={() => setRegenProvider(provider)}
                          className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left text-gray-300 hover:bg-gray-700/70 transition-colors"
                        >
                          <span>{MODEL_LABELS[provider] || provider}</span>
                          <ChevronDownIcon />
                        </button>
                      ))}
                    </div>
                  ) : (
                    /* Model list for selected provider */
                    <div className="py-1 max-h-52 overflow-y-auto">
                      <button
                        type="button"
                        onClick={() => setRegenProvider(null)}
                        className="w-full flex items-center gap-1.5 px-3 py-2 text-[11px] text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 transition-colors"
                      >
                        <span>←</span>
                        {MODEL_LABELS[regenProvider] || regenProvider}
                      </button>
                      <div className="border-t border-gray-700/50 my-0.5" />
                      {(PROVIDER_MODELS[regenProvider] || []).map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            setRegenOpen(false);
                            setRegenProvider(null);
                            onRegenerate(msg.id, regenProvider, m.id);
                          }}
                          className="w-full px-3 py-2 text-[11px] text-left text-gray-300 hover:bg-gray-700/70 transition-colors"
                        >
                          {m.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        {(replyHistory?.back?.length > 0 || replyHistory?.forward?.length > 0) && (
          <div className="flex items-center gap-2 mt-2">
            {replyHistory.back?.length > 0 && onRevert && (
              <button
                type="button"
                onClick={() => onRevert(msg.id)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-gray-500 hover:text-amber-600 hover:bg-amber-50 transition-colors border border-gray-200 hover:border-amber-200"
              >
                <RevertIcon />
                Revert response
              </button>
            )}
            {replyHistory.forward?.length > 0 && onRestore && (
              <button
                type="button"
                onClick={() => onRestore(msg.id)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-gray-500 hover:text-emerald-600 hover:bg-emerald-50 transition-colors border border-gray-200 hover:border-emerald-200"
              >
                <RestoreIcon />
                Restore response
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function ChatTab({ course, userData, sessionToken }) {
  const [activeConv, setActiveConv] = useState(null);
  const [chats, setChats] = useState([]);
  const [chatsLoading, setChatsLoading] = useState(false);
  const [archivedChats, setArchivedChats] = useState([]);
  const [archivedOpen, setArchivedOpen] = useState(false);
  const [archivedLoading, setArchivedLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [selectedModel, setSelectedModel] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [selectedModelId, setSelectedModelId] = useState(null);
  const [modelListDropdownOpen, setModelListDropdownOpen] = useState(false);
  const [switchBanner, setSwitchBanner] = useState('');
  const [materials, setMaterials] = useState([]);
  const [selectedMaterials, setSelectedMaterials] = useState(new Set());
  const [selectAllMaterials, setSelectAllMaterials] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(224);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState('');
  const [titleSaving, setTitleSaving] = useState(false);
  const [editingMsgId, setEditingMsgId] = useState(null);
  const [editingContent, setEditingContent] = useState('');
  const [msgChunks, setMsgChunks] = useState({});
  const [sourcesPanel, setSourcesPanel] = useState({ open: false, messageId: null, focusIndex: null });
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);
  const modelListDropdownRef = useRef(null);
  const titleInputRef = useRef(null);
  const bannerTimerRef = useRef(null);
  const containerRef = useRef(null);
  const isDraggingRef = useRef(false);
  const sendingRef = useRef(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load materials for this course
  useEffect(() => {
    if (!course?.id || !sessionToken) return;
    fetch(`/api/material?course_id=${course.id}`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {});
  }, [course?.id, sessionToken]);

  // Load chats for this course
  useEffect(() => {
    if (!course?.id || !sessionToken) return;
    setChatsLoading(true);
    fetch(`/api/chat?resource=chat&course_id=${course.id}`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => setChats(data.chats || []))
      .catch(() => {})
      .finally(() => setChatsLoading(false));
  }, [course?.id, sessionToken]);

  // Fetch archived chats when the archived dropdown is opened
  useEffect(() => {
    if (!archivedOpen || !course?.id || !sessionToken) return;
    setArchivedLoading(true);
    fetch(`/api/chat?resource=chat&course_id=${course.id}&archived=true`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => setArchivedChats(data.chats || []))
      .catch(() => {})
      .finally(() => setArchivedLoading(false));
  }, [archivedOpen, course?.id, sessionToken]);

  // Load messages when active conversation changes
  useEffect(() => {
    if (!activeConv || activeConv === '__new__' || !sessionToken) return;
    if (sendingRef.current) return;
    fetch(`/api/chat?resource=message&chat_id=${activeConv}`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => setMessages(data.messages || []))
      .catch(() => {});
  }, [activeConv, sessionToken]);

  // Load available API-key-backed models
  useEffect(() => {
    if (!sessionToken) return;
    fetch('/api/user_api_keys', {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => {
        const available = Object.entries(data)
          .filter(([, hasKey]) => hasKey)
          .map(([provider]) => provider);
        setAvailableModels(available);
        if (available.length > 0) {
          const savedProvider = localStorage.getItem('chat_selected_provider');
          const savedModelId = localStorage.getItem('chat_selected_model_id');
          const provider = available.includes(savedProvider) ? savedProvider : available[0];
          const modelList = PROVIDER_MODELS[provider] ?? [];
          const modelId = modelList.find((m) => m.id === savedModelId)?.id ?? modelList[0]?.id ?? null;
          setSelectedModel(provider);
          setSelectedModelId(modelId);
        }
      })
      .catch(() => {});
  }, [sessionToken]);

  useEffect(() => {
    if (!modelDropdownOpen) return;
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setModelDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [modelDropdownOpen]);

  useEffect(() => {
    if (!modelListDropdownOpen) return;
    function handleClickOutside(e) {
      if (modelListDropdownRef.current && !modelListDropdownRef.current.contains(e.target)) {
        setModelListDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [modelListDropdownOpen]);

  function handleModelSelect(provider) {
    setSelectedModel(provider);
    setModelDropdownOpen(false);
    const modelId = PROVIDER_MODELS[provider]?.[0]?.id ?? null;
    setSelectedModelId(modelId);
    localStorage.setItem('chat_selected_provider', provider);
    if (modelId) localStorage.setItem('chat_selected_model_id', modelId);
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    setSwitchBanner(MODEL_LABELS[provider] || provider);
    bannerTimerRef.current = setTimeout(() => setSwitchBanner(''), 2500);
  }

  function handleModelIdSelect(modelId) {
    setSelectedModelId(modelId);
    setModelListDropdownOpen(false);
    localStorage.setItem('chat_selected_model_id', modelId);
  }

  function handleSelectAllMaterials() {
    if (selectAllMaterials) {
      setSelectAllMaterials(false);
      setSelectedMaterials(new Set());
    } else {
      setSelectAllMaterials(true);
      setSelectedMaterials(new Set());
    }
  }

  function handleToggleMaterial(id) {
    setSelectAllMaterials(false);
    setSelectedMaterials((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function isMaterialChecked(id) {
    return selectAllMaterials || selectedMaterials.has(id);
  }

  function handleDownloadMaterial(m) {
    if (!m.download_url) return;
    const a = document.createElement('a');
    a.href = m.download_url;
    a.download = m.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  function handleDragStart(e) {
    e.preventDefault();
    isDraggingRef.current = true;

    function onMouseMove(ev) {
      if (!isDraggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const maxWidth = rect.width * 0.35;
      const newWidth = Math.min(maxWidth, Math.max(160, ev.clientX - rect.left));
      setSidebarWidth(newWidth);
    }

    function onMouseUp() {
      isDraggingRef.current = false;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  function handleNewChat() {
    // Remove any stale temp entry then add a fresh optimistic one
    setChats((prev) => [
      { id: '__new__', title: 'New Chat', course_id: course?.id, message_count: 0, last_message_at: null, created_at: new Date().toISOString(), is_archived: false },
      ...prev.filter((c) => c.id !== '__new__'),
    ]);
    setActiveConv('__new__');
    setMessages([]);
    setInput('');
  }

  async function handleArchiveChat(chatId, isArchived) {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ resource: 'chat', action: 'archive', chat_id: chatId, is_archived: isArchived }),
      });
      if (!res.ok) return;
      const archived = chats.find((c) => c.id === chatId);
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (archived) setArchivedChats((prev) => [{ ...archived, is_archived: true }, ...prev]);
      if (activeConv === chatId) { setActiveConv(null); setMessages([]); }
    } catch {}
  }

  async function handleUnarchiveChat(chatId) {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ resource: 'chat', action: 'archive', chat_id: chatId, is_archived: false }),
      });
      if (!res.ok) return;
      const unarchived = archivedChats.find((c) => c.id === chatId);
      setArchivedChats((prev) => prev.filter((c) => c.id !== chatId));
      if (unarchived) setChats((prev) => [{ ...unarchived, is_archived: false }, ...prev]);
    } catch {}
  }

  async function handleDeleteArchivedChat(chatId) {
    try {
      const res = await fetch('/api/chat', {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ resource: 'chat', chat_id: chatId }),
      });
      if (!res.ok) return;
      setArchivedChats((prev) => prev.filter((c) => c.id !== chatId));
    } catch {}
  }

  async function handleClearAll() {
    if (!course?.id) return;
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ resource: 'chat', action: 'archive_all', course_id: course.id }),
      });
      if (!res.ok) return;
      setChats([]);
      setActiveConv(null);
      setMessages([]);
    } catch {}
  }

  function handleConvSelect(id) {
    setActiveConv(id);
    setMessages([]);
    setEditingTitle(false);
  }

  function handleConvDoubleClick(conv) {
    setActiveConv(conv.id);
    setMessages([]);
    setTitleValue(conv.title || '');
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 0);
  }

  function handleTitleDoubleClick() {
    const chat = chats.find((c) => c.id === activeConv);
    if (!chat || activeConv === '__new__') return;
    setTitleValue(chat.title || '');
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 0);
  }

  async function handleTitleSave() {
    const trimmed = titleValue.trim();
    if (!trimmed || !activeConv || activeConv === '__new__') {
      setEditingTitle(false);
      return;
    }
    const chat = chats.find((c) => c.id === activeConv);
    if (chat && trimmed === chat.title) {
      setEditingTitle(false);
      return;
    }
    setTitleSaving(true);
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ resource: 'chat', action: 'update', chat_id: activeConv, title: trimmed }),
      });
      const data = await res.json();
      if (res.ok && data.chat) {
        setChats((prev) => prev.map((c) => c.id === activeConv ? { ...c, title: data.chat.title } : c));
      }
    } catch {}
    setTitleSaving(false);
    setEditingTitle(false);
  }

  function handleTitleKeyDown(e) {
    if (e.key === 'Enter') { e.preventDefault(); handleTitleSave(); }
    if (e.key === 'Escape') { setEditingTitle(false); }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function openSources(messageId, focusIndex) {
    if (!msgChunks[messageId]) {
      fetch(`/api/chat?resource=chunks&message_id=${messageId}`, {
        headers: { Authorization: `Bearer ${sessionToken}` },
      })
        .then((r) => r.json())
        .then((data) => setMsgChunks((prev) => ({ ...prev, [messageId]: data.chunks || [] })))
        .catch(() => {});
    }
    setSourcesPanel({ open: true, messageId, focusIndex });
    setSidebarWidth(0);
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || sending || !selectedModel) return;
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setSending(true);
    sendingRef.current = true;

    const tempId = Date.now();
    const tempUserMsg = { id: tempId, role: 'user', content: text };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      let chatId = activeConv;

      // Create a chat thread if none exists or if this is the optimistic temp entry
      if (!chatId || chatId === '__new__') {
        const title = text.slice(0, 80);
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${sessionToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ resource: 'chat', action: 'create', course_id: course.id, title }),
        });
        const chatData = await res.json();
        if (!res.ok) throw new Error(chatData.error || 'Failed to create chat');
        chatId = chatData.chat.id;
        setActiveConv(chatId);
        // Replace the optimistic __new__ entry (or prepend if there wasn't one)
        setChats((prev) => [chatData.chat, ...prev.filter((c) => c.id !== '__new__')]);
      }

      const contextIds = selectAllMaterials
        ? materials.map((m) => m.id)
        : Array.from(selectedMaterials);

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          resource: 'message',
          action: 'send',
          chat_id: chatId,
          content: text,
          context_material_ids: contextIds,
          ai_provider: selectedModel,
          ai_model: selectedModelId || selectedModel,
        }),
      });
      const msgData = await res.json();
      if (!res.ok) throw new Error(msgData.error || 'Failed to send message');

      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempId),
        msgData.user_message,
        msgData.assistant_message,
      ]);
      if (msgData.chunks?.length) {
        setMsgChunks((prev) => ({ ...prev, [msgData.assistant_message.id]: msgData.chunks }));
      }
      setChats((prev) => prev.map((c) =>
        c.id === chatId
          ? { ...c, last_message_at: msgData.assistant_message.created_at, message_count: (c.message_count || 0) + 2 }
          : c
      ));
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleEditMessage(messageId, newContent) {
    const trimmed = (newContent || '').trim();
    if (!trimmed || sending || !sessionToken || !selectedModel) return;
    const target = messages.find((m) => m.id === messageId);
    if (!target || target.role !== 'user' || typeof target.message_index !== 'number') return;

    const contextIds = selectAllMaterials
      ? materials.map((m) => m.id)
      : Array.from(selectedMaterials);

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const cutoffIndex = target.message_index;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < cutoffIndex);
    const optimisticEdited = { ...target, content: trimmed, is_edited: true };

    setEditingMsgId(null);
    setEditingContent('');
    setSending(true);
    sendingRef.current = true;
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });
    setMessages([...keptPrefix, optimisticEdited]);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          resource: 'message',
          action: 'edit',
          message_id: messageId,
          content: trimmed,
          context_material_ids: contextIds,
          ai_provider: selectedModel,
          ai_model: selectedModelId || selectedModel,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to edit message');

      const nextMessages = [...keptPrefix, data.user_message, data.assistant_message];
      setMessages(nextMessages);
      setMsgChunks((prev) => {
        const keptIds = new Set(nextMessages.map((m) => m.id));
        const cleaned = Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
        if (data.chunks?.length) cleaned[data.assistant_message.id] = data.chunks;
        return cleaned;
      });
      setChats((prev) => prev.map((c) =>
        c.id === target.chat_id
          ? {
              ...c,
              last_message_at: data.assistant_message.created_at,
              message_count: nextMessages.length,
            }
          : c
      ));
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleRevertMessage(assistantMsgId) {
    if (sending) return;
    const assistantMsg = messages.find((m) => m.id === assistantMsgId);
    if (!assistantMsg) return;
    // Find the nearest user message before this assistant — don't assume contiguous indices
    const userMsg = messages
      .filter((m) => m.role === 'user' && m.message_index < assistantMsg.message_index)
      .sort((a, b) => b.message_index - a.message_index)[0];
    if (!userMsg) return;

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < userMsg.message_index);

    setSending(true);
    sendingRef.current = true;
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { Authorization: `Bearer ${sessionToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ resource: 'message', action: 'revert', message_id: assistantMsgId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to revert');

      const nextMessages = [...keptPrefix, data.user_message, data.assistant_message];
      setMessages(nextMessages);
      setMsgChunks((prev) => {
        const keptIds = new Set(nextMessages.map((m) => m.id));
        return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
      });
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleRestoreMessage(assistantMsgId) {
    if (sending) return;
    const assistantMsg = messages.find((m) => m.id === assistantMsgId);
    if (!assistantMsg) return;
    const userMsg = messages
      .filter((m) => m.role === 'user' && m.message_index < assistantMsg.message_index)
      .sort((a, b) => b.message_index - a.message_index)[0];
    if (!userMsg) return;

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < userMsg.message_index);

    setSending(true);
    sendingRef.current = true;
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { Authorization: `Bearer ${sessionToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ resource: 'message', action: 'restore', message_id: assistantMsgId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to restore');

      const nextMessages = [...keptPrefix, data.user_message, data.assistant_message];
      setMessages(nextMessages);
      setMsgChunks((prev) => {
        const keptIds = new Set(nextMessages.map((m) => m.id));
        return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
      });
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleRegenerateMessage(assistantMsgId, provider, modelId) {
    if (sending) return;
    const assistantMsg = messages.find((m) => m.id === assistantMsgId);
    if (!assistantMsg) return;
    const userMsg = messages
      .filter((m) => m.role === 'user' && m.message_index < assistantMsg.message_index)
      .sort((a, b) => b.message_index - a.message_index)[0];
    if (!userMsg) return;

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < userMsg.message_index);

    setSending(true);
    sendingRef.current = true;
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { Authorization: `Bearer ${sessionToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resource: 'message',
          action: 'regenerate',
          message_id: assistantMsgId,
          ai_provider: provider,
          ai_model: modelId,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to regenerate');

      const nextMessages = [...keptPrefix, data.user_message, data.assistant_message];
      setMessages(nextMessages);
      setMsgChunks((prev) => {
        const keptIds = new Set(nextMessages.map((m) => m.id));
        return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
      });
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  }

  const { today, lastWeek, older } = groupChatsByDate(chats);

  return (
    <div ref={containerRef} className="relative flex rounded-2xl overflow-hidden border border-gray-200 bg-white shadow-sm" style={{ height: '68vh', minHeight: '520px' }}>

      {/* Switched-to banner — centred over the full modal */}
      {switchBanner && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-4 py-1.5 rounded-full bg-gray-900 text-white text-xs font-medium shadow-lg whitespace-nowrap pointer-events-none select-none">
          Switched to {switchBanner} ⚡
        </div>
      )}

      {/* ── Sidebar ── */}
      <div className="flex-shrink-0 bg-gray-50/80 flex flex-col overflow-hidden" style={{ width: sidebarWidth }}>
        {/* Logo / title */}
        <div className="px-4 pt-5 pb-3">
          <div className="flex items-center gap-2 mb-4">
            <span className="font-bold text-gray-900 text-sm">Course Chat</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleNewChat}
              className="flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-full bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors shadow-sm"
            >
              <PlusIcon />
              New chat
            </button>
            <button
              type="button"
              className="flex-shrink-0 p-1.5 text-gray-800 hover:text-indigo-600 transition-colors"
              title="Search"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </button>
          </div>
        </div>

        {/* Scrollable middle: conversations + materials */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">

          {/* Conversations */}
          <div className="overflow-y-auto px-2 space-y-4 pb-3 shrink-0" style={{ maxHeight: '45%' }}>
            {chatsLoading && (
              <p className="px-3 py-2 text-[10px] text-gray-400">Loading...</p>
            )}
            {!chatsLoading && chats.length === 0 && (
              <p className="px-3 py-2 text-[10px] text-gray-400 italic">No conversations yet.</p>
            )}
            {today.length > 0 && (
              <div>
                <p className="px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Today</span>
                  {chats.length > 0 && (
                    <button type="button" onClick={handleClearAll} className="text-indigo-500 hover:text-indigo-700 normal-case text-[10px] font-normal transition-colors">
                      Clear all
                    </button>
                  )}
                </p>
                <div className="space-y-0.5">
                  {today.map((c) => (
                    <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} onDoubleClick={() => handleConvDoubleClick(c)} onArchive={handleArchiveChat} />
                  ))}
                </div>
              </div>
            )}
            {lastWeek.length > 0 && (
              <div>
                <p className="px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Last 7 Days</span>
                  {today.length === 0 && chats.length > 0 && (
                    <button type="button" onClick={handleClearAll} className="text-indigo-500 hover:text-indigo-700 normal-case text-[10px] font-normal transition-colors">
                      Clear all
                    </button>
                  )}
                </p>
                <div className="space-y-0.5">
                  {lastWeek.map((c) => (
                    <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} onDoubleClick={() => handleConvDoubleClick(c)} onArchive={handleArchiveChat} />
                  ))}
                </div>
              </div>
            )}
            {older.length > 0 && (
              <div>
                <p className="px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Older</span>
                  {today.length === 0 && lastWeek.length === 0 && (
                    <button type="button" onClick={handleClearAll} className="text-indigo-500 hover:text-indigo-700 normal-case text-[10px] font-normal transition-colors">
                      Clear all
                    </button>
                  )}
                </p>
                <div className="space-y-0.5">
                  {older.map((c) => (
                    <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} onDoubleClick={() => handleConvDoubleClick(c)} onArchive={handleArchiveChat} />
                  ))}
                </div>
              </div>
            )}

            {/* Archived dropdown */}
            <div className="mt-1">
              <button
                type="button"
                onClick={() => setArchivedOpen((o) => !o)}
                className="w-full flex items-center gap-1.5 px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider hover:text-gray-600 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                  style={{ transform: archivedOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
                  <polyline points="9 18 15 12 9 6" />
                </svg>
                Archived
              </button>
              {archivedOpen && (
                <div className="space-y-0.5 mt-0.5">
                  {archivedLoading && (
                    <p className="px-3 py-1 text-[10px] text-gray-400">Loading...</p>
                  )}
                  {!archivedLoading && archivedChats.length === 0 && (
                    <p className="px-3 py-1 text-[10px] text-gray-400 italic">No archived chats.</p>
                  )}
                  {archivedChats.map((c) => (
                    <ArchivedConvItem
                      key={c.id}
                      conv={c}
                      onDelete={handleDeleteArchivedChat}
                      onUnarchive={handleUnarchiveChat}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Materials */}
          <div className="flex-1 min-h-0 flex flex-col border-t border-gray-200 pt-2">
            {/* Header row */}
            <div className="px-3 py-1 flex items-center justify-between">
              <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">Your Materials</span>
              <button
                type="button"
                onClick={handleSelectAllMaterials}
                title={selectAllMaterials ? 'Deselect all' : 'Select all'}
                className={`flex-shrink-0 w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-colors ${
                  selectAllMaterials
                    ? 'bg-indigo-500 border-indigo-500'
                    : 'border-gray-300 hover:border-indigo-400'
                }`}
              >
                {selectAllMaterials && (
                  <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24"
                    fill="none" stroke="white" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </button>
            </div>

            {/* Materials list */}
            <div className="flex-1 overflow-y-auto pb-3">
              {materials.length === 0 ? (
                <p className="px-3 py-2 text-[10px] text-gray-400 italic">No materials uploaded yet.</p>
              ) : (
                <div className="space-y-0.5">
                  {materials.map((m) => (
                    <div
                      key={m.id}
                      className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors cursor-default"
                    >
                      <FileTypeBadge name={m.name} />
                      <span
                        className="flex-1 truncate min-w-0 hover:underline cursor-pointer"
                        onClick={() => handleDownloadMaterial(m)}
                        title={m.name}
                      >{m.name}</span>
                      <MaterialCheckbox
                        checked={isMaterialChecked(m.id)}
                        onToggle={() => handleToggleMaterial(m.id)}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

        </div>

        {/* Bottom: user */}
        {userData && (
          <div className="border-t border-gray-200 p-3 flex items-center gap-2">
            {userData.picture ? (
              <img src={userData.picture} alt={userData.name} className="w-7 h-7 rounded-full border border-gray-200 flex-shrink-0" />
            ) : (
              <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                {(userData.name || userData.username || 'U')[0].toUpperCase()}
              </div>
            )}
            <span className="text-xs text-gray-700 font-medium truncate">{userData.name || userData.username}</span>
          </div>
        )}
      </div>

      {/* ── Drag handle ── */}
      <div
        onMouseDown={handleDragStart}
        className="w-1 flex-shrink-0 cursor-col-resize bg-gray-100 hover:bg-indigo-300 active:bg-indigo-400 transition-colors"
      />

      {/* ── Main chat ── */}
      <div className="flex-1 flex flex-col min-w-0 relative overflow-hidden">

        {/* Chat title header */}
        {activeConv && activeConv !== '__new__' && (() => {
          const activeChat = chats.find((c) => c.id === activeConv);
          if (!activeChat) return null;
          return (
            <div className="flex-shrink-0 px-6 pt-4 pb-2 border-b border-gray-100">
              {editingTitle ? (
                <input
                  ref={titleInputRef}
                  value={titleValue}
                  onChange={(e) => setTitleValue(e.target.value)}
                  onBlur={handleTitleSave}
                  onKeyDown={handleTitleKeyDown}
                  disabled={titleSaving}
                  className="w-full text-sm font-semibold text-gray-900 bg-transparent border-b-2 border-indigo-400 focus:outline-none px-0 py-0.5 disabled:opacity-50"
                  maxLength={500}
                />
              ) : (
                <p
                  role="button"
                  tabIndex={0}
                  className="text-sm font-semibold text-gray-900 truncate cursor-text select-none"
                  title="Double-click to rename"
                  onDoubleClick={handleTitleDoubleClick}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === 'F2') handleTitleDoubleClick(); }}
                >
                  {activeChat.title}
                </p>
              )}
            </div>
          );
        })()}

        {/* Messages */}
        <div className={`flex-1 overflow-y-auto overflow-x-auto px-6 pt-5 pb-20 space-y-6 transition-all duration-200 ${sourcesPanel.open ? 'mr-80' : ''}`}>
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-center">
              <p className="text-base font-semibold text-gray-800">Ask me anything about {course?.title || 'this course'}</p>
              <p className="text-sm text-gray-400 max-w-xs">I can explain concepts, quiz you on the material, summarize lectures, and more.</p>
            </div>
          ) : (
            messages.map((msg, i) => {
              const prevMsg = messages[i - 1];
              const rawHistory = msg.role === 'assistant' ? prevMsg?.reply_history : null;
              const replyHistory = (() => {
                if (!rawHistory) return null;
                if (Array.isArray(rawHistory)) return rawHistory.length ? { back: rawHistory, forward: [] } : null;
                const b = rawHistory.back || [], f = rawHistory.forward || [];
                return b.length || f.length ? { back: b, forward: f } : null;
              })();
              return (
              <MessageBubble
                key={msg.id}
                msg={msg}
                courseName={course?.title}
                userPicture={userData?.picture}
                onCiteClick={msg.role === 'assistant' ? (n) => openSources(msg.id, n) : null}
                isEditing={editingMsgId === msg.id}
                editingContent={editingContent}
                onEditStart={(id, content) => {
                  setEditingMsgId(id);
                  setEditingContent(content || '');
                }}
                onEditChange={setEditingContent}
                onEditSave={() => handleEditMessage(msg.id, editingContent)}
                onEditCancel={() => {
                  setEditingMsgId(null);
                  setEditingContent('');
                }}
                canEdit={msg.role === 'user' && typeof msg.message_index === 'number' && !sending}
                replyHistory={replyHistory}
                onRevert={replyHistory?.back?.length ? handleRevertMessage : null}
                onRestore={replyHistory?.forward?.length ? handleRestoreMessage : null}
                onRegenerate={msg.role === 'assistant' && !sending ? handleRegenerateMessage : null}
                availableModels={availableModels}
              />
              );
            })
          )}
          {sending && (
            <div className="flex items-start">
              <div className="w-10 flex-shrink-0" />
              <div className="flex items-center gap-1 pt-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar - floating overlay */}
        <div className="absolute bottom-0 left-0 right-0 px-4 pb-4 pt-6 bg-gradient-to-t from-white via-white/90 to-transparent">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-gray-200 bg-white hover:shadow-lg focus-within:border-indigo-300 focus-within:shadow-lg transition-all" style={{ boxShadow: '0 4px 24px 0 rgba(0,0,0,0.13)' }}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Reply…"
              rows={1}
              className="flex-1 bg-transparent resize-none text-xs text-gray-800 placeholder-gray-400 focus:outline-none leading-relaxed self-center"
              style={{ maxHeight: '80px', overflowY: 'auto' }}
              onInput={(e) => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 80) + 'px';
              }}
            />
            {/* Model selector */}
            {availableModels.length > 0 && (
              <div className="flex items-center gap-1 flex-shrink-0">
                {/* Provider dropdown */}
                <div className="relative" ref={dropdownRef}>
                  <button
                    type="button"
                    onClick={() => setModelDropdownOpen((o) => !o)}
                    className="flex items-center gap-0.5 text-gray-400 text-xs hover:text-gray-600 transition-colors"
                  >
                    <span>{MODEL_LABELS[selectedModel] || selectedModel}</span>
                    <ChevronDownIcon />
                  </button>
                  {modelDropdownOpen && (
                    <div className="absolute bottom-full right-0 mb-2 bg-gray-900 rounded-xl shadow-xl py-1 min-w-[130px] z-50 border border-gray-700/60">
                      {availableModels.map((provider) => (
                        <button key={provider} type="button" onClick={() => handleModelSelect(provider)}
                          className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left transition-colors rounded-lg hover:bg-gray-700/70">
                          <span className={selectedModel === provider ? 'text-white font-medium' : 'text-gray-300'}>
                            {MODEL_LABELS[provider] || provider}
                          </span>
                          {selectedModel === provider && <span className="text-indigo-400"><CheckIcon /></span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Specific model dropdown */}
                {selectedModel && PROVIDER_MODELS[selectedModel] && (
                  <div className="relative ml-1" ref={modelListDropdownRef}>
                    <button
                      type="button"
                      onClick={() => setModelListDropdownOpen((o) => !o)}
                      className="flex items-center gap-0.5 text-gray-400 text-xs hover:text-gray-600 transition-colors"
                    >
                      <span>{PROVIDER_MODELS[selectedModel]?.find((m) => m.id === selectedModelId)?.label || selectedModelId}</span>
                      <ChevronDownIcon />
                    </button>
                    {modelListDropdownOpen && (
                      <div className="absolute bottom-full right-0 mb-2 bg-gray-900 rounded-xl shadow-xl py-1 min-w-[180px] z-50 border border-gray-700/60 max-h-48 overflow-y-auto">
                        {PROVIDER_MODELS[selectedModel].map((m) => (
                          <button key={m.id} type="button" onClick={() => handleModelIdSelect(m.id)}
                            className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left transition-colors rounded-lg hover:bg-gray-700/70">
                            <span className={selectedModelId === m.id ? 'text-white font-medium' : 'text-gray-300'}>
                              {m.label}
                            </span>
                            {selectedModelId === m.id && <span className="text-indigo-400"><CheckIcon /></span>}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || sending || !selectedModel}
              className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
            >
              <SendIcon />
            </button>
          </div>
          <p className="text-center text-[10px] text-gray-400 mt-1.5">
            AI responses are based on your uploaded course materials.
          </p>
        </div>

        <SourcesPanel
          open={sourcesPanel.open}
          chunks={sourcesPanel.messageId ? msgChunks[sourcesPanel.messageId] : null}
          focusIndex={sourcesPanel.focusIndex}
          onClose={() => setSourcesPanel((p) => ({ ...p, open: false }))}
          materials={materials}
        />
      </div>
    </div>
  );
}
