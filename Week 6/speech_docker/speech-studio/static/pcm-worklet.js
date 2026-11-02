/* Capture mono PCM16 at 16 kHz. Average each resampling interval, retaining
   fractional samples across audio blocks. Send 100 ms chunks to the page. */
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.weight = 0;
    this.sum = 0;
    this.samples = [];
    this.port.onmessage = (event) => {
      if (event.data === "flush") {
        this.flush();
        this.port.postMessage({type: "flushed"});
      }
    };
  }

  flush() {
    if (!this.samples.length) return;
    const buffer = new ArrayBuffer(this.samples.length * 2);
    const view = new DataView(buffer);
    this.samples.forEach((sample, index) => {
      sample = Math.max(-1, Math.min(1, sample));
      view.setInt16(index * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
    });
    this.samples = [];
    this.port.postMessage({type: "audio", buffer}, [buffer]);
  }

  process(inputs) {
    const channels = inputs[0];
    if (!channels?.length) return true;
    for (let index = 0; index < channels[0].length; index++) {
      let sample = 0;
      for (const channel of channels) sample += channel[index] / channels.length;
      let remaining = 1;
      while (remaining > 0.000001) {
        const take = Math.min(remaining, this.ratio - this.weight);
        this.sum += sample * take;
        this.weight += take;
        remaining -= take;
        if (this.weight >= this.ratio - 0.000001) {
          this.samples.push(this.sum / this.ratio);
          this.weight = 0;
          this.sum = 0;
          if (this.samples.length >= 1600) this.flush();
        }
      }
    }
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);
