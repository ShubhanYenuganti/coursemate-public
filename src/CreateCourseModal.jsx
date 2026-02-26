import { useState, forwardRef, useImperativeHandle } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";

function NotebookIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 6h4" />
      <path d="M2 10h4" />
      <path d="M2 14h4" />
      <path d="M2 18h4" />
      <rect x="6" y="3" width="16" height="18" rx="2" />
      <line x1="12" y1="9" x2="16" y2="9" />
      <line x1="12" y1="13" x2="16" y2="13" />
    </svg>
  );
}

const CreateCourseModal = forwardRef(function CreateCourseModal({ sessionToken }, ref) {
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  useImperativeHandle(ref, () => ({
    open: () => {
      setTitle("");
      setDescription("");
      setError(null);
      setShowModal(true);
    },
  }));

  const openModal = () => {
    setTitle("");
    setDescription("");
    setError(null);
    setShowModal(true);
  };

  const closeModal = () => {
    if (!creating) setShowModal(false);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    setCreating(true);
    setError(null);

    try {
      const res = await fetch("/api/create_course", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionToken}`,
        },
        body: JSON.stringify({ title: title.trim(), description: description.trim() || undefined }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setShowModal(false);
      navigate(`/course/${data.course.id}`, { state: { course: data.course } });
    } catch (e) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={openModal}
        className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
        title="New course"
        aria-label="New course"
      >
        <NotebookIcon />
      </button>

      {showModal && createPortal(
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center px-4 z-50"
          onClick={closeModal}
        >
          <div
            className="bg-white/90 backdrop-blur-md rounded-2xl shadow-[0_8px_40px_rgba(0,0,0,0.2)] w-full max-w-md p-8 border border-white/60"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-xl font-bold text-gray-900 mb-6">New Course</h2>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="course-title">
                  Title <span className="text-red-500">*</span>
                </label>
                <input
                  id="course-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Introduction to Machine Learning"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 text-gray-900 placeholder-gray-400 text-sm"
                  autoFocus
                  disabled={creating}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="course-desc">
                  Description <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <textarea
                  id="course-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What is this course about?"
                  rows={3}
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400 text-gray-900 placeholder-gray-400 text-sm resize-none"
                  disabled={creating}
                />
              </div>

              {error && (
                <p className="text-red-600 text-sm">{error}</p>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={creating}
                  className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-gray-700 text-sm font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !title.trim()}
                  className="flex-1 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {creating ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                      Creating…
                    </>
                  ) : (
                    "Create Course"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </>
  );
});

export default CreateCourseModal;
