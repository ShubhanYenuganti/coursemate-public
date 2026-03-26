import { useEffect, useMemo, useState } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

// ─── Icons ─────────────────────────────────────────────────────────────────────

function RefreshIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </svg>
  );
}

function BookmarkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18" /><path d="m6 6 12 12" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

const SAFE_HTML_TAGS = new Set([
  'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'section', 'span', 'strong', 'sub', 'sup', 'table',
  'tbody', 'td', 'th', 'thead', 'tr', 'u', 'ul',
]);

const SAFE_HTML_ATTRS = new Set([
  'alt', 'aria-label', 'aria-hidden', 'class', 'colspan', 'href', 'rel', 'role', 'rowspan', 'scope',
  'src', 'target', 'title',
]);

function sanitizeHtml(html) {
  if (!html) return '';
  if (typeof document === 'undefined') return '';

  const template = document.createElement('template');
  template.innerHTML = html;

  const sanitizeNode = (root) => {
    for (const child of Array.from(root.querySelectorAll('*'))) {
      if (!child.isConnected) continue;

      const tagName = child.tagName.toLowerCase();
      if (!SAFE_HTML_TAGS.has(tagName)) {
        child.replaceWith(...Array.from(child.childNodes));
        continue;
      }

      for (const attr of Array.from(child.attributes)) {
        const attrName = attr.name.toLowerCase();
        const attrValue = attr.value || '';
        const isEventHandler = attrName.startsWith('on');
        const isStyleAttr = attrName === 'style';
        const isAllowed = SAFE_HTML_ATTRS.has(attrName) || attrName.startsWith('data-');
        if (isEventHandler || isStyleAttr || !isAllowed) {
          child.removeAttribute(attr.name);
          continue;
        }
        if (attrName === 'href' || attrName === 'src') {
          const trimmed = attrValue.trim();
          const hasScheme = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed);
          const scheme = hasScheme ? trimmed.split(':', 1)[0].toLowerCase() : '';
          const isSafeUrl =
            (!hasScheme && (trimmed.startsWith('/') || trimmed.startsWith('./') || trimmed.startsWith('../') || trimmed.startsWith('#'))) ||
            scheme === 'http' ||
            scheme === 'https' ||
            scheme === 'mailto' ||
            scheme === 'tel';
          if (!isSafeUrl) {
            child.removeAttribute(attr.name);
          }
        }
        if (tagName === 'a' && attrName === 'target' && attrValue === '_blank') {
          child.setAttribute('rel', 'noopener noreferrer');
        }
      }
    }
  };

  sanitizeNode(template.content);
  return template.innerHTML;
}

// ─── File type badge (same palette as rest of app) ─────────────────────────────

const FILE_TYPE_MAP = {
  pdf:  { label: 'PDF', bg: 'bg-rose-100',   text: 'text-rose-600'   },
  doc:  { label: 'DOC', bg: 'bg-blue-100',   text: 'text-blue-600'   },
  docx: { label: 'DOC', bg: 'bg-blue-100',   text: 'text-blue-600'   },
  txt:  { label: 'TXT', bg: 'bg-gray-100',   text: 'text-gray-500'   },
};

function FileTypeBadge({ name }) {
  const ext = (name || '').split('.').pop().toLowerCase();
  const style = FILE_TYPE_MAP[ext] || { label: ext.slice(0, 3).toUpperCase() || 'DOC', bg: 'bg-gray-100', text: 'text-gray-500' };
  return (
    <span className={`flex-shrink-0 inline-flex items-center justify-center w-[34px] h-[21px] rounded text-[8px] font-bold tracking-tight ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

// ─── Inline math renderer ───────────────────────────────────────────────────────

// Splits text on $...$ delimiters and renders math spans with KaTeX.
// Returns a plain string when there is no math, or a React node array when math is present.
function renderInlineMath(text) {
  if (!text || !text.includes('$')) return text;
  // Capturing group preserves the delimiter in the split result array.
  const parts = text.split(/(\$[^\n$]+?\$)/);
  if (parts.length === 1) return text;
  return parts.map((part, i) => {
    if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
      const math = part.slice(1, -1);
      try {
        const html = katex.renderToString(math, { throwOnError: false, displayMode: false });
        // eslint-disable-next-line react/no-danger
        return <span key={i} dangerouslySetInnerHTML={{ __html: html }} />;
      } catch {
        return part;
      }
    }
    return part;
  });
}

// ─── Document content renderer ─────────────────────────────────────────────────

// Renders structured sections array OR falls back to raw HTML / markdown string.
function DocumentBody({ report, zoom }) {
  const html = report.html || report.content_html;
  const sanitizedHtml = useMemo(() => sanitizeHtml(html), [html]);

  // Prefer structured sections, then html, then markdown/content string
  const sections = report.sections || report.sections_json;
  if (sections && Array.isArray(sections)) {
    const normalizedReport = sections === report.sections ? report : { ...report, sections };
    return <StructuredDocument report={normalizedReport} zoom={zoom} />;
  }
  if (html) {
    return (
      <div
        className="prose prose-sm max-w-none"
        style={{ fontSize: `${zoom}%` }}
        dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
      />
    );
  }
  const text = report.markdown || report.content || report.text || report.report || '';
  if (text) {
    return <MarkdownDocument text={text} zoom={zoom} />;
  }
  return <p className="text-sm text-gray-400 italic">No content available.</p>;
}

// Renders a structured sections array
function StructuredDocument({ report, zoom }) {
  const title = report.title || '';
  const subtitle = report.subtitle || '';
  const date = report.date || report.generated_at || '';
  const sections = report.sections || [];

  return (
    <div style={{ fontSize: `${zoom}%` }}>
      {title && (
        <div className="text-center mb-10">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{title}</h1>
          {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
          {date && <p className="text-xs text-gray-400 mt-1">{date}</p>}
        </div>
      )}
      {sections.map((block, i) => <DocBlock key={i} block={block} />)}
    </div>
  );
}

function DocBlock({ block }) {
  const type = block.type || 'paragraph';
  const content = block.content || block.text || '';

  if (type === 'heading' || type === 'section') {
    return (
      <h2 className="text-base font-bold text-gray-900 mt-8 mb-3 pb-1 border-b border-gray-100">
        {content}
      </h2>
    );
  }
  if (type === 'subheading' || type === 'subsection') {
    return (
      <h3 className="text-sm font-semibold text-gray-800 mt-5 mb-2">{content}</h3>
    );
  }
  if (type === 'callout') {
    return (
      <div className="my-4 pl-4 pr-4 py-3 bg-indigo-50 border-l-4 border-indigo-300 rounded-r-lg">
        <p className="text-sm text-indigo-700 italic leading-relaxed">{renderInlineMath(content)}</p>
      </div>
    );
  }
  if (type === 'equation' || type === 'display_equation') {
    const lines = Array.isArray(block.lines) ? block.lines : (content ? [content] : []);
    return (
      <div className="my-4 py-4 bg-gray-50 border border-gray-200 rounded-lg overflow-x-auto text-center">
        {lines.map((line, i) => {
          try {
            const html = katex.renderToString(line, { throwOnError: false, displayMode: true });
            // eslint-disable-next-line react/no-danger
            return <div key={i} className="py-1" dangerouslySetInnerHTML={{ __html: html }} />;
          } catch {
            return <p key={i} className="font-mono text-sm text-gray-700">{line}</p>;
          }
        })}
      </div>
    );
  }
  if (type === 'table') {
    const headers = Array.isArray(block.headers) ? block.headers : [];
    const rows = Array.isArray(block.rows) ? block.rows : [];
    if (headers.length === 0 && rows.length === 0) return null;
    return (
      <div className="overflow-x-auto my-4">
        <table className="w-full text-xs border-collapse">
          {headers.length > 0 && (
            <thead className="bg-gray-100 text-gray-700">
              <tr className="border-b border-gray-200">
                {headers.map((h, i) => (
                  <th key={i} className="px-3 py-1.5 text-left font-semibold border border-gray-200">
                    {renderInlineMath(h)}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} className="border-b border-gray-200">
                {(Array.isArray(row) ? row : []).map((cell, ci) => (
                  <td key={ci} className="px-3 py-1.5 border border-gray-200">
                    {renderInlineMath(String(cell))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (type === 'bullet_list' || type === 'list') {
    const items = Array.isArray(block.items) ? block.items : [content];
    return (
      <ul className="my-3 space-y-1.5 pl-5 list-disc">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-gray-700 leading-relaxed">{renderInlineMath(item)}</li>
        ))}
      </ul>
    );
  }
  if (type === 'page_break') {
    const page = block.page || '';
    return (
      <div className="my-8 flex items-center gap-3">
        <div className="flex-1 h-px bg-gray-200" />
        {page && <span className="text-[10px] text-gray-400 flex-shrink-0">{page}</span>}
        <div className="flex-1 h-px bg-gray-200" />
      </div>
    );
  }
  // default: paragraph
  return (
    <p className="text-sm text-gray-700 leading-relaxed my-3">{renderInlineMath(content)}</p>
  );
}

// Very lightweight markdown → JSX for common report patterns
function MarkdownDocument({ text, zoom }) {
  const lines = text.split('\n');
  const elements = [];
  let listBuffer = [];
  let key = 0;

  function flushList() {
    if (listBuffer.length === 0) return;
    elements.push(
      <ul key={key++} className="my-3 space-y-1.5 pl-5 list-disc">
        {listBuffer.map((item, i) => (
          <li key={i} className="text-sm text-gray-700 leading-relaxed">{item}</li>
        ))}
      </ul>
    );
    listBuffer = [];
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // H1
    if (/^# /.test(line)) {
      flushList();
      elements.push(
        <h1 key={key++} className="text-2xl font-bold text-gray-900 text-center mb-2 mt-6">{line.replace(/^# /, '')}</h1>
      );
      continue;
    }
    // H2
    if (/^## /.test(line)) {
      flushList();
      elements.push(
        <h2 key={key++} className="text-base font-bold text-gray-900 mt-8 mb-3 pb-1 border-b border-gray-100">{line.replace(/^## /, '')}</h2>
      );
      continue;
    }
    // H3
    if (/^### /.test(line)) {
      flushList();
      elements.push(
        <h3 key={key++} className="text-sm font-semibold text-gray-800 mt-5 mb-2">{line.replace(/^### /, '')}</h3>
      );
      continue;
    }
    // Numbered section e.g. "1. Title" or "2.1 Title"
    if (/^\d+[\.\d]*\.?\s+\S/.test(line) && line.length < 100) {
      flushList();
      const isSubsection = /^\d+\.\d+/.test(line);
      elements.push(
        isSubsection
          ? <h3 key={key++} className="text-sm font-semibold text-gray-800 mt-5 mb-2">{line}</h3>
          : <h2 key={key++} className="text-base font-bold text-gray-900 mt-8 mb-3 pb-1 border-b border-gray-100">{line}</h2>
      );
      continue;
    }
    // Blockquote / callout
    if (/^> /.test(line)) {
      flushList();
      elements.push(
        <div key={key++} className="my-4 pl-4 pr-4 py-3 bg-indigo-50 border-l-4 border-indigo-300 rounded-r-lg">
          <p className="text-sm text-indigo-700 italic leading-relaxed">{line.replace(/^> /, '')}</p>
        </div>
      );
      continue;
    }
    // Bullet
    if (/^[-*] /.test(line)) {
      listBuffer.push(line.replace(/^[-*] /, ''));
      continue;
    }
    // Horizontal rule / page break
    if (/^---+$/.test(line.trim())) {
      flushList();
      elements.push(
        <div key={key++} className="my-8 flex items-center gap-3">
          <div className="flex-1 h-px bg-gray-200" />
        </div>
      );
      continue;
    }
    // Empty line
    if (line.trim() === '') {
      flushList();
      continue;
    }
    // Paragraph
    flushList();
    elements.push(
      <p key={key++} className="text-sm text-gray-700 leading-relaxed my-3">{line}</p>
    );
  }
  flushList();

  return <div style={{ fontSize: `${zoom}%` }}>{elements}</div>;
}

// ─── ReportsViewer ─────────────────────────────────────────────────────────────

export default function ReportsViewer({
  report,
  course,
  sourceMaterials = [],
  templateLabel = 'Study Guide',
  generationError = '',
  onClose,
  onRegenerate,
  onSaveComplete,
  onResolve,
}) {
  const [zoom, setZoom] = useState(100);
  const [copied, setCopied] = useState(false);
  const [saveStatus, setSaveStatus] = useState(report?.artifact_material_id ? 'saved' : 'idle');
  const [saveError, setSaveError] = useState('');
  const [exportStatus, setExportStatus] = useState('idle');
  const [resolving, setResolving] = useState(false);

  const courseName = course?.name || course?.title || 'Report';
  const title = report?.title || courseName;
  const generationId = report?.generation_id || null;
  const selectedSourceIds = useMemo(
    () => new Set(Array.isArray(report?.selected_material_ids) ? report.selected_material_ids.map(String) : []),
    [report?.selected_material_ids],
  );

  // Page count hint from the report
  const pageCount = report?.page_count || report?.pages || null;

  // Sources: prefer report-selected materials, then explicit report sources, then fallback list.
  const sources = useMemo(() => {
    if (selectedSourceIds.size > 0 && sourceMaterials.length > 0) {
      const resolved = sourceMaterials.filter((src) => selectedSourceIds.has(String(src.id)));
      if (resolved.length > 0) return resolved;
    }
    if (Array.isArray(report?.sources) && report.sources.length > 0) {
      return report.sources;
    }
    return sourceMaterials;
  }, [report?.sources, selectedSourceIds, sourceMaterials]);
  const saveButtonClasses = [
    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors',
    saveStatus === 'saved'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : 'border-gray-200 text-gray-600 hover:bg-gray-50',
    saveStatus === 'saving' || !generationId ? 'opacity-70 cursor-not-allowed' : '',
  ].join(' ');
  const exportButtonClasses = [
    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium transition-colors',
    exportStatus === 'exporting' || !generationId ? 'opacity-70 cursor-not-allowed' : 'hover:bg-indigo-700',
  ].join(' ');

  useEffect(() => {
    setSaveStatus(report?.artifact_material_id ? 'saved' : 'idle');
    setSaveError('');
    setExportStatus('idle');
  }, [report?.artifact_material_id, report?.generation_id]);

  function handleCopy() {
    const text = report?.markdown || report?.content || report?.text || report?.report || title;
    const clipboard = navigator?.clipboard;
    if (!clipboard?.writeText) return;
    clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      setCopied(false);
    });
  }

  async function handleSave() {
    if (!generationId || saveStatus === 'saving' || saveStatus === 'saved') return;

    setSaveStatus('saving');
    setSaveError('');
    try {
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ action: 'save_artifact', generation_id: generationId }),
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        const savedMaterialId = data?.artifact_material_id ?? data?.material_id ?? null;
        if (savedMaterialId) {
          onSaveComplete?.({
            generation_id: generationId,
            artifact_material_id: savedMaterialId,
          });
        }
        setSaveStatus('saved');
      } else {
        const data = await res.json().catch(() => ({}));
        setSaveError(data.error || `HTTP ${res.status}`);
        setSaveStatus('error');
      }
    } catch (error) {
      setSaveError(error?.message || 'Save failed');
      setSaveStatus('error');
    }
  }

  async function handleExport() {
    if (!generationId || exportStatus === 'exporting') return;

    setExportStatus('exporting');
    try {
      const res = await fetch(`/api/reports?action=export_pdf&generation_id=${generationId}`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(title || 'report').replace(/\s+/g, '_').toLowerCase()}-${generationId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportStatus('idle');
    } catch {
      setExportStatus('error');
    }
  }

  async function handleResolve(resolution) {
    if (!generationId || !report?.parent_generation_id || resolving) return;
    setResolving(true);
    try {
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          action: 'resolve_regeneration',
          generation_id: generationId,
          parent_generation_id: report.parent_generation_id,
          resolution,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) onResolve?.(resolution, data);
    } catch {
      // keep banner visible to allow retry
    } finally {
      setResolving(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50 to-blue-50 flex flex-col">

      {/* ── Resolve banner ── */}
      {report?.parent_generation_id && (
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
            <p className="text-sm text-amber-800 font-medium">
              New version generated. What would you like to do with the previous version?
            </p>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                type="button"
                onClick={() => handleResolve('save_both')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg border border-amber-300 text-xs font-medium text-amber-800 hover:bg-amber-100 transition-colors disabled:opacity-50"
              >
                Save Both
              </button>
              <button
                type="button"
                onClick={() => handleResolve('replace')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg border border-amber-300 text-xs font-medium text-amber-800 hover:bg-amber-100 transition-colors disabled:opacity-50"
              >
                Replace Previous
              </button>
              <button
                type="button"
                onClick={() => handleResolve('revert')}
                disabled={resolving}
                className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-medium hover:bg-amber-700 transition-colors disabled:opacity-50"
              >
                Revert
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-100 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-gray-900">{courseName}</span>
            <span className="px-2.5 py-0.5 rounded-full border border-indigo-200 text-xs font-medium text-indigo-600 bg-white">
              {templateLabel}
            </span>
            {generationError ? (
              <span className="px-2 py-0.5 rounded-md border border-red-200 bg-red-50 text-[11px] text-red-700">
                {generationError}
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onRegenerate?.({ parent_generation_id: report?.generation_id })}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
            >
              <RefreshIcon />
              Regenerate
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={!generationId || saveStatus === 'saving' || saveStatus === 'saved'}
              className={saveButtonClasses}
              title={saveStatus === 'error' ? saveError : undefined}
            >
              <BookmarkIcon />
              {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved ✓' : saveStatus === 'error' ? 'Retry Save' : 'Save Report'}
            </button>
            <button
              type="button"
              onClick={handleExport}
              disabled={!generationId || exportStatus === 'exporting'}
              className={exportButtonClasses}
            >
              <DownloadIcon />
              {exportStatus === 'exporting' ? 'Exporting…' : exportStatus === 'error' ? 'Retry Export' : 'Export as PDF'}
            </button>
            <div className="w-px h-5 bg-gray-200 mx-1" />
            <button
              type="button"
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <SettingsIcon />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <XIcon />
            </button>
          </div>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 gap-4 p-4 max-w-7xl mx-auto w-full">

        {/* Sources sidebar */}
        <aside className="w-[220px] flex-shrink-0 bg-white rounded-2xl border border-gray-200 shadow-sm self-start overflow-hidden">
          <div className="px-4 pt-4 pb-3 border-b border-gray-100">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Sources</span>
              <span className="text-[10px] text-gray-400 tabular-nums">{sources.length}</span>
            </div>
            <p className="text-[10px] text-gray-400 leading-snug">Materials used in this report</p>
          </div>

          <div className="py-2">
            {sources.length === 0 && (
              <p className="px-4 py-2 text-[10px] text-gray-400 italic">No sources listed.</p>
            )}
            {sources.map((src, i) => {
              const name = src.name || src.filename || src.title || String(src);
              return (
                <div key={i} className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-gray-50 transition-colors">
                  <FileTypeBadge name={name} />
                  <span className="flex-1 min-w-0 text-xs text-gray-600 truncate" title={name}>{name}</span>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Document viewer */}
        <div className="flex-1 min-w-0 bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col overflow-hidden">
          {/* Viewer toolbar */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-gray-100 flex-shrink-0">
            <span className="text-sm text-gray-400">
              {pageCount ? `${pageCount} page${pageCount > 1 ? 's' : ''}` : ''}
            </span>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-0.5 p-1 bg-gray-100 rounded-lg">
                {[75, 100, 125].map((z) => (
                  <button
                    key={z}
                    type="button"
                    onClick={() => setZoom(z)}
                    className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                      zoom === z ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    {z}%
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={handleCopy}
                title={copied ? 'Copied!' : 'Copy content'}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <CopyIcon />
              </button>
            </div>
          </div>

          {/* Scrollable document area */}
          <div className="flex-1 overflow-y-auto px-6 py-8 bg-gray-50">
            <div
              className="mx-auto bg-white rounded-xl border border-gray-100 shadow-sm px-14 py-12"
              style={{ maxWidth: `${Math.round(640 * zoom / 100)}px` }}
            >
              <DocumentBody report={report || {}} zoom={zoom} />
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
