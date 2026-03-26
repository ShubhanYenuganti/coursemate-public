import { useState, useEffect, useRef } from 'react';
import ReportsViewer from './ReportsViewer';
import GenerationConfirmModal from './components/GenerationConfirmModal.jsx';

// ─── icons ────────────────────────────────────────────────────────────────────

function PlusIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function SparkleIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
    </svg>
  );
}

function StudyGuideIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  );
}

function BriefingIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function SummaryIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <line x1="21" y1="10" x2="3" y2="10" />
      <line x1="21" y1="6" x2="3" y2="6" />
      <line x1="21" y1="14" x2="3" y2="14" />
      <line x1="21" y1="18" x2="9" y2="18" />
    </svg>
  );
}

function CreateOwnIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  );
}

// ─── shared mini-components ───────────────────────────────────────────────────

const FILE_TYPE_MAP = {
  pdf:  { label: 'PDF', bg: 'bg-rose-100',   text: 'text-rose-600'   },
  doc:  { label: 'DOC', bg: 'bg-blue-100',   text: 'text-blue-600'   },
  docx: { label: 'DOC', bg: 'bg-blue-100',   text: 'text-blue-600'   },
  xls:  { label: 'XLS', bg: 'bg-green-100',  text: 'text-green-700'  },
  xlsx: { label: 'XLS', bg: 'bg-green-100',  text: 'text-green-700'  },
  csv:  { label: 'CSV', bg: 'bg-green-100',  text: 'text-green-700'  },
  png:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  jpg:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  jpeg: { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  gif:  { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  svg:  { label: 'SVG', bg: 'bg-orange-100', text: 'text-orange-600' },
  txt:  { label: 'TXT', bg: 'bg-gray-100',   text: 'text-gray-500'   },
};

function FileTypeBadge({ name }) {
  const ext = (name || '').split('.').pop().toLowerCase();
  const style = FILE_TYPE_MAP[ext] || { label: ext.slice(0, 3).toUpperCase() || 'DOC', bg: 'bg-gray-100', text: 'text-gray-500' };
  return (
    <span className={`flex-shrink-0 inline-flex items-center justify-center w-[22px] h-[16px] rounded text-[7px] font-bold tracking-tight ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

function SourceToggle({ checked, onToggle }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
      className={`flex-shrink-0 relative inline-flex h-4 w-7 items-center rounded-full transition-colors focus:outline-none ${
        checked ? 'bg-indigo-500' : 'bg-gray-200'
      }`}
    >
      <span className={`inline-block h-3 w-3 transform rounded-full bg-white shadow-sm transition-transform ${
        checked ? 'translate-x-3.5' : 'translate-x-0.5'
      }`} />
    </button>
  );
}

// ─── template config ──────────────────────────────────────────────────────────

const TEMPLATES = [
  {
    id: 'study-guide',
    label: 'Study Guide',
    description: 'Structured outline with key concepts, definitions, and examples',
    Icon: StudyGuideIcon,
    customPrompt: false,
  },
  {
    id: 'briefing',
    label: 'Briefing',
    description: 'Executive summary of core topics for quick understanding',
    Icon: BriefingIcon,
    customPrompt: false,
  },
  {
    id: 'summary',
    label: 'Summary',
    description: 'Condensed overview of main points from the selected sources',
    Icon: SummaryIcon,
    customPrompt: false,
  },
  {
    id: 'custom',
    label: 'Create Your Own',
    description: 'Write a custom prompt to generate exactly what you need',
    Icon: CreateOwnIcon,
    customPrompt: true,
  },
];

const PROVIDER_MODELS = {
  claude: [
    { label: 'Claude Opus 4.6', id: 'claude-opus-4-6' },
    { label: 'Claude Sonnet 4.6', id: 'claude-sonnet-4-6' },
    { label: 'Claude Haiku 4.5', id: 'claude-haiku-4-5-20251001' },
    { label: 'Claude Sonnet 4.5', id: 'claude-sonnet-4-5-20250929' },
    { label: 'Claude Sonnet 4', id: 'claude-sonnet-4-20250514' },
    { label: 'Claude Opus 4', id: 'claude-opus-4-20250514' },
  ],
  gemini: [
    { label: 'Gemini 3.1 Pro', id: 'gemini-3.1-pro-preview' },
    { label: 'Gemini 3 Flash', id: 'gemini-3-flash-preview' },
    { label: 'Gemini 2.5 Pro', id: 'gemini-2.5-pro' },
    { label: 'Gemini 2.5 Flash', id: 'gemini-2.5-flash' },
    { label: 'Gemini 2.5 Flash-Lite', id: 'gemini-2.5-flash-lite' },
    { label: 'Deep Research', id: 'deep-research-pro-preview-12-2025' },
    { label: 'Gemini 2.0 Flash', id: 'gemini-2.0-flash' },
    { label: 'Gemini 2.0 Flash-Lite', id: 'gemini-2.0-flash-lite' },
  ],
  openai: [
    { label: 'GPT-5.2', id: 'gpt-5.2' },
    { label: 'GPT-5.1', id: 'gpt-5.1' },
    { label: 'GPT-5 Mini', id: 'gpt-5-mini' },
    { label: 'GPT-5 Nano', id: 'gpt-5-nano' },
    { label: 'GPT-4.1', id: 'gpt-4.1' },
    { label: 'GPT-4.1 mini', id: 'gpt-4.1-mini' },
    { label: 'GPT-4.1 nano', id: 'gpt-4.1-nano' },
    { label: 'GPT-4o', id: 'gpt-4o' },
    { label: 'GPT-4o mini', id: 'gpt-4o-mini' },
    { label: 'o3', id: 'o3' },
    { label: 'o3-mini', id: 'o3-mini' },
    { label: 'o3-pro', id: 'o3-pro' },
    { label: 'o4-mini', id: 'o4-mini' },
    { label: 'o1', id: 'o1' },
    { label: 'o1-pro', id: 'o1-pro' },
    { label: 'o3 Deep Research', id: 'o3-deep-research' },
    { label: 'o4-mini Deep Research', id: 'o4-mini-deep-research' },
    { label: 'GPT-OSS 120B', id: 'gpt-oss-120b' },
  ],
};

const MODEL_LABELS = { gemini: 'Gemini', openai: 'GPT', claude: 'Claude' };

// ─── Reports component ────────────────────────────────────────────────────────

export default function Reports({ course, sessionToken, onAddSource }) {
  const [materials, setMaterials] = useState([]);
  const [selectedSources, setSelectedSources] = useState(new Set());
  const [selectAll, setSelectAll] = useState(true);
  const [materialsLoading, setMaterialsLoading] = useState(true);

  const [template, setTemplate] = useState('study-guide');
  const [customPrompt, setCustomPrompt] = useState('');
  const [selectedProvider, setSelectedProvider] = useState(
    () => localStorage.getItem('reports_selected_provider') || 'openai'
  );
  const [selectedModelId, setSelectedModelId] = useState(
    () => localStorage.getItem('reports_selected_model_id') || 'gpt-4o-mini'
  );

  const [reportData, setReportData] = useState(null);
  const [generationId, setGenerationId] = useState(null);
  const [generationStatus, setGenerationStatus] = useState(null);
  const [generationError, setGenerationError] = useState('');
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [estimateData, setEstimateData] = useState(null);
  const [isEstimating, setIsEstimating] = useState(false);
  const [isQueueing, setIsQueueing] = useState(false);
  const pollingTimeoutRef = useRef(null);
  const pollingAbortRef = useRef(null);
  const pollingSessionRef = useRef(0);
  const activePollGenerationRef = useRef(null);
  const generationStatusRef = useRef(null);
  const [availableProviders, setAvailableProviders] = useState([]);

  const authHeaders = { Authorization: `Bearer ${sessionToken}` };
  const activeTemplate = TEMPLATES.find((t) => t.id === template);
  const isCustom = activeTemplate?.customPrompt;
  const generationInProgress = generationStatus === 'queued' || generationStatus === 'generating';

  useEffect(() => {
    if (!course?.id || !sessionToken) return;
    setMaterialsLoading(true);
    fetch(`/api/material?course_id=${course.id}`, {
      headers: authHeaders,
    })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {})
      .finally(() => setMaterialsLoading(false));
  }, [course?.id, sessionToken]);

  useEffect(() => {
    generationStatusRef.current = generationStatus;
  }, [generationStatus]);

  useEffect(() => {
    stopPolling();
    setGenerationId(null);
    setGenerationStatus(null);
    if (!course?.id || !sessionToken) return;
    loadHistory();
    loadAvailableProviders();
    return () => stopPolling();
  }, [course?.id, sessionToken]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadAvailableProviders() {
    if (!sessionToken) return;
    try {
      const res = await fetch('/api/user?resource=api_keys', { headers: authHeaders });
      const data = await res.json();
      const providers = Object.entries(data || {})
        .filter(([, has]) => has)
        .map(([provider]) => provider);
      setAvailableProviders(providers);

      const savedProvider = localStorage.getItem('reports_selected_provider');
      const provider = providers.includes(savedProvider) ? savedProvider : (providers[0] || 'openai');
      const savedModelId = localStorage.getItem('reports_selected_model_id');
      const modelList = PROVIDER_MODELS[provider] || [];
      const modelId = modelList.find((model) => model.id === savedModelId)?.id || modelList[0]?.id || null;

      setSelectedProvider(provider);
      setSelectedModelId(modelId);
    } catch {
      // non-fatal
    }
  }

  async function loadHistory() {
    if (!course?.id || !sessionToken) return;
    try {
      const res = await fetch(`/api/reports?action=list_generations&course_id=${course.id}`, {
        headers: authHeaders,
      });
      const data = await res.json().catch(() => ({}));
      const generations = Array.isArray(data?.generations) ? data.generations : [];
      const locallyTrackedGenerationId = activePollGenerationRef.current;
      const normalizedGenerations = generations.map((generation) => {
        if (
          locallyTrackedGenerationId &&
          String(generation.generation_id) === String(locallyTrackedGenerationId) &&
          generation.status === 'draft'
        ) {
          return {
            ...generation,
            status: generationStatusRef.current === 'queued' ? 'queued' : 'generating',
          };
        }
        return generation;
      });

      const inflight = normalizedGenerations.find(
        (generation) => generation.status === 'queued' || generation.status === 'generating'
      );
      if (inflight) {
        setGenerationId(inflight.generation_id);
        setGenerationStatus(inflight.status);
        startPolling(inflight.generation_id);
      } else if (
        locallyTrackedGenerationId &&
        (generationStatusRef.current === 'queued' || generationStatusRef.current === 'generating')
      ) {
        startPolling(locallyTrackedGenerationId);
      }
    } catch {
      // non-fatal
    }
  }

  function stopPolling() {
    pollingSessionRef.current += 1;

    if (pollingTimeoutRef.current) {
      clearTimeout(pollingTimeoutRef.current);
      pollingTimeoutRef.current = null;
    }

    if (pollingAbortRef.current) {
      pollingAbortRef.current.abort();
      pollingAbortRef.current = null;
    }

    activePollGenerationRef.current = null;
  }

  function startPolling(genId) {
    if (!genId) return;
    if (activePollGenerationRef.current === genId && (pollingTimeoutRef.current || pollingAbortRef.current)) {
      return;
    }

    stopPolling();
    const pollingSessionId = pollingSessionRef.current;
    activePollGenerationRef.current = genId;
    setGenerationId(genId);
    setGenerationStatus((prev) => (
      prev === 'queued' || prev === 'generating' ? prev : 'queued'
    ));

    const scheduleNextPoll = () => {
      if (
        pollingSessionRef.current !== pollingSessionId ||
        activePollGenerationRef.current !== genId
      ) {
        return;
      }
      pollingTimeoutRef.current = setTimeout(runPoll, 3000);
    };

    const runPoll = async () => {
      try {
        const statusController = new AbortController();
        pollingAbortRef.current = statusController;
        const res = await fetch(
          `/api/reports?action=get_generation_status&generation_id=${genId}`,
          { headers: authHeaders, signal: statusController.signal },
        );
        if (pollingAbortRef.current === statusController) {
          pollingAbortRef.current = null;
        }
        const data = await res.json().catch(() => null);
        if (
          pollingSessionRef.current !== pollingSessionId ||
          activePollGenerationRef.current !== genId
        ) {
          return;
        }
        if (!res.ok || !data) {
          scheduleNextPoll();
          return;
        }

        const normalizedStatus = (
          data.status === 'draft' && activePollGenerationRef.current === genId
            ? (generationStatusRef.current === 'queued' ? 'queued' : 'generating')
            : data.status
        );
        setGenerationStatus(normalizedStatus);

        if (normalizedStatus === 'ready') {
          const viewController = new AbortController();
          pollingAbortRef.current = viewController;
          const viewRes = await fetch(
            `/api/reports?action=get_generation&generation_id=${genId}`,
            { headers: authHeaders, signal: viewController.signal },
          );
          if (pollingAbortRef.current === viewController) {
            pollingAbortRef.current = null;
          }
          const viewData = await viewRes.json().catch(() => null);
          if (!viewRes.ok || !viewData) {
            setGenerationError('Report finished but could not be loaded.');
            setGenerationStatus(null);
            setGenerationId(null);
            activePollGenerationRef.current = null;
            await loadHistory();
            return;
          }
          setReportData(viewData);
          setEstimateData(null);
          setGenerationStatus(null);
          setGenerationId(null);
          activePollGenerationRef.current = null;
          await loadHistory();
        } else if (normalizedStatus === 'failed') {
          setGenerationError(data.error || 'Generation failed.');
          setGenerationStatus(null);
          setGenerationId(null);
          activePollGenerationRef.current = null;
          await loadHistory();
        } else {
          scheduleNextPoll();
        }
      } catch (error) {
        if (error?.name === 'AbortError') return;
        scheduleNextPoll();
      }
    };

    runPoll();
  }

  function isSourceSelected(id) {
    return selectAll || selectedSources.has(id);
  }

  function toggleSource(id) {
    if (selectAll) {
      setSelectAll(false);
      setSelectedSources(new Set(materials.map((m) => m.id).filter((mid) => mid !== id)));
      return;
    }
    setSelectedSources((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selectAll) {
      setSelectAll(false);
      setSelectedSources(new Set());
    } else {
      setSelectAll(true);
      setSelectedSources(new Set());
    }
  }

  const selectedCount = selectAll ? materials.length : selectedSources.size;

  async function handleEstimate({ parent_generation_id: parentGenerationId } = {}) {
    if (isEstimating) return false;
    setGenerationError('');
    setIsEstimating(true);
    try {
      const materialIds = selectAll
        ? materials.map((m) => m.id)
        : Array.from(selectedSources);
      const providerToUse = selectedProvider || 'openai';
      const modelIdToUse = selectedModelId || PROVIDER_MODELS[providerToUse]?.[0]?.id || 'gpt-4o-mini';
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: {
          ...authHeaders,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'estimate',
          course_id: course?.id,
          template_id: template,
          custom_prompt: isCustom ? customPrompt.trim() : undefined,
          parent_generation_id: parentGenerationId,
          material_ids: materialIds,
          provider: providerToUse,
          model_id: modelIdToUse,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setEstimateData({
        ...data,
        provider: data.provider || providerToUse,
        model_id: data.model_id || modelIdToUse,
      });
      setShowConfirmModal(true);
      loadHistory();
      return true;
    } catch (error) {
      setGenerationError(error?.message || 'Estimate failed. Please try again.');
      return false;
    } finally {
      setIsEstimating(false);
    }
  }

  async function handleConfirmGenerate({ provider, model_id: modelId } = {}) {
    if (!estimateData?.generation_id || isQueueing) return;
    setGenerationError('');
    setIsQueueing(true);
    try {
      const providerToUse = provider || selectedProvider || 'openai';
      const modelIdToUse = modelId || selectedModelId || PROVIDER_MODELS[providerToUse]?.[0]?.id || 'gpt-4o-mini';
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: {
          ...authHeaders,
          'Content-Type': 'application/json',
        },
        keepalive: true,
        body: JSON.stringify({
          action: 'generate',
          generation_id: estimateData.generation_id,
          provider: providerToUse,
          model_id: modelIdToUse,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status !== 202 && !res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      setSelectedProvider(providerToUse);
      setSelectedModelId(modelIdToUse);
      localStorage.setItem('reports_selected_provider', providerToUse);
      localStorage.setItem('reports_selected_model_id', modelIdToUse);

      activePollGenerationRef.current = estimateData.generation_id;
      setGenerationId(estimateData.generation_id);
      setGenerationStatus(data.status || 'queued');
      setShowConfirmModal(false);
      startPolling(estimateData.generation_id);
      loadHistory();
    } catch (error) {
      setGenerationError(error?.message || 'Failed to queue generation.');
    } finally {
      setIsQueueing(false);
    }
  }

  function handleCancelConfirm() {
    setShowConfirmModal(false);
    setEstimateData(null);
  }

  function handleReportSaveComplete({ generation_id: savedGenerationId, artifact_material_id: artifactMaterialId } = {}) {
    if (!savedGenerationId || !artifactMaterialId) return;
    setReportData((prev) => {
      if (!prev || String(prev.generation_id) !== String(savedGenerationId)) return prev;
      return { ...prev, artifact_material_id: artifactMaterialId };
    });
    loadHistory();
  }

  if (reportData) {
    const reportTemplate = TEMPLATES.find((t) => t.id === reportData.template_id) || activeTemplate;
    return (
      <ReportsViewer
        report={reportData}
        course={course}
        sessionToken={sessionToken}
        sourceMaterials={materials}
        templateLabel={reportTemplate?.label || 'Report'}
        generationError={generationError}
        onClose={() => setReportData(null)}
        onSaveComplete={handleReportSaveComplete}
        onRegenerate={async (payload) => {
          const estimated = await handleEstimate(payload);
          if (estimated) {
            setReportData(null);
          }
        }}
      />
    );
  }

  return (
    <div className="flex gap-4 items-start">

      {/* ── Sources sidebar ── */}
      <div className="w-[220px] flex-shrink-0 bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col overflow-hidden" style={{ minHeight: '520px' }}>
        <div className="px-4 pt-4 pb-2">
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Sources</span>
            <span className="text-[10px] text-gray-400 tabular-nums">{selectedCount}/{materials.length}</span>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-[10px] text-gray-400 leading-snug">Select sources to include in generation</p>
            <SourceToggle checked={selectAll} onToggle={toggleSelectAll} />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
          {materialsLoading && (
            <p className="px-3 py-2 text-[10px] text-gray-400">Loading…</p>
          )}
          {!materialsLoading && materials.length === 0 && (
            <p className="px-3 py-2 text-[10px] text-gray-400 italic">No materials yet.</p>
          )}
          {materials.map((m) => {
            const on = isSourceSelected(m.id);
            return (
              <div
                key={m.id}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-50 transition-colors cursor-default border-l-2 ${
                  on ? 'border-indigo-400' : 'border-transparent'
                }`}
              >
                <FileTypeBadge name={m.name} />
                <span className="flex-1 truncate min-w-0 text-xs" title={m.name}>{m.name}</span>
                <SourceToggle checked={on} onToggle={() => toggleSource(m.id)} />
              </div>
            );
          })}
        </div>

        <div className="px-3 py-3 flex-shrink-0 border-t border-gray-100">
          <button
            type="button"
            onClick={onAddSource}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-dashed border-gray-300 text-xs text-gray-500 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
          >
            <PlusIcon />
            Add Source
          </button>
        </div>
      </div>

      {/* ── Report config form ── */}
      <div className="flex-1 min-w-0 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col gap-5">
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-1">Custom Report Generator</h2>
          <p className="text-sm text-gray-500">Choose a report template or write your own prompt to generate a document from your sources.</p>
        </div>

        {/* Template grid */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Template</label>
          <div className="grid grid-cols-2 gap-3">
            {TEMPLATES.map(({ id, label, description, Icon }) => {
              const active = template === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTemplate(id)}
                  className={`relative text-left p-4 rounded-xl border transition-colors ${
                    active
                      ? 'bg-indigo-50 border-indigo-300'
                      : 'bg-white border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {active && (
                    <span className="absolute top-3 right-3 w-3 h-3 rounded-full bg-indigo-600 flex-shrink-0" />
                  )}
                  <span className={`block mb-2 ${active ? 'text-indigo-600' : 'text-gray-400'}`}>
                    <Icon />
                  </span>
                  <p className={`text-sm font-semibold mb-0.5 ${active ? 'text-indigo-700' : 'text-gray-800'}`}>
                    {label}
                  </p>
                  <p className="text-xs text-gray-500 leading-snug">{description}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom prompt — only for "Create Your Own" */}
        {isCustom && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Custom Prompt</label>
            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              rows={4}
              placeholder="Describe what you'd like the report to cover. Be as specific as possible — e.g. 'Create a comparative analysis of SLAM algorithms covered in the lectures'"
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-colors resize-none"
            />
            <p className="text-[10px] text-gray-400 mt-1">{customPrompt.length} characters</p>
          </div>
        )}

        {/* Summary info */}
        <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-indigo-50 border border-indigo-100">
          <SparkleIcon />
          <div className="text-xs text-indigo-700">
            <span>Generating a </span>
            <span className="font-semibold">{activeTemplate?.label}</span>
            <p className="text-indigo-500 mt-0.5">AI will analyze your selected sources and produce a well-structured document.</p>
          </div>
        </div>

        {/* Error */}
        {generationError && (
          <p className="text-xs text-red-600">{generationError}</p>
        )}

        {(generationStatus === 'queued' || generationStatus === 'generating') && (
          <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-indigo-50 border border-indigo-100">
            <svg className="animate-spin h-4 w-4 text-indigo-500 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span className="text-xs text-indigo-700">
              {generationStatus === 'queued' ? 'Queued - waiting for worker...' : 'Generating report...'}
            </span>
          </div>
        )}

        {/* Generate button */}
        <button
          type="button"
          onClick={() => handleEstimate()}
          disabled={isEstimating || isQueueing || generationInProgress || selectedCount === 0 || (isCustom && !customPrompt.trim())}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
        >
          {isEstimating ? (
            <>
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Estimating...
            </>
          ) : generationInProgress ? (
            <>
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Report in progress...
            </>
          ) : (
            <>
              <SparkleIcon />
              Generate {activeTemplate?.label}
            </>
          )}
        </button>

        <p className="text-[10px] text-gray-400 flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
          AI responses are based on your selected course materials.{' '}
          <a href="#" className="text-indigo-500 hover:underline">Learn more</a>
        </p>
      </div>

      {showConfirmModal && estimateData && (
        <GenerationConfirmModal
          mode="reports"
          data={estimateData}
          onConfirm={handleConfirmGenerate}
          onCancel={handleCancelConfirm}
          isLoading={isQueueing}
          availableProviders={availableProviders}
          providerModels={PROVIDER_MODELS}
          modelLabels={MODEL_LABELS}
        />
      )}

    </div>
  );
}
