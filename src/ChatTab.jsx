import { useState, useRef, useEffect } from 'react';
import { formatDateTime, parseUTC } from './utils/dateUtils';
import { getMaterialUrl } from './utils/materialUtils';
import SearchChat from './SearchChat';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
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

function PinIcon({ filled = false }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
      fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="17" x2="12" y2="22" />
      <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z" />
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
    <svg xmlns="http://www.w3.org/2000/svg" width="13.2" height="13.2" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round">
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

function NotionBadgeIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" className="shrink-0">
      <path d="M4 4a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v16a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V4z" opacity=".15"/>
      <rect x="7" y="7" width="10" height="1.5" rx=".75"/>
      <rect x="7" y="11" width="7" height="1.5" rx=".75"/>
      <rect x="7" y="15" width="8" height="1.5" rx=".75"/>
    </svg>
  );
}

function FileTypeBadge({ name, sourceType }) {
  const ext = (name || '').split('.').pop().toLowerCase();
  const mapped = FILE_TYPE_MAP[ext];

  if (!mapped && sourceType === 'notion') {
    return (
      <span className="flex-shrink-0 inline-flex items-center justify-center w-[22px] h-[16px] rounded bg-gray-100 text-gray-600">
        <NotionBadgeIcon />
      </span>
    );
  }

  const style = mapped || { label: ext.slice(0, 3).toUpperCase() || 'DOC', bg: 'bg-gray-100', text: 'text-gray-500' };
  return (
    <span className={`flex-shrink-0 inline-flex items-center justify-center w-[22px] h-[16px] rounded text-[7px] font-bold tracking-tight ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

function MaterialToggle({ checked, onToggle }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
      className={`flex-shrink-0 relative inline-flex h-4 w-7 items-center rounded-full transition-colors focus:outline-none ${
        checked ? 'bg-indigo-500' : 'bg-gray-200'
      }`}
    >
      <span className={`inline-block h-3 w-3 transform rounded-full bg-white shadow-sm transition-transform ${
        checked ? 'translate-x-3.5' : 'translate-x-0.5'
      }`} />
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
    const d = parseUTC(chat.last_message_at || chat.created_at);
    if (d >= todayStart) today.push(chat);
    else if (d >= weekStart) lastWeek.push(chat);
    else older.push(chat);
  }
  return { today, lastWeek, older };
}

function inferProviderFromModelId(modelId) {
  if (!modelId) return null;
  for (const [provider, models] of Object.entries(PROVIDER_MODELS)) {
    if ((models || []).some((m) => m.id === modelId)) return provider;
  }
  return null;
}

function getMessageModelLabel(msg) {
  const modelId = msg?.ai_model || null;
  const provider = msg?.ai_provider || inferProviderFromModelId(modelId);
  if (provider && modelId) {
    const modelLabel = (PROVIDER_MODELS[provider] || []).find((m) => m.id === modelId)?.label;
    if (modelLabel) return modelLabel;
  }
  if (modelId) return modelId;
  if (provider) return MODEL_LABELS[provider] || provider;
  return null;
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
        className="flex-shrink-0 p-0.5 rounded transition-all text-gray-400 hover:text-red-500 hover:bg-red-50"
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
          const downloadUrl = getMaterialUrl(material) || null;
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
                  <span className="text-gray-500 truncate text-[9px]">{material.name}</span>
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
  webSearchUrls,
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
  materials,
  onPin,
  isPinned,
  onFollowUpClick,
  onSkipClarification,
  isLastAssistantMsg,
}) {
  const isUser = msg.role === 'user';
  const modelLabel = getMessageModelLabel(msg);
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
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
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
          table: ({ children }) => (
            <div className="overflow-x-auto mt-2 mb-1">
              <table className="w-full text-xs border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-100 text-gray-700">{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr className="border-b border-gray-200">{children}</tr>,
          th: ({ children }) => <th className="px-3 py-1.5 text-left font-semibold border border-gray-200">{children}</th>,
          td: ({ children }) => <td className="px-3 py-1.5 border border-gray-200">{children}</td>,
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
    return formatDateTime(raw);
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
          {modelLabel ? (
            <>
              <span className="w-1 h-1 rounded-full bg-indigo-300" />
              <span className="text-xs text-gray-400">
                {modelLabel}
              </span>
            </>
          ) : (
            <span className="w-1 h-1 rounded-full bg-indigo-300" />
          )}
        </div>
        <ToolTraceIndicator toolTrace={msg.tool_trace} materials={materials} />
        <div className="text-sm text-gray-700 leading-relaxed space-y-0.5">
          {renderContent(msg.content)}
        </div>
        {webSearchUrls && webSearchUrls.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {webSearchUrls.map((item, idx) => {
              let hostname = item.url;
              try { hostname = new URL(item.url).hostname.replace(/^www\./, ''); } catch {}
              return (
                <a
                  key={idx}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={item.title || item.url}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-teal-50 text-teal-700 border border-teal-200 hover:bg-teal-100 hover:border-teal-300 transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                  </svg>
                  {hostname}
                  <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                  </svg>
                </a>
              );
            })}
          </div>
        )}
        {isLastAssistantMsg && msg.is_clarification_request && !msg.clarification_skipped && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-xs font-medium text-amber-700 mb-1">Clarifying question</p>
            <p className="text-sm text-amber-900">{msg.clarification_question}</p>
            <button
              type="button"
              onClick={() => onSkipClarification && onSkipClarification()}
              className="mt-2 inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-amber-300 text-amber-700 bg-white hover:bg-amber-100 transition-colors"
            >
              Skip clarification
            </button>
          </div>
        )}
        {Array.isArray(msg.follow_ups) && msg.follow_ups.length > 0 && !(msg.is_clarification_request && !msg.clarification_skipped) && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {isLastAssistantMsg && msg.is_clarification_request && msg.clarification_skipped && (
              <p className="w-full text-xs text-gray-500 mb-0.5">Would you like to discuss any of these further?</p>
            )}
            {msg.follow_ups.map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onFollowUpClick && onFollowUpClick(q)}
                className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-indigo-200 text-indigo-600 bg-white hover:bg-indigo-50 hover:border-indigo-300 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-1 mt-3">
          {onPin && (
            <button
              type="button"
              onClick={onPin}
              className={`p-1.5 rounded-lg transition-colors ${isPinned ? 'text-indigo-600 bg-indigo-50' : 'text-gray-400 hover:text-indigo-600 hover:bg-indigo-50'}`}
              title={isPinned ? 'Unpin' : 'Pin response'}
            >
              <PinIcon filled={isPinned} />
            </button>
          )}
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

// ─── streaming status bubble ──────────────────────────────────────────────────

function getTracePrimary(status) {
  switch (status.phase) {
    case 'handoff_decision': {
      const rec = status.recommendation || 'optional';
      const confPct = Number.isFinite(Number(status.confidence))
        ? `${Math.round(Number(status.confidence) * 100)}%`
        : 'unknown';
      if (status.override) return `Handoff says "${rec}" at ${confPct} confidence — override enabled, web search remains available`;
      if (status.web_search_allowed === false) return `Handoff says "${rec}" at ${confPct} confidence — web search constrained unless strong contradiction appears`;
      return `Handoff says "${rec}" at ${confPct} confidence — web search can be used if needed`;
    }
    case 'loop_start':
      return `Agentic pass ${status.iteration}${status.maxIteration ? ` of ${status.maxIteration}` : ''}: evaluating evidence and tool options`;
    case 'sources_found':
      return `Retrieved ${status.result_count || 0} course chunks and grounding context`;
    case 'web_search_start':
      return 'Running web search for external coverage and implementation details';
    case 'web_result':
      return `Inspecting web result from ${status.hostname || 'source'}`;
    case 'rerank':
      return `Re-ranking candidate chunks by relevance (${status.input_count || '?'} → ${status.output_count || '?'})`;
    default:
      return 'Initializing retrieval and planning tool steps…';
  }
}

function getTraceSecondary(status, materialMap) {
  switch (status.phase) {
    case 'sources_found': {
      const chunks = status.chunks || [];
      if (!chunks.length) return null;
      const parts = chunks.map((c) => {
        const mat = c.material_id != null ? (materialMap || {})[c.material_id] : null;
        const name = mat?.name ? mat.name.replace(/\.[^.]+$/, '').slice(0, 20) : null;
        return name ? `${name} — "${c.snippet}"` : `"${c.snippet}"`;
      });
      return parts.join('  ·  ');
    }
    case 'web_search_start':
      return status.query ? `"${status.query.slice(0, 60)}"` : null;
    case 'web_result':
      return status.excerpt ? `"${status.excerpt}"` : null;
    case 'handoff_decision': {
      const details = [];
      if (status.override) details.push(`Guardrail override: confidence ${status.confidence ?? '?'} below threshold ${status.threshold ?? '?'}`);
      else if (status.recommendation === 'not_needed') details.push(`High-confidence no-search recommendation (threshold ${status.threshold ?? '?'})`);
      if (Array.isArray(status.missing_facts) && status.missing_facts.length) details.push(`Possible gaps: ${status.missing_facts.slice(0, 2).join(' · ')}`);
      if (Array.isArray(status.suggested_queries) && status.suggested_queries.length) details.push(`Candidate queries: ${status.suggested_queries.slice(0, 2).join(' | ')}`);
      if (!details.length && status.reasoning) details.push(status.reasoning);
      return details.join('  ·  ') || null;
    }
    default:
      return null;
  }
}

function toolTraceToEvents(toolTrace) {
  const events = [];
  const seenIterations = new Set();
  for (const entry of (toolTrace || [])) {
    if (entry.iteration != null && !seenIterations.has(entry.iteration)) {
      seenIterations.add(entry.iteration);
      events.push({ phase: 'loop_start', iteration: entry.iteration, maxIteration: null });
    }
    if (entry.tool === 'search_materials') {
      events.push({ phase: 'sources_found', result_count: entry.result_count || 0, chunks: [] });
    } else if (entry.tool === 'web_search') {
      events.push({ phase: 'web_search_start', query: '' });
      for (const u of (entry.urls || [])) {
        let hostname = u.url || '';
        try { hostname = new URL(u.url).hostname.replace(/^www\./, ''); } catch {}
        events.push({ phase: 'web_result', url: u.url, hostname, excerpt: u.title || '' });
      }
    } else if (entry.tool === 'rerank_results') {
      events.push({ phase: 'rerank', input_count: entry.result_count, output_count: entry.result_count });
    }
  }
  return events;
}

function ToolTraceIndicator({ toolTrace, materials }) {
  const [open, setOpen] = useState(false);
  const events = toolTraceToEvents(toolTrace);
  if (!events.length) return null;
  const materialMap = {};
  (materials || []).forEach((m) => { materialMap[m.id] = m; });
  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[11px] text-indigo-400 hover:text-indigo-600 transition-colors select-none"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-70"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
        <span>{events.length} reasoning steps</span>
        <span className="opacity-50">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-1.5 pl-1 border-l-2 border-indigo-100">
          {events.map((s, i) => {
            const secondary = getTraceSecondary(s, materialMap);
            return (
              <div key={i} className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-200 mt-1 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-[11px] text-indigo-500 leading-snug">{getTracePrimary(s)}</p>
                  {secondary && <p className="text-[10px] text-indigo-300 leading-snug truncate">{secondary}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StreamingHistoryBubble({ history, materials }) {
  const materialMap = {};
  (materials || []).forEach((m) => { materialMap[m.id] = m; });
  const items = (history || []).filter((s) => s.phase !== 'init');

  if (!items.length) {
    return (
      <div className="flex items-start">
        <div className="w-10 flex-shrink-0" />
        <div className="flex items-center gap-1 pt-2">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start">
      <div className="w-10 flex-shrink-0" />
      <div className="flex-1 flex flex-col gap-1.5 px-4 py-3 rounded-xl bg-indigo-50 border border-indigo-100">
        {items.map((s, i) => {
          const isLast = i === items.length - 1;
          const secondary = getTraceSecondary(s, materialMap);
          return (
            <div key={i} className="flex items-start gap-2">
              <span className={`w-2 h-2 rounded-full mt-0.5 flex-shrink-0 ${isLast ? 'bg-indigo-400 animate-pulse' : 'bg-indigo-200'}`} />
              <div className="min-w-0">
                <p className={`text-xs font-medium leading-snug ${isLast ? 'text-indigo-700' : 'text-indigo-400'}`}>{getTracePrimary(s)}</p>
                {secondary && <p className="text-[11px] text-indigo-300 leading-snug truncate">{secondary}</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── pins panel ──────────────────────────────────────────────────────────────

function PinsPanel({ pins, courseName, userData, materials, onDeletePin }) {
  const [expandedPin, setExpandedPin] = useState(null);

  return (
    <div className="flex-shrink-0 bg-white overflow-hidden" style={{ maxHeight: '220px' }}>
      {/* Header */}
      <div className="px-6 py-2 flex items-center gap-2 flex-shrink-0 border-b border-gray-100">
        <span className="text-indigo-500"><PinIcon filled /></span>
        <span className="text-xs font-semibold text-gray-700">Saved Pins</span>
        {pins.length > 0 && (
          <span className="px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-600 text-[10px] font-semibold">{pins.length}</span>
        )}
      </div>

      {/* List */}
      <div className="overflow-y-auto" style={{ maxHeight: '180px' }}>
        {pins.length === 0 && (
          <p className="px-6 py-2 text-xs text-gray-400 italic">No saved pins yet.</p>
        )}
        {pins.map((pin) => {
          const isExpanded = expandedPin === pin.id;
          const pinDate = pin.pinned_at ? formatDateTime(pin.pinned_at) : '';
          return (
            <div key={pin.id}>
              {/* Row */}
              <div className="flex items-center group hover:bg-gray-50 transition-colors">
              <button
                type="button"
                onClick={() => setExpandedPin(isExpanded ? null : pin.id)}
                className={`flex-1 flex gap-2 px-6 py-1.5 text-left min-w-0 ${
                  isExpanded ? 'items-start py-2' : 'items-center'
                }`}
              >
                {isExpanded ? (
                  <>
                    <span className="flex-1 min-w-0 text-[11px] font-medium text-gray-700 whitespace-normal break-words text-left">
                      {pin.chat_title || 'Chat'}
                    </span>
                    <span className="text-[10px] text-gray-400 flex-shrink-0 ml-1">{pinDate}</span>
                    <span className="flex-shrink-0 text-gray-400 transition-transform duration-200 rotate-180 mt-0.5">
                      <ChevronDownIcon />
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-[11px] font-medium text-gray-700 truncate max-w-[240px] flex-shrink-0">{pin.chat_title || 'Chat'}</span>
                    <span className="text-[10px] text-gray-300">·</span>
                    <span className="text-[10px] text-gray-500 truncate max-w-[200px] flex-shrink-0">{pin.assistant_message?.ai_model || ''}</span>
                    <span className="text-[10px] text-gray-300">·</span>
                    <span className="text-[10px] text-gray-600 flex-1 truncate">{pin.ai_summary}</span>
                    <span className="text-[10px] text-gray-400 flex-shrink-0 ml-1">{pinDate}</span>
                    <span className="flex-shrink-0 text-gray-400 transition-transform duration-200">
                      <ChevronDownIcon />
                    </span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => onDeletePin && onDeletePin(pin)}
                className="flex-shrink-0 pl-1 pr-2.5 py-1.5 text-gray-400 hover:text-red-500 transition-colors"
                aria-label="Delete pin"
              >
                <TrashIcon />
              </button>
              </div>

              {/* Expanded card */}
              {isExpanded && pin.user_message && pin.assistant_message && (
                <div className="px-4 pb-3 pt-1 space-y-3 bg-gray-50 border-t border-gray-100">
                  <MessageBubble
                    msg={pin.user_message}
                    courseName={courseName}
                    userPicture={userData?.picture}
                    onCiteClick={null}
                    webSearchUrls={null}
                    isEditing={false}
                    editingContent=""
                    onEditStart={null}
                    onEditChange={null}
                    onEditSave={null}
                    onEditCancel={null}
                    canEdit={false}
                    replyHistory={null}
                    onRevert={null}
                    onRestore={null}
                    onRegenerate={null}
                    availableModels={[]}
                    materials={materials}
                    onPin={null}
                    isPinned={false}
                  />
                  <MessageBubble
                    msg={pin.assistant_message}
                    courseName={courseName}
                    userPicture={userData?.picture}
                    onCiteClick={null}
                    webSearchUrls={null}
                    isEditing={false}
                    editingContent=""
                    onEditStart={null}
                    onEditChange={null}
                    onEditSave={null}
                    onEditCancel={null}
                    canEdit={false}
                    replyHistory={null}
                    onRevert={null}
                    onRestore={null}
                    onRegenerate={null}
                    availableModels={[]}
                    materials={materials}
                    onPin={null}
                    isPinned={false}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

/** Max height (px) for the composer textarea before it scrolls internally. */
const CHAT_COMPOSER_MAX_HEIGHT_PX = 280;
/** Min height (px) — matches the send row (~h-6) so single-line text isn’t short vs controls. */
const CHAT_COMPOSER_MIN_HEIGHT_PX = 24;

export default function ChatTab({ course, userData, onAddSource }) {
  const [activeConv, setActiveConv] = useState(null);
  const [chats, setChats] = useState([]);
  const [chatsLoading, setChatsLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [archivedChats, setArchivedChats] = useState([]);
  const [archivedOpen, setArchivedOpen] = useState(false);
  const [archivedLoading, setArchivedLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  // null = idle; { phase, detail, iteration, maxIteration } = streaming in progress
  const [streamingHistory, setStreamingHistory] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [selectedModelId, setSelectedModelId] = useState(null);
  const [modelListDropdownOpen, setModelListDropdownOpen] = useState(false);
  const [switchBanner, setSwitchBanner] = useState('');
  const [pinnedResponses, setPinnedResponses] = useState([]);
  const [pinToast, setPinToast] = useState('');
  const pinToastTimerRef = useRef(null);
  const [materials, setMaterials] = useState([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState('');
  const [titleSaving, setTitleSaving] = useState(false);
  const [editingMsgId, setEditingMsgId] = useState(null);
  const [editingContent, setEditingContent] = useState('');
  const [msgChunks, setMsgChunks] = useState({});
  const [sourcesPanel, setSourcesPanel] = useState({ open: false, messageId: null, focusIndex: null });
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const h = Math.min(
      Math.max(el.scrollHeight, CHAT_COMPOSER_MIN_HEIGHT_PX),
      CHAT_COMPOSER_MAX_HEIGHT_PX,
    );
    el.style.height = `${h}px`;
  }, [input]);
  const dropdownRef = useRef(null);
  const modelListDropdownRef = useRef(null);
  const titleInputRef = useRef(null);
  const bannerTimerRef = useRef(null);
  const sendingRef = useRef(false);

  // Sidebar resize / collapse
  const SIDEBAR_DEFAULT_WIDTH = 280;
  const SIDEBAR_MIN_WIDTH = 220;
  const SIDEBAR_MAX_WIDTH = 360;
  const SIDEBAR_COLLAPSE_THRESHOLD = 160;
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const sidebarLastExpandedWidthRef = useRef(SIDEBAR_DEFAULT_WIDTH);
  const sidebarIsDraggingRef = useRef(false);
  const sidebarDragStartXRef = useRef(0);
  const sidebarDragStartWidthRef = useRef(SIDEBAR_DEFAULT_WIDTH);

  function handleSidebarRestore() {
    setSidebarCollapsed(false);
    // Restore in two steps: snap to min width then animate to last width
    const target = Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, sidebarLastExpandedWidthRef.current || SIDEBAR_DEFAULT_WIDTH));
    setSidebarWidth(SIDEBAR_MIN_WIDTH);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setSidebarWidth(target));
    });
  }

  function startSidebarDrag(e) {
    e.preventDefault();
    e.stopPropagation();
    sidebarIsDraggingRef.current = true;
    sidebarDragStartXRef.current = e.clientX;
    sidebarDragStartWidthRef.current = sidebarWidth;

    const onMove = (ev) => {
      if (!sidebarIsDraggingRef.current) return;
      const dx = ev.clientX - sidebarDragStartXRef.current;
      const next = sidebarDragStartWidthRef.current + dx;

      if (next <= SIDEBAR_COLLAPSE_THRESHOLD) {
        setSidebarCollapsed(true);
        return;
      }

      setSidebarCollapsed(false);
      const clamped = Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, next));
      sidebarLastExpandedWidthRef.current = clamped;
      setSidebarWidth(clamped);
    };

    const onUp = () => {
      sidebarIsDraggingRef.current = false;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);

      // If we ended collapsed, remember last expanded width and hide sidebar
      if (sidebarCollapsed) {
        sidebarLastExpandedWidthRef.current = Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, sidebarWidth));
      }
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load materials for this course
  useEffect(() => {
    if (!course?.id) return;
    setMaterialsLoading(true);
    fetch(`/api/material?action=selections&course_id=${course.id}&context=chat`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {})
      .finally(() => setMaterialsLoading(false));
  }, [course?.id]);

  // Load chats for this course
  useEffect(() => {
    if (!course?.id) return;
    setChatsLoading(true);
    fetch(`/api/chat?resource=chat&course_id=${course.id}`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setChats(data.chats || []))
      .catch(() => {})
      .finally(() => setChatsLoading(false));
  }, [course?.id]);

  // Load pinned responses for this course
  useEffect(() => {
    if (!course?.id) return;
    fetch(`/api/chat?resource=pin&course_id=${course.id}`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => setPinnedResponses(data.pins || []))
      .catch(() => {});
  }, [course?.id]);

  // Fetch archived chats when the archived dropdown is opened
  useEffect(() => {
    if (!archivedOpen || !course?.id) return;
    setArchivedLoading(true);
    fetch(`/api/chat?resource=chat&course_id=${course.id}&archived=true`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setArchivedChats(data.chats || []))
      .catch(() => {})
      .finally(() => setArchivedLoading(false));
  }, [archivedOpen, course?.id]);

  // Load messages when active conversation changes
  useEffect(() => {
    if (!activeConv || activeConv === '__new__') return;
    if (sendingRef.current) return;
    fetch(`/api/chat?resource=message&chat_id=${activeConv}`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setMessages(data.messages || []))
      .catch(() => {});
  }, [activeConv]);

  // Load available API-key-backed models
  useEffect(() => {
    fetch('/api/user?resource=api_keys', {
      credentials: 'include',
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
  }, []);

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

  async function persistMaterialSelection(material, selected) {
    if (!course?.id || !material?.id) return;
    try {
      await fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          action: 'set_selection',
          material_id: material.id,
          course_id: course.id,
          context: 'chat',
          selected,
          provider: material.source_type === 'notion' ? 'notion' : null,
        }),
      });
    } catch {}
  }

  function handleSelectAllMaterials() {
    const allOn = materials.length > 0 && materials.every((m) => m.selected);
    const newVal = !allOn;
    const nextMaterials = materials.map((m) => ({ ...m, selected: newVal }));
    setMaterials(nextMaterials);
    nextMaterials.forEach((m) => {
      persistMaterialSelection(m, newVal);
    });
  }

  function setAllMaterialsSelected(selected) {
    const nextMaterials = materials.map((m) => ({ ...m, selected }));
    setMaterials(nextMaterials);
    nextMaterials.forEach((m) => {
      persistMaterialSelection(m, selected);
    });
  }

  function handleToggleMaterial(id) {
    setMaterials((prev) => prev.map((m) => {
      if (m.id !== id) return m;
      const updated = { ...m, selected: !m.selected };
      persistMaterialSelection(m, updated.selected);
      return updated;
    }));
  }

  function handleOpenMaterial(m) {
    const url = getMaterialUrl(m);
    if (!url) return;
    window.open(url, '_blank', 'noopener,noreferrer');
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
          'Content-Type': 'application/json',
        },
        credentials: 'include',
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
          'Content-Type': 'application/json',
        },
        credentials: 'include',
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
          'Content-Type': 'application/json',
        },
        credentials: 'include',
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
          'Content-Type': 'application/json',
        },
        credentials: 'include',
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

  async function handleDeletePin(pin) {
    try {
      const r = await fetch('/api/chat', {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resource: 'pin', assistant_message_id: pin.assistant_message_id }),
      });
      if (!r.ok) return;
      setPinnedResponses((prev) => prev.filter((p) => p.assistant_message_id !== pin.assistant_message_id));
    } catch {
      // ignore network errors
    }
  }

  async function handlePinMessage(assistantMsg, userMsg) {
    const isCurrentlyPinned = pinnedResponses.some((p) => p.assistant_message_id === assistantMsg.id);
    const action = isCurrentlyPinned ? 'unpin' : 'pin';

    setPinToast(action === 'pin' ? 'Saving…' : 'Pin removed');
    if (pinToastTimerRef.current) clearTimeout(pinToastTimerRef.current);
    pinToastTimerRef.current = setTimeout(() => setPinToast(''), 1500);

    const body = action === 'pin'
      ? { resource: 'pin', action: 'pin', user_message_id: userMsg.id, assistant_message_id: assistantMsg.id, course_id: course.id, chat_id: activeConv }
      : { resource: 'pin', action: 'unpin', assistant_message_id: assistantMsg.id };

    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) return;
      const responseData = await r.json();
      if (action === 'pin' && responseData.pin) {
        const chatTitle = chats.find((c) => c.id === activeConv)?.title || 'Chat';
        setPinnedResponses((prev) => [
          {
            id: responseData.pin?.id,
            user_message_id: userMsg.id,
            assistant_message_id: assistantMsg.id,
            course_id: course.id,
            chat_id: activeConv,
            ai_summary: assistantMsg.summary || '',
            pinned_at: responseData.pin?.pinned_at,
            chat_title: chatTitle,
            user_message: userMsg,
            assistant_message: assistantMsg,
          },
          ...prev,
        ]);
      } else if (responseData.deleted) {
        setPinnedResponses((prev) => prev.filter((p) => p.assistant_message_id !== assistantMsg.id));
      }
    } catch {}
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
          'Content-Type': 'application/json',
        },
        credentials: 'include',
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
        credentials: 'include',
      })
        .then((r) => r.json())
        .then((data) => setMsgChunks((prev) => ({ ...prev, [messageId]: data.chunks || [] })))
        .catch(() => {});
    }
    setSourcesPanel({ open: true, messageId, focusIndex });
    setSidebarWidth(0);
  }

  function handleStreamEvent(evt, { tempId, chatId, setActiveConvFn }) {
    switch (evt.type) {
      case 'handoff_decision':
        setStreamingHistory((prev) => [...prev, {
          phase: 'handoff_decision',
          recommendation: evt.recommendation || 'optional',
          confidence: evt.confidence,
          threshold: evt.threshold,
          override: Boolean(evt.override),
          web_search_allowed: evt.web_search_allowed,
          missing_facts: Array.isArray(evt.missing_facts) ? evt.missing_facts : [],
          suggested_queries: Array.isArray(evt.suggested_queries) ? evt.suggested_queries : [],
          reasoning: evt.reasoning || '',
        }]);
        break;
      case 'user_message':
        setMessages((prev) => [...prev.filter((m) => m.id !== tempId), evt.message]);
        break;
      case 'loop_start':
        setStreamingHistory((prev) => [...prev, { phase: 'loop_start', iteration: evt.iteration, maxIteration: evt.max }]);
        break;
      case 'sources_found':
        setStreamingHistory((prev) => [...prev, { phase: 'sources_found', chunks: evt.chunks || [], result_count: evt.result_count || 0 }]);
        break;
      case 'web_search_start':
        setStreamingHistory((prev) => [...prev, { phase: 'web_search_start', query: evt.query || '' }]);
        break;
      case 'web_result': {
        let hostname = evt.url || '';
        try { hostname = new URL(evt.url).hostname.replace(/^www\./, ''); } catch {}
        setStreamingHistory((prev) => [...prev, { phase: 'web_result', url: evt.url, hostname, excerpt: (evt.excerpt || '').slice(0, 80) }]);
        break;
      }
      case 'rerank':
        setStreamingHistory((prev) => [...prev, { phase: 'rerank', input_count: evt.input_count, output_count: evt.output_count }]);
        break;
      case 'done':
        setStreamingHistory([]);
        setMessages((prev) => {
          const withoutTemp = prev.filter((m) => m.id !== tempId && m.id !== evt.user_message?.id);
          return [...withoutTemp, evt.user_message, evt.assistant_message];
        });
        setChats((prev) => prev.map((c) =>
          c.id === chatId
            ? {
                ...c,
                last_message_at: evt.assistant_message?.created_at,
                message_count: (c.message_count || 0) + 2,
                ...(evt.suggested_title ? { title: evt.suggested_title } : {}),
              }
            : c
        ));
        setSending(false);
        sendingRef.current = false;
        break;
      case 'error':
        setStreamingHistory([]);
        setSending(false);
        sendingRef.current = false;
        setMessages((prev) => prev.filter((m) => m.id !== tempId));
        break;
      default:
        break;
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || sending || !selectedModel) return;
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setSending(true);
    sendingRef.current = true;
    setStreamingHistory([{ phase: 'init' }]);

    const tempId = Date.now();
    const tempUserMsg = { id: tempId, role: 'user', content: text };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      let chatId = activeConv;

      // Create a chat thread if none exists or if this is the optimistic temp entry
      if (!chatId || chatId === '__new__') {
        const title = 'New Chat';
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify({ resource: 'chat', action: 'create', course_id: course.id, title }),
        });
        const chatData = await res.json();
        if (!res.ok) throw new Error(chatData.error || 'Failed to create chat');
        chatId = chatData.chat.id;
        setActiveConv(chatId);
        setChats((prev) => [chatData.chat, ...prev.filter((c) => c.id !== '__new__')]);
      }

      const contextIds = materials.filter((m) => m.selected).map((m) => m.id);

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          resource: 'message',
          action: 'stream_send',
          chat_id: chatId,
          content: text,
          context_material_ids: contextIds,
          ai_provider: selectedModel,
          ai_model: selectedModelId || selectedModel,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to send message');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      // scheduledDelay accumulates when events arrive batched in the same read()
      // so each phase is visible for 400ms. Resets to 0 when a read() returns only
      // non-phase events, meaning the stream is actually progressive.
      let scheduledDelay = 0;
      const PHASE_EVENTS = new Set(['handoff_decision', 'loop_start', 'sources_found', 'web_search_start', 'web_result', 'rerank']);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(part.slice(6));
            const delay = scheduledDelay;
            setTimeout(() => handleStreamEvent(evt, { tempId, chatId }), delay);
            if (PHASE_EVENTS.has(evt.type)) scheduledDelay += 400;
          } catch {}
        }
      }
    } catch {
      setStreamingHistory([]);
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleEditMessage(messageId, newContent) {
    const trimmed = (newContent || '').trim();
    if (!trimmed || sending || !selectedModel) return;
    const target = messages.find((m) => m.id === messageId);
    if (!target || target.role !== 'user' || typeof target.message_index !== 'number') return;

    const contextIds = materials.filter((m) => m.selected).map((m) => m.id);

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const cutoffIndex = target.message_index;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < cutoffIndex);
    const optimisticEdited = { ...target, content: trimmed, is_edited: true };

    setEditingMsgId(null);
    setEditingContent('');
    setSending(true);
    sendingRef.current = true;
    setStreamingHistory([{ phase: 'init' }]);
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });
    setMessages([...keptPrefix, optimisticEdited]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          resource: 'message',
          action: 'stream_edit',
          message_id: messageId,
          content: trimmed,
          context_material_ids: contextIds,
          ai_provider: selectedModel,
          ai_model: selectedModelId || selectedModel,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to edit message');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let scheduledDelay = 0;
      const PHASE_EVENTS = new Set(['handoff_decision', 'loop_start', 'sources_found', 'web_search_start', 'web_result', 'rerank']);

      let editDoneReceived = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(part.slice(6));
            const delay = scheduledDelay;
            setTimeout(() => {
              if (evt.type === 'done') {
                editDoneReceived = true;
                setStreamingHistory([]);
                const nextMessages = [...keptPrefix, evt.user_message, evt.assistant_message];
                setMessages(nextMessages);
                setMsgChunks((prev) => {
                  const keptIds = new Set(nextMessages.map((m) => m.id));
                  return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
                });
                setChats((prev) => prev.map((c) =>
                  c.id === target.chat_id
                    ? {
                        ...c,
                        last_message_at: evt.assistant_message?.created_at,
                        message_count: nextMessages.length,
                        ...(evt.suggested_title ? { title: evt.suggested_title } : {}),
                      }
                    : c
                ));
                setSending(false);
                sendingRef.current = false;
              } else if (evt.type === 'error') {
                editDoneReceived = true;
                setStreamingHistory([]);
                setMessages(prevMessages);
                setMsgChunks(prevMsgChunks);
                setSending(false);
                sendingRef.current = false;
              } else {
                handleStreamEvent(evt, { tempId: null, chatId: target.chat_id });
              }
            }, delay);
            if (PHASE_EVENTS.has(evt.type)) scheduledDelay += 400;
          } catch {}
        }
      }
      if (!editDoneReceived) {
        setStreamingHistory([]);
        setMessages(prevMessages);
        setMsgChunks(prevMsgChunks);
        setSending(false);
        sendingRef.current = false;
      }
    } catch {
      setStreamingHistory([]);
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
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
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ resource: 'message', action: 'revert', message_id: assistantMsgId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to revert');

      const newAsst = data.assistant_message;
      const nextMessages = [...keptPrefix, data.user_message, newAsst];
      const displayedIds = new Set(nextMessages.map((m) => m.id));
      // Synchronously update pin state alongside messages so both render in the same pass.
      // Remove pins for messages no longer displayed; add a minimal entry if the new row is pinned.
      setPinnedResponses((prev) => {
        const kept = prev.filter((p) => displayedIds.has(p.assistant_message_id));
        return newAsst.is_pinned ? [...kept, { assistant_message_id: newAsst.id }] : kept;
      });
      setMessages(nextMessages);
      setMsgChunks((prev) => {
        const keptIds = new Set(nextMessages.map((m) => m.id));
        return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
      });
      // Background re-fetch replaces the minimal pin entry with the full object for PinsPanel.
      fetch(`/api/chat?resource=pin&course_id=${course.id}`, { credentials: 'include' })
        .then((r) => r.json())
        .then((d) => setPinnedResponses(d.pins || []))
        .catch(() => {});
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
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ resource: 'message', action: 'restore', message_id: assistantMsgId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to restore');

      const newAsst = data.assistant_message;
      const nextMessages = [...keptPrefix, data.user_message, newAsst];
      const displayedIds = new Set(nextMessages.map((m) => m.id));
      // Synchronously update pin state alongside messages so both render in the same pass.
      setPinnedResponses((prev) => {
        const kept = prev.filter((p) => displayedIds.has(p.assistant_message_id));
        return newAsst.is_pinned ? [...kept, { assistant_message_id: newAsst.id }] : kept;
      });
      setMessages(nextMessages);
      setMsgChunks((prev) => {
        const keptIds = new Set(nextMessages.map((m) => m.id));
        return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
      });
      // Background re-fetch replaces the minimal pin entry with the full object for PinsPanel.
      fetch(`/api/chat?resource=pin&course_id=${course.id}`, { credentials: 'include' })
        .then((r) => r.json())
        .then((d) => setPinnedResponses(d.pins || []))
        .catch(() => {});
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
    setStreamingHistory([{ phase: 'init' }]);
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          resource: 'message',
          action: 'stream_regenerate',
          message_id: assistantMsgId,
          ai_provider: provider,
          ai_model: modelId,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to regenerate');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let scheduledDelay = 0;
      const PHASE_EVENTS = new Set(['handoff_decision', 'loop_start', 'sources_found', 'web_search_start', 'web_result', 'rerank']);

      let regenDoneReceived = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(part.slice(6));
            const delay = scheduledDelay;
            setTimeout(() => {
              if (evt.type === 'done') {
                regenDoneReceived = true;
                setStreamingHistory([]);
                const nextMessages = [...keptPrefix, evt.user_message, evt.assistant_message];
                setMessages(nextMessages);
                setMsgChunks((prev) => {
                  const keptIds = new Set(nextMessages.map((m) => m.id));
                  return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
                });
                if (evt.suggested_title) {
                  setChats((prev) => prev.map((c) =>
                    c.id === (userMsg.chat_id || assistantMsg.chat_id)
                      ? { ...c, title: evt.suggested_title }
                      : c
                  ));
                }
                setSending(false);
                sendingRef.current = false;
              } else if (evt.type === 'error') {
                regenDoneReceived = true;
                setStreamingHistory([]);
                setMessages(prevMessages);
                setMsgChunks(prevMsgChunks);
                setSending(false);
                sendingRef.current = false;
              } else {
                handleStreamEvent(evt, { tempId: null, chatId: userMsg.chat_id });
              }
            }, delay);
            if (PHASE_EVENTS.has(evt.type)) scheduledDelay += 400;
          } catch {}
        }
      }
      if (!regenDoneReceived) {
        setStreamingHistory([]);
        setMessages(prevMessages);
        setMsgChunks(prevMsgChunks);
        setSending(false);
        sendingRef.current = false;
      }
    } catch {
      setStreamingHistory([]);
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleSkipClarification(messageId) {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          resource: 'message',
          action: 'clarification_skip',
          message_id: messageId,
        }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.message) {
        setMessages((prev) =>
          prev.map((m) => (m.id === messageId ? { ...m, ...data.message } : m))
        );
      }
    } catch {
      // silently ignore
    }
  }

  const { today, lastWeek, older } = groupChatsByDate(chats);

  return (
    <div className="flex flex-col gap-4">
    <div className="relative flex gap-4" style={{ height: '68vh', minHeight: '520px' }}>

      {/* Switched-to banner — centred over the full modal */}
      {switchBanner && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-4 py-1.5 rounded-full bg-gray-900 text-white text-xs font-medium shadow-lg whitespace-nowrap pointer-events-none select-none">
          Switched to {switchBanner} ⚡
        </div>
      )}

      {/* Pin toast */}
      {pinToast && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-4 py-1.5 rounded-full bg-gray-900 text-white text-xs font-medium shadow-lg whitespace-nowrap pointer-events-none select-none">
          {pinToast}
        </div>
      )}

      {/* ── Sidebar ── */}
      {!sidebarCollapsed ? (
        <div
          className={`flex-shrink-0 bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col overflow-hidden relative ${
            sidebarIsDraggingRef.current ? '' : 'transition-[width] duration-200'
          }`}
          style={{ width: sidebarWidth }}
        >
          {/* Drag handle (right edge) */}
          <div
            role="separator"
            aria-orientation="vertical"
            title="Drag to resize"
            onPointerDown={startSidebarDrag}
            className="absolute top-2 bottom-2 -right-2 w-4 cursor-col-resize z-20"
          >
            <div className="absolute right-2 top-0 bottom-0 w-px bg-gray-200" />
          </div>
        {/* Logo / title */}
        <div className="px-4 py-3 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-gray-900 text-sm">Course Chat</span>
            <button
              type="button"
              className="flex-shrink-0 p-1.5 text-gray-600 hover:text-indigo-600 hover:bg-gray-50 rounded-lg transition-colors"
              title="Search"
              onClick={() => setSearchOpen(true)}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </button>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={handleNewChat}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors shadow-sm"
            >
              <PlusIcon />
              New chat
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
                className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider hover:text-gray-600 transition-colors rounded-lg hover:bg-gray-50"
              >
                <span>Archived</span>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ transform: archivedOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
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
            <div className="px-3 py-2 flex items-center justify-between">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Your Materials</span>
              {materials.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-400 tabular-nums">
                    {materials.filter((m) => m.selected).length} selected
                  </span>
                  <button
                    type="button"
                    onClick={() => setAllMaterialsSelected(true)}
                    className="text-[10px] font-medium text-indigo-500 hover:text-indigo-700 transition-colors"
                  >
                    All
                  </button>
                  <button
                    type="button"
                    onClick={() => setAllMaterialsSelected(false)}
                    className="text-[10px] font-medium text-gray-500 hover:text-gray-700 transition-colors"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>

            {/* Materials list */}
            <div className="flex-1 overflow-y-auto pb-2">
              {materialsLoading && (
                <p className="px-3 py-2 text-[10px] text-gray-400">Loading…</p>
              )}
              {!materialsLoading && materials.length === 0 ? (
                <p className="px-3 py-2 text-[10px] text-gray-400 italic">No materials uploaded yet.</p>
              ) : (
                (() => {
                  const myMats = materials.filter((m) => !m.collaborator);
                  const collabMats = materials.filter((m) => m.collaborator);
                  return (
                    <div className="space-y-0.5">
                      {myMats.map((m) => (
                        <div
                          key={m.id}
                          className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors cursor-default border-l-2 ${
                            m.selected ? 'border-indigo-400' : 'border-transparent'
                          }`}
                        >
                          <FileTypeBadge name={m.name} sourceType={m.source_type} />
                          <span
                            className="flex-1 truncate min-w-0 hover:underline cursor-pointer"
                            onClick={() => handleOpenMaterial(m)}
                          >{m.name}</span>
                          <MaterialToggle checked={m.selected} onToggle={() => handleToggleMaterial(m.id)} />
                        </div>
                      ))}
                      {collabMats.length > 0 && (
                        <>
                          <div className="px-3 pt-2 pb-0.5">
                            <span className="text-[9px] font-semibold text-gray-300 uppercase tracking-wider">From collaborators</span>
                          </div>
                          {collabMats.map((m) => (
                            <div
                              key={m.id}
                              className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-500 hover:bg-gray-100 transition-colors cursor-default border-l-2 ${
                                m.selected ? 'border-indigo-300' : 'border-transparent'
                              }`}
                            >
                              <FileTypeBadge name={m.name} sourceType={m.source_type} />
                              <span
                                className="flex-1 truncate min-w-0 hover:underline cursor-pointer"
                                onClick={() => handleOpenMaterial(m)}
                              >{m.name}</span>
                              <MaterialToggle checked={m.selected} onToggle={() => handleToggleMaterial(m.id)} />
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  );
                })()
              )}
            </div>

            {/* Add Source button */}
            <div className="px-3 pb-3 pt-2 flex-shrink-0 border-t border-gray-100 bg-white">
              <button
                type="button"
                onClick={onAddSource}
                className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <PlusIcon />
                Add Source
              </button>
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
      ) : (
        <button
          type="button"
          onClick={handleSidebarRestore}
          className="flex-shrink-0 w-3 rounded-2xl border border-gray-200 bg-white shadow-sm hover:bg-gray-50 transition-colors relative"
          title="Show sidebar"
        >
          <span className="absolute inset-y-2 left-1/2 -translate-x-1/2 w-px bg-gray-300" />
        </button>
      )}

      {/* ── Main chat ── */}
      <div className="flex-1 flex flex-col min-w-0 relative overflow-hidden bg-white rounded-2xl border border-gray-200 shadow-sm">

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
        <div className={`flex-1 min-h-0 overflow-y-auto overflow-x-auto px-6 pt-5 pb-4 space-y-6 transition-all duration-200 ${sourcesPanel.open ? 'mr-80' : ''}`}>
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-center">
              <p className="text-base font-semibold text-gray-800">Ask me anything about {course?.title || 'this course'}</p>
              <p className="text-sm text-gray-400 max-w-xs">I can explain concepts, quiz you on the material, summarize lectures, and more.</p>
            </div>
          ) : (
            (() => {
              const lastAssistantIdx = messages.reduce((acc, m, idx) => m.role === 'assistant' ? idx : acc, -1);
              return messages.map((msg, i) => {
              const prevMsg = messages[i - 1];
              const rawHistory = msg.role === 'assistant' ? prevMsg?.reply_history : null;
              const replyHistory = (() => {
                if (!rawHistory) return null;
                if (Array.isArray(rawHistory)) return rawHistory.length ? { back: rawHistory, forward: [] } : null;
                const b = rawHistory.back || [], f = rawHistory.forward || [];
                return b.length || f.length ? { back: b, forward: f } : null;
              })();
              const webSearchUrls = msg.role === 'assistant' ? (() => {
                const trace = Array.isArray(msg.tool_trace) ? msg.tool_trace : [];
                const seen = new Set();
                return trace
                  .filter((t) => t.tool === 'web_search' && Array.isArray(t.urls))
                  .flatMap((t) => t.urls)
                  .filter((u) => u.url && !seen.has(u.url) && seen.add(u.url));
              })() : null;
              return (
              <MessageBubble
                key={msg.id}
                msg={msg}
                courseName={course?.title}
                userPicture={userData?.picture}
                onCiteClick={msg.role === 'assistant' ? (n) => openSources(msg.id, n) : null}
                webSearchUrls={webSearchUrls?.length ? webSearchUrls : null}
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
                materials={materials}
                onPin={msg.role === 'assistant' ? () => {
                  const userMsg = messages.slice(0, i).reverse().find((m) => m.role === 'user');
                  if (userMsg) handlePinMessage(msg, userMsg);
                } : null}
                isPinned={msg.role === 'assistant' ? pinnedResponses.some((p) => p.assistant_message_id === msg.id) : false}
                onFollowUpClick={msg.role === 'assistant' ? (q) => {
                  setInput(q);
                  setTimeout(() => textareaRef.current?.focus(), 0);
                } : null}
                onSkipClarification={msg.role === 'assistant' ? () => handleSkipClarification(msg.id) : null}
                isLastAssistantMsg={msg.role === 'assistant' && i === lastAssistantIdx && !sending}
              />
              );
            });
            })()
          )}
          {sending && (
            <StreamingHistoryBubble history={streamingHistory} materials={materials} />
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="flex-shrink-0 px-4 pb-4 pt-2 border-t border-gray-100 bg-white">
          <div className="flex items-stretch gap-2 pl-4 pr-3 py-2 rounded-2xl border border-gray-200 bg-white hover:shadow-lg focus-within:border-indigo-300 focus-within:shadow-lg transition-all" style={{ boxShadow: '0 4px 24px 0 rgba(0,0,0,0.13)' }}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Reply…"
              rows={1}
              className="flex-1 min-h-0 min-w-0 bg-transparent resize-none text-xs text-gray-800 placeholder-gray-400 focus:outline-none leading-relaxed py-0.5"
              style={{
                minHeight: CHAT_COMPOSER_MIN_HEIGHT_PX,
                maxHeight: CHAT_COMPOSER_MAX_HEIGHT_PX,
                overflowY: 'auto',
              }}
            />
            <div className="flex flex-col justify-end flex-shrink-0">
              <div className="flex items-center gap-1">
                {/* Model selector */}
                {availableModels.length > 0 && (
                  <>
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
                  </>
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
            </div>
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

    {/* Saved pins — full width below chat + input */}
    <div className="w-full rounded-2xl border border-gray-200 shadow-sm bg-white overflow-hidden">
      <PinsPanel
        pins={pinnedResponses}
        courseName={course?.title}
        userData={userData}
        materials={materials}
        onDeletePin={handleDeletePin}
      />
    </div>

    {searchOpen && (
      <SearchChat
        courseId={course.id}
        chats={chats.filter(c => c.id !== '__new__')}
        onSelectChat={handleConvSelect}
        onClose={() => setSearchOpen(false)}
      />
    )}
    </div>
  );
}
