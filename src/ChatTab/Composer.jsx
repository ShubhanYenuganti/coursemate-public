import { Link } from 'react-router-dom';
import PromptLibrary from '../components/PromptLibrary';
import {
  PaperclipIcon, ChevronDownIcon, CheckIcon,
  SendIcon, SpinnerIcon, XIcon,
} from './icons';
import { MODEL_LABELS } from './helpers';
import { PROVIDER_MODELS } from '../modelCatalog.js';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';

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
        <div className="flex-shrink-0 px-4 pb-4 pt-2 border-t border-border bg-background">
          {/* Image preview strip */}
          {images.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {images.map((file, idx) => {
                const uploading = imageUploadStates[idx] === 'uploading';
                return (
                  <div key={idx} className="relative flex flex-col items-center gap-0.5">
                    <div className="relative w-14 h-14 rounded-lg overflow-hidden border border-border bg-muted flex-shrink-0">
                      <img
                        src={URL.createObjectURL(file)}
                        alt={file.name}
                        className="w-full h-full object-cover"
                      />
                      {uploading && (
                        <div className="absolute inset-0 bg-background/70 flex items-center justify-center">
                          <SpinnerIcon />
                        </div>
                      )}
                    </div>
                    <span className="text-[9px] text-muted-foreground max-w-[56px] truncate">{file.name}</span>
                    {!uploading && (
                      <button
                        type="button"
                        onClick={() => removeImage(idx)}
                        className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-muted-foreground text-background flex items-center justify-center hover:bg-destructive transition-colors"
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

          <div className="relative flex flex-col rounded-2xl border border-border bg-background hover:shadow-lg focus-within:border-ring focus-within:shadow-lg transition-all" style={{ boxShadow: '0 4px 24px 0 rgba(0,0,0,0.13)' }}>
            {promptLibOpen && (
              <PromptLibrary
                onInsert={(text) => {
                  setInput((v) => (v ? `${v}\n${text}` : text));
                  setPromptLibOpen(false);
                }}
                onClose={() => setPromptLibOpen(false)}
              />
            )}
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder="Reply…"
              rows={1}
              className="w-full min-w-0 min-h-0 rounded-none border-transparent bg-transparent resize-none text-xs text-foreground placeholder:text-muted-foreground focus-visible:border-transparent focus-visible:ring-0 leading-relaxed px-4 pt-3 pb-1 md:text-xs"
              style={{
                minHeight: composerMinHeight,
                maxHeight: composerMaxHeight,
                overflowY: 'auto',
              }}
            />
            <div className="flex items-center justify-end gap-1 px-3 pb-2 pt-1">
                {/* Attachment button */}
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-shrink-0 rounded text-muted-foreground hover:text-primary hover:bg-accent"
                  title="Attach image"
                >
                  <PaperclipIcon />
                </Button>

                {/* Model selector */}
                {availableModels.length > 0 && (
                  <>
                    {/* Provider dropdown */}
                    <div className="relative" ref={dropdownRef}>
                      <button
                        type="button"
                        onClick={() => setModelDropdownOpen((o) => !o)}
                        className="flex items-center gap-0.5 text-muted-foreground text-xs hover:text-foreground transition-colors"
                      >
                        <span>{MODEL_LABELS[selectedModel] || selectedModel}</span>
                        <ChevronDownIcon />
                      </button>
                      {modelDropdownOpen && (
                        <div className="absolute bottom-full right-0 mb-2 bg-popover text-popover-foreground rounded-xl shadow-xl py-1 min-w-[130px] z-50 border border-border">
                          {availableModels.map((provider) => (
                            <button key={provider} type="button" onClick={() => handleModelSelect(provider)}
                              className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left transition-colors rounded-lg hover:bg-accent">
                              <span className={selectedModel === provider ? 'text-foreground font-medium' : 'text-muted-foreground'}>
                                {MODEL_LABELS[provider] || provider}
                              </span>
                              {selectedModel === provider && <span className="text-primary"><CheckIcon /></span>}
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
                          className="flex items-center gap-0.5 text-muted-foreground text-xs hover:text-foreground transition-colors"
                        >
                          <span>{PROVIDER_MODELS[selectedModel]?.find((m) => m.id === selectedModelId)?.label || selectedModelId}</span>
                          <ChevronDownIcon />
                        </button>
                        {modelListDropdownOpen && (
                          <div className="absolute bottom-full right-0 mb-2 bg-popover text-popover-foreground rounded-xl shadow-xl py-1 min-w-[180px] z-50 border border-border max-h-48 overflow-y-auto">
                            {PROVIDER_MODELS[selectedModel].map((m) => (
                              <button key={m.id} type="button" onClick={() => handleModelIdSelect(m.id)}
                                className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left transition-colors rounded-lg hover:bg-accent">
                                <span className={selectedModelId === m.id ? 'text-foreground font-medium' : 'text-muted-foreground'}>
                                  {m.label}
                                </span>
                                {selectedModelId === m.id && <span className="text-primary"><CheckIcon /></span>}
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
                      ? 'border-ring text-primary bg-accent'
                      : 'border-border text-muted-foreground hover:border-ring hover:text-primary hover:bg-accent'
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
                      ? 'border-ring text-primary bg-accent'
                      : 'border-border text-muted-foreground hover:border-ring hover:text-primary hover:bg-accent'
                  }`}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="2" y1="12" x2="22" y2="12"/>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                  </svg>
                </button>
                <Button
                  type="button"
                  size="icon-xs"
                  onClick={handleSend}
                  disabled={!gate.canSend || (!input.trim() && images.length === 0) || sending || !selectedModel}
                  title={gate.disabledReason || undefined}
                  className="flex-shrink-0 w-6 h-6 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
                >
                  <SendIcon />
                </Button>
            </div>
          </div>
          <p className="text-center text-[10px] text-muted-foreground mt-1.5">
            AI responses are based on your uploaded course materials.
          </p>
        </div>
  );
}
