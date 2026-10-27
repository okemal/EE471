// Keep microphone audio local until the user finishes this one recording.
class RecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) this.port.postMessage(channel.slice());
    return true;
  }
}
registerProcessor('calculator-recorder', RecorderProcessor);
