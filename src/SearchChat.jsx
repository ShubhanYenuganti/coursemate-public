import { useState, useEffect } from 'react';
import { parseUTC } from './utils/dateUtils';

function formatRelative(str) {
  const d = parseUTC(str);
  if (!d || isNaN(d.getTime())) return '';
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function SectionLabel({ label }) {
  return (
    <div className="px-4 py-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider bg-gray-50 border-b border-gray-100 sticky top-0 z-10">
      {label}
    </div>
  );
}

function ResultRow({ chat, onSelectChat, onClose }) {
  return (
    <button
      type="button"
      className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-indigo-50 cursor-pointer text-left"
      onClick={() => { onSelectChat(chat.id); onClose(); }}
    >
      <span className="text-gray-400 flex-shrink-0">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </span>
      <span className="text-sm text-gray-800 truncate flex-1">{chat.title || 'Untitled'}</span>
      <span className="text-[11px] text-gray-400 flex-shrink-0">
        {formatRelative(chat.last_message_at)}
      </span>
    </button>
  );
}

export default function SearchChat({ courseId, chats, onSelectChat, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  // ESC to close
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  // Debounced fetch
  useEffect(() => {
    if (!query.trim()) {
      setResults(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/chat?resource=chat_search&q=${encodeURIComponent(query)}&course_id=${courseId}`
        );
        if (res.ok) {
          const data = await res.json();
          setResults(data);
        }
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, courseId]);

  const recencyList = query === ''
    ? [...chats].sort((a, b) => {
        const ta = parseUTC(a.last_message_at)?.getTime() ?? 0;
        const tb = parseUTC(b.last_message_at)?.getTime() ?? 0;
        return tb - ta;
      })
    : null;

  const hasResults = results && (results.title_matches.length > 0 || results.content_matches.length > 0);
  const noResults = results && !hasResults && !loading;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/20"
      onClick={onClose}
    >
      <div
        className="absolute top-[18%] left-1/2 -translate-x-1/2 w-full max-w-xl bg-white rounded-2xl shadow-xl border border-gray-200 flex flex-col max-h-[62vh]"
        onClick={e => e.stopPropagation()}
      >
        {/* Header / search input */}
        <div className="px-4 py-3 flex items-center gap-3 border-b border-gray-100">
          <span className="text-indigo-400 flex-shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </span>
          <input
            type="text"
            className="flex-1 text-sm text-gray-800 outline-none placeholder-gray-400 bg-transparent"
            placeholder="Search chats…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
          {query && (
            <button
              type="button"
              className="text-gray-400 hover:text-gray-600 flex-shrink-0"
              onClick={() => setQuery('')}
            >
              ✕
            </button>
          )}
        </div>

        {/* Results area */}
        <div className="overflow-y-auto flex-1">
          {/* Empty query — recency list */}
          {recencyList && recencyList.map(chat => (
            <ResultRow key={chat.id} chat={chat} onSelectChat={onSelectChat} onClose={onClose} />
          ))}

          {/* Loading */}
          {loading && (
            <div className="px-4 py-6 text-center text-sm text-gray-400">Searching…</div>
          )}

          {/* Two-section results */}
          {!loading && results && (
            <>
              {results.title_matches.length > 0 && (
                <>
                  <SectionLabel label="Title Matches" />
                  {results.title_matches.map(chat => (
                    <ResultRow key={chat.id} chat={chat} onSelectChat={onSelectChat} onClose={onClose} />
                  ))}
                </>
              )}
              {results.content_matches.length > 0 && (
                <>
                  <SectionLabel label="In Conversation" />
                  {results.content_matches.map(chat => (
                    <ResultRow key={chat.id} chat={chat} onSelectChat={onSelectChat} onClose={onClose} />
                  ))}
                </>
              )}
              {noResults && (
                <div className="px-4 py-8 text-center text-sm text-gray-400">No chats found</div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
