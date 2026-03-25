import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import QuizViewer from './QuizViewer';
import GenerationConfirmModal from './components/GenerationConfirmModal.jsx';

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

function ToolbarItem({ icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex items-center gap-2 transition-all duration-150 rounded-xl px-1 py-1 focus:outline-none cursor-pointer"
    >
      <span className="max-w-0 overflow-hidden whitespace-nowrap text-sm font-medium transition-all duration-200 ease-out group-hover:max-w-xs text-gray-700">
        {label}
      </span>
      <div className="w-10 h-10 flex items-center justify-center rounded-xl border shadow-sm text-lg transition-all duration-200 bg-white/80 border-gray-200 text-gray-600 group-hover:text-indigo-600 group-hover:border-indigo-300 group-hover:shadow-md">
        {icon}
      </div>
    </button>
  );
}

export default function QuizViewerRoute({ sessionToken }) {
  const navigate = useNavigate();
  const params = useParams();

  const courseId = params?.id;
  const routeGenerationId = params?.generationId;

  const authHeaders = useMemo(
    () => ({
      Authorization: `Bearer ${sessionToken}`,
    }),
    [sessionToken]
  );

  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [generationId, setGenerationId] = useState(null);
  const [parentGenerationId, setParentGenerationId] = useState(null);

  const [availableProviders, setAvailableProviders] = useState([]);
  const [confirmModalData, setConfirmModalData] = useState(null);
  const [estimating, setEstimating] = useState(false);

  useEffect(() => {
    async function load() {
      if (!sessionToken || !routeGenerationId) return;
      setLoading(true);
      setLoadError('');
      try {
        const res = await fetch(`/api/quiz?action=get_generation&generation_id=${routeGenerationId}`, {
          headers: authHeaders,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

        setQuiz(data);
        setGenerationId(data.generation_id);
        setParentGenerationId(data.parent_generation_id || null);
      } catch (e) {
        setLoadError(e.message || 'Failed to load quiz');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [sessionToken, routeGenerationId, authHeaders]);

  useEffect(() => {
    if (!sessionToken) return;
    fetch('/api/generate?action=available_providers', {
      headers: authHeaders,
    })
      .then((r) => r.json())
      .then((data) => {
        const providers = Array.isArray(data?.providers) ? data.providers : [];
        setAvailableProviders(providers);
      })
      .catch(() => {});
  }, [sessionToken, authHeaders]);

  async function handleRegenerate() {
    if (!quiz || !courseId || !sessionToken || estimating) return;
    setEstimating(true);
    try {
      const materialIds = Array.isArray(quiz.selected_material_ids) ? quiz.selected_material_ids : [];
      const res = await fetch('/api/quiz', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'estimate',
          course_id: quiz.course_id || Number(courseId),
          topic: quiz.topic || '',
          tf_count: quiz.tf_count || 0,
          sa_count: quiz.sa_count || 0,
          la_count: quiz.la_count || 0,
          mcq_count: quiz.mcq_count || 0,
          mcq_options: quiz.mcq_options || 4,
          material_ids: materialIds,
          provider: quiz.provider || 'openai',
          model_id: quiz.model_id || 'gpt-4o-mini',
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
    if (!confirmModalData) return;
    const { generation_id: genId, parent_generation_id: parentId } = confirmModalData;
    setConfirmModalData(null);
    const body = { action: 'generate', generation_id: genId, parent_generation_id: parentId };
    if (provider) body.provider = provider;
    if (modelId) body.model_id = modelId;
    const res = await fetch('/api/quiz', {
      method: 'POST',
      headers: { ...authHeaders, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data?.generation_id) {
      setQuiz(data);
      setGenerationId(data.generation_id);
      setParentGenerationId(data.parent_generation_id || null);
    }
  }

  function handleResolve(resolution, revertPayload) {
    if (resolution === 'revert' && revertPayload) {
      setQuiz(revertPayload);
      setGenerationId(revertPayload.generation_id);
      setParentGenerationId(revertPayload.parent_generation_id || null);
    } else {
      setParentGenerationId(null);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (loadError || !quiz) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center px-6">
        <p className="text-sm text-red-600 font-medium">{loadError || 'Failed to load quiz'}</p>
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

  function goToTab(tab) {
    localStorage.setItem(`coursemate_active_tab_${courseId}`, tab);
    navigate(`/course/${courseId}`);
  }

  return (
    <>
      <QuizViewer
        quiz={quiz}
        generationId={generationId}
        parentGenerationId={parentGenerationId}
        sessionToken={sessionToken}
        onClose={() => navigate(`/course/${courseId}`)}
        onRegenerate={handleRegenerate}
        onResolve={handleResolve}
      />
      {confirmModalData && (
        <GenerationConfirmModal
          data={confirmModalData}
          onConfirm={confirmRegenerate}
          onCancel={() => {
            const genId = confirmModalData?.generation_id;
            setConfirmModalData(null);
            if (genId) {
              fetch(`/api/quiz?generation_id=${genId}`, {
                method: 'DELETE',
                headers: authHeaders,
              }).catch(() => {});
            }
          }}
          availableProviders={availableProviders}
          providerModels={PROVIDER_MODELS}
          modelLabels={MODEL_LABELS}
        />
      )}
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-3 rounded-2xl bg-white/70 backdrop-blur-md border border-gray-200 shadow-lg z-20">
        <ToolbarItem icon="📄" label="Materials" onClick={() => goToTab('materials')} />
        <div className="w-px h-6 bg-gray-200" />
        <ToolbarItem icon="💬" label="Chat"      onClick={() => goToTab('chat')} />
        <div className="w-px h-6 bg-gray-200" />
        <ToolbarItem icon="💡" label="Generate"  onClick={() => goToTab('generate')} />
      </div>
    </>
  );
}
