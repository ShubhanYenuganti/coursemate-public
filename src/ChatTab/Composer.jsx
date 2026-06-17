import { Link } from 'react-router-dom';
import PromptLibrary from '../components/PromptLibrary';
import {
  PaperclipIcon, ChevronDownIcon, CheckIcon,
  SendIcon, SpinnerIcon, XIcon,
} from './icons';
import { MODEL_LABELS } from './helpers';
import { PROVIDER_MODELS } from '../modelCatalog.js';

export function Composer({
  // state + setters
  images,
  imageUploadStates,
  input,
  setInput,
  availableModels,
  selectedModel,
  selectedModelId,
  modelDropdownOpen,
  setModelDropdownOpen,
  modelListDropdownOpen,
  setModelListDropdownOpen,
  promptLibOpen,
  setPromptLibOpen,
  webSearchEnabled,
  sending,
  gate,
  // refs (created in ChatTab)
  textareaRef,
  fileInputRef,
  dropdownRef,
  modelListDropdownRef,
  // handlers (defined in ChatTab)
  handleSend,
  handleKeyDown,
  handlePaste,
  handleFileInputChange,
  handleModelSelect,
  handleModelIdSelect,
  toggleWebSearch,
  removeImage,
  // height constants (shared with ChatTab auto-resize effect)
  composerMinHeight,
  composerMaxHeight,
}) {
  return (
        <div className="flex-shrink-0 px-4 pb-4 pt-2 border-t border-gray-100 bg-white">
          {/* Image preview strip */}
          {images.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {images.map((file, idx) => {
                const uploading = imageUploadStates[idx] === 'uploading';
                return (
                  <div key={idx} className="relative flex flex-col items-center gap-0.5">
                    <div className="relative w-14 h-14 rounded-lg overflow-hidden border border-gray-200 bg-gray-50 flex-shrink-0">
                      <img
                        src={URL.createObjectURL(file)}
                        alt={file.name}
                        className="w-full h-full object-cover"
                      />
                      {uploading && (
                        <div className="absolute inset-0 bg-white/70 flex items-center justify-center">
                          <SpinnerIcon />
                        </div>
                      )}
                    </div>
                    <span className="text-[9px] text-gray-400 max-w-[56px] truncate">{file.name}</span>
                    {!uploading && (
                      <button
                        type="button"
                        onClick={() => removeImage(idx)}
                        className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-gray-600 text-white flex items-center justify-center hover:bg-red-500 transition-colors"
                      >
                        <XIcon />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg"
            multiple
            className="hidden"
            onChange={handleFileInputChange}
          />

          {gate.bannerText && (
            <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {gate.bannerText}{' '}
              <Link to="/profile" className="font-medium text-amber-900 underline hover:text-amber-950">
                Open Profile
              </Link>
            </div>
          )}

          <div className="relative flex flex-col rounded-2xl border border-gray-200 bg-white hover:shadow-lg focus-within:border-indigo-300 focus-within:shadow-lg transition-all" style={{ boxShadow: '0 4px 24px 0 rgba(0,0,0,0.13)' }}>
            {promptLibOpen && (
              <PromptLibrary
                onInsert={(text) => {
                  setInput((v) => (v ? `${v}\n${text}` : text));
                  setPromptLibOpen(false);
                }}
                onClose={() => setPromptLibOpen(false)}
              />
            )}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder="Reply…"
              rows={1}
              className="w-full min-w-0 bg-transparent resize-none text-xs text-gray-800 placeholder-gray-400 focus:outline-none leading-relaxed px-4 pt-3 pb-1"
              style={{
                minHeight: composerMinHeight,
                maxHeight: composerMaxHeight,
                overflowY: 'auto',
              }}
            />
            <div className="flex items-center justify-end gap-1 px-3 pb-2 pt-1">
                {/* Attachment button */}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-shrink-0 p-1 rounded text-gray-300 hover:text-indigo-500 hover:bg-indigo-50 transition-colors"
                  title="Attach image"
                >
                  <PaperclipIcon />
                </button>

                {/* Model selector */}
                {availableModels.length > 0 && (
                  <>
                    {/* Provider dropdown */}
                    <div className="relative" ref={dropdownRef}>
                      <button
                        type="button"
                        onClick={() => setModelDropdownOpen((o) => !o)}
                        className="flex items-center gap-0.5 text-gray-400 text-xs hover:text-gray-600 transition-colors"
                      >
                        <span>{MODEL_LABELS[selectedModel] || selectedModel}</span>
                        <ChevronDownIcon />
                      </button>
                      {modelDropdownOpen && (
                        <div className="absolute bottom-full right-0 mb-2 bg-gray-900 rounded-xl shadow-xl py-1 min-w-[130px] z-50 border border-gray-700/60">
                          {availableModels.map((provider) => (
                            <button key={provider} type="button" onClick={() => handleModelSelect(provider)}
                              className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left transition-colors rounded-lg hover:bg-gray-700/70">
                              <span className={selectedModel === provider ? 'text-white font-medium' : 'text-gray-300'}>
                                {MODEL_LABELS[provider] || provider}
                              </span>
                              {selectedModel === provider && <span className="text-indigo-400"><CheckIcon /></span>}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Specific model dropdown */}
                    {selectedModel && PROVIDER_MODELS[selectedModel] && (
                      <div className="relative ml-1" ref={modelListDropdownRef}>
                        <button
                          type="button"
                          onClick={() => setModelListDropdownOpen((o) => !o)}
                          className="flex items-center gap-0.5 text-gray-400 text-xs hover:text-gray-600 transition-colors"
                        >
                          <span>{PROVIDER_MODELS[selectedModel]?.find((m) => m.id === selectedModelId)?.label || selectedModelId}</span>
                          <ChevronDownIcon />
                        </button>
                        {modelListDropdownOpen && (
                          <div className="absolute bottom-full right-0 mb-2 bg-gray-900 rounded-xl shadow-xl py-1 min-w-[180px] z-50 border border-gray-700/60 max-h-48 overflow-y-auto">
                            {PROVIDER_MODELS[selectedModel].map((m) => (
                              <button key={m.id} type="button" onClick={() => handleModelIdSelect(m.id)}
                                className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left transition-colors rounded-lg hover:bg-gray-700/70">
                                <span className={selectedModelId === m.id ? 'text-white font-medium' : 'text-gray-300'}>
                                  {m.label}
                                </span>
                                {selectedModelId === m.id && <span className="text-indigo-400"><CheckIcon /></span>}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
                <button
                  type="button"
                  onClick={() => setPromptLibOpen((o) => !o)}
                  title="Saved prompts"
                  aria-pressed={promptLibOpen}
                  className={`flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full border transition-colors ${
                    promptLibOpen
                      ? 'border-indigo-400 text-indigo-600 bg-indigo-50'
                      : 'border-gray-200 text-gray-400 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50'
                  }`}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                  </svg>
                </button>
                <button
                  type="button"
                  onClick={toggleWebSearch}
                  title={webSearchEnabled ? 'Web search on (click to disable)' : 'Web search off (click to enable)'}
                  aria-pressed={webSearchEnabled}
                  className={`flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full border transition-colors ${
                    webSearchEnabled
                      ? 'border-indigo-400 text-indigo-600 bg-indigo-50'
                      : 'border-gray-200 text-gray-400 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50'
                  }`}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="2" y1="12" x2="22" y2="12"/>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                  </svg>
                </button>
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!gate.canSend || (!input.trim() && images.length === 0) || sending || !selectedModel}
                  title={gate.disabledReason || undefined}
                  className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
                >
                  <SendIcon />
                </button>
            </div>
          </div>
          <p className="text-center text-[10px] text-gray-400 mt-1.5">
            AI responses are based on your uploaded course materials.
          </p>
        </div>
  );
}
