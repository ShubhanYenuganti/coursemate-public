import { useEffect } from 'react';

export default function GenerationConfirmModal({ data, onConfirm, onCancel }) {
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') {
        onCancel?.();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onCancel]);

  if (!data) return null;

  const promptLow = data.estimated_prompt_tokens_low;
  const promptHigh = data.estimated_prompt_tokens_high;
  const totalLow = data.estimated_total_tokens_low;
  const totalHigh = data.estimated_total_tokens_high;

  const tokenText =
    typeof promptLow === 'number' && typeof promptHigh === 'number'
      ? `Prompt: ${promptLow}-${promptHigh}`
      : 'Prompt: N/A';

  const totalText =
    typeof totalLow === 'number' && typeof totalHigh === 'number'
      ? `Total: ${totalLow}-${totalHigh}`
      : 'Total: N/A';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 py-6">
      <div className="w-full max-w-lg rounded-2xl bg-white border border-gray-200 shadow-xl p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-gray-900">Confirm Quiz Generation</h3>
          <button
            type="button"
            onClick={() => onCancel?.()}
            className="px-2 py-1 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
            aria-label="Close"
          >
            Esc
          </button>
        </div>

        <div className="mt-4 space-y-3">
          <div className="text-xs text-gray-600">
            Model: <span className="font-medium text-gray-900">{data.provider || 'provider'}</span>{' '}
            <span className="font-medium text-gray-900">{data.model_id || ''}</span>
          </div>

          <div className="rounded-xl border border-indigo-100 bg-indigo-50 px-3 py-2">
            <p className="text-[11px] text-indigo-800 font-medium">{tokenText}</p>
            <p className="text-[11px] text-indigo-800 font-medium">{totalText}</p>
          </div>

          <div className="text-xs text-gray-600">
            You are generating: <span className="font-medium text-gray-900">{data.tf_count || 0}</span> T/F,{' '}
            <span className="font-medium text-gray-900">{data.sa_count || 0}</span> short answers,{' '}
            <span className="font-medium text-gray-900">{data.la_count || 0}</span> long answers,{' '}
            <span className="font-medium text-gray-900">{data.mcq_count || 0}</span> MCQ
          </div>
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => onCancel?.()}
            className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm?.()}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition-colors"
          >
            Confirm generate
          </button>
        </div>
      </div>
    </div>
  );
}

