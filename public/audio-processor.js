class PCMDownsamplerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.buffer = [];
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const inputChannel = input[0]; // Mono channel
    const inputSampleRate = typeof sampleRate !== 'undefined' ? sampleRate : 48000;
    const sampleRateRatio = inputSampleRate / this.targetSampleRate;

    // Linear downsampling
    let offset = 0;
    while (offset < inputChannel.length) {
      const nextOffset = Math.round((this.buffer.length + 1) * sampleRateRatio);
      if (nextOffset < inputChannel.length) {
        const sample = inputChannel[nextOffset];
        // Convert Float32 (-1.0 to 1.0) to Int16 (-32768 to 32767)
        const int16Sample = Math.max(-32768, Math.min(32767, Math.floor(sample * 32767)));
        this.buffer.push(int16Sample);
      } else {
        break;
      }
      offset = nextOffset;
    }

    // Flush in chunks of 512 samples (~32ms chunks for low latency)
    if (this.buffer.length >= 512) {
      const pcm16 = new Int16Array(this.buffer.splice(0, 512));
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }

    return true;
  }
}

registerProcessor('pcm-downsampler-processor', PCMDownsamplerProcessor);
