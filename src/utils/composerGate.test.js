import { describe, it, expect } from 'vitest';
import { composerGateState } from './composerGate';

describe('composerGateState', () => {
  it('allows sending when at least one provider key exists', () => {
    const gate = composerGateState(['openai']);
    expect(gate.canSend).toBe(true);
    expect(gate.bannerText).toBeNull();
  });

  it('blocks sending and explains when no keys exist', () => {
    const gate = composerGateState([]);
    expect(gate.canSend).toBe(false);
    expect(gate.bannerText).toMatch(/Profile/);
    expect(gate.disabledReason).toMatch(/Profile/);
  });

  it('treats a non-array (still loading) as no keys', () => {
    const gate = composerGateState(undefined);
    expect(gate.canSend).toBe(false);
  });
});
