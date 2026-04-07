import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import CreateCourseModal from './CreateCourseModal.jsx';
import SharingAccessModal from './SharingAccessModal.jsx';
import MaterialsPage from './MaterialsPage.jsx';
import ChatTab from './ChatTab.jsx';
import Generations from './Generations.jsx';

// ─── icons ────────────────────────────────────────────────────────────────────

function BackIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 19l-7-7 7-7"/>
    </svg>
  );
}

function SignOutIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

// ─── floating toolbar item ────────────────────────────────────────────────────

function ToolbarItem({ icon, label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex items-center gap-2 transition-all duration-150 rounded-xl px-1 py-1 focus:outline-none ${
        active ? 'cursor-default' : 'cursor-pointer'
      }`}
    >
      <span className={`max-w-0 overflow-hidden whitespace-nowrap text-sm font-medium transition-all duration-200 ease-out group-hover:max-w-xs ${
        active ? 'text-indigo-700 max-w-xs' : 'text-gray-700'
      }`}>
        {label}
      </span>
      <div className={`w-10 h-10 flex items-center justify-center rounded-xl border shadow-sm text-lg transition-all duration-200 ${
        active
          ? 'bg-indigo-600 border-indigo-600 text-white shadow-md'
          : 'bg-white/80 border-gray-200 text-gray-600 group-hover:text-indigo-600 group-hover:border-indigo-300 group-hover:shadow-md'
      }`}>
        {icon}
      </div>
    </button>
  );
}

// ─── Notion Sources Panel ─────────────────────────────────────────────────────

function NotionSourcesPanel({ courseId }) {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');
  const [confirmRemoveId, setConfirmRemoveId] = useState(null);
  const [notionConnected, setNotionConnected] = useState(false);

  useEffect(() => {
    fetch('/api/notion?action=status', { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => setNotionConnected(!!d.connected))
      .catch(() => {});
    loadSources();
  }, [courseId]); // eslint-disable-line react-hooks/exhaustive-deps

  function loadSources() {
    if (!courseId) return;
    setLoading(true);
    fetch(`/api/notion?action=list_source_points&course_id=${courseId}`, { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => setSources(d.source_points || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  // Debounced DB search
  useEffect(() => {
    if (query.trim() === '') { setResults([]); return; }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(`/api/notion?action=search&q=${encodeURIComponent(query.trim())}&filter_type=database`, { credentials: 'include' });
        const data = await res.json();
        setResults(data.results || []);
      } catch { setResults([]); }
      finally { setSearching(false); }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  async function handleAdd(db) {
    try {
      const res = await fetch('/api/notion?action=add_source_point', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ course_id: courseId, provider: 'notion', external_id: db.id, external_title: db.title }),
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }
      if (!res.ok) {
        const msg = data?.error || 'Failed to add source';
        setSyncMsg(msg);
        setTimeout(() => setSyncMsg(''), 4000);
        return;
      }

      if (data?.sync_triggered) {
        setSyncMsg('Source added, initial sync started');
      } else {
        setSyncMsg('Source added; initial sync was not triggered. Use Sync Now.');
      }
      setTimeout(() => setSyncMsg(''), 4000);
      setQuery('');
      setResults([]);
      loadSources();
    } catch { /* ignore */ }
  }

  async function handleToggle(id) {
    try {
      const res = await fetch(`/api/notion?action=toggle_source_point&id=${id}`, { method: 'PATCH', credentials: 'include' });
      const data = await res.json();
      setSources((prev) => prev.map((s) => s.id === id ? { ...s, is_active: data.is_active } : s));
    } catch { /* ignore */ }
  }

  async function handleRemove(id) {
    try {
      await fetch(`/api/notion?action=remove_source_point&id=${id}`, { method: 'DELETE', credentials: 'include' });
      setSources((prev) => prev.filter((s) => s.id !== id));
    } catch { /* ignore */ }
    finally { setConfirmRemoveId(null); }
  }

  async function handleSync() {
    if (syncing) return;
    setSyncing(true);
    setSyncMsg('');
    try {
      await fetch(`/api/notion?action=sync&course_id=${courseId}`, { method: 'POST', credentials: 'include' });
      setSyncMsg('Sync started');
      setTimeout(() => setSyncMsg(''), 3000);
    } catch { setSyncMsg('Sync failed'); }
    finally { setSyncing(false); }
  }

  function formatDate(ts) {
    if (!ts) return 'Never';
    return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  if (!notionConnected) return null;

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="text-gray-500">
            <path d="M4 4a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v16a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V4z" opacity=".15"/>
            <rect x="7" y="7" width="10" height="1.5" rx=".75"/>
            <rect x="7" y="11" width="7" height="1.5" rx=".75"/>
            <rect x="7" y="15" width="8" height="1.5" rx=".75"/>
          </svg>
          <span className="text-sm font-semibold text-gray-900">Notion Sources</span>
        </div>
        <div className="flex items-center gap-2">
          {syncMsg && <span className="text-xs text-gray-500">{syncMsg}</span>}
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing || sources.filter((s) => s.is_active).length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-40"
          >
            {syncing ? 'Syncing…' : 'Sync Now'}
          </button>
        </div>
      </div>

      {/* Search to add */}
      <div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search Notion databases to add…"
          className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
        />
        {searching && <p className="text-xs text-gray-400 mt-1">Searching…</p>}
        {results.length > 0 && (
          <div className="mt-1 border border-gray-100 rounded-lg overflow-hidden max-h-40 overflow-y-auto">
            {results.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => handleAdd(r)}
                className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-800 hover:bg-gray-50 transition-colors"
              >
                <span className="flex-1 truncate">{r.title || 'Untitled'}</span>
                <span className="text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">DB</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Source list */}
      {loading ? (
        <p className="text-xs text-gray-400">Loading…</p>
      ) : sources.length === 0 ? (
        <p className="text-xs text-gray-400 italic">No Notion databases connected. Search above to add one.</p>
      ) : (
        <div className="space-y-2">
          {sources.map((s) => (
            <div key={s.id} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-colors ${s.is_active ? 'border-gray-200 bg-white' : 'border-gray-100 bg-gray-50'}`}>
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium truncate ${s.is_active ? 'text-gray-900' : 'text-gray-400'}`}>{s.external_title || s.external_id}</p>
                <p className="text-[10px] text-gray-400 mt-0.5">Last synced: {formatDate(s.last_synced_at)}</p>
              </div>
              <button
                type="button"
                onClick={() => handleToggle(s.id)}
                className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                  s.is_active
                    ? 'border-gray-200 text-gray-600 hover:bg-gray-50'
                    : 'border-indigo-200 text-indigo-600 bg-indigo-50 hover:bg-indigo-100'
                }`}
              >
                {s.is_active ? 'Disable' : 'Enable'}
              </button>
              {confirmRemoveId === s.id ? (
                <div className="flex items-center gap-1">
                  <button type="button" onClick={() => handleRemove(s.id)} className="text-xs px-2 py-1 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 transition-colors">Delete</button>
                  <button type="button" onClick={() => setConfirmRemoveId(null)} className="text-xs px-2 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors">Cancel</button>
                </div>
              ) : (
                <button type="button" onClick={() => setConfirmRemoveId(s.id)} className="text-gray-300 hover:text-red-500 transition-colors p-1">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>
                    <path d="M9 6V4h6v2"/>
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function CoursePage({ course, userData, csrfToken, onSignOut, onCourseUpdate }) {
  const navigate = useNavigate();
  const storageKey = `coursemate_active_tab_${course?.id}`;
  const isOwner = course?.primary_creator === userData?.db_id;
  const [activeTab, setActiveTab] = useState(
    () => {
      const saved = localStorage.getItem(storageKey) || 'home';
      return saved;
    }
  );

  function handleTabChange(tab) {
    localStorage.setItem(storageKey, tab);
    setActiveTab(tab);
  }

  // Description edit state
  const [editingDesc, setEditingDesc] = useState(false);
  const [descValue, setDescValue] = useState(course?.description || '');
  const [descStatus, setDescStatus] = useState(null); // null | 'saving' | 'error'
  const [descError, setDescError] = useState('');

  async function handleSaveDesc() {
    setDescStatus('saving');
    setDescError('');
    try {
      const res = await fetch('/api/course', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ course_id: course.id, description: descValue }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      onCourseUpdate?.(data.course);
      setEditingDesc(false);
      setDescStatus(null);
    } catch (err) {
      setDescError(err.message);
      setDescStatus('error');
    }
  }

  function cancelEditDesc() {
    setDescValue(course?.description || '');
    setEditingDesc(false);
    setDescStatus(null);
    setDescError('');
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              title="Back to home"
            >
              <BackIcon />
            </button>
            <span className="text-xl font-bold text-gray-900">{course?.title || 'Course'}</span>
          </div>

          <div className="flex items-center gap-3">
            {userData?.picture && (
              <button
                type="button"
                onClick={() => navigate('/profile')}
                className="rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-400"
                title="View profile"
              >
                <img
                  src={userData.picture}
                  alt={userData.username || userData.name}
                  className="w-8 h-8 rounded-full border-2 border-gray-200 hover:opacity-80 transition-opacity cursor-pointer"
                />
              </button>
            )}
            <CreateCourseModal />
            <button
              type="button"
              onClick={onSignOut}
              className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              title="Sign out"
            >
              <SignOutIcon />
            </button>
          </div>
        </div>
      </header>

      {/* Tab content */}
      <main className="px-4 sm:px-6 lg:px-8 py-8 pb-32">
        {activeTab === 'home' && (
          <div className="space-y-6 max-w-3xl mx-auto">
            {/* Description */}
            <div className="group relative">
              {editingDesc ? (
                <div className="space-y-2">
                  <textarea
                    autoFocus
                    value={descValue}
                    onChange={(e) => { setDescValue(e.target.value); setDescError(''); }}
                    rows={4}
                    maxLength={2000}
                    placeholder="Add a description…"
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 bg-white text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent resize-none transition-all"
                  />
                  {descError && <p className="text-xs text-red-600">{descError}</p>}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleSaveDesc}
                      disabled={descStatus === 'saving'}
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                    >
                      {descStatus === 'saving' ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      type="button"
                      onClick={cancelEditDesc}
                      className="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {course?.description ? (
                    <p className="text-sm text-gray-600 leading-relaxed pr-8">{course.description}</p>
                  ) : (
                    isOwner && (
                      <p className="text-sm text-gray-400 italic pr-8">No description yet.</p>
                    )
                  )}
                  {isOwner && (
                    <button
                      type="button"
                      onClick={() => setEditingDesc(true)}
                      title="Edit description"
                      className="absolute top-0 right-0 p-1.5 rounded-lg text-gray-300 hover:text-indigo-600 hover:bg-indigo-50 opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                    </button>
                  )}
                </>
              )}
            </div>
            {isOwner && (
            <SharingAccessModal
              courseId={course?.id}
              csrfToken={csrfToken}
              isOwner={isOwner}
            />
          )}
          <NotionSourcesPanel courseId={course?.id} />
          </div>
        )}

        {activeTab === 'materials' && (
          <div className="max-w-5xl mx-auto">
            <MaterialsPage
              courseId={course?.id}
              userId={userData?.db_id}
            />
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="max-w-5xl mx-auto">
            <ChatTab course={course} userData={userData} onAddSource={() => handleTabChange('materials')} />
          </div>
        )}

        {activeTab === 'generate' && (
          <div className="max-w-5xl mx-auto">
            <Generations
              course={course}
              userData={userData}
              onAddSource={() => handleTabChange('materials')}
            />
          </div>
        )}
      </main>

      {/* Floating toolbar */}
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-3 rounded-2xl bg-white/70 backdrop-blur-md border border-gray-200 shadow-lg">
        <>
          <ToolbarItem icon="🏠" label="Overview" active={activeTab === 'home'} onClick={() => handleTabChange('home')} />
          <div className="w-px h-6 bg-gray-200" />
        </>
        <ToolbarItem icon="📄" label="Materials" active={activeTab === 'materials'} onClick={() => handleTabChange('materials')} />
        <div className="w-px h-6 bg-gray-200" />
        <ToolbarItem icon="💬" label="Chat"      active={activeTab === 'chat'}      onClick={() => handleTabChange('chat')} />
        <div className="w-px h-6 bg-gray-200" />
        <ToolbarItem icon="💡" label="Generate"  active={activeTab === 'generate'}  onClick={() => handleTabChange('generate')} />
      </div>
    </div>
  );
}
