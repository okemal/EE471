/** Safe DOM rendering helpers for Vision10 (textContent only, never executable HTML). */

export function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "" && text !== null && text !== undefined) node.textContent = String(text);
  return node;
}

export const photos = {
  airplane: "/assets/airplane.png",
  automobile: "/assets/automobile.png",
  bird: "/assets/bird.png",
  cat: "/assets/cat.png",
  deer: "/assets/deer.png",
  dog: "/assets/dog.png",
  frog: "/assets/frog.png",
  horse: "/assets/horse.png",
  ship: "/assets/ship.png",
  truck: "/assets/truck.png",
};

function formatPct(value, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function classCard(item) {
  const card = element("button", "species-card");
  card.dataset.cifarClass = item.id;
  card.type = "button";
  card.setAttribute("aria-label", `Inspect ${item.display_name}`);

  const picture = element("div", "card-image cifar-thumb");
  if (photos[item.id]) {
    const img = element("img");
    img.src = photos[item.id];
    img.alt = "";
    img.loading = "lazy";
    picture.append(img);
  } else {
    picture.append(
      element("span", "taxon-monogram", String(item.class_index).padStart(2, "0")),
      element("span", "monogram-label", item.category_group.toUpperCase()),
    );
  }
  picture.append(element("span", "card-arrow", "↗"));

  const info = element("div", "card-info");
  info.append(
    element("span", "family-tag", `Class ${item.class_index} · ${item.category_group}`),
    element("h3", "", item.display_name),
  );
  if (item.baseline_accuracy != null && item.optimized_accuracy != null) {
    info.append(
      element(
        "p",
        "card-accuracy",
        `Base ${formatPct(item.baseline_accuracy)} → Opt ${formatPct(item.optimized_accuracy)}`,
      ),
    );
  } else {
    info.append(element("p", "", item.label));
  }
  card.append(picture, info);
  return card;
}

function buildModelCard(pred, roleLabel, roleClass, baselineAcc = null) {
  const card = element("article", `model-card ${roleClass}`);
  const header = element("div", "model-card-header");
  header.append(
    element("span", "eyebrow", roleLabel),
    element("span", "accuracy-pill", `Test Acc ${formatPct(pred.test_accuracy)}`),
  );
  card.append(header);

  card.append(element("h3", "model-title", pred.predicted_display_name));

  const sub = element(
    "p",
    "model-subtitle",
    `${pred.architecture} · Confidence ${formatPct(pred.confidence)} · ${pred.elapsed_ms.toFixed(1)} ms`,
  );
  card.append(sub);

  if (baselineAcc !== null) {
    const gain = (pred.test_accuracy - baselineAcc) * 100;
    card.append(
      element(
        "p",
        "gain-badge",
        `${gain >= 0 ? "+" : ""}${gain.toFixed(1)} pp test accuracy vs. baseline`,
      ),
    );
  }

  const barList = element("div", "prob-bars");
  for (const item of pred.top_classes) {
    const row = element("div", "prob-row");
    const labelLine = element("div", "prob-label-line");
    labelLine.append(
      element("span", "", item.display_name),
      element("span", "prob-val", formatPct(item.probability)),
    );
    const track = element("div", "prob-track");
    const fill = element("div", "prob-fill");
    fill.style.width = `${Math.max(2, Math.round(item.probability * 100))}%`;
    track.append(fill);
    row.append(labelLine, track);
    barList.append(row);
  }
  card.append(barList);

  const hp = pred.hyperparameters;
  const hpLine = `optimizer=${hp.optimizer}, lr=${hp.learning_rate}, batch=${hp.batch_size}, epochs=${hp.epochs}`;
  card.append(element("p", "hyperparam-note", hpLine));
  return card;
}

export function candidatesList(candidates, note) {
  const section = element("div", "candidates");
  const heading = element("div", "candidates-heading");
  heading.append(
    element("span", "", "TOP CANDIDATES (OPTIMIZED VS. BASELINE)"),
    element("span", "", "Opt / Base"),
  );
  section.append(heading);
  candidates.forEach((candidate, index) => {
    const button = element("button", "candidate");
    button.dataset.cifarClass = candidate.cifar_class.id;
    const name = element("span", "candidate-name", candidate.cifar_class.display_name);
    name.append(
      element(
        "i",
        "",
        `Class ${candidate.cifar_class.class_index} · ${candidate.cifar_class.category_group}`,
      ),
    );
    button.append(
      element("span", "candidate-rank", String(index + 1).padStart(2, "0")),
      name,
      element(
        "span",
        "candidate-score",
        `${formatPct(candidate.probability)} / ${formatPct(candidate.baseline_probability)}`,
      ),
    );
    section.append(button);
  });
  section.append(element("p", "score-note", note));
  return section;
}

export function renderResult(result) {
  const content = document.createDocumentFragment();
  const isMatched = result.status === "matched";
  const isUncertain = result.status === "uncertain";

  content.append(
    element(
      "span",
      `result-tag ${isMatched ? "" : isUncertain ? "uncertain" : "no-match"}`,
      isMatched
        ? "✓  Confident optimized match"
        : isUncertain
          ? "◌  Uncertain subject"
          : "↳  Low confidence",
    ),
  );

  const primary = result.candidates[0]?.cifar_class;
  const title = element(
    "h1",
    "",
    primary ? result.optimized.predicted_display_name : "Unrecognized image",
  );
  title.id = "analysis-title";
  content.append(title);

  if (primary) {
    content.append(
      element(
        "p",
        "scientific-name",
        `CIFAR-10 Class ${primary.class_index} · ${primary.category_group}`,
      ),
      element("p", "result-description", result.message),
    );
    const actions = element("div", "result-actions");
    const inspect = element("button", "button primary", "Inspect class clues ↗");
    inspect.dataset.cifarClass = primary.id;
    const save = element("button", "text-button", "Save comparison ↓");
    save.id = "save-result";
    const retry = element("button", "text-button", "Try another image");
    retry.dataset.choose = "true";
    actions.append(inspect, save, retry);
    content.append(actions);
  }

  const comparisonSection = element("section", "comparison-section");
  comparisonSection.id = "comparison-panel";
  const verdict = element(
    "div",
    `comparison-verdict ${result.comparison.agreement ? "agree" : "disagree"}`,
  );
  verdict.append(
    element(
      "strong",
      "",
      result.comparison.agreement ? "Models Agree" : "Models Disagree",
    ),
    element("span", "", result.comparison.summary),
  );
  comparisonSection.append(verdict);

  const grid = element("div", "comparison-grid");
  grid.append(
    buildModelCard(result.baseline, "BASELINE · TUTORIAL NET", "baseline-card"),
    buildModelCard(
      result.optimized,
      "OPTIMIZED · HPO RESNET-9",
      "optimized-card",
      result.baseline.test_accuracy,
    ),
  );
  comparisonSection.append(grid);
  content.append(comparisonSection);

  if (result.candidates.length) {
    content.append(candidatesList(result.candidates, result.score_note));
  }

  const prepLabel = result.diagnostics?.center_cropped
    ? "Center-cropped & resized to 32×32 RGB"
    : "Normalized to 32×32 RGB tensor";
  content.append(
    element(
      "p",
      "result-duration",
      `${prepLabel} · ${result.model} · ${result.elapsed_ms} ms`,
    ),
  );
  return content;
}

export function classDetails(item) {
  const fragment = document.createDocumentFragment();
  if (photos[item.id]) {
    const image = element("img", "dialog-photo cifar-dialog-photo");
    image.src = photos[item.id];
    image.alt = item.display_name;
    fragment.append(image);
  }
  const body = element("div", "dialog-body");
  const title = element("h2", "", item.display_name);
  title.id = "dialog-title";
  body.append(
    element(
      "p",
      "eyebrow",
      `CIFAR-10 CLASS ${item.class_index} / ${item.category_group.toUpperCase()}`,
    ),
    title,
    element("p", "scientific-name", `Canonical label: "${item.label}"`),
    element("p", "", item.summary),
  );

  if (item.baseline_accuracy != null && item.optimized_accuracy != null) {
    const facts = element("dl", "result-facts");
    for (const [label, value] of [
      ["Baseline Test Acc", formatPct(item.baseline_accuracy)],
      ["Optimized Test Acc", formatPct(item.optimized_accuracy)],
    ]) {
      const group = element("div");
      group.append(element("dt", "", label), element("dd", "", value));
      facts.append(group);
    }
    body.append(facts);
  }

  body.append(element("h3", "", "Visual cues at 32×32"));
  const clues = element("ul");
  item.visual_clues.forEach((entry) => clues.append(element("li", "", entry)));
  body.append(clues);

  body.append(element("h3", "", "Common model confusions"));
  const confusions = element("ul");
  item.common_confusions.forEach((entry) => confusions.append(element("li", "", entry)));
  body.append(confusions);

  body.append(element("p", "taxonomy-warning", item.imaging_notes));
  fragment.append(body);
  return fragment;
}

export function renderBenchmarks(benchmark) {
  const kpiGrid = document.getElementById("benchmark-kpis");
  const hpoBody = document.getElementById("hpo-table-body");
  const classBody = document.getElementById("per-class-table-body");
  if (!kpiGrid || !hpoBody || !classBody) return;

  const baseAcc = benchmark.baseline.test_accuracy;
  const optAcc = benchmark.optimized.test_accuracy;
  const gain = (optAcc - baseAcc) * 100;

  kpiGrid.replaceChildren(
    ...[
      ["Tutorial Baseline", formatPct(baseAcc, 2), `${benchmark.baseline.optimizer} · ${benchmark.baseline.epochs} epochs`],
      ["HPO-Optimized ResNet-9", formatPct(optAcc, 2), `${benchmark.optimized.optimizer} · ${benchmark.optimized.epochs} epochs`],
      ["Accuracy Improvement", `+${gain.toFixed(2)} pp`, `${benchmark.trials.length} experiments on ${benchmark.device.toUpperCase()}`],
      ["Error Reduction", `${(((1 - optAcc) / Math.max(1e-6, 1 - baseAcc) - 1) * -100).toFixed(1)}%`, `${(100 - optAcc * 100).toFixed(2)}% residual test error`],
    ].map(([label, metric, sub]) => {
      const card = element("div", "kpi-card");
      card.append(
        element("span", "eyebrow", label),
        element("strong", "kpi-value", metric),
        element("span", "kpi-sub", sub),
      );
      return card;
    }),
  );

  hpoBody.replaceChildren(
    ...benchmark.trials.map((t) => {
      const tr = element("tr", t.role === "optimized" ? "row-highlight" : t.role === "baseline" ? "row-baseline" : "");
      for (const cellText of [
        t.name,
        t.architecture,
        `${t.optimizer}${t.scheduler !== "none" ? ` + ${t.scheduler}` : ""}`,
        String(t.learning_rate),
        String(t.batch_size),
        String(t.epochs),
        t.augmentation,
        formatPct(t.best_val_accuracy, 2),
        formatPct(t.test_accuracy, 2),
      ]) {
        tr.append(element("td", "", cellText));
      }
      return tr;
    }),
  );

  classBody.replaceChildren(
    ...benchmark.per_class_accuracy.map((row) => {
      const tr = element("tr");
      const delta = (row.delta * 100).toFixed(2);
      for (const cellText of [
        String(row.class_index),
        row.display_name,
        row.category_group,
        formatPct(row.baseline_accuracy, 2),
        formatPct(row.optimized_accuracy, 2),
        `${row.delta >= 0 ? "+" : ""}${delta} pp`,
      ]) {
        tr.append(element("td", "", cellText));
      }
      return tr;
    }),
  );
}
