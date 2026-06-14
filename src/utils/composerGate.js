// Pure: decides whether the chat composer can send, and what to tell the user if not.
// `loaded` indicates the API-key status has actually been fetched; while it is
// false we stay silent instead of flashing the no-key banner on mount.
export function composerGateState(availableModels, loaded = true) {
  const hasKey = Array.isArray(availableModels) && availableModels.length > 0;
  const msg = 'Add an API key in your Profile to start chatting.';
  if (!loaded) {
    return { canSend: false, bannerText: null, disabledReason: null };
  }
  return {
    canSend: hasKey,
    bannerText: hasKey ? null : msg,
    disabledReason: hasKey ? null : msg,
  };
}
