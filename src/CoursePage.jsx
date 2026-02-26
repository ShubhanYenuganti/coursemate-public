function SignOutIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export default function CoursePage({ course, userData, onSignOut }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Left: Course title */}
          <span className="text-xl font-bold text-gray-900">{course?.title || "Course"}</span>

          {/* Right: Avatar + Sign out */}
          <div className="flex items-center gap-3">
            {userData?.user?.picture && (
              <img
                src={userData.user.picture}
                alt={userData.user.name}
                className="w-8 h-8 rounded-full border-2 border-gray-200"
              />
            )}
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

      {/* Empty course body */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-gray-500 text-center py-32">
          <p className="text-lg font-medium text-gray-700 mb-1">{course?.title}</p>
          {course?.description && (
            <p className="text-sm text-gray-400">{course.description}</p>
          )}
        </div>
      </main>
    </div>
  );
}
