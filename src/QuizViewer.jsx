import { useState } from 'react';

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

function MCQContent({ options, selected, onSelect, submitted, correct }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-3">Choose an answer</p>
      <div className="grid grid-cols-2 gap-2">
        {(options || []).map((opt, i) => {
          const optText = typeof opt === 'string' ? opt : (opt.text || opt.label || String(opt));
          const isSelected = selected === optText;
          const isCorrect = submitted && (optText === correct || i === correct);
          const isWrong = submitted && isSelected && !isCorrect;
          return (
            <button
              key={i}
              type="button"
              onClick={() => !submitted && onSelect(optText)}
              className={`px-4 py-3 rounded-lg border text-sm text-center transition-colors ${
                isCorrect ? 'border-green-400 bg-green-50 text-green-700' :
                isWrong   ? 'border-red-300 bg-red-50 text-red-600' :
                isSelected ? 'border-indigo-400 bg-indigo-50 text-indigo-700' :
                'border-gray-200 bg-white text-gray-700 hover:border-indigo-300 hover:bg-indigo-50'
              } ${submitted ? 'cursor-default' : 'cursor-pointer'}`}
            >
              {optText}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TrueFalseContent({ selected, onSelect, submitted, correct }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-3">Choose an answer</p>
      <div className="flex flex-col gap-2">
        {['True', 'False'].map((opt) => {
          const isSelected = selected === opt;
          const isCorrect = submitted && String(correct).toLowerCase() === opt.toLowerCase();
          const isWrong = submitted && isSelected && !isCorrect;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => !submitted && onSelect(opt)}
              className={`w-full px-4 py-3 rounded-lg border text-sm text-center transition-colors ${
                isCorrect ? 'border-green-400 bg-green-50 text-green-700' :
                isWrong   ? 'border-red-300 bg-red-50 text-red-600' :
                isSelected ? 'border-indigo-400 bg-indigo-50 text-indigo-700' :
                'border-gray-200 bg-white text-gray-700 hover:border-indigo-300 hover:bg-indigo-50'
              } ${submitted ? 'cursor-default' : 'cursor-pointer'}`}
            >
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ShortAnswerContent({ value, onChange, onSubmit, submitted }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-3">Your answer</p>
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={submitted}
          placeholder="Type your answer here..."
          className="flex-1 min-w-0 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 disabled:bg-gray-50 disabled:text-gray-500 transition-colors"
        />
        {!submitted && (
          <button
            type="button"
            onClick={onSubmit}
            disabled={!value.trim()}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            Submit
          </button>
        )}
      </div>
    </div>
  );
}

function LongAnswerContent({ value, onChange, onSubmit, submitted }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-3">Your answer</p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={submitted}
        placeholder="Type your detailed answer here..."
        rows={4}
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 disabled:bg-gray-50 disabled:text-gray-500 transition-colors resize-none"
      />
      {!submitted && (
        <div className="flex justify-end mt-2">
          <button
            type="button"
            onClick={onSubmit}
            disabled={!value.trim()}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Submit
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Question Card ─────────────────────────────────────────────────────────────

function QuestionCard({ question, index, total, answer, onAnswer, submitted, onSubmit, onDontKnow }) {
  const type = (question.type || '').toLowerCase();
  const questionText = question.question || question.text || '';
  const isSelectType = type === 'mcq' || type === 'multiple_choice' || type === 'tf' || type === 'true_false';

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
          onSelect={(val) => { onAnswer(val); onSubmit(); }}
          submitted={submitted}
          correct={question.answer}
        />
      )}
      {(type === 'tf' || type === 'true_false') && (
        <TrueFalseContent
          selected={answer}
          onSelect={(val) => { onAnswer(val); onSubmit(); }}
          submitted={submitted}
          correct={question.answer}
        />
      )}
      {(type === 'sa' || type === 'short_answer') && (
        <ShortAnswerContent
          value={answer || ''}
          onChange={onAnswer}
          onSubmit={onSubmit}
          submitted={submitted}
        />
      )}
      {(type === 'la' || type === 'long_answer') && (
        <LongAnswerContent
          value={answer || ''}
          onChange={onAnswer}
          onSubmit={onSubmit}
          submitted={submitted}
        />
      )}

      {!submitted && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={onDontKnow}
            className="text-xs text-indigo-500 hover:text-indigo-700 hover:underline transition-colors"
          >
            Don&apos;t know?
          </button>
        </div>
      )}
    </div>
  );
}

// ─── QuizViewer ────────────────────────────────────────────────────────────────

export default function QuizViewer({ quiz, onClose, onRegenerate }) {
  const questions = quiz?.questions || (Array.isArray(quiz) ? quiz : []);
  const total = questions.length;

  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState({});
  const answeredCount = Object.keys(submitted).length;

  function setAnswer(index, value) {
    setAnswers((prev) => ({ ...prev, [index]: value }));
  }

  function submitAnswer(index) {
    setSubmitted((prev) => ({ ...prev, [index]: true }));
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-blue-50 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b border-gray-100 px-8 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <span className="text-lg font-bold text-gray-900">CourseMate</span>

          <div className="text-center">
            <p className="text-base font-semibold text-gray-900 tabular-nums leading-none">
              {answeredCount} / {total}
            </p>
            <p className="text-[10px] text-gray-400 mt-0.5">Quiz Progress</p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onRegenerate}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
            >
              <RefreshIcon />
              Regenerate
            </button>
            <button
              type="button"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
            >
              <BookmarkIcon />
              Save Quiz
            </button>
            <button
              type="button"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
            >
              <DownloadIcon />
              Export Quiz
              <ChevronDownIcon />
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

      {/* Question cards */}
      <main className="flex-1 py-8 px-4">
        <div className="max-w-2xl mx-auto flex flex-col gap-6">
          {questions.length === 0 && (
            <p className="text-center text-sm text-gray-400 py-12">No questions generated.</p>
          )}
          {questions.map((q, i) => (
            <QuestionCard
              key={i}
              question={q}
              index={i}
              total={total}
              answer={answers[i]}
              onAnswer={(val) => setAnswer(i, val)}
              submitted={!!submitted[i]}
              onSubmit={() => submitAnswer(i)}
              onDontKnow={() => submitAnswer(i)}
            />
          ))}
        </div>
      </main>
    </div>
  );
}
