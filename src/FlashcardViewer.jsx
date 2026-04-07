import { useState, useMemo, useEffect } from 'react';
import NotionTargetPicker from './components/NotionTargetPicker';

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
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18" /><path d="m6 6 12 12" />
    </svg>
  );
}

function SpeakerIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  );
}

function StarIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function LightbulbIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5" />
      <path d="M9 18h6" /><path d="M10 22h4" />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

function ShuffleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16 3 21 3 21 8" />
      <line x1="4" y1="20" x2="21" y2="3" />
      <polyline points="21 16 21 21 16 21" />
      <line x1="15" y1="15" x2="21" y2="21" />
      <line x1="4" y1="4" x2="9" y2="9" />
    </svg>
  );
}

function ToolbarItem({ icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex items-center gap-2 transition-all duration-150 rounded-xl px-1 py-1 focus:outline-none cursor-pointer"
    >
      <span className="max-w-0 overflow-hidden whitespace-nowrap text-sm font-medium transition-all duration-200 ease-out group-hover:max-w-xs text-gray-700">
        {label}
      </span>
      <div className="w-10 h-10 flex items-center justify-center rounded-xl border shadow-sm text-lg transition-all duration-200 bg-white/80 border-gray-200 text-gray-600 group-hover:text-indigo-600 group-hover:border-indigo-300 group-hover:shadow-md">
        {icon}
      </div>
    </button>
  );
}

// ─── FlashcardViewer ───────────────────────────────────────────────────────────

export default function FlashcardViewer({
  data,
  course,
  generationId,
  parentGenerationId,
  onClose,
  onRegenerate,
  onResolve,
  onGoToTab,
}) {
  const flashcardsDownloadName = ((data?.title || 'flashcards')
    .toString()
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || `flashcards-${generationId || 'export'}`) + '.pdf';
  const cards = data?.flashcards || data?.cards || (Array.isArray(data) ? data : []);

  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [trackProgress, setTrackProgress] = useState(true);
  const [shuffled, setShuffled] = useState(false);
  const [seen, setSeen] = useState(new Set());
  const [showHint, setShowHint] = useState(false);
  const [saveStatus, setSaveStatus] = useState(data?.artifact_material_id ? 'saved' : 'idle');
  const [exportStatus, setExportStatus] = useState('idle');
  const [resolving, setResolving] = useState(false);

  // Notion export state
  const courseId = course?.id;
  const [notionConnected, setNotionConnected] = useState(false);
  const [notionPickerOpen, setNotionPickerOpen] = useState(false);
  const [notionBanner, setNotionBanner] = useState(null); // null | { ok, url, message }
  const [notionExporting, setNotionExporting] = useState(false);

  useEffect(() => {
    setSaveStatus(data?.artifact_material_id ? 'saved' : 'idle');
  }, [data?.artifact_material_id, data?.generation_id]);

  // Fetch Notion connection status on mount
  useEffect(() => {
    fetch("/api/notion?action=status", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setNotionConnected(!!d.connected))
      .catch(() => {});
  }, []);

  const displayCards = useMemo(() => {
    if (!shuffled) return cards;
    const arr = [...cards];
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }, [shuffled, cards]);

  const total = displayCards.length;
  const card = displayCards[currentIndex] || {};
  const front = card.front || card.term || card.question || '';
  const back = card.back || card.definition || card.answer || '';
  const hint = card.hint || (back ? back.split(' ').slice(0, 4).join(' ') + '…' : '');
  const courseName = course?.name || course?.title || 'Flashcards';

  function goNext() {
    if (currentIndex < total - 1) {
      if (trackProgress) setSeen((prev) => new Set(prev).add(currentIndex));
      setCurrentIndex((i) => i + 1);
      setIsFlipped(false);
      setShowHint(false);
    }
  }

  function goPrev() {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1);
      setIsFlipped(false);
      setShowHint(false);
    }
  }

  function handleFlip() {
    if (trackProgress && !isFlipped) setSeen((prev) => new Set(prev).add(currentIndex));
    setIsFlipped((f) => !f);
  }

  function toggleShuffle() {
    setShuffled((s) => !s);
    setCurrentIndex(0);
    setIsFlipped(false);
    setShowHint(false);
  }

  async function handleSave() {
    if (!generationId || saveStatus === 'saving' || saveStatus === 'saved') return;
    setSaveStatus('saving');
    try {
      const res = await fetch('/api/flashcards', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ action: 'save_artifact', generation_id: generationId }),
      });
      if (res.ok) setSaveStatus('saved');
      else setSaveStatus('error');
    } catch {
      setSaveStatus('error');
    }
  }

  async function handleExportPdf() {
    if (!generationId || exportStatus === 'exporting') return;
    setExportStatus('exporting');
    try {
      const res = await fetch(`/api/flashcards?action=export_pdf&generation_id=${generationId}`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = flashcardsDownloadName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportStatus('idle');
    } catch {
      setExportStatus('error');
    }
  }

  async function handleResolve(resolution) {
    if (!parentGenerationId || !generationId || resolving) return;
    setResolving(true);
    try {
      const res = await fetch('/api/flashcards', {
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
      const payload = await res.json().catch(() => ({}));
      if (res.ok) onResolve?.(resolution, payload.generation || null);
    } catch {
      // keep banner visible for retry
    } finally {
      setResolving(false);
    }
  }

  async function handleNotionExport(databaseId, name) {
    if (!generationId || notionExporting) return;
    setNotionExporting(true);
    setNotionBanner(null);
    try {
      const res = await fetch("/api/notion?action=export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          exports: [{ generation_id: generationId, generation_type: "flashcards", targets: [{ provider: "notion", target_id: databaseId, name }] }],
        }),
      });
      const data = await res.json();
      const result = data.results?.[0];
      if (result?.status === "success") {
        setNotionBanner({ ok: true, url: result.url, message: "Exported to Notion" });
      } else {
        console.error("[Notion] flashcard export failed", result);
        setNotionBanner({ ok: false, message: result?.error || "Export failed" });
      }
    } catch (err) {
      console.error("[Notion] flashcard export error", err);
      setNotionBanner({ ok: false, message: err.message || "Export failed" });
    } finally {
      setNotionExporting(false);
    }
  }

  function handleNotionClick() {
    if (!notionConnected) return;
    setNotionPickerOpen(true);
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-teal-50 flex flex-col">
      {parentGenerationId && (
        <div className="bg-amber-50 border-b border-amber-200 px-8 py-3">
          <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
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

      {/* ── Header ── */}
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b border-gray-100 px-8 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <span className="text-lg font-bold text-gray-900">{courseName}</span>

          <div className="text-center">
            <p className="text-base font-semibold text-gray-900 tabular-nums leading-none">
              {currentIndex + 1} / {total}
            </p>
            <p className="text-[10px] text-gray-400 mt-0.5">{courseName} Flashcards</p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onRegenerate?.(data)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
            >
              <RefreshIcon />
              Regenerate
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saveStatus === 'saving' || saveStatus === 'saved'}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
                saveStatus === 'saved'
                  ? 'border-green-300 text-green-700 bg-green-50 cursor-default'
                  : saveStatus === 'error'
                    ? 'border-red-300 text-red-600 hover:bg-red-50'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              <BookmarkIcon />
              {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved ✓' : saveStatus === 'error' ? 'Retry Save' : 'Save Flashcards'}
            </button>
            <button
              type="button"
              onClick={handleExportPdf}
              disabled={!generationId || exportStatus === 'exporting'}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
            >
              <DownloadIcon />
              {exportStatus === 'exporting' ? 'Exporting…' : 'Export Flashcards'}
              <ChevronDownIcon />
            </button>
            {notionConnected && (
              <button
                type="button"
                onClick={handleNotionClick}
                disabled={notionExporting}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" className="shrink-0">
                  <path d="M4 4a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v16a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V4z" opacity=".15"/>
                  <rect x="7" y="7" width="10" height="1.5" rx=".75"/>
                  <rect x="7" y="11" width="7" height="1.5" rx=".75"/>
                  <rect x="7" y="15" width="8" height="1.5" rx=".75"/>
                </svg>
                {notionExporting ? "Exporting…" : "Notion"}
              </button>
            )}
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

      {/* ── Card area ── */}
      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-[680px]" style={{ perspective: '1200px' }}>
          <div
            onClick={handleFlip}
            className="relative cursor-pointer"
            style={{
              transformStyle: 'preserve-3d',
              transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
              transition: 'transform 0.45s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          >
            {/* Front face */}
            <div
              className="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden"
              style={{ backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden' }}
            >
              {/* Card top bar */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-50">
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setShowHint((h) => !h); }}
                  className="flex items-center gap-1.5 text-xs text-indigo-500 hover:text-indigo-700 transition-colors"
                >
                  <LightbulbIcon />
                  Get a hint
                </button>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={(e) => e.stopPropagation()}
                    className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                  >
                    <SpeakerIcon />
                  </button>
                  <button
                    type="button"
                    onClick={(e) => e.stopPropagation()}
                    className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                  >
                    <StarIcon />
                  </button>
                </div>
              </div>

              {/* Card body */}
              <div className="flex flex-col items-center justify-center px-10 py-16 min-h-[350px]">
                {showHint && hint && (
                  <p className="text-xs text-indigo-400 italic mb-6 text-center">Hint: {hint}</p>
                )}
                <p className="text-[10px] font-bold text-indigo-500 uppercase tracking-widest mb-4">Front</p>
                <p className="text-xl font-semibold text-gray-900 text-center leading-snug">{front}</p>
              </div>

              {/* Flip bar */}
              <div className="bg-indigo-600 rounded-b-2xl px-6 py-3 text-center">
                <p className="text-sm text-white/90">Click the card to flip</p>
              </div>
            </div>

            {/* Back face */}
            <div
              className="absolute inset-0 bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden"
              style={{
                backfaceVisibility: 'hidden',
                WebkitBackfaceVisibility: 'hidden',
                transform: 'rotateY(180deg)',
              }}
            >
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-50">
                <span className="text-xs text-gray-400">Answer</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={(e) => e.stopPropagation()}
                    className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                  >
                    <SpeakerIcon />
                  </button>
                  <button
                    type="button"
                    onClick={(e) => e.stopPropagation()}
                    className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                  >
                    <StarIcon />
                  </button>
                </div>
              </div>

              <div className="flex flex-col items-center justify-center px-10 py-16 min-h-[350px]">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Back</p>
                <p className="text-base text-gray-700 text-center leading-relaxed">{back}</p>
              </div>

              <div className="bg-indigo-600 rounded-b-2xl px-6 py-3 text-center">
                <p className="text-sm text-white/90">Click to flip back</p>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* ── Bottom navigation ── */}
      <footer className="bg-white/80 backdrop-blur border-t border-gray-100 px-8 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">

          {/* Track progress toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Track progress</span>
            <button
              type="button"
              onClick={() => setTrackProgress((t) => !t)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${
                trackProgress ? 'bg-indigo-500' : 'bg-gray-200'
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                trackProgress ? 'translate-x-4' : 'translate-x-0.5'
              }`} />
            </button>
            {trackProgress && total > 0 && (
              <span className="text-[10px] text-gray-400 tabular-nums">{seen.size}/{total}</span>
            )}
          </div>

          {/* Prev / Next */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={goPrev}
              disabled={currentIndex === 0}
              className="w-10 h-10 flex items-center justify-center rounded-full border border-gray-200 text-gray-500 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeftIcon />
            </button>
            <button
              type="button"
              onClick={goNext}
              disabled={currentIndex === total - 1}
              className="w-10 h-10 flex items-center justify-center rounded-full border border-gray-200 text-gray-500 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRightIcon />
            </button>
          </div>

          {/* Play / Shuffle */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="w-9 h-9 flex items-center justify-center rounded-full border border-gray-200 text-gray-500 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
            >
              <PlayIcon />
            </button>
            <button
              type="button"
              onClick={toggleShuffle}
              className={`w-9 h-9 flex items-center justify-center rounded-full border transition-colors ${
                shuffled
                  ? 'border-indigo-400 text-indigo-600 bg-indigo-50'
                  : 'border-gray-200 text-gray-500 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50'
              }`}
            >
              <ShuffleIcon />
            </button>
          </div>

        </div>
      </footer>

      {onGoToTab && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-3 rounded-2xl bg-white/70 backdrop-blur-md border border-gray-200 shadow-lg z-20">
          <ToolbarItem icon="📄" label="Materials" onClick={() => onGoToTab('materials')} />
          <div className="w-px h-6 bg-gray-200" />
          <ToolbarItem icon="💬" label="Chat" onClick={() => onGoToTab('chat')} />
          <div className="w-px h-6 bg-gray-200" />
          <ToolbarItem icon="💡" label="Generate" onClick={() => onGoToTab('generate')} />
        </div>
      )}

      {notionBanner && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg text-sm font-medium ${
          notionBanner.ok ? "bg-gray-900 text-white" : "bg-red-600 text-white"
        }`}>
          {notionBanner.ok ? (
            <>
              <span>Exported to Notion</span>
              {notionBanner.url && (
                <a href={notionBanner.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 opacity-80 hover:opacity-100">Open</a>
              )}
            </>
          ) : (
            <span>{notionBanner.message}</span>
          )}
          <button type="button" onClick={() => setNotionBanner(null)} className="ml-2 opacity-60 hover:opacity-100">
            <XIcon />
          </button>
        </div>
      )}

      {notionPickerOpen && (
        <NotionTargetPicker
          courseId={courseId}
          generationType="flashcards"
          onSelect={({ databaseId, name }) => {
            setNotionPickerOpen(false);
            handleNotionExport(databaseId, name);
          }}
          onClose={() => setNotionPickerOpen(false)}
        />
      )}
    </div>
  );
}
