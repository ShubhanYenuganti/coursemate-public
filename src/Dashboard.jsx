import { useRef } from "react";
import { useNavigate } from "react-router-dom";
import CardViewer from "./CardViewer.jsx";
import CreateCourseModal from "./CreateCourseModal.jsx";
import { Button } from "@/components/ui/button";

function SignOutIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export default function Dashboard({ userData, onSignOut }) {
  const createModalRef = useRef(null);
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-background/80 backdrop-blur-sm border-b border-border shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Left: Brand */}
          <span className="text-xl font-bold text-foreground">CourseMate</span>

          {/* Right: Avatar + New course + Sign out */}
          <div className="flex items-center gap-3">
            {userData?.picture && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => navigate('/profile')}
                className="rounded-full focus:ring-ring"
                title="View profile"
                aria-label="View profile"
              >
                <img
                  src={userData.picture}
                  alt={userData.username || userData.name}
                  className="w-8 h-8 rounded-full border-2 border-border hover:opacity-80 transition-opacity cursor-pointer"
                />
              </Button>
            )}
            <CreateCourseModal ref={createModalRef} />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onSignOut}
              className="text-muted-foreground hover:text-foreground"
              title="Sign out"
              aria-label="Sign out"
            >
              <SignOutIcon />
            </Button>
          </div>
        </div>
      </header>

      {/* Dashboard body */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <CardViewer onCreateNew={() => createModalRef.current?.open()} />
      </main>
    </div>
  );
}
