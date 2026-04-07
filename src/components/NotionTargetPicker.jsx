import { useState, useEffect, useRef } from "react";

/**
 * NotionTargetPicker
 *
 * Props:
 *   courseId       — current course id
 *   generationType — 'flashcards' | 'quiz' | 'report'
 *   allowedTypes   — array of allowed Notion resource types, e.g. ['page']
 *   onSelect(target) — called when user confirms a target { id, title, type }
 *   onClose()      — called when picker is dismissed without selection
 */
export default function NotionTargetPicker({ courseId, generationType, allowedTypes, onSelect, onClose }) {
  const [stickyTarget, setStickyTarget] = useState(undefined); // undefined = loading
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null);
  const [saving, setSaving] = useState(false);

  // Create-new sub-form
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createType, setCreateType] = useState(allowedTypes[0] || "page");
  const [parentQuery, setParentQuery] = useState("");
  const [parentResults, setParentResults] = useState([]);
  const [parentSearching, setParentSearching] = useState(false);
  const [parentSelected, setParentSelected] = useState(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const inputRef = useRef(null);

  // Load sticky target on mount
  useEffect(() => {
    if (!courseId || !generationType) { setStickyTarget(null); return; }
    fetch(`/api/notion?action=get_target&course_id=${courseId}&generation_type=${generationType}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((data) => {
        setStickyTarget(data.target || null);
        if (data.target) setSelected(data.target);
      })
      .catch(() => setStickyTarget(null));
  }, [courseId, generationType]);

  // Debounced search for main picker
  useEffect(() => {
    if (query.trim() === "") { setResults([]); return; }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const url = `/api/notion?action=search&q=${encodeURIComponent(query.trim())}`;
        const res = await fetch(url, { credentials: "include" });
        const data = await res.json();
        const items = (data.results || []).filter((r) => allowedTypes.includes(r.type));
        setResults(items);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, allowedTypes]);

  // Debounced parent page search for create-new sub-form
  useEffect(() => {
    if (parentQuery.trim() === "") { setParentResults([]); return; }
    const timer = setTimeout(async () => {
      setParentSearching(true);
      try {
        const url = `/api/notion?action=search&q=${encodeURIComponent(parentQuery.trim())}&filter_type=page`;
        const res = await fetch(url, { credentials: "include" });
        const data = await res.json();
        setParentResults(data.results || []);
      } catch {
        setParentResults([]);
      } finally {
        setParentSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [parentQuery]);

  async function handleConfirm() {
    if (!selected) return;
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
      onSelect(selected);
    } finally {
      setSaving(false);
    }
  }

  async function handleCreate() {
    if (!createName.trim()) { setCreateError("Name is required."); return; }
    if (!parentSelected) { setCreateError("Select a parent page."); return; }
    setCreating(true);
    setCreateError("");
    try {
      const body = {
        type: createType,
        name: createName.trim(),
        parent_id: parentSelected.id,
      };
      if (courseId && generationType) {
        body.course_id = courseId;
        body.generation_type = generationType;
      }
      const res = await fetch("/api/notion?action=create_target", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      // Auto-select the new resource
      const newTarget = { id: data.id, title: data.title, type: data.type };
      setSelected(newTarget);
      setShowCreate(false);
      onSelect(newTarget);
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreating(false);
    }
  }

  const typeBadge = (type) => (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
      type === "database"
        ? "bg-purple-100 text-purple-700"
        : "bg-blue-100 text-blue-700"
    }`}>
      {type === "database" ? "DB" : "Page"}
    </span>
  );

  const isLoading = stickyTarget === undefined;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-sm mx-4 bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-900">Select Notion destination</h3>
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

        {isLoading ? (
          <div className="px-4 py-6 text-sm text-gray-400">Loading…</div>
        ) : showCreate ? (
          /* ── Create-new sub-form ── */
          <div className="px-4 py-4 space-y-3">
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Create new</p>

            {/* Type selector — only when allowedTypes includes both */}
            {allowedTypes.length > 1 && (
              <div className="flex gap-2">
                {allowedTypes.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setCreateType(t)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                      createType === t
                        ? "bg-indigo-600 text-white border-indigo-600"
                        : "bg-white text-gray-700 border-gray-200 hover:bg-gray-50"
                    }`}
                  >
                    {t === "database" ? "Database" : "Page"}
                  </button>
                ))}
              </div>
            )}

            <input
              autoFocus
              type="text"
              value={createName}
              onChange={(e) => { setCreateName(e.target.value); setCreateError(""); }}
              placeholder="Name"
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
            />

            <div>
              <p className="text-xs text-gray-500 mb-1">Parent page</p>
              <input
                type="text"
                value={parentQuery}
                onChange={(e) => setParentQuery(e.target.value)}
                placeholder="Search pages…"
                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
              />
              {parentSelected && (
                <div className="mt-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-50 border border-indigo-100">
                  <span className="text-xs text-indigo-700 flex-1 truncate">{parentSelected.title}</span>
                  <button type="button" onClick={() => setParentSelected(null)} className="text-indigo-400 hover:text-indigo-600 text-xs">✕</button>
                </div>
              )}
              {parentSearching && <p className="text-xs text-gray-400 mt-1">Searching…</p>}
              {parentResults.length > 0 && !parentSelected && (
                <div className="mt-1 border border-gray-100 rounded-lg overflow-hidden max-h-32 overflow-y-auto">
                  {parentResults.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => { setParentSelected(r); setParentQuery(""); setParentResults([]); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-800 hover:bg-gray-50 transition-colors"
                    >
                      <span className="flex-1 truncate">{r.title || "Untitled"}</span>
                      {typeBadge(r.type)}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {createError && <p className="text-xs text-red-600">{createError}</p>}

            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={handleCreate}
                disabled={creating}
                className="flex-1 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {creating ? "Creating…" : "Create"}
              </button>
              <button
                type="button"
                onClick={() => { setShowCreate(false); setCreateError(""); }}
                className="px-4 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                Back
              </button>
            </div>
          </div>
        ) : (
          /* ── Main search + select ── */
          <div className="px-4 py-3 space-y-3">
            {/* Current selection */}
            {selected && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-50 border border-indigo-100">
                <span className="text-xs text-indigo-700 flex-1 truncate">{selected.title || "Untitled"}</span>
                {typeBadge(selected.type)}
                <button type="button" onClick={() => setSelected(null)} className="text-indigo-400 hover:text-indigo-600 text-xs ml-1">✕</button>
              </div>
            )}

            {/* Search */}
            <input
              ref={inputRef}
              autoFocus={!selected}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search Notion pages…"
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
            />

            {searching && <p className="text-xs text-gray-400">Searching…</p>}

            {results.length > 0 && (
              <div className="border border-gray-100 rounded-lg overflow-hidden max-h-48 overflow-y-auto">
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
                    {typeBadge(r.type)}
                  </button>
                ))}
              </div>
            )}

            {/* Create new */}
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-indigo-600 transition-colors"
            >
              <span className="text-base leading-none">+</span> Create new
            </button>

            <div className="flex gap-2 pt-1 border-t border-gray-100">
              <button
                type="button"
                onClick={handleConfirm}
                disabled={!selected || saving}
                className="flex-1 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors"
              >
                {saving ? "Saving…" : "Confirm"}
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
