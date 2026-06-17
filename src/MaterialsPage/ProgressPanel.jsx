import { Button } from "@/components/ui/button";
import { Spinner } from "./atoms";

export default function ProgressPanel({
  syncJobs,
  uploadItems,
  embedStatusMap,
  onClearDone,
  onCancelSyncJob,
}) {
  function deriveSyncStatus(item) {
    const status = embedStatusMap[item.external_id];
    if (!status) return { label: "Syncing…", spinner: true, color: "primary" };
    switch (status) {
      case "pending":
        return { label: "Queued", spinner: true, color: "amber" };
      case "processing":
        return { label: "Indexing…", spinner: true, color: "amber" };
      case "done":
        return { label: "Done", spinner: false, color: "emerald" };
      case "failed":
        return { label: "Failed", spinner: false, color: "destructive" };
      case "skipped":
        return { label: "Skipped", spinner: false, color: "muted" };
      default:
        return { label: "Syncing…", spinner: true, color: "primary" };
    }
  }

  const colorClasses = {
    primary: "text-primary bg-accent border-primary/30",
    amber: "text-amber-600 bg-amber-50 border-amber-200",
    emerald: "text-emerald-600 bg-emerald-50 border-emerald-200",
    destructive: "text-destructive bg-destructive/10 border-destructive/30",
    muted: "text-muted-foreground bg-muted border-border",
  };

  const uploadStatusLabel = (status) => {
    switch (status) {
      case "uploading":
      case "confirming":
        return {
          label: status === "uploading" ? "Uploading…" : "Confirming…",
          spinner: true,
          color: "primary",
        };
      case "done":
        return { label: "Done", spinner: false, color: "emerald" };
      case "error":
        return { label: "Failed", spinner: false, color: "destructive" };
      default:
        return { label: status, spinner: false, color: "muted" };
    }
  };

  return (
    <div className="bg-background rounded-xl border border-border shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Processing</h3>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onClearDone}
          className="h-auto px-2 py-0.5 text-xs font-medium text-primary hover:text-primary/80"
        >
          Clear done
        </Button>
      </div>

      {syncJobs.map((job) => (
        <div key={job.jobId} className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide truncate">
              {job.provider === "notion" ? "Notion" : "Google Drive"} ·{" "}
              {job.label}
            </p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onCancelSyncJob(job)}
              className="h-auto px-2 py-0.5 text-xs font-medium text-destructive hover:text-destructive/80 shrink-0"
            >
              Give up
            </Button>
          </div>
          {job.items.map((item) => {
            const st = deriveSyncStatus(item);
            return (
              <div
                key={item.external_id}
                className="flex items-center gap-2.5 rounded-lg border border-border bg-muted/40 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-foreground truncate">{item.name}</p>
                </div>
                <span
                  className={`inline-flex items-center gap-1 text-[10px] font-medium border rounded-full px-1.5 py-0.5 leading-none shrink-0 ${colorClasses[st.color]}`}
                >
                  {st.spinner && <Spinner size={9} className="opacity-80" />}
                  {st.label}
                </span>
              </div>
            );
          })}
        </div>
      ))}

      {uploadItems.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Uploads
          </p>
          {uploadItems.map((item) => {
            const st =
              item.status === "indexing"
                ? deriveSyncStatus({ external_id: String(item.materialId) })
                : uploadStatusLabel(item.status);
            return (
              <div
                key={item.id}
                className="flex items-center gap-2.5 rounded-lg border border-border bg-muted/40 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-foreground truncate">
                    {item.name || item.file?.name || item.id}
                  </p>
                </div>
                <span
                  className={`inline-flex items-center gap-1 text-[10px] font-medium border rounded-full px-1.5 py-0.5 leading-none shrink-0 ${colorClasses[st.color]}`}
                >
                  {st.spinner && <Spinner size={9} className="opacity-80" />}
                  {st.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
