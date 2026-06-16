import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { formatDate } from './utils/dateUtils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';


function EditIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function DotsIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <circle cx="12" cy="5" r="1.5" />
      <circle cx="12" cy="12" r="1.5" />
      <circle cx="12" cy="19" r="1.5" />
    </svg>
  );
}

function CourseMenu({ courseId, onDelete }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className="p-1.5 h-auto w-auto rounded-lg text-muted-foreground hover:text-foreground"
        aria-label="Course options"
      >
        <DotsIcon />
      </Button>
      {open && (
        <div className="absolute right-0 top-8 z-20 w-36 bg-background border border-border rounded-xl shadow-lg overflow-hidden">
          <Button
            type="button"
            variant="destructive"
            onClick={(e) => { e.stopPropagation(); setOpen(false); onDelete(courseId); }}
            className="w-full justify-start text-left px-4 py-2.5 h-auto rounded-none text-sm"
          >
            Delete
          </Button>
        </div>
      )}
    </div>
  );
}

function CourseCard({ course, onDelete, onClick, onRename }) {
  const isCoCreator = !course.is_owner;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(course.title);
  const inputRef = useRef(null);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const startEdit = useCallback((e) => {
    e.stopPropagation();
    setDraft(course.title);
    setEditing(true);
  }, [course.title]);

  const commitEdit = useCallback(() => {
    const trimmed = draft.trim();
    setEditing(false);
    if (trimmed && trimmed !== course.title) onRename(course.id, trimmed);
    else setDraft(course.title);
  }, [draft, course.title, course.id, onRename]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') { e.preventDefault(); commitEdit(); }
    if (e.key === 'Escape') { setEditing(false); setDraft(course.title); }
  }, [commitEdit, course.title]);

  return (
    <div
      onClick={() => !editing && onClick(course)}
      className="group relative h-44 bg-background/80 backdrop-blur-sm border border-border rounded-2xl shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer flex flex-col overflow-hidden"
    >
      {/* Fixed height: title clamps to 3 lines; meta row pinned to bottom */}
      <div className="flex flex-1 min-h-0 flex-col gap-2 p-4">
        <div className="grid flex-1 min-h-0 grid-rows-[minmax(0,1fr)_auto] gap-2">
          <div className="min-h-0 flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1 min-h-0">
              {editing ? (
                <Input
                  ref={inputRef}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={commitEdit}
                  onKeyDown={handleKeyDown}
                  onClick={(e) => e.stopPropagation()}
                  className="w-full h-auto text-sm font-semibold text-foreground leading-snug bg-background border border-primary/40 rounded-lg px-2 py-0.5 focus-visible:ring-2 focus-visible:ring-ring"
                  maxLength={200}
                />
              ) : (
                <div className="flex items-start gap-1">
                  <h3
                    className="flex-1 min-w-0 text-sm font-semibold text-foreground leading-snug line-clamp-3 [overflow-wrap:anywhere]"
                    title={course.title}
                  >
                    {course.title}
                  </h3>
                  {course.is_owner && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={startEdit}
                      className="flex-shrink-0 p-0.5 h-auto w-auto rounded-md text-muted-foreground/60 hover:text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
                      aria-label="Rename course"
                    >
                      <EditIcon />
                    </Button>
                  )}
                </div>
              )}
            </div>
            <div className="flex-shrink-0 -mr-0.5 -mt-0.5">
              <CourseMenu courseId={course.id} onDelete={onDelete} />
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap flex-shrink-0">
            {formatDate(course.created_at) && (
              <span className="text-xs text-muted-foreground">{formatDate(course.created_at)}</span>
            )}
            {isCoCreator && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-accent text-primary border border-accent font-medium">
                Co-creator
              </span>
            )}
            {course.status && course.status !== "draft" && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${
                course.status === "published"
                  ? "bg-green-50 text-green-600 border-green-100"
                  : "bg-muted text-muted-foreground border-border"
              }`}>
                {course.status}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CardViewer({ onCreateNew }) {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch("/api/course", {
      credentials: "include",
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setCourses(data.courses || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (courseId) => {
    setCourses((prev) => prev.filter((c) => c.id !== courseId));
    try {
      const res = await fetch("/api/course", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ course_id: courseId }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `HTTP ${res.status}`);
      }
    } catch (e) {
      // Rollback optimistic removal on failure
      setError(`Failed to delete course: ${e.message}`);
      fetch("/api/course", { credentials: "include" })
        .then((r) => r.json())
        .then((data) => setCourses(data.courses || []));
    }
  };

  const handleCardClick = (course) => {
    navigate(`/course/${course.id}`, { state: { course } });
  };

  const handleRename = async (courseId, newTitle) => {
    setCourses((prev) => prev.map((c) => c.id === courseId ? { ...c, title: newTitle } : c));
    try {
      const res = await fetch("/api/course", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ course_id: courseId, title: newTitle }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `HTTP ${res.status}`);
      }
    } catch (e) {
      setError(`Failed to rename course: ${e.message}`);
      fetch("/api/course", { credentials: "include" })
        .then((r) => r.json())
        .then((data) => setCourses(data.courses || []));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-4 border-border border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-24 text-destructive text-sm">{error}</div>
    );
  }

  return (
    <div>
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
        Your Courses
      </h2>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {/* Create new card */}
        <Button
          type="button"
          variant="ghost"
          onClick={onCreateNew}
          className="h-44 w-full bg-background/60 border border-dashed border-border rounded-2xl flex flex-col items-center justify-center gap-2 text-muted-foreground hover:text-primary hover:border-primary/40 hover:bg-accent/40"
        >
          <div className="w-10 h-10 rounded-full border-2 border-current flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </div>
          <span className="text-sm font-medium">New course</span>
        </Button>

        {courses.map((course) => (
          <CourseCard
            key={course.id}
            course={course}
            onDelete={handleDelete}
            onClick={handleCardClick}
            onRename={handleRename}
          />
        ))}
      </div>

      {courses.length === 0 && (
        <p className="text-sm text-muted-foreground mt-6 text-center">
          No courses yet — create your first one above.
        </p>
      )}
    </div>
  );
}
