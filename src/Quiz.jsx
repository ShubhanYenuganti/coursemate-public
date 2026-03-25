import { useState, useEffect } from 'react';

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

function Stepper({ value, onChange, min = 0, max = 99 }) {
  return (
    <div className="flex items-center gap-3 border border-gray-200 rounded-lg px-3 py-2 bg-white">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - 1))}
        className="text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-30"
        disabled={value <= min}
      >
        <MinusIcon />
      </button>
      <span className="text-sm font-semibold text-gray-900 w-5 text-center tabular-nums">{value}</span>
      <button
        type="button"
        onClick={() => onChange(Math.min(max, value + 1))}
        className="text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-30"
        disabled={value >= max}
      >
        <PlusIcon />
      </button>
    </div>
  );
}

// ─── Quiz component ───────────────────────────────────────────────────────────

export default function Quiz({ course, sessionToken, onAddSource }) {
  const [materials, setMaterials] = useState([]);
  const [selectedSources, setSelectedSources] = useState(new Set());
  const [selectAll, setSelectAll] = useState(true);
  const [materialsLoading, setMaterialsLoading] = useState(true);

  // Quiz config
  const [topic, setTopic] = useState('');
  const [tfCount, setTfCount] = useState(5);
  const [saCount, setSaCount] = useState(3);
  const [laCount, setLaCount] = useState(2);
  const [mcqCount, setMcqCount] = useState(10);
  const [mcqOptions, setMcqOptions] = useState(4);

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState('');

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

  const selectedCount = selectAll ? materials.length : selectedSources.size;
  const totalQuestions = tfCount + saCount + laCount + mcqCount;

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
          resource: 'quiz',
          course_id: course?.id,
          topic,
          tf_count: tfCount,
          sa_count: saCount,
          la_count: laCount,
          mcq_count: mcqCount,
          mcq_options: mcqOptions,
          material_ids: contextIds,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setGenerateError(err.error || 'Generation failed. Please try again.');
      }
    } catch {
      setGenerateError('Something went wrong. Please try again.');
    } finally {
      setGenerating(false);
    }
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
          <p className="text-[10px] text-gray-400 leading-snug">Select sources to include in generation</p>
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

      {/* ── Quiz config form ── */}
      <div className="flex-1 min-w-0 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col gap-5">
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-1">Custom Quiz Generator</h2>
          <p className="text-sm text-gray-500">Configure your quiz parameters and generate questions from your selected sources.</p>
        </div>

        {/* Primary topic */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Primary Topic</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Reinforcement Learning, Neural Networks..."
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-colors"
          />
        </div>

        {/* Question type counts */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">True / False Questions</label>
            <Stepper value={tfCount} onChange={setTfCount} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Short Answer Questions</label>
            <Stepper value={saCount} onChange={setSaCount} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Long Answer Questions</label>
            <Stepper value={laCount} onChange={setLaCount} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Multiple Choice (MCQ)</label>
            <Stepper value={mcqCount} onChange={setMcqCount} />
          </div>
        </div>

        {/* MCQ option count */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-2">MCQ Option Count</label>
          <div className="flex gap-2 p-1 bg-gray-100 rounded-lg w-fit">
            {[4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setMcqOptions(n)}
                className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  mcqOptions === n
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                {n} Options
              </button>
            ))}
          </div>
        </div>

        {/* Summary */}
        {totalQuestions > 0 && (
          <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-indigo-50 border border-indigo-100">
            <SparkleIcon />
            <span className="text-xs text-indigo-700">
              <span className="font-semibold">{totalQuestions} questions</span> will be generated
              {' '}({tfCount} T/F · {saCount} SA · {laCount} LA · {mcqCount} MCQ)
            </span>
          </div>
        )}

        {/* Error */}
        {generateError && (
          <p className="text-xs text-red-600">{generateError}</p>
        )}

        {/* Generate button */}
        <button
          type="button"
          onClick={handleGenerate}
          disabled={generating || totalQuestions === 0 || selectedCount === 0}
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
              Generate Quiz
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
