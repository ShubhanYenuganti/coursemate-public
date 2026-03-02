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
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors ${
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
    <div className="flex items-start gap-3">
      <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 mt-0.5">
        <SparkleIcon />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-indigo-600 uppercase tracking-wide">
            {courseName || 'CourseMate AI'}
          </span>
          <span className="w-1 h-1 rounded-full bg-indigo-300" />
          <SparkleIcon />
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
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
    <div className="flex rounded-2xl overflow-hidden border border-gray-200 bg-white shadow-sm" style={{ height: '68vh', minHeight: '520px' }}>

      {/* ── Sidebar ── */}
      <div className="w-56 flex-shrink-0 border-r border-gray-100 bg-gray-50/80 flex flex-col">
        {/* Logo / title */}
        <div className="px-4 pt-5 pb-3">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center">
              <SparkleIcon />
            </div>
            <span className="font-bold text-gray-900 text-sm">Course Chat</span>
          </div>
          <button
            type="button"
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors shadow-sm"
          >
            <PlusIcon />
            New chat
          </button>
        </div>

        {/* Conversations */}
        <div className="flex-1 overflow-y-auto px-2 space-y-4 pb-4">
          <div>
            <p className="px-3 py-1 text-xs font-medium text-gray-400 uppercase tracking-wide flex items-center justify-between">
              <span>Your conversations</span>
              <button type="button" className="text-indigo-500 hover:text-indigo-700 normal-case text-xs font-normal transition-colors">
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
            <p className="px-3 py-1 text-xs font-medium text-gray-400 uppercase tracking-wide">Last 7 Days</p>
            <div className="space-y-0.5">
              {WEEK_CONVS.map((c) => (
                <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} />
              ))}
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

      {/* ── Main chat ── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-center">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 flex items-center justify-center">
                <div className="text-indigo-500 scale-150"><SparkleIcon /></div>
              </div>
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
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
                <SparkleIcon />
              </div>
              <div className="flex items-center gap-1 pt-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="border-t border-gray-100 p-4">
          <div className="flex items-end gap-3 px-4 py-3 rounded-2xl border border-gray-200 bg-gray-50 focus-within:border-indigo-300 focus-within:bg-white transition-all shadow-sm">
            <div className="w-5 h-5 flex-shrink-0 mb-0.5 text-indigo-400">
              <SparkleIcon />
            </div>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask about ${course?.title || 'this course'}…`}
              rows={1}
              className="flex-1 bg-transparent resize-none text-sm text-gray-800 placeholder-gray-400 focus:outline-none leading-relaxed"
              style={{ maxHeight: '120px', overflowY: 'auto' }}
              onInput={(e) => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
            >
              <SendIcon />
            </button>
          </div>
          <p className="text-center text-xs text-gray-400 mt-2">
            AI responses are based on your uploaded course materials.
          </p>
        </div>
      </div>
    </div>
  );
}
