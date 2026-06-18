import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ACCEPTED_TYPES } from "./constants";

export default function UploadZone({ onFiles, disabled }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const files = [...e.dataTransfer.files].filter((f) =>
        ACCEPTED_TYPES.has(f.type),
      );
      if (files.length) onFiles(files);
    },
    [onFiles, disabled],
  );

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!disabled) setDragging(true);
  };
  const handleDragLeave = () => setDragging(false);

  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold text-foreground">Upload Files</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          PDF, DOCX, TXT, JPEG, PNG, GIF, SVG, XLSX, CSV
        </p>
      </div>

      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed py-10 transition-all cursor-pointer select-none
          ${
            dragging
              ? "border-primary bg-accent"
              : "border-border bg-muted/40 hover:border-primary/50 hover:bg-accent/30"
          }
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <div
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
            dragging ? "bg-accent" : "bg-muted"
          }`}
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={dragging ? "text-primary" : "text-muted-foreground"}
          >
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </div>
        <p className="text-sm text-muted-foreground">
          <Button
            variant="link"
            size="sm"
            className="h-auto p-0 font-medium"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              inputRef.current?.click();
            }}
          >
            Browse
          </Button>{" "}
          or drag files here
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={[...ACCEPTED_TYPES].join(",")}
          className="sr-only"
          onChange={(e) => {
            const files = [...e.target.files].filter((f) =>
              ACCEPTED_TYPES.has(f.type),
            );
            if (files.length) onFiles(files);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
