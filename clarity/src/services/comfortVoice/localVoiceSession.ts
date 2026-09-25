import {
  type ComfortVoiceScope,
  comfortVoiceScopeToken,
  isComfortVoiceScope,
  isValidSimulatedOutput,
  isValidSyntheticPcm16Frame,
  MAX_SIMULATED_OUTPUT_BYTES,
  MAX_SIMULATED_OUTPUT_ITEMS,
  type SimulatedOutputMetadata,
  type SyntheticPcm16FrameMetadata,
} from './localContracts.ts';

export type LocalComfortVoiceState = 'idle' | 'authorizing' | 'connecting' | 'listening' | 'thinking' | 'speaking' | 'stopping' | 'error';

type LocalFakeCallbacks = {
  readonly onFrame: (frame: SyntheticPcm16FrameMetadata) => void;
  readonly onOutput: (output: SimulatedOutputMetadata) => void;
  readonly onError: () => void;
};

export type LocalComfortVoiceFakes = {
  readonly authorize: (input: { readonly scopeToken: string; readonly signal: AbortSignal }) => Promise<void>;
  readonly connect: (input: { readonly scopeToken: string; readonly signal: AbortSignal }) => Promise<void>;
  readonly openSyntheticMedia: (input: { readonly scopeToken: string; readonly signal: AbortSignal } & LocalFakeCallbacks) => { readonly close: () => void };
  readonly schedule: (task: () => void) => unknown;
  readonly cancelSchedule: (handle: unknown) => void;
};

export type LocalComfortVoiceCallbacks = {
  readonly onState: (state: LocalComfortVoiceState) => void;
  readonly onOutput: (output: SimulatedOutputMetadata) => void;
  readonly onError: () => void;
};

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

/**
 * A single owner for the synthetic-only session.  All callbacks are bound to
 * a generation and contain only generic state metadata.
 */
export class LocalComfortVoiceSession {
  #generation = 0;
  #state: LocalComfortVoiceState = 'idle';
  #controller: AbortController | null = null;
  #media: { close: () => void } | null = null;
  #scheduled = new Set<unknown>();
  #queue: SimulatedOutputMetadata[] = [];
  #queueBytes = 0;
  #scope: ComfortVoiceScope | null = null;
  #disposed = false;
  private readonly fakes: LocalComfortVoiceFakes;
  private readonly callbacks: LocalComfortVoiceCallbacks;

  constructor(fakes: LocalComfortVoiceFakes, callbacks: LocalComfortVoiceCallbacks) {
    this.fakes = fakes;
    this.callbacks = callbacks;
  }

  get stateScope(): ComfortVoiceScope | null {
    return this.#scope;
  }

  async start(scope: ComfortVoiceScope): Promise<void> {
    if (this.#disposed || !isComfortVoiceScope(scope)) return;
    this.stop();
    const generation = ++this.#generation;
    const controller = new AbortController();
    this.#controller = controller;
    this.#scope = scope;
    const scopeToken = comfortVoiceScopeToken(scope);
    try {
      this.#publish(generation, 'authorizing');
      await this.fakes.authorize({ scopeToken, signal: controller.signal });
      if (!this.#isCurrent(generation, scope, controller)) return;
      this.#publish(generation, 'connecting');
      await this.fakes.connect({ scopeToken, signal: controller.signal });
      if (!this.#isCurrent(generation, scope, controller)) return;
      this.#media = this.fakes.openSyntheticMedia({
        scopeToken,
        signal: controller.signal,
        onFrame: (frame) => this.#onFrame(generation, scope, frame),
        onOutput: (output) => this.#onOutput(generation, scope, output),
        onError: () => this.#fail(generation, scope),
      });
      if (!this.#isCurrent(generation, scope, controller)) {
        this.#media?.close();
        this.#media = null;
        return;
      }
      this.#publish(generation, 'listening');
    } catch (error) {
      if (this.#isCurrent(generation, scope, controller) && !isAbort(error)) this.#fail(generation, scope);
    }
  }

  retry(scope: ComfortVoiceScope): Promise<void> {
    return this.start(scope);
  }

  replaceScope(scope: ComfortVoiceScope | null): void {
    if (scope === this.#scope) return;
    this.stop();
    if (scope) void this.start(scope);
  }

  stop(): void {
    const wasActive = this.#controller !== null || this.#media !== null || this.#queue.length > 0 || this.#scope !== null;
    ++this.#generation;
    if (wasActive) {
      this.#state = 'stopping';
      this.callbacks.onState('stopping');
    }
    this.#controller?.abort();
    this.#controller = null;
    this.#media?.close();
    this.#media = null;
    for (const handle of this.#scheduled) this.fakes.cancelSchedule(handle);
    this.#scheduled.clear();
    this.#queue = [];
    this.#queueBytes = 0;
    this.#scope = null;
    if (wasActive) {
      this.#state = 'idle';
      this.callbacks.onState('idle');
    }
  }

  dispose(): void {
    if (this.#disposed) return;
    this.#disposed = true;
    this.stop();
  }

  #isCurrent(generation: number, scope: ComfortVoiceScope, controller: AbortController): boolean {
    return !this.#disposed && generation === this.#generation && this.#scope === scope && this.#controller === controller && !controller.signal.aborted;
  }

  #publish(generation: number, state: LocalComfortVoiceState): void {
    if (!this.#disposed && generation === this.#generation) {
      this.#state = state;
      this.callbacks.onState(state);
    }
  }

  #onFrame(generation: number, scope: ComfortVoiceScope, frame: SyntheticPcm16FrameMetadata): void {
    const controller = this.#controller;
    if (!controller || !this.#isCurrent(generation, scope, controller)) return;
    if (this.#state !== 'listening' || !isValidSyntheticPcm16Frame(frame)) {
      this.#fail(generation, scope);
      return;
    }
    this.#publish(generation, 'thinking');
  }

  #onOutput(generation: number, scope: ComfortVoiceScope, output: SimulatedOutputMetadata): void {
    const controller = this.#controller;
    if (!controller || !this.#isCurrent(generation, scope, controller)) return;
    if (this.#state !== 'thinking'
      || !isValidSimulatedOutput(output)
      || this.#queue.length >= MAX_SIMULATED_OUTPUT_ITEMS
      || this.#queueBytes + output.byteLength > MAX_SIMULATED_OUTPUT_BYTES) {
      this.#fail(generation, scope);
      return;
    }
    this.#queue.push(output);
    this.#queueBytes += output.byteLength;
    this.#scheduleDrain(generation, scope);
  }

  #scheduleDrain(generation: number, scope: ComfortVoiceScope): void {
    let handle: unknown;
    let ranSynchronously = false;
    const drain = () => {
      if (handle === undefined) ranSynchronously = true;
      else this.#scheduled.delete(handle);
      const controller = this.#controller;
      if (!controller || !this.#isCurrent(generation, scope, controller)) return;
      const next = this.#queue.shift();
      if (!next) return;
      this.#queueBytes -= next.byteLength;
      this.#publish(generation, 'speaking');
      this.callbacks.onOutput(next);
      if (this.#queue.length > 0) this.#scheduleDrain(generation, scope);
      else this.#publish(generation, 'listening');
    };
    handle = this.fakes.schedule(drain);
    if (!ranSynchronously) this.#scheduled.add(handle);
  }

  #fail(generation: number, scope: ComfortVoiceScope): void {
    if (generation !== this.#generation || this.#scope !== scope || this.#disposed) return;
    ++this.#generation;
    this.#controller?.abort();
    this.#controller = null;
    this.#media?.close();
    this.#media = null;
    for (const handle of this.#scheduled) this.fakes.cancelSchedule(handle);
    this.#scheduled.clear();
    this.#queue = [];
    this.#queueBytes = 0;
    this.#scope = null;
    this.#state = 'error';
    this.callbacks.onState('error');
    this.callbacks.onError();
  }
}
