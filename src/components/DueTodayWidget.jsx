import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function DueTodayWidget({ courseId }) {
  const [due, setDue] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!courseId) return;
    fetch(`/api/flashcards?action=due&course_id=${courseId}`, { credentials: 'include' })
      .then((r) => r.json())
      .then(setDue)
      .catch(() => {});
  }, [courseId]);

  if (!due || !due.due_count) return null;

  return (
    <button
      onClick={() => due.next && navigate(`/course/${due.next.course_id}/flashcards/${due.next.generation_id}`)}
      className="w-full rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-left hover:bg-indigo-100 transition-colors"
    >
      <div className="text-2xl font-bold text-indigo-700">{due.due_count}</div>
      <div className="text-xs text-indigo-600">cards due today - review now</div>
    </button>
  );
}
