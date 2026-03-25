import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import QuizViewer from './QuizViewer';

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

  async function handleRegenerate() {
    if (!quiz || !courseId || !sessionToken) return;

    const materialIds = Array.isArray(quiz.selected_material_ids) ? quiz.selected_material_ids : [];

    const res = await fetch('/api/quiz', {
      method: 'POST',
      headers: {
        ...authHeaders,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action: 'generate',
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
    if (res.ok && data) {
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

  return (
    <QuizViewer
      quiz={quiz}
      generationId={generationId}
      parentGenerationId={parentGenerationId}
      sessionToken={sessionToken}
      onClose={() => navigate(`/course/${courseId}`)}
      onRegenerate={handleRegenerate}
      onResolve={handleResolve}
    />
  );
}

