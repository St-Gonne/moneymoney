export class AudioRecorder {
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;

  async start(onChunk: (base64Data: string) => void) {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    this.audioCtx = new AudioCtx({ sampleRate: 16000 });
    
    const source = this.audioCtx.createMediaStreamSource(this.stream);
    
    this.processor = this.audioCtx.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);
      
      const int16Buffer = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]));
        int16Buffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      
      const uint8 = new Uint8Array(int16Buffer.buffer);
      let binary = '';
      for (let i = 0; i < uint8.length; i++) {
        binary += String.fromCharCode(uint8[i]);
      }
      onChunk(btoa(binary));
    };
    
    source.connect(this.processor);
    this.processor.connect(this.audioCtx.destination);
  }

  stop() {
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
  }
}
