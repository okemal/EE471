import {
  element,
  garmentCard,
  garmentDetails,
  renderBenchmarks,
  renderResult,
} from "./ui.js";

const $ = (selector) => document.querySelector(selector);
const state = {
  catalogue: [],
  benchmark: null,
  file: null,
  previewUrl: null,
  result: null,
  phase: "empty",
  health: null,
  requestId: 0,
  controller: null,
  dialogId: 0,
};

const panel = $("#result-panel");
const dialog = $("#detail-dialog");
const maxBytes = 10 * 1024 * 1024;
let healthTimer;
let toastTimer;

async function request(path, options = {}) {
  const response = await fetch(path, { cache: "no-store", ...options });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The local server returned an unreadable response. Check that it is running.",
    );
  }
  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "The request could not be completed. Please try again.",
    );
  }
  return data;
}

function notify(text) {
  clearTimeout(toastTimer);
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  toastTimer = setTimeout(() => {
    $("#toast").hidden = true;
  }, 5000);
}

function navigate() {
  const route = ["catalogue", "about"].includes(location.hash.slice(1))
    ? location.hash.slice(1)
    : "identify";
  document.querySelectorAll(".view").forEach((view) => {
    view.hidden = view.id !== `${route}-view`;
  });
  document.querySelectorAll("[data-nav]").forEach((link) => {
    const active = link.dataset.nav === route;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.title = `${
    route === "catalogue"
      ? "Garment catalogue"
      : route === "about"
        ? "HPO & Benchmarks"
        : "Garment classifier"
  } — Atelier`;
  window.scrollTo({ top: 0, behavior: "instant" });
}
window.addEventListener("hashchange", navigate);

function renderCatalogue() {
  const query = $("#garment-search").value.trim().toLocaleLowerCase();
  const group = $("#group-filter").value;
  const matches = state.catalogue.filter((item) => {
    const searchable = [
      item.display_name,
      item.label,
      item.category_group,
      ...(item.aliases || []),
    ]
      .join(" ")
      .toLocaleLowerCase();
    return (
      searchable.includes(query) &&
      (group === "all" || item.category_group === group)
    );
  });
  $("#garments-grid").replaceChildren(...matches.map(garmentCard));
  $("#garment-count").textContent =
    `${matches.length} of ${state.catalogue.length} garment categories`;
  $("#empty-search").hidden = matches.length > 0;
}

function showUploadError(message) {
  $("#upload-error").textContent = message;
  $("#upload-error").hidden = !message;
  if (message && state.phase !== "empty") notify(message);
}

function resetPhoto() {
  state.requestId++;
  state.controller?.abort();
  state.controller = null;
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  Object.assign(state, {
    file: null,
    previewUrl: null,
    result: null,
    phase: "empty",
  });
  $("#preview").removeAttribute("src");
  $("#image-input").value = "";
  $("#analysis").hidden = true;
  $("#landing").hidden = false;
  $(".scan-line").hidden = true;
  panel.setAttribute("aria-busy", "false");
  showUploadError("");
  $("#choose-file").focus({ preventScroll: true });
}

async function selectFile(file) {
  if (!file) return;
  if (file.size > maxBytes) {
    showUploadError("This image is too large. Choose a file under 10 MB.");
    return;
  }
  if (!file.size) {
    showUploadError("This file is empty. Choose a JPEG, PNG, or WebP image.");
    return;
  }
  if (
    file.type &&
    !["image/jpeg", "image/png", "image/webp"].includes(file.type)
  ) {
    showUploadError("Please choose a JPEG, PNG, or WebP image.");
    return;
  }
  resetPhoto();
  const id = state.requestId;
  const url = URL.createObjectURL(file);
  state.previewUrl = url;
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    if (id !== state.requestId) return;
    if (
      image.naturalWidth * image.naturalHeight > 20_000_000 ||
      Math.max(image.naturalWidth, image.naturalHeight) > 12_000
    ) {
      throw new Error(
        "Resize this image to 20 megapixels or less before uploading.",
      );
    }
    if (Math.min(image.naturalWidth, image.naturalHeight) < 28) {
      throw new Error("Use an image at least 28 pixels on each side.");
    }
  } catch (error) {
    if (id !== state.requestId) return;
    URL.revokeObjectURL(url);
    state.previewUrl = null;
    showUploadError(
      error.message.includes("image")
        ? error.message
        : "This file could not be read as an image. Try another file.",
    );
    return;
  }
  state.file = file;
  state.phase = "ready";
  $("#preview").src = url;
  $("#file-name").textContent = file.name;
  $("#file-size").textContent = `${Math.max(1, Math.round(file.size / 1024))} KB`;
  $("#landing").hidden = true;
  $("#analysis").hidden = false;
  location.hash = "identify";
  renderReady();
  $("#analysis").scrollIntoView({ behavior: "smooth", block: "start" });
  $("#identify-button").focus({ preventScroll: true });
}

function modelMessage() {
  if (state.health?.status === "ready") {
    return `Ready on ${state.health.device === "cuda" ? "your NVIDIA GPU" : "this computer"}. Side-by-side inference runs locally.`;
  }
  if (state.health?.status === "error") return state.health.error;
  if (state.health?.status === "disabled") {
    return "The model is disabled. Restart with GARMENT_ID_LOAD_MODEL=1 to classify images.";
  }
  if (state.health?.status === "offline-server") {
    return "The local server is unavailable. Start it and this page will reconnect.";
  }
  return "The local garment models are warming up.";
}

function renderReady(error = "") {
  panel.replaceChildren();
  panel.append(element("p", "eyebrow", "READY FOR SIDE-BY-SIDE INFERENCE"));
  const title = element("h1", "", "Compare baseline vs. optimized.");
  title.id = "analysis-title";
  panel.append(
    title,
    element(
      "p",
      "loading-text",
      "Both the 5-epoch Quickstart MLP and the HPO-optimized ConvNet will evaluate your image on a 28×28 grayscale tensor.",
    ),
  );
  const tips = element("ul", "tips-list");
  [
    "Centered garment silhouette with clear edges.",
    "Dark or light plain studio background (light backgrounds are auto-inverted).",
    "Side-by-side confidence, top-3 probabilities, and test accuracy context.",
  ].forEach((tip) => tips.append(element("li", "", tip)));
  panel.append(tips);
  const identify = element("button", "button primary", "Classify garment ↗");
  identify.id = "identify-button";
  identify.dataset.identify = "true";
  identify.disabled = state.health?.status !== "ready";
  const actions = element("div", "result-actions");
  const change = element("button", "text-button", "Choose another image");
  change.dataset.choose = "true";
  actions.append(identify, change);
  panel.append(actions, element("p", "ready-note", modelMessage()));
  if (error) {
    const box = element("div", "error-panel");
    box.setAttribute("role", "alert");
    box.append(element("p", "", error));
    panel.append(box);
  }
}

async function identifyGarment() {
  if (
    !state.file ||
    state.phase === "loading" ||
    state.health?.status !== "ready"
  ) {
    return;
  }
  const id = ++state.requestId;
  state.controller?.abort();
  const controller = new AbortController();
  state.controller = controller;
  state.phase = "loading";
  panel.replaceChildren(
    element("p", "eyebrow", "RUNNING BOTH PYTORCH MODELS"),
    element("div", "loading-orbit"),
  );
  const title = element("h1", "", "Comparing classifiers…");
  title.id = "analysis-title";
  panel.append(
    title,
    element(
      "p",
      "loading-text",
      "Evaluating QuickstartMLP and GarmentConvNet side by side.",
    ),
  );
  const cancel = element("button", "text-button", "Cancel and start again");
  cancel.dataset.reset = "true";
  panel.append(cancel);
  panel.setAttribute("aria-busy", "true");
  $(".scan-line").hidden = false;
  const timeout = setTimeout(() => controller.abort("timeout"), 120_000);
  try {
    const result = await request("/api/identify", {
      method: "POST",
      headers: {
        "Content-Type": state.file.type || "application/octet-stream",
      },
      body: state.file,
      signal: controller.signal,
    });
    if (id !== state.requestId) return;
    state.result = result;
    state.phase = "complete";
    panel.replaceChildren(renderResult(result));
    const heading = $("#analysis-title");
    heading.tabIndex = -1;
    heading.focus({ preventScroll: true });
  } catch (error) {
    if (id !== state.requestId) return;
    state.phase = "ready";
    renderReady(
      controller.signal.aborted
        ? "The inference request timed out. Please try again."
        : error instanceof TypeError
          ? "Could not reach the local server. Check that it is running."
          : error.message,
    );
  } finally {
    clearTimeout(timeout);
    if (id === state.requestId) {
      panel.setAttribute("aria-busy", "false");
      $(".scan-line").hidden = true;
      state.controller = null;
    }
  }
}

async function pollHealth() {
  clearTimeout(healthTimer);
  try {
    state.health = await request("/api/health", {
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    state.health = { status: "offline-server" };
  }
  const ready = state.health.status === "ready";
  const status = $("#model-status");
  status.replaceChildren(
    element(
      "span",
      `status-dot ${ready ? "" : state.health.status === "loading" ? "warming" : "error"}`,
    ),
    document.createTextNode(
      ready
        ? `Local ${state.health.device === "cuda" ? "GPU" : "CPU"} ready`
        : state.health.status === "loading"
          ? "Local models warming up"
          : "Local models unavailable",
    ),
  );
  $("#model-info").textContent = modelMessage();
  const button = $("#identify-button");
  if (button) button.disabled = !ready;
  const note = $(".ready-note");
  if (note) note.textContent = modelMessage();
  healthTimer = setTimeout(pollHealth, ready ? 30_000 : 3000);
}

async function openGarment(id) {
  const item = state.catalogue.find((g) => g.id === id);
  if (!item) return;
  const requestId = ++state.dialogId;
  $("#dialog-content").replaceChildren(garmentDetails(item));
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
  try {
    const data = await request(`/api/garments/${encodeURIComponent(id)}`, {
      signal: AbortSignal.timeout(8000),
    });
    if (requestId === state.dialogId && dialog.open) {
      $("#dialog-content").replaceChildren(garmentDetails(data.garment));
    }
  } catch {
    /* Local cached item is already shown. */
  }
}

async function openCredits() {
  const id = ++state.dialogId;
  const body = element("div", "dialog-body");
  const title = element("h2", "", "Dataset & Model Credits.");
  title.id = "dialog-title";
  body.append(
    element("p", "eyebrow", "PROVENANCE"),
    title,
    element(
      "p",
      "",
      "FashionMNIST is published by Zalando Research (MIT License). Baseline architecture follows the PyTorch Quickstart tutorial; optimized weights were trained via hyperparameter optimization on 54,000 train / 6,000 validation images and verified on 10,000 test images.",
    ),
  );
  $("#dialog-content").replaceChildren(body);
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
  try {
    const credits = await request("/assets/credits.json");
    if (id !== state.dialogId || !dialog.open) return;
    credits.forEach((credit) => {
      const item = element("div", "credit-item");
      item.append(
        element("strong", "", credit.title),
        element("p", "", `${credit.source} · ${credit.license}`),
        element("p", "", credit.notes),
      );
      body.append(item);
    });
  } catch {
    body.append(
      element("p", "", "Asset metadata is stored in frontend/assets/credits.json."),
    );
  }
}

function saveResult() {
  if (!state.result) return;
  const exportData = {
    ...state.result,
    exported_at: new Date().toISOString(),
    dataset: "FashionMNIST",
  };
  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = element("a");
  link.href = url;
  link.download = `atelier-comparison-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function examplePhoto(name, button) {
  const allowed = ["sneaker", "shirt", "ankle-boot", "studio-tee"];
  if (!allowed.includes(name)) return;
  button.disabled = true;
  try {
    const response = await fetch(`/assets/${name}.png`);
    if (!response.ok) throw new Error("Sample unavailable");
    const blob = await response.blob();
    await selectFile(new File([blob], `${name}.png`, { type: "image/png" }));
  } catch {
    showUploadError(
      "The sample image could not load. Please choose an image from your computer.",
    );
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.id === "choose-file" || button.dataset.choose) $("#image-input").click();
  else if (button.id === "start-over" || button.dataset.reset) resetPhoto();
  else if (button.dataset.identify) identifyGarment();
  else if (button.dataset.example) examplePhoto(button.dataset.example, button);
  else if (button.dataset.garment) openGarment(button.dataset.garment);
  else if (button.dataset.navTarget) location.hash = button.dataset.navTarget;
  else if (button.dataset.open === "credits") openCredits();
  else if (button.id === "close-dialog") dialog.close();
  else if (button.id === "save-result") saveResult();
});

dialog.addEventListener("close", () => {
  state.dialogId++;
});
dialog.addEventListener("click", (event) => {
  const rect = dialog.getBoundingClientRect();
  if (
    event.target === dialog &&
    (event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom)
  ) {
    dialog.close();
  }
});

$("#image-input").addEventListener("change", (event) => {
  selectFile(event.target.files[0]);
});
$("#garment-search").addEventListener("input", renderCatalogue);
$("#group-filter").addEventListener("change", renderCatalogue);

const dropzone = $("#dropzone");
let dragDepth = 0;
for (const name of ["dragenter", "dragover", "dragleave", "drop"]) {
  dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    if (name === "dragenter") dragDepth++;
    if (name === "dragleave") dragDepth = Math.max(0, dragDepth - 1);
    if (name === "dragover") event.dataTransfer.dropEffect = "copy";
    if (name === "drop") {
      dragDepth = 0;
      if (event.dataTransfer.files.length !== 1) {
        showUploadError("Choose one garment image at a time.");
      } else {
        selectFile(event.dataTransfer.files[0]);
      }
    }
    dropzone.classList.toggle("dragover", dragDepth > 0);
  });
}

window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());
window.addEventListener("beforeunload", () => {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
});

navigate();
pollHealth();

try {
  const [catData, benchData] = await Promise.all([
    request("/api/garments"),
    request("/api/benchmarks").catch(() => null),
  ]);
  state.catalogue = catData.garments;
  state.benchmark = benchData;
  const featured = ["sneaker", "shirt", "pullover", "ankle-boot"]
    .map((id) => state.catalogue.find((g) => g.id === id))
    .filter(Boolean);
  $("#featured-garments").replaceChildren(...featured.map(garmentCard));
  renderCatalogue();
  if (benchData) renderBenchmarks(benchData);
} catch {
  $("#featured-garments").replaceChildren(
    element(
      "p",
      "",
      "The garment catalogue could not load. Check the local server and refresh the page.",
    ),
  );
  $("#garment-count").textContent =
    "Garment catalogue unavailable — refresh when the server is running.";
}
