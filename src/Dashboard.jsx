import { useRef } from "react";
import { useNavigate } from "react-router-dom";
import CardViewer from "./CardViewer.jsx";
import CreateCourseModal from "./CreateCourseModal.jsx";

function SignOutIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export default function Dashboard({ userData, sessionToken, onSignOut }) {
  const createModalRef = useRef(null);
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Left: Brand */}
          <span className="text-xl font-bold text-gray-900">CourseMate</span>

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
            <CreateCourseModal ref={createModalRef} sessionToken={sessionToken} />
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

      {/* Dashboard body */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <CardViewer
          sessionToken={sessionToken}
          onCreateNew={() => createModalRef.current?.open()}
        />
      </main>
    </div>
  );
}
