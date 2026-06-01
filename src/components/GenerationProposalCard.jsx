import React from 'react';

const TYPE_LABEL = { quiz: 'Quiz', flashcards: 'Flashcards', report: 'Report' };

export default function GenerationProposalCard({ proposal, onBuild, onRefine, status }) {
  if (!proposal) return null;
  const { generation_type, title, material_ids = [], params = {} } = proposal;
  const paramSummary = Object.entries(params)
    .map(([k, v]) => `${v} ${k.replace(/_count$/, '').replace(/_/g, ' ')}`)
    .join(' · ');

  return (
    <div className="mt-2 rounded-xl border border-indigo-200 bg-indigo-50/60 p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-indigo-700">
        <span>💡 {TYPE_LABEL[generation_type] || 'Generation'}</span>
        <span className="text-indigo-400">·</span>
        <span className="truncate">{title}</span>
      </div>
      <div className="mt-1 text-[11px] text-indigo-600/80">
        {paramSummary && <span>{paramSummary} · </span>}
        <span>{material_ids.length} material{material_ids.length === 1 ? '' : 's'} + this conversation</span>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={onBuild}
          disabled={status === 'building'}
          className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {status === 'building' ? 'Queuing…' : status === 'queued' ? 'Queued ✓' : 'Build'}
        </button>
        <button
          type="button"
          onClick={onRefine}
          disabled={status === 'building'}
          className="px-3 py-1.5 rounded-lg border border-indigo-300 text-indigo-700 text-xs font-medium hover:bg-indigo-100"
        >
          Refine
        </button>
      </div>
    </div>
  );
}
