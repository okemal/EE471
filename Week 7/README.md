# EE471 Week 7 — PyTorch Classification, HPO & Cog Containerization

This directory contains the complete Week 7 deliverables for **EE471 — Modern Software Development Practices and Technologies**:

1. **Task 1 ([garment_id/](garment_id/)) — Atelier**: Local dual-model FashionMNIST garment classifier (`QuickstartMLP` baseline `64.28%` vs. HPO-tuned `GarmentConvNet` `94.61%` test accuracy), modified from the Week 6 `cat_id` web application and containerized with Cog.
2. **Task 2 ([cifar10_id/](cifar10_id/)) — Vision10**: Local dual-model CIFAR-10 classifier (`TutorialCifarNet` baseline `55.80%` vs. HPO-tuned `CifarResNet9` `92.49%` test accuracy), using the same security-hardened side-by-side web + Cog architecture.
3. **1-Page Comparative Performance Report**: [REPORT.md](REPORT.md) and compiled LaTeX PDF [report/week7_performance_report.pdf](report/week7_performance_report.pdf).

> **Manual Deliverable Note:** Screen-recorded demonstration videos (`.avi`) and interactive clicks inside the Postman Desktop GUI are user-recorded deliverables and were not autonomously recorded or clicked by the agent. The step-by-step scripts and Postman payload CLI checks below support recording all four videos cleanly.

## Quick Setup & Verification Commands

### Task 1 (`garment_id` — FashionMNIST)

```bash
cd "Week 7/garment_id"
uv sync --frozen
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen pytest --cov=backend/app --cov=run --cov-report=term-missing
node --check frontend/app.js && node --check frontend/ui.js

# Containerized Cog + Web stack (ports 5002 Cog / 8000 Web)
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
uv run --frozen python scripts/verify_cog.py
GARMENT_ID_ARTIFACT_DIR=artifacts/cog/browser uv run --frozen python scripts/check_browser.py
docker compose -f compose.cog.yaml down
```

### Task 2 (`cifar10_id` — CIFAR-10)

```bash
cd "Week 7/cifar10_id"
uv sync --frozen
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen pytest --cov=backend/app --cov=run --cov-report=term-missing
node --check frontend/app.js && node --check frontend/ui.js

# Containerized Cog + Web stack (ports 5003 Cog / 8001 Web)
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
uv run --frozen python scripts/verify_cog.py
CIFAR10_ID_ARTIFACT_DIR=artifacts/cog/browser uv run --frozen python scripts/check_browser.py
docker compose -f compose.cog.yaml down
```

---

## Screen-Recording Guide for Required `.avi` Deliverables

### 1. `Task-pre-demo.avi` (PyTorch Basics Preliminary Task, <= 5 min)

Demonstrates the six PyTorch fundamentals (`Tensors`, `Datasets & DataLoaders`, `Transforms`, `nn.Module`, `Optimization Loop`, `Save/Load`):

1. Open [garment_id/docs/preliminary-basics.md](garment_id/docs/preliminary-basics.md) alongside a terminal in `Week 7/garment_id`.
2. Run the live walkthrough script:
   ```bash
   uv run --frozen python scripts/preliminary_basics_demo.py
   ```
3. Briefly walk through each printed section (tensor device/shape, FashionMNIST batching, `QuickstartDemoNet` architecture, forward + `CrossEntropyLoss` + `backward()` + `SGD.step()`, and `safetensors` round-trip).

### 2. `Task-1-demo.avi` (Atelier Garment Classifier + Cog + Postman)

1. Start the Task 1 Cog + Web stack and tail inside-container logs in a split terminal:
   ```bash
   cd "Week 7/garment_id"
   docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
   docker compose -f compose.cog.yaml exec cog tail -f /tmp/garment-predictions.jsonl
   ```
2. Open Postman Desktop, import [garment_id/docs/postman/Atelier.postman_collection.json](garment_id/docs/postman/Atelier.postman_collection.json) and `garment_id/artifacts/postman/local.postman_environment.json`, then click **Send** on `POST http://127.0.0.1:5002/predictions` (`shirt.png`: baseline `Pullover` vs. optimized `Shirt` appear in both the Postman JSON response and the tailed `/tmp/garment-predictions.jsonl` terminal).
3. Open `http://127.0.0.1:8000` in the browser: upload `shirt.png` and `sneaker.png`, inspect side-by-side probability bars, browse **Garment catalogue** search/filter, and inspect **HPO & Benchmarks** (`6` trials, `64.28% -> 94.61%`).
4. Stop cleanly: `docker compose -f compose.cog.yaml down`.

### 3. `Task-2-demo.avi` (Vision10 CIFAR-10 Classifier + Cog + Postman)

1. Start the Task 2 Cog + Web stack and tail inside-container logs:
   ```bash
   cd "Week 7/cifar10_id"
   docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
   docker compose -f compose.cog.yaml exec cog tail -f /tmp/cifar10-predictions.jsonl
   ```
2. Import [cifar10_id/docs/postman/Vision10.postman_collection.json](cifar10_id/docs/postman/Vision10.postman_collection.json) and `cifar10_id/artifacts/postman/local.postman_environment.json` into Postman Desktop; click **Send** (`cat.png`: baseline `dog` vs. optimized `cat` logged to `/tmp/cifar10-predictions.jsonl`).
3. Open `http://127.0.0.1:8001` in the browser: test sample pills (`cat`, `airplane`, `ship`), inspect **Classes** catalogue filters, and open **HPO & Benchmarks** (`5` trials, `55.80% -> 92.49%`).
4. Stop cleanly: `docker compose -f compose.cog.yaml down`.

### 4. `Tasks-code-explained.avi` (Technical Code Walkthrough, <= 3 min)

Walk concisely through four files (~45s each):
1. `backend/app/architecture.py` (baseline `QuickstartMLP`/`TutorialCifarNet` vs. HPO CNN `GarmentConvNet`/`CifarResNet9` and `prepare_*_tensor` normalization).
2. `backend/app/training.py` (stratified split, seeded HPO trials, cosine/step LR schedules, augmentation, `safetensors` + SHA-256 export).
3. `run.py` + `cog.yaml` (Cog `Runner`, SHA-256 verification on startup, SSRF URL rejection, structured JSONL logging).
4. `backend/app/main.py` + `frontend/app.js` (EXIF-stripped local validation, FastAPI -> Cog HTTP proxy, side-by-side UI comparison).
