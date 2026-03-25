import { useEffect, useState } from 'react';

export default function GenerationConfirmModal({
  data,
  onConfirm,
  onCancel,
  onSaveDraft,
  isLoading = false,
  availableProviders = [],
  providerModels = {},
  modelLabels = {},
  mode = 'quiz',
}) {
  const [selectedProvider, setSelectedProvider] = useState(data?.provider || '');
  const [selectedModelId, setSelectedModelId] = useState(data?.model_id || '');
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    setSelectedProvider(data?.provider || '');
    setSelectedModelId(data?.model_id || '');
  }, [data?.provider, data?.model_id]);

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') {
        if (dropdownOpen) { setDropdownOpen(false); return; }
        if (isLoading) return;
        onCancel?.();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onCancel, dropdownOpen, isLoading]);

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

  const providerLabel = modelLabels[selectedProvider] || selectedProvider || data.provider;
  const modelLabel =
    (providerModels[selectedProvider] || []).find((m) => m.id === selectedModelId)?.label ||
    selectedModelId ||
    data.model_id;
  const hasProviders = availableProviders.length > 0;
  const isFlashcards = mode === 'flashcards';

  const summaryText = isFlashcards
    ? (
      <>
        You are generating: <span className="font-medium text-gray-900">{data.card_count || 0}</span> flashcards
        {' '}at <span className="font-medium text-gray-900">{data.depth || 'moderate'}</span> depth
      </>
    )
    : (
      <>
        You are generating: <span className="font-medium text-gray-900">{data.tf_count || 0}</span> T/F,{' '}
        <span className="font-medium text-gray-900">{data.sa_count || 0}</span> short answers,{' '}
        <span className="font-medium text-gray-900">{data.la_count || 0}</span> long answers,{' '}
        <span className="font-medium text-gray-900">{data.mcq_count || 0}</span> MCQ
      </>
    );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 py-6">
      <div className="w-full max-w-lg rounded-2xl bg-white border border-gray-200 shadow-xl p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-gray-900">
            {isFlashcards ? 'Confirm Flashcards Generation' : 'Confirm Quiz Generation'}
          </h3>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => onCancel?.()}
            className="px-2 py-1 rounded-lg border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Close"
          >
            Esc
          </button>
        </div>

        <div className="mt-4 space-y-3">
          {/* Model picker */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600 flex-shrink-0">Model:</span>
            {hasProviders ? (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setDropdownOpen((o) => !o)}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-gray-200 bg-white text-xs text-gray-700 hover:border-indigo-400 transition-colors"
                >
                  <span className="font-medium">{providerLabel}</span>
                  <span className="text-gray-400">·</span>
                  <span>{modelLabel}</span>
                  <svg className="w-3 h-3 text-gray-400 ml-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" /></svg>
                </button>
                {dropdownOpen && (
                  <div className="absolute z-10 mt-1 left-0 bg-white border border-gray-200 rounded-xl shadow-lg py-1 min-w-[200px] max-h-[220px] overflow-y-auto">
                    {availableProviders.map((prov) => (
                      <div key={prov}>
                        <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                          {modelLabels[prov] || prov}
                        </p>
                        {(providerModels[prov] || []).map((model) => (
                          <button
                            key={model.id}
                            type="button"
                            onClick={() => {
                              setSelectedProvider(prov);
                              setSelectedModelId(model.id);
                              setDropdownOpen(false);
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
            ) : (
              <span className="text-xs font-medium text-gray-900">
                {providerLabel} {modelLabel}
              </span>
            )}
          </div>

          <div className="rounded-xl border border-indigo-100 bg-indigo-50 px-3 py-2">
            <p className="text-[11px] text-indigo-800 font-medium">{tokenText}</p>
            <p className="text-[11px] text-indigo-800 font-medium">{totalText}</p>
          </div>

          <div className="text-xs text-gray-600">{summaryText}</div>
        </div>

        <div className="mt-5 flex items-center justify-between gap-2">
          <button
            type="button"
            disabled={isLoading}
            onClick={() => onCancel?.()}
            className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <div className="flex items-center gap-2">
            {onSaveDraft && (
              <button
                type="button"
                disabled={isLoading}
                onClick={() => onSaveDraft?.()}
                className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save as Draft
              </button>
            )}
            <button
              type="button"
              disabled={isLoading}
              onClick={() => onConfirm?.({ provider: selectedProvider, model_id: selectedModelId })}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Queueing…' : 'Confirm generate'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
