# Felis · A field guide to the cat family

A polished, local website for exploring the Felidae family from a photograph.
Upload a JPEG, PNG, or WebP, receive a closest species suggestion or an explicit
uncertain/no-match result, and explore a cited field guide.

The interface is English, with responsive layouts, keyboard-accessible controls,
real example photographs, a searchable catalogue, and optional JSON observation
exports. Photos are processed in memory and are not saved by the application.
No API key, account, Node.js installation, or frontend build is needed.

## Week 6 assignment: build and run with Cog

The assignment explicitly requires Cog and the tutorial's pretrained ResNet50.
Use this path for the course demonstration; each upload runs **ResNet50
IMAGENET1K_V1** inside Cog as well as the broader Felidae species classifier.
Both outputs appear on the website. ImageNet classes and species suggestions
are kept separate because labels such as “tiger cat” refer to domestic cats.
Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Docker,
and Cog first if they are not already available.

```bash
cd "Week 6/cat_id"
uv sync --frozen
uv run --frozen python scripts/download_models.py
uv run --frozen python scripts/download_resnet.py
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml build web
docker compose stop web  # stop an earlier direct-inference demo, if present
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 240
```

Open **http://127.0.0.1:8000**; Cog serves **http://127.0.0.1:5002/predictions**.
Use Cog 0.23.1 and allocate at least 10 GiB of Docker Desktop VM memory.
The build flag uses a clean Python base instead of inheriting unrelated packages
from Cog's prebuilt image.
The standalone `compose.cog.yaml` connects a web container to a Cog inference
container; only Cog loads the models from its read-only cache. Both services run
offline. See the [assignment and recording guide](docs/assignment.md) for
inside-container logs, the Postman image-upload collection, the three required
AVI filenames, and the code-explanation walkthrough. The recordings still need
to be made; test records do not substitute for the required videos.

## Start the direct local demo

This is an alternative to the assignment stack. If that stack is running, stop
it with `docker compose -f compose.cog.yaml down` from this directory first so
port 8000 and model memory are available.

From the repository root:

```bash
cd "Week 6/cat_id"
./scripts/start.sh
```

Open **http://127.0.0.1:8000**. The footer reports when the local model is ready.
`Ctrl+C` stops the server. The launcher binds to loopback, uses one model worker,
and disables HTTP access logs.

This checkout already has a Python environment and both model checkpoints
cached from development. For a fresh checkout, install
[uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
uv sync --frozen
uv run --frozen python scripts/download_models.py
./scripts/start.sh
```

Use Python 3.11 (selected by `.python-version`). The application supports Python
3.11–3.12. CUDA 12.8 PyTorch wheels are pinned for Linux/Windows; the host driver
must support them. An NVIDIA RTX 4050 Laptop GPU with 6 GB VRAM was used for the
local inference checks. CPU inference was also checked on the host. It is slower and needs
substantial RAM; plan for about 10 GB of available system memory for loading.
The two model files total about 4.5 GB; the CUDA Python environment also needs
several GB of disk space. First-time downloads can take several minutes.

### Offline demonstration

After the download command has succeeded:

```bash
CAT_ID_OFFLINE=1 ./scripts/start.sh
```

Offline mode uses only cached weights and curated local species profiles. All
fonts and example photos are bundled locally. It does not request Wikipedia.
If cached model files are missing, the UI reports that the model cannot start;
it never substitutes fabricated predictions.

### Suggested demonstration

1. Select **Try a cat**, then **Identify this cat**. Open its species profile.
2. Try the tiger example and inspect the three similarity scores.
3. Choose **Not a cat** to demonstrate the explicit no-match result.
4. Open **Field guide**, search `Panthera`, and try the subfamily filter.
5. Read **How it works** for uncertainty, privacy, and catalogue scope.

For a real uncertainty example, `scripts/fetch_evaluation.py` can cache a
caracal photograph at `.cache/evaluation/caracal.jpg`. On the tested model it
stays uncertain between the caracal and African golden cat.

## Models and interpretation

The species classifier uses two freely available, MIT-licensed checkpoints:

- [OpenCLIP ViT-B/32](https://huggingface.co/laion/CLIP-ViT-B-32-laion2B-s34B-b79K)
  compares cat descriptions with non-cat animals, objects, and non-photographic
  alternatives. Weak evidence is rejected before species ranking.
- [BioCLIP 2.5 Huge](https://huggingface.co/imageomics/bioclip-2.5-vith14) ranks
  the supported Felidae descriptions. It is a biodiversity-specific model with
  broader species-name support than an ImageNet classifier. Its published
  benchmarks support this choice, but do not establish accuracy for this app.

Both repositories are pinned to exact revisions in `backend/app/model.py`.
Only safetensors weights and preprocessing configuration are downloaded; remote
Python code and pickle checkpoints are not loaded.

The Cog assignment path additionally uses the exact ResNet50 weight variant in
the [Cog tutorial](https://github.com/replicate/cog/blob/main/docs/getting-started.md).
The official TorchVision checkpoint is SHA-256 verified and loaded using
`torch.load(..., weights_only=True)`. Its 1,000 ImageNet categories are not a
complete Felidae taxonomy. Its softmax scores are separate from BioCLIP cosine
similarities and are not verified identification confidence.

The catalogue contains **41 species concepts from IUCN CCTF 2017**, including
*Felis catus*. It is a versioned reference, not every species proposed by newer
taxonomies. Breeds, hybrids, subspecies, and later splits are not separate
classifier targets. See [taxonomy notes](docs/taxonomy.md).

A similarity score is **not a probability or verified confidence**. The model
compares descriptions, does not locate each animal, and can be wrong. Multiple
animals, small subjects, unusual colour forms, illustrations, and closely related
species are particularly difficult. A no-match result means the evidence was
insufficient, not proof that no cat is present. See the
[model and decision documentation](docs/model.md) for thresholds and limitations.

## Species information

Each species has an independently paraphrased, sourced local profile: scientific
name, genus, subfamily, broad range, habitat, and identification clues. When
online, the server optionally retrieves a Wikipedia summary using a fixed
catalogue article title. It caches successful summaries for 24 hours and falls
back to the local profile on timeout, rate limit, invalid content, or failure.

Only the article title is sent to Wikipedia. Photos, filenames, image embeddings,
and location metadata are not sent. The browser makes no third-party requests
unless you explicitly open a source link. Wikipedia excerpts retain source and
CC BY-SA attribution; taxonomy caveats remain visible beside them.

## Configuration

The application reads environment variables at process start. `.env.example`
is a reference; the host launcher does **not** automatically execute `.env`.

- `CAT_ID_DEVICE=auto`: choose CUDA when available. Use `cpu` or `cuda` to require
  a specific device. A requested but unavailable CUDA device is an explicit error.
- `CAT_ID_OFFLINE=1`: require local weights and disable Wikipedia.
- `CAT_ID_WIKIPEDIA=0`: disable article lookups while allowing model downloads.
- `CAT_ID_MODEL_CACHE=/absolute/path`: override `.cache/models`.
- `CAT_ID_PORT=8001`: change the local launch/Compose port.
- `CAT_ID_LOAD_MODEL=0`: UI-only development; identification is visibly disabled.
- `CAT_ID_COG_URL=http://cog:5000`: delegate web inference to the local Cog service
  (set by `compose.cog.yaml`). With no value, the direct model runs in FastAPI.

Keep **one Uvicorn worker**. Multiple workers load multiple copies of the models
and can exhaust VRAM. The application admits one image-processing request at a
time and returns `429` with `Retry-After` when busy.

## Docker

These are the alternative direct-inference containers. Before switching from
the Cog stack, run `docker compose -f compose.cog.yaml down`; do not leave its
large inference service running alongside another CPU model instance.

A CPU image is the portable default. It uses a separately hashed Linux/Python
3.11 CPU dependency lock, a non-root user, a read-only filesystem and model mount,
and a loopback-only published port. Pre-download the weights on the host first:

```bash
uv run --frozen python scripts/download_models.py
docker compose up --build
# Open http://127.0.0.1:8000
docker compose down
```

The Compose defaults are offline. For a machine with NVIDIA Container Toolkit
configured in Docker:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up --build
docker compose -f compose.yaml -f compose.gpu.yaml down
```

The CPU container has been built and exercised with real model inference. For
Docker Desktop, allocate **at least 10 GiB of VM memory** under Settings →
Resources; the default 4 GiB VM is too small for this model. The container's
`mem_limit: 10g` does not increase the Docker VM's allocation. Leave additional
room if other workloads share the VM.

A working host `nvidia-smi` alone does not make GPU devices available inside
Docker. In the tested Docker Desktop for Linux engine, a GPU request was rejected
because no GPU vendor was available. CPU container inference and host GPU
inference are verified; the CUDA container remains unverified. Docker documents
GPU passthrough through `--gpus` for its Windows/WSL 2 backend; on Linux use a
separately configured Docker Engine with NVIDIA Container Toolkit for that path.
See [Docker's GPU support documentation](https://docs.docker.com/desktop/features/gpu/)
and the [testing record](docs/testing.md).

These original Docker commands use direct FastAPI inference. For assignment
compliance, use the Cog stack at the top of this document. Both share model,
image-validation, and decision modules; the Cog mode adds the tutorial baseline
and an independently accessible prediction API.

## Development and verification

```bash
uv run --frozen pytest -q
node --check frontend/app.js
node --check frontend/ui.js
```

With the server running and ready, browser checks exercise the actual app in a
separate Chromium instance:

```bash
uv run --frozen playwright install chromium
uv run --frozen python scripts/check_browser.py
```

Optional functional model evaluation:

```bash
uv run --frozen python scripts/fetch_evaluation.py  # downloads public test photos
uv run --frozen python scripts/evaluate.py         # calls the running local API
```

The small smoke set is **not a held-out accuracy benchmark**. Results,
screenshots, and exported observations are written to ignored `artifacts/`.
Downloaded evaluation photos are ignored under `.cache/evaluation/`.
Use `CAT_ID_TEST_URL` to select a different local server and `CAT_ID_ARTIFACT_DIR`
to keep runs separate, for example:

```bash
CAT_ID_ARTIFACT_DIR=artifacts/container uv run --frozen python scripts/evaluate.py
CAT_ID_ARTIFACT_DIR=artifacts/container/browser uv run --frozen python scripts/check_browser.py
```

See [testing notes](docs/testing.md) for observed results and verification limits.

## Project structure

```text
backend/app/
  main.py             HTTP routes, startup, admission control, browser protections
  schemas.py          Public API contracts
  images.py           Bounded image validation and metadata removal
  model.py            Pinned model loading, prompt ensembles, local inference
  decision.py         Deterministic acceptance and abstention rules
  knowledge.py        Optional, bounded Wikipedia enrichment with fallback
  catalogue.py        Validated, versioned catalogue loader
  data/               Species profiles and taxonomy provenance
frontend/
  index.html          Semantic page structure
  styles.css          Responsive visual system and reduced-motion rules
  app.js              Upload lifecycle, API requests, navigation, dialogs
  ui.js               Safe DOM rendering helpers
  assets/             Local photos, fonts, and attribution
scripts/              Launch, download, asset refresh, and verification tools
tests/                Model-independent API, safety, and decision tests
docs/                 Architecture, model, API, taxonomy, and test notes
```

## Maintenance and licenses

Use `uv lock` deliberately when updating dependencies, then rerun the relevant
checks. Regenerate the CPU lock with:

```bash
uv pip compile pyproject.toml --no-sources --python-version 3.11 \
  --python-platform x86_64-manylinux_2_28 \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match --generate-hashes \
  --output-file requirements-cpu.lock
```

Keep the `--extra-index-url https://download.pytorch.org/whl/cpu` line in the
CPU lock: Cog reads this same flat dependency file and cannot follow `-r`
includes. The Dockerfile enforces its hashes; Cog resolves the pinned versions
through its own generated requirements/install steps. Check `pip check` inside
the resulting Cog container after dependency updates.

Changes to model revisions, prompts, preprocessing, taxonomy, or thresholds are
model changes and require a fresh evaluation. Never lower rejection thresholds
merely to make a demonstration image pass. A more serious evaluation should use
an independent, labelled set with difficult non-cats, lookalikes, poor lighting,
multiple animals, and out-of-catalogue taxa.

Application source follows the parent repository's [MIT license](../../LICENSE).
Third-party photo licenses and authors are in
[assets/credits.json](frontend/assets/credits.json) and in the website's credits
dialog. Fonts include their SIL OFL license files. Model licenses and Wikipedia
content licenses remain separate from the application source license.
