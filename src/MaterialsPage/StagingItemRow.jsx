import { Button } from "@/components/ui/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { FileTypeIcon, TrashIcon } from "./atoms";
import { DOCUMENT_TYPES, fmtSize } from "./constants";

export default function StagingItemRow({ item, onDocTypeChange, onUpload, onRemove }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-accent/30 px-3 py-2.5">
      <FileTypeIcon type={item.file.type} />

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate">
          {item.file.name}
        </p>
        <p className="text-xs text-muted-foreground">{fmtSize(item.file.size)}</p>
      </div>

      <Select
        value={item.docType || "__unset__"}
        onValueChange={(v) => onDocTypeChange(item.id, v === "__unset__" ? "" : v)}
      >
        <SelectTrigger className="h-7 w-32 text-xs shrink-0">
          <SelectValue placeholder="Type…" />
        </SelectTrigger>
        <SelectContent>
          {DOCUMENT_TYPES.map((dt) => (
            <SelectItem key={dt.value} value={dt.value} className="text-xs">
              {dt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        type="button"
        onClick={() => onUpload(item)}
        disabled={!item.docType}
        size="sm"
        className="shrink-0 h-7 px-3 text-xs"
      >
        Upload
      </Button>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => onRemove(item.id)}
        className="h-7 w-7 text-muted-foreground/50 hover:text-muted-foreground shrink-0"
        title="Remove"
      >
        <TrashIcon size={14} />
      </Button>
    </div>
  );
}
