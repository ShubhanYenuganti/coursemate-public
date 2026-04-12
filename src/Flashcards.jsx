import { useState, useEffect, useRef, useCallback } from 'react';
import { formatDateTime } from './utils/dateUtils';
import { getMaterialUrl } from './utils/materialUtils';
import FlashcardViewer from './FlashcardViewer';
import GenerationConfirmModal from './components/GenerationConfirmModal.jsx';

function ExternalLinkIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

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

const FILE_TYPE_MAP = {
  pdf: { label: 'PDF', bg: 'bg-rose-100', text: 'text-rose-600' },
  doc: { label: 'DOC', bg: 'bg-blue-100', text: 'text-blue-600' },
  docx: { label: 'DOC', bg: 'bg-blue-100', text: 'text-blue-600' },
  xls: { label: 'XLS', bg: 'bg-green-100', text: 'text-green-700' },
  xlsx: { label: 'XLS', bg: 'bg-green-100', text: 'text-green-700' },
  csv: { label: 'CSV', bg: 'bg-green-100', text: 'text-green-700' },
  png: { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  jpg: { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  jpeg: { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  gif: { label: 'IMG', bg: 'bg-purple-100', text: 'text-purple-600' },
  svg: { label: 'SVG', bg: 'bg-orange-100', text: 'text-orange-600' },
  txt: { label: 'TXT', bg: 'bg-gray-100', text: 'text-gray-500' },
};

function NotionBadgeIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" className="shrink-0">
      <path d="M4 4a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v16a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V4z" opacity=".15"/>
      <rect x="7" y="7" width="10" height="1.5" rx=".75"/>
      <rect x="7" y="11" width="7" height="1.5" rx=".75"/>
      <rect x="7" y="15" width="8" height="1.5" rx=".75"/>
    </svg>
  );
}

function FileTypeBadge({ name, sourceType }) {
  const ext = (name || '').split('.').pop().toLowerCase();
  const mapped = FILE_TYPE_MAP[ext];

  if (!mapped && sourceType === 'notion') {
    return (
      <span className="flex-shrink-0 inline-flex items-center justify-center w-[22px] h-[16px] rounded bg-gray-100 text-gray-600">
        <NotionBadgeIcon />
      </span>
    );
  }

  const style = mapped || { label: ext.slice(0, 3).toUpperCase() || 'DOC', bg: 'bg-gray-100', text: 'text-gray-500' };
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

const DEPTH_OPTIONS = [
  {
    id: 'brief',
    label: 'Brief',
    description: 'Concise definitions with essential information',
    backPreview: 'A concise definition will appear here.',
  },
  {
    id: 'moderate',
    label: 'Moderate',
    description: 'Balanced explanations with key context',
    backPreview: 'A balanced explanation with key context will appear here.',
  },
  {
    id: 'in-depth',
    label: 'In-Depth',
    description: 'Comprehensive explanations with examples and detail',
    backPreview: 'A comprehensive explanation with examples will appear here.',
  },
];

const PROVIDER_MODELS = {
  claude: [
    { label: 'Claude Opus 4.6',   id: 'claude-opus-4-6' },
    { label: 'Claude Sonnet 4.6', id: 'claude-sonnet-4-6' },
    { label: 'Claude Haiku 4.5',  id: 'claude-haiku-4-5-20251001' },
    { label: 'Claude Sonnet 4.5', id: 'claude-sonnet-4-5-20250929' },
    { label: 'Claude Sonnet 4',   id: 'claude-sonnet-4-20250514' },
    { label: 'Claude Opus 4',     id: 'claude-opus-4-20250514' },
  ],
  gemini: [
    { label: 'Gemini 3.1 Pro',        id: 'gemini-3.1-pro-preview' },
    { label: 'Gemini 3 Flash',        id: 'gemini-3-flash-preview' },
    { label: 'Gemini 2.5 Pro',        id: 'gemini-2.5-pro' },
    { label: 'Gemini 2.5 Flash',      id: 'gemini-2.5-flash' },
    { label: 'Gemini 2.5 Flash-Lite', id: 'gemini-2.5-flash-lite' },
    { label: 'Deep Research',         id: 'deep-research-pro-preview-12-2025' },
    { label: 'Gemini 2.0 Flash',      id: 'gemini-2.0-flash' },
    { label: 'Gemini 2.0 Flash-Lite', id: 'gemini-2.0-flash-lite' },
  ],
  openai: [
    { label: 'GPT-5.2',               id: 'gpt-5.2' },
    { label: 'GPT-5.1',               id: 'gpt-5.1' },
    { label: 'GPT-5 Mini',            id: 'gpt-5-mini' },
    { label: 'GPT-5 Nano',            id: 'gpt-5-nano' },
    { label: 'GPT-4.1',               id: 'gpt-4.1' },
    { label: 'GPT-4.1 mini',          id: 'gpt-4.1-mini' },
    { label: 'GPT-4.1 nano',          id: 'gpt-4.1-nano' },
    { label: 'GPT-4o',                id: 'gpt-4o' },
    { label: 'GPT-4o mini',           id: 'gpt-4o-mini' },
    { label: 'o3',                    id: 'o3' },
    { label: 'o3-mini',               id: 'o3-mini' },
    { label: 'o3-pro',                id: 'o3-pro' },
    { label: 'o4-mini',               id: 'o4-mini' },
    { label: 'o1',                    id: 'o1' },
    { label: 'o1-pro',                id: 'o1-pro' },
    { label: 'o3 Deep Research',      id: 'o3-deep-research' },
    { label: 'o4-mini Deep Research', id: 'o4-mini-deep-research' },
    { label: 'GPT-OSS 120B',          id: 'gpt-oss-120b' },
  ],
};

const MODEL_LABELS = { gemini: 'Gemini', openai: 'GPT', claude: 'Claude' };

export default function Flashcards({ course, onAddSource }) {
  const [materials, setMaterials] = useState([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);

  const [topic, setTopic] = useState('');
  const [cardCount, setCardCount] = useState(20);
  const [depth, setDepth] = useState('moderate');

  const [availableProviders, setAvailableProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState(
    () => localStorage.getItem('flashcards_selected_provider') || 'openai'
  );
  const [selectedModelId, setSelectedModelId] = useState(
    () => localStorage.getItem('flashcards_selected_model_id') || 'gpt-4o-mini'
  );
  const [providerDropdownOpen, setProviderDropdownOpen] = useState(false);
  const providerDropdownRef = useRef(null);

  const [estimating, setEstimating] = useState(false);
  const [startingGeneration, setStartingGeneration] = useState(false);
  const [generateError, setGenerateError] = useState('');

  const [confirmModalData, setConfirmModalData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyGenerations, setHistoryGenerations] = useState([]);
  const [generatingIds, setGeneratingIds] = useState(new Set());
  const pollTimersRef = useRef({});
  const generatingIdsRef = useRef(new Set());

  const [flashcardData, setFlashcardData] = useState(null);
  const [generationId, setGenerationId] = useState(null);
  const [parentGenerationId, setParentGenerationId] = useState(null);
  const [pendingRegenerationParentId, setPendingRegenerationParentId] = useState(null);

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

  useEffect(() => {
    if (!course?.id) return;
    setMaterialsLoading(true);
    fetch(`/api/material?action=selections&course_id=${course.id}&context=flashcards`, {
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

        const savedProvider = localStorage.getItem('flashcards_selected_provider');
        const provider = available.includes(savedProvider) ? savedProvider : (available[0] || 'openai');
        const savedModelId = localStorage.getItem('flashcards_selected_model_id');
        const modelList = PROVIDER_MODELS[provider] || [];
        const modelId = modelList.find((m) => m.id === savedModelId)?.id || modelList[0]?.id || null;

        setSelectedProvider(provider);
        setSelectedModelId(modelId);
      })
      .catch(() => {});
  }, []);

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
      const r = await fetch(`/api/flashcards?action=list_generations&course_id=${course.id}`, {
        credentials: 'include',
      });
      const data = await r.json();
      const generations = Array.isArray(data?.generations) ? data.generations : [];
      const locallyGenerating = new Set([
        ...Array.from(generatingIdsRef.current, (id) => String(id)),
        ...Object.keys(pollTimersRef.current),
      ]);
      const normalizedGenerations = generations.map((g) => (
        locallyGenerating.has(String(g.generation_id)) && g.status === 'draft'
          ? { ...g, status: 'generating' }
          : g
      ));
      setHistoryGenerations(normalizedGenerations);
      normalizedGenerations.forEach((g) => {
        if (g.status === 'queued' || g.status === 'generating') {
          if (!pollTimersRef.current[g.generation_id]) {
            setGeneratingIds((prev) => new Set([...prev, g.generation_id]));
            pollTimersRef.current[g.generation_id] = setInterval(async () => {
              try {
                const rr = await fetch(`/api/flashcards?action=get_generation_status&generation_id=${g.generation_id}`, {
                  credentials: 'include',
                });
                if (!rr.ok) return;
                const sd = await rr.json().catch(() => null);
                if (!sd) return;
                if (sd.status === 'ready') {
                  stopPolling(g.generation_id);
                  setHistoryGenerations((prev) => prev.map((x) => x.generation_id === g.generation_id ? { ...x, status: 'ready' } : x));
                  loadHistory();
                } else if (sd.status === 'failed') {
                  stopPolling(g.generation_id);
                  setHistoryGenerations((prev) => prev.map((x) => x.generation_id === g.generation_id ? { ...x, status: 'failed' } : x));
                  if (sd.error) setGenerateError(`Generation failed: ${sd.error}`);
                }
              } catch {
                // retry on next interval
              }
            }, 5000);
          }
        }
      });
    } catch {}
    finally {
      setHistoryLoading(false);
    }
  }, [course?.id, stopPolling]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    return () => {
      Object.values(pollTimersRef.current).forEach(clearInterval);
      pollTimersRef.current = {};
    };
  }, [course?.id]);

  async function triggerGeneration(genId, parentId = null, provider = null, modelId = null) {
    const body = { action: 'generate', generation_id: genId, parent_generation_id: parentId };
    if (provider) body.provider = provider;
    if (modelId) body.model_id = modelId;

    try {
      const res = await fetch('/api/flashcards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
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
      setHistoryGenerations((prev) => prev.map((g) => g.generation_id === genId ? { ...g, status: nextStatus, ...(provider && { provider }), ...(modelId && { model_id: modelId }) } : g));
      if (nextStatus === 'queued' || nextStatus === 'generating') {
        if (!pollTimersRef.current[genId]) {
          setGeneratingIds((prev) => new Set([...prev, genId]));
          pollTimersRef.current[genId] = setInterval(async () => {
            try {
              const rr = await fetch(`/api/flashcards?action=get_generation_status&generation_id=${genId}`, {
                credentials: 'include',
              });
              if (!rr.ok) return;
              const sd = await rr.json().catch(() => null);
              if (!sd) return;
              if (sd.status === 'ready') {
                stopPolling(genId);
                setHistoryGenerations((prev) => prev.map((x) => x.generation_id === genId ? { ...x, status: 'ready' } : x));
                loadHistory();
              } else if (sd.status === 'failed') {
                stopPolling(genId);
                setHistoryGenerations((prev) => prev.map((x) => x.generation_id === genId ? { ...x, status: 'failed' } : x));
                if (sd.error) setGenerateError(`Generation failed: ${sd.error}`);
              }
            } catch {
              // retry on next interval
            }
          }, 5000);
        }
      } else if (nextStatus === 'ready') {
        stopPolling(genId);
      }
      return true;
    } catch (err) {
      setGenerateError(`Failed to start generation. ${err?.message || 'Please try again.'}`);
      loadHistory();
      return false;
    }
  }

  async function handleGenerate(parentId = null, overrides = null) {
    if (estimating) return;
    setGenerateError('');
    setEstimating(true);
    try {
      const normalizedParentId =
        (typeof parentId === 'number' && Number.isFinite(parentId))
          ? parentId
          : (typeof parentId === 'string' && /^\d+$/.test(parentId))
            ? Number(parentId)
            : null;

      const contextIds = Array.isArray(overrides?.material_ids)
        ? overrides.material_ids
        : materials.filter((m) => m.selected).map((m) => m.id);

      const topicToUse = overrides?.topic ?? topic;
      const cardCountToUse = overrides?.card_count ?? cardCount;
      const depthToUse = overrides?.depth ?? depth;
      const providerToUse = overrides?.provider ?? selectedProvider;
      const modelIdToUse = overrides?.model_id ?? selectedModelId;

      const res = await fetch('/api/flashcards', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          action: 'estimate',
          course_id: course?.id,
          topic: topicToUse,
          card_count: cardCountToUse,
          depth: depthToUse,
          material_ids: contextIds,
          provider: providerToUse,
          model_id: modelIdToUse,
          parent_generation_id: normalizedParentId,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setGenerateError(err.error || 'Estimate failed. Please try again.');
      } else {
        const data = await res.json().catch(() => null);
        if (data?.generation_id) {
          setConfirmModalData({
            ...data,
            topic: topicToUse,
            card_count: cardCountToUse,
            depth: depthToUse,
            provider: providerToUse,
            model_id: modelIdToUse,
            parent_generation_id: normalizedParentId,
          });
          loadHistory();
        } else {
          setGenerateError('Estimate returned no generation_id.');
        }
      }
    } catch (err) {
      setGenerateError(`Estimate request failed. ${err?.message || 'Please try again.'}`);
    } finally {
      setEstimating(false);
    }
  }

  async function confirmGenerate({ provider, model_id: modelId } = {}) {
    if (!confirmModalData || startingGeneration) return;
    setGenerateError('');
    setStartingGeneration(true);
    const started = await triggerGeneration(
      confirmModalData.generation_id,
      confirmModalData.parent_generation_id,
      provider || null,
      modelId || null,
    );
    if (started) {
      setConfirmModalData(null);
      setPendingRegenerationParentId(null);
    }
    setStartingGeneration(false);
  }

  function saveDraft() {
    setConfirmModalData(null);
    loadHistory();
  }

  function cancelConfirm() {
    const genId = confirmModalData?.generation_id;
    setConfirmModalData(null);
    if (!genId) return;
    setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== genId));
    fetch(`/api/flashcards?generation_id=${genId}`, {
      method: 'DELETE',
      credentials: 'include',
    }).catch(() => {});
  }

  async function deleteGeneration(genId) {
    stopPolling(genId);
    setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== genId));
    await fetch(`/api/flashcards?generation_id=${genId}`, {
      method: 'DELETE',
      credentials: 'include',
    }).catch(() => {});
  }

  async function reopenFromHistory(gen) {
    if (!gen) return;
    const res = await fetch(`/api/flashcards?action=get_generation&generation_id=${gen.generation_id}`, {
      credentials: 'include',
    });
    const data = await res.json().catch(() => null);
    if (data?.generation_id) {
      setGenerationId(data.generation_id);
      setParentGenerationId(data.parent_generation_id || null);
      setFlashcardData(data);
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
        context: 'flashcards',
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
          context: 'flashcards',
          selected: newVal,
          provider: m.source_type === 'notion' ? 'notion' : null,
        }),
      }).catch(() => {});
    });
  }

  function setAllMaterialsSelected(selected) {
    setMaterials((prev) => prev.map((m) => ({ ...m, selected })));
    materials.forEach((m) => {
      fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          action: 'set_selection',
          material_id: m.id,
          course_id: course.id,
          context: 'flashcards',
          selected,
          provider: m.source_type === 'notion' ? 'notion' : null,
        }),
      }).catch(() => {});
    });
  }

  const selectedCount = materials.filter((m) => m.selected).length;
  const allSelected = materials.length > 0 && materials.every((m) => m.selected);
  const activeDepth = DEPTH_OPTIONS.find((d) => d.id === depth);

  function applyFlashcardsPreset(preset, parentId = null) {
    if (!preset) return;

    setTopic(preset.topic || '');
    const normalizedCardCount = Number(preset.card_count);
    setCardCount(
      Number.isFinite(normalizedCardCount)
        ? Math.max(1, Math.min(100, normalizedCardCount))
        : 20
    );
    if (preset.depth) setDepth(preset.depth);

    if (preset.provider) {
      setSelectedProvider(preset.provider);
      localStorage.setItem('flashcards_selected_provider', preset.provider);
    }
    if (preset.model_id) {
      setSelectedModelId(preset.model_id);
      localStorage.setItem('flashcards_selected_model_id', preset.model_id);
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

  if (flashcardData) {
    return (
      <>
        <FlashcardViewer
          data={flashcardData}
          course={course}
          generationId={generationId}
          parentGenerationId={parentGenerationId}
          onClose={() => {
            setFlashcardData(null);
            setGenerationId(null);
            setParentGenerationId(null);
          }}
          onRegenerate={(regeneratePayload) => {
            const current = regeneratePayload || flashcardData || {};
            applyFlashcardsPreset(current, generationId);
            setFlashcardData(null);
          }}
          onResolve={(resolution, revertPayload) => {
            if (resolution === 'revert' && revertPayload) {
              setHistoryGenerations((prev) => prev.filter((g) => g.generation_id !== generationId));
              setFlashcardData(revertPayload);
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
            mode="flashcards"
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
      <div className="w-[220px] flex-shrink-0 bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col overflow-hidden" style={{ minHeight: '520px' }}>
        <div className="px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Sources</span>
            {materials.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400 tabular-nums whitespace-nowrap">{selectedCount} selected</span>
                <button
                  type="button"
                  onClick={() => setAllMaterialsSelected(true)}
                  className="text-[10px] font-medium text-indigo-500 hover:text-indigo-700 transition-colors whitespace-nowrap"
                >
                  All
                </button>
                <button
                  type="button"
                  onClick={() => setAllMaterialsSelected(false)}
                  className="text-[10px] font-medium text-gray-500 hover:text-gray-700 transition-colors whitespace-nowrap"
                >
                  Clear
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
          {materialsLoading && <p className="px-3 py-2 text-[10px] text-gray-400">Loading…</p>}
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
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors cursor-default border-l-2 ${
                      m.selected ? 'border-indigo-400' : 'border-transparent'
                    }`}
                  >
                    <FileTypeBadge name={m.name} sourceType={m.source_type} />
                    <span className="flex-1 truncate min-w-0 text-xs">{m.name}</span>
                    {(() => { const url = getMaterialUrl(m); return url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 p-0.5 rounded text-gray-300 hover:text-indigo-500 transition-colors" onClick={(e) => e.stopPropagation()}>
                        <ExternalLinkIcon />
                      </a>
                    ) : null; })()}
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
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-500 hover:bg-gray-100 transition-colors cursor-default border-l-2 ${
                          m.selected ? 'border-indigo-300' : 'border-transparent'
                        }`}
                      >
                        <FileTypeBadge name={m.name} sourceType={m.source_type} />
                        <span className="flex-1 truncate min-w-0 text-xs">{m.name}</span>
                        {(() => { const url = getMaterialUrl(m); return url ? (
                          <a href={url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 p-0.5 rounded text-gray-300 hover:text-indigo-500 transition-colors" onClick={(e) => e.stopPropagation()}>
                            <ExternalLinkIcon />
                          </a>
                        ) : null; })()}
                        <SourceToggle checked={m.selected} onToggle={() => toggleSource(m.id)} />
                      </div>
                    ))}
                  </>
                )}
              </>
            );
          })()}
        </div>

        <div className="px-3 pb-3 pt-2 flex-shrink-0 border-t border-gray-100 bg-white">
          <button
            type="button"
            onClick={onAddSource}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <PlusIcon />
            Add Source
          </button>
        </div>
      </div>

      <div className="flex-1 min-w-0 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col gap-5">
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-1">Custom Flashcard Generator</h2>
          <p className="text-sm text-gray-500">Generate study flashcards from your selected sources with customizable depth.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Primary Topic</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Kinematics, Control Systems..."
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-colors"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Number of Flashcards</label>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3 border border-gray-200 rounded-lg px-3 py-2 bg-white">
              <button
                type="button"
                onClick={() => setCardCount((c) => Math.max(1, c - 1))}
                disabled={cardCount <= 1}
                className="text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-30"
              >
                <MinusIcon />
              </button>
              <span className="text-sm font-semibold text-gray-900 w-5 text-center tabular-nums">{cardCount}</span>
              <button
                type="button"
                onClick={() => setCardCount((c) => Math.min(100, c + 1))}
                disabled={cardCount >= 100}
                className="text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-30"
              >
                <PlusIcon />
              </button>
            </div>
            <span className="text-sm text-gray-400">{cardCount} cards</span>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Definition Depth</label>
          <div className="flex gap-1 p-1 bg-gray-100 rounded-lg w-fit mb-2">
            {DEPTH_OPTIONS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setDepth(id)}
                className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  depth === id
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {activeDepth && <p className="text-xs text-gray-500">{activeDepth.description}</p>}
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
                            localStorage.setItem('flashcards_selected_provider', provider);
                            localStorage.setItem('flashcards_selected_model_id', model.id);
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

        <div className="mt-1 bg-white rounded-xl border border-gray-200 p-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-xs font-semibold text-gray-900">Generated & Drafted Flashcards</p>
            {historyLoading ? (
              <p className="text-[10px] text-gray-400">Loading…</p>
            ) : (
              <p className="text-[10px] text-gray-400">{historyGenerations.length} saved</p>
            )}
          </div>

          {historyLoading ? (
            <p className="text-[10px] text-gray-400">Fetching your generations…</p>
          ) : historyGenerations.length === 0 ? (
            <p className="text-[10px] text-gray-400 italic">No flashcard history yet.</p>
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
                        <p className="text-xs font-semibold text-gray-900 truncate">{g.title || g.topic || 'Flashcards'}</p>
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
                                onClick={() => applyFlashcardsPreset(g, g.generation_id)}
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

        {generateError && <p className="text-xs text-red-600">{generateError}</p>}

        <button
          type="button"
          onClick={() => handleGenerate(pendingRegenerationParentId)}
          disabled={estimating || selectedCount === 0}
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
              Generate {cardCount} Flashcards
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
            mode="flashcards"
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
