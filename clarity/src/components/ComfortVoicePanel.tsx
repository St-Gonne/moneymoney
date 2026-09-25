import type { ComfortVoiceScope } from '../services/comfortVoice/localContracts.ts';
import type { LocalComfortVoiceFakes, LocalComfortVoiceState } from '../services/comfortVoice/localVoiceSession.ts';
import { useComfortVoiceLocal } from '../hooks/useComfortVoiceLocal.ts';
import './ComfortVoicePanel.css';

export type ComfortVoicePanelProps = {
  readonly mode?: 'unavailable' | 'local-mock';
  readonly scope?: ComfortVoiceScope | null;
  readonly privacyShieldActive: boolean;
  readonly fakes?: LocalComfortVoiceFakes;
};

const stateCopy: Record<LocalComfortVoiceState, string> = {
  idle: 'Ready',
  authorizing: 'Preparing local state',
  connecting: 'Connecting locally',
  listening: 'Listening state ready',
  thinking: 'Processing local state',
  speaking: 'Displaying local state',
  stopping: 'Stopping',
  error: 'Local state unavailable',
};

/**
 * The regular private route keeps the unavailable copy. A harness may inject
 * the local mode, which exposes generic state tokens only.
 */
export function ComfortVoicePanel({ mode = 'unavailable', scope = null, privacyShieldActive, fakes }: ComfortVoicePanelProps) {
  const local = useComfortVoiceLocal({
    enabled: mode === 'local-mock',
    scope: mode === 'local-mock' ? scope : null,
    privacyShieldActive,
    fakes,
  });

  if (mode !== 'local-mock') {
    return (
      <article className="comfort-voice-panel" aria-label="Talk">
        <h2>Voice unavailable — coming soon</h2>
        <p>Voice is not connected in this private preview.</p>
      </article>
    );
  }

  if (privacyShieldActive) {
    return (
      <article className="comfort-voice-panel comfort-voice-panel-masked" aria-label="Privacy Shield content masked">
        <h2>••••••</h2>
        <p>••••••</p>
      </article>
    );
  }

  return (
    <article className="comfort-voice-panel" aria-labelledby="comfort-voice-heading">
      <p className="comfort-voice-eyebrow">Synthetic local voice mock</p>
      <h2 id="comfort-voice-heading">Simulated local-only voice state</h2>
      <p className="comfort-voice-notice">No microphone or network</p>
      <p className="comfort-voice-status" role="status" aria-live="polite">State: {stateCopy[local.state]}</p>
      <p className="comfort-voice-output" aria-live="polite">Generic output items: {local.outputCount}</p>
      <div className="comfort-voice-actions">
        <button type="button" onClick={local.start} disabled={local.state !== 'idle' && local.state !== 'error'}>Start</button>
        <button type="button" onClick={local.retry} disabled={local.state !== 'error'}>Retry</button>
        <button type="button" onClick={local.stop} disabled={local.state === 'idle'}>Stop</button>
      </div>
    </article>
  );
}
