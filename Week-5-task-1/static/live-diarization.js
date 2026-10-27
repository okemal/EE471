"use strict";

(() => {
  const panel = document.querySelector(".live-controls");
  if (!panel) return;
  const start = document.querySelector("#live-start");
  const language = document.querySelector("#live-language");
  const status = document.querySelector("#live-status");
  const timer = document.querySelector("#live-timer");
  const partial = document.querySelector("#live-partial");
  const lines = document.querySelector("#live-lines");
  const copy = document.querySelector("#live-copy");
  const download = document.querySelector("#live-download");
  let phase = "idle";
  let attempt = 0;
  let stream = null;
  let context = null;
  let source = null;
  let node = null;
  let socket = null;
  let ticker = null;
  let deadline = null;
  let textUrl = null;
  let elapsedSeconds = 0;
  let turns = [];
  let speakers = new Set();

  function setStatus(message, error = false) {
    status.textContent = message;
    status.classList.toggle("is-error", error);
  }

  function setPhase(value) {
    phase = value;
    language.disabled = phase !== "idle";
    start.disabled = phase === "finishing" || panel.dataset.configured !== "true";
    start.textContent = phase === "starting" ? "Cancel connection" : phase === "live" ? "Stop live session" : phase === "finishing" ? "Finishing transcript…" : "Start live session";
    start.classList.toggle("is-recording", phase === "live");
    panel.setAttribute("aria-busy", String(phase === "starting" || phase === "finishing"));
  }

  function timestamp(seconds) {
    const total = Math.max(0, Math.floor(seconds));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  function exportText() {
    return turns.map(turn => `[${timestamp(turn.offset)}] ${turn.speaker}: ${turn.text}`).join("\n");
  }

  function updateDownload() {
    if (textUrl) URL.revokeObjectURL(textUrl);
    textUrl = null;
    copy.disabled = !turns.length;
    if (turns.length) {
      textUrl = URL.createObjectURL(new Blob([exportText()], {type: "text/plain;charset=utf-8"}));
      download.href = textUrl;
      download.setAttribute("aria-disabled", "false");
    } else {
      download.removeAttribute("href");
      download.setAttribute("aria-disabled", "true");
    }
  }

  function addTurn(turn) {
    turns.push(turn);
    if (turn.speaker !== "Unknown") speakers.add(turn.speaker);
    document.querySelector("#speaker-count").textContent = `${speakers.size} ${speakers.size === 1 ? "SPEAKER" : "SPEAKERS"}`;
    document.querySelector("#live-empty").hidden = true;
    const line = document.createElement("li");
    const heading = document.createElement("div");
    const speaker = document.createElement("strong");
    speaker.className = "speaker-label";
    speaker.textContent = turn.speaker;
    const time = document.createElement("span");
    time.textContent = timestamp(turn.offset);
    heading.append(speaker, time);
    const text = document.createElement("p");
    text.textContent = turn.text;
    line.append(heading, text);
    lines.append(line);
    partial.textContent = "";
    lines.scrollTop = lines.scrollHeight;
    updateDownload();
  }

  function releaseMic() {
    clearInterval(ticker);
    ticker = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    if (source) source.disconnect();
    source = null;
  }

  function cleanup() {
    attempt++;
    releaseMic();
    clearTimeout(deadline);
    deadline = null;
    if (node) node.disconnect();
    node = null;
    if (context) void context.close().catch(() => {});
    context = null;
    if (socket) {
      socket.onclose = null;
      socket.onerror = null;
      socket.onmessage = null;
      socket.onopen = null;
      socket.close();
    }
    socket = null;
    partial.textContent = "";
    timer.textContent = elapsedSeconds ? `Session length · ${timestamp(elapsedSeconds)}` : "Up to 5 minutes per session";
    setPhase("idle");
  }

  function fail(message) {
    attempt++;
    cleanup();
    setStatus(message, true);
  }

  async function stop() {
    if (phase === "idle" || phase === "finishing") return;
    if (phase === "starting") {
      attempt++;
      cleanup();
      setStatus("Live session cancelled. No microphone is recording.");
      return;
    }
    setPhase("finishing");
    const stopping = attempt;
    releaseMic();
    setStatus("Finishing the last speaker turn…");
    if (node) {
      const activeNode = node;
      await new Promise(resolve => {
        const timeout = setTimeout(resolve, 250);
        const flushed = (event) => {
          if (event.data.type === "flushed") {
            clearTimeout(timeout);
            activeNode.port.removeEventListener("message", flushed);
            resolve();
          }
        };
        activeNode.port.addEventListener("message", flushed);
        activeNode.port.postMessage("flush");
      });
    }
    if (stopping !== attempt || phase !== "finishing") return;
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: "stop"}));
    clearTimeout(deadline);
    deadline = setTimeout(() => fail("The session ended before Azure finished. You can still copy the completed lines."), 15000);
  }

  async function begin() {
    if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
      setStatus("Live speaker labels need a recent browser with microphone access on localhost or HTTPS.", true);
      return;
    }
    // Stop any short recording before opening the live microphone.
    document.dispatchEvent(new Event("speech-studio:leave-speech"));
    const current = ++attempt;
    setPhase("starting");
    setStatus("Allow microphone access to connect your live session.");
    try {
      const microphone = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}});
      if (current !== attempt) {
        microphone.getTracks().forEach(track => track.stop());
        return;
      }
      stream = microphone;
      context = new AudioContext();
      const activeContext = context;
      await activeContext.audioWorklet.addModule("/static/pcm-worklet.js");
      if (current !== attempt) return;
      await activeContext.resume();
      if (current !== attempt) return;
      source = activeContext.createMediaStreamSource(stream);
      node = new AudioWorkletNode(activeContext, "pcm-capture");
      node.connect(activeContext.destination);
      socket = new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/live-diarization`);
      const activeSocket = socket;
      node.port.onmessage = (event) => {
        if (event.data.type !== "audio" || activeSocket.readyState !== WebSocket.OPEN) return;
        if (activeSocket.bufferedAmount > 256 * 1024) {
          fail("The connection can’t keep up with microphone audio. Try again on a steadier connection.");
          return;
        }
        activeSocket.send(event.data.buffer);
      };
      activeSocket.onopen = () => {
        if (current === attempt) activeSocket.send(JSON.stringify({type: "start", language: language.value}));
      };
      activeSocket.onmessage = (event) => {
        if (current !== attempt) return;
        let message;
        try { message = JSON.parse(event.data); } catch (_) { fail("The server returned an unreadable live update."); return; }
        if (message.type === "ready") {
          clearTimeout(deadline);
          turns = [];
          speakers = new Set();
          lines.replaceChildren();
          document.querySelector("#live-empty").hidden = false;
          document.querySelector("#speaker-count").textContent = "0 SPEAKERS";
          document.querySelector("#live-copy-status").textContent = "";
          updateDownload();
          source.connect(node);
          setPhase("live");
          elapsedSeconds = 0;
          setStatus("Listening live. Speaker labels appear as Azure recognizes each voice.");
          const started = Date.now();
          timer.textContent = "Live · 0:00 / 5:00";
          ticker = setInterval(() => {
            const seconds = Math.floor((Date.now() - started) / 1000);
            elapsedSeconds = seconds;
            timer.textContent = `Live · ${timestamp(seconds)} / 5:00`;
            if (seconds >= Number(panel.dataset.maxSeconds)) void stop();
          }, 1000);
        } else if (message.type === "partial") {
          partial.textContent = `${message.speaker}: ${message.text}`;
        } else if (message.type === "final") {
          addTurn(message);
        } else if (message.type === "finishing") {
          void stop();
        } else if (message.type === "error") {
          fail(typeof message.error === "string" ? message.error : "The live speech session failed.");
        } else if (message.type === "done") {
          cleanup();
          setStatus(turns.length ? "Session complete. Copy or download the speaker transcript." : "Session complete. No speech was recognized; check the language and try again.", !turns.length);
        }
      };
      activeSocket.onerror = () => {
        if (current === attempt) fail("Couldn’t connect to the live speech service. Check that the Flask server is running.");
      };
      activeSocket.onclose = () => {
        if (current === attempt && phase !== "idle") fail("The live connection closed. Completed speaker turns are still available.");
      };
      deadline = setTimeout(() => fail("The live connection took too long. Check Azure availability and try again."), 15000);
    } catch (error) {
      if (current !== attempt) return;
      fail(error.name === "NotAllowedError" ? "Microphone access was denied. Allow it in browser settings and try again." : error.name === "NotFoundError" ? "No microphone was found. Connect one and try again." : "Couldn’t start live audio. Check microphone access and try a recent browser.");
    }
  }

  start.addEventListener("click", () => { if (phase === "idle") void begin(); else void stop(); });
  document.addEventListener("speech-studio:leave-live", () => { void stop(); });
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(exportText());
      document.querySelector("#live-copy-status").textContent = "Copied to your clipboard.";
    } catch (_) {
      document.querySelector("#live-copy-status").textContent = "Clipboard access was blocked. Download the transcript instead.";
    }
  });
  download.addEventListener("click", event => { if (!turns.length) event.preventDefault(); });
  window.addEventListener("pagehide", () => {
    attempt++;
    cleanup();
    if (textUrl) URL.revokeObjectURL(textUrl);
    textUrl = null;
  });
  window.addEventListener("pageshow", event => { if (event.persisted) updateDownload(); });
})();
