import { useState, useEffect, useRef } from 'react';
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

// ─── progress state persistence ──────────────────────────────────────────────

function loadProgressState(courseId) {
  try {
    const raw = localStorage.getItem(`coursemate_progress_${courseId}`);
    if (!raw) return { syncJobs: [], uploadItems: [], panelDismissed: false };
    const parsed = JSON.parse(raw);
    const uploadItems = (parsed.uploadItems || []).map((item) =>
      item.status === 'uploading' || item.status === 'confirming'
        ? { ...item, status: 'error' }
        : item,
    );
    return {
      syncJobs: parsed.syncJobs || [],
      uploadItems,
      panelDismissed: parsed.panelDismissed ?? false,
    };
  } catch {
    return { syncJobs: [], uploadItems: [], panelDismissed: false };
  }
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

  // ─── progress panel state (persists across tab switches and page refresh) ────
  const [syncJobs, setSyncJobs] = useState([]);
  const [uploadItems, setUploadItems] = useState([]);
  const [panelDismissed, setPanelDismissed] = useState(false);
  const progressInitialized = useRef(false);

  // Load from localStorage once courseId is known
  useEffect(() => {
    if (!course?.id || progressInitialized.current) return;
    progressInitialized.current = true;
    const saved = loadProgressState(course.id);
    setSyncJobs(saved.syncJobs);
    setUploadItems(saved.uploadItems);
    setPanelDismissed(saved.panelDismissed);
  }, [course?.id]);

  // Record open for dashboard ordering (most recently opened first)
  useEffect(() => {
    if (!course?.id) return;
    fetch('/api/course', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ action: 'record_open', course_id: course.id }),
    }).catch(() => {});
  }, [course?.id]);

  // Persist to localStorage on every change
  useEffect(() => {
    if (!course?.id) return;
    localStorage.setItem(
      `coursemate_progress_${course.id}`,
      JSON.stringify({ syncJobs, uploadItems, panelDismissed }),
    );
  }, [syncJobs, uploadItems, panelDismissed, course?.id]);

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
          </div>
        )}

        {activeTab === 'materials' && (
          <div className="max-w-5xl mx-auto">
            <MaterialsPage
              courseId={course?.id}
              userId={userData?.db_id}
              syncJobs={syncJobs}
              setSyncJobs={setSyncJobs}
              uploadItems={uploadItems}
              setUploadItems={setUploadItems}
              panelDismissed={panelDismissed}
              setPanelDismissed={setPanelDismissed}
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
