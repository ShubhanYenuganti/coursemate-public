import { useState, useEffect } from "react";

/**
 * NotionTargetPicker
 *
 * Lets the user pick an existing Notion database and enter a name for the
 * new page that will be created inside it on export.
 *
 * Props:
 *   courseId       — current course id (for sticky target persistence)
 *   generationType — 'flashcards' | 'quiz' | 'report'
 *   onSelect({ databaseId, name }) — called when user confirms
 *   onClose()      — called when picker is dismissed without selection
 */
export default function NotionTargetPicker({ courseId, generationType, onSelect, onClose }) {
  const [stickyLoaded, setStickyLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  // Pre-populate database from sticky target on mount
  useEffect(() => {
    if (!courseId || !generationType) { setStickyLoaded(true); return; }
    fetch(`/api/notion?action=get_target&course_id=${courseId}&generation_type=${generationType}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((data) => {
        const t = data.target;
        if (t && t.type === "database") setSelected(t);
      })
      .catch(() => {})
      .finally(() => setStickyLoaded(true));
  }, [courseId, generationType]);

  // Debounced database search
  useEffect(() => {
    if (query.trim() === "") { setResults([]); return; }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(
          `/api/notion?action=search&q=${encodeURIComponent(query.trim())}&filter_type=database`,
          { credentials: "include" }
        );
        const data = await res.json();
        setResults(res.ok ? (data.results || []).filter((r) => r.type === "database") : []);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  async function handleConfirm() {
    if (!selected || !name.trim()) return;
    setSaving(true);
    try {
      if (courseId && generationType) {
        await fetch("/api/notion?action=set_target", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            course_id: courseId,
            generation_type: generationType,
            provider: "notion",
            target_id: selected.id,
            target_title: selected.title,
            target_type: selected.type,
          }),
        });
      }
      onSelect({ databaseId: selected.id, name: name.trim() });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-sm mx-4 bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-900">Export to Notion</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {!stickyLoaded ? (
          <div className="px-4 py-6 text-sm text-gray-400">Loading…</div>
        ) : (
          <div className="px-4 py-3 space-y-3">
            {/* Page name */}
            <div>
              <p className="text-xs text-gray-500 mb-1">Page name</p>
              <input
                autoFocus
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleConfirm()}
                placeholder="e.g. Week 3 Flashcards"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
              />
            </div>

            {/* Database selection */}
            <div>
              <p className="text-xs text-gray-500 mb-1">Parent database</p>
              {selected && (
                <div className="mb-1.5 flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-50 border border-indigo-100">
                  <span className="text-xs text-indigo-700 flex-1 truncate">{selected.title || "Untitled"}</span>
                  <button type="button" onClick={() => setSelected(null)} className="text-indigo-400 hover:text-indigo-600 text-xs">✕</button>
                </div>
              )}
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search databases…"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
              />
              {searching && <p className="text-xs text-gray-400 mt-1">Searching…</p>}
              {results.length > 0 && (
                <div className="mt-1 border border-gray-100 rounded-lg overflow-hidden max-h-40 overflow-y-auto">
                  {results.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => { setSelected(r); setQuery(""); setResults([]); }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors ${
                        selected?.id === r.id ? "bg-indigo-50 text-indigo-700" : "text-gray-800"
                      }`}
                    >
                      <span className="flex-1 truncate">{r.title || "Untitled"}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-purple-100 text-purple-700">DB</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex gap-2 pt-1 border-t border-gray-100">
              <button
                type="button"
                onClick={handleConfirm}
                disabled={!selected || !name.trim() || saving}
                className="flex-1 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors"
              >
                {saving ? "Saving…" : "Export"}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
