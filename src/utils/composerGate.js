// Pure: decides whether the chat composer can send, and what to tell the user if not.
export function composerGateState(availableModels) {
  const hasKey = Array.isArray(availableModels) && availableModels.length > 0;
  const msg = 'Add an API key in your Profile to start chatting.';
  return {
    canSend: hasKey,
    bannerText: hasKey ? null : msg,
    disabledReason: hasKey ? null : msg,
  };
}
