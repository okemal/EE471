"use strict";

(() => {
  const form = document.querySelector("#tts-form");
  if (!form) return;
  const text = document.querySelector("#speech-text");
  const voice = document.querySelector("#voice");
  const rate = document.querySelector("#rate");
  const generate = document.querySelector("#generate-button");
  const label = document.querySelector("#generate-label");
  const status = document.querySelector("#tts-status");
  const audio = document.querySelector("#audio-player");
  const result = document.querySelector("#audio-result");
  const empty = document.querySelector("#audio-empty");
  const download = document.querySelector("#download-audio");
  const outputPanel = document.querySelector("#text-to-speech-panel .output-panel");
  let audioUrl = null;
  let pending = false;

  function setStatus(message, error = false) {
    status.textContent = message;
    status.classList.toggle("is-error", error);
  }

  function updateCount() {
    document.querySelector("#character-count").textContent = `${Array.from(text.value).length} / ${text.maxLength}`;
  }

  text.addEventListener("input", updateCount);
  rate.addEventListener("input", () => {
    document.querySelector("#rate-value").value = `${Number(rate.value).toFixed(2)}×`;
  });
  document.querySelector("#example-button").addEventListener("click", () => {
    text.value = "Some ideas begin as a whisper. Give them a voice, and see how far they travel. Welcome to Vocal, a little space for your words to come alive.";
    updateCount();
    text.focus();
  });
  document.querySelector("#clear-button").addEventListener("click", () => {
    text.value = "";
    updateCount();
    text.focus();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (pending) return;
    if (form.dataset.configured !== "true") {
      setStatus("Add the Azure Speech key and region on the server, then restart the app.", true);
      return;
    }
    const value = text.value.trim();
    if (!value) {
      setStatus("Write a few words first, then generate your audio.", true);
      text.focus();
      return;
    }

    pending = true;
    generate.disabled = true;
    label.textContent = "Creating audio…";
    form.setAttribute("aria-busy", "true");
    outputPanel.classList.add("is-loading");
    setStatus("Giving your words a voice. This may take a moment…");
    const selectedVoice = voice.options[voice.selectedIndex].text;
    const selectedRate = Number(rate.value);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 100000);

    try {
      const response = await fetch("/api/text-to-speech", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: value, voice: voice.value, rate: selectedRate}),
        signal: controller.signal,
      });
      if (!response.ok) {
        let message = "We couldn’t create the audio. Please try again.";
        try {
          const body = await response.json();
          if (typeof body.error === "string") message = body.error;
        } catch (_) { /* Keep a readable fallback for non-JSON errors. */ }
        throw new Error(message);
      }
      const blob = await response.blob();
      if (!blob.size || !response.headers.get("Content-Type")?.startsWith("audio/")) {
        throw new Error("The speech service returned no playable audio. Please try again.");
      }
      audio.pause();
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = URL.createObjectURL(blob);
      audio.src = audioUrl;
      download.href = audioUrl;
      document.querySelector("#audio-description").textContent = `${selectedVoice} · ${selectedRate.toFixed(2)}× speed`;
      empty.hidden = true;
      result.hidden = false;
      setStatus("Your audio is ready. Play it here or download the WAV file.");
    } catch (error) {
      setStatus(error.name === "AbortError" ? "The request took too long. Please try again." : error.message || "Couldn’t reach the server. Please try again.", true);
    } finally {
      clearTimeout(timeout);
      pending = false;
      generate.disabled = false;
      label.textContent = "Generate speech";
      form.removeAttribute("aria-busy");
      outputPanel.classList.remove("is-loading");
    }
  });

  window.addEventListener("pagehide", () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  });
  updateCount();
})();
