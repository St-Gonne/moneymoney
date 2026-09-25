import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import type { ComfortVoiceScope, SimulatedOutputMetadata } from '../services/comfortVoice/localContracts.ts';
import { LocalComfortVoiceSession, type LocalComfortVoiceFakes, type LocalComfortVoiceState } from '../services/comfortVoice/localVoiceSession.ts';

const defaultLocalFakes: LocalComfortVoiceFakes = {
  authorize: async () => undefined,
  connect: async () => undefined,
  openSyntheticMedia: () => ({ close() {} }),
  schedule: (task) => setTimeout(task, 0),
  cancelSchedule: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

export type UseComfortVoiceLocalInput = {
  readonly enabled: boolean;
  readonly scope: ComfortVoiceScope | null;
  readonly privacyShieldActive: boolean;
  readonly fakes?: LocalComfortVoiceFakes;
};

export type ComfortVoiceLocalController = {
  readonly state: LocalComfortVoiceState;
  readonly outputCount: number;
  readonly start: () => void;
  readonly retry: () => void;
  readonly stop: () => void;
  readonly reset: () => void;
};

export type ComfortVoiceLocalCleanupBoundary = 'input-change' | 'talk-exit' | 'unmount';

/** The hook executes this pure decision at every local-session boundary. */
export function requiresComfortVoiceLocalReset(
  input: Pick<UseComfortVoiceLocalInput, 'enabled' | 'scope' | 'privacyShieldActive'>,
  boundary: ComfortVoiceLocalCleanupBoundary,
): boolean {
  return boundary === 'talk-exit' || boundary === 'unmount' || !input.enabled || input.privacyShieldActive || input.scope === null;
}

/** The session is constructed only for the injected local-mock path. */
export function useComfortVoiceLocal(input: UseComfortVoiceLocalInput): ComfortVoiceLocalController {
  const [state, setState] = useState<LocalComfortVoiceState>('idle');
  const [outputCount, setOutputCount] = useState(0);
  const sessionRef = useRef<LocalComfortVoiceSession | null>(null);
  const fakesRef = useRef(input.fakes || defaultLocalFakes);
  const scopeRef = useRef(input.scope);
  scopeRef.current = input.scope;

  const reset = useCallback(() => {
    sessionRef.current?.stop();
    setOutputCount(0);
    setState('idle');
  }, []);

  useLayoutEffect(() => {
    if (requiresComfortVoiceLocalReset(input, 'input-change')) {
      reset();
      return;
    }
    if (!sessionRef.current) {
      sessionRef.current = new LocalComfortVoiceSession(fakesRef.current, {
        onState: setState,
        onOutput: (_output: SimulatedOutputMetadata) => setOutputCount((value) => value + 1),
        onError: () => setOutputCount(0),
      });
    }
    sessionRef.current.replaceScope(input.scope);
    return () => {
      if (requiresComfortVoiceLocalReset(input, 'talk-exit')) reset();
    };
  }, [input.enabled, input.privacyShieldActive, input.scope, reset]);

  useLayoutEffect(() => () => {
    if (requiresComfortVoiceLocalReset(input, 'unmount')) {
      sessionRef.current?.dispose();
      sessionRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    const scope = scopeRef.current;
    if (!input.enabled || input.privacyShieldActive || !scope) return;
    if (!sessionRef.current) return;
    setOutputCount(0);
    void sessionRef.current.start(scope);
  }, [input.enabled, input.privacyShieldActive]);

  const retry = useCallback(() => {
    const scope = scopeRef.current;
    if (!input.enabled || input.privacyShieldActive || !scope || !sessionRef.current) return;
    setOutputCount(0);
    void sessionRef.current.retry(scope);
  }, [input.enabled, input.privacyShieldActive]);

  return { state, outputCount, start, retry, stop: reset, reset };
}
