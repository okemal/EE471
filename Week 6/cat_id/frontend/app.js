import {
  element,
  externalLink,
  speciesCard,
  speciesDetails,
  renderResult,
} from "./ui.js";

const $ = (selector) => document.querySelector(selector);
const state = {
  catalogue: [],
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
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "The request could not be completed. Please try again.",
    );
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
  const route = ["field-guide", "about"].includes(location.hash.slice(1))
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
  document.title = `${route === "field-guide" ? "The field guide" : route === "about" ? "How it works" : "Meet your mystery cat"} — Felis`;
  window.scrollTo({ top: 0, behavior: "instant" });
}
window.addEventListener("hashchange", navigate);

function renderCatalogue() {
  const query = $("#species-search").value.trim().toLocaleLowerCase();
  const subfamily = $("#subfamily-filter").value;
  const matches = state.catalogue.filter((item) => {
    const searchable = [
      item.common_name,
      item.scientific_name,
      item.genus,
      ...(item.aliases || []),
    ]
      .join(" ")
      .toLocaleLowerCase();
    return (
      searchable.includes(query) &&
      (subfamily === "all" || item.subfamily === subfamily)
    );
  });
  $("#species-grid").replaceChildren(...matches.map(speciesCard));
  $("#species-count").textContent =
    `${matches.length} of ${state.catalogue.length} species concepts`;
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
    showUploadError("This photo is too large. Choose a file under 10 MB.");
    return;
  }
  if (!file.size) {
    showUploadError(
      "This file is empty. Choose a JPEG, PNG, or WebP photograph.",
    );
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
    if (Math.min(image.naturalWidth, image.naturalHeight) < 32) {
      throw new Error("Use an image at least 32 pixels on each side.");
    }
  } catch (error) {
    if (id !== state.requestId) return;
    URL.revokeObjectURL(url);
    state.previewUrl = null;
    showUploadError(
      error.message.includes("image")
        ? error.message
        : "This file could not be read as an image. Try another photo.",
    );
    return;
  }
  state.file = file;
  state.phase = "ready";
  $("#preview").src = url;
  $("#file-name").textContent = file.name;
  $("#file-size").textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
  $("#landing").hidden = true;
  $("#analysis").hidden = false;
  location.hash = "identify";
  renderReady();
  $("#analysis").scrollIntoView({ behavior: "smooth", block: "start" });
  $("#identify-button").focus({ preventScroll: true });
}

function renderReady(error = "") {
  panel.replaceChildren();
  panel.append(element("p", "eyebrow", "A NEW DISCOVERY STARTS HERE"));
  const title = element("h1", "", "Who’s in your photograph?");
  title.id = "analysis-title";
  panel.append(
    title,
    element(
      "p",
      "loading-text",
      "We’ll look for a cat, then compare its appearance with the species in our field guide.",
    ),
  );
  const tips = element("ul", "tips-list");
  [
    "One cat, clearly visible.",
    "A photograph, with the face and coat in focus.",
    "A closest match — not a guaranteed identification.",
  ].forEach((tip) => tips.append(element("li", "", tip)));
  panel.append(tips);
  const identify = element("button", "button primary", "Identify this cat ↗");
  identify.id = "identify-button";
  identify.dataset.identify = "true";
  identify.disabled = state.health?.status !== "ready";
  const actions = element("div", "result-actions");
  const change = element("button", "text-button", "Choose another photo");
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

function modelMessage() {
  if (state.health?.status === "ready")
    return `Ready on ${state.health.device === "cuda" ? "your NVIDIA GPU" : "this computer"}. Your photo is never saved.`;
  if (state.health?.status === "error") return state.health.error;
  if (state.health?.status === "disabled")
    return "The model is disabled. Restart the server with CAT_ID_LOAD_MODEL=1 to identify photos.";
  if (state.health?.status === "offline-server")
    return "The local server is unavailable. Start it and this page will reconnect.";
  return "The local models are warming up. The first run may take a few minutes while weights download.";
}

async function identifyPhoto() {
  if (
    !state.file ||
    state.phase === "loading" ||
    state.health?.status !== "ready"
  )
    return;
  const id = ++state.requestId;
  state.controller?.abort();
  const controller = new AbortController();
  state.controller = controller;
  state.phase = "loading";
  panel.replaceChildren(
    element("p", "eyebrow", "FOLLOWING THE CLUES"),
    element("div", "loading-orbit"),
  );
  const title = element("h1", "", "A closer look…");
  title.id = "analysis-title";
  panel.append(
    title,
    element(
      "p",
      "loading-text",
      "Checking for a cat, then comparing species. This may take a little longer on a CPU.",
    ),
    element(
      "p",
      "privacy-note",
      "Processing on this computer. Your photo stays here.",
    ),
  );
  const cancel = element("button", "text-button", "Cancel and start again");
  cancel.dataset.reset = "true";
  panel.append(cancel);
  panel.setAttribute("aria-busy", "true");
  $(".scan-line").hidden = false;
  const timeout = setTimeout(() => controller.abort("timeout"), 180_000);
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
        ? "The model took too long to respond. It may still be processing; wait a moment before retrying."
        : error instanceof TypeError
          ? "Could not reach the local server. Check that it is running, then try again."
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
          ? "Local model warming up"
          : "Local model unavailable",
    ),
  );
  $("#model-info").textContent = modelMessage();
  const button = $("#identify-button");
  if (button) button.disabled = !ready;
  const note = $(".ready-note");
  if (note) note.textContent = modelMessage();
  healthTimer = setTimeout(pollHealth, ready ? 30_000 : 3000);
}

async function openSpecies(id) {
  const species = state.catalogue.find((item) => item.id === id);
  if (!species) return;
  const requestId = ++state.dialogId;
  $("#dialog-content").replaceChildren(speciesDetails(species));
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
  try {
    const data = await request(`/api/species/${encodeURIComponent(id)}`, {
      signal: AbortSignal.timeout(8000),
    });
    if (requestId === state.dialogId && dialog.open)
      $("#dialog-content").replaceChildren(
        speciesDetails(data.species, data.knowledge),
      );
  } catch {
    /* The local, cited profile is already visible. */
  }
}

async function openCredits() {
  const id = ++state.dialogId;
  const body = element("div", "dialog-body");
  const title = element("h2", "", "Made with good sources.");
  title.id = "dialog-title";
  body.append(
    element("p", "eyebrow", "ACKNOWLEDGEMENTS"),
    title,
    element(
      "p",
      "",
      "Photography brings this field guide to life. The images below are hosted locally and retain their original credits and licenses.",
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
        element("p", "", `${credit.artist} · ${credit.license}`),
        externalLink("Original photograph ↗", credit.source_url),
        document.createTextNode(" · "),
        externalLink("License ↗", credit.license_url || credit.source_url),
        element("p", "", credit.changes),
      );
      body.append(item);
    });
  } catch {
    body.append(
      element(
        "p",
        "",
        "Photo credits are also available in frontend/assets/credits.json.",
      ),
    );
  }
  body.append(
    element("h3", "", "Science & type"),
    externalLink(
      "IUCN Cat Specialist Group · taxonomy ↗",
      "https://www.catsg.org/classification",
    ),
    element(
      "p",
      "",
      "Species notes are independently paraphrased from the references linked in each profile. Optional article extracts: Wikipedia, CC BY-SA 4.0. BioCLIP 2.5 and OpenCLIP model weights: MIT license. Fonts: Fraunces and DM Sans, SIL Open Font License 1.1.",
    ),
  );
}

function openTaxonomy() {
  state.dialogId++;
  const body = element("div", "dialog-body");
  const title = element("h2", "", "Names evolve, too.");
  title.id = "dialog-title";
  body.append(
    element("p", "eyebrow", "OUR CATALOGUE"),
    title,
    element(
      "p",
      "",
      "Felis uses 41 species concepts from the IUCN Cat Classification Task Force’s 2017 reference: 40 wild species and the domestic cat, across 14 genera.",
    ),
    element(
      "p",
      "",
      "This is a pinned educational reference. Newer research splits some of these concepts into additional species. In particular, pampas cats and tiger cats have unresolved or revised boundaries. The catalogue does not distinguish those newer splits.",
    ),
    element(
      "p",
      "",
      "A species profile flags relevant naming caveats. Wikipedia may describe a more recent or narrower concept. The visual matcher cannot establish ancestry, hybrid status, or locality from a photograph.",
    ),
    externalLink(
      "Read the Cat Specialist Group classification ↗",
      "https://www.catsg.org/classification",
    ),
  );
  $("#dialog-content").replaceChildren(body);
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
}

function saveResult() {
  if (!state.result) return;
  const exportData = {
    ...state.result,
    exported_at: new Date().toISOString(),
    taxonomy: "IUCN CCTF 2017",
    notice:
      "Educational visual suggestion, not a verified species identification. Scores are not probabilities.",
  };
  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = element("a");
  link.href = url;
  link.download = `felis-observation-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function examplePhoto(name, button) {
  const allowed = ["domestic-cat", "tiger", "dog"];
  if (!allowed.includes(name)) return;
  button.disabled = true;
  try {
    const response = await fetch(`/assets/${name}.jpg`);
    if (!response.ok) throw new Error("Example unavailable");
    const blob = await response.blob();
    await selectFile(new File([blob], `${name}.jpg`, { type: "image/jpeg" }));
  } catch {
    showUploadError(
      "The example photo could not load. Please choose a photo from your computer.",
    );
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.id === "choose-file" || button.dataset.choose)
    $("#image-input").click();
  else if (button.id === "start-over" || button.dataset.reset) resetPhoto();
  else if (button.dataset.identify) identifyPhoto();
  else if (button.dataset.example) examplePhoto(button.dataset.example, button);
  else if (button.dataset.species) openSpecies(button.dataset.species);
  else if (button.dataset.scientific)
    openSpecies(
      state.catalogue.find(
        (item) => item.scientific_name === button.dataset.scientific,
      )?.id,
    );
  else if (button.dataset.open === "credits") openCredits();
  else if (button.dataset.open === "taxonomy") openTaxonomy();
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
  )
    dialog.close();
});
$("#image-input").addEventListener("change", (event) => {
  selectFile(event.target.files[0]);
});
$("#species-search").addEventListener("input", renderCatalogue);
$("#subfamily-filter").addEventListener("change", renderCatalogue);
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
      if (event.dataTransfer.files.length !== 1)
        showUploadError("Choose one photograph at a time.");
      else selectFile(event.dataTransfer.files[0]);
    }
    dropzone.classList.toggle("dragover", dragDepth > 0);
  });
}
// Prevent a misplaced drop from navigating away and exposing a local file as a document.
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => event.preventDefault());
window.addEventListener("beforeunload", () => {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
});

navigate();
pollHealth();
try {
  const data = await request("/api/species");
  state.catalogue = data.species;
  const featured = ["domestic-cat", "tiger", "lion", "leopard"]
    .map((id) => state.catalogue.find((s) => s.id === id))
    .filter(Boolean);
  $("#featured-species").replaceChildren(...featured.map(speciesCard));
  renderCatalogue();
} catch {
  $("#featured-species").replaceChildren(
    element(
      "p",
      "",
      "The field guide could not load. Check the local server and refresh the page.",
    ),
  );
  $("#species-count").textContent =
    "Field guide unavailable — refresh when the server is running.";
}
