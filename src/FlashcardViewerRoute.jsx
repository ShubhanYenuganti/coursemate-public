import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import FlashcardViewer from './FlashcardViewer';
import GenerationConfirmModal from './components/GenerationConfirmModal.jsx';

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

export default function FlashcardViewerRoute() {
  const navigate = useNavigate();
  const params = useParams();

  const courseId = params?.id;
  const routeGenerationId = params?.generationId;

  const [flashcards, setFlashcards] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [generationId, setGenerationId] = useState(null);
  const [parentGenerationId, setParentGenerationId] = useState(null);

  const [availableProviders, setAvailableProviders] = useState([]);
  const [confirmModalData, setConfirmModalData] = useState(null);
  const [estimating, setEstimating] = useState(false);
  const [regeneratingId, setRegeneratingId] = useState(null);
  const [startingRegeneration, setStartingRegeneration] = useState(false);

  useEffect(() => {
    async function load() {
      if (!routeGenerationId) return;
      setLoading(true);
      setLoadError('');
      try {
        const res = await fetch(`/api/flashcards?action=get_generation&generation_id=${routeGenerationId}`, {
          credentials: 'include',
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

        setFlashcards(data);
        setGenerationId(data.generation_id);
        setParentGenerationId(data.parent_generation_id || null);
      } catch (e) {
        setLoadError(e.message || 'Failed to load flashcards');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [routeGenerationId]);

  useEffect(() => {
    fetch('/api/user?resource=api_keys', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        const providers = Object.entries(data || {})
          .filter(([, has]) => has)
          .map(([provider]) => provider);
        setAvailableProviders(providers);
      })
      .catch(() => {});
  }, []);

  async function handleRegenerate() {
    if (!flashcards || !courseId || estimating) return;
    setEstimating(true);
    try {
      const materialIds = Array.isArray(flashcards.selected_material_ids) ? flashcards.selected_material_ids : [];
      const res = await fetch('/api/flashcards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          action: 'estimate',
          course_id: flashcards.course_id || Number(courseId),
          topic: flashcards.topic || '',
          card_count: flashcards.card_count || 20,
          depth: flashcards.depth || 'moderate',
          material_ids: materialIds,
          provider: flashcards.provider || 'openai',
          model_id: flashcards.model_id || 'gpt-4o-mini',
          parent_generation_id: generationId,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data?.generation_id) {
        setConfirmModalData(data);
      }
    } finally {
      setEstimating(false);
    }
  }

  async function confirmRegenerate({ provider, model_id: modelId } = {}) {
    if (!confirmModalData || startingRegeneration) return;
    setStartingRegeneration(true);
    const { generation_id: genId, parent_generation_id: parentId } = confirmModalData;
    setConfirmModalData(null);

    const body = { action: 'generate', generation_id: genId, parent_generation_id: parentId };
    if (provider) body.provider = provider;
    if (modelId) body.model_id = modelId;

    try {
      const res = await fetch('/api/flashcards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data?.generation_id) {
        setRegeneratingId(data.generation_id);
        setGenerationId(data.generation_id);
      } else if (!res.ok) {
        const detail = data?.detail ? ` (${data.detail})` : '';
        setLoadError((data?.error || `Failed to start regeneration (HTTP ${res.status})`) + detail);
      }
    } finally {
      setStartingRegeneration(false);
    }
  }

  useEffect(() => {
    if (!regeneratingId) return;
    const timer = setInterval(async () => {
      try {
        const r = await fetch(`/api/flashcards?action=get_generation_status&generation_id=${regeneratingId}`, {
          credentials: 'include',
        });
        if (!r.ok) return;
        const statusData = await r.json().catch(() => null);
        if (!statusData) return;

        if (statusData.status === 'ready') {
          clearInterval(timer);
          setRegeneratingId(null);
          const full = await fetch(`/api/flashcards?action=get_generation&generation_id=${regeneratingId}`, {
            credentials: 'include',
          });
          const payload = await full.json().catch(() => null);
          if (full.ok && payload?.generation_id) {
            setFlashcards(payload);
            setGenerationId(payload.generation_id);
            setParentGenerationId(payload.parent_generation_id || null);
          }
        } else if (statusData.status === 'failed') {
          clearInterval(timer);
          setRegeneratingId(null);
          setLoadError(statusData.error || 'Regeneration failed');
        }
      } catch {
        // polling retry
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [regeneratingId]);

  function handleResolve(resolution, revertPayload) {
    if (resolution === 'revert' && revertPayload) {
      setFlashcards(revertPayload);
      setGenerationId(revertPayload.generation_id);
      setParentGenerationId(revertPayload.parent_generation_id || null);
    } else {
      setParentGenerationId(null);
    }
  }

  function goToTab(tab) {
    localStorage.setItem(`coursemate_active_tab_${courseId}`, tab);
    navigate(`/course/${courseId}`);
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (loadError || !flashcards) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center px-6">
        <p className="text-sm text-red-600 font-medium">{loadError || 'Failed to load flashcards'}</p>
        <button
          type="button"
          onClick={() => navigate(`/course/${courseId}`)}
          className="mt-4 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          Back to course
        </button>
      </div>
    );
  }

  return (
    <>
      <FlashcardViewer
        data={flashcards}
        course={{ id: Number(courseId), name: flashcards.title || 'Flashcards' }}
        generationId={generationId}
        parentGenerationId={parentGenerationId}
        onRegenerate={handleRegenerate}
        onResolve={handleResolve}
        onClose={() => navigate(`/course/${courseId}`)}
        onGoToTab={goToTab}
      />
      {confirmModalData && (
        <GenerationConfirmModal
          mode="flashcards"
          data={confirmModalData}
          onConfirm={confirmRegenerate}
          onCancel={() => setConfirmModalData(null)}
          isLoading={startingRegeneration}
          availableProviders={availableProviders}
          providerModels={PROVIDER_MODELS}
          modelLabels={MODEL_LABELS}
        />
      )}
    </>
  );
}
