export const digitWords = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'];
const commands = Object.fromEntries(digitWords.map((word, digit) => [word, String(digit)]));
Object.assign(commands, {
  point: '.', over: '/', times: '*', plus: '+', minus: '-', is: '=',
  clear: 'Escape', percent: '%', backspace: 'Backspace',
});

export function parseCommands(text) {
  // Reject the entire phrase before changing calculator state if any word is unknown.
  const normalized = text.toLowerCase().trim().replace(/change sign/g, 'changesign')
    .replace(/[?!,;:]/g, '').replace(/\.$/, '');
  const keys = [];
  for (const word of normalized.split(/\s+/)) {
    if (Object.hasOwn(commands, word)) keys.push(commands[word]);
    else if (word === 'changesign') keys.push('F9');
    else if (/^\d+(?:\.\d+)?$/.test(word)) keys.push(...word);
    else if (['+', '-', '*', '/', '=', '.'].includes(word)) keys.push(word);
    else throw new Error('Command not understood. Use Zero–Nine, Point, Over, Times, Plus, Minus, or Is.');
  }
  if (!keys.length || keys.length > 60) throw new Error('Please say a shorter calculator command.');
  return keys;
}

export function spokenNumber(value) {
  return [...String(value)].map((character) => digitWords[Number(character)] ??
    ({ '-': 'minus', '.': 'point', e: 'times ten to the power', '+': 'plus' }[character] || character)).join(' ');
}

export function encodeWav(chunks, sampleRate) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const samples = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) { samples.set(chunk, offset); offset += chunk.length; }
  const count = Math.floor(length * 16000 / sampleRate);
  const buffer = new ArrayBuffer(44 + count * 2);
  const view = new DataView(buffer);
  const write = (position, text) => [...text].forEach((char, i) => view.setUint8(position + i, char.charCodeAt(0)));
  write(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); write(8, 'WAVE');
  write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, 16000, true);
  view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  write(36, 'data'); view.setUint32(40, count * 2, true);
  for (let i = 0; i < count; i++) {
    // Average source samples when downsampling to Azure's 16 kHz PCM format.
    const start = Math.floor(i * sampleRate / 16000);
    const end = Math.min(length, Math.max(start + 1, Math.floor((i + 1) * sampleRate / 16000)));
    let total = 0;
    for (let j = start; j < end; j++) total += samples[j];
    const value = Math.max(-1, Math.min(1, total / (end - start)));
    view.setInt16(44 + i * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true);
  }
  return buffer;
}

export function createVoice({ onBusy, onCommands }) {
  const mic = document.querySelector('#microphone');
  const status = document.querySelector('#voice-status');
  let context;
  let queue = Promise.resolve();
  let generation = 0;
  let playing;
  let recording;
  let starting = false;
  let processing = false;
  const cache = new Map();
  const message = (text) => { status.textContent = text; };
  const unlock = async () => {
    context ??= new AudioContext();
    return context.resume();
  };
  const cancelSpeech = () => { generation++; playing?.stop(); playing = null; };

  function speak(text) {
    const version = generation;
    queue = queue.then(async () => {
      if (version !== generation) return;
      await unlock();
      let audio = cache.get(text);
      if (!audio) {
        const response = await fetch('/api/speech/speak', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }), signal: AbortSignal.timeout(25000),
        });
        if (!response.ok) throw new Error((await response.json()).error || 'Speech unavailable.');
        audio = await context.decodeAudioData(await response.arrayBuffer());
        if (cache.size >= 64) cache.delete(cache.keys().next().value);
        cache.set(text, audio);
      }
      if (version !== generation) return;
      await new Promise((resolve) => {
        const source = context.createBufferSource();
        source.buffer = audio;
        source.connect(context.destination);
        source.onended = () => { source.disconnect(); if (playing === source) playing = null; resolve(); };
        playing = source;
        source.start();
      });
    }).catch(() => message('Spoken feedback unavailable. Check Azure Speech and try again.'));
  }

  async function finish() {
    const session = recording;
    if (!session) return;
    recording = null;
    processing = true;
    clearTimeout(session.timer);
    session.node.port.onmessage = null;
    session.source.disconnect();
    session.node.disconnect();
    session.stream.getTracks().forEach((track) => track.stop());
    mic.setAttribute('aria-pressed', 'false');
    mic.setAttribute('aria-label', 'Start voice command');
    mic.disabled = true;
    message('Recognizing…');
    try {
      const response = await fetch('/api/speech/recognize', {
        method: 'POST', headers: { 'Content-Type': 'audio/wav' },
        body: encodeWav(session.chunks, context.sampleRate), signal: AbortSignal.timeout(25000),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Recognition failed. Please try again.');
      const keys = parseCommands(data.text);
      message(`Heard: “${data.text}”`);
      await onCommands(keys);
    } catch (error) {
      message(error.name === 'TimeoutError' ? 'Speech request timed out. Try again.' : error.message);
    } finally {
      processing = false;
      onBusy(false);
      mic.disabled = false;
    }
  }

  mic.addEventListener('click', async () => {
    if (recording) { await finish(); return; }
    if (starting) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
      message('Microphone needs a browser with audio support on HTTPS or localhost.');
      return;
    }
    starting = true;
    mic.disabled = true;
    onBusy(true);
    cancelSpeech();
    let stream;
    try {
      await unlock();
      message('Allow microphone access…');
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      await context.audioWorklet.addModule(new URL('./recorder-worklet.js', import.meta.url));
      const source = context.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(context, 'calculator-recorder');
      const session = { stream, source, node, chunks: [], frames: 0, lastSound: 0, heardSound: false };
      recording = session;
      node.port.onmessage = ({ data }) => {
        if (recording !== session) return;
        session.chunks.push(data);
        session.frames += data.length;
        const time = session.frames / context.sampleRate;
        const rms = Math.sqrt(data.reduce((sum, value) => sum + value * value, 0) / data.length);
        if (rms > 0.015) { session.heardSound = true; session.lastSound = time; }
        if (session.heardSound && time - session.lastSound > 1.4) void finish();
      };
      source.connect(node);
      node.connect(context.destination); // Worklet emits silence; microphone is never played back.
      session.timer = setTimeout(() => void finish(), 10000);
      mic.setAttribute('aria-pressed', 'true');
      mic.setAttribute('aria-label', 'Finish voice command');
      message('Listening… Say a command, then pause.');
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      recording = null;
      message(error.name === 'NotAllowedError' ? 'Microphone access denied. Allow it in your browser and retry.' : 'Could not start the microphone. Check your audio device and retry.');
      onBusy(false);
    } finally {
      starting = false;
      mic.disabled = false;
    }
  });
  return { speak, unlock, cancelSpeech, setCalculating: (busy) => { if (!recording) mic.disabled = busy || starting || processing; } };
}
