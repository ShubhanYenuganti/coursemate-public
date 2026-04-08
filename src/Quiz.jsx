import { useState, useEffect, useRef, useCallback } from 'react';
import { formatDateTime } from './utils/dateUtils';
import QuizViewer from './QuizViewer';
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

function MinusIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
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

function ChevronDownIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
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

function Stepper({ value, onChange, min = 0, max = 99 }) {
  return (
    <div className="flex items-center gap-3 border border-gray-200 rounded-lg px-3 py-2 bg-white">
      <button
        type="button"
        onClick={() => onChange(Math.max(min, value - 1))}
        className="text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-30"
        disabled={value <= min}
      >
        <MinusIcon />
      </button>
      <span className="text-sm font-semibold text-gray-900 w-5 text-center tabular-nums">{value}</span>
      <button
        type="button"
        onClick={() => onChange(Math.min(max, value + 1))}
        className="text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-30"
        disabled={value >= max}
      >
        <PlusIcon />
      </button>
    </div>
  );
}

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

// ─── Quiz component ───────────────────────────────────────────────────────────

export default function Quiz({ course, onAddSource }) {
  const [materials, setMaterials] = useState([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);

  // Quiz config
  const [topic, setTopic] = useState('');
  const [tfCount, setTfCount] = useState(5);
  const [saCount, setSaCount] = useState(3);
  const [laCount, setLaCount] = useState(2);
  const [mcqCount, setMcqCount] = useState(10);
  const [mcqOptions, setMcqOptions] = useState(4);
  const [availableProviders, setAvailableProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(
    () => localStorage.getItem('quiz_selected_provider') || 'openai'
  );
  const [selectedModelId, setSelectedModelId] = useState(
    () => localStorage.getItem('quiz_selected_model_id') || 'gpt-4o-mini'
  );
  const [providerDropdownOpen, setProviderDropdownOpen] = useState(false);
  const providerDropdownRef = useRef(null);

  const [estimating, setEstimating] = useState(false);
  const [generateError, setGenerateError] = useState('');
  const [quizData, setQuizData] = useState(null);
  const [generationId, setGenerationId] = useState(null);
  const [parentGenerationId, setParentGenerationId] = useState(null);
  const [pendingRegenerationParentId, setPendingRegenerationParentId] = useState(null);

  const [confirmModalData, setConfirmModalData] = useState(null);
  const [startingGeneration, setStartingGeneration] = useState(false);

  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyGenerations, setHistoryGenerations] = useState([]);

  // Polling — track which generation IDs are currently being polled.
  const [generatingIds, setGeneratingIds] = useState(new Set());
  const pollTimersRef = useRef({});

  useEffect(() => {
    if (!course?.id) return;
    setMaterialsLoading(true);
    fetch(`/api/material?action=selections&course_id=${course.id}&context=quiz`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {})
      .finally(() => setMaterialsLoading(false));
  }, [course?.id]);

  useEffect(() => {
    fetch('/api/user?resource=api_keys', {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => {
        const available = Object.entries(data || {})
          .filter(([, has]) => has)
          .map(([provider]) => provider);
        setAvailableProviders(available);

        const savedProvider = localStorage.getItem('quiz_selected_provider');
        const provider = available.includes(savedProvider) ? savedProvider : (available[0] || 'openai');
        const savedModelId = localStorage.getItem('quiz_selected_model_id');
        const modelList = PROVIDER_MODELS[provider] || [];
        const modelId = modelList.find((m) => m.id === savedModelId)?.id || modelList[0]?.id || null;

        setSelectedProvider(provider);
        setSelectedModelId(modelId);
      })
      .catch(() => {});
  }, []);

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

  // Load generation history for the current course.
  // Also resumes polling for any rows that are still mid-generation (e.g. after a page refresh).
  async function loadHistory() {
    if (!course?.id) return;
    setHistoryLoading(true);
    try {
      const r = await fetch(`/api/quiz?action=list_generations&course_id=${course.id}`, {
        credentials: 'include',
      });
      const data = await r.json();
      const generations = Array.isArray(data?.generations) ? data.generations : [];
      // Preserve local in-flight state if list_generations briefly returns stale "draft".
      const locallyGenerating = new Set([
        ...Array.from(generatingIds, (id) => String(id)),
        ...Object.keys(pollTimersRef.current),
      ]);
      const normalizedGenerations = generations.map((g) => (
        locallyGenerating.has(String(g.generation_id)) && g.status === 'draft'
          ? { ...g, status: 'generating' }
          : g
      ));
      setHistoryGenerations(normalizedGenerations);
      normalizedGenerations.forEach((g) => {
        if (g.status === 'queued' || g.status === 'generating') startPolling(g.generation_id);
      });
    } catch {}
    finally { setHistoryLoading(false); }
  }

  useEffect(() => { loadHistory(); }, [course?.id]);

  // Clear all polls when the course changes or component unmounts.
  useEffect(() => {
    return () => {
      Object.values(pollTimersRef.current).forEach(clearInterval);
      pollTimersRef.current = {};
    };
  }, [course?.id]);

  const stopPolling = useCallback((genId) => {
    if (pollTimersRef.current[genId]) {
      clearInterval(pollTimersRef.current[genId]);
      delete pollTimersRef.current[genId];
    }
    setGeneratingIds((prev) => { const n = new Set(prev); n.delete(genId); return n; });
  }, []);

  const startPolling = useCallback((genId) => {
    if (pollTimersRef.current[genId]) return; // already polling
    setGeneratingIds((prev) => new Set([...prev, genId]));

    pollTimersRef.current[genId] = setInterval(async () => {
      try {
        const r = await fetch(`/api/quiz?action=get_generation_status&generation_id=${genId}`, {
          credentials: 'include',
        });
        if (!r.ok) return;
        const data = await r.json().catch(() => null);
        if (!data) return;

        if (data.status === 'ready') {
          stopPolling(genId);
          setHistoryGenerations((prev) =>
            prev.map((g) => g.generation_id === genId ? { ...g, status: 'ready' } : g)
          );
          loadHistory();
        } else if (data.status === 'failed') {
          stopPolling(genId);
          setHistoryGenerations((prev) =>
            prev.map((g) => g.generation_id === genId ? { ...g, status: 'failed' } : g)
          );
          setGenerateError(data.error ? `Generation failed: ${data.error}` : 'Generation failed.');
          loadHistory();
        }
      } catch {
        // Network hiccup — keep polling.
      }
    }, 5000);
  }, [stopPolling]);

  // Fire generate (from draft or confirm) and begin polling after server ack.
  const triggerGeneration = useCallback(async (genId, parentId = null, provider = null, modelId = null) => {
    const body = { action: 'generate', generation_id: genId, parent_generation_id: parentId };
    if (provider) body.provider = provider;
    if (modelId) body.model_id = modelId;
    try {
      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
        // Helps the request continue during quick route changes / refresh.
        keepalive: true,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const detail = data?.detail ? ` (${data.detail})` : '';
        setGenerateError((data?.error || `Failed to start generation (HTTP ${res.status})`) + detail);
        loadHistory();
        return false;
      }
      const nextStatus = data?.status || 'queued';
      setHistoryGenerations((prev) =>
        prev.map((g) => g.generation_id === genId ? { ...g, status: nextStatus, ...(provider && { provider }), ...(modelId && { model_id: modelId }) } : g)
      );
      if (nextStatus === 'queued' || nextStatus === 'generating') {
        startPolling(genId);
      } else if (nextStatus === 'ready') {
        stopPolling(genId);
      }
      return true;
    } catch (err) {
      if (err?.name === 'AbortError') {
        setGenerateError('Request was interrupted. Please try again.');
      } else {
        setGenerateError(`Failed to start generation. ${err?.message || 'Please try again.'}`);
      }
      loadHistory();
      return false;
    }
  }, [startPolling, stopPolling]);

  async function reopenFromHistory(gen) {
    if (!gen) return;
    const res = await fetch(`/api/quiz?action=get_generation&generation_id=${gen.generation_id}`, {
      credentials: 'include',
    });
    const data = await res.json().catch(() => null);
    if (data?.generation_id) {
      setGenerationId(data.generation_id);
      setParentGenerationId(data.parent_generation_id || null);
      setQuizData(data);
    }
  }

  function toggleSource(id) {
    const mat = materials.find((m) => m.id === id);
    if (!mat) return;
    const newSelected = !mat.selected;
    setMaterials((prev) => prev.map((m) => m.id === id ? { ...m, selected: newSelected } : m));
    fetch('/api/material', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        action: 'set_selection',
        material_id: id,
        course_id: course.id,
        context: 'quiz',
        selected: newSelected,
        provider: mat.source_type === 'notion' ? 'notion' : null,
      }),
    }).catch(() => {});
  }

  function toggleSelectAll() {
    const allOn = materials.length > 0 && materials.every((m) => m.selected);
    const newVal = !allOn;
    setMaterials((prev) => prev.map((m) => ({ ...m, selected: newVal })));
    materials.forEach((m) => {
      fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          action: 'set_selection',
          material_id: m.id,
          course_id: course.id,
          context: 'quiz',
          selected: newVal,
          provider: m.source_type === 'notion' ? 'notion' : null,
        }),
      }).catch(() => {});
    });
  }

  const selectedCount = materials.filter((m) => m.selected).length;
  const allSelected = materials.length > 0 && materials.every((m) => m.selected);
  const totalQuestions = tfCount + saCount + laCount + mcqCount;

  function applyQuizPreset(preset, parentId = null) {
    if (!preset) return;

    setTopic(preset.topic || '');
    setTfCount(Number.isFinite(Number(preset.tf_count)) ? Number(preset.tf_count) : 0);
    setSaCount(Number.isFinite(Number(preset.sa_count)) ? Number(preset.sa_count) : 0);
    setLaCount(Number.isFinite(Number(preset.la_count)) ? Number(preset.la_count) : 0);
    setMcqCount(Number.isFinite(Number(preset.mcq_count)) ? Number(preset.mcq_count) : 0);

    const options = Number(preset.mcq_options);
    setMcqOptions(options === 5 ? 5 : 4);

    if (preset.provider) {
      setSelectedProvider(preset.provider);
      localStorage.setItem('quiz_selected_provider', preset.provider);
    }
    if (preset.model_id) {
      setSelectedModelId(preset.model_id);
      localStorage.setItem('quiz_selected_model_id', preset.model_id);
    }

    const selectedIds = Array.isArray(preset.selected_material_ids)
      ? preset.selected_material_ids.map((id) => Number(id)).filter((id) => Number.isFinite(id))
      : [];

    if (selectedIds.length === 0) {
      setMaterials((prev) => prev.map((m) => ({ ...m, selected: true })));
    } else {
      setMaterials((prev) => prev.map((m) => ({ ...m, selected: selectedIds.includes(Number(m.id)) })));
    }

    const normalizedParentId =
      (typeof parentId === 'number' && Number.isFinite(parentId))
        ? parentId
        : (typeof parentId === 'string' && /^\d+$/.test(parentId))
          ? Number(parentId)
          : null;
    setPendingRegenerationParentId(normalizedParentId);
  }

  async function handleGenerate(parentId = null, overrides = null) {
    if (estimating) return;
    setGenerateError('');
    setEstimating(true);
    try {
      const normalizedParentId = (
        (typeof parentId === 'number' && Number.isFinite(parentId))
          ? parentId
          : (typeof parentId === 'string' && /^\d+$/.test(parentId))
            ? Number(parentId)
            : null
      );

      const contextIds = Array.isArray(overrides?.material_ids)
        ? overrides.material_ids
        : materials.filter((m) => m.selected).map((m) => m.id);

      const topicToUse = overrides?.topic ?? topic;
      const tfCountToUse = overrides?.tf_count ?? tfCount;
      const saCountToUse = overrides?.sa_count ?? saCount;
      const laCountToUse = overrides?.la_count ?? laCount;
      const mcqCountToUse = overrides?.mcq_count ?? mcqCount;
      const mcqOptionsToUse = overrides?.mcq_options ?? mcqOptions;
      const providerToUse = overrides?.provider ?? selectedProvider;
      const modelIdToUse = overrides?.model_id ?? selectedModelId;

      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          action: 'estimate',
          course_id: course?.id,
          topic: topicToUse,
          tf_count: tfCountToUse,
          sa_count: saCountToUse,
          la_count: laCountToUse,
          mcq_count: mcqCountToUse,
          mcq_options: mcqOptionsToUse,
          material_ids: contextIds,
          provider: providerToUse,
          model_id: modelIdToUse,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setGenerateError(err.error || 'Estimate failed. Please try again.');
      } else {
        const data = await res.json().catch(() => null);
        if (data && data.generation_id) {
          setConfirmModalData({
            ...data,
            provider: providerToUse,
            model_id: modelIdToUse,
            topic: topicToUse,
            tf_count: tfCountToUse,
            sa_count: saCountToUse,
            la_count: laCountToUse,
            mcq_count: mcqCountToUse,
            mcq_options: mcqOptionsToUse,
            parent_generation_id: normalizedParentId,
          });
          // Refresh history so the draft row is already in the list before the user confirms.
          loadHistory();
        } else {
          setGenerateError('Estimate returned no generation_id.');
        }
      }
    } catch (err) {
      if (err?.name === 'AbortError') {
        setGenerateError('Estimate request was interrupted. Please try again.');
      } else {
        setGenerateError(`Estimate request failed. ${err?.message || 'Please try again.'}`);
      }
    } finally {
      setEstimating(false);
    }
  }

  async function confirmGenerate({ provider, model_id: modelId } = {}) {
    if (!confirmModalData || startingGeneration) return;
    const { generation_id: genId, parent_generation_id: parentId } = confirmModalData;
    setGenerateError('');
    setStartingGeneration(true);
    const started = await triggerGeneration(genId, parentId, provider || null, modelId || null);
    if (started) {
      setConfirmModalData(null);
      setPendingRegenerationParentId(null);
    }
    setStartingGeneration(false);
  }

  function saveDraft() {
    // The estimate step already persisted the draft row — just close modal + refresh.
    setConfirmModalData(null);
    loadHistory();
  }

  function cancelConfirm() {
    const genId = confirmModalData?.generation_id;
    setConfirmModalData(null);
    if (!genId) return;
    // Optimistically remove the draft row created by the estimate step.
    setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== genId));
    fetch(`/api/quiz?generation_id=${genId}`, {
      method: 'DELETE',
      credentials: 'include',
    }).catch(() => {});
  }

  async function deleteGeneration(genId) {
    stopPolling(genId);
    setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== genId));
    await fetch(`/api/quiz?generation_id=${genId}`, {
      method: 'DELETE',
      credentials: 'include',
    }).catch(() => {});
  }

  if (quizData) {
    return (
      <>
        <QuizViewer
          quiz={quizData}
          courseId={course?.id}
          generationId={generationId}
          parentGenerationId={parentGenerationId}
          onClose={() => {
            setQuizData(null);
            setGenerationId(null);
            setParentGenerationId(null);
          }}
          onRegenerate={(regeneratePayload) => {
            const current = regeneratePayload || quizData || {};
            applyQuizPreset(current, generationId);
            setQuizData(null);
          }}
          onResolve={(resolution, revertPayload) => {
            if (resolution === 'revert' && revertPayload) {
              setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== generationId));
              setQuizData(revertPayload);
              setGenerationId(revertPayload.generation_id || null);
              setParentGenerationId(revertPayload.parent_generation_id || null);
            } else {
              if (resolution === 'replace') {
                setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== parentGenerationId));
              }
              setParentGenerationId(null);
            }
          }}
        />
        {confirmModalData && (
          <GenerationConfirmModal
            data={confirmModalData}
            onConfirm={confirmGenerate}
            onCancel={cancelConfirm}
            onSaveDraft={saveDraft}
            isLoading={startingGeneration}
            availableProviders={availableProviders}
            providerModels={PROVIDER_MODELS}
            modelLabels={MODEL_LABELS}
          />
        )}
      </>
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
                        {/* Collaborator tooltip */}
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

      {/* ── Quiz config form ── */}
      <div className="flex-1 min-w-0 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col gap-5">
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-1">Custom Quiz Generator</h2>
          <p className="text-sm text-gray-500">Configure your quiz parameters and generate questions from your selected sources.</p>
        </div>

        {/* Primary topic */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Primary Topic</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Reinforcement Learning, Neural Networks..."
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-colors"
          />
        </div>

        {/* Question type counts */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">True / False Questions</label>
            <Stepper value={tfCount} onChange={setTfCount} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Short Answer Questions</label>
            <Stepper value={saCount} onChange={setSaCount} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Long Answer Questions</label>
            <Stepper value={laCount} onChange={setLaCount} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">Multiple Choice (MCQ)</label>
            <Stepper value={mcqCount} onChange={setMcqCount} />
          </div>
        </div>

        {/* MCQ option count */}
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-2">MCQ Option Count</label>
          <div className="flex gap-2 p-1 bg-gray-100 rounded-lg w-fit">
            {[4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setMcqOptions(n)}
                className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  mcqOptions === n
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                {n} Options
              </button>
            ))}
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
                            localStorage.setItem('quiz_selected_provider', provider);
                            localStorage.setItem('quiz_selected_model_id', model.id);
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

        {/* Summary */}
        {totalQuestions > 0 && (
          <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-indigo-50 border border-indigo-100">
            <SparkleIcon />
            <span className="text-xs text-indigo-700">
              <span className="font-semibold">{totalQuestions} questions</span> will be generated
              {' '}({tfCount} T/F · {saCount} SA · {laCount} LA · {mcqCount} MCQ)
            </span>
          </div>
        )}

        {/* History */}
        <div className="mt-3 bg-white rounded-xl border border-gray-200 p-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-xs font-semibold text-gray-900">Generated & Drafted Quizzes</p>
            {historyLoading ? (
              <p className="text-[10px] text-gray-400">Loading…</p>
            ) : (
              <p className="text-[10px] text-gray-400">{historyGenerations.length} saved</p>
            )}
          </div>

          {historyLoading ? (
            <p className="text-[10px] text-gray-400">Fetching your generations…</p>
          ) : historyGenerations.length === 0 ? (
            <p className="text-[10px] text-gray-400 italic">No quiz history yet.</p>
          ) : (
            <div className="space-y-2">
              {historyGenerations.map((g) => {
                const isPolling = generatingIds.has(g.generation_id);
                const status = isPolling && g.status === 'queued' ? 'queued' : (isPolling ? 'generating' : (g.status || 'ready'));
                const badgeClass =
                  status === 'ready'
                    ? 'border-green-200 bg-green-50 text-green-700'
                    : status === 'failed'
                      ? 'border-red-200 bg-red-50 text-red-600'
                      : status === 'draft'
                        ? 'border-amber-200 bg-amber-50 text-amber-800'
                        : status === 'queued'
                          ? 'border-purple-200 bg-purple-50 text-purple-700'
                        : 'border-indigo-200 bg-indigo-50 text-indigo-700';

                const tokenLow = g.estimated_total_tokens_low;
                const tokenHigh = g.estimated_total_tokens_high;
                const tokenText =
                  typeof tokenLow === 'number' && typeof tokenHigh === 'number'
                    ? `${tokenLow}-${tokenHigh}`
                    : 'N/A';

                const createdAt = formatDateTime(g.created_at);

                return (
                  <div key={g.generation_id} className="rounded-lg border border-gray-200 p-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-gray-900 truncate">
                          {g.title || g.topic || 'Quiz'}
                        </p>
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
                        ) : status === 'draft' ? (
                          <button
                            type="button"
                            onClick={() => triggerGeneration(g.generation_id)}
                            disabled={estimating}
                            className="px-2 py-1 rounded-lg bg-indigo-600 text-white text-[10px] font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            Generate
                          </button>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => reopenFromHistory(g)}
                              className="px-2 py-1 rounded-lg border border-gray-200 text-[10px] font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                            >
                              Open
                            </button>
                            {status === 'ready' && (
                              <button
                                type="button"
                                onClick={() => applyQuizPreset(g, g.generation_id)}
                                disabled={estimating}
                                className="px-2 py-1 rounded-lg bg-indigo-600 text-white text-[10px] font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                              >
                                Regenerate
                              </button>
                            )}
                          </>
                        )}
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

        {/* Generate button */}
        <button
          type="button"
          onClick={() => handleGenerate(pendingRegenerationParentId)}
          disabled={estimating || totalQuestions === 0 || selectedCount === 0}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
        >
          {estimating ? (
            <>
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Estimating…
            </>
          ) : (
            <>
              <SparkleIcon />
              Generate Quiz
            </>
          )}
        </button>

        <p className="text-[10px] text-gray-400 flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
          AI responses are based on your selected course materials.{' '}
          <a href="#" className="text-indigo-500 hover:underline">Learn more</a>
        </p>

        {confirmModalData && (
          <GenerationConfirmModal
            data={confirmModalData}
            onConfirm={confirmGenerate}
            onCancel={cancelConfirm}
            onSaveDraft={saveDraft}
            isLoading={startingGeneration}
            availableProviders={availableProviders}
            providerModels={PROVIDER_MODELS}
            modelLabels={MODEL_LABELS}
          />
        )}
      </div>

    </div>
  );
}
