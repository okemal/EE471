"use strict";

(() => {
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));

  function activate(tab, moveFocus = false) {
    const previous = tabs.find(candidate => candidate.getAttribute("aria-selected") === "true");
    const wasSpeech = document.querySelector("#speech-to-text-tab").getAttribute("aria-selected") === "true";
    const willBeSpeech = tab.id === "speech-to-text-tab";
    if (wasSpeech && !willBeSpeech) {
      document.dispatchEvent(new Event("speech-studio:leave-speech"));
    }
    if (previous?.id === "live-diarization-tab" && previous !== tab) {
      document.dispatchEvent(new Event("speech-studio:leave-live"));
    }
    document.querySelectorAll("audio").forEach((audio) => audio.pause());
    for (const candidate of tabs) {
      const selected = candidate === tab;
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
      candidate.classList.toggle("mode-active", selected);
      document.getElementById(candidate.getAttribute("aria-controls")).hidden = !selected;
    }
    if (moveFocus) tab.focus();
    history.replaceState(null, "", `#${tab.id.replace(/-tab$/, "")}`);
  }

  for (const [index, tab] of tabs.entries()) {
    tab.addEventListener("click", () => activate(tab));
    tab.addEventListener("keydown", (event) => {
      let next;
      if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
      if (event.key === "ArrowLeft") next = tabs[(index + tabs.length - 1) % tabs.length];
      if (event.key === "Home") next = tabs[0];
      if (event.key === "End") next = tabs[tabs.length - 1];
      if (next) {
        event.preventDefault();
        activate(next, true);
      }
    });
  }

  function activateFromHash() {
    activate(tabs.find(tab => `#${tab.id.replace(/-tab$/, "")}` === location.hash) || tabs[0]);
  }

  window.addEventListener("hashchange", activateFromHash);
  if (location.hash) activateFromHash();
})();
