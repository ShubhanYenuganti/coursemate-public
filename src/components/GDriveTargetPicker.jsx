import { useState, useEffect, useMemo, useRef } from "react";

/**
 * GDriveTargetPicker
 *
 * Lets the user pick a Google Drive folder to export into.
 * Persists the selection as a sticky target via set_target.
 *
 * Props:
 *   courseId       — current course id (for sticky target persistence)
 *   generationType — 'flashcards' | 'quiz' | 'report'
 *   onSelect({ folderId, folderName, name }) — called when user confirms
 *   onClose()      — called when picker is dismissed without selection
 */
export default function GDriveTargetPicker({ courseId, generationType, onSelect, onClose }) {
  const [stickyLoaded, setStickyLoaded] = useState(false);
  const [sourcesLoaded, setSourcesLoaded] = useState(false);
  const [sourcePoints, setSourcePoints] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null); // { id, name }
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const pickerContainerRef = useRef(null);

  function loadSourcePoints() {
    if (!courseId) {
      setSourcePoints([]);
      setSourcesLoaded(true);
      return;
    }

    setSourcesLoaded(false);
    fetch(`/api/gdrive?action=list_source_points&course_id=${courseId}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const points = Array.isArray(data.source_points) ? data.source_points : [];
        setSourcePoints(points.filter((p) => p?.external_id));
      })
      .catch(() => setSourcePoints([]))
      .finally(() => setSourcesLoaded(true));
  }

  const sourceTargets = useMemo(() => {
    return sourcePoints
      .map((sp) => ({
        id: sp?.external_id,
        name: sp?.external_title || "Untitled folder",
      }))
      .filter((t) => t.id);
  }, [sourcePoints]);

  const filteredSourceTargets = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return sourceTargets;
    return sourceTargets.filter((t) => String(t.name || "").toLowerCase().includes(q));
  }, [sourceTargets, searchQuery]);

  // Load existing source points immediately (same behavior as Notion picker)
  useEffect(() => {
    loadSourcePoints();
  }, [courseId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load sticky target on mount
  useEffect(() => {
    if (!courseId || !generationType) {
      setStickyLoaded(true);
      return;
    }
    fetch(`/api/gdrive?action=get_target&course_id=${courseId}&generation_type=${generationType}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((data) => {
        const t = data.target;
        if (t && t.id) {
          setSelected({ id: t.id, name: t.title || "Untitled folder" });
        }
      })
      .catch(() => {})
      .finally(() => setStickyLoaded(true));
  }, [courseId, generationType]);

  // Suggest a default document name (user can edit)
  useEffect(() => {
    if (name.trim()) return;
    const typeLabel =
      generationType === "quiz" ? "Quiz" : generationType === "flashcards" ? "Flashcards" : "Report";
    const date = new Date();
    const dateStr = date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
    setName(`${typeLabel} — ${dateStr}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generationType]);

  // Debounced folder search
  useEffect(() => {
    const q = searchQuery.trim();
    if (!q) {
      setSearching(false);
      setSearchResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const url = `/api/gdrive?action=search&q=${encodeURIComponent(q)}`;
        const res = await fetch(url, { credentials: "include" });
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

  async function handleConfirm() {
    if (!selected || !name.trim()) return;
    setSaving(true);
    try {
      if (courseId && generationType) {
        await fetch("/api/gdrive?action=set_target", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            course_id: courseId,
            generation_type: generationType,
            target_id: selected.id,
            target_title: selected.name,
          }),
        });
      }
      onSelect({ folderId: selected.id, folderName: selected.name, name: name.trim() });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md mx-4 bg-white rounded-2xl shadow-xl border border-gray-200 max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <svg width="16" height="14" viewBox="0 0 87.3 78" xmlns="http://www.w3.org/2000/svg">
              <path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/>
              <path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44a9.06 9.06 0 0 0 -1.2 4.5h27.5z" fill="#00ac47"/>
              <path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.502l5.852 11.5z" fill="#ea4335"/>
              <path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/>
              <path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/>
              <path d="m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 28h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00"/>
            </svg>
            <h3 className="text-sm font-semibold text-gray-900">Export to Google Drive</h3>
          </div>
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
          <div className="px-4 py-3 space-y-4 overflow-y-auto">
            <div>
              <p className="text-xs text-gray-500 mb-1">Document name</p>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={`e.g. Week 3 ${generationType === "quiz" ? "Quiz" : generationType === "flashcards" ? "Flashcards" : "Report"}`}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
              />
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Destination folder</p>

              {selected && (
                <div className="mb-2 inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-50 border border-indigo-100 w-full">
                  <svg width="12" height="10" viewBox="0 0 87.3 78" xmlns="http://www.w3.org/2000/svg" className="shrink-0">
                    <path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/>
                    <path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44a9.06 9.06 0 0 0 -1.2 4.5h27.5z" fill="#00ac47"/>
                    <path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.502l5.852 11.5z" fill="#ea4335"/>
                    <path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/>
                    <path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/>
                    <path d="m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 28h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00"/>
                  </svg>
                  <span className="text-xs text-indigo-700 flex-1 truncate">{selected.name}</span>
                  <button
                    type="button"
                    onClick={() => setSelected(null)}
                    className="text-indigo-400 hover:text-indigo-600 text-xs"
                  >
                    ✕
                  </button>
                </div>
              )}

              <div ref={pickerContainerRef} className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                  }}
                  placeholder="Search folders…"
                  className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                />
                {searchQuery.trim() !== "" && (
                  <div className="mt-1 border border-gray-100 rounded-lg overflow-hidden max-h-40 overflow-y-auto">
                  {sourceTargets.length > 0 && (
                    <div className="px-3 py-2 text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
                      CourseMate Folders
                    </div>
                  )}

                  {!sourcesLoaded ? (
                    <p className="px-3 pb-2 text-xs text-gray-400">Loading…</p>
                  ) : sourceTargets.length > 0 && filteredSourceTargets.length === 0 ? (
                    <p className="px-3 pb-2 text-xs text-gray-400">No matches.</p>
                  ) : (
                    filteredSourceTargets.map((folder) => (
                      <button
                        key={folder.id}
                        type="button"
                        onClick={() => {
                          setSelected({ id: folder.id, name: folder.name });
                          setSearchQuery("");
                        }}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-indigo-50 flex items-center gap-2 ${
                          selected?.id === folder.id ? "bg-indigo-50 text-indigo-700" : "text-gray-800"
                        }`}
                      >
                        <span className="text-gray-400">📁</span>
                        <span className="truncate">{folder.name}</span>
                      </button>
                    ))
                  )}

                  <div
                    className={`px-3 py-2 text-[10px] font-semibold text-gray-400 uppercase tracking-widest ${
                      sourceTargets.length > 0 ? "border-t border-gray-100" : ""
                    }`}
                  >
                    Google Drive Folders
                  </div>

                  {searching ? (
                    <p className="px-3 pb-2 text-xs text-gray-400">Searching…</p>
                  ) : searchResults.length === 0 ? (
                    <p className="px-3 pb-2 text-xs text-gray-400">No folders found</p>
                  ) : (
                    searchResults.map((folder) => (
                      <button
                        key={folder.id}
                        type="button"
                        onClick={() => {
                          setSelected({ id: folder.id, name: folder.name });
                          setSearchQuery("");
                        }}
                        className="w-full text-left px-3 py-2 text-sm text-gray-800 hover:bg-indigo-50 flex items-center gap-2"
                      >
                        <span className="text-gray-400">📁</span>
                        <span className="truncate">{folder.name}</span>
                      </button>
                    ))
                  )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-100 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!selected || !name.trim() || saving}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors"
          >
            {saving ? "Saving…" : "Export"}
          </button>
        </div>
      </div>
    </div>
  );
}
