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

function DriveIcon({ width = 16, height = 14, className }) {
  return (
    <svg width={width} height={height} viewBox="0 0 87.3 78" xmlns="http://www.w3.org/2000/svg" className={className}>
      <path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/>
      <path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44a9.06 9.06 0 0 0 -1.2 4.5h27.5z" fill="#00ac47"/>
      <path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.502l5.852 11.5z" fill="#ea4335"/>
      <path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/>
      <path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/>
      <path d="m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 28h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00"/>
    </svg>
  );
}

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

  function selectFolder(folder) {
    setSelected({ id: folder.id, name: folder.name });
    setSearchQuery("");
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-md gap-0 p-0">
        <DialogHeader className="flex-row items-center gap-2 space-y-0 px-4 py-3">
          <DriveIcon />
          <DialogTitle className="text-sm font-semibold">Export to Google Drive</DialogTitle>
        </DialogHeader>

        {!stickyLoaded ? (
          <div className="px-4 py-6 text-sm text-muted-foreground">Loading…</div>
        ) : (
          <div className="space-y-4 overflow-y-auto px-4 py-3">
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Document name</p>
              <Input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={`e.g. Week 3 ${generationType === "quiz" ? "Quiz" : generationType === "flashcards" ? "Flashcards" : "Report"}`}
              />
            </div>
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Destination folder</p>

              {selected && (
                <div className="mb-2 inline-flex w-full items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 px-3 py-2">
                  <DriveIcon width={12} height={10} className="shrink-0" />
                  <span className="flex-1 truncate text-xs text-primary">{selected.name}</span>
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
                  onValueChange={setSearchQuery}
                  placeholder="Search folders…"
                />
                {searchQuery.trim() !== "" && (
                  <CommandList className="max-h-40">
                    {sourceTargets.length > 0 && (
                      <CommandGroup heading="CourseMate Folders">
                        {!sourcesLoaded ? (
                          <p className="px-3 pb-2 text-xs text-muted-foreground">Loading…</p>
                        ) : filteredSourceTargets.length === 0 ? (
                          <p className="px-3 pb-2 text-xs text-muted-foreground">No matches.</p>
                        ) : (
                          filteredSourceTargets.map((folder) => (
                            <CommandItem
                              key={folder.id}
                              value={`source-${folder.id}`}
                              onSelect={() => selectFolder(folder)}
                            >
                              <span className="text-muted-foreground">📁</span>
                              <span className="truncate">{folder.name}</span>
                            </CommandItem>
                          ))
                        )}
                      </CommandGroup>
                    )}

                    <CommandGroup heading="Google Drive Folders">
                      {searching ? (
                        <p className="px-3 pb-2 text-xs text-muted-foreground">Searching…</p>
                      ) : searchResults.length === 0 ? (
                        <p className="px-3 pb-2 text-xs text-muted-foreground">No folders found</p>
                      ) : (
                        searchResults.map((folder) => (
                          <CommandItem
                            key={folder.id}
                            value={`drive-${folder.id}`}
                            onSelect={() => selectFolder(folder)}
                          >
                            <span className="text-muted-foreground">📁</span>
                            <span className="truncate">{folder.name}</span>
                          </CommandItem>
                        ))
                      )}
                    </CommandGroup>
                  </CommandList>
                )}
              </Command>
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
