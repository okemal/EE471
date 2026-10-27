"use strict";

(() => {
  const form = document.querySelector("#stt-form");
  if (!form) return;
  const fileInput = document.querySelector("#audio-file");
  const dropZone = document.querySelector("#drop-zone");
  const recordButton = document.querySelector("#record-button");
  const recordLabel = document.querySelector("#record-label");
  const recordTimer = document.querySelector("#record-timer");
  const removeButton = document.querySelector("#remove-audio");
  const player = document.querySelector("#source-player");
  const language = document.querySelector("#recognition-language");
  const transcribe = document.querySelector("#transcribe-button");
  const transcribeLabel = document.querySelector("#transcribe-label");
  const status = document.querySelector("#stt-status");
  const transcript = document.querySelector("#transcript");
  const copyButton = document.querySelector("#copy-transcript");
  const download = document.querySelector("#download-transcript");
  const transcriptStatus = document.querySelector("#transcript-status");
  const maxSeconds = Number(form.dataset.maxSeconds) || 60;
  let audioBlob = null;
  let audioUrl = null;
  let textUrl = null;
  let busy = false;
  let recording = false;
  let requestingMic = false;
  let micRequestCancelled = false;
  let recorder = null;
  let stream = null;
  let timerInterval = null;
  let stopTimeout = null;
  let leaving = false;

  function setStatus(message, error = false) {
    status.textContent = message;
    status.classList.toggle("is-error", error);
  }

  function updateControls() {
    const locked = busy || recording || requestingMic;
    fileInput.disabled = locked;
    removeButton.disabled = locked;
    language.disabled = locked;
    recordButton.disabled = busy || requestingMic;
    transcribe.disabled = locked || !audioBlob || form.dataset.configured !== "true";
    dropZone.classList.toggle("is-disabled", locked);
    form.setAttribute("aria-busy", String(busy || requestingMic));
  }

  function updateTranscript() {
    const value = transcript.value;
    const count = value.trim() ? value.trim().split(/\s+/u).length : 0;
    document.querySelector("#word-count").textContent = `${count} ${count === 1 ? "word" : "words"}`;
    copyButton.disabled = !value.trim() || busy;
    if (textUrl) URL.revokeObjectURL(textUrl);
    textUrl = null;
    if (value.trim()) {
      textUrl = URL.createObjectURL(new Blob([value], {type: "text/plain;charset=utf-8"}));
      download.href = textUrl;
      download.setAttribute("aria-disabled", "false");
    } else {
      download.removeAttribute("href");
      download.setAttribute("aria-disabled", "true");
    }
  }

  function clearTranscript() {
    transcript.value = "";
    transcript.disabled = true;
    transcriptStatus.textContent = "";
    updateTranscript();
  }

  function clearAudio() {
    audioBlob = null;
    player.pause();
    player.removeAttribute("src");
    player.load();
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    audioUrl = null;
    document.querySelector("#source-preview").hidden = true;
    clearTranscript();
    updateControls();
  }

  function encodeWav(samples) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const write = (offset, value) => {
      for (let index = 0; index < value.length; index++) view.setUint8(offset + index, value.charCodeAt(index));
    };
    write(0, "RIFF");
    view.setUint32(4, buffer.byteLength - 8, true);
    write(8, "WAVE");
    write(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, 16000, true);
    view.setUint32(28, 32000, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    write(36, "data");
    view.setUint32(40, samples.length * 2, true);
    for (let index = 0; index < samples.length; index++) {
      const sample = Math.max(-1, Math.min(1, samples[index]));
      view.setInt16(44 + index * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
    }
    return new Blob([buffer], {type: "audio/wav"});
  }

  async function loadAudio(file, name) {
    if (busy || recording || requestingMic) return;
    clearAudio();
    busy = true;
    updateControls();
    setStatus("Preparing your audio for a listen…");
    let context = null;
    try {
      if (!file.size) throw new Error("This audio file is empty. Choose another recording.");
      if (file.size > 20 * 1024 * 1024) throw new Error("Choose an audio file smaller than 20 MB.");
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const OfflineContextClass = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      if (!AudioContextClass || !OfflineContextClass) throw new Error("This browser can’t prepare audio. Please use a recent version of Chrome, Firefox, Edge, or Safari.");
      context = new AudioContextClass();
      let decoded;
      try {
        decoded = await context.decodeAudioData(await file.arrayBuffer());
      } catch (_) {
        throw new Error("This browser couldn’t read that recording. Try a WAV or MP3 file.");
      }
      if (!decoded.length || !Number.isFinite(decoded.duration)) throw new Error("This recording contains no readable audio.");
      if (decoded.duration > maxSeconds) throw new Error(`Keep your recording to ${maxSeconds} seconds or less. This one is ${decoded.duration.toFixed(1)} seconds.`);
      const offline = new OfflineContextClass(1, Math.ceil(decoded.duration * 16000), 16000);
      const source = offline.createBufferSource();
      source.buffer = decoded;
      source.connect(offline.destination);
      source.start();
      const normalized = await offline.startRendering();
      if (leaving) return;
      audioBlob = encodeWav(normalized.getChannelData(0));
      audioUrl = URL.createObjectURL(audioBlob);
      player.src = audioUrl;
      document.querySelector("#source-name").textContent = name;
      document.querySelector("#source-details").textContent = `${decoded.duration.toFixed(1)} seconds · Ready to transcribe`;
      document.querySelector("#source-preview").hidden = false;
      setStatus("Audio ready. Listen first, then choose Transcribe audio.");
    } catch (error) {
      setStatus(error.message || "Couldn’t prepare this recording. Please try another file.", true);
    } finally {
      if (context) await context.close().catch(() => {});
      busy = false;
      updateControls();
    }
  }

  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) void loadAudio(file, file.name);
    fileInput.value = "";
  });
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (!busy && !recording && !requestingMic) dropZone.classList.add("is-dragging");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("is-dragging"));
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
    if (busy || recording || requestingMic) return;
    if (event.dataTransfer.files.length !== 1) {
      setStatus("Drop one audio file at a time.", true);
      return;
    }
    const file = event.dataTransfer.files[0];
    void loadAudio(file, file.name);
  });
  removeButton.addEventListener("click", () => {
    clearAudio();
    setStatus("Recording removed. Choose a file or record something new.");
    fileInput.focus();
  });
  language.addEventListener("change", clearTranscript);

  function releaseMic() {
    window.clearInterval(timerInterval);
    window.clearTimeout(stopTimeout);
    timerInterval = null;
    stopTimeout = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }

  function finishRecording() {
    if (recorder && recorder.state !== "inactive") recorder.stop();
    releaseMic();
  }

  recordButton.addEventListener("click", async () => {
    if (recording) {
      recordButton.disabled = true;
      finishRecording();
      return;
    }
    if (busy || requestingMic) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setStatus("Microphone recording isn’t available in this browser. Open this page on localhost in a recent browser, or upload an audio file.", true);
      return;
    }
    micRequestCancelled = false;
    requestingMic = true;
    updateControls();
    setStatus("Allow microphone access in your browser to start recording.");
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio: true});
      if (leaving || micRequestCancelled) {
        releaseMic();
        return;
      }
      clearAudio();
      const mimeType = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find((type) => MediaRecorder.isTypeSupported(type));
      const activeRecorder = new MediaRecorder(stream, mimeType ? {mimeType} : undefined);
      recorder = activeRecorder;
      const chunks = [];
      let failed = false;
      activeRecorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) chunks.push(event.data);
      });
      activeRecorder.addEventListener("error", () => {
        failed = true;
        releaseMic();
        setStatus("The microphone recording failed. Please try again or upload an audio file.", true);
      });
      activeRecorder.addEventListener("stop", () => {
        const type = activeRecorder.mimeType || mimeType || "audio/webm";
        releaseMic();
        recording = false;
        recorder = null;
        recordLabel.textContent = "Record your voice";
        recordTimer.textContent = "Microphone · 55 sec max";
        recordButton.classList.remove("is-recording");
        updateControls();
        if (!failed && !leaving) void loadAudio(new Blob(chunks, {type}), "Microphone recording");
      }, {once: true});
      recorder.start();
      recording = true;
      recordLabel.textContent = "Stop recording";
      recordButton.classList.add("is-recording");
      recordTimer.textContent = "Recording · 0:00 / 0:55";
      const started = Date.now();
      timerInterval = window.setInterval(() => {
        const seconds = Math.min(55, Math.floor((Date.now() - started) / 1000));
        recordTimer.textContent = `Recording · 0:${String(seconds).padStart(2, "0")} / 0:55`;
      }, 1000);
      stopTimeout = window.setTimeout(finishRecording, 55000);
      setStatus("Recording your voice. Stop when you’re ready; recording ends automatically after 55 seconds.");
    } catch (error) {
      releaseMic();
      recording = false;
      const message = error.name === "NotAllowedError" ? "Microphone access was denied. Allow it in your browser settings, or upload an audio file." : error.name === "NotFoundError" ? "No microphone was found. Connect one or upload an audio file." : "Couldn’t start the microphone. Check your browser permissions or upload an audio file.";
      setStatus(message, true);
    } finally {
      requestingMic = false;
      updateControls();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || recording || requestingMic || !audioBlob) return;
    if (form.dataset.configured !== "true") {
      setStatus("Add the Azure Speech key and region on the server, then restart the app.", true);
      return;
    }
    clearTranscript();
    busy = true;
    updateControls();
    transcribeLabel.textContent = "Transcribing…";
    setStatus("Listening for your words. This may take a moment…");
    const body = new FormData();
    body.append("audio", audioBlob, "recording.wav");
    body.append("language", language.value);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 100000);
    try {
      const response = await fetch("/api/speech-to-text", {method: "POST", body, signal: controller.signal});
      let data;
      try { data = await response.json(); } catch (_) { throw new Error("The server returned an unexpected response. Please try again."); }
      if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "Couldn’t transcribe your audio. Please try again.");
      if (typeof data.text !== "string" || !data.text.trim()) throw new Error("No speech was recognized. Try a clearer recording and check the spoken language.");
      transcript.value = data.text;
      transcript.disabled = false;
      setStatus("Your transcript is ready. Review it, make any edits, and take it with you.");
    } catch (error) {
      setStatus(error.name === "AbortError" ? "Transcription took too long. Please try again with a shorter clip." : error.message || "Couldn’t reach the server. Please try again.", true);
    } finally {
      window.clearTimeout(timeout);
      busy = false;
      transcribeLabel.textContent = "Transcribe audio";
      updateControls();
      updateTranscript();
    }
  });

  transcript.addEventListener("input", () => {
    transcriptStatus.textContent = "";
    updateTranscript();
  });
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(transcript.value);
      transcriptStatus.textContent = "Copied to your clipboard.";
    } catch (_) {
      transcript.focus();
      transcript.select();
      transcriptStatus.textContent = "Text selected. Press Ctrl+C (or Command+C) to copy.";
    }
  });
  download.addEventListener("click", (event) => {
    if (download.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
  document.addEventListener("speech-studio:leave-speech", () => {
    micRequestCancelled = true;
    if (recording) finishRecording();
    player.pause();
  });
  window.addEventListener("pagehide", () => {
    leaving = true;
    finishRecording();
    player.pause();
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    if (textUrl) URL.revokeObjectURL(textUrl);
    audioUrl = null;
    textUrl = null;
  });
  window.addEventListener("pageshow", (event) => {
    leaving = false;
    if (event.persisted) {
      if (audioBlob) {
        audioUrl = URL.createObjectURL(audioBlob);
        player.src = audioUrl;
      }
      updateTranscript();
      updateControls();
    }
  });
  updateControls();
})();
