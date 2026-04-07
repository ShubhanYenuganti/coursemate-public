import { useState, useEffect, useRef, useCallback } from 'react';
import { formatDateTime } from './utils/dateUtils';
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

function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
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
    { label: 'Claude Sonnet 4.5', id: 'claude-sonnet-4-5-20250929' },
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

export default function Reports({ course, onAddSource }) {
  const [materials, setMaterials] = useState([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);

  const [template, setTemplate] = useState('study-guide');
  const [customPrompt, setCustomPrompt] = useState('');
  const [selectedProvider, setSelectedProvider] = useState(
    () => localStorage.getItem('reports_selected_provider') || 'openai'
  );
  const [selectedModelId, setSelectedModelId] = useState(
    () => localStorage.getItem('reports_selected_model_id') || 'gpt-4o-mini'
  );
  const [providerDropdownOpen, setProviderDropdownOpen] = useState(false);
  const providerDropdownRef = useRef(null);

  const [reportData, setReportData] = useState(null);
  const [parentGenerationId, setParentGenerationId] = useState(null);
  const [generateError, setGenerateError] = useState('');
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [estimateData, setEstimateData] = useState(null);
  const [isEstimating, setIsEstimating] = useState(false);
  const [isQueueing, setIsQueueing] = useState(false);
  const [availableProviders, setAvailableProviders] = useState([]);

  // ── multi-generation polling (mirrors Flashcards pattern) ──────────────────
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyGenerations, setHistoryGenerations] = useState([]);
  const [generatingIds, setGeneratingIds] = useState(new Set());
  const generatingIdsRef = useRef(new Set());
  const pollTimersRef = useRef({});

  const activeTemplate = TEMPLATES.find((t) => t.id === template);
  const isCustom = activeTemplate?.customPrompt;

  useEffect(() => {
    generatingIdsRef.current = generatingIds;
  }, [generatingIds]);

  useEffect(() => {
    if (!providerDropdownOpen) return;
    function onOutsideClick(e) {
      if (providerDropdownRef.current && !providerDropdownRef.current.contains(e.target)) {
        setProviderDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', onOutsideClick);
    return () => document.removeEventListener('mousedown', onOutsideClick);
  }, [providerDropdownOpen]);

  // ── materials ──────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!course?.id) return;
    setMaterialsLoading(true);
    fetch(`/api/material?action=selections&course_id=${course.id}&context=report`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {})
      .finally(() => setMaterialsLoading(false));
  }, [course?.id]);

  // ── available providers ────────────────────────────────────────────────────

  useEffect(() => {
    fetch('/api/user?resource=api_keys', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        const available = Object.entries(data || {})
          .filter(([, has]) => has)
          .map(([provider]) => provider);
        setAvailableProviders(available);

        const savedProvider = localStorage.getItem('reports_selected_provider');
        const provider = available.includes(savedProvider) ? savedProvider : (available[0] || 'openai');
        const savedModelId = localStorage.getItem('reports_selected_model_id');
        const modelList = PROVIDER_MODELS[provider] || [];
        const modelId = modelList.find((m) => m.id === savedModelId)?.id || modelList[0]?.id || null;

        setSelectedProvider(provider);
        setSelectedModelId(modelId);
      })
      .catch(() => {});
  }, []);

  // ── polling helpers ────────────────────────────────────────────────────────

  const stopPolling = useCallback((genId) => {
    if (pollTimersRef.current[genId]) {
      clearInterval(pollTimersRef.current[genId]);
      delete pollTimersRef.current[genId];
    }
    setGeneratingIds((prev) => {
      const n = new Set(prev);
      n.delete(genId);
      return n;
    });
  }, []);

  const loadHistory = useCallback(async () => {
    if (!course?.id) return;
    setHistoryLoading(true);
    try {
      const r = await fetch(
        `/api/reports?action=list_generations&course_id=${course.id}`,
        { credentials: 'include' },
      );
      const data = await r.json();
      const generations = Array.isArray(data?.generations) ? data.generations : [];

      // Prevent stale "draft" status for generations we're actively tracking
      const locallyGenerating = new Set([
        ...Array.from(generatingIdsRef.current, (id) => String(id)),
        ...Object.keys(pollTimersRef.current),
      ]);
      const normalized = generations.map((g) => (
        locallyGenerating.has(String(g.generation_id)) && g.status === 'draft'
          ? { ...g, status: 'generating' }
          : g
      ));
      setHistoryGenerations(normalized);

      // Auto-start polls for any in-flight generation not yet tracked
      normalized.forEach((g) => {
        if (g.status === 'queued' || g.status === 'generating') {
          if (!pollTimersRef.current[g.generation_id]) {
            setGeneratingIds((prev) => new Set([...prev, g.generation_id]));
            pollTimersRef.current[g.generation_id] = setInterval(async () => {
              try {
                const rr = await fetch(
                  `/api/reports?action=get_generation_status&generation_id=${g.generation_id}`,
                  { credentials: 'include' },
                );
                if (!rr.ok) return;
                const sd = await rr.json().catch(() => null);
                if (!sd) return;
                if (sd.status === 'ready') {
                  stopPolling(g.generation_id);
                  setHistoryGenerations((prev) =>
                    prev.map((x) => x.generation_id === g.generation_id ? { ...x, status: 'ready' } : x)
                  );
                  loadHistory();
                } else if (sd.status === 'failed') {
                  stopPolling(g.generation_id);
                  setHistoryGenerations((prev) =>
                    prev.map((x) => x.generation_id === g.generation_id ? { ...x, status: 'failed', error: sd.error } : x)
                  );
                  if (sd.error) setGenerateError(`Generation failed: ${sd.error}`);
                }
              } catch {
                // retry on next interval
              }
            }, 5000);
          }
        }
      });
    } catch {
      // non-fatal
    } finally {
      setHistoryLoading(false);
    }
  }, [course?.id, stopPolling]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Clear all poll timers when course changes
  useEffect(() => {
    return () => {
      Object.values(pollTimersRef.current).forEach(clearInterval);
      pollTimersRef.current = {};
    };
  }, [course?.id]);

  // ── source selection ───────────────────────────────────────────────────────

  async function persistMaterialSelection(material, selected) {
    if (!course?.id || !material?.id) return;
    try {
      await fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          action: 'set_selection',
          material_id: material.id,
          course_id: course.id,
          context: 'report',
          selected,
          provider: material.source_type === 'notion' ? 'notion' : null,
        }),
      });
    } catch {}
  }

  function toggleSource(id) {
    setMaterials((prev) => prev.map((m) => {
      if (m.id !== id) return m;
      const updated = { ...m, selected: !m.selected };
      persistMaterialSelection(m, updated.selected);
      return updated;
    }));
  }

  function toggleSelectAll() {
    const allOn = materials.length > 0 && materials.every((m) => m.selected);
    const newVal = !allOn;
    const nextMaterials = materials.map((m) => ({ ...m, selected: newVal }));
    setMaterials(nextMaterials);
    nextMaterials.forEach((m) => {
      persistMaterialSelection(m, newVal);
    });
  }

  const selectedCount = materials.filter((m) => m.selected).length;
  const allSelected = materials.length > 0 && selectedCount === materials.length;

  // ── estimate → confirm → generate ─────────────────────────────────────────

  async function handleEstimate() {
    if (isEstimating) return false;
    setGenerateError('');
    setIsEstimating(true);
    try {
      const materialIds = materials.filter((m) => m.selected).map((m) => m.id);
      const providerToUse = selectedProvider || 'openai';
      const modelIdToUse = selectedModelId || PROVIDER_MODELS[providerToUse]?.[0]?.id || 'gpt-4o-mini';
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
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
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setEstimateData({
        ...data,
        provider: data.provider || providerToUse,
        model_id: data.model_id || modelIdToUse,
      });
      setShowConfirmModal(true);
      loadHistory();
      return true;
    } catch (error) {
      setGenerateError(error?.message || 'Estimate failed. Please try again.');
      return false;
    } finally {
      setIsEstimating(false);
    }
  }

  async function handleConfirmGenerate({ provider, model_id: modelId } = {}) {
    if (!estimateData?.generation_id || isQueueing) return;
    setGenerateError('');
    setIsQueueing(true);
    try {
      const providerToUse = provider || selectedProvider || 'openai';
      const modelIdToUse = modelId || selectedModelId || PROVIDER_MODELS[providerToUse]?.[0]?.id || 'gpt-4o-mini';
      const res = await fetch('/api/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        keepalive: true,
        body: JSON.stringify({
          action: 'generate',
          generation_id: estimateData.generation_id,
          provider: providerToUse,
          model_id: modelIdToUse,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status !== 202 && !res.ok) throw new Error(data.error || `HTTP ${res.status}`);

      setSelectedProvider(providerToUse);
      setSelectedModelId(modelIdToUse);
      localStorage.setItem('reports_selected_provider', providerToUse);
      localStorage.setItem('reports_selected_model_id', modelIdToUse);

      const genId = estimateData.generation_id;
      const nextStatus = data.status || 'queued';

      // Update history row immediately (include provider/model in case user changed them in the modal)
      setHistoryGenerations((prev) =>
        prev.map((g) => g.generation_id === genId ? { ...g, status: nextStatus, provider: providerToUse, model_id: modelIdToUse } : g)
      );

      // Start per-generation poll
      if (nextStatus === 'queued' || nextStatus === 'generating') {
        if (!pollTimersRef.current[genId]) {
          setGeneratingIds((prev) => new Set([...prev, genId]));
          pollTimersRef.current[genId] = setInterval(async () => {
            try {
              const rr = await fetch(
                `/api/reports?action=get_generation_status&generation_id=${genId}`,
                { credentials: 'include' },
              );
              if (!rr.ok) return;
              const sd = await rr.json().catch(() => null);
              if (!sd) return;
              if (sd.status === 'ready') {
                stopPolling(genId);
                setHistoryGenerations((prev) =>
                  prev.map((x) => x.generation_id === genId ? { ...x, status: 'ready' } : x)
                );
                loadHistory();
              } else if (sd.status === 'failed') {
                stopPolling(genId);
                setHistoryGenerations((prev) =>
                  prev.map((x) => x.generation_id === genId ? { ...x, status: 'failed', error: sd.error } : x)
                );
                if (sd.error) setGenerateError(`Generation failed: ${sd.error}`);
              }
            } catch {
              // retry on next interval
            }
          }, 5000);
        }
      }

      setShowConfirmModal(false);
      setEstimateData(null);
    } catch (error) {
      setGenerateError(error?.message || 'Failed to queue generation.');
    } finally {
      setIsQueueing(false);
    }
  }

  function handleCancelConfirm() {
    const genId = estimateData?.generation_id;
    setShowConfirmModal(false);
    setEstimateData(null);
    if (!genId) return;
    // Remove the draft from history and delete it server-side
    setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== genId));
    fetch(`/api/reports?generation_id=${genId}`, {
      method: 'DELETE',
      credentials: 'include',
    }).catch(() => {});
  }

  // ── history actions ────────────────────────────────────────────────────────

  async function reopenFromHistory(gen) {
    if (!gen) return;
    const res = await fetch(
      `/api/reports?action=get_generation&generation_id=${gen.generation_id}`,
      { credentials: 'include' },
    );
    const data = await res.json().catch(() => null);
    if (data?.generation_id) {
      setReportData(data);
    }
  }

  async function deleteGeneration(genId) {
    stopPolling(genId);
    setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== genId));
    await fetch(`/api/reports?generation_id=${genId}`, {
      method: 'DELETE',
      credentials: 'include',
    }).catch(() => {});
  }

  function handleReportSaveComplete({ generation_id: savedGenerationId, artifact_material_id: artifactMaterialId } = {}) {
    if (!savedGenerationId || !artifactMaterialId) return;
    setReportData((prev) => {
      if (!prev || String(prev.generation_id) !== String(savedGenerationId)) return prev;
      return { ...prev, artifact_material_id: artifactMaterialId };
    });
    setHistoryGenerations((prev) =>
      prev.map((g) => String(g.generation_id) === String(savedGenerationId)
        ? { ...g, artifact_material_id: artifactMaterialId }
        : g
      )
    );
  }

  // ── viewer ─────────────────────────────────────────────────────────────────

  if (reportData) {
    const reportTemplate = TEMPLATES.find((t) => t.id === reportData.template_id) || activeTemplate;
    return (
      <ReportsViewer
        report={reportData}
        course={course}
        sourceMaterials={materials}
        templateLabel={reportTemplate?.label || 'Report'}
        generationError={generateError}
        onClose={() => { setReportData(null); setParentGenerationId(null); }}
        onSaveComplete={handleReportSaveComplete}
        onRegenerate={() => {
          // Restore template + sources from the current report so the form is pre-filled
          const savedMaterialIds = Array.isArray(reportData?.selected_material_ids)
            ? reportData.selected_material_ids.map((id) => Number(id)).filter((id) => Number.isFinite(id))
            : [];
          setTemplate(reportData?.template_id || template);
          if (reportData?.custom_prompt) setCustomPrompt(reportData.custom_prompt);
          setMaterials((prev) => {
            if (savedMaterialIds.length === 0) return prev.map((m) => ({ ...m, selected: true }));
            return prev.map((m) => ({ ...m, selected: savedMaterialIds.includes(m.id) }));
          });
          setParentGenerationId(reportData?.generation_id || null);
          setReportData(null);
        }}
        onResolve={(resolution, data) => {
          if (resolution === 'revert' && data?.generation) {
            const childId = reportData?.generation_id;
            setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== childId));
            setReportData(data.generation);
          } else {
            if (resolution === 'replace') {
              const parentId = reportData?.parent_generation_id;
              setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== parentId));
            }
            setReportData((prev) => prev ? { ...prev, parent_generation_id: null } : prev);
          }
        }}
      />
    );
  }

  // ── form view ──────────────────────────────────────────────────────────────

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
            <SourceToggle checked={allSelected} onToggle={toggleSelectAll} />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
          {materialsLoading && (
            <p className="px-3 py-2 text-[10px] text-gray-400">Loading…</p>
          )}
          {!materialsLoading && materials.length === 0 && (
            <p className="px-3 py-2 text-[10px] text-gray-400 italic">No materials yet.</p>
          )}
          {(() => {
            const myMats = materials.filter((m) => !m.collaborator);
            const collabMats = materials.filter((m) => m.collaborator);
            return (
              <>
                {myMats.map((m) => (
                  <div
                    key={m.id}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-50 transition-colors cursor-default border-l-2 ${
                      m.selected ? 'border-indigo-400' : 'border-transparent'
                    }`}
                  >
                    <FileTypeBadge name={m.name} />
                    <span className="flex-1 truncate min-w-0 text-xs" title={m.name}>{m.name}</span>
                    <SourceToggle checked={m.selected} onToggle={() => toggleSource(m.id)} />
                  </div>
                ))}
                {collabMats.length > 0 && (
                  <>
                    <div className="px-3 pt-2 pb-0.5">
                      <span className="text-[9px] font-semibold text-gray-300 uppercase tracking-wider">From collaborators</span>
                    </div>
                    {collabMats.map((m) => (
                      <div
                        key={m.id}
                        className={`relative group flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-500 hover:bg-gray-50 transition-colors cursor-default border-l-2 ${
                          m.selected ? 'border-indigo-300' : 'border-transparent'
                        }`}
                      >
                        <FileTypeBadge name={m.name} />
                        <span className="flex-1 truncate min-w-0 text-xs">{m.name}</span>
                        <SourceToggle checked={m.selected} onToggle={() => toggleSource(m.id)} />
                        <div className="pointer-events-none absolute left-2 bottom-full mb-1.5 z-10 hidden group-hover:block w-56 rounded-lg bg-gray-800 px-2.5 py-2 shadow-lg">
                          <p className="text-[10px] font-medium text-white whitespace-normal break-words">{m.collaborator?.name}</p>
                          <p className="text-[10px] text-gray-300 whitespace-normal break-words">{m.name}</p>
                          <p className="text-[10px] text-gray-400 whitespace-normal break-words">{m.collaborator?.email}</p>
                        </div>
                      </div>
                    ))}
                  </>
                )}
              </>
            );
          })()}
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

        {/* Custom prompt */}
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

        {availableProviders.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">AI Model</label>
            <div className="relative inline-block" ref={providerDropdownRef}>
              <button
                type="button"
                onClick={() => setProviderDropdownOpen((open) => !open)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-white text-xs text-gray-700 hover:border-indigo-400 transition-colors"
              >
                <span className="font-medium">{MODEL_LABELS[selectedProvider] || selectedProvider}</span>
                <span className="text-gray-400">·</span>
                <span>{(PROVIDER_MODELS[selectedProvider] || []).find((m) => m.id === selectedModelId)?.label || selectedModelId}</span>
                <ChevronDownIcon />
              </button>
              {providerDropdownOpen && (
                <div className="absolute z-20 mt-1 left-0 bg-white border border-gray-200 rounded-xl shadow-lg py-1 min-w-[220px] max-h-[280px] overflow-y-auto">
                  {availableProviders.map((provider) => (
                    <div key={provider}>
                      <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                        {MODEL_LABELS[provider] || provider}
                      </p>
                      {(PROVIDER_MODELS[provider] || []).map((model) => (
                        <button
                          key={model.id}
                          type="button"
                          onClick={() => {
                            setSelectedProvider(provider);
                            setSelectedModelId(model.id);
                            localStorage.setItem('reports_selected_provider', provider);
                            localStorage.setItem('reports_selected_model_id', model.id);
                            setProviderDropdownOpen(false);
                          }}
                          className={`w-full text-left px-4 py-1.5 text-xs hover:bg-indigo-50 transition-colors ${
                            model.id === selectedModelId ? 'text-indigo-600 font-medium' : 'text-gray-700'
                          }`}
                        >
                          {model.label}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* History */}
        <div className="bg-white rounded-xl border border-gray-200 p-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-xs font-semibold text-gray-900">Generated & Drafted Reports</p>
            {historyLoading ? (
              <p className="text-[10px] text-gray-400">Loading…</p>
            ) : (
              <p className="text-[10px] text-gray-400">{historyGenerations.length} saved</p>
            )}
          </div>

          {historyLoading ? (
            <p className="text-[10px] text-gray-400">Fetching your reports…</p>
          ) : historyGenerations.length === 0 ? (
            <p className="text-[10px] text-gray-400 italic">No report history yet.</p>
          ) : (
            <div className="space-y-2">
              {historyGenerations.map((g) => {
                const isPolling = generatingIds.has(g.generation_id);
                const status = isPolling && g.status === 'queued'
                  ? 'queued'
                  : (isPolling ? 'generating' : (g.status || 'ready'));
                const badgeClass =
                  status === 'ready'    ? 'border-green-200 bg-green-50 text-green-700'
                  : status === 'failed' ? 'border-red-200 bg-red-50 text-red-600'
                  : status === 'draft'  ? 'border-amber-200 bg-amber-50 text-amber-800'
                  : status === 'queued' ? 'border-purple-200 bg-purple-50 text-purple-700'
                  :                       'border-indigo-200 bg-indigo-50 text-indigo-700';

                const templateLabel = TEMPLATES.find((t) => t.id === g.template_id)?.label
                  || (g.template_id ? g.template_id : 'Report');
                const rowTitle = g.title
                  ? g.title
                  : g.template_id === 'custom' && g.custom_prompt
                    ? g.custom_prompt.slice(0, 60) + (g.custom_prompt.length > 60 ? '…' : '')
                    : templateLabel;

                const tokenLow = g.estimated_total_tokens_low;
                const tokenHigh = g.estimated_total_tokens_high;
                const tokenText =
                  typeof tokenLow === 'number' && typeof tokenHigh === 'number'
                    ? `${tokenLow}–${tokenHigh}`
                    : 'N/A';

                const createdAt = formatDateTime(g.created_at);

                return (
                  <div key={g.generation_id} className="rounded-lg border border-gray-200 p-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-gray-900 truncate">{rowTitle}</p>
                        <p className="text-[10px] text-gray-500 mt-0.5 truncate">
                          {g.provider || 'provider'} · {g.model_id || 'model'} · {createdAt}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full border text-[10px] font-medium ${badgeClass}`}>
                          {(status === 'generating' || status === 'queued') && (
                            <svg className="animate-spin h-2.5 w-2.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                            </svg>
                          )}
                          {status}
                        </span>
                        <button
                          type="button"
                          onClick={() => deleteGeneration(g.generation_id)}
                          className="p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                          aria-label="Delete"
                        >
                          <TrashIcon />
                        </button>
                      </div>
                    </div>

                    <div className="mt-2 flex items-center justify-between gap-3">
                      <p className="text-[10px] text-gray-500">
                        Tokens: <span className="font-medium text-gray-700">{tokenText}</span>
                      </p>
                      <div className="flex items-center gap-2">
                        {status === 'generating' ? (
                          <p className="text-[10px] text-indigo-600 italic">Processing…</p>
                        ) : status === 'queued' ? (
                          <p className="text-[10px] text-purple-600 italic">Queued…</p>
                        ) : status === 'ready' ? (
                          <button
                            type="button"
                            onClick={() => reopenFromHistory(g)}
                            className="px-2 py-1 rounded-lg border border-gray-200 text-[10px] font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                          >
                            Open
                          </button>
                        ) : status === 'failed' ? (
                          <p className="text-[10px] text-red-500 italic truncate max-w-[120px]" title={g.error}>
                            {g.error ? g.error.slice(0, 40) : 'Failed'}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Error */}
        {generateError && (
          <p className="text-xs text-red-600">{generateError}</p>
        )}

        {/* Generate button — no longer blocked by in-progress generation */}
        <button
          type="button"
          onClick={() => handleEstimate()}
          disabled={isEstimating || isQueueing || selectedCount === 0 || (isCustom && !customPrompt.trim())}
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
