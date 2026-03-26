import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ReportsViewer from './ReportsViewer.jsx';

export default function ReportViewerRoute({ sessionToken }) {
  const navigate = useNavigate();
  const params = useParams();

  const courseId = params?.id;
  const routeGenerationId = params?.generationId;

  const authHeaders = useMemo(
    () => ({ Authorization: `Bearer ${sessionToken}` }),
    [sessionToken]
  );

  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    async function load() {
      if (!sessionToken || !routeGenerationId) return;
      setLoading(true);
      setLoadError('');
      try {
        const res = await fetch(`/api/reports?action=get_generation&generation_id=${routeGenerationId}`, {
          headers: authHeaders,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        setReport(data);
      } catch (e) {
        setLoadError(e.message || 'Failed to load report');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [sessionToken, routeGenerationId, authHeaders]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (loadError || !report) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center px-6">
        <p className="text-sm text-red-600 font-medium">{loadError || 'Failed to load report'}</p>
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
    <ReportsViewer
      report={report}
      course={{ id: Number(courseId), name: report.title || 'Report' }}
      sessionToken={sessionToken}
      templateLabel={report.template_label || report.template || 'Report'}
      onClose={() => navigate(`/course/${courseId}`)}
      onRegenerate={() => navigate(`/course/${courseId}`)}
      onSaveComplete={() => {}}
    />
  );
}
