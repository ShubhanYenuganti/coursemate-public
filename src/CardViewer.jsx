import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

/** Deterministic indigo/cyan/violet accent from a string */
function cardAccent(title) {
  const accents = [
    "from-indigo-400 to-indigo-600",
    "from-cyan-400 to-cyan-600",
    "from-violet-400 to-violet-600",
    "from-blue-400 to-blue-600",
    "from-teal-400 to-teal-600",
    "from-sky-400 to-sky-600",
  ];
  let hash = 0;
  for (let i = 0; i < title.length; i++) hash = (hash * 31 + title.charCodeAt(i)) | 0;
  return accents[Math.abs(hash) % accents.length];
}

function formatDate(dateStr) {
  if (!dateStr) return null;
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
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
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        aria-label="Course options"
      >
        <DotsIcon />
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-20 w-36 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setOpen(false); onDelete(courseId); }}
            className="w-full text-left px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

function CourseCard({ course, onDelete, onClick }) {
  const accent = cardAccent(course.title);
  const initial = course.title.trim()[0]?.toUpperCase() || "?";
  const isCoCreator = !course.is_owner;

  return (
    <div
      onClick={() => onClick(course)}
      className="group relative bg-white/80 backdrop-blur-sm border border-gray-200 rounded-2xl shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer flex flex-col overflow-hidden"
    >
      {/* Card top: icon + menu */}
      <div className="flex items-start justify-between p-4 pb-0">
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${accent} flex items-center justify-center flex-shrink-0`}>
          <span className="text-xl font-bold text-white">{initial}</span>
        </div>
        <CourseMenu courseId={course.id} onDelete={onDelete} />
      </div>

      {/* Card bottom: title + meta */}
      <div className="p-4 pt-3 mt-auto">
        <h3 className="text-base font-semibold text-gray-900 leading-snug line-clamp-2 mb-1.5">
          {course.title}
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          {formatDate(course.created_at) && (
            <span className="text-xs text-gray-400">{formatDate(course.created_at)}</span>
          )}
          {isCoCreator && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-500 border border-indigo-100 font-medium">
              Co-creator
            </span>
          )}
          {course.status && course.status !== "draft" && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${
              course.status === "published"
                ? "bg-green-50 text-green-600 border-green-100"
                : "bg-gray-50 text-gray-400 border-gray-200"
            }`}>
              {course.status}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CardViewer({ sessionToken, onCreateNew }) {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionToken) return;
    setLoading(true);
    fetch("/api/get_courses", {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setCourses(data.courses || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sessionToken]);

  const handleDelete = async (courseId) => {
    setCourses((prev) => prev.filter((c) => c.id !== courseId));
    try {
      const res = await fetch("/api/delete_course", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionToken}`,
        },
        body: JSON.stringify({ course_id: courseId }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `HTTP ${res.status}`);
      }
    } catch (e) {
      // Rollback optimistic removal on failure
      setError(`Failed to delete course: ${e.message}`);
      fetch("/api/get_courses", { headers: { Authorization: `Bearer ${sessionToken}` } })
        .then((r) => r.json())
        .then((data) => setCourses(data.courses || []));
    }
  };

  const handleCardClick = (course) => {
    navigate(`/course/${course.id}`, { state: { course } });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-4 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-24 text-red-500 text-sm">{error}</div>
    );
  }

  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
        Your Courses
      </h2>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {/* Create new card */}
        <button
          type="button"
          onClick={onCreateNew}
          className="bg-white/60 border border-dashed border-gray-300 rounded-2xl flex flex-col items-center justify-center gap-2 py-8 text-gray-400 hover:text-indigo-500 hover:border-indigo-300 hover:bg-indigo-50/40 transition-all duration-200 cursor-pointer min-h-[160px]"
        >
          <div className="w-10 h-10 rounded-full border-2 border-current flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </div>
          <span className="text-sm font-medium">New course</span>
        </button>

        {courses.map((course) => (
          <CourseCard
            key={course.id}
            course={course}
            onDelete={handleDelete}
            onClick={handleCardClick}
          />
        ))}
      </div>

      {courses.length === 0 && (
        <p className="text-sm text-gray-400 mt-6 text-center">
          No courses yet — create your first one above.
        </p>
      )}
    </div>
  );
}
