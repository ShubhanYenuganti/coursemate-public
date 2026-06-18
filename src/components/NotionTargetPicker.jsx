import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Command,
  CommandInput,
  CommandList,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";

/**
 * NotionTargetPicker
 *
 * Lets the user pick an existing Notion data source and enter a name for the
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
    const databaseId = normalizeNotionId(sp?.external_id || urlDerivedId || "");
    return {
      id: databaseId,
      title: sp?.external_title || "Untitled",
      type: "data_source",
    };
  }

  function mapSearchDbToCandidateId(db) {
    if (db?.type === "data_source") return normalizeNotionId(db?.id || "");
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
        if (t && (t.type === "database" || t.type === "data_source")) {
          setSelected({ ...t, id: normalizeNotionId(t.id) });
        }
      })
      .catch(() => {})
      .finally(() => setStickyLoaded(true));
  }, [courseId, generationType]);

  // Suggest a default page name (user can edit)
  useEffect(() => {
    if (name.trim()) return;
    const typeLabel =
      generationType === "quiz" ? "Quiz" : generationType === "flashcards" ? "Flashcards" : "Report";
    const date = new Date();
    const dateStr = date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
    setName(`${typeLabel} — ${dateStr}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generationType]);

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

  const filteredSourceTargets = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return sourceTargets;
    return sourceTargets.filter((t) => String(t.title || "").toLowerCase().includes(q));
  }, [sourceTargets, searchQuery]);

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
      type: db?.type || "data_source",
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
            target_type: selected.type || "data_source",
          }),
        });
      }

      onSelect({ databaseId, name: name.trim() });
    } finally {
      setSaving(false);
    }
  }

  function selectSourceTarget(target) {
    setSelected(target);
    setSearchQuery("");
    setSearchResults([]);
  }

  const DbBadge = () => (
    <span className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-700">
      DB
    </span>
  );

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-md gap-0 p-0">
        <DialogHeader className="flex-row items-center justify-between space-y-0 px-4 py-3">
          <DialogTitle className="text-sm font-semibold">Export to Notion</DialogTitle>
        </DialogHeader>

        {!stickyLoaded ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">Loading…</div>
        ) : (
          <div className="space-y-4 overflow-y-auto px-4 py-3">
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Page name</p>
              <Input
                autoFocus
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleConfirm()}
                placeholder={`e.g. Week 3 ${generationType === "quiz" ? "Quiz" : generationType === "flashcards" ? "Flashcards" : "Report"}`}
              />
            </div>

            <div>
              <p className="mb-1 text-xs text-muted-foreground">Parent database</p>

              {selected && (
                <div className="mb-2 inline-flex w-full items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 px-3 py-2">
                  <span className="flex-1 truncate text-xs text-primary">
                    {selected.title || "Untitled"}
                  </span>
                  <DbBadge />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => setSelected(null)}
                    className="text-primary/60 hover:bg-transparent hover:text-primary"
                  >
                    ✕
                  </Button>
                </div>
              )}

              <Command shouldFilter={false} className="rounded-lg border border-border bg-background">
                <CommandInput
                  value={searchQuery}
                  onValueChange={(v) => {
                    setAddError("");
                    setSearchQuery(v);
                  }}
                  placeholder={selected ? "Change parent database…" : "Search Notion databases…"}
                />
                <CommandList className="max-h-52">
                  {sourceTargets.length > 0 && (
                    <CommandGroup heading="CourseMate Databases">
                      {!sourcesLoaded ? (
                        <p className="px-3 pb-2 text-xs text-muted-foreground">Loading…</p>
                      ) : filteredSourceTargets.length === 0 ? (
                        <p className="px-3 pb-2 text-xs text-muted-foreground">No matches.</p>
                      ) : (
                        filteredSourceTargets.map((r) => (
                          <CommandItem
                            key={r.id}
                            value={`source-${r.id}`}
                            onSelect={() => selectSourceTarget(r)}
                          >
                            <span className="flex-1 truncate">{r.title || "Untitled"}</span>
                            <DbBadge />
                          </CommandItem>
                        ))
                      )}
                    </CommandGroup>
                  )}

                  <CommandGroup heading="Notion Databases">
                    {searchQuery.trim() === "" ? (
                      <p className="px-3 pb-2 text-xs text-muted-foreground">Start typing to search Notion databases…</p>
                    ) : searching ? (
                      <p className="px-3 pb-2 text-xs text-muted-foreground">Searching…</p>
                    ) : searchResults.length === 0 ? (
                      <p className="px-3 pb-2 text-xs text-muted-foreground">No results.</p>
                    ) : (
                      searchResults.map((r) => (
                        <CommandItem
                          key={r.id}
                          value={`notion-${r.id}`}
                          onSelect={() => handleSelectSearchResult(r)}
                        >
                          <span className="flex-1 truncate">{r.title || "Untitled"}</span>
                          <DbBadge />
                        </CommandItem>
                      ))
                    )}
                  </CommandGroup>
                </CommandList>
              </Command>

              {sourcesLoaded && sourceTargets.length === 0 && (
                <div className="mt-3 rounded-lg border border-border bg-muted px-3 py-2">
                  <p className="text-[11px] font-medium text-foreground">Add from Notion database search</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    You don’t have any saved databases yet. Search Notion above and pick a database to export into.
                  </p>
                </div>
              )}

              {addError && <p className="mt-1 text-xs text-destructive">{addError}</p>}
            </div>
          </div>
        )}

        <DialogFooter className="border-t border-border px-4 py-3">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleConfirm}
            disabled={!selected || !name.trim() || saving}
          >
            {saving ? "Saving…" : "Export"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
