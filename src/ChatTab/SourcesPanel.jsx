import { useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { ExternalLinkIcon, XIcon } from './icons';
import { getMaterialUrl } from '../utils/materialUtils';

export function SourcesPanel({ open, chunks, focusIndex, onClose, materials }) {
  const focusRef = useRef(null);
  const materialMap = {};
  (materials || []).forEach((m) => { materialMap[m.id] = m; });

  useEffect(() => {
    if (open && focusRef.current) {
      focusRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [open, focusIndex]);

  return (
    <div className={`absolute right-0 top-0 h-full w-80 bg-background border-l border flex flex-col shadow-xl z-20 transition-transform duration-200 ${open ? 'translate-x-0' : 'translate-x-full'}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0">
        <span className="text-sm font-semibold text-foreground">Sources ({chunks?.length || 0})</span>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-7 w-7 text-muted-foreground hover:text-foreground"
        >
          <XIcon />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {(chunks || []).map((chunk, idx) => {
          const n = idx + 1;
          const isFocused = n === focusIndex;
          const material = chunk.material_id != null ? materialMap[chunk.material_id] : null;
          const downloadUrl = getMaterialUrl(material) || null;
          const pageCount = (chunks || []).filter((c) => c.citation_type === 'page').length;

          if (chunk.citation_type === 'web') {
            const webNum = idx - pageCount + 1;
            let hostname = chunk.url || '';
            try { hostname = new URL(chunk.url).hostname.replace(/^www\./, ''); } catch {}
            return (
              <div
                key={idx}
                ref={isFocused ? focusRef : null}
                className={`rounded-lg px-3 py-2.5 border text-xs transition-colors ${
                  isFocused ? 'border-l-4 border-teal-400 bg-teal-50' : 'border bg-muted/40'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center justify-center px-1 h-4 rounded bg-teal-100 text-teal-700 font-semibold text-[10px] flex-shrink-0">
                    W{webNum}
                  </span>
                  <span className="text-foreground font-medium truncate flex-1">{chunk.title || hostname}</span>
                  {chunk.url && (
                    <a
                      href={chunk.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1 rounded text-muted-foreground hover:text-teal-600 hover:bg-teal-50 transition-colors flex-shrink-0"
                    >
                      <ExternalLinkIcon />
                    </a>
                  )}
                </div>
                {hostname && chunk.title && (
                  <div className="mt-0.5 ml-6 text-[10px] text-muted-foreground truncate">{hostname}</div>
                )}
              </div>
            );
          }

          if (chunk.citation_type === 'page') {
            const pages = chunk.pages || [];
            const pageLabel = pages.length === 0
              ? ''
              : pages.length === 1
                ? `p. ${pages[0]}`
                : `pp. ${pages[0]}–${pages[pages.length - 1]}`;
            return (
              <div
                key={idx}
                ref={isFocused ? focusRef : null}
                className={`rounded-lg px-3 py-2.5 border text-xs transition-colors ${
                  isFocused
                    ? 'border-l-4 border-primary bg-accent'
                    : 'border bg-muted/40'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center justify-center w-4 h-4 rounded bg-accent text-primary font-semibold text-[10px] flex-shrink-0">
                    {n}
                  </span>
                  {material?.name && (
                    <span className="text-foreground font-medium truncate">
                      {material.name.replace(/\.[^.]+$/, '')}
                    </span>
                  )}
                  {pageLabel && <span className="text-muted-foreground ml-auto flex-shrink-0">{pageLabel}</span>}
                  {downloadUrl && (
                    <a
                      href={downloadUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-accent transition-colors flex-shrink-0"
                    >
                      <ExternalLinkIcon />
                    </a>
                  )}
                </div>
              </div>
            );
          }

          return (
            <div
              key={idx}
              ref={isFocused ? focusRef : null}
              className={`rounded-lg px-3 py-2.5 border text-xs transition-colors ${
                isFocused
                  ? 'border-l-4 border-primary bg-accent'
                  : 'border bg-muted/40'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center w-4 h-4 rounded bg-accent text-primary font-semibold text-[10px] flex-shrink-0">
                  {n}
                </span>
                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium ${
                  chunk.chunk_type === 'visual' ? 'bg-orange-100 text-orange-600' : 'bg-blue-100 text-blue-600'
                }`}>
                  {chunk.chunk_type === 'visual' ? 'Slide' : 'Text'}
                </span>
                {material?.name && (
                  <span className="text-muted-foreground truncate text-[9px]">{material.name}</span>
                )}
                {chunk.page_number != null && (
                  <span className="text-muted-foreground">p.{chunk.page_number}</span>
                )}
                {chunk.similarity != null && (
                  <span className="text-muted-foreground tabular-nums">{chunk.similarity}</span>
                )}
                <div className="flex-1" />
                {downloadUrl ? (
                  <a
                    href={downloadUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-accent transition-colors flex-shrink-0"
                  >
                    <ExternalLinkIcon />
                  </a>
                ) : (
                  <span className="p-1 text-muted-foreground/30 flex-shrink-0">
                    <ExternalLinkIcon />
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
