class Recorder extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(4096);
    this.index = 0;
    this.port.onmessage = (event) => {
      if (event.data === "flush") {
        if (this.index) this.port.postMessage(this.buffer.slice(0, this.index));
        this.index = 0;
        this.port.postMessage("flushed");
      }
    };
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel)
      for (const sample of channel) {
        this.buffer[this.index++] = sample;
        if (this.index === this.buffer.length) {
          this.port.postMessage(this.buffer.slice());
          this.index = 0;
        }
      }
    return true;
  }
}
registerProcessor("recorder", Recorder);
