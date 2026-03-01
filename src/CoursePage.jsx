import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import CreateCourseModal from './CreateCourseModal.jsx';
import SharingAccessModal from './SharingAccessModal.jsx';
import MaterialsPage from './MaterialsPage.jsx';

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

// ─── main component ───────────────────────────────────────────────────────────

export default function CoursePage({ course, userData, sessionToken, onSignOut }) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('home');

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
            <CreateCourseModal sessionToken={sessionToken} />
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
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-32">
        {activeTab === 'home' && (
          <div className="space-y-6 max-w-3xl">
            {course?.description && (
              <p className="text-sm text-gray-600 leading-relaxed">{course.description}</p>
            )}
            <SharingAccessModal />
          </div>
        )}

        {activeTab === 'materials' && (
          <MaterialsPage
            courseId={course?.id}
            sessionToken={sessionToken}
            userId={userData?.db_id}
          />
        )}

        {activeTab === 'chat' && (
          <div className="flex items-center justify-center py-24 text-gray-400 text-sm">
            Chat — coming soon
          </div>
        )}

        {activeTab === 'generate' && (
          <div className="flex items-center justify-center py-24 text-gray-400 text-sm">
            Generate Materials — coming soon
          </div>
        )}
      </main>

      {/* Floating toolbar */}
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-3 rounded-2xl bg-white/70 backdrop-blur-md border border-gray-200 shadow-lg">
        <ToolbarItem icon="📄" label="Materials" active={activeTab === 'materials'} onClick={() => setActiveTab('materials')} />
        <div className="w-px h-6 bg-gray-200" />
        <ToolbarItem icon="💬" label="Chat"      active={activeTab === 'chat'}      onClick={() => setActiveTab('chat')} />
        <div className="w-px h-6 bg-gray-200" />
        <ToolbarItem icon="💡" label="Generate"  active={activeTab === 'generate'}  onClick={() => setActiveTab('generate')} />
      </div>
    </div>
  );
}
