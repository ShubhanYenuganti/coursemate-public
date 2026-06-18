import { useState } from 'react';

// ─── streaming status bubble ──────────────────────────────────────────────────

function materialTraceName(materialMap, materialId, limit = 25) {
  const mat = (materialMap || {})[materialId];
  const raw = mat?.name || mat?.title || mat?.filename || mat?.material_title;
  return raw ? raw.replace(/\.[^.]+$/, '').slice(0, limit) : `material ${materialId}`;
}

export function LiveStatusLine({ liveToolTrace, materials }) {
  const materialMap = {};
  (materials || []).forEach((m) => { materialMap[m.id] = m; });
  const last = liveToolTrace?.[liveToolTrace.length - 1];
  let text = 'Searching course materials…';
  if (last) {
    if (last.tool === 'web_search') {
      text = 'Searching the web…';
    } else if (last.tool === 'web_url_view') {
      let display = last.args?.url || '';
      try {
        const u = new URL(display);
        display = (u.hostname + u.pathname).replace(/^www\./, '').slice(0, 50);
      } catch {}
      text = `Viewing ${display}…`;
    } else {
      const name = materialTraceName(materialMap, last.args?.material_id);
      if (last.tool === 'get_page_content') text = `Retrieving pages ${last.args?.pages || '?'} from ${name}`;
      else if (last.tool === 'get_material_structure') text = `Reading structure of ${name}`;
      else if (last.tool === 'get_related_materials') text = `Finding related materials for ${name}`;
    }
  }
  return (
    <div className="flex items-center gap-2 mb-2">
      <div className="flex gap-0.5 items-center">
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '120ms' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '240ms' }} />
      </div>
      <span className="text-[11px] text-muted-foreground">{text}</span>
    </div>
  );
}

function getTracePrimary(status, materialMap) {
  switch (status.phase) {
    case 'handoff_decision': {
      const rec = status.recommendation || 'optional';
      const confPct = Number.isFinite(Number(status.confidence))
        ? `${Math.round(Number(status.confidence) * 100)}%`
        : 'unknown';
      if (status.override) return `Handoff says "${rec}" at ${confPct} confidence — override enabled, web search remains available`;
      if (status.web_search_allowed === false) return `Handoff says "${rec}" at ${confPct} confidence — web search constrained unless strong contradiction appears`;
      return `Handoff says "${rec}" at ${confPct} confidence — web search can be used if needed`;
    }
    case 'loop_start':
      return `Agentic pass ${status.iteration}${status.maxIteration ? ` of ${status.maxIteration}` : ''}: evaluating evidence and tool options`;
    case 'sources_found':
      return `Retrieved ${status.result_count || 0} course chunks and grounding context`;
    case 'web_search_start':
      return 'Running web search for external coverage and implementation details';
    case 'web_result':
      return `Inspecting web result from ${status.hostname || 'source'}`;
    case 'rerank':
      return `Re-ranking candidate chunks by relevance (${status.input_count || '?'} → ${status.output_count || '?'})`;
    case 'page_fetch': {
      const name = materialTraceName(materialMap, status.material_id);
      return `Fetched pages ${status.pages || '?'} from ${name}`;
    }
    case 'structure_fetch': {
      const name = materialTraceName(materialMap, status.material_id);
      return `Retrieved structure of ${name}`;
    }
    case 'related_fetch': {
      const name = materialTraceName(materialMap, status.material_id);
      return `Looked up materials related to ${name}`;
    }
    default:
      return 'Initializing retrieval and planning tool steps…';
  }
}

function getTraceSecondary(status, materialMap) {
  switch (status.phase) {
    case 'sources_found': {
      const chunks = status.chunks || [];
      if (!chunks.length) return null;
      const parts = chunks.map((c) => {
        const name = c.material_id != null ? materialTraceName(materialMap, c.material_id, 20) : null;
        return name ? `${name} — "${c.snippet}"` : `"${c.snippet}"`;
      });
      return parts.join('  ·  ');
    }
    case 'web_search_start':
      return status.query ? `"${status.query.slice(0, 60)}"` : null;
    case 'web_result':
      return status.excerpt ? `"${status.excerpt}"` : null;
    case 'handoff_decision': {
      const details = [];
      if (status.override) details.push(`Guardrail override: confidence ${status.confidence ?? '?'} below threshold ${status.threshold ?? '?'}`);
      else if (status.recommendation === 'not_needed') details.push(`High-confidence no-search recommendation (threshold ${status.threshold ?? '?'})`);
      if (Array.isArray(status.missing_facts) && status.missing_facts.length) details.push(`Possible gaps: ${status.missing_facts.slice(0, 2).join(' · ')}`);
      if (Array.isArray(status.suggested_queries) && status.suggested_queries.length) details.push(`Candidate queries: ${status.suggested_queries.slice(0, 2).join(' | ')}`);
      if (!details.length && status.reasoning) details.push(status.reasoning);
      return details.join('  ·  ') || null;
    }
    default:
      return null;
  }
}

function toolTraceToEvents(toolTrace) {
  const events = [];
  const seenIterations = new Set();
  for (const entry of (toolTrace || [])) {
    if (entry.iteration != null && !seenIterations.has(entry.iteration)) {
      seenIterations.add(entry.iteration);
      events.push({ phase: 'loop_start', iteration: entry.iteration, maxIteration: null });
    }
    if (entry.tool === 'search_materials') {
      events.push({ phase: 'sources_found', result_count: entry.result_count || 0, chunks: [] });
    } else if (entry.tool === 'web_search') {
      events.push({ phase: 'web_search_start', query: '' });
      for (const u of (entry.urls || [])) {
        let hostname = u.url || '';
        try { hostname = new URL(u.url).hostname.replace(/^www\./, ''); } catch {}
        events.push({ phase: 'web_result', url: u.url, hostname, excerpt: u.title || '' });
      }
    } else if (entry.tool === 'rerank_results') {
      events.push({ phase: 'rerank', input_count: entry.result_count, output_count: entry.result_count });
    } else if (entry.tool === 'get_page_content') {
      events.push({ phase: 'page_fetch', material_id: entry.args?.material_id, pages: entry.args?.pages });
    } else if (entry.tool === 'get_material_structure') {
      events.push({ phase: 'structure_fetch', material_id: entry.args?.material_id });
    } else if (entry.tool === 'get_related_materials') {
      events.push({ phase: 'related_fetch', material_id: entry.args?.material_id });
    }
  }
  return events;
}

export function ToolTraceIndicator({ toolTrace, materials }) {
  const [open, setOpen] = useState(false);
  const events = toolTraceToEvents(toolTrace);
  if (!events.length) return null;
  const materialMap = {};
  (materials || []).forEach((m) => { materialMap[m.id] = m; });
  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-primary transition-colors select-none"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-70"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
        <span>{events.length} reasoning steps</span>
        <span className="opacity-50">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-1.5 pl-1 border-l-2 border-border">
          {events.map((s, i) => {
            const secondary = getTraceSecondary(s, materialMap);
            return (
              <div key={i} className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-primary/40 mt-1 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-[11px] text-foreground leading-snug">{getTracePrimary(s, materialMap)}</p>
                  {secondary && <p className="text-[10px] text-muted-foreground leading-snug truncate">{secondary}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
