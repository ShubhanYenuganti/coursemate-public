import { useState, useEffect, useRef, useCallback } from 'react';

// ─── constants ───────────────────────────────────────────────────────────────

const ACCEPTED_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain', 'image/jpeg', 'image/png', 'image/gif', 'image/svg+xml',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/csv',
]);

const TYPE_META = {
  'application/pdf':   { label: 'PDF',  color: 'text-red-600',     bg: 'bg-red-50',     border: 'border-red-200',     accent: 'bg-red-500' },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                       { label: 'DOCX', color: 'text-blue-600',    bg: 'bg-blue-50',    border: 'border-blue-200',    accent: 'bg-blue-500' },
  'text/plain':        { label: 'TXT',  color: 'text-gray-600',    bg: 'bg-gray-50',    border: 'border-gray-200',    accent: 'bg-gray-400' },
  'image/jpeg':        { label: 'JPG',  color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200', accent: 'bg-emerald-500' },
  'image/png':         { label: 'PNG',  color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200', accent: 'bg-emerald-500' },
  'image/gif':         { label: 'GIF',  color: 'text-purple-600',  bg: 'bg-purple-50',  border: 'border-purple-200',  accent: 'bg-purple-500' },
  'image/svg+xml':     { label: 'SVG',  color: 'text-orange-600',  bg: 'bg-orange-50',  border: 'border-orange-200',  accent: 'bg-orange-500' },
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                       { label: 'XLSX', color: 'text-teal-600',    bg: 'bg-teal-50',    border: 'border-teal-200',    accent: 'bg-teal-500' },
  'text/csv':          { label: 'CSV',  color: 'text-teal-600',    bg: 'bg-teal-50',    border: 'border-teal-200',    accent: 'bg-teal-500' },
};

function getMeta(type) {
  return TYPE_META[type] ?? { label: 'FILE', color: 'text-gray-500', bg: 'bg-gray-50', border: 'border-gray-200', accent: 'bg-gray-400' };
}

function fmtSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

let _seq = 0;
function uid() { return ++_seq; }

// ─── small shared pieces ─────────────────────────────────────────────────────

function FileTypeIcon({ type, large = false }) {
  const { label, color, bg, border } = getMeta(type);
  const w = large ? 52 : 40;
  const h = large ? 62 : 48;
  return (
    <div
      className={`flex flex-col items-center justify-between rounded border ${bg} ${border} shrink-0`}
      style={{ width: w, height: h, padding: '4px 3px 3px' }}
    >
      <svg width={large ? 22 : 18} height={large ? 26 : 21} viewBox="0 0 20 24" fill="none" className={color}>
        <path d="M2 0C.9 0 0 .9 0 2v20c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V7L13 0H2Z" fill="currentColor" opacity=".12"/>
        <path d="M13 0v7h7L13 0Z" fill="currentColor" opacity=".35"/>
        <rect x="3" y="11" width="14" height="1.5" rx=".75" fill="currentColor" opacity=".45"/>
        <rect x="3" y="14" width="9"  height="1.5" rx=".75" fill="currentColor" opacity=".45"/>
        <rect x="3" y="17" width="11" height="1.5" rx=".75" fill="currentColor" opacity=".45"/>
      </svg>
      <span className={`font-bold leading-none ${color}`} style={{ fontSize: large ? 10 : 8 }}>{label}</span>
    </div>
  );
}

function Spinner({ size = 16, className = 'text-indigo-500' }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      className={`animate-spin ${className}`}
      style={{ animationDuration: '0.75s' }}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
        strokeDasharray="42 14" />
    </svg>
  );
}

function VisibilityToggle({ isPublic, onChange, disabled = false, size = 'md' }) {
  const track = size === 'sm'
    ? 'h-4 w-7' : 'h-5 w-9';
  const knob = size === 'sm'
    ? `h-3 w-3 ${isPublic ? 'translate-x-[14px]' : 'translate-x-0.5'}`
    : `h-3.5 w-3.5 ${isPublic ? 'translate-x-[18px]' : 'translate-x-0.5'}`;

  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!isPublic)}
      disabled={disabled}
      title={isPublic ? 'Public — click to make private' : 'Private — click to make public'}
      className={`relative inline-flex shrink-0 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-1 ${track} ${
        isPublic ? 'bg-indigo-500' : 'bg-gray-300'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <span className={`inline-block rounded-full bg-white shadow-sm transform transition-transform duration-200 ${knob}`} />
    </button>
  );
}

function TrashIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6l-1 14H6L5 6"/>
      <path d="M10 11v6M14 11v6"/>
      <path d="M9 6V4h6v2"/>
    </svg>
  );
}

// ─── upload drop zone ────────────────────────────────────────────────────────

function UploadZone({ onFiles, disabled }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const files = [...e.dataTransfer.files].filter(f => ACCEPTED_TYPES.has(f.type));
    if (files.length) onFiles(files);
  }, [onFiles, disabled]);

  const handleDragOver = (e) => { e.preventDefault(); if (!disabled) setDragging(true); };
  const handleDragLeave = () => setDragging(false);

  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold text-gray-800">Upload Files</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          PDF, DOCX, TXT, JPEG, PNG, GIF, SVG, XLSX, CSV · max 10 MB per file · batches of 3
        </p>
      </div>

      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed py-10 transition-all cursor-pointer select-none
          ${dragging
            ? 'border-indigo-400 bg-indigo-50'
            : 'border-gray-200 bg-gray-50/60 hover:border-indigo-300 hover:bg-indigo-50/30'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
          dragging ? 'bg-indigo-200' : 'bg-gray-200/80'
        }`}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            className={dragging ? 'text-indigo-600' : 'text-gray-500'}>
            <path d="M12 19V5M5 12l7-7 7 7"/>
          </svg>
        </div>
        <p className="text-sm text-gray-500">
          <span className="text-indigo-600 font-medium">Browse</span>
          {' '}or drag files here
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={[...ACCEPTED_TYPES].join(',')}
          className="sr-only"
          onChange={e => {
            const files = [...e.target.files].filter(f => ACCEPTED_TYPES.has(f.type));
            if (files.length) onFiles(files);
            e.target.value = '';
          }}
        />
      </div>
    </div>
  );
}

// ─── upload item row ──────────────────────────────────────────────────────────

function UploadItemRow({ item, onVisibilityChange, onDismiss }) {
  const isLoading = item.status === 'uploading';
  const isDone    = item.status === 'done';
  const isError   = item.status === 'error';

  return (
    <div className={`rounded-lg border bg-white transition-all ${
      isError ? 'border-red-200 bg-red-50/40' : 'border-gray-200'
    }`}>
      {/* Main row */}
      <div className="flex items-center gap-3 px-3 py-2.5">
        <FileTypeIcon type={item.file.type} />

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate">{item.file.name}</p>
          <p className="text-xs text-gray-400">{fmtSize(item.file.size)}</p>
        </div>

        {/* State indicator */}
        <div className="flex items-center gap-2 shrink-0">
          {isLoading && (
            <span className="flex items-center gap-1.5 text-xs text-indigo-500 font-medium">
              <Spinner size={13} />
              Uploading…
            </span>
          )}
          {isDone && (
            <span className="text-xs text-emerald-600 font-medium">✓ Done</span>
          )}
          {isError && (
            <span className="text-xs text-red-500 font-medium" title={item.error}>Failed</span>
          )}

          <button
            type="button"
            onClick={() => onDismiss(item.id)}
            className="p-1 rounded text-gray-300 hover:text-gray-500 transition-colors"
            title="Dismiss"
          >
            <TrashIcon size={14} />
          </button>
        </div>
      </div>

      {/* Loading progress banner — shown while uploading */}
      {isLoading && (
        <div className="mx-3 mb-2.5 h-1 rounded-full bg-gray-100 overflow-hidden">
          <div className="h-full bg-indigo-400 rounded-full animate-[loading-bar_1.6s_ease-in-out_infinite]" style={{ width: '60%' }} />
        </div>
      )}

      {/* Visibility toggle row — shown only after confirmed done */}
      {isDone && (
        <div className="flex items-center justify-between px-3 pb-2.5">
          <span className="text-xs text-gray-400">
            {item.visibilityUpdating ? 'Saving…' : (item.isPublic ? 'Public' : 'Private')}
          </span>
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-gray-400">Private</span>
            <VisibilityToggle
              isPublic={item.isPublic}
              onChange={(val) => onVisibilityChange(item.id, val)}
              disabled={item.visibilityUpdating}
              size="sm"
            />
            <span className="text-[11px] text-gray-400">Public</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── material grid card (existing materials) ──────────────────────────────────

function MaterialCard({ material, onVisibilityChange, onDelete, isOwner }) {
  const [deleting, setDeleting] = useState(false);

  return (
    <div className="flex rounded-lg border border-gray-200 bg-white overflow-hidden hover:shadow-md transition-shadow group">
      {/* Blue left accent matching PDF_modal_ex.png */}
      <div className={`w-1 shrink-0 ${getMeta(material.file_type).accent}`} />

      {/* Icon area */}
      <div className="flex items-center justify-center px-4 py-4 bg-gray-50/70 border-r border-gray-100">
        <FileTypeIcon type={material.file_type} large />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 px-4 py-3 flex flex-col justify-center gap-0.5">
        <a
          href={material.download_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-bold text-gray-900 hover:text-indigo-700 hover:underline underline-offset-2 line-clamp-2 leading-snug"
        >
          {material.name}
        </a>
        <p className="text-xs text-gray-400">
          {getMeta(material.file_type).label}
          {material.visibility === 'public' ? ' · Public' : ' · Private'}
        </p>
      </div>

      {/* Actions */}
      <div className="flex flex-col items-end justify-between px-3 py-3 shrink-0">
        {isOwner && (
          <button
            type="button"
            onClick={async () => {
              setDeleting(true);
              await onDelete(material.id);
            }}
            disabled={deleting}
            className="p-1 rounded text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
            title="Delete material"
          >
            {deleting ? <Spinner size={14} className="text-gray-400" /> : <TrashIcon size={14} />}
          </button>
        )}

        {isOwner && (
          <div className="flex items-center gap-1 mt-auto">
            <VisibilityToggle
              isPublic={material.visibility === 'public'}
              onChange={(val) => onVisibilityChange(material.id, val)}
              disabled={material.updating}
              size="sm"
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

// ─── filter pill bar ──────────────────────────────────────────────────────────

function FilterBar({ ownerFilter, setOwnerFilter, typeFilter, setTypeFilter }) {
  const ownerPills = [
    { id: 'all',  label: 'All materials' },
    { id: 'mine', label: 'My materials' },
  ];
  const typePills = [
    { id: 'all',       label: 'All types',  prefix: null },
    { id: 'uploaded',  label: 'Uploaded',   prefix: '↑' },
    { id: 'generated', label: 'Generated',  prefix: '✦' },
  ];

  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-full bg-gray-900 w-fit flex-wrap">
      {/* Owner group */}
      <div className="flex items-center gap-1">
        {ownerPills.map(p => (
          <button
            key={p.id}
            type="button"
            onClick={() => setOwnerFilter(p.id)}
            className={`px-3.5 py-1.5 rounded-full text-sm font-medium transition-colors duration-150 focus:outline-none ${
              ownerFilter === p.id
                ? 'bg-white text-gray-900'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-gray-600" />

      {/* Type group label */}
      <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-widest select-none">Show</span>

      {/* Type group */}
      <div className="flex items-center gap-1">
        {typePills.map(p => (
          <button
            key={p.id}
            type="button"
            onClick={() => setTypeFilter(p.id)}
            className={`flex items-center gap-1 px-3.5 py-1.5 rounded-full text-sm font-medium transition-colors duration-150 focus:outline-none ${
              typeFilter === p.id
                ? 'bg-gray-700 text-white'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {p.prefix && <span className="text-xs">{p.prefix}</span>}
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function MaterialsPage({ courseId, sessionToken, userId }) {
  const [materials, setMaterials]       = useState([]);
  const [loadingMats, setLoadingMats]   = useState(true);
  const [uploadItems, setUploadItems]   = useState([]);
  const [ownerFilter, setOwnerFilter]   = useState('all');
  const [typeFilter,  setTypeFilter]    = useState('all');

  // ── fetch existing materials ──────────────────────────────────────────────
  const fetchMaterials = useCallback(async () => {
    setLoadingMats(true);
    try {
      const res = await fetch(`/api/material?course_id=${courseId}`, {
        headers: { Authorization: `Bearer ${sessionToken}` },
      });
      const data = await res.json();
      setMaterials(data.materials || []);
    } catch {
      // silently fail — UI will show empty state
    } finally {
      setLoadingMats(false);
    }
  }, [courseId, sessionToken]);

  useEffect(() => { fetchMaterials(); }, [fetchMaterials]);

  // ── upload one file ──────────────────────────────────────────────────────
  const uploadOne = useCallback(async (item) => {
    const update = (patch) =>
      setUploadItems(prev => prev.map(i => i.id === item.id ? { ...i, ...patch } : i));

    update({ status: 'uploading' });

    try {
      // 1. Request presigned URL
      const r1 = await fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionToken}` },
        body: JSON.stringify({
          action: 'request_upload',
          course_id: courseId,
          filename: item.file.name,
          file_type: item.file.type,
          visibility: 'private',
        }),
      });
      if (!r1.ok) throw new Error('Failed to get upload URL');
      const { upload_url, fields, s3_key } = await r1.json();

      // 2. Upload directly to S3 via presigned POST
      const form = new FormData();
      Object.entries(fields).forEach(([k, v]) => form.append(k, v));
      form.append('file', item.file); // must be last
      const r2 = await fetch(upload_url, { method: 'POST', body: form });
      if (!r2.ok && r2.status !== 204) throw new Error('S3 upload failed');

      // 3. Confirm upload — creates DB record (loading banner stops here)
      const r3 = await fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionToken}` },
        body: JSON.stringify({
          action: 'confirm_upload',
          s3_key,
          course_id: courseId,
          filename: item.file.name,
          file_type: item.file.type,
          visibility: 'private',
        }),
      });
      if (!r3.ok) throw new Error('Upload confirmation failed');
      const { material } = await r3.json();

      update({ status: 'done', materialId: material.id, isPublic: false, visibilityUpdating: false });
    } catch (e) {
      update({ status: 'error', error: e.message });
    }
  }, [courseId, sessionToken]);

  // ── queue files in batches of 3 ──────────────────────────────────────────
  const handleFiles = useCallback(async (files) => {
    const items = files.map(f => ({
      id: uid(), file: f, status: 'queued',
      materialId: null, isPublic: false,
      visibilityUpdating: false, error: null,
    }));
    setUploadItems(prev => [...prev, ...items]);

    for (let i = 0; i < items.length; i += 3) {
      await Promise.all(items.slice(i, i + 3).map(uploadOne));
    }
    await fetchMaterials();
    // Files now appear in the grid — clear them from the upload list
    setUploadItems(prev => prev.filter(i => i.status !== 'done'));
  }, [uploadOne, fetchMaterials]);

  // ── visibility toggle for upload items ───────────────────────────────────
  const handleUploadItemVisibility = useCallback(async (id, isPublic) => {
    const item = uploadItems.find(i => i.id === id);
    if (!item?.materialId) return;

    setUploadItems(prev => prev.map(i => i.id === id ? { ...i, isPublic, visibilityUpdating: true } : i));
    try {
      await fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionToken}` },
        body: JSON.stringify({
          action: 'update_visibility',
          material_id: item.materialId,
          visibility: isPublic ? 'public' : 'private',
        }),
      });
      // Refresh materials grid so visibility badge stays in sync
      setMaterials(prev => prev.map(m => m.id === item.materialId
        ? { ...m, visibility: isPublic ? 'public' : 'private' } : m));
    } catch {
      // revert on failure
      setUploadItems(prev => prev.map(i => i.id === id ? { ...i, isPublic: !isPublic } : i));
    } finally {
      setUploadItems(prev => prev.map(i => i.id === id ? { ...i, visibilityUpdating: false } : i));
    }
  }, [uploadItems, sessionToken]);

  // ── visibility toggle for existing materials ──────────────────────────────
  const handleMaterialVisibility = useCallback(async (materialId, isPublic) => {
    setMaterials(prev => prev.map(m => m.id === materialId
      ? { ...m, visibility: isPublic ? 'public' : 'private', updating: true } : m));
    try {
      await fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionToken}` },
        body: JSON.stringify({
          action: 'update_visibility',
          material_id: materialId,
          visibility: isPublic ? 'public' : 'private',
        }),
      });
    } catch {
      // revert
      setMaterials(prev => prev.map(m => m.id === materialId
        ? { ...m, visibility: isPublic ? 'private' : 'public' } : m));
    } finally {
      setMaterials(prev => prev.map(m => m.id === materialId ? { ...m, updating: false } : m));
    }
  }, [sessionToken]);

  // ── delete material ──────────────────────────────────────────────────────
  const handleDelete = useCallback(async (materialId) => {
    try {
      await fetch('/api/material', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionToken}` },
        body: JSON.stringify({ material_id: materialId, course_id: courseId }),
      });
      setMaterials(prev => prev.filter(m => m.id !== materialId));
    } catch {
      // ignore
    }
  }, [courseId, sessionToken]);

  const dismissItem = (id) => setUploadItems(prev => prev.filter(i => i.id !== id));

  const activeUploads    = uploadItems.filter(i => i.status === 'uploading');
  const completedUploads = uploadItems.filter(i => i.status === 'done' || i.status === 'error');

  const visibleMaterials = materials.filter(m => {
    if (ownerFilter === 'mine' && m.uploaded_by !== userId) return false;
    if (typeFilter  === 'uploaded'  && m.source_type !== 'upload')     return false;
    if (typeFilter  === 'generated' && m.source_type !== 'generated')  return false;
    return true;
  });

  return (
    <div className="space-y-8 pb-4">
      {/* Upload section */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
        <UploadZone
          onFiles={handleFiles}
          disabled={false}
        />

        {/* Active upload queue */}
        {activeUploads.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Uploading</p>
            {activeUploads.map(item => (
              <UploadItemRow
                key={item.id}
                item={item}
                onVisibilityChange={handleUploadItemVisibility}
                onDismiss={dismissItem}
              />
            ))}
          </div>
        )}

        {/* Completed uploads */}
        {completedUploads.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              {activeUploads.length > 0 ? 'Completed' : 'Just uploaded'}
            </p>
            {completedUploads.map(item => (
              <UploadItemRow
                key={item.id}
                item={item}
                onVisibilityChange={handleUploadItemVisibility}
                onDismiss={dismissItem}
              />
            ))}
          </div>
        )}
      </div>

      {/* Materials grid */}
      <div>
        {/* Header + filter bar */}
        <div className="flex flex-col gap-3 mb-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-800">Course Materials</h2>
            {!loadingMats && (
              <span className="text-xs text-gray-400">
                {visibleMaterials.length} file{visibleMaterials.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <FilterBar
            ownerFilter={ownerFilter} setOwnerFilter={setOwnerFilter}
            typeFilter={typeFilter}   setTypeFilter={setTypeFilter}
          />
        </div>

        {loadingMats ? (
          <div className="flex items-center justify-center py-16">
            <Spinner size={28} className="text-indigo-400" />
          </div>
        ) : visibleMaterials.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-3 opacity-40">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <p className="text-sm">
              {materials.length === 0
                ? 'No materials yet — upload your first file above.'
                : 'No materials match the current filter.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {visibleMaterials.map(m => (
              <MaterialCard
                key={m.id}
                material={m}
                onVisibilityChange={handleMaterialVisibility}
                onDelete={handleDelete}
                isOwner={m.uploaded_by === userId}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
