import { Spinner, FileTypeIcon, VisibilityToggle } from "./atoms";
import { DOCUMENT_TYPES } from "./constants";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

export default function SyncModal({
  open,
  provider,
  sourcePointTitle,
  rows,
  page,
  hasMore,
  loading,
  toggles,
  docTypes = {},
  error,
  onToggle,
  onDocTypeChange,
  onSetAllDocTypes,
  onPrevPage,
  onNextPage,
  onSync,
  onSyncAll,
  onClose,
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle>Sync Modal</DialogTitle>
          <DialogDescription>
            {provider === "notion" ? "Notion" : "Google Drive"} ·{" "}
            {sourcePointTitle || "Source point"}
          </DialogDescription>
        </DialogHeader>

        <div className="px-6 pb-6 space-y-4">
          {error && <p className="text-xs text-destructive">{error}</p>}

          {loading ? (
            <div className="py-8 flex items-center justify-center">
              <Spinner size={22} className="text-primary" />
            </div>
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6">
              No files found for this source point.
            </p>
          ) : (
            <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
              {rows.length > 1 && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-accent/50">
                  <span className="text-xs text-muted-foreground shrink-0">Set all to:</span>
                  <Select onValueChange={(v) => onSetAllDocTypes(v)}>
                    <SelectTrigger className="h-7 text-xs w-40 shrink-0">
                      <SelectValue placeholder="— pick type —" />
                    </SelectTrigger>
                    <SelectContent>
                      {DOCUMENT_TYPES.map((dt) => (
                        <SelectItem key={dt.value} value={dt.value}>
                          {dt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="flex-1" />
                  <Button
                    size="sm"
                    onClick={onSyncAll}
                    disabled={loading}
                    className="shrink-0"
                  >
                    Sync all
                  </Button>
                </div>
              )}
              {rows.map((row) => {
                const enabled = toggles[row.external_id] ?? row.sync !== false;
                return (
                  <div
                    key={row.external_id}
                    className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-2.5"
                  >
                    <FileTypeIcon type={row.mime_type} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-foreground truncate">
                        {row.name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {row.external_id}
                      </p>
                    </div>
                    <Select
                      value={docTypes[row.external_id] ?? row.doc_type ?? "general"}
                      onValueChange={(v) => onDocTypeChange(row.external_id, v)}
                    >
                      <SelectTrigger className="h-7 text-xs w-36 shrink-0">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DOCUMENT_TYPES.map((dt) => (
                          <SelectItem key={dt.value} value={dt.value}>
                            {dt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-medium ${enabled ? "text-emerald-600" : "text-muted-foreground"}`}
                      >
                        {enabled ? "Sync ON" : "Sync OFF"}
                      </span>
                      <VisibilityToggle
                        isPublic={enabled}
                        onChange={(next) => onToggle(row.external_id, next)}
                        size="sm"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <div className="text-xs text-muted-foreground">Page {page}</div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onPrevPage}
                disabled={page <= 1 || loading}
              >
                Prev
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onNextPage}
                disabled={!hasMore || loading}
              >
                Next
              </Button>
            </div>
          </div>

          <div className="pt-1">
            <Button
              type="button"
              onClick={onSync}
              disabled={loading || rows.length === 0}
            >
              Sync
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
