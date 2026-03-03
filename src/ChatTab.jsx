import { useState, useRef, useEffect } from 'react';

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
  openai: 'GPT-4o',
  claude: 'Claude',
};

// ─── sample data ──────────────────────────────────────────────────────────────

const TODAY_CONVS = [
  { id: 1, title: 'Explain key concepts from Week 3' },
  { id: 2, title: 'Quiz me on Chapter 5' },
  { id: 3, title: 'Summarize the lecture notes' },
];

const WEEK_CONVS = [
  { id: 4, title: 'What topics will be on the exam?' },
  { id: 5, title: 'Help with assignment 2' },
  { id: 6, title: 'Clarify the homework instructions' },
];

const SAMPLE_MESSAGES = [
  {
    id: 1,
    role: 'user',
    content: 'Can you explain the key concepts from this week\'s lecture materials?',
  },
  {
    id: 2,
    role: 'assistant',
    content: `Sure! Based on the course materials, here are the key concepts from this week:\n\n**1. Core Principles**\nThe foundational ideas introduced this week build on prior concepts and establish the framework for upcoming topics. Understanding these principles is essential for the assignments ahead.\n\n**2. Practical Applications**\nThe lecture demonstrates how theory maps to real-world scenarios. Pay close attention to the worked examples — they are commonly tested.\n\n**3. Common Pitfalls**\nStudents often confuse related terms. Review the definitions carefully and use the provided examples to distinguish between them.\n\nWould you like me to go deeper on any of these points, or quiz you on the material?`,
  },
  {
    id: 3,
    role: 'user',
    content: 'Yes, please quiz me on the key concepts.',
  },
  {
    id: 4,
    role: 'assistant',
    content: `Great! Let's start with a few questions:\n\n**Question 1:** In your own words, what is the primary objective introduced in the first section of this week's material?\n\nTake your time — when you're ready, type your answer and I'll give you feedback!`,
  },
];

// ─── sub-components ───────────────────────────────────────────────────────────

function ConvItem({ conv, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-xs transition-colors ${
        active
          ? 'bg-indigo-50 text-indigo-700 font-medium'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      }`}
    >
      <span className={`flex-shrink-0 ${active ? 'text-indigo-500' : 'text-gray-400'}`}>
        <ChatBubbleIcon />
      </span>
      <span className="truncate">{conv.title}</span>
    </button>
  );
}

function MessageBubble({ msg, courseName, userPicture }) {
  const isUser = msg.role === 'user';

  function renderContent(content) {
    const lines = content.split('\n');
    return lines.map((line, i) => {
      if (line.startsWith('**') && line.endsWith('**')) {
        return <p key={i} className="font-semibold text-gray-900 mt-3 first:mt-0">{line.slice(2, -2)}</p>;
      }
      const parts = line.split(/(\*\*[^*]+\*\*)/g);
      if (parts.length > 1) {
        return (
          <p key={i} className={i > 0 ? 'mt-1' : ''}>
            {parts.map((part, j) =>
              part.startsWith('**') && part.endsWith('**')
                ? <strong key={j}>{part.slice(2, -2)}</strong>
                : part
            )}
          </p>
        );
      }
      if (line === '') return <div key={i} className="h-1" />;
      return <p key={i} className={i > 0 ? 'mt-1' : ''}>{line}</p>;
    });
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
          <p className="text-sm text-gray-800 leading-relaxed">{msg.content}</p>
        </div>
        <button
          type="button"
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
          <span className="w-1 h-1 rounded-full bg-indigo-300" />
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
          <button type="button" className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors" title="Copy">
            <CopyIcon />
          </button>
          <button type="button" className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors" title="More">
            <MoreIcon />
          </button>
          <div className="flex-1" />
          <button type="button" className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors border border-gray-200 hover:border-indigo-200">
            <RefreshIcon />
            Regenerate
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function ChatTab({ course, userData, sessionToken }) {
  const [activeConv, setActiveConv] = useState(1);
  const [messages, setMessages] = useState(SAMPLE_MESSAGES);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [selectedModel, setSelectedModel] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [switchBanner, setSwitchBanner] = useState('');
  const [materials, setMaterials] = useState([]);
  const [selectedMaterials, setSelectedMaterials] = useState(new Set());
  const [selectAllMaterials, setSelectAllMaterials] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(224);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);
  const bannerTimerRef = useRef(null);
  const containerRef = useRef(null);
  const isDraggingRef = useRef(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!course?.id || !sessionToken) return;
    fetch(`/api/material?course_id=${course.id}`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {});
  }, [course?.id, sessionToken]);

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
        if (available.length > 0) setSelectedModel(available[0]);
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

  function handleModelSelect(provider) {
    setSelectedModel(provider);
    setModelDropdownOpen(false);
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    setSwitchBanner(MODEL_LABELS[provider] || provider);
    bannerTimerRef.current = setTimeout(() => setSwitchBanner(''), 2500);
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
    setMessages([]);
    setActiveConv(null);
    setInput('');
  }

  function handleConvSelect(id) {
    setActiveConv(id);
    setMessages(SAMPLE_MESSAGES);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setSending(true);

    const userMsg = { id: Date.now(), role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);

    // Placeholder — replace with real API call
    await new Promise((r) => setTimeout(r, 800));
    const aiMsg = {
      id: Date.now() + 1,
      role: 'assistant',
      content: `I'm working on connecting to the course materials API. For now, here's a placeholder response to your question: "${text}"`,
    };
    setMessages((prev) => [...prev, aiMsg]);
    setSending(false);
  }

  return (
    <div ref={containerRef} className="relative flex rounded-2xl overflow-hidden border border-gray-200 bg-white shadow-sm" style={{ height: '68vh', minHeight: '520px' }}>

      {/* Switched-to banner — centred over the full modal */}
      {switchBanner && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-4 py-1.5 rounded-full bg-gray-900 text-white text-xs font-medium shadow-lg whitespace-nowrap pointer-events-none select-none">
          Switched to {switchBanner} ⚡
        </div>
      )}

      {/* ── Sidebar ── */}
      <div className="flex-shrink-0 bg-gray-50/80 flex flex-col" style={{ width: sidebarWidth }}>
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
            <div>
              <p className="px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider flex items-center justify-between">
                <span>Your conversations</span>
                <button type="button" className="text-indigo-500 hover:text-indigo-700 normal-case text-[10px] font-normal transition-colors">
                  Clear all
                </button>
              </p>
              <div className="space-y-0.5">
                {TODAY_CONVS.map((c) => (
                  <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} />
                ))}
              </div>
            </div>

            <div>
              <p className="px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider">Last 7 Days</p>
              <div className="space-y-0.5">
                {WEEK_CONVS.map((c) => (
                  <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} />
                ))}
              </div>
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
      <div className="flex-1 flex flex-col min-w-0 relative">


        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 pt-5 pb-20 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-center">
              <p className="text-base font-semibold text-gray-800">Ask me anything about {course?.title || 'this course'}</p>
              <p className="text-sm text-gray-400 max-w-xs">I can explain concepts, quiz you on the material, summarize lectures, and more.</p>
            </div>
          ) : (
            messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                msg={msg}
                courseName={course?.title}
                userPicture={userData?.picture}
              />
            ))
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
              <div className="relative flex-shrink-0" ref={dropdownRef}>
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
                      <button
                        key={provider}
                        type="button"
                        onClick={() => handleModelSelect(provider)}
                        className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left transition-colors rounded-lg hover:bg-gray-700/70"
                      >
                        <span className={selectedModel === provider ? 'text-white font-medium' : 'text-gray-300'}>
                          {MODEL_LABELS[provider] || provider}
                        </span>
                        {selectedModel === provider && (
                          <span className="text-indigo-400"><CheckIcon /></span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
            >
              <SendIcon />
            </button>
          </div>
          <p className="text-center text-[10px] text-gray-400 mt-1.5">
            AI responses are based on your uploaded course materials.
          </p>
        </div>
      </div>
    </div>
  );
}