import { useState, useMemo } from 'react';
import { formatDateTime } from './utils/dateUtils';

// ─── Icons ─────────────────────────────────────────────────────────────────────

function RefreshIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </svg>
  );
}

function BookmarkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18" /><path d="m6 6 12 12" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function ArrowLeftIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

function SpeakerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}

// ─── Answer sub-components ─────────────────────────────────────────────────────

function MCQContent({ options, selected, onSelect, revealed, correct }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-3">Choose an answer</p>
      <div className="grid grid-cols-2 gap-2">
        {(options || []).map((opt, i) => {
          const optText = typeof opt === 'string' ? opt : (opt.text || opt.label || String(opt));
          const isSelected = selected === optText;
          const isCorrect = revealed && (optText === correct || i === correct);
          const isWrong = revealed && isSelected && !isCorrect;
          return (
            <button
              key={i}
              type="button"
              onClick={() => !revealed && onSelect(optText)}
              className={`px-4 py-3 rounded-lg border text-sm text-center transition-colors ${
                isCorrect ? 'border-green-400 bg-green-50 text-green-700' :
                isWrong   ? 'border-red-300 bg-red-50 text-red-600' :
                isSelected ? 'border-indigo-400 bg-indigo-50 text-indigo-700' :
                'border-gray-200 bg-white text-gray-700 hover:border-indigo-300 hover:bg-indigo-50'
              } ${revealed ? 'cursor-default' : 'cursor-pointer'}`}
            >
              {optText}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TrueFalseContent({ selected, onSelect, revealed, correct }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-3">Choose an answer</p>
      <div className="flex flex-col gap-2">
        {['True', 'False'].map((opt) => {
          const isSelected = selected === opt;
          const isCorrect = revealed && String(correct).toLowerCase() === opt.toLowerCase();
          const isWrong = revealed && isSelected && !isCorrect;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => !revealed && onSelect(opt)}
              className={`w-full px-4 py-3 rounded-lg border text-sm text-center transition-colors ${
                isCorrect ? 'border-green-400 bg-green-50 text-green-700' :
                isWrong   ? 'border-red-300 bg-red-50 text-red-600' :
                isSelected ? 'border-indigo-400 bg-indigo-50 text-indigo-700' :
                'border-gray-200 bg-white text-gray-700 hover:border-indigo-300 hover:bg-indigo-50'
              } ${revealed ? 'cursor-default' : 'cursor-pointer'}`}
            >
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ShortAnswerContent({ value, onChange, revealed, expectedAnswer, explanation }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-3">Your answer</p>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={revealed}
        placeholder="Type your answer here..."
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 disabled:bg-gray-50 disabled:text-gray-500 transition-colors"
      />
      {revealed && (
        <div className="mt-3 space-y-2">
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Expected</p>
            <div className="rounded-lg border border-green-200 bg-green-50/70 px-3 py-2 text-sm text-gray-800 whitespace-pre-wrap">
              {expectedAnswer || ''}
            </div>
          </div>
          {explanation && (
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Explanation</p>
              <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-700 whitespace-pre-wrap">
                {explanation}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function LongAnswerContent({ value, onChange, revealed, expectedAnswer, explanation }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-3">Your answer</p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={revealed}
        placeholder="Type your detailed answer here..."
        rows={4}
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 disabled:bg-gray-50 disabled:text-gray-500 transition-colors resize-none"
      />
      {revealed && (
        <div className="mt-3 space-y-2">
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Expected</p>
            <div className="rounded-lg border border-green-200 bg-green-50/70 px-3 py-2 text-sm text-gray-800 whitespace-pre-wrap">
              {expectedAnswer || ''}
            </div>
          </div>
          {explanation && (
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Explanation</p>
              <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-700 whitespace-pre-wrap">
                {explanation}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Question Card ─────────────────────────────────────────────────────────────

function QuestionCard({ question, index, total, answer, onAnswer, revealed, onReveal }) {
  const type = (question.type || '').toLowerCase();
  const questionText = question.question || question.text || '';
  const isSelectType = type === 'mcq' || type === 'multiple_choice' || type === 'tf' || type === 'true_false';
  const hasAnswer = answer !== undefined && answer !== null && String(answer).trim() !== '';

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-indigo-600 tracking-widest uppercase">Term</span>
          <span className="text-gray-400">
            <SpeakerIcon />
          </span>
        </div>
        <span className="text-xs text-gray-400 tabular-nums">{index + 1} of {total}</span>
      </div>

      <p className="text-sm font-medium text-gray-900 mb-5 leading-relaxed">{questionText}</p>

      {(type === 'mcq' || type === 'multiple_choice') && (
        <MCQContent
          options={question.options}
          selected={answer}
          onSelect={onAnswer}
          revealed={revealed}
          correct={question.answer}
        />
      )}
      {(type === 'tf' || type === 'true_false') && (
        <TrueFalseContent
          selected={answer}
          onSelect={onAnswer}
          revealed={revealed}
          correct={question.answer}
        />
      )}
      {(type === 'sa' || type === 'short_answer') && (
        <ShortAnswerContent
          value={answer || ''}
          onChange={onAnswer}
          revealed={revealed}
          expectedAnswer={question.answer}
          explanation={question.explanation}
        />
      )}
      {(type === 'la' || type === 'long_answer') && (
        <LongAnswerContent
          value={answer || ''}
          onChange={onAnswer}
          revealed={revealed}
          expectedAnswer={question.answer}
          explanation={question.explanation}
        />
      )}

      {revealed && isSelectType && question.explanation && (
        <div className="mt-4">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Explanation</p>
          <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-700">
            {question.explanation}
          </div>
        </div>
      )}

      {!revealed && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={onReveal}
            className="text-xs text-indigo-500 hover:text-indigo-700 hover:underline transition-colors"
          >
            {hasAnswer ? 'Show the answer' : 'Show the answer'}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── QuizViewer ────────────────────────────────────────────────────────────────

export default function QuizViewer({ quiz, generationId, parentGenerationId, onClose, onRegenerate, onResolve }) {
  const quizDownloadName = ((quiz?.title || 'quiz')
    .toString()
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || `quiz-${generationId || 'export'}`) + '.pdf';
  // Shuffle questions once per quiz load, preserving originalIndex for backend submission.
  const questions = useMemo(() => {
    const raw = quiz?.questions || (Array.isArray(quiz) ? quiz : []);
    return [...raw].map((q, i) => ({ ...q, originalIndex: i })).sort(() => Math.random() - 0.5);
  }, [quiz?.generation_id]); // eslint-disable-line react-hooks/exhaustive-deps
  const total = questions.length;

  const [answers, setAnswers] = useState({});
  const [revealed, setRevealed] = useState({});
  const answeredCount = Object.values(answers).filter((v) => v !== undefined && v !== null && String(v).trim() !== '').length;
  const [saveStatus, setSaveStatus] = useState(quiz?.artifact_material_id ? 'saved' : 'idle');
  const [resolving, setResolving] = useState(false);

  const [attemptStatus, setAttemptStatus] = useState('idle'); // idle | submitting | submitted | error
  const [attemptResult, setAttemptResult] = useState(null);
  const [exportStatus, setExportStatus] = useState('idle'); // idle | exporting | error

  // Attempt history
  const [viewMode, setViewMode] = useState('quiz'); // 'quiz' | 'attempts' | 'attempt-detail'
  const [attemptsList, setAttemptsList] = useState([]);
  const [attemptsLoading, setAttemptsLoading] = useState(false);
  const [selectedAttempt, setSelectedAttempt] = useState(null);
  const [attemptDetailLoading, setAttemptDetailLoading] = useState(false);

  async function loadAttempts() {
    if (!generationId) return;
    setAttemptsLoading(true);
    try {
      const r = await fetch(`/api/quiz?action=list_attempts&generation_id=${generationId}`, {
        credentials: 'include',
      });
      const data = await r.json().catch(() => ({}));
      setAttemptsList(Array.isArray(data?.attempts) ? data.attempts : []);
    } catch { /* ignore */ }
    finally { setAttemptsLoading(false); }
  }

  async function openAttemptDetail(attemptId) {
    setAttemptDetailLoading(true);
    setViewMode('attempt-detail');
    try {
      const r = await fetch(`/api/quiz?action=get_attempt&attempt_id=${attemptId}`, {
        credentials: 'include',
      });
      const data = await r.json().catch(() => null);
      setSelectedAttempt(data);
    } catch { setSelectedAttempt(null); }
    finally { setAttemptDetailLoading(false); }
  }

  function showAttempts() {
    setViewMode('attempts');
    loadAttempts();
  }

  function backToQuiz() {
    setViewMode('quiz');
    setSelectedAttempt(null);
  }

  async function handleSubmitAttempt() {
    if (!generationId || attemptStatus === 'submitting') return;
    setAttemptStatus('submitting');

    try {
      // Map display-index answers back to original DB question_index for the backend.
      const answers_by_index = {};
      for (const [k, v] of Object.entries(answers || {})) {
        if (v === undefined || v === null) continue;
        const s = String(v);
        if (!s.trim()) continue;
        const q = questions[parseInt(k)];
        if (q) answers_by_index[q.originalIndex] = s;
      }

      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          action: 'submit_attempt',
          generation_id: generationId,
          answers_by_index,
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

      setAttemptResult(data);
      setAttemptStatus('submitted');
      // Reveal all questions so correct answers + explanations are shown.
      const allRevealed = {};
      questions.forEach((_, i) => { allRevealed[i] = true; });
      setRevealed(allRevealed);
    } catch (e) {
      setAttemptResult(null);
      setAttemptStatus('error');
    }
  }

  async function handleExportPdf() {
    if (!generationId || exportStatus === 'exporting') return;
    setExportStatus('exporting');

    try {
      const res = await fetch(`/api/quiz?action=export_pdf&generation_id=${generationId}`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = quizDownloadName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportStatus('idle');
    } catch (e) {
      setExportStatus('error');
    }
  }

  function setAnswer(index, value) {
    setAnswers((prev) => ({ ...prev, [index]: value }));
  }

  function revealAnswer(index) {
    setRevealed((prev) => ({ ...prev, [index]: true }));
  }

  async function handleSave() {
    if (!generationId || saveStatus === 'saving' || saveStatus === 'saved') return;
    setSaveStatus('saving');
    try {
      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ action: 'save_artifact', generation_id: generationId }),
      });
      if (res.ok) {
        setSaveStatus('saved');
      } else {
        setSaveStatus('error');
      }
    } catch {
      setSaveStatus('error');
    }
  }

  async function handleResolve(resolution) {
    if (!parentGenerationId || !generationId || resolving) return;
    setResolving(true);
    try {
      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          action: 'resolve_regeneration',
          generation_id: generationId,
          parent_generation_id: parentGenerationId,
          resolution,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        onResolve?.(resolution, data.generation || null);
      }
    } catch {
      // keep banner visible to allow retry
    } finally {
      setResolving(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-blue-50 flex flex-col">
      {parentGenerationId && (
        <div className="bg-amber-50 border-b border-amber-200 px-8 py-3">
          <div className="max-w-5xl mx-auto flex items-center justify-between gap-4">
            <p className="text-sm text-amber-800 font-medium">
              New version generated. What would you like to do with the previous version?
            </p>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                type="button"
                onClick={() => handleResolve('save_both')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg border border-amber-300 text-xs font-medium text-amber-800 hover:bg-amber-100 transition-colors disabled:opacity-50"
              >
                Save Both
              </button>
              <button
                type="button"
                onClick={() => handleResolve('replace')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg border border-amber-300 text-xs font-medium text-amber-800 hover:bg-amber-100 transition-colors disabled:opacity-50"
              >
                Replace Previous
              </button>
              <button
                type="button"
                onClick={() => handleResolve('revert')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-medium hover:bg-amber-700 transition-colors disabled:opacity-50"
              >
                Revert
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b border-gray-100 px-8 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <span className="text-lg font-bold text-gray-900">CourseMate</span>

          <div className="text-center">
            {viewMode === 'quiz' ? (
              <>
                <p className="text-base font-semibold text-gray-900 tabular-nums leading-none">{answeredCount} / {total}</p>
                <p className="text-[10px] text-gray-400 mt-0.5">Quiz Progress</p>
              </>
            ) : viewMode === 'attempts' ? (
              <>
                <p className="text-base font-semibold text-gray-900 tabular-nums leading-none">{attemptsList.length}</p>
                <p className="text-[10px] text-gray-400 mt-0.5">Attempts</p>
              </>
            ) : (
              <>
                <p className="text-base font-semibold text-gray-900 tabular-nums leading-none">
                  {selectedAttempt ? `${(selectedAttempt.score_percent ?? 0).toFixed(0)}%` : '—'}
                </p>
                <p className="text-[10px] text-gray-400 mt-0.5">Score</p>
              </>
            )}
          </div>

          <div className="flex items-center gap-2">
            {viewMode !== 'quiz' ? (
              <button
                type="button"
                onClick={backToQuiz}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <ArrowLeftIcon />
                Back to Quiz
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => onRegenerate?.(quiz)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
                >
                  <RefreshIcon />
                  Regenerate
                </button>

                <button
                  type="button"
                  onClick={handleSubmitAttempt}
                  disabled={attemptStatus === 'submitting' || !generationId}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    attemptStatus === 'submitted'
                      ? 'border border-green-200 bg-green-50 text-green-700 cursor-default'
                      : attemptStatus === 'error'
                        ? 'border border-red-200 bg-red-50 text-red-700 hover:bg-red-50'
                        : 'border border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {attemptStatus === 'submitting' ? 'Grading…' : 'Submit Attempt'}
                </button>

                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saveStatus === 'saving' || saveStatus === 'saved'}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                    saveStatus === 'saved'
                      ? 'border-green-300 text-green-700 bg-green-50 cursor-default'
                      : saveStatus === 'error'
                        ? 'border-red-300 text-red-600 hover:bg-red-50'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <BookmarkIcon />
                  {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved ✓' : saveStatus === 'error' ? 'Retry Save' : 'Save Quiz'}
                </button>

                <button
                  type="button"
                  onClick={handleExportPdf}
                  disabled={!generationId || exportStatus === 'exporting'}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <DownloadIcon />
                  {exportStatus === 'exporting' ? 'Exporting…' : 'Export Quiz'}
                  <ChevronDownIcon />
                </button>
              </>
            )}

            <button
              type="button"
              onClick={showAttempts}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                viewMode !== 'quiz'
                  ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
                  : 'border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              <ClockIcon />
              Attempts
            </button>

            <div className="w-px h-5 bg-gray-200 mx-1" />
            <button
              type="button"
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <SettingsIcon />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <XIcon />
            </button>
          </div>
        </div>
      </header>

      {/* Main content — quiz / attempts list / attempt detail */}
      <main className="flex-1 py-8 px-4">

        {/* ── Quiz view ── */}
        {viewMode === 'quiz' && (
          <div className="max-w-2xl mx-auto flex flex-col gap-6">
            {attemptResult && (
              <div className="mb-2 rounded-xl border border-gray-200 bg-white px-4 py-3">
                <div className="text-xs font-semibold text-gray-900">
                  Score: {typeof attemptResult.score_percent === 'number' ? `${attemptResult.score_percent.toFixed(0)}%` : 'N/A'}
                </div>
                {attemptResult.manual_review_required && (
                  <div className="mt-2 text-xs font-medium text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    Manual review required for SA/LA responses.
                  </div>
                )}
              </div>
            )}
            {questions.length === 0 && (
              <p className="text-center text-sm text-gray-400 py-12">No questions generated.</p>
            )}
            {questions.map((q, i) => (
              <QuestionCard
                key={q.originalIndex}
                question={q}
                index={i}
                total={total}
                answer={answers[i]}
                onAnswer={(val) => setAnswer(i, val)}
                revealed={!!revealed[i]}
                onReveal={() => revealAnswer(i)}
              />
            ))}
          </div>
        )}

        {/* ── Attempts list ── */}
        {viewMode === 'attempts' && (
          <div className="max-w-2xl mx-auto">
            <h2 className="text-base font-semibold text-gray-900 mb-4">Past Attempts</h2>
            {attemptsLoading && (
              <div className="flex justify-center py-12">
                <div className="w-8 h-8 border-4 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
              </div>
            )}
            {!attemptsLoading && attemptsList.length === 0 && (
              <p className="text-sm text-gray-400 italic text-center py-12">No attempts yet. Submit the quiz to record your first attempt.</p>
            )}
            {!attemptsLoading && attemptsList.map((a) => {
              const score = typeof a.score_percent === 'number' ? a.score_percent : null;
              const scoreColor = score === null ? 'text-gray-500' : score >= 70 ? 'text-green-600' : score >= 40 ? 'text-amber-600' : 'text-red-600';
              return (
                <div key={a.attempt_id} className="flex items-center justify-between gap-4 bg-white rounded-xl border border-gray-200 px-4 py-3 mb-3">
                  <div>
                    <p className={`text-lg font-bold ${scoreColor}`}>
                      {score !== null ? `${score.toFixed(0)}%` : 'N/A'}
                    </p>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      {formatDateTime(a.submitted_at)}
                      {a.manual_review_count > 0 && <span className="ml-2 text-amber-600">· {a.manual_review_count} manual review</span>}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => openAttemptDetail(a.attempt_id)}
                    className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Review
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Attempt detail ── */}
        {viewMode === 'attempt-detail' && (
          <div className="max-w-2xl mx-auto flex flex-col gap-4">
            {attemptDetailLoading && (
              <div className="flex justify-center py-12">
                <div className="w-8 h-8 border-4 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
              </div>
            )}
            {!attemptDetailLoading && selectedAttempt && (
              <>
                {/* Score summary */}
                <div className="bg-white rounded-xl border border-gray-200 px-4 py-3 flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500">Score</p>
                    <p className={`text-2xl font-bold ${
                      typeof selectedAttempt.score_percent === 'number'
                        ? selectedAttempt.score_percent >= 70 ? 'text-green-600' : selectedAttempt.score_percent >= 40 ? 'text-amber-600' : 'text-red-600'
                        : 'text-gray-500'
                    }`}>
                      {typeof selectedAttempt.score_percent === 'number' ? `${selectedAttempt.score_percent.toFixed(0)}%` : 'N/A'}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[11px] text-gray-400">{formatDateTime(selectedAttempt.submitted_at)}</p>
                    {selectedAttempt.manual_review_count > 0 && (
                      <p className="text-[11px] text-amber-600 mt-0.5">{selectedAttempt.manual_review_count} question(s) need manual review</p>
                    )}
                  </div>
                </div>

                {/* Per-question review */}
                {(selectedAttempt.per_question || []).map((q, i) => {
                  const hasAnswer = q.user_response !== null && q.user_response !== undefined;
                  const isCorrect = q.is_correct === true;
                  const isSkipped = q.skipped === true || !hasAnswer;
                  const borderColor = isCorrect ? 'border-green-200' : isSkipped ? 'border-gray-200' : 'border-red-200';
                  const badge = isCorrect
                    ? <span className="px-2 py-0.5 rounded-full bg-green-50 border border-green-200 text-green-700 text-[10px] font-medium">Correct</span>
                    : isSkipped
                      ? <span className="px-2 py-0.5 rounded-full bg-gray-50 border border-gray-200 text-gray-500 text-[10px] font-medium">Skipped</span>
                      : <span className="px-2 py-0.5 rounded-full bg-red-50 border border-red-200 text-red-600 text-[10px] font-medium">Incorrect</span>;

                  return (
                    <div key={i} className={`bg-white rounded-2xl border ${borderColor} shadow-sm p-5`}>
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest">{i + 1} of {selectedAttempt.per_question.length}</span>
                        {badge}
                      </div>

                      <p className="text-sm font-medium text-gray-900 mb-4 leading-relaxed">{q.question_text}</p>

                      {/* MCQ options */}
                      {q.question_type === 'mcq' && Array.isArray(q.options) && (
                        <div className="grid grid-cols-2 gap-2 mb-4">
                          {q.options.map((opt, oi) => {
                            const isOpt = opt === q.correct_answer;
                            const isUserWrong = opt === q.user_response && !isOpt;
                            return (
                              <div key={oi} className={`px-3 py-2 rounded-lg border text-sm text-center ${
                                isOpt ? 'border-green-400 bg-green-50 text-green-700' :
                                isUserWrong ? 'border-red-300 bg-red-50 text-red-600' :
                                'border-gray-100 text-gray-600'
                              }`}>
                                {opt}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* TF */}
                      {q.question_type === 'tf' && (
                        <div className="flex gap-2 mb-4">
                          {['True', 'False'].map((opt) => {
                            const isOpt = opt.toLowerCase() === String(q.correct_answer).toLowerCase();
                            const isUserWrong = opt === q.user_response && !isOpt;
                            return (
                              <div key={opt} className={`flex-1 px-3 py-2 rounded-lg border text-sm text-center ${
                                isOpt ? 'border-green-400 bg-green-50 text-green-700' :
                                isUserWrong ? 'border-red-300 bg-red-50 text-red-600' :
                                'border-gray-100 text-gray-600'
                              }`}>
                                {opt}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* SA / LA — show user's response */}
                      {(q.question_type === 'sa' || q.question_type === 'la') && (
                        <div className="mb-4 space-y-2">
                          <div>
                            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Your answer</p>
                            <div className={`rounded-lg border px-3 py-2 text-sm whitespace-pre-wrap ${
                              isSkipped ? 'border-gray-100 text-gray-400 italic' :
                              isCorrect ? 'border-green-200 bg-green-50/60 text-gray-800' :
                              'border-red-200 bg-red-50/60 text-gray-800'
                            }`}>
                              {q.user_response || 'No answer given'}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Correct answer + explanation for all types */}
                      {!isCorrect && (
                        <div className="mt-1">
                          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Correct answer</p>
                          <div className="rounded-lg border border-green-200 bg-green-50/70 px-3 py-2 text-sm text-gray-800">
                            {q.correct_answer}
                          </div>
                        </div>
                      )}
                      {q.explanation && (
                        <div className="mt-3">
                          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Explanation</p>
                          <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                            {q.explanation}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </>
            )}
          </div>
        )}

      </main>
    </div>
  );
}
