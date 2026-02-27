import { useNavigate } from 'react-router-dom';
import CreateCourseModal from './CreateCourseModal.jsx';
import SharingAccessModal from './SharingAccessModal.jsx';

function ToolbarItem({ icon, label }) {
  return (
    <div className="group flex items-center gap-2">
      <span className="max-w-0 overflow-hidden whitespace-nowrap text-sm font-medium text-gray-700 transition-all duration-200 ease-out group-hover:max-w-xs">
        {label}
      </span>
      <div className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/80 border border-gray-200 shadow-sm text-gray-600 group-hover:text-indigo-600 group-hover:border-indigo-300 group-hover:shadow-md transition-all duration-200 cursor-default select-none text-lg">
        {icon}
      </div>
    </div>
  );
}

function BackIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 19l-7-7 7-7"/>
    </svg>
  );
}

function SignOutIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export default function CoursePage({ course, userData, sessionToken, onSignOut }) {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Left: Back button + Course title */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              title="Back to home"
              aria-label="Back to home"
            >
              <BackIcon />
            </button>
            <span className="text-xl font-bold text-gray-900">{course?.title || "Course"}</span>
          </div>

          {/* Right: Avatar + New course + Sign out */}
          <div className="flex items-center gap-3">
            {userData?.picture && (
              <button
                type="button"
                onClick={() => navigate('/profile')}
                className="rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-400"
                title="View profile"
                aria-label="View profile"
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
              aria-label="Sign out"
            >
              <SignOutIcon />
            </button>
          </div>
        </div>
      </header>

      {/* Course body */}
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-32 space-y-6">
        {course?.description && (
          <p className="text-sm text-gray-600 leading-relaxed">{course.description}</p>
        )}
        <SharingAccessModal />
      </main>

      {/* Floating toolbar */}
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-3 rounded-2xl bg-white/70 backdrop-blur-md border border-gray-200 shadow-lg">
        <ToolbarItem icon="📄" label="Materials" />
        <div className="w-px h-6 bg-gray-200" />
        <ToolbarItem icon="💬" label="Chat" />
        <div className="w-px h-6 bg-gray-200" />
        <ToolbarItem icon="💡" label="Generate Materials" />
      </div>
    </div>
  );
}
