import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

import {
  PinIcon, CopyIcon, RefreshIcon, RevertIcon, RestoreIcon, MoreIcon, EditIcon,
  XIcon, ChevronDownIcon, CheckIcon, PaperclipIcon, SpinnerIcon,
} from './icons';
import { getMessageModelLabel, MODEL_LABELS } from './helpers';
import { LiveStatusLine, ToolTraceIndicator } from './StreamingStatus';
import { PROVIDER_MODELS } from '../modelCatalog.js';
import { formatDateTime } from '../utils/dateUtils';
import GenerationProposalCard from '../components/GenerationProposalCard';

export default function MessageBubble({
  msg,
  courseName,
  userPicture,
  onCiteClick,
  webSearchUrls,
  isEditing,
  editingContent,
  onEditStart,
  onEditChange,
  onEditSave,
  onEditCancel,
  canEdit,
  replyHistory,
  onRevert,
  onRestore,
  onRegenerate,
  availableModels,
  materials,
  onPin,
  isPinned,
  onFollowUpClick,
  onSkipClarification,
  isLastAssistantMsg,
  editImages = [],
  onEditImageAdd,
  onEditImageRemove,
  editFileInputRef,
  onBuild,
  onRefine,
}) {
  const isUser = msg.role === 'user';
  const modelLabel = getMessageModelLabel(msg);
  const [copied, setCopied] = useState(false);
  const [regenOpen, setRegenOpen] = useState(false);
  const [regenProvider, setRegenProvider] = useState(null);
  const regenRef = useRef(null);

  useEffect(() => {
    if (!regenOpen) return;
    function handleClickOutside(e) {
      if (regenRef.current && !regenRef.current.contains(e.target)) setRegenOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [regenOpen]);

  function processCitations(children) {
    const nodes = Array.isArray(children) ? children : [children];
    return nodes.flatMap((child, ci) => {
      if (typeof child !== 'string') return [child];
      // Match [N] (page) and [W1],[W2] (web) citations
      const parts = child.split(/(?<!\])(\[(?:\d+|W\d+)\])(?!\[)/);
      return parts.map((part, i) => {
        const pageM = part.match(/^\[(\d+)\]$/);
        if (pageM) {
          const n = Number(pageM[1]);
          return (
            <button
              key={`${ci}-${i}`}
              onClick={() => onCiteClick && onCiteClick(n)}
              className="inline-flex items-center justify-center w-4 h-4 rounded text-[10px] font-semibold bg-indigo-100 text-indigo-600 hover:bg-indigo-200 cursor-pointer align-super mx-0.5"
            >
              {n}
            </button>
          );
        }
        const webM = part.match(/^\[W(\d+)\]$/);
        if (webM) {
          const wn = Number(webM[1]);
          return (
            <button
              key={`${ci}-${i}`}
              onClick={() => onCiteClick && onCiteClick(`W${wn}`)}
              className="inline-flex items-center justify-center px-1 h-4 rounded text-[10px] font-semibold bg-teal-100 text-teal-700 hover:bg-teal-200 cursor-pointer align-super mx-0.5"
            >
              W{wn}
            </button>
          );
        }
        return part;
      });
    });
  }

  function renderContent(content) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={{
          p: ({ children }) => (
            <p className="mt-1 first:mt-0">
              {onCiteClick ? processCitations(children) : children}
            </p>
          ),
          strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
          ol: ({ children }) => <ol className="list-decimal list-outside ml-5 mt-1 space-y-0.5">{children}</ol>,
          ul: ({ children }) => <ul className="list-disc list-outside ml-5 mt-1 space-y-0.5">{children}</ul>,
          li: ({ children }) => <li className="mt-0.5">{onCiteClick ? processCitations(children) : children}</li>,
          code: ({ inline, children }) => inline
            ? <code className="bg-gray-100 text-indigo-700 rounded px-1 py-0.5 text-xs font-mono">{children}</code>
            : <pre className="bg-gray-100 rounded-lg p-3 mt-2 overflow-x-auto text-xs font-mono">{children}</pre>,
          table: ({ children }) => (
            <div className="overflow-x-auto mt-2 mb-1">
              <table className="w-full text-xs border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-100 text-gray-700">{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr className="border-b border-gray-200">{children}</tr>,
          th: ({ children }) => <th className="px-3 py-1.5 text-left font-semibold border border-gray-200">{children}</th>,
          td: ({ children }) => <td className="px-3 py-1.5 border border-gray-200">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    );
  }

  async function handleCopy() {
    if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(msg.content || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Ignore clipboard failures; keep UI responsive.
    }
  }

  function formatEditTime(raw) {
    return formatDateTime(raw);
  }

  if (isUser) {
    return (
      <div className="group flex items-start gap-3">
        {userPicture ? (
          <img src={userPicture} alt="You" className="w-7 h-7 rounded-full border border-gray-200 flex-shrink-0 mt-0.5" />
        ) : (
          <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
            U
          </div>
        )}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="space-y-2">
              <textarea
                autoFocus
                value={editingContent}
                onChange={(e) => onEditChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    onEditSave();
                  } else if (e.key === 'Escape') {
                    e.preventDefault();
                    onEditCancel();
                  }
                }}
                onPaste={(e) => {
                  const items = Array.from(e.clipboardData?.items || []);
                  const imageItems = items.filter((it) => it.type.startsWith('image/'));
                  if (imageItems.length === 0) return;
                  e.preventDefault();
                  onEditImageAdd?.(imageItems.map((it) => it.getAsFile()).filter(Boolean));
                }}
                rows={3}
                className="w-full rounded-lg border border-indigo-200 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 text-sm text-gray-800 leading-relaxed px-3 py-2 resize-y"
              />
              {editImages.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {editImages.map((entry, idx) => {
                    const src = entry.kind === 'existing' ? entry.url : URL.createObjectURL(entry.file);
                    const name = entry.kind === 'existing' ? entry.filename : entry.file.name;
                    return (
                      <div key={idx} className="relative flex flex-col items-center gap-0.5">
                        <div className="w-14 h-14 rounded-lg overflow-hidden border border-gray-200 bg-gray-50 flex-shrink-0">
                          <img src={src} alt={name} className="w-full h-full object-cover" />
                        </div>
                        <span className="text-[9px] text-gray-400 max-w-[56px] truncate">{name}</span>
                        <button
                          type="button"
                          onClick={() => onEditImageRemove?.(idx)}
                          className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-gray-600 text-white flex items-center justify-center hover:bg-red-500 transition-colors"
                        >
                          <XIcon />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              <input
                ref={editFileInputRef}
                type="file"
                accept="image/png,image/jpeg"
                multiple
                className="hidden"
                onChange={(e) => { onEditImageAdd?.(e.target.files); e.target.value = ''; }}
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onEditSave}
                  className="px-2.5 py-1 text-xs rounded-md bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={onEditCancel}
                  className="px-2.5 py-1 text-xs rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => editFileInputRef?.current?.click()}
                  className="p-1 rounded text-gray-300 hover:text-indigo-500 hover:bg-indigo-50 transition-colors"
                  title="Attach image"
                >
                  <PaperclipIcon />
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {msg._inflightImages?.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-1">
                  {msg._inflightImages.map((img, i) => (
                    <div key={i} className="relative flex flex-col items-center gap-0.5">
                      <div
                        className={`relative w-14 h-14 rounded-lg overflow-hidden border border-gray-200 bg-gray-50 flex-shrink-0 ${!msg._isTemp ? 'cursor-pointer' : ''}`}
                        onClick={!msg._isTemp ? () => window.open(img.objectUrl, '_blank') : undefined}
                      >
                        <img src={img.objectUrl} alt={img.filename} className="w-full h-full object-cover" />
                        {msg._isTemp && (
                          <div className="absolute inset-0 bg-white/70 flex items-center justify-center">
                            <SpinnerIcon />
                          </div>
                        )}
                      </div>
                      <span className="text-[9px] text-gray-400 max-w-[56px] truncate">{img.filename}</span>
                    </div>
                  ))}
                </div>
              )}
              {!msg._inflightImages?.length && msg.image_download_urls?.length > 0 && (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
                  <span className="text-gray-400 flex-shrink-0"><PaperclipIcon /></span>
                  {msg.image_download_urls.map((img, i) => (
                    <a
                      key={i}
                      href={img.url}
                      download={img.filename}
                      className="text-[11px] text-gray-400 hover:text-indigo-500 truncate max-w-[160px]"
                    >
                      {img.filename}
                    </a>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2">
                <p className="text-sm text-gray-800 leading-relaxed">{msg.content}</p>
                {msg.is_edited && (
                  <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                    Edited
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={() => onEditStart(msg.id, msg.content)}
          disabled={!canEdit || isEditing}
          className="flex-shrink-0 mt-0.5 p-1.5 rounded-lg text-gray-300 hover:text-indigo-500 hover:bg-indigo-50 opacity-0 group-hover:opacity-100 transition-all"
          title="Edit message"
        >
          <EditIcon />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-start">
      <div className="w-10 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-indigo-600 uppercase tracking-wide">
            {courseName || 'CourseMate AI'}
          </span>
          {modelLabel ? (
            <>
              <span className="w-1 h-1 rounded-full bg-indigo-300" />
              <span className="text-xs text-gray-400">
                {modelLabel}
              </span>
            </>
          ) : (
            <span className="w-1 h-1 rounded-full bg-indigo-300" />
          )}
        </div>
        {msg._streaming && !msg.content && !msg._generationProposal && (
          <LiveStatusLine liveToolTrace={msg._liveToolTrace} materials={materials} />
        )}
        {!msg._generationProposal && <ToolTraceIndicator toolTrace={msg.tool_trace} materials={materials} />}
        {!msg._generationProposal && (
          <div className="text-sm text-gray-700 leading-relaxed space-y-0.5">
            {renderContent(msg.content)}
          </div>
        )}
        {msg._generationProposal && (
          <GenerationProposalCard
            proposal={msg._generationProposal}
            status={msg._proposalStatus}
            onBuild={onBuild}
            onRefine={onRefine}
          />
        )}
        {webSearchUrls && webSearchUrls.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {webSearchUrls.map((item, idx) => {
              let hostname = item.url;
              try { hostname = new URL(item.url).hostname.replace(/^www\./, ''); } catch {}
              return (
                <a
                  key={idx}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={item.title || item.url}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-teal-50 text-teal-700 border border-teal-200 hover:bg-teal-100 hover:border-teal-300 transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                  </svg>
                  {hostname}
                  <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                  </svg>
                </a>
              );
            })}
          </div>
        )}
        {isLastAssistantMsg && msg.is_clarification_request && !msg.clarification_skipped && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-xs font-medium text-amber-700 mb-1">Clarifying question</p>
            <p className="text-sm text-amber-900">{msg.clarification_question}</p>
            <button
              type="button"
              onClick={() => onSkipClarification && onSkipClarification()}
              className="mt-2 inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-amber-300 text-amber-700 bg-white hover:bg-amber-100 transition-colors"
            >
              Skip clarification
            </button>
          </div>
        )}
        {!msg._generationProposal && Array.isArray(msg.follow_ups) && msg.follow_ups.length > 0 && !(msg.is_clarification_request && !msg.clarification_skipped) && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {isLastAssistantMsg && msg.is_clarification_request && msg.clarification_skipped && (
              <p className="w-full text-xs text-gray-500 mb-0.5">Would you like to discuss any of these further?</p>
            )}
            {msg.follow_ups.map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onFollowUpClick && onFollowUpClick(q)}
                className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-indigo-200 text-indigo-600 bg-white hover:bg-indigo-50 hover:border-indigo-300 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-1 mt-3">
          {onPin && (
            <button
              type="button"
              onClick={onPin}
              className={`p-1.5 rounded-lg transition-colors ${isPinned ? 'text-indigo-600 bg-indigo-50' : 'text-gray-400 hover:text-indigo-600 hover:bg-indigo-50'}`}
              title={isPinned ? 'Unpin' : 'Pin response'}
            >
              <PinIcon filled={isPinned} />
            </button>
          )}
          <button
            type="button"
            onClick={handleCopy}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            title={copied ? 'Copied' : 'Copy'}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
          </button>
          <button type="button" className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors" title="More">
            <MoreIcon />
          </button>
          <div className="flex-1" />
          {onRegenerate && availableModels?.length > 0 && (
            <div className="relative" ref={regenRef}>
              <button
                type="button"
                onClick={() => { setRegenOpen((o) => !o); setRegenProvider(null); }}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors border border-gray-200 hover:border-indigo-200"
              >
                <RefreshIcon />
                Regenerate
              </button>
              {regenOpen && (
                <div className="absolute bottom-full right-0 mb-2 bg-gray-900 rounded-xl shadow-xl border border-gray-700/60 z-50 overflow-hidden min-w-[190px]">
                  {regenProvider === null ? (
                    /* Provider list */
                    <div className="py-1">
                      <p className="px-3 pt-1.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500">Choose model</p>
                      {availableModels.map((provider) => (
                        <button
                          key={provider}
                          type="button"
                          onClick={() => setRegenProvider(provider)}
                          className="w-full flex items-center justify-between px-3 py-2 text-[11px] text-left text-gray-300 hover:bg-gray-700/70 transition-colors"
                        >
                          <span>{MODEL_LABELS[provider] || provider}</span>
                          <ChevronDownIcon />
                        </button>
                      ))}
                    </div>
                  ) : (
                    /* Model list for selected provider */
                    <div className="py-1 max-h-52 overflow-y-auto">
                      <button
                        type="button"
                        onClick={() => setRegenProvider(null)}
                        className="w-full flex items-center gap-1.5 px-3 py-2 text-[11px] text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 transition-colors"
                      >
                        <span>←</span>
                        {MODEL_LABELS[regenProvider] || regenProvider}
                      </button>
                      <div className="border-t border-gray-700/50 my-0.5" />
                      {(PROVIDER_MODELS[regenProvider] || []).map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            setRegenOpen(false);
                            setRegenProvider(null);
                            onRegenerate(msg.id, regenProvider, m.id);
                          }}
                          className="w-full px-3 py-2 text-[11px] text-left text-gray-300 hover:bg-gray-700/70 transition-colors"
                        >
                          {m.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        {(replyHistory?.back?.length > 0 || replyHistory?.forward?.length > 0) && (
          <div className="flex items-center gap-2 mt-2">
            {replyHistory.back?.length > 0 && onRevert && (
              <button
                type="button"
                onClick={() => onRevert(msg.id)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-gray-500 hover:text-amber-600 hover:bg-amber-50 transition-colors border border-gray-200 hover:border-amber-200"
              >
                <RevertIcon />
                Revert response
              </button>
            )}
            {replyHistory.forward?.length > 0 && onRestore && (
              <button
                type="button"
                onClick={() => onRestore(msg.id)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-gray-500 hover:text-emerald-600 hover:bg-emerald-50 transition-colors border border-gray-200 hover:border-emerald-200"
              >
                <RestoreIcon />
                Restore response
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
