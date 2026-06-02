import React, { useEffect, useState } from 'react';

function Stat({ label, value }) {
  return (
    <div className="flex flex-col items-center px-4 py-3">
      <span className="text-2xl font-semibold text-gray-900 tabular-nums">{value ?? '—'}</span>
      <span className="text-[11px] text-gray-500 uppercase tracking-wide">{label}</span>
    </div>
  );
}

export default function CourseStatsWidget({ courseId }) {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    if (!courseId) return;
    fetch(`/api/course?action=stats&course_id=${courseId}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then(setStats)
      .catch(() => {});
  }, [courseId]);
  if (!stats) return null;
  return (
    <div className="flex flex-wrap items-center divide-x divide-gray-100 rounded-xl border border-gray-100 bg-white/70">
      <Stat label="Materials" value={stats.materials} />
      <Stat label="Generations" value={stats.generations?.total} />
      <Stat label="Chats" value={stats.chats} />
      <Stat label="Messages" value={stats.messages} />
    </div>
  );
}
