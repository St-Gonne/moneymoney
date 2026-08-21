/**
 * Raw PCM 24kHz Audio Player for Gemini Live API
 * Supports continuous audio chunk queuing and instantaneous barge-in flush
 */
export class LiveAudioPlayer {
  private audioCtx: AudioContext | null = null;
  private nextStartTime = 0;
  private activeSources: AudioBufferSourceNode[] = [];

  private getContext(): AudioContext {
    if (!this.audioCtx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioCtx = new AudioCtx({ sampleRate: 24000 });
    }
    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
    return this.audioCtx;
  }

  public async playChunk(base64Pcm24k: string) {
    try {
      const ctx = this.getContext();

      // Decode base64 to 16-bit PCM Int16Array
      const binary = atob(base64Pcm24k);
      const len = binary.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const int16 = new Int16Array(bytes.buffer);

      // Convert Int16 (-32768 to 32767) to Float32 (-1.0 to 1.0)
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768.0;
      }

      const audioBuffer = ctx.createBuffer(1, float32.length, 24000);
      audioBuffer.getChannelData(0).set(float32);

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);

      const currentTime = ctx.currentTime;
      const startTime = Math.max(currentTime, this.nextStartTime);
      source.start(startTime);
      this.nextStartTime = startTime + audioBuffer.duration;

      this.activeSources.push(source);
      source.onended = () => {
        this.activeSources = this.activeSources.filter((s) => s !== source);
      };
    } catch (err) {
      console.warn('Error playing Live audio chunk:', err);
    }
  }

  /**
   * Called immediately when user starts speaking or Gemini emits interruption
   */
  public interrupt() {
    for (const source of this.activeSources) {
      try {
        source.stop();
        source.disconnect();
      } catch {
        // Source might have already ended
      }
    }
    this.activeSources = [];
    if (this.audioCtx) {
      this.nextStartTime = this.audioCtx.currentTime;
    }
  }

  public close() {
    this.interrupt();
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
  }
}
