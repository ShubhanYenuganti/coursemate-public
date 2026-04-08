import { useState, useEffect, useMemo } from "react";

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
  const [sourcesLoaded, setSourcesLoaded] = useState(false);
  const [sourcePoints, setSourcePoints] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [addError, setAddError] = useState("");

  function normalizeNotionId(rawId) {
    const cleaned = String(rawId || "").trim().replace(/-/g, "");
    if (!/^[0-9a-fA-F]{32}$/.test(cleaned)) return String(rawId || "").trim();
    return `${cleaned.slice(0, 8)}-${cleaned.slice(8, 12)}-${cleaned.slice(12, 16)}-${cleaned.slice(16, 20)}-${cleaned.slice(20)}`.toLowerCase();
  }

  function extractNotionIdFromUrl(url) {
    const text = String(url || "").trim();
    if (!text) return null;
    const match = text.match(/([0-9a-fA-F]{32})/);
    if (!match) return null;
    return normalizeNotionId(match[1]);
  }

  function parseMetadata(rawMetadata) {
    if (!rawMetadata) return {};
    if (typeof rawMetadata === "string") {
      try {
        return JSON.parse(rawMetadata);
      } catch {
        return {};
      }
    }
    return typeof rawMetadata === "object" ? rawMetadata : {};
  }

  function sourcePointToTarget(sp) {
    const meta = parseMetadata(sp?.metadata);
    const urlDerivedId = extractNotionIdFromUrl(meta.database_url || meta.notion_url || meta.url);
    const databaseId = normalizeNotionId(urlDerivedId || sp?.external_id || "");
    return {
      id: databaseId,
      title: sp?.external_title || "Untitled",
      type: "database",
    };
  }

  function mapSearchDbToCandidateId(db) {
    const urlDerivedId = extractNotionIdFromUrl(db?.url);
    return normalizeNotionId(urlDerivedId || db?.id || "");
  }

  function loadSourcePoints() {
    if (!courseId) {
      setSourcePoints([]);
      setSourcesLoaded(true);
      return;
    }

    setSourcesLoaded(false);
    fetch(`/api/notion?action=list_source_points&course_id=${courseId}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const points = Array.isArray(data.source_points) ? data.source_points : [];
        setSourcePoints(points.filter((p) => p?.external_id));
      })
      .catch(() => setSourcePoints([]))
      .finally(() => setSourcesLoaded(true));
  }

  // Pre-populate sticky target
  useEffect(() => {
    if (!courseId || !generationType) {
      setStickyLoaded(true);
      return;
    }

    fetch(`/api/notion?action=get_target&course_id=${courseId}&generation_type=${generationType}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((data) => {
        const t = data.target;
        if (t && t.type === "database") {
          setSelected({ ...t, id: normalizeNotionId(t.id) });
        }
      })
      .catch(() => {})
      .finally(() => setStickyLoaded(true));
  }, [courseId, generationType]);

  // Load existing source points immediately (same as CoursePage)
  useEffect(() => {
    loadSourcePoints();
  }, [courseId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Search Notion databases endpoint (same as CoursePage)
  useEffect(() => {
    if (searchQuery.trim() === "") {
      setSearchResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(
          `/api/notion?action=search&q=${encodeURIComponent(searchQuery.trim())}&filter_type=database`,
          { credentials: "include" }
        );
        const data = await res.json();
        setSearchResults(Array.isArray(data.results) ? data.results : []);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const sourceTargets = useMemo(
    () => sourcePoints.map(sourcePointToTarget).filter((t) => t.id),
    [sourcePoints]
  );

  async function handleSelectSearchResult(db) {
    setAddError("");
    if (!courseId) return;

    const candidateId = mapSearchDbToCandidateId(db);
    if (!candidateId) {
      setAddError("Invalid Notion database selection");
      return;
    }

    // Search selection is transient for export targeting only.
    // It must not create/update integration_source_points.
    setSelected({
      id: candidateId,
      title: db?.title || "Untitled",
      type: "database",
    });
    setSearchQuery("");
    setSearchResults([]);
  }

  async function handleConfirm() {
    if (!selected || !name.trim()) return;
    const databaseId = normalizeNotionId(selected.id);
    setSaving(true);
    try {
      // Persist sticky target into course_export_targets via set_target.
      if (courseId && generationType) {
        await fetch("/api/notion?action=set_target", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            course_id: courseId,
            generation_type: generationType,
            provider: "notion",
            target_id: databaseId,
            target_title: selected.title,
            target_type: "database",
          }),
        });
      }

      onSelect({ databaseId, name: name.trim() });
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

            <div>
              <p className="text-xs text-gray-500 mb-1">Parent database</p>

              {selected && (
                <div className="mb-1.5 flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-50 border border-indigo-100">
                  <span className="text-xs text-indigo-700 flex-1 truncate">{selected.title || "Untitled"}</span>
                  <button
                    type="button"
                    onClick={() => setSelected(null)}
                    className="text-indigo-400 hover:text-indigo-600 text-xs"
                  >
                    ✕
                  </button>
                </div>
              )}

              {/* Existing source points list (immediate) */}
              <div className="border border-gray-100 rounded-lg overflow-hidden max-h-36 overflow-y-auto">
                {!sourcesLoaded ? (
                  <p className="px-3 py-2 text-xs text-gray-400">Loading connected databases…</p>
                ) : sourceTargets.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-gray-400">No connected course databases yet.</p>
                ) : (
                  sourceTargets.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => setSelected(r)}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors ${
                        selected?.id === r.id ? "bg-indigo-50 text-indigo-700" : "text-gray-800"
                      }`}
                    >
                      <span className="flex-1 truncate">{r.title || "Untitled"}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-purple-100 text-purple-700">DB</span>
                    </button>
                  ))
                )}
              </div>

              {/* Search endpoint below source list */}
              <p className="text-[11px] text-gray-500 mt-2 mb-1">Add from Notion database search</p>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search Notion databases…"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
              />
              {searching && <p className="text-xs text-gray-400 mt-1">Searching…</p>}
              {searchResults.length > 0 && (
                <div className="mt-1 border border-gray-100 rounded-lg overflow-hidden max-h-40 overflow-y-auto">
                  {searchResults.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => handleSelectSearchResult(r)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-800 hover:bg-gray-50 transition-colors"
                    >
                      <span className="flex-1 truncate">{r.title || "Untitled"}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-purple-100 text-purple-700">DB</span>
                    </button>
                  ))}
                </div>
              )}
              {addError && <p className="text-xs text-red-500 mt-1">{addError}</p>}
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
