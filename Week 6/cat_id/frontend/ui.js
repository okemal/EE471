/** DOM helpers: upstream text is always rendered as text, never executable HTML. */
export function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

export function externalLink(text, href, className = "") {
  const link = element("a", className, text);
  try {
    const url = new URL(href);
    if (url.protocol === "https:") link.href = url.href;
  } catch {
    /* Invalid upstream links stay inert. */
  }
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

export const photos = {
  "domestic-cat": "/assets/domestic-cat.jpg",
  "snow-leopard": "/assets/snow-leopard.jpg",
  tiger: "/assets/tiger.jpg",
  lion: "/assets/lion.jpg",
  leopard: "/assets/leopard.jpg",
};

export function speciesCard(species) {
  const card = element("button", "species-card");
  card.dataset.species = species.id;
  card.type = "button";
  card.setAttribute("aria-label", `Explore ${species.common_name}`);
  const picture = element("div", "card-image");
  if (photos[species.id]) {
    const img = element("img");
    img.src = photos[species.id];
    img.alt = "";
    img.loading = "lazy";
    picture.append(img);
  } else {
    picture.append(
      element("span", "taxon-monogram", species.genus.slice(0, 2)),
      element("span", "monogram-label", species.genus.toUpperCase()),
    );
  }
  picture.append(element("span", "card-arrow", "↗"));
  const info = element("div", "card-info");
  info.append(
    element("span", "family-tag", species.subfamily),
    element("h3", "", species.common_name),
    element("p", "", species.scientific_name),
  );
  card.append(picture, info);
  return card;
}

export function facts(species) {
  const list = element("dl", "result-facts");
  for (const [label, value] of [
    ["Range", species.range],
    ["Habitat", species.habitat],
  ]) {
    const group = element("div");
    group.append(element("dt", "", label), element("dd", "", value));
    list.append(group);
  }
  return list;
}

export function taxonomyNote(species) {
  return species.taxonomy_note
    ? element("p", "taxonomy-warning", species.taxonomy_note)
    : null;
}

export function sourceLine(knowledge, species) {
  const line = element("p", "result-source");
  if (knowledge?.live) {
    line.append(
      "Overview: ",
      externalLink("Wikipedia ↗", knowledge.source_url),
      " · CC BY-SA 4.0 · Retrieved ",
      knowledge.retrieved_at.slice(0, 10),
      ". ",
    );
  } else {
    line.append("Overview: local field guide. ");
  }
  line.append(externalLink("Species reference ↗", species.source_url));
  return line;
}

export function candidatesList(candidates, note) {
  const section = element("div", "candidates");
  const heading = element("div", "candidates-heading");
  heading.append(
    element("span", "", "CLOSEST IN THE CATALOGUE"),
    element("span", "", "Similarity ↗"),
  );
  section.append(heading);
  candidates.forEach((candidate, index) => {
    const button = element("button", "candidate");
    button.dataset.species = candidate.species.id;
    const name = element(
      "span",
      "candidate-name",
      candidate.species.common_name,
    );
    name.append(element("i", "", candidate.species.scientific_name));
    button.append(
      element("span", "candidate-rank", String(index + 1).padStart(2, "0")),
      name,
      element("span", "candidate-score", candidate.similarity.toFixed(3)),
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
        ? "✓  Closest visual match"
        : isUncertain
          ? "◌  Identification uncertain"
          : "↳  No reliable match",
    ),
  );
  const title = element(
    "h1",
    "",
    isMatched
      ? result.candidates[0].species.common_name
      : isUncertain
        ? "A cat. But which one?"
        : "A different kind of wild.",
  );
  title.id = "analysis-title";
  content.append(title);
  if (isMatched) {
    const species = result.candidates[0].species;
    content.append(
      element("p", "scientific-name", species.scientific_name),
      element(
        "p",
        "result-description",
        result.knowledge?.text || species.summary,
      ),
      facts(species),
    );
    const note = taxonomyNote(species);
    if (note) content.append(note);
    const actions = element("div", "result-actions");
    const explore = element("button", "button primary", "Meet this species ↗");
    explore.dataset.species = species.id;
    const save = element("button", "text-button", "Save observation ↓");
    save.id = "save-result";
    actions.append(explore, save);
    content.append(actions, sourceLine(result.knowledge, species));
  } else {
    content.append(element("p", "loading-text", result.message));
    if (isUncertain) {
      content.append(
        element(
          "p",
          "result-description",
          "These species share visual features. Compare the possibilities below, or try a sharper photograph with the face and coat clearly visible.",
        ),
      );
    } else {
      content.append(
        element(
          "p",
          "result-description",
          "This photograph didn’t provide enough evidence for a cat-family identification. It may show another animal, an object, or a cat that is difficult to see.",
        ),
      );
      const tips = element("ul", "tips-list");
      [
        "Include one cat, large in the frame.",
        "Use a clear photograph with natural lighting.",
        "Show the face, body, and coat if possible.",
      ].forEach((tip) => tips.append(element("li", "", tip)));
      content.append(tips);
    }
    const retry = element(
      "button",
      "button secondary",
      "Choose another photograph ↗",
    );
    retry.dataset.choose = "true";
    content.append(retry);
  }
  if (result.candidates.length)
    content.append(candidatesList(result.candidates, result.score_note));
  content.append(
    element(
      "p",
      "result-duration",
      `Examined locally · ${result.model} · ${(result.elapsed_ms / 1000).toFixed(1)} s`,
    ),
  );
  return content;
}

export function speciesDetails(species, knowledge) {
  const fragment = document.createDocumentFragment();
  if (photos[species.id]) {
    const image = element("img", "dialog-photo");
    image.src = photos[species.id];
    image.alt = species.common_name;
    fragment.append(image);
  }
  const body = element("div", "dialog-body");
  const title = element("h2", "", species.common_name);
  title.id = "dialog-title";
  body.append(
    element(
      "p",
      "eyebrow",
      `FELIDAE / ${species.subfamily.toUpperCase()} / ${species.genus.toUpperCase()}`,
    ),
    title,
    element("p", "scientific-name", species.scientific_name),
    element("p", "", knowledge?.text || species.summary),
    facts(species),
    element("h3", "", "Clues to look for"),
  );
  const clues = element("ul");
  species.identification.forEach((item) =>
    clues.append(element("li", "", item)),
  );
  body.append(clues);
  const note = taxonomyNote(species);
  if (note) body.append(note);
  body.append(
    sourceLine(knowledge, species),
    element(
      "p",
      "result-source",
      "Catalogue: IUCN CCTF 2017. Names and species boundaries may differ in more recent references.",
    ),
  );
  fragment.append(body);
  return fragment;
}
