import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileTypeIcon, Spinner, VisibilityToggle, TrashIcon } from "./atoms";
import { fmtSize } from "./constants";

export default function UploadItemRow({ item, onVisibilityChange, onDismiss }) {
  const isLoading = item.status === "uploading";
  const isDone = item.status === "done";
  const isError = item.status === "error";

  return (
    <div
      className={`rounded-lg border bg-background transition-all ${
        isError ? "border-destructive/30 bg-destructive/5" : "border-border"
      }`}
    >
      {/* Main row */}
      <div className="flex items-center gap-3 px-3 py-2.5">
        <FileTypeIcon type={item.file.type} />

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            {item.file.name}
          </p>
          <p className="text-xs text-muted-foreground">{fmtSize(item.file.size)}</p>
        </div>

        {/* State indicator */}
        <div className="flex items-center gap-2 shrink-0">
          {isLoading && (
            <Badge variant="outline" className="gap-1.5 text-primary border-primary/30">
              <Spinner size={13} />
              Uploading…
            </Badge>
          )}
          {isDone && (
            <Badge variant="outline" className="text-emerald-600 border-emerald-200">
              ✓ Done
            </Badge>
          )}
          {isError && (
            <Badge variant="destructive" title={item.error}>
              Failed
            </Badge>
          )}

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground/50 hover:text-muted-foreground"
            onClick={() => onDismiss(item.id)}
            title="Dismiss"
          >
            <TrashIcon size={14} />
          </Button>
        </div>
      </div>

      {/* Loading progress banner — shown while uploading (indeterminate) */}
      {isLoading && (
        <div className="mx-3 mb-2.5 h-1 rounded-full bg-muted overflow-hidden">
          <div className="h-full w-[60%] bg-primary rounded-full animate-[loading-bar_1.6s_ease-in-out_infinite]" />
        </div>
      )}

      {/* Visibility toggle row — shown only after confirmed done */}
      {isDone && (
        <div className="flex items-center justify-between px-3 pb-2.5">
          <span className="text-xs text-muted-foreground">
            {item.visibilityUpdating
              ? "Saving…"
              : item.isPublic
                ? "Public"
                : "Private"}
          </span>
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-muted-foreground">Private</span>
            <VisibilityToggle
              isPublic={item.isPublic}
              onChange={(val) => onVisibilityChange(item.id, val)}
              disabled={item.visibilityUpdating}
              size="sm"
            />
            <span className="text-[11px] text-muted-foreground">Public</span>
          </div>
        </div>
      )}
    </div>
  );
}
