import { useState, useEffect } from 'react';
import FlashcardViewer from './FlashcardViewer';

// ─── icons ────────────────────────────────────────────────────────────────────

function PlusIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function MinusIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function SparkleIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
    </svg>
  );
}

// ─── shared mini-components ───────────────────────────────────────────────────

const FILE_TYPE_MAP = {
  pdf:  { label: 'PDF', bg: 'bg-rose-100',   text: 'text-rose-600'   },
  doc:  { label: 'DOC', bg: 'bg-blue-100',   text: 'text-blue-600'   },
  docx: { label: 'DOC', bg: 'bg-blue-100',   text: 'text-blue-600'   },
  xls:  { label: 'XLS', bg: 'bg-green-100',  text: 'text-green-700'  },
  xlsx: { label: 'XLS', bg: 'bg-green-100',  text: 'text-green-700'  },
  csv:  { label: 'CSV', bg: 'bg-green-100',  text: 'text-green-700'  },
  png:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  jpg:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  jpeg: { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  gif:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  svg:  { label: 'SVG', bg: 'bg-orange-100', text: 'text-orange-600' },
  txt:  { label: 'TXT', bg: 'bg-gray-100',   text: 'text-gray-500'   },
};

function FileTypeBadge({ name }) {
  const ext = (name || '').split('.').pop().toLowerCase();
  const style = FILE_TYPE_MAP[ext] || { label: ext.slice(0, 3).toUpperCase() || 'DOC', bg: 'bg-gray-100', text: 'text-gray-500' };
  return (
    <span className={`flex-shrink-0 inline-flex items-center justify-center w-[22px] h-[16px] rounded text-[7px] font-bold tracking-tight ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

function SourceToggle({ checked, onToggle }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
      className={`flex-shrink-0 relative inline-flex h-4 w-7 items-center rounded-full transition-colors focus:outline-none ${
        checked ? 'bg-indigo-500' : 'bg-gray-200'
      }`}
    >
      <span className={`inline-block h-3 w-3 transform rounded-full bg-white shadow-sm transition-transform ${
        checked ? 'translate-x-3.5' : 'translate-x-0.5'
      }`} />
    </button>
  );
}

// ─── depth config ─────────────────────────────────────────────────────────────

const DEPTH_OPTIONS = [
  {
    id: 'brief',
    label: 'Brief',
    description: 'Concise definitions with essential information',
    backPreview: 'A concise definition will appear here.',
  },
  {
    id: 'moderate',
    label: 'Moderate',
    description: 'Balanced explanations with key context',
    backPreview: 'A balanced explanation with key context will appear here.',
  },
  {
    id: 'in-depth',
    label: 'In-Depth',
    description: 'Comprehensive explanations with examples and detail',
    backPreview: 'A comprehensive explanation with examples will appear here.',
  },
];

// ─── Flashcards component ─────────────────────────────────────────────────────

export default function Flashcards({ course, sessionToken, onAddSource }) {
  const [materials, setMaterials] = useState([]);
  const [selectedSources, setSelectedSources] = useState(new Set());
  const [selectAll, setSelectAll] = useState(true);
  const [materialsLoading, setMaterialsLoading] = useState(true);

  // Flashcard config
  const [topic, setTopic] = useState('');
  const [cardCount, setCardCount] = useState(20);
  const [depth, setDepth] = useState('moderate');

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState('');
  const [flashcardData, setFlashcardData] = useState(null);

  useEffect(() => {
    if (!course?.id || !sessionToken) return;
    setMaterialsLoading(true);
    fetch(`/api/materials?course_id=${course.id}`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {})
      .finally(() => setMaterialsLoading(false));
  }, [course?.id, sessionToken]);

  function isSourceSelected(id) {
    return selectAll || selectedSources.has(id);
  }

  function toggleSource(id) {
    setSelectAll(false);
    setSelectedSources((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selectAll) {
      setSelectAll(false);
      setSelectedSources(new Set());
    } else {
      setSelectAll(true);
      setSelectedSources(new Set());
    }
  }

  const selectedCount = selectAll ? materials.length : selectedSources.size;
  const activeDepth = DEPTH_OPTIONS.find((d) => d.id === depth);

  async function handleGenerate() {
    if (generating) return;
    setGenerateError('');
    setGenerating(true);
    try {
      const contextIds = selectAll
        ? materials.map((m) => m.id)
        : Array.from(selectedSources);
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          resource: 'flashcards',
          course_id: course?.id,
          topic,
          card_count: cardCount,
          depth,
          material_ids: contextIds,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setGenerateError(err.error || 'Generation failed. Please try again.');
      } else {
        const data = await res.json().catch(() => null);
        if (data) setFlashcardData(data);
      }
    } catch {
      setGenerateError('Something went wrong. Please try again.');
    } finally {
      setGenerating(false);
    }
  }

  if (flashcardData) {
    return (
      <FlashcardViewer
        data={flashcardData}
        course={course}
        onClose={() => setFlashcardData(null)}
        onRegenerate={() => { setFlashcardData(null); handleGenerate(); }}
      />
    );
  }

  return (
    <div className="flex gap-4 items-start">

      {/* ── Sources sidebar ── */}
      <div className="w-[220px] flex-shrink-0 bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col overflow-hidden" style={{ minHeight: '520px' }}>
        <div className="px-4 pt-4 pb-2">
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Sources</span>
            <span className="text-[10px] text-gray-400 tabular-nums">{selectedCount}/{materials.length}</span>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-[10px] text-gray-400 leading-snug">Select sources to include in generation</p>
            <SourceToggle checked={selectAll} onToggle={toggleSelectAll} />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
          {materialsLoading && (
            <p className="px-3 py-2 text-[10px] text-gray-400">Loading…</p>
          )}
          {!materialsLoading && materials.length === 0 && (
            <p className="px-3 py-2 text-[10px] text-gray-400 italic">No materials yet.</p>
          )}
          {materials.map((m) => {
            const on = isSourceSelected(m.id);
            return (
              <div
                key={m.id}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-50 transition-colors cursor-default border-l-2 ${
                  on ? 'border-indigo-400' : 'border-transparent'
                }`}
              >
                <FileTypeBadge name={m.name} />
                <span className="flex-1 truncate min-w-0 text-xs" title={m.name}>{m.name}</span>
                <SourceToggle checked={on} onToggle={() => toggleSource(m.id)} />
              </div>
            );
          })}
        </div>

        <div className="px-3 py-3 flex-shrink-0 border-t border-gray-100">
          <button
            type="button"
            onClick={onAddSource}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-dashed border-gray-300 text-xs text-gray-500 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
          >
            <PlusIcon />
            Add Source
          </button>
        </div>
      </div>

      {/* ── Flashcard config form ── */}
      <div className="flex-1 min-w-0 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col gap-5">
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-1">Custom Flashcard Generator</h2>
          <p className="text-sm text-gray-500">Generate study flashcards from your selected sources with customizable depth.</p>
        </div>

        {/* Primary topic */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Primary Topic</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Kinematics, Control Systems..."
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-colors"
          />
        </div>

        {/* Number of flashcards */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Number of Flashcards</label>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3 border border-gray-200 rounded-lg px-3 py-2 bg-white">
              <button
                type="button"
                onClick={() => setCardCount((c) => Math.max(1, c - 1))}
                disabled={cardCount <= 1}
                className="text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-30"
              >
                <MinusIcon />
              </button>
              <span className="text-sm font-semibold text-gray-900 w-5 text-center tabular-nums">{cardCount}</span>
              <button
                type="button"
                onClick={() => setCardCount((c) => Math.min(100, c + 1))}
                disabled={cardCount >= 100}
                className="text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-30"
              >
                <PlusIcon />
              </button>
            </div>
            <span className="text-sm text-gray-400">{cardCount} cards</span>
          </div>
        </div>

        {/* Definition depth */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Definition Depth</label>
          <div className="flex gap-1 p-1 bg-gray-100 rounded-lg w-fit mb-2">
            {DEPTH_OPTIONS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setDepth(id)}
                className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  depth === id
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {activeDepth && (
            <p className="text-xs text-gray-500">{activeDepth.description}</p>
          )}
        </div>

        {/* Preview card */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Preview Card</p>
          <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
            <div>
              <p className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider mb-1">Front</p>
              <p className="text-sm text-gray-400 italic">
                {topic.trim() ? topic : 'What is your topic?'}
              </p>
            </div>
            <div className="border-t border-gray-100 pt-3">
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">Back</p>
              <p className="text-sm text-gray-400 italic">
                {activeDepth?.backPreview}
              </p>
            </div>
          </div>
        </div>

        {/* Error */}
        {generateError && (
          <p className="text-xs text-red-600">{generateError}</p>
        )}

        {/* Generate button */}
        <button
          type="button"
          onClick={handleGenerate}
          disabled={generating || selectedCount === 0}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
        >
          {generating ? (
            <>
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Generating…
            </>
          ) : (
            <>
              <SparkleIcon />
              Generate {cardCount} Flashcards
            </>
          )}
        </button>

        <p className="text-[10px] text-gray-400 flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
          AI responses are based on your selected course materials.{' '}
          <a href="#" className="text-indigo-500 hover:underline">Learn more</a>
        </p>
      </div>

    </div>
  );
}
