/**
 * Local-only Comfort voice contracts.  These values deliberately describe
 * synthetic state, never audio samples, portfolio projections, or narration.
 */
export const LOCAL_MOCK_SAMPLE_RATE_HZ = 16000;
export const MAX_SYNTHETIC_PCM_FRAME_BYTES = 2048;
export const MAX_SIMULATED_OUTPUT_ITEMS = 3;
export const MAX_SIMULATED_OUTPUT_BYTES = 1024;

const scopeBrand = Symbol('comfort-voice-local-scope');
const scopeTokens = new WeakMap<object, string>();
let nextScopeToken = 0;

export type ComfortVoiceScope = {
  readonly [scopeBrand]: true;
};

export type ComfortVoiceScopeInput = {
  readonly portfolioId: string;
  readonly selectedAccountScope: string;
  readonly asOf: string;
  readonly calculationVersion?: string | null;
  readonly inputDigest?: string | null;
  readonly viewEpoch: number;
};

function boundedText(value: unknown, max = 256): string {
  return typeof value === 'string' ? value.slice(0, max) : '';
}

/**
 * Creates an opaque, non-serializable capability for one rendered Comfort
 * projection.  Canonical values exist only while the factory runs; the
 * returned object has no enumerable fields and its generic token reveals no
 * portfolio, account, date, digest, or calculation value.
 */
export function createComfortVoiceScope(input: ComfortVoiceScopeInput): ComfortVoiceScope {
  const canonicalParts = [
    boundedText(input.portfolioId),
    boundedText(input.selectedAccountScope),
    boundedText(input.asOf),
    boundedText(input.calculationVersion),
    boundedText(input.inputDigest),
    Number.isSafeInteger(input.viewEpoch) && input.viewEpoch >= 0 ? String(input.viewEpoch) : '',
  ];
  if (canonicalParts[0] === '' || canonicalParts[1] === '' || canonicalParts[2] === '' || canonicalParts[5] === '') {
    throw new Error('invalid local Comfort voice scope');
  }
  const scope = Object.freeze(Object.create(null)) as ComfortVoiceScope;
  scopeTokens.set(scope, `local-scope-${++nextScopeToken}`);
  return scope;
}

export function isComfortVoiceScope(value: unknown): value is ComfortVoiceScope {
  return typeof value === 'object' && value !== null && scopeTokens.has(value);
}

/** Generic local state only; it is safe for fake adapters to observe. */
export function comfortVoiceScopeToken(scope: ComfortVoiceScope): string {
  const token = scopeTokens.get(scope);
  if (!token) throw new Error('invalid local Comfort voice scope');
  return token;
}

export type SyntheticPcm16FrameMetadata = {
  readonly encoding: 'PCM16';
  readonly sampleRateHz: number;
  readonly byteLength: number;
  readonly synthetic: true;
};

export function isValidSyntheticPcm16Frame(value: unknown): value is SyntheticPcm16FrameMetadata {
  if (!value || typeof value !== 'object') return false;
  const frame = value as Partial<SyntheticPcm16FrameMetadata>;
  const byteLength = frame.byteLength;
  return frame.encoding === 'PCM16'
    && frame.sampleRateHz === LOCAL_MOCK_SAMPLE_RATE_HZ
    && frame.synthetic === true
    && Number.isInteger(byteLength)
    && byteLength !== undefined
    && byteLength > 0
    && byteLength <= MAX_SYNTHETIC_PCM_FRAME_BYTES
    && byteLength % 2 === 0;
}

export type SimulatedOutputMetadata = {
  readonly kind: 'simulated-local-state';
  readonly byteLength: number;
};

export function isValidSimulatedOutput(value: unknown): value is SimulatedOutputMetadata {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<SimulatedOutputMetadata>;
  const byteLength = item.byteLength;
  return item.kind === 'simulated-local-state'
    && Number.isInteger(byteLength)
    && byteLength !== undefined
    && byteLength > 0
    && byteLength <= MAX_SIMULATED_OUTPUT_BYTES;
}
