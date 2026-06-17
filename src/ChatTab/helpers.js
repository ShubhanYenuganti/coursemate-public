// ─── helpers ──────────────────────────────────────────────────────────────────

import { parseUTC } from '../utils/dateUtils';
import { PROVIDER_MODELS } from '../modelCatalog.js';

export const MODEL_LABELS = {
  gemini: 'Gemini',
  openai: 'GPT',
  claude: 'Claude',
};

export function groupChatsByDate(chats) {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const weekStart = new Date(todayStart.getTime() - 6 * 24 * 60 * 60 * 1000);
  const today = [], lastWeek = [], older = [];
  for (const chat of chats) {
    const d = parseUTC(chat.last_message_at || chat.created_at);
    if (d >= todayStart) today.push(chat);
    else if (d >= weekStart) lastWeek.push(chat);
    else older.push(chat);
  }
  return { today, lastWeek, older };
}

export function inferProviderFromModelId(modelId) {
  if (!modelId) return null;
  for (const [provider, models] of Object.entries(PROVIDER_MODELS)) {
    if ((models || []).some((m) => m.id === modelId)) return provider;
  }
  return null;
}

export function getMessageModelLabel(msg) {
  const modelId = msg?.ai_model || null;
  const provider = msg?.ai_provider || inferProviderFromModelId(modelId);
  if (provider && modelId) {
    const modelLabel = (PROVIDER_MODELS[provider] || []).find((m) => m.id === modelId)?.label;
    if (modelLabel) return modelLabel;
  }
  if (modelId) return modelId;
  if (provider) return MODEL_LABELS[provider] || provider;
  return null;
}
