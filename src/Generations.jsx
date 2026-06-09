import { useEffect, useMemo, useState } from 'react';
import Quiz from './Quiz.jsx';
import Flashcards from './Flashcards.jsx';
import Reports from './Reports.jsx';

// ─── Tab icons ────────────────────────────────────────────────────────────────

function QuizIcon({ size = 14 }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
    </svg>
  );
}

function FlashcardsIcon({ size = 14 }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="6" width="20" height="13" rx="2" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

function ReportsIcon({ size = 14 }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="16" y2="17" />
    </svg>
  );
}

// ─── Tab definitions ──────────────────────────────────────────────────────────

const TABS = [
  { id: 'quiz',       label: 'Custom Quizzes',     Icon: QuizIcon       },
  { id: 'flashcards', label: 'Custom Flashcards',   Icon: FlashcardsIcon },
  { id: 'reports',    label: 'Custom Reports',      Icon: ReportsIcon    },
];

// ─── Generations ─────────────────────────────────────────────────────────────

export default function Generations({ course, userData, onAddSource }) {
  const storageKey = useMemo(
    () => `coursemate_generations_tab_${course?.id || 'global'}`,
    [course?.id]
  );

  const [activeTab, setActiveTab] = useState(() => {
    const saved = localStorage.getItem(storageKey);
    return TABS.some((t) => t.id === saved) ? saved : 'quiz';
  });

  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    setActiveTab(TABS.some((t) => t.id === saved) ? saved : 'quiz');
  }, [storageKey]);

  useEffect(() => {
    localStorage.setItem(storageKey, activeTab);
  }, [activeTab, storageKey]);

  return (
    <div className="flex flex-col gap-4">

      {/* ── Tab header ── */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm px-2 py-2 flex items-center gap-1">
        {TABS.map(({ id, label, Icon }) => {
          const active = activeTab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
                active
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          );
        })}
      </div>

      {/* ── Active generator ── */}
      {activeTab === 'quiz' && (
        <Quiz course={course} onAddSource={onAddSource} />
      )}
      {activeTab === 'flashcards' && (
        <Flashcards course={course} onAddSource={onAddSource} />
      )}
      {activeTab === 'reports' && (
        <Reports course={course} onAddSource={onAddSource} />
      )}

    </div>
  );
}
