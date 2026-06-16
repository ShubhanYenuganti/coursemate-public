import { useState, useEffect, useRef, useCallback } from 'react';
import { formatDateTime } from './utils/dateUtils';
import { getMaterialUrl } from './utils/materialUtils';
import FlashcardViewer from './FlashcardViewer';
import GenerationConfirmModal from './components/GenerationConfirmModal.jsx';
import DueTodayWidget from './components/DueTodayWidget.jsx';
import { PROVIDER_MODELS } from './modelCatalog.js';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';

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
  txt: { label: 'TXT', bg: 'bg-muted', text: 'text-muted-foreground' },
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
      <span className="flex-shrink-0 inline-flex items-center justify-center w-[22px] h-[16px] rounded bg-muted text-muted-foreground">
        <NotionBadgeIcon />
      </span>
    );
  }

  const style = mapped || { label: ext.slice(0, 3).toUpperCase() || 'DOC', bg: 'bg-muted', text: 'text-muted-foreground' };
  return (
    <span className={`flex-shrink-0 inline-flex items-center justify-center w-[22px] h-[16px] rounded text-[7px] font-bold tracking-tight ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}

function SourceToggle({ checked, onToggle }) {
  return (
    <Button
      type="button"
      variant="ghost"
      onClick={(e) => { e.stopPropagation(); onToggle(); }}
      className={`flex-shrink-0 relative inline-flex h-4 w-7 p-0 items-center rounded-full transition-colors focus:outline-none hover:bg-transparent ${
        checked ? 'bg-primary' : 'bg-muted'
      }`}
    >
      <span className={`inline-block h-3 w-3 transform rounded-full bg-background shadow-sm transition-transform ${
        checked ? 'translate-x-3.5' : 'translate-x-0.5'
      }`} />
    </Button>
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

// PROVIDER_MODELS imported from ./modelCatalog.js

const MODEL_LABELS = { gemini: 'Gemini', openai: 'GPT', claude: 'Claude' };

export default function Flashcards({ course, onAddSource }) {
  const [materials, setMaterials] = useState([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);

  const [topic, setTopic] = useState(() => {
    try { return JSON.parse(localStorage.getItem(`flashcards_fields_${course?.id}`) || '{}').topic || ''; } catch { return ''; }
  });
  const [cardCount, setCardCount] = useState(() => {
    try { return JSON.parse(localStorage.getItem(`flashcards_fields_${course?.id}`) || '{}').card_count ?? 20; } catch { return 20; }
  });
  const [depth, setDepth] = useState(() => {
    try { return JSON.parse(localStorage.getItem(`flashcards_fields_${course?.id}`) || '{}').depth || 'moderate'; } catch { return 'moderate'; }
  });

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
      .then((data) => {
        const mats = Array.isArray(data) ? data : (data.materials || []);
        try {
          const stored = JSON.parse(localStorage.getItem(`flashcards_fields_${course.id}`) || '{}');
          if (Array.isArray(stored.material_ids) && stored.material_ids.length > 0) {
            const ids = new Set(stored.material_ids.map(Number));
            setMaterials(mats.map((m) => ({ ...m, selected: ids.has(Number(m.id)) })));
            return;
          }
        } catch {}
        setMaterials(mats);
      })
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

      try {
        localStorage.setItem(`flashcards_fields_${course?.id}`, JSON.stringify({
          topic: topicToUse, card_count: cardCountToUse, depth: depthToUse,
          material_ids: contextIds,
        }));
      } catch {}

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
    <>
    <div className="flex gap-4 items-start">
      <Card className="w-[220px] flex-shrink-0 rounded-2xl border border-border shadow-sm ring-0 flex flex-col overflow-hidden p-0 gap-0 [--card-spacing:0px]" style={{ minHeight: '520px' }}>
        <div className="px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Sources</span>
            {materials.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground tabular-nums whitespace-nowrap">{selectedCount} selected</span>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setAllMaterialsSelected(true)}
                  className="h-auto w-auto p-0 rounded-md text-[10px] font-medium text-primary hover:text-accent-foreground hover:bg-transparent transition-colors whitespace-nowrap"
                >
                  All
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setAllMaterialsSelected(false)}
                  className="h-auto w-auto p-0 rounded-md text-[10px] font-medium text-muted-foreground hover:text-foreground hover:bg-transparent transition-colors whitespace-nowrap"
                >
                  Clear
                </Button>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
          {materialsLoading && <p className="px-3 py-2 text-[10px] text-muted-foreground">Loading…</p>}
          {!materialsLoading && materials.length === 0 && (
            <p className="px-3 py-2 text-[10px] text-muted-foreground italic">No materials yet.</p>
          )}
          {(() => {
            const myMats = materials.filter((m) => !m.collaborator);
            const collabMats = materials.filter((m) => m.collaborator);
            return (
              <>
                {myMats.map((m) => (
                  <div
                    key={m.id}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-muted-foreground hover:bg-muted transition-colors cursor-default border-l-2 ${
                      m.selected ? 'border-primary' : 'border-transparent'
                    }`}
                  >
                    <FileTypeBadge name={m.name} sourceType={m.source_type} />
                    <span className="flex-1 truncate min-w-0 text-xs">{m.name}</span>
                    {(() => { const url = getMaterialUrl(m); return url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 p-0.5 rounded text-muted-foreground hover:text-primary transition-colors" onClick={(e) => e.stopPropagation()}>
                        <ExternalLinkIcon />
                      </a>
                    ) : null; })()}
                    <SourceToggle checked={m.selected} onToggle={() => toggleSource(m.id)} />
                  </div>
                ))}
                {collabMats.length > 0 && (
                  <>
                    <div className="px-3 pt-2 pb-0.5">
                      <span className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider">From collaborators</span>
                    </div>
                    {collabMats.map((m) => (
                      <div
                        key={m.id}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-muted-foreground hover:bg-muted transition-colors cursor-default border-l-2 ${
                          m.selected ? 'border-primary' : 'border-transparent'
                        }`}
                      >
                        <FileTypeBadge name={m.name} sourceType={m.source_type} />
                        <span className="flex-1 truncate min-w-0 text-xs">{m.name}</span>
                        {(() => { const url = getMaterialUrl(m); return url ? (
                          <a href={url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0 p-0.5 rounded text-muted-foreground hover:text-primary transition-colors" onClick={(e) => e.stopPropagation()}>
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

        <div className="px-3 pb-3 pt-2 flex-shrink-0 border-t border-border bg-background">
          <Button
            type="button"
            variant="outline"
            onClick={onAddSource}
            className="w-full h-auto flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium text-foreground hover:bg-muted transition-colors"
          >
            <PlusIcon />
            Add Source
          </Button>
        </div>
      </Card>

      <Card className="flex-1 min-w-0 rounded-2xl border border-border shadow-sm ring-0 p-6 flex flex-col gap-5 [--card-spacing:0px]">
        <div>
          <h2 className="text-xl font-bold text-foreground mb-1">Custom Flashcard Generator</h2>
          <p className="text-sm text-muted-foreground">Generate study flashcards from your selected sources with customizable depth.</p>
        </div>

        <div>
          <Label className="block text-sm font-medium text-foreground mb-1.5">Primary Topic</Label>
          <Input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Kinematics, Control Systems..."
            className="w-full rounded-lg border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring transition-colors"
          />
        </div>

        <div>
          <Label className="block text-sm font-medium text-foreground mb-1.5">Number of Flashcards</Label>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3 border border-border rounded-lg px-3 py-2 bg-background">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setCardCount((c) => Math.max(1, c - 1))}
                disabled={cardCount <= 1}
                className="h-auto w-auto p-0 rounded-md text-muted-foreground hover:text-foreground hover:bg-transparent transition-colors disabled:opacity-30"
              >
                <MinusIcon />
              </Button>
              <span className="text-sm font-semibold text-foreground w-5 text-center tabular-nums">{cardCount}</span>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setCardCount((c) => Math.min(100, c + 1))}
                disabled={cardCount >= 100}
                className="h-auto w-auto p-0 rounded-md text-muted-foreground hover:text-foreground hover:bg-transparent transition-colors disabled:opacity-30"
              >
                <PlusIcon />
              </Button>
            </div>
            <span className="text-sm text-muted-foreground">{cardCount} cards</span>
          </div>
        </div>

        <div>
          <Label className="block text-sm font-medium text-foreground mb-2">Definition Depth</Label>
          <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit mb-2">
            {DEPTH_OPTIONS.map(({ id, label }) => (
              <Button
                key={id}
                type="button"
                variant="ghost"
                onClick={() => setDepth(id)}
                className={`h-auto px-4 py-1.5 rounded-md text-xs font-medium transition-colors hover:bg-transparent ${
                  depth === id
                    ? 'bg-primary text-primary-foreground shadow-sm hover:bg-primary'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {label}
              </Button>
            ))}
          </div>
          {activeDepth && <p className="text-xs text-muted-foreground">{activeDepth.description}</p>}
        </div>

        {availableProviders.length > 0 && (
          <div>
            <Label className="block text-xs font-medium text-muted-foreground mb-2">AI Model</Label>
            <div className="relative inline-block" ref={providerDropdownRef}>
              <Button
                type="button"
                variant="outline"
                onClick={() => setProviderDropdownOpen((open) => !open)}
                className="h-auto flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-foreground hover:border-ring transition-colors"
              >
                <span className="font-medium">{MODEL_LABELS[selectedProvider] || selectedProvider}</span>
                <span className="text-muted-foreground">·</span>
                <span>{(PROVIDER_MODELS[selectedProvider] || []).find((m) => m.id === selectedModelId)?.label || selectedModelId}</span>
                <ChevronDownIcon />
              </Button>
              {providerDropdownOpen && (
                <div className="absolute z-20 mt-1 left-0 bg-background border border-border rounded-xl shadow-lg py-1 min-w-[220px] max-h-[280px] overflow-y-auto">
                  {availableProviders.map((provider) => (
                    <div key={provider}>
                      <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        {MODEL_LABELS[provider] || provider}
                      </p>
                      {(PROVIDER_MODELS[provider] || []).map((model) => (
                        <Button
                          key={model.id}
                          type="button"
                          variant="ghost"
                          onClick={() => {
                            setSelectedProvider(provider);
                            setSelectedModelId(model.id);
                            localStorage.setItem('flashcards_selected_provider', provider);
                            localStorage.setItem('flashcards_selected_model_id', model.id);
                            setProviderDropdownOpen(false);
                          }}
                          className={`w-full h-auto block rounded-none text-left px-4 py-1.5 text-xs hover:bg-accent transition-colors ${
                            model.id === selectedModelId ? 'text-primary font-medium' : 'text-foreground'
                          }`}
                        >
                          {model.label}
                        </Button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mt-1 bg-background rounded-xl border border-border p-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-xs font-semibold text-foreground">Generated & Drafted Flashcards</p>
            {historyLoading ? (
              <p className="text-[10px] text-muted-foreground">Loading…</p>
            ) : (
              <p className="text-[10px] text-muted-foreground">{historyGenerations.length} saved</p>
            )}
          </div>

          {historyLoading ? (
            <p className="text-[10px] text-muted-foreground">Fetching your generations…</p>
          ) : historyGenerations.length === 0 ? (
            <p className="text-[10px] text-muted-foreground italic">No flashcard history yet.</p>
          ) : (
            <div className="space-y-2">
              {historyGenerations.map((g) => {
                const isPolling = generatingIds.has(g.generation_id);
                const status = isPolling && g.status === 'queued' ? 'queued' : (isPolling ? 'generating' : (g.status || 'ready'));
                const badgeClass =
                  status === 'ready'
                    ? 'border-green-200 bg-green-50 text-green-700'
                    : status === 'failed'
                      ? 'border-destructive/20 bg-destructive/10 text-destructive'
                      : status === 'draft'
                        ? 'border-amber-200 bg-amber-50 text-amber-800'
                        : status === 'queued'
                          ? 'border-purple-200 bg-purple-50 text-purple-700'
                          : 'border-accent bg-accent text-accent-foreground';

                const tokenLow = g.estimated_total_tokens_low;
                const tokenHigh = g.estimated_total_tokens_high;
                const tokenText =
                  typeof tokenLow === 'number' && typeof tokenHigh === 'number'
                    ? `${tokenLow}-${tokenHigh}`
                    : 'N/A';

                const createdAt = formatDateTime(g.created_at);

                return (
                  <div key={g.generation_id} className="rounded-lg border border-border p-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-foreground truncate">{g.title || g.topic || 'Flashcards'}</p>
                        <p className="text-[10px] text-muted-foreground mt-0.5 truncate">
                          {g.provider || 'provider'} · {g.model_id || 'model'} · {createdAt}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <Badge variant="outline" className={`gap-1 px-2 py-1 h-auto rounded-full text-[10px] font-medium ${badgeClass}`}>
                          {(status === 'generating' || status === 'queued') && (
                            <svg className="animate-spin h-2.5 w-2.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                            </svg>
                          )}
                          {status}
                        </Badge>
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => deleteGeneration(g.generation_id)}
                          className="h-auto w-auto p-1 rounded text-muted-foreground/50 hover:text-destructive hover:bg-destructive/10 transition-colors"
                          aria-label="Delete"
                        >
                          <TrashIcon />
                        </Button>
                      </div>
                    </div>

                    <div className="mt-2 flex items-center justify-between gap-3">
                      <p className="text-[10px] text-muted-foreground">
                        Tokens: <span className="font-medium text-muted-foreground">{tokenText}</span>
                      </p>

                      <div className="flex items-center gap-2">
                        {status === 'generating' ? (
                          <p className="text-[10px] text-primary italic">Processing…</p>
                        ) : status === 'queued' ? (
                          <p className="text-[10px] text-purple-600 italic">Queued…</p>
                        ) : status === 'draft' ? (
                          <Button
                            type="button"
                            onClick={() => triggerGeneration(g.generation_id)}
                            disabled={estimating}
                            className="h-auto px-2 py-1 rounded-lg text-[10px] font-medium"
                          >
                            Generate
                          </Button>
                        ) : (
                          <>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => reopenFromHistory(g)}
                              className="h-auto px-2 py-1 rounded-lg text-[10px] font-medium text-muted-foreground"
                            >
                              Open
                            </Button>
                            {status === 'ready' && (
                              <Button
                                type="button"
                                onClick={() => applyFlashcardsPreset(g, g.generation_id)}
                                disabled={estimating}
                                className="h-auto px-2 py-1 rounded-lg text-[10px] font-medium"
                              >
                                Regenerate
                              </Button>
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

        {generateError && <p className="text-xs text-destructive">{generateError}</p>}

        <Button
          type="button"
          onClick={() => handleGenerate(pendingRegenerationParentId)}
          disabled={estimating || selectedCount === 0}
          className="h-auto w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
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
        </Button>

        <p className="text-[10px] text-muted-foreground flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
          AI responses are based on your selected course materials.{' '}
          <a href="#" className="text-primary hover:underline">Learn more</a>
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
      </Card>
    </div>
      <div className="mt-4">
        <DueTodayWidget courseId={course?.id} />
      </div>
    </>
  );
}
