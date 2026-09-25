import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  LOCAL_MOCK_SAMPLE_RATE_HZ,
  createComfortVoiceScope,
  comfortVoiceScopeToken,
  isValidSyntheticPcm16Frame,
} from '../src/services/comfortVoice/localContracts.ts';
import { LocalComfortVoiceSession } from '../src/services/comfortVoice/localVoiceSession.ts';
import { requiresComfortVoiceLocalReset } from '../src/hooks/useComfortVoiceLocal.ts';

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function createFakes({ authorize = async () => undefined, connect = async () => undefined } = {}) {
  const media = [];
  const scheduled = [];
  const fakes = {
    authorize,
    connect,
    openSyntheticMedia(input) {
      const port = { ...input, closed: 0, close() { this.closed += 1; } };
      media.push(port);
      return port;
    },
    schedule(task) {
      const handle = { task, cancelled: false };
      scheduled.push(handle);
      return handle;
    },
    cancelSchedule(handle) { handle.cancelled = true; },
  };
  return { fakes, media, scheduled };
}

function scope(epoch = 1) {
  return createComfortVoiceScope({
    portfolioId: 'synthetic-portfolio',
    selectedAccountScope: 'all',
    asOf: '2026-09-10',
    calculationVersion: 'synthetic-version',
    inputDigest: 'synthetic-digest',
    viewEpoch: epoch,
  });
}

function validFrame(byteLength = 64) {
  return { encoding: 'PCM16', sampleRateHz: LOCAL_MOCK_SAMPLE_RATE_HZ, byteLength, synthetic: true };
}

function validOutput(byteLength = 16) {
  return { kind: 'simulated-local-state', byteLength };
}

function createSession(fakes) {
  const effects = { states: [], outputs: [], errors: 0 };
  const session = new LocalComfortVoiceSession(fakes, {
    onState: (state) => effects.states.push(state),
    onOutput: (output) => effects.outputs.push(output),
    onError: () => { effects.errors += 1; },
  });
  return { session, effects };
}

const localContractsSource = await readFile(new URL('../src/services/comfortVoice/localContracts.ts', import.meta.url), 'utf8');
const localSessionSource = await readFile(new URL('../src/services/comfortVoice/localVoiceSession.ts', import.meta.url), 'utf8');
const hookSource = await readFile(new URL('../src/hooks/useComfortVoiceLocal.ts', import.meta.url), 'utf8');
const dadSource = await readFile(new URL('../src/components/DadModeView.tsx', import.meta.url), 'utf8');
const privateAppSource = await readFile(new URL('../src/components/PrivateNsdlApp.tsx', import.meta.url), 'utf8');
const viewSource = await readFile(new URL('../src/components/NsdlPortfolioView.tsx', import.meta.url), 'utf8');

assert.equal(JSON.stringify(scope()), '{}', 'canonical scope is non-serializable');
assert.deepEqual(Object.keys(scope()), [], 'canonical scope exposes no enumerable facts');
assert.match(comfortVoiceScopeToken(scope()), /^local-scope-\d+$/, 'adapter receives a generic state token only');
assert.throws(() => createComfortVoiceScope({ portfolioId: '', selectedAccountScope: 'all', asOf: '2026-09-10', viewEpoch: 1 }), /invalid local Comfort voice scope/);
assert.equal(isValidSyntheticPcm16Frame(validFrame()), true);
for (const invalid of [
  { ...validFrame(), sampleRateHz: 8000 },
  { ...validFrame(), byteLength: 63 },
  { ...validFrame(), byteLength: 4096 },
  { ...validFrame(), encoding: 'PCM8' },
  { ...validFrame(), synthetic: false },
]) assert.equal(isValidSyntheticPcm16Frame(invalid), false, 'only 16 kHz bounded synthetic PCM16 metadata is accepted');

assert.match(dadSource, /Voice unavailable — coming soon/, 'normal Comfort Talk remains unavailable');
assert.match(privateAppSource, /comfortVoiceTestMode\?: 'local-mock'/, 'test mode is absent unless injected');
assert.doesNotMatch(privateAppSource, /VITE_.*VOICE|localStorage|sessionStorage/);
assert.match(viewSource, /createComfortVoiceScope/);
assert.match(viewSource, /calculationVersion/);
assert.match(viewSource, /inputDigest/);
assert.doesNotMatch(localContractsSource, /JSON\.stringify|toJSON|localStorage|sessionStorage|indexedDB|fetch\(|WebSocket|AudioContext|getUserMedia|speechSynthesis/);
assert.doesNotMatch(localSessionSource, /fetch\(|WebSocket|AudioContext|getUserMedia|speechSynthesis|navigator\.|google|Gemini|provider/);
assert.match(hookSource, /useLayoutEffect/);
assert.equal(requiresComfortVoiceLocalReset({ enabled: true, scope: scope(), privacyShieldActive: false }, 'input-change'), false, 'active Talk keeps its local session');
assert.equal(requiresComfortVoiceLocalReset({ enabled: true, scope: scope(), privacyShieldActive: true }, 'input-change'), true, 'Privacy Shield resets local voice synchronously');
assert.equal(requiresComfortVoiceLocalReset({ enabled: true, scope: scope(), privacyShieldActive: false }, 'talk-exit'), true, 'Talk exit cleanup resets local voice');
assert.equal(requiresComfortVoiceLocalReset({ enabled: true, scope: scope(), privacyShieldActive: false }, 'unmount'), true, 'unmount cleanup resets local voice');

// Stop invalidates before each awaited fake boundary.
const authorizing = deferred();
const delayedAuth = createFakes({ authorize: () => authorizing.promise });
const delayedAuthRun = createSession(delayedAuth.fakes);
const pendingAuth = delayedAuthRun.session.start(scope());
delayedAuthRun.session.stop();
authorizing.resolve();
await pendingAuth;
assert.equal(delayedAuth.media.length, 0, 'late authorization cannot connect or open simulated media');
assert.equal(delayedAuthRun.effects.states.at(-1), 'idle', 'stop clears state synchronously');

const connecting = deferred();
const delayedConnect = createFakes({ connect: () => connecting.promise });
const delayedConnectRun = createSession(delayedConnect.fakes);
const pendingConnect = delayedConnectRun.session.start(scope());
await Promise.resolve();
delayedConnectRun.session.stop();
connecting.resolve();
await pendingConnect;
assert.equal(delayedConnect.media.length, 0, 'late connect cannot open simulated media');

// Retry takes ownership before the original authorization settles. Resolve the
// retry first, then reverse-resolve the stale start: its completion must not
// install media, mutate state, or close the new owner's media session.
const oldAuthorization = deferred();
const retryAuthorization = deferred();
let authorizationCalls = 0;
const reverseResolution = createFakes({
  authorize: () => (++authorizationCalls === 1 ? oldAuthorization.promise : retryAuthorization.promise),
});
const reverseResolutionRun = createSession(reverseResolution.fakes);
const sharedScope = scope(11);
const staleStart = reverseResolutionRun.session.start(sharedScope);
const ownerRetry = reverseResolutionRun.session.retry(sharedScope);
retryAuthorization.resolve();
await ownerRetry;
assert.equal(reverseResolution.media.length, 1, 'new retry installs exactly one current media owner');
const retryOwner = reverseResolution.media[0];
const statesBeforeOldResolution = [...reverseResolutionRun.effects.states];
oldAuthorization.resolve();
await staleStart;
assert.equal(reverseResolution.media.length, 1, 'old completion cannot install a second media session');
assert.equal(reverseResolutionRun.session.stateScope, sharedScope, 'old completion cannot replace the retry scope owner');
assert.equal(retryOwner.closed, 0, 'old completion cannot close the retry media owner');
assert.deepEqual(reverseResolutionRun.effects.states, statesBeforeOldResolution, 'old completion cannot mutate the retry state');
assert.equal(reverseResolutionRun.effects.errors, 0, 'old completion cannot surface an error for the retry owner');

// A fake is allowed to invoke its callback synchronously.  While opening it is
// still connecting, so a frame is invalid and must fail closed without a later
// listening state or a temporal-dead-zone error.
const synchronousOpen = createFakes();
synchronousOpen.fakes.openSyntheticMedia = (input) => {
  const port = { ...input, closed: 0, close() { this.closed += 1; } };
  synchronousOpen.media.push(port);
  input.onFrame(validFrame());
  return port;
};
const synchronousOpenRun = createSession(synchronousOpen.fakes);
await synchronousOpenRun.session.start(scope());
assert.deepEqual(synchronousOpenRun.effects.states, ['authorizing', 'connecting', 'error'], 'connecting callbacks cannot skip into thinking/listening');
assert.equal(synchronousOpenRun.effects.errors, 1, 'invalid connecting frame is surfaced only as a generic error');
assert.equal(synchronousOpen.media[0].closed, 1, 'invalid synchronous media owner is closed');

// A current fake can move through generic state; stopping and replacing scope
// invalidates every late frame, output, scheduled drain, and error callback.
const current = createFakes();
const currentRun = createSession(current.fakes);
const firstScope = scope(2);
await currentRun.session.start(firstScope);
assert.equal(current.media.length, 1);
const oldPort = current.media[0];
oldPort.onFrame(validFrame());
assert.equal(currentRun.effects.states.at(-1), 'thinking');
oldPort.onOutput(validOutput());
assert.equal(current.scheduled.length, 1);
currentRun.session.replaceScope(scope(3));
assert.equal(oldPort.closed, 1, 'scope replacement closes the old fake media owner once');
assert.equal(currentRun.effects.outputs.length, 0, 'scope replacement clears pending output before it drains');
current.scheduled[0].task();
oldPort.onFrame(validFrame());
oldPort.onOutput(validOutput());
oldPort.onError();
assert.equal(currentRun.effects.outputs.length, 0, 'stale callbacks cannot publish output');
assert.equal(currentRun.effects.errors, 0, 'stale callback cannot surface an error');

await new Promise((resolve) => setImmediate(resolve));
const activePort = current.media[1];
activePort.onFrame(validFrame());
activePort.onOutput(validOutput());
const activeDrain = current.scheduled.at(-1);
currentRun.session.stop();
activeDrain.task();
activePort.onFrame(validFrame());
assert.equal(currentRun.effects.outputs.length, 0, 'stop clears queue and prevents old drains');

// Invalid frame metadata and bounded output overflow fail closed with generic
// state only; no payload is retained or emitted.
for (const frame of [{ ...validFrame(), sampleRateHz: 44100 }, { ...validFrame(), byteLength: 65 }, { ...validFrame(), byteLength: 4096 }]) {
  const invalid = createFakes();
  const invalidRun = createSession(invalid.fakes);
  await invalidRun.session.start(scope());
  invalid.media[0].onFrame(frame);
  assert.equal(invalidRun.effects.states.at(-1), 'error');
  assert.equal(invalidRun.effects.errors, 1);
  assert.equal(invalidRun.effects.outputs.length, 0);
}

const bounded = createFakes();
const boundedRun = createSession(bounded.fakes);
await boundedRun.session.start(scope());
bounded.media[0].onFrame(validFrame());
for (let index = 0; index < 3; index += 1) bounded.media[0].onOutput(validOutput(300));
assert.equal(boundedRun.effects.errors, 0, 'bounded generic output queue accepts capacity');
bounded.media[0].onOutput(validOutput(300));
assert.equal(boundedRun.effects.states.at(-1), 'error', 'overflow fails closed');
for (const handle of bounded.scheduled) handle.task();
assert.equal(boundedRun.effects.outputs.length, 0, 'failure resets every queued generic output item');
boundedRun.session.dispose();
boundedRun.session.dispose();

// Retry starts a new generation after failure, and an injected synchronous
// scheduler drains without reading an uninitialized handle.
const retrying = createFakes();
const retryingRun = createSession(retrying.fakes);
await retryingRun.session.start(scope());
retrying.media[0].onFrame({ ...validFrame(), byteLength: 65 });
assert.equal(retryingRun.effects.states.at(-1), 'error');
await retryingRun.session.retry(scope());
assert.deepEqual(retryingRun.effects.states.slice(-3), ['authorizing', 'connecting', 'listening'], 'retry re-enters lifecycle in order');
assert.equal(retrying.media.length, 2, 'retry owns a distinct fake media session');

const synchronousSchedule = createFakes();
synchronousSchedule.fakes.schedule = (task) => {
  task();
  return { completed: true };
};
const synchronousScheduleRun = createSession(synchronousSchedule.fakes);
await synchronousScheduleRun.session.start(scope());
synchronousSchedule.media[0].onFrame(validFrame());
synchronousSchedule.media[0].onOutput(validOutput());
assert.equal(synchronousScheduleRun.effects.outputs.length, 1, 'synchronous scheduler drains one generic output without a TDZ failure');
assert.equal(synchronousScheduleRun.effects.states.at(-1), 'listening', 'synchronous drain returns to listening');

console.log('private Comfort voice local tests passed');
