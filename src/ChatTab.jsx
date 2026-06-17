import { useState, useRef, useEffect } from 'react';
import { getMaterialUrl } from './utils/materialUtils';
import { composerGateState } from './utils/composerGate';
import { PROVIDER_MODELS, NON_VISION_MODEL_IDS } from './modelCatalog.js';
import SearchChat from './SearchChat';

import {
  PlusIcon, SparkleIcon,
  ExternalLinkIcon, XIcon,
} from './ChatTab/icons';
import { FileTypeBadge, MaterialToggle } from './ChatTab/atoms';
import { groupChatsByDate, MODEL_LABELS } from './ChatTab/helpers';
import { ConvItem, ArchivedConvItem } from './ChatTab/ConversationList';
import { SourcesPanel } from './ChatTab/SourcesPanel';
import { PinsPanel } from './ChatTab/PinsPanel';
import { Composer } from './ChatTab/Composer';
import MessageBubble from './ChatTab/MessageBubble';

// PROVIDER_MODELS lives in ./modelCatalog.js; re-exported here for existing
// importers (e.g. CoursePage) that pull it from this module.
export { PROVIDER_MODELS };

// ─── main component ───────────────────────────────────────────────────────────

/** Max height (px) for the composer textarea before it scrolls internally. */
const CHAT_COMPOSER_MAX_HEIGHT_PX = 280;
/** Min height (px) — matches the send row (~h-6) so single-line text isn’t short vs controls. */
const CHAT_COMPOSER_MIN_HEIGHT_PX = 24;

function enrichMessageWithProposal(msg) {
  if (msg.role !== 'assistant' || msg._generationProposal) return msg;
  const trace = Array.isArray(msg.tool_trace) ? msg.tool_trace : [];
  const entry = trace.find((t) => t.tool === 'propose_generation');
  if (!entry) return msg;
  const args = entry.args || {};
  return {
    ...msg,
    _generationProposal: {
      generation_type: args.generation_type || '',
      title: args.title || '',
      discussion_summary: args.discussion_summary || '',
      material_ids: Array.isArray(args.material_ids) ? args.material_ids : [],
      params: args.params || {},
    },
  };
}

export default function ChatTab({ course, userData, onAddSource, onGoToTab }) {
  const [activeConv, setActiveConv] = useState(null);
  const [chats, setChats] = useState([]);
  const [chatsLoading, setChatsLoading] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [pendingScrollMessageId, setPendingScrollMessageId] = useState(null);
  const [highlightMessageId, setHighlightMessageId] = useState(null);
  const [archivedChats, setArchivedChats] = useState([]);
  const [archivedOpen, setArchivedOpen] = useState(false);
  const [archivedLoading, setArchivedLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [promptLibOpen, setPromptLibOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(
    () => localStorage.getItem('chat_web_search_enabled') === '1'
  );

  function toggleWebSearch() {
    setWebSearchEnabled((v) => {
      const next = !v;
      localStorage.setItem('chat_web_search_enabled', next ? '1' : '0');
      return next;
    });
  }
  const [selectedModel, setSelectedModel] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [keysLoaded, setKeysLoaded] = useState(false);
  const gate = composerGateState(availableModels, keysLoaded);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [selectedModelId, setSelectedModelId] = useState(null);
  const [modelListDropdownOpen, setModelListDropdownOpen] = useState(false);
  const [switchBanner, setSwitchBanner] = useState('');
  const [pinnedResponses, setPinnedResponses] = useState([]);
  const [pinToast, setPinToast] = useState('');
  const pinToastTimerRef = useRef(null);
  const [materials, setMaterials] = useState([]);
  const [materialsLoading, setMaterialsLoading] = useState(true);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState('');
  const [titleSaving, setTitleSaving] = useState(false);
  const [editingMsgId, setEditingMsgId] = useState(null);
  const [editingContent, setEditingContent] = useState('');
  const [msgChunks, setMsgChunks] = useState({});
  const [sourcesPanel, setSourcesPanel] = useState({ open: false, messageId: null, focusIndex: null });
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const h = Math.min(
      Math.max(el.scrollHeight, CHAT_COMPOSER_MIN_HEIGHT_PX),
      CHAT_COMPOSER_MAX_HEIGHT_PX,
    );
    el.style.height = `${h}px`;
  }, [input]);
  const dropdownRef = useRef(null);
  const modelListDropdownRef = useRef(null);
  const titleInputRef = useRef(null);
  const bannerTimerRef = useRef(null);
  const sendingRef = useRef(false);
  const [images, setImages] = useState([]);
  const [imageUploadStates, setImageUploadStates] = useState({});
  const [visionBanner, setVisionBanner] = useState('');
  const fileInputRef = useRef(null);
  // Edit-mode image staging: { kind: 'existing', s3_key, filename, url } | { kind: 'new', file: File }
  const [editImages, setEditImages] = useState([]);
  const editFileInputRef = useRef(null);

  // Sidebar resize / collapse
  const SIDEBAR_DEFAULT_WIDTH = 280;
  const SIDEBAR_MIN_WIDTH = 220;
  const SIDEBAR_MAX_WIDTH = 360;
  const SIDEBAR_COLLAPSE_THRESHOLD = 160;
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const sidebarLastExpandedWidthRef = useRef(SIDEBAR_DEFAULT_WIDTH);
  const sidebarIsDraggingRef = useRef(false);
  const sidebarDragStartXRef = useRef(0);
  const sidebarDragStartWidthRef = useRef(SIDEBAR_DEFAULT_WIDTH);

  function handleSidebarRestore() {
    setSidebarCollapsed(false);
    // Restore in two steps: snap to min width then animate to last width
    const target = Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, sidebarLastExpandedWidthRef.current || SIDEBAR_DEFAULT_WIDTH));
    setSidebarWidth(SIDEBAR_MIN_WIDTH);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setSidebarWidth(target));
    });
  }

  function startSidebarDrag(e) {
    e.preventDefault();
    e.stopPropagation();
    sidebarIsDraggingRef.current = true;
    sidebarDragStartXRef.current = e.clientX;
    sidebarDragStartWidthRef.current = sidebarWidth;

    const onMove = (ev) => {
      if (!sidebarIsDraggingRef.current) return;
      const dx = ev.clientX - sidebarDragStartXRef.current;
      const next = sidebarDragStartWidthRef.current + dx;

      if (next <= SIDEBAR_COLLAPSE_THRESHOLD) {
        setSidebarCollapsed(true);
        return;
      }

      setSidebarCollapsed(false);
      const clamped = Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, next));
      sidebarLastExpandedWidthRef.current = clamped;
      setSidebarWidth(clamped);
    };

    const onUp = () => {
      sidebarIsDraggingRef.current = false;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);

      // If we ended collapsed, remember last expanded width and hide sidebar
      if (sidebarCollapsed) {
        sidebarLastExpandedWidthRef.current = Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, sidebarWidth));
      }
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!pendingScrollMessageId || !messages.length) return;
    const el = document.getElementById(`msg-${pendingScrollMessageId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setHighlightMessageId(pendingScrollMessageId);
      const t = setTimeout(() => setHighlightMessageId(null), 2000);
      setPendingScrollMessageId(null);
      return () => clearTimeout(t);
    }
    setPendingScrollMessageId(null);
  }, [pendingScrollMessageId, messages]);

  // Load materials for this course
  useEffect(() => {
    if (!course?.id) return;
    setMaterialsLoading(true);
    fetch(`/api/material?action=selections&course_id=${course.id}&context=chat`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setMaterials(Array.isArray(data) ? data : (data.materials || [])))
      .catch(() => {})
      .finally(() => setMaterialsLoading(false));
  }, [course?.id]);

  // Load chats for this course
  useEffect(() => {
    if (!course?.id) return;
    setChatsLoading(true);
    fetch(`/api/chat?resource=chat&course_id=${course.id}`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setChats(data.chats || []))
      .catch(() => {})
      .finally(() => setChatsLoading(false));
  }, [course?.id]);

  // Load pinned responses for this course
  useEffect(() => {
    if (!course?.id) return;
    fetch(`/api/chat?resource=pin&course_id=${course.id}`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => setPinnedResponses(data.pins || []))
      .catch(() => {});
  }, [course?.id]);

  // Fetch archived chats when the archived dropdown is opened
  useEffect(() => {
    if (!archivedOpen || !course?.id) return;
    setArchivedLoading(true);
    fetch(`/api/chat?resource=chat&course_id=${course.id}&archived=true`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setArchivedChats(data.chats || []))
      .catch(() => {})
      .finally(() => setArchivedLoading(false));
  }, [archivedOpen, course?.id]);

  // Load messages when active conversation changes
  useEffect(() => {
    if (!activeConv || activeConv === '__new__') return;
    if (sendingRef.current) return;
    fetch(`/api/chat?resource=message&chat_id=${activeConv}`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => setMessages((data.messages || []).map(enrichMessageWithProposal)))
      .catch(() => {});
  }, [activeConv]);

  // Load available API-key-backed models
  useEffect(() => {
    fetch('/api/user?resource=api_keys', {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data) => {
        const available = Object.entries(data)
          .filter(([, hasKey]) => hasKey)
          .map(([provider]) => provider);
        setAvailableModels(available);
        if (available.length > 0) {
          const savedProvider = course?.default_ai_provider || localStorage.getItem('chat_selected_provider');
          const savedModelId = course?.default_ai_model || localStorage.getItem('chat_selected_model_id');
          const provider = available.includes(savedProvider) ? savedProvider : available[0];
          const modelList = PROVIDER_MODELS[provider] ?? [];
          const modelId = modelList.find((m) => m.id === savedModelId)?.id ?? modelList[0]?.id ?? null;
          setSelectedModel(provider);
          setSelectedModelId(modelId);
        }
      })
      .catch(() => {})
      .finally(() => setKeysLoaded(true));
  }, [course?.default_ai_provider, course?.default_ai_model]);

  useEffect(() => {
    if (!modelDropdownOpen) return;
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setModelDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [modelDropdownOpen]);

  useEffect(() => {
    if (!modelListDropdownOpen) return;
    function handleClickOutside(e) {
      if (modelListDropdownRef.current && !modelListDropdownRef.current.contains(e.target)) {
        setModelListDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [modelListDropdownOpen]);

  function handleModelSelect(provider) {
    setSelectedModel(provider);
    setModelDropdownOpen(false);
    const modelId = PROVIDER_MODELS[provider]?.[0]?.id ?? null;
    setSelectedModelId(modelId);
    localStorage.setItem('chat_selected_provider', provider);
    if (modelId) localStorage.setItem('chat_selected_model_id', modelId);
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    setSwitchBanner(MODEL_LABELS[provider] || provider);
    bannerTimerRef.current = setTimeout(() => setSwitchBanner(''), 2500);
  }

  function handleModelIdSelect(modelId) {
    setSelectedModelId(modelId);
    setModelListDropdownOpen(false);
    localStorage.setItem('chat_selected_model_id', modelId);
  }

  async function persistMaterialSelection(material, selected) {
    if (!course?.id || !material?.id) return;
    try {
      await fetch('/api/material', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          action: 'set_selection',
          material_id: material.id,
          course_id: course.id,
          context: 'chat',
          selected,
          provider: material.source_type === 'notion' ? 'notion' : null,
        }),
      });
    } catch {}
  }

  function handleSelectAllMaterials() {
    const allOn = materials.length > 0 && materials.every((m) => m.selected);
    const newVal = !allOn;
    const nextMaterials = materials.map((m) => ({ ...m, selected: newVal }));
    setMaterials(nextMaterials);
    nextMaterials.forEach((m) => {
      persistMaterialSelection(m, newVal);
    });
  }

  function setAllMaterialsSelected(selected) {
    const nextMaterials = materials.map((m) => ({ ...m, selected }));
    setMaterials(nextMaterials);
    nextMaterials.forEach((m) => {
      persistMaterialSelection(m, selected);
    });
  }

  function handleToggleMaterial(id) {
    setMaterials((prev) => prev.map((m) => {
      if (m.id !== id) return m;
      const updated = { ...m, selected: !m.selected };
      persistMaterialSelection(m, updated.selected);
      return updated;
    }));
  }

  function handleOpenMaterial(m) {
    const url = getMaterialUrl(m);
    if (!url) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  function handleNewChat() {
    // Remove any stale temp entry then add a fresh optimistic one
    setChats((prev) => [
      { id: '__new__', title: 'New Chat', course_id: course?.id, message_count: 0, last_message_at: null, created_at: new Date().toISOString(), is_archived: false },
      ...prev.filter((c) => c.id !== '__new__'),
    ]);
    setActiveConv('__new__');
    setMessages([]);
    setInput('');
  }

  async function handleArchiveChat(chatId, isArchived) {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ resource: 'chat', action: 'archive', chat_id: chatId, is_archived: isArchived }),
      });
      if (!res.ok) return;
      const archived = chats.find((c) => c.id === chatId);
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (archived) setArchivedChats((prev) => [{ ...archived, is_archived: true }, ...prev]);
      if (activeConv === chatId) { setActiveConv(null); setMessages([]); }
    } catch {}
  }

  async function handleUnarchiveChat(chatId) {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ resource: 'chat', action: 'archive', chat_id: chatId, is_archived: false }),
      });
      if (!res.ok) return;
      const unarchived = archivedChats.find((c) => c.id === chatId);
      setArchivedChats((prev) => prev.filter((c) => c.id !== chatId));
      if (unarchived) setChats((prev) => [{ ...unarchived, is_archived: false }, ...prev]);
    } catch {}
  }

  async function handleDeleteArchivedChat(chatId) {
    try {
      const res = await fetch('/api/chat', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ resource: 'chat', chat_id: chatId }),
      });
      if (!res.ok) return;
      setArchivedChats((prev) => prev.filter((c) => c.id !== chatId));
    } catch {}
  }

  async function handleClearAll() {
    if (!course?.id) return;
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ resource: 'chat', action: 'archive_all', course_id: course.id }),
      });
      if (!res.ok) return;
      setChats([]);
      setActiveConv(null);
      setMessages([]);
    } catch {}
  }

  function handleConvSelect(chatId, target) {
    const id = typeof chatId === 'object' ? chatId?.id : chatId;
    setActiveConv(id);
    setMessages([]);
    setEditingTitle(false);
    setPendingScrollMessageId(target?.messageId ?? null);
  }

  async function handleDeletePin(pin) {
    try {
      const r = await fetch('/api/chat', {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resource: 'pin', assistant_message_id: pin.assistant_message_id }),
      });
      if (!r.ok) return;
      setPinnedResponses((prev) => prev.filter((p) => p.assistant_message_id !== pin.assistant_message_id));
    } catch {
      // ignore network errors
    }
  }

  async function handlePinMessage(assistantMsg, userMsg) {
    const isCurrentlyPinned = pinnedResponses.some((p) => p.assistant_message_id === assistantMsg.id);
    const action = isCurrentlyPinned ? 'unpin' : 'pin';

    setPinToast(action === 'pin' ? 'Saving…' : 'Pin removed');
    if (pinToastTimerRef.current) clearTimeout(pinToastTimerRef.current);
    pinToastTimerRef.current = setTimeout(() => setPinToast(''), 1500);

    const body = action === 'pin'
      ? { resource: 'pin', action: 'pin', user_message_id: userMsg.id, assistant_message_id: assistantMsg.id, course_id: course.id, chat_id: activeConv }
      : { resource: 'pin', action: 'unpin', assistant_message_id: assistantMsg.id };

    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) return;
      const responseData = await r.json();
      if (action === 'pin' && responseData.pin) {
        const chatTitle = chats.find((c) => c.id === activeConv)?.title || 'Chat';
        setPinnedResponses((prev) => [
          {
            id: responseData.pin?.id,
            user_message_id: userMsg.id,
            assistant_message_id: assistantMsg.id,
            course_id: course.id,
            chat_id: activeConv,
            ai_summary: assistantMsg.summary || '',
            pinned_at: responseData.pin?.pinned_at,
            chat_title: chatTitle,
            user_message: userMsg,
            assistant_message: assistantMsg,
          },
          ...prev,
        ]);
      } else if (responseData.deleted) {
        setPinnedResponses((prev) => prev.filter((p) => p.assistant_message_id !== assistantMsg.id));
      }
    } catch {}
  }

  function handleConvDoubleClick(conv) {
    setActiveConv(conv.id);
    setMessages([]);
    setTitleValue(conv.title || '');
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 0);
  }

  function handleTitleDoubleClick() {
    const chat = chats.find((c) => c.id === activeConv);
    if (!chat || activeConv === '__new__') return;
    setTitleValue(chat.title || '');
    setEditingTitle(true);
    setTimeout(() => titleInputRef.current?.select(), 0);
  }

  async function handleTitleSave() {
    const trimmed = titleValue.trim();
    if (!trimmed || !activeConv || activeConv === '__new__') {
      setEditingTitle(false);
      return;
    }
    const chat = chats.find((c) => c.id === activeConv);
    if (chat && trimmed === chat.title) {
      setEditingTitle(false);
      return;
    }
    setTitleSaving(true);
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ resource: 'chat', action: 'update', chat_id: activeConv, title: trimmed }),
      });
      const data = await res.json();
      if (res.ok && data.chat) {
        setChats((prev) => prev.map((c) => c.id === activeConv ? { ...c, title: data.chat.title } : c));
      }
    } catch {}
    setTitleSaving(false);
    setEditingTitle(false);
  }

  function handleTitleKeyDown(e) {
    if (e.key === 'Enter') { e.preventDefault(); handleTitleSave(); }
    if (e.key === 'Escape') { setEditingTitle(false); }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey && gate.canSend) {
      e.preventDefault();
      handleSend();
    }
  }

  function resolveWebFocusIndex(chunks, focusIndex) {
    if (typeof focusIndex !== 'string' || !/^W\d+$/.test(focusIndex)) return focusIndex;
    const pageCount = (chunks || []).filter((c) => c.citation_type === 'page').length;
    return pageCount + Number(focusIndex.slice(1));
  }

  function openSources(messageId, focusIndex) {
    if (!msgChunks[messageId]) {
      fetch(`/api/chat?resource=chunks&message_id=${messageId}`, {
        credentials: 'include',
      })
        .then((r) => r.json())
        .then((data) => {
          const chunks = data.chunks || [];
          setMsgChunks((prev) => ({ ...prev, [messageId]: chunks }));
          setSourcesPanel({ open: true, messageId, focusIndex: resolveWebFocusIndex(chunks, focusIndex) });
        })
        .catch(() => {});
      return;
    }
    setSourcesPanel({ open: true, messageId, focusIndex: resolveWebFocusIndex(msgChunks[messageId], focusIndex) });
  }

  function handleStreamEvent(evt, { tempId, tempAssistantId, chatId, setActiveConvFn }) {
    switch (evt.type) {
      case 'user_message':
        setMessages((prev) => {
          const temp = prev.find((m) => m.id === tempId);
          const enriched = temp?._inflightImages ? { ...evt.message, _inflightImages: temp._inflightImages, _isTemp: true } : evt.message;
          return [
            ...prev.filter((m) => m.id !== tempId),
            enriched,
            { id: tempAssistantId, role: 'assistant', content: '', _streaming: true },
          ];
        });
        break;
      case 'tool_call':
        setMessages((prev) => {
          const entry = { tool: evt.tool, args: { material_id: evt.material_id, pages: evt.pages } };
          const existing = prev.find((m) => m.id === tempAssistantId);
          if (existing) {
            return prev.map((m) =>
              m.id === tempAssistantId
                ? { ...m, _liveToolTrace: [...(m._liveToolTrace || []), entry] }
                : m
            );
          }
          return [...prev, { id: tempAssistantId, role: 'assistant', content: '', _streaming: true, _liveToolTrace: [entry] }];
        });
        break;
      case 'web_search_start':
        setMessages((prev) => {
          const entry = { tool: 'web_search', args: { query: evt.query } };
          const existing = prev.find((m) => m.id === tempAssistantId);
          if (existing) {
            return prev.map((m) =>
              m.id === tempAssistantId
                ? { ...m, _liveToolTrace: [...(m._liveToolTrace || []), entry] }
                : m
            );
          }
          return [...prev, { id: tempAssistantId, role: 'assistant', content: '', _streaming: true, _liveToolTrace: [entry] }];
        });
        break;
      case 'web_url_view':
        setMessages((prev) => {
          const entry = { tool: 'web_url_view', args: { url: evt.url } };
          const existing = prev.find((m) => m.id === tempAssistantId);
          if (existing) {
            return prev.map((m) =>
              m.id === tempAssistantId
                ? { ...m, _liveToolTrace: [...(m._liveToolTrace || []), entry] }
                : m
            );
          }
          return [...prev, { id: tempAssistantId, role: 'assistant', content: '', _streaming: true, _liveToolTrace: [entry] }];
        });
        break;
      case 'text':
        if (!evt.chunk) break;
        setMessages((prev) => {
          const existing = prev.find((m) => m.id === tempAssistantId);
          if (existing) {
            return prev.map((m) =>
              m.id === tempAssistantId ? { ...m, content: m.content + evt.chunk } : m
            );
          }
          return [...prev, { id: tempAssistantId, role: 'assistant', content: evt.chunk }];
        });
        break;
      case 'done':
        setMessages((prev) => {
          const prevUserMsg = prev.find((m) => m.id === tempId || m.id === evt.user_message?.id);
          const prevAssistantMsg = prev.find((m) => m.id === tempAssistantId);
          const enrichedUser = prevUserMsg?._inflightImages
            ? { ...evt.user_message, _inflightImages: prevUserMsg._inflightImages }
            : evt.user_message;
          const withoutTemp = prev.filter(
            (m) => m.id !== tempId && m.id !== tempAssistantId && m.id !== evt.user_message?.id
          );
          const finalAssistant = prevAssistantMsg?._generationProposal
            ? { ...evt.assistant_message, _generationProposal: prevAssistantMsg._generationProposal }
            : evt.assistant_message;
          return [...withoutTemp, enrichedUser, finalAssistant];
        });
        setChats((prev) => prev.map((c) =>
          c.id === chatId
            ? {
                ...c,
                last_message_at: evt.assistant_message?.created_at,
                message_count: (c.message_count || 0) + 2,
                ...(evt.suggested_title ? { title: evt.suggested_title } : {}),
              }
            : c
        ));
        setSending(false);
        sendingRef.current = false;
        break;
      case 'error':
        console.error('[SSE error]', evt);
        setSending(false);
        sendingRef.current = false;
        setMessages((prev) => prev.filter((m) => m.id !== tempId && m.id !== tempAssistantId));
        break;
      case 'generation_proposal':
        setMessages((prev) => {
          const existing = prev.find((m) => m.id === tempAssistantId);
          if (existing) {
            return prev.map((m) =>
              m.id === tempAssistantId ? { ...m, _generationProposal: evt } : m
            );
          }
          return [...prev, { id: tempAssistantId, role: 'assistant', content: '', _streaming: true, _generationProposal: evt }];
        });
        break;
      default:
        break;
    }
  }

  function addImages(files) {
    const MAX_SIZE = 10 * 1024 * 1024;
    const MAX_COUNT = 5;
    setImages((prev) => {
      const valid = Array.from(files).filter((f) => f.size <= MAX_SIZE);
      const combined = [...prev, ...valid];
      return combined.slice(0, MAX_COUNT);
    });
  }

  function removeImage(index) {
    setImages((prev) => prev.filter((_, i) => i !== index));
    setImageUploadStates((prev) => {
      const next = { ...prev };
      delete next[index];
      return next;
    });
  }

  function addEditImages(files) {
    const MAX_SIZE = 10 * 1024 * 1024;
    const MAX_COUNT = 5;
    setEditImages((prev) => {
      const valid = Array.from(files)
        .filter((f) => f.size <= MAX_SIZE)
        .map((f) => ({ kind: 'new', file: f }));
      return [...prev, ...valid].slice(0, MAX_COUNT);
    });
  }

  function removeEditImage(index) {
    setEditImages((prev) => prev.filter((_, i) => i !== index));
  }

  function handleFileInputChange(e) {
    addImages(e.target.files);
    e.target.value = '';
  }

  function handlePaste(e) {
    const items = Array.from(e.clipboardData?.items || []);
    const imageItems = items.filter((it) => it.type.startsWith('image/'));
    if (imageItems.length === 0) return;
    e.preventDefault();
    const files = imageItems.map((it) => it.getAsFile()).filter(Boolean);
    addImages(files);
  }

  const ENDPOINT_BY_TYPE = { quiz: '/api/quiz', flashcards: '/api/flashcards', report: '/api/reports' };

  function handleRefineGeneration(msg) {
    const p = msg._generationProposal;
    if (!p || !onGoToTab) return;
    const tabId = p.generation_type === 'report' ? 'reports' : p.generation_type;
    const materialIds = Array.isArray(p.material_ids) && p.material_ids.length > 0 ? p.material_ids : null;
    try {
      if (tabId === 'quiz') {
        const stored = JSON.parse(localStorage.getItem(`quiz_fields_${course.id}`) || '{}');
        localStorage.setItem(`quiz_fields_${course.id}`, JSON.stringify({
          ...stored, topic: p.title, ...(materialIds ? { material_ids: materialIds } : {}),
        }));
      } else if (tabId === 'flashcards') {
        const stored = JSON.parse(localStorage.getItem(`flashcards_fields_${course.id}`) || '{}');
        const cardCount = Number(p.params?.card_count ?? p.params?.num_cards ?? 0);
        localStorage.setItem(`flashcards_fields_${course.id}`, JSON.stringify({
          ...stored, topic: p.title,
          ...(cardCount > 0 ? { card_count: cardCount } : {}),
          ...(materialIds ? { material_ids: materialIds } : {}),
        }));
      } else if (tabId === 'reports') {
        const stored = JSON.parse(localStorage.getItem(`reports_fields_${course.id}`) || '{}');
        const tpl = normalizeReportTemplate(p.params?.template_id ?? p.params?.template);
        const isCustomTpl = tpl === 'custom';
        localStorage.setItem(`reports_fields_${course.id}`, JSON.stringify({
          ...stored,
          template: tpl,
          ...(isCustomTpl ? { customPrompt: p.params?.custom_prompt || p.title } : {}),
          ...(materialIds ? { material_ids: materialIds } : {}),
        }));
      }
      localStorage.setItem(`coursemate_generations_tab_${course.id}`, tabId);
    } catch {}
    onGoToTab('generate');
  }

  const VALID_REPORT_TEMPLATES = ['study-guide', 'briefing', 'summary', 'custom'];

  function normalizeReportTemplate(raw) {
    const v = String(raw || 'study-guide').trim().replace(/_/g, '-').toLowerCase();
    return VALID_REPORT_TEMPLATES.includes(v) ? v : 'study-guide';
  }

  // All generation types use the estimate → generate (async SQS) two-step flow.
  async function queueProposalGeneration(p) {
    const endpoint = ENDPOINT_BY_TYPE[p.generation_type];
    if (!endpoint) throw new Error('unknown generation type');
    const provider = selectedModel;
    const model_id = selectedModelId || selectedModel;
    const conversation_context = p.discussion_summary;
    const material_ids = p.material_ids;

    const estimateBody = {
      action: 'estimate',
      course_id: course.id,
      topic: p.title,
      material_ids,
      conversation_context,
      provider,
      model_id,
    };
    if (p.generation_type === 'quiz') {
      const tf = Number(p.params?.tf_count ?? 0);
      const sa = Number(p.params?.sa_count ?? 0);
      const la = Number(p.params?.la_count ?? 0);
      const mcq = Number(p.params?.mcq_count ?? p.params?.question_count ?? 0);
      estimateBody.tf_count = tf;
      estimateBody.sa_count = sa;
      estimateBody.la_count = la;
      estimateBody.mcq_count = mcq || (!tf && !sa && !la ? 10 : 0);
      estimateBody.mcq_options = Number(p.params?.mcq_options ?? 4);
    } else if (p.generation_type === 'flashcards') {
      estimateBody.card_count = Number(p.params?.card_count ?? p.params?.num_cards ?? 20);
    } else if (p.generation_type === 'report') {
      estimateBody.template_id = normalizeReportTemplate(p.params?.template_id ?? p.params?.template);
    }

    const estRes = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(estimateBody),
    });
    if (!estRes.ok) throw new Error('estimate failed');
    const estData = await estRes.json();
    const generationId = estData.generation_id;
    if (!generationId) throw new Error('no generation_id from estimate');

    const genRes = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        action: 'generate',
        generation_id: generationId,
        provider,
        model_id,
        conversation_context,
      }),
    });
    if (!genRes.ok) throw new Error('queue failed');
  }

  async function handleBuildGeneration(msg) {
    const p = msg._generationProposal;
    if (!p || !ENDPOINT_BY_TYPE[p.generation_type]) return;

    setMessages((prev) => prev.map((m) => m.id === msg.id ? { ...m, _proposalStatus: 'building' } : m));
    try {
      await queueProposalGeneration(p);
      setMessages((prev) => prev.map((m) => m.id === msg.id ? { ...m, _proposalStatus: 'queued' } : m));
    } catch (e) {
      setMessages((prev) => prev.map((m) => m.id === msg.id ? { ...m, _proposalStatus: null } : m));
    }
  }

  async function handleSend() {
    if (!gate.canSend) return;

    const text = input.trim();
    const hasImages = images.length > 0;
    if ((!text && !hasImages) || sending || !selectedModel) return;

    if (hasImages && NON_VISION_MODEL_IDS.has(selectedModelId || selectedModel)) {
      const modelEntry = (PROVIDER_MODELS[selectedModel] || []).find((m) => m.id === (selectedModelId || selectedModel));
      const label = modelEntry?.label || selectedModelId || selectedModel;
      setVisionBanner(`${label} does not support image inputs. Please select a different model.`);
      return;
    }

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setSending(true);
    sendingRef.current = true;

    const stagedImages = [...images];
    setImages([]);
    setImageUploadStates({});

    const tempId = Date.now();
    const tempAssistantId = tempId + 1;
    const tempUserMsg = {
      id: tempId,
      role: 'user',
      content: text,
      ...(stagedImages.length > 0 ? {
        _inflightImages: stagedImages.map((f) => ({ objectUrl: URL.createObjectURL(f), filename: f.name })),
        _isTemp: true,
      } : {}),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    let imageAttachments = [];
    try {
      if (stagedImages.length > 0) {
        const uploadResults = await Promise.all(
          stagedImages.map(async (file, idx) => {
            setImageUploadStates((prev) => ({ ...prev, [idx]: 'uploading' }));
            const buf = await file.arrayBuffer();
            const hashBuf = await crypto.subtle.digest('SHA-256', buf);
            const sha256 = Array.from(new Uint8Array(hashBuf))
              .map((b) => b.toString(16).padStart(2, '0'))
              .join('');
            const res = await fetch('/api/chat', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({
                resource: 'message',
                action: 'upload_image',
                filename: file.name,
                content_type: file.type,
                sha256,
              }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Upload failed');
            if (data.upload_url) {
              await fetch(data.upload_url, {
                method: 'PUT',
                headers: { 'Content-Type': file.type },
                body: file,
              });
            }
            setImageUploadStates((prev) => ({ ...prev, [idx]: 'done' }));
            return { s3_key: data.s3_key, filename: file.name };
          })
        );
        imageAttachments = uploadResults;
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
      setSending(false);
      sendingRef.current = false;
      setVisionBanner('Image upload failed. Please try again.');
      return;
    }

    try {
      let chatId = activeConv;

      // Create a chat thread if none exists or if this is the optimistic temp entry
      if (!chatId || chatId === '__new__') {
        const title = 'New Chat';
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify({ resource: 'chat', action: 'create', course_id: course.id, title }),
        });
        const chatData = await res.json();
        if (!res.ok) throw new Error(chatData.error || 'Failed to create chat');
        chatId = chatData.chat.id;
        setActiveConv(chatId);
        setChats((prev) => [chatData.chat, ...prev.filter((c) => c.id !== '__new__')]);
      }

      const contextIds = materials.filter((m) => m.selected).map((m) => m.id);

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          resource: 'message',
          action: 'stream_send',
          chat_id: chatId,
          content: text,
          context_material_ids: contextIds,
          ai_provider: selectedModel,
          ai_model: selectedModelId || selectedModel,
          web_search_enabled: webSearchEnabled,
          ...(imageAttachments.length > 0 ? { image_attachments: imageAttachments } : {}),
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to send message');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(part.slice(6));
            handleStreamEvent(evt, { tempId, tempAssistantId, chatId });
          } catch (e) { console.error('[SSE parse error]', e, part); }
        }
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleEditMessage(messageId, newContent) {
    const trimmed = (newContent || '').trim();
    if (!trimmed || sending || !selectedModel) return;
    const target = messages.find((m) => m.id === messageId);
    if (!target || target.role !== 'user' || typeof target.message_index !== 'number') return;

    const stagedEditImages = [...editImages];

    if (stagedEditImages.length > 0 && NON_VISION_MODEL_IDS.has(selectedModelId || selectedModel)) {
      const modelEntry = (PROVIDER_MODELS[selectedModel] || []).find((m) => m.id === (selectedModelId || selectedModel));
      const label = modelEntry?.label || selectedModelId || selectedModel;
      setVisionBanner(`${label} does not support image inputs. Please select a different model.`);
      return;
    }

    const contextIds = materials.filter((m) => m.selected).map((m) => m.id);

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const cutoffIndex = target.message_index;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < cutoffIndex);
    const optimisticEdited = { ...target, content: trimmed, is_edited: true };

    setEditingMsgId(null);
    setEditingContent('');
    setEditImages([]);
    setSending(true);
    sendingRef.current = true;
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });
    setMessages([...keptPrefix, optimisticEdited]);

    let imageAttachments = [];
    try {
      const newEntries = stagedEditImages.filter((e) => e.kind === 'new');
      const existingEntries = stagedEditImages.filter((e) => e.kind === 'existing');

      if (newEntries.length > 0) {
        const uploadResults = await Promise.all(
          newEntries.map(async ({ file }) => {
            const buf = await file.arrayBuffer();
            const hashBuf = await crypto.subtle.digest('SHA-256', buf);
            const sha256 = Array.from(new Uint8Array(hashBuf))
              .map((b) => b.toString(16).padStart(2, '0'))
              .join('');
            const res = await fetch('/api/chat', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({
                resource: 'message',
                action: 'upload_image',
                filename: file.name,
                content_type: file.type,
                sha256,
              }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Upload failed');
            if (data.upload_url) {
              await fetch(data.upload_url, {
                method: 'PUT',
                headers: { 'Content-Type': file.type },
                body: file,
              });
            }
            return { s3_key: data.s3_key, filename: file.name };
          })
        );
        imageAttachments = [
          ...existingEntries.map((e) => ({ s3_key: e.s3_key, filename: e.filename })),
          ...uploadResults,
        ];
      } else {
        imageAttachments = existingEntries.map((e) => ({ s3_key: e.s3_key, filename: e.filename }));
      }
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
      setSending(false);
      sendingRef.current = false;
      setVisionBanner('Image upload failed. Please try again.');
      return;
    }

    const existingUrlMap = Object.fromEntries(
      stagedEditImages.filter((e) => e.kind === 'existing').map((e) => [e.s3_key, e.url])
    );

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          resource: 'message',
          action: 'stream_edit',
          message_id: messageId,
          content: trimmed,
          context_material_ids: contextIds,
          ai_provider: selectedModel,
          ai_model: selectedModelId || selectedModel,
          web_search_enabled: webSearchEnabled,
          image_attachments: imageAttachments,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to edit message');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      let editDoneReceived = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(part.slice(6));
            if (evt.type === 'done') {
              editDoneReceived = true;
              const enrichedUserMessage = {
                ...evt.user_message,
                image_download_urls: imageAttachments.map((a) => ({
                  filename: a.filename,
                  url: existingUrlMap[a.s3_key] || '',
                })),
              };
              const nextMessages = [...keptPrefix, enrichedUserMessage, evt.assistant_message];
              setMessages(nextMessages);
              setMsgChunks((prev) => {
                const keptIds = new Set(nextMessages.map((m) => m.id));
                return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
              });
              setChats((prev) => prev.map((c) =>
                c.id === target.chat_id
                  ? {
                      ...c,
                      last_message_at: evt.assistant_message?.created_at,
                      message_count: nextMessages.length,
                      ...(evt.suggested_title ? { title: evt.suggested_title } : {}),
                    }
                  : c
              ));
              setSending(false);
              sendingRef.current = false;
            } else if (evt.type === 'error') {
              console.error('[SSE error] edit', evt);
              editDoneReceived = true;
              setMessages(prevMessages);
              setMsgChunks(prevMsgChunks);
              setSending(false);
              sendingRef.current = false;
            } else {
              handleStreamEvent(evt, { tempId: null, chatId: target.chat_id });
            }
          } catch (e) { console.error('[SSE parse error] edit', e, part); }
        }
      }
      if (!editDoneReceived) {
        setMessages(prevMessages);
        setMsgChunks(prevMsgChunks);
        setSending(false);
        sendingRef.current = false;
      }
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleRevertMessage(assistantMsgId) {
    if (sending) return;
    const assistantMsg = messages.find((m) => m.id === assistantMsgId);
    if (!assistantMsg) return;
    // Find the nearest user message before this assistant — don't assume contiguous indices
    const userMsg = messages
      .filter((m) => m.role === 'user' && m.message_index < assistantMsg.message_index)
      .sort((a, b) => b.message_index - a.message_index)[0];
    if (!userMsg) return;

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < userMsg.message_index);

    setSending(true);
    sendingRef.current = true;
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ resource: 'message', action: 'revert', message_id: assistantMsgId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to revert');

      const newAsst = data.assistant_message;
      const nextMessages = [...keptPrefix, data.user_message, newAsst];
      const displayedIds = new Set(nextMessages.map((m) => m.id));
      // Synchronously update pin state alongside messages so both render in the same pass.
      // Remove pins for messages no longer displayed; add a minimal entry if the new row is pinned.
      setPinnedResponses((prev) => {
        const kept = prev.filter((p) => displayedIds.has(p.assistant_message_id));
        return newAsst.is_pinned ? [...kept, { assistant_message_id: newAsst.id }] : kept;
      });
      setMessages(nextMessages);
      setMsgChunks((prev) => {
        const keptIds = new Set(nextMessages.map((m) => m.id));
        return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
      });
      // Background re-fetch replaces the minimal pin entry with the full object for PinsPanel.
      fetch(`/api/chat?resource=pin&course_id=${course.id}`, { credentials: 'include' })
        .then((r) => r.json())
        .then((d) => setPinnedResponses(d.pins || []))
        .catch(() => {});
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleRestoreMessage(assistantMsgId) {
    if (sending) return;
    const assistantMsg = messages.find((m) => m.id === assistantMsgId);
    if (!assistantMsg) return;
    const userMsg = messages
      .filter((m) => m.role === 'user' && m.message_index < assistantMsg.message_index)
      .sort((a, b) => b.message_index - a.message_index)[0];
    if (!userMsg) return;

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < userMsg.message_index);

    setSending(true);
    sendingRef.current = true;
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ resource: 'message', action: 'restore', message_id: assistantMsgId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to restore');

      const newAsst = data.assistant_message;
      const nextMessages = [...keptPrefix, data.user_message, newAsst];
      const displayedIds = new Set(nextMessages.map((m) => m.id));
      // Synchronously update pin state alongside messages so both render in the same pass.
      setPinnedResponses((prev) => {
        const kept = prev.filter((p) => displayedIds.has(p.assistant_message_id));
        return newAsst.is_pinned ? [...kept, { assistant_message_id: newAsst.id }] : kept;
      });
      setMessages(nextMessages);
      setMsgChunks((prev) => {
        const keptIds = new Set(nextMessages.map((m) => m.id));
        return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
      });
      // Background re-fetch replaces the minimal pin entry with the full object for PinsPanel.
      fetch(`/api/chat?resource=pin&course_id=${course.id}`, { credentials: 'include' })
        .then((r) => r.json())
        .then((d) => setPinnedResponses(d.pins || []))
        .catch(() => {});
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
    } finally {
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleRegenerateMessage(assistantMsgId, provider, modelId) {
    if (sending) return;
    const assistantMsg = messages.find((m) => m.id === assistantMsgId);
    if (!assistantMsg) return;
    const userMsg = messages
      .filter((m) => m.role === 'user' && m.message_index < assistantMsg.message_index)
      .sort((a, b) => b.message_index - a.message_index)[0];
    if (!userMsg) return;

    const prevMessages = messages;
    const prevMsgChunks = msgChunks;
    const keptPrefix = prevMessages.filter((m) => (m.message_index ?? Number.POSITIVE_INFINITY) < userMsg.message_index);

    setSending(true);
    sendingRef.current = true;
    setSourcesPanel({ open: false, messageId: null, focusIndex: null });
    setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: '', ai_provider: provider, ai_model: modelId, _streaming: true, _liveToolTrace: undefined } : m));

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          resource: 'message',
          action: 'stream_regenerate',
          message_id: assistantMsgId,
          ai_provider: provider,
          ai_model: modelId,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to regenerate');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      let regenDoneReceived = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(part.slice(6));
            if (evt.type === 'done') {
              regenDoneReceived = true;
              const nextMessages = [...keptPrefix, evt.user_message, evt.assistant_message];
              setMessages(nextMessages);
              setMsgChunks((prev) => {
                const keptIds = new Set(nextMessages.map((m) => m.id));
                return Object.fromEntries(Object.entries(prev).filter(([id]) => keptIds.has(Number(id))));
              });
              if (evt.suggested_title) {
                setChats((prev) => prev.map((c) =>
                  c.id === (userMsg.chat_id || assistantMsg.chat_id)
                    ? { ...c, title: evt.suggested_title }
                    : c
                ));
              }
              setSending(false);
              sendingRef.current = false;
            } else if (evt.type === 'error') {
              console.error('[SSE error] regen', evt);
              regenDoneReceived = true;
              setMessages(prevMessages);
              setMsgChunks(prevMsgChunks);
              setSending(false);
              sendingRef.current = false;
            } else {
              handleStreamEvent(evt, { tempId: null, tempAssistantId: assistantMsgId, chatId: userMsg.chat_id });
            }
          } catch {}
        }
      }
      if (!regenDoneReceived) {
        setMessages(prevMessages);
        setMsgChunks(prevMsgChunks);
        setSending(false);
        sendingRef.current = false;
      }
    } catch {
      setMessages(prevMessages);
      setMsgChunks(prevMsgChunks);
      setSending(false);
      sendingRef.current = false;
    }
  }

  async function handleSkipClarification(messageId) {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          resource: 'message',
          action: 'clarification_skip',
          message_id: messageId,
        }),
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.message) {
        setMessages((prev) =>
          prev.map((m) => (m.id === messageId ? { ...m, ...data.message } : m))
        );
      }
    } catch {
      // silently ignore
    }
  }

  const { today, lastWeek, older } = groupChatsByDate(chats);

  return (
    <div className="flex flex-col gap-4">
    <div className="relative flex gap-4" style={{ height: '68vh', minHeight: '520px' }}>

      {/* Switched-to banner — centred over the full modal */}
      {switchBanner && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-4 py-1.5 rounded-full bg-gray-900 text-white text-xs font-medium shadow-lg whitespace-nowrap pointer-events-none select-none">
          Switched to {switchBanner} ⚡
        </div>
      )}

      {/* Pin toast */}
      {pinToast && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-4 py-1.5 rounded-full bg-gray-900 text-white text-xs font-medium shadow-lg whitespace-nowrap pointer-events-none select-none">
          {pinToast}
        </div>
      )}

      {/* Vision model banner */}
      {visionBanner && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 px-4 py-1.5 rounded-full bg-red-600 text-white text-xs font-medium shadow-lg whitespace-nowrap select-none">
          <span>{visionBanner}</span>
          <button type="button" onClick={() => setVisionBanner('')} className="hover:opacity-70 transition-opacity">
            <XIcon />
          </button>
        </div>
      )}

      {/* ── Sidebar ── */}
      {!sidebarCollapsed ? (
        <div
          className={`flex-shrink-0 bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col overflow-hidden relative ${
            sidebarIsDraggingRef.current ? '' : 'transition-[width] duration-200'
          }`}
          style={{ width: sidebarWidth }}
        >
          {/* Drag handle (right edge) */}
          <div
            role="separator"
            aria-orientation="vertical"
            title="Drag to resize"
            onPointerDown={startSidebarDrag}
            className="absolute top-2 bottom-2 -right-2 w-4 cursor-col-resize z-20"
          >
            <div className="absolute right-2 top-0 bottom-0 w-px bg-gray-200" />
          </div>
        {/* Logo / title */}
        <div className="px-4 py-3 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-gray-900 text-sm">Course Chat</span>
            <button
              type="button"
              className="flex-shrink-0 p-1.5 text-gray-600 hover:text-indigo-600 hover:bg-gray-50 rounded-lg transition-colors"
              title="Search"
              onClick={() => setSearchOpen(true)}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </button>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={handleNewChat}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors shadow-sm"
            >
              <PlusIcon />
              New chat
            </button>
          </div>
        </div>

        {/* Scrollable middle: conversations + materials */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">

          {/* Conversations */}
          <div className="overflow-y-auto px-2 space-y-4 pb-3 shrink-0" style={{ maxHeight: '45%' }}>
            {chatsLoading && (
              <p className="px-3 py-2 text-[10px] text-gray-400">Loading...</p>
            )}
            {!chatsLoading && chats.length === 0 && (
              <p className="px-3 py-2 text-[10px] text-gray-400 italic">No conversations yet.</p>
            )}
            {today.length > 0 && (
              <div>
                <p className="px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Today</span>
                  {chats.length > 0 && (
                    <button type="button" onClick={handleClearAll} className="text-indigo-500 hover:text-indigo-700 normal-case text-[10px] font-normal transition-colors">
                      Clear all
                    </button>
                  )}
                </p>
                <div className="space-y-0.5">
                  {today.map((c) => (
                    <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} onDoubleClick={() => handleConvDoubleClick(c)} onArchive={handleArchiveChat} />
                  ))}
                </div>
              </div>
            )}
            {lastWeek.length > 0 && (
              <div>
                <p className="px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Last 7 Days</span>
                  {today.length === 0 && chats.length > 0 && (
                    <button type="button" onClick={handleClearAll} className="text-indigo-500 hover:text-indigo-700 normal-case text-[10px] font-normal transition-colors">
                      Clear all
                    </button>
                  )}
                </p>
                <div className="space-y-0.5">
                  {lastWeek.map((c) => (
                    <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} onDoubleClick={() => handleConvDoubleClick(c)} onArchive={handleArchiveChat} />
                  ))}
                </div>
              </div>
            )}
            {older.length > 0 && (
              <div>
                <p className="px-3 py-1 text-[10px] font-medium text-gray-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Older</span>
                  {today.length === 0 && lastWeek.length === 0 && (
                    <button type="button" onClick={handleClearAll} className="text-indigo-500 hover:text-indigo-700 normal-case text-[10px] font-normal transition-colors">
                      Clear all
                    </button>
                  )}
                </p>
                <div className="space-y-0.5">
                  {older.map((c) => (
                    <ConvItem key={c.id} conv={c} active={activeConv === c.id} onClick={() => handleConvSelect(c.id)} onDoubleClick={() => handleConvDoubleClick(c)} onArchive={handleArchiveChat} />
                  ))}
                </div>
              </div>
            )}

            {/* Archived dropdown */}
            <div className="mt-1">
              <button
                type="button"
                onClick={() => setArchivedOpen((o) => !o)}
                className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider hover:text-gray-600 transition-colors rounded-lg hover:bg-gray-50"
              >
                <span>Archived</span>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ transform: archivedOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
              {archivedOpen && (
                <div className="space-y-0.5 mt-0.5">
                  {archivedLoading && (
                    <p className="px-3 py-1 text-[10px] text-gray-400">Loading...</p>
                  )}
                  {!archivedLoading && archivedChats.length === 0 && (
                    <p className="px-3 py-1 text-[10px] text-gray-400 italic">No archived chats.</p>
                  )}
                  {archivedChats.map((c) => (
                    <ArchivedConvItem
                      key={c.id}
                      conv={c}
                      onDelete={handleDeleteArchivedChat}
                      onUnarchive={handleUnarchiveChat}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Materials */}
          <div className="flex-1 min-h-0 flex flex-col border-t border-gray-200 pt-2">
            {/* Header row */}
            <div className="px-3 py-2 flex items-center justify-between">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Your Materials</span>
              {materials.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-400 tabular-nums">
                    {materials.filter((m) => m.selected).length} selected
                  </span>
                  <button
                    type="button"
                    onClick={() => setAllMaterialsSelected(true)}
                    className="text-[10px] font-medium text-indigo-500 hover:text-indigo-700 transition-colors"
                  >
                    All
                  </button>
                  <button
                    type="button"
                    onClick={() => setAllMaterialsSelected(false)}
                    className="text-[10px] font-medium text-gray-500 hover:text-gray-700 transition-colors"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>

            {/* Materials list */}
            <div className="flex-1 overflow-y-auto pb-2">
              {materialsLoading && (
                <p className="px-3 py-2 text-[10px] text-gray-400">Loading…</p>
              )}
              {!materialsLoading && materials.length === 0 ? (
                <p className="px-3 py-2 text-[10px] text-gray-400 italic">No materials uploaded yet.</p>
              ) : (
                (() => {
                  const myMats = materials.filter((m) => !m.collaborator);
                  const collabMats = materials.filter((m) => m.collaborator);
                  return (
                    <div className="space-y-0.5">
                      {myMats.map((m) => (
                        <div
                          key={m.id}
                          className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors cursor-default border-l-2 ${
                            m.selected ? 'border-indigo-400' : 'border-transparent'
                          }`}
                        >
                          <FileTypeBadge name={m.name} sourceType={m.source_type} />
                          <span
                            className="flex-1 truncate min-w-0 hover:underline cursor-pointer"
                            onClick={() => handleOpenMaterial(m)}
                          >{m.name}</span>
                          <MaterialToggle checked={m.selected} onToggle={() => handleToggleMaterial(m.id)} />
                        </div>
                      ))}
                      {collabMats.length > 0 && (
                        <>
                          <div className="px-3 pt-2 pb-0.5">
                            <span className="text-[9px] font-semibold text-gray-300 uppercase tracking-wider">From collaborators</span>
                          </div>
                          {collabMats.map((m) => (
                            <div
                              key={m.id}
                              className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-gray-500 hover:bg-gray-100 transition-colors cursor-default border-l-2 ${
                                m.selected ? 'border-indigo-300' : 'border-transparent'
                              }`}
                            >
                              <FileTypeBadge name={m.name} sourceType={m.source_type} />
                              <span
                                className="flex-1 truncate min-w-0 hover:underline cursor-pointer"
                                onClick={() => handleOpenMaterial(m)}
                              >{m.name}</span>
                              <MaterialToggle checked={m.selected} onToggle={() => handleToggleMaterial(m.id)} />
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  );
                })()
              )}
            </div>

            {/* Add Source button */}
            <div className="px-3 pb-3 pt-2 flex-shrink-0 border-t border-gray-100 bg-white">
              <button
                type="button"
                onClick={onAddSource}
                className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <PlusIcon />
                Add Source
              </button>
            </div>
          </div>

        </div>

        {/* Bottom: user */}
        {userData && (
          <div className="border-t border-gray-200 p-3 flex items-center gap-2">
            {userData.picture ? (
              <img src={userData.picture} alt={userData.name} className="w-7 h-7 rounded-full border border-gray-200 flex-shrink-0" />
            ) : (
              <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                {(userData.name || userData.username || 'U')[0].toUpperCase()}
              </div>
            )}
            <span className="text-xs text-gray-700 font-medium truncate">{userData.name || userData.username}</span>
          </div>
        )}
        </div>
      ) : (
        <button
          type="button"
          onClick={handleSidebarRestore}
          className="flex-shrink-0 w-3 rounded-2xl border border-gray-200 bg-white shadow-sm hover:bg-gray-50 transition-colors relative"
          title="Show sidebar"
        >
          <span className="absolute inset-y-2 left-1/2 -translate-x-1/2 w-px bg-gray-300" />
        </button>
      )}

      {/* ── Main chat ── */}
      <div className="flex-1 flex flex-col min-w-0 relative overflow-hidden bg-white rounded-2xl border border-gray-200 shadow-sm">

        {/* Chat title header */}
        {activeConv && activeConv !== '__new__' && (() => {
          const activeChat = chats.find((c) => c.id === activeConv);
          if (!activeChat) return null;
          return (
            <div className="flex-shrink-0 px-6 pt-4 pb-2 border-b border-gray-100">
              {editingTitle ? (
                <input
                  ref={titleInputRef}
                  value={titleValue}
                  onChange={(e) => setTitleValue(e.target.value)}
                  onBlur={handleTitleSave}
                  onKeyDown={handleTitleKeyDown}
                  disabled={titleSaving}
                  className="w-full text-sm font-semibold text-gray-900 bg-transparent border-b-2 border-indigo-400 focus:outline-none px-0 py-0.5 disabled:opacity-50"
                  maxLength={500}
                />
              ) : (
                <p
                  role="button"
                  tabIndex={0}
                  className="text-sm font-semibold text-gray-900 truncate cursor-text select-none"
                  title="Double-click to rename"
                  onDoubleClick={handleTitleDoubleClick}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === 'F2') handleTitleDoubleClick(); }}
                >
                  {activeChat.title}
                </p>
              )}
            </div>
          );
        })()}

        {/* Messages */}
        <div className={`flex-1 min-h-0 overflow-y-auto overflow-x-auto px-6 pt-5 pb-4 space-y-6 transition-all duration-200 ${sourcesPanel.open ? 'mr-80' : ''}`}>
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-center">
              <p className="text-base font-semibold text-gray-800">Ask me anything about {course?.title || 'this course'}</p>
              <p className="text-sm text-gray-400 max-w-xs">I can explain concepts, quiz you on the material, summarize lectures, and more.</p>
            </div>
          ) : (
            (() => {
              const lastAssistantIdx = messages.reduce((acc, m, idx) => m.role === 'assistant' ? idx : acc, -1);
              return messages.map((msg, i) => {
              const prevMsg = messages[i - 1];
              const rawHistory = msg.role === 'assistant' ? prevMsg?.reply_history : null;
              const replyHistory = (() => {
                if (!rawHistory) return null;
                if (Array.isArray(rawHistory)) return rawHistory.length ? { back: rawHistory, forward: [] } : null;
                const b = rawHistory.back || [], f = rawHistory.forward || [];
                return b.length || f.length ? { back: b, forward: f } : null;
              })();
              const webSearchUrls = msg.role === 'assistant' ? (() => {
                const trace = Array.isArray(msg.tool_trace) ? msg.tool_trace : [];
                const seen = new Set();
                return trace
                  .filter((t) => t.tool === 'web_search' && Array.isArray(t.urls))
                  .flatMap((t) => t.urls)
                  .filter((u) => u.url && !seen.has(u.url) && seen.add(u.url));
              })() : null;
              const usedWebOnly = msg.role === 'assistant' && (() => {
                const trace = Array.isArray(msg.tool_trace) ? msg.tool_trace : [];
                const hasWeb = trace.some((t) => t.tool === 'web_search');
                const hasPage = trace.some((t) => t.tool === 'get_page_content');
                return hasWeb && !hasPage;
              })();
              return (
              <div
                key={msg.id}
                id={`msg-${msg.id}`}
                className={highlightMessageId === msg.id ? 'ring-2 ring-yellow-300 rounded-lg transition' : undefined}
              >
              <MessageBubble
                msg={msg}
                courseName={course?.title}
                userPicture={userData?.picture}
                onCiteClick={msg.role === 'assistant' && !usedWebOnly ? (n) => openSources(msg.id, n) : null}
                webSearchUrls={webSearchUrls?.length ? webSearchUrls : null}
                isEditing={editingMsgId === msg.id}
                editingContent={editingContent}
                onEditStart={(id, content) => {
                  setEditingMsgId(id);
                  setEditingContent(content || '');
                  const keys = msg.image_s3_keys || [];
                  const urls = msg.image_download_urls || [];
                  setEditImages(keys.map((key, i) => ({
                    kind: 'existing',
                    s3_key: key,
                    filename: urls[i]?.filename || key.split('/').pop(),
                    url: urls[i]?.url || '',
                  })));
                }}
                onEditChange={setEditingContent}
                onEditSave={() => handleEditMessage(msg.id, editingContent)}
                onEditCancel={() => {
                  setEditingMsgId(null);
                  setEditingContent('');
                  setEditImages([]);
                }}
                editImages={editImages}
                onEditImageAdd={addEditImages}
                onEditImageRemove={removeEditImage}
                editFileInputRef={editFileInputRef}
                canEdit={msg.role === 'user' && typeof msg.message_index === 'number' && !sending}
                replyHistory={replyHistory}
                onRevert={!msg._generationProposal && replyHistory?.back?.length ? handleRevertMessage : null}
                onRestore={replyHistory?.forward?.length ? handleRestoreMessage : null}
                onRegenerate={msg.role === 'assistant' && !msg._generationProposal && !sending ? handleRegenerateMessage : null}
                availableModels={availableModels}
                materials={materials}
                onPin={msg.role === 'assistant' ? () => {
                  const userMsg = messages.slice(0, i).reverse().find((m) => m.role === 'user');
                  if (userMsg) handlePinMessage(msg, userMsg);
                } : null}
                isPinned={msg.role === 'assistant' ? pinnedResponses.some((p) => p.assistant_message_id === msg.id) : false}
                onFollowUpClick={msg.role === 'assistant' ? (q) => {
                  setInput(q);
                  setTimeout(() => textareaRef.current?.focus(), 0);
                } : null}
                onSkipClarification={msg.role === 'assistant' ? () => handleSkipClarification(msg.id) : null}
                isLastAssistantMsg={msg.role === 'assistant' && i === lastAssistantIdx && !sending}
                onBuild={msg._generationProposal ? () => handleBuildGeneration(msg) : null}
                onRefine={msg._generationProposal ? () => handleRefineGeneration(msg) : null}
              />
              </div>
              );
            });
            })()
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <Composer
          images={images}
          imageUploadStates={imageUploadStates}
          input={input}
          setInput={setInput}
          availableModels={availableModels}
          selectedModel={selectedModel}
          selectedModelId={selectedModelId}
          modelDropdownOpen={modelDropdownOpen}
          setModelDropdownOpen={setModelDropdownOpen}
          modelListDropdownOpen={modelListDropdownOpen}
          setModelListDropdownOpen={setModelListDropdownOpen}
          promptLibOpen={promptLibOpen}
          setPromptLibOpen={setPromptLibOpen}
          webSearchEnabled={webSearchEnabled}
          sending={sending}
          gate={gate}
          textareaRef={textareaRef}
          fileInputRef={fileInputRef}
          dropdownRef={dropdownRef}
          modelListDropdownRef={modelListDropdownRef}
          handleSend={handleSend}
          handleKeyDown={handleKeyDown}
          handlePaste={handlePaste}
          handleFileInputChange={handleFileInputChange}
          handleModelSelect={handleModelSelect}
          handleModelIdSelect={handleModelIdSelect}
          toggleWebSearch={toggleWebSearch}
          removeImage={removeImage}
          composerMinHeight={CHAT_COMPOSER_MIN_HEIGHT_PX}
          composerMaxHeight={CHAT_COMPOSER_MAX_HEIGHT_PX}
        />

        <SourcesPanel
          open={sourcesPanel.open}
          chunks={sourcesPanel.messageId ? msgChunks[sourcesPanel.messageId] : null}
          focusIndex={sourcesPanel.focusIndex}
          onClose={() => setSourcesPanel((p) => ({ ...p, open: false }))}
          materials={materials}
        />
      </div>
    </div>

    {/* Saved pins — full width below chat + input */}
    <div className="w-full rounded-2xl border border-gray-200 shadow-sm bg-white overflow-hidden">
      <PinsPanel
        pins={pinnedResponses}
        courseName={course?.title}
        userData={userData}
        materials={materials}
        onDeletePin={handleDeletePin}
      />
    </div>

    {searchOpen && (
      <SearchChat
        courseId={course.id}
        chats={chats.filter(c => c.id !== '__new__')}
        onSelectChat={handleConvSelect}
        onClose={() => setSearchOpen(false)}
      />
    )}
    </div>
  );
}
