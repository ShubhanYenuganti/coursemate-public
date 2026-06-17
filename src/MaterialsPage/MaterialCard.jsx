import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { formatDateTime } from "../utils/dateUtils";
import { getMeta } from "./constants";
import {
  FileTypeIcon,
  Spinner,
  VisibilityToggle,
  TrashIcon,
  SourceTypeBadge,
} from "./atoms";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function MaterialCard({
  material,
  courseId,
  onVisibilityChange,
  onDelete,
  isOwner,
}) {
  const [deleting, setDeleting] = useState(false);
  const navigate = useNavigate();

  const quizGenMatch = material?.file_url?.match(
    /^quiz:\/\/generation\/(\d+)$/,
  );
  const quizGenerationId = quizGenMatch ? quizGenMatch[1] : null;
  const flashcardsGenMatch = material?.file_url?.match(
    /^flashcards:\/\/generation\/(\d+)$/,
  );
  const flashcardsGenerationId = flashcardsGenMatch
    ? flashcardsGenMatch[1]
    : null;
  const reportGenMatch = material?.file_url?.match(
    /^report:\/\/generation\/(\d+)$/,
  );
  const reportGenerationId = reportGenMatch ? reportGenMatch[1] : null;
  const driveFallbackUrl = material?.external_id
    ? `https://drive.google.com/file/d/${material.external_id}/view`
    : null;
  const materialOpenUrl =
    material?.source_type === "gdrive"
      ? material?.outsourced_url || driveFallbackUrl || material?.download_url
      : material?.source_type !== "upload" && material?.outsourced_url
        ? material.outsourced_url
        : material?.download_url;
  const isIntegrationMaterial =
    material?.source_type === "gdrive" || material?.source_type === "notion";
  const lastEditedAt = isIntegrationMaterial
    ? formatDateTime(material?.external_last_edited)
    : "";
  const lastUpdatedAt = isIntegrationMaterial
    ? formatDateTime(material?.updated_at)
    : "";

  return (
    <Card className="flex flex-row rounded-lg overflow-hidden hover:shadow-md transition-shadow group gap-0 py-0">
      {/* Color accent strip */}
      <div className={`w-1 shrink-0 ${getMeta(material.file_type).accent}`} />

      {/* Icon area */}
      <div className="flex items-center justify-center px-4 py-4 bg-muted/40 border-r border-border/50">
        <FileTypeIcon type={material.file_type} large />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 px-4 py-3 flex flex-col justify-center gap-0.5">
        {quizGenerationId ? (
          <button
            type="button"
            onClick={() =>
              navigate(`/course/${courseId}/quiz/${quizGenerationId}`)
            }
            className="text-sm font-bold text-foreground hover:text-accent-foreground hover:underline underline-offset-2 line-clamp-2 leading-snug text-left"
          >
            {material.name}
          </button>
        ) : flashcardsGenerationId ? (
          <button
            type="button"
            onClick={() =>
              navigate(
                `/course/${courseId}/flashcards/${flashcardsGenerationId}`,
              )
            }
            className="text-sm font-bold text-foreground hover:text-accent-foreground hover:underline underline-offset-2 line-clamp-2 leading-snug text-left"
          >
            {material.name}
          </button>
        ) : reportGenerationId ? (
          <button
            type="button"
            onClick={() =>
              navigate(`/course/${courseId}/reports/${reportGenerationId}`)
            }
            className="text-sm font-bold text-foreground hover:text-accent-foreground hover:underline underline-offset-2 line-clamp-2 leading-snug text-left"
          >
            {material.name}
          </button>
        ) : (
          <a
            href={materialOpenUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-bold text-foreground hover:text-accent-foreground hover:underline underline-offset-2 line-clamp-2 leading-snug"
          >
            {material.name}
          </a>
        )}
        <div className="flex items-center gap-1.5 flex-wrap">
          <p className="text-xs text-muted-foreground">
            {getMeta(material.file_type).label}
            {material.visibility === "public" ? " · Public" : " · Private"}
          </p>
          <SourceTypeBadge sourceType={material.source_type} />
        </div>
        {lastEditedAt && (
          <p className="text-xs text-muted-foreground">
            Last Edited At: {lastEditedAt}
          </p>
        )}
        {lastUpdatedAt && (
          <p className="text-xs text-muted-foreground">
            Last Updated At: {lastUpdatedAt}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col items-end justify-between px-3 py-3 shrink-0">
        {isOwner && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={async () => {
              setDeleting(true);
              await onDelete(material);
            }}
            disabled={deleting}
            className="h-7 w-7 text-muted-foreground/50 hover:text-destructive"
            title="Delete material"
          >
            {deleting ? (
              <Spinner size={14} className="text-muted-foreground" />
            ) : (
              <TrashIcon size={14} />
            )}
          </Button>
        )}

        {isOwner && (
          <div className="flex items-center gap-1 mt-auto">
            <VisibilityToggle
              isPublic={material.visibility === "public"}
              onChange={(val) => onVisibilityChange(material.id, val)}
              disabled={material.updating}
              size="sm"
            />
          </div>
        )}
      </div>
    </Card>
  );
}
