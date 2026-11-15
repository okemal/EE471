# Week 7 Assignment & Recording Guide · Garment Classifier (Task 1)

Checked against `course_materials/Week-7-InClass-Exercise.pdf` (EE 471, 9 November 2026).

## Requirements Covered by `Week 7/garment_id`

1. **PyTorch Quickstart Baseline**: `backend/app/architecture.py:QuickstartMLP` reproduces the tutorial's 3-layer MLP (`Flatten -> 512 -> ReLU -> 512 -> ReLU -> 10`) trained with `SGD(lr=1e-3)`, `batch_size=64`, and 5 epochs (`backend/app/training.py`).
2. **Website Modified from Week 6**: `frontend/` adapts the Week 6 editorial interface into **Atelier**, supporting image upload, bundled sample silhouettes (including light-background studio polarity inversion), a 10-class searchable garment catalogue, and an interactive HPO benchmark page.
3. **Hyperparameter Optimization**: `backend/app/training.py` executes a 6-trial progression across learning rates, optimizers (`SGD`, `SGD+Momentum`, `AdamW`), schedulers (`StepLR`, `CosineAnnealingLR`), batch sizes (`32`, `64`, `128`), dropout, weight decay, and geometric data augmentations (`Flip+Affine`), selecting `GarmentConvNet` on the 6,000-image validation split.
4. **Side-by-Side Comparison UI**: Uploading any garment runs **both** the Quickstart baseline and HPO-optimized CNN on the identical preprocessed 28×28 grayscale tensor, displaying agreement/disagreement, confidence delta, per-class probabilities, and overall test accuracy gap.
5. **Containerized with Cog**: `cog.yaml` and `run.py:Runner` package both verified `safetensors` models behind Cog's HTTP `/predictions` endpoint and connect to the FastAPI web service via `compose.cog.yaml`.

## Build and Run Commands

```bash
cd "Week 7/garment_id"
uv sync --frozen
uv run --frozen python scripts/train_models.py --device cuda
uv run --frozen python scripts/generate_assets.py
cog build --use-cog-base-image=false
docker compose -f compose.cog.yaml build web
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 180
```

Website: **http://127.0.0.1:8000** · Cog API: **http://127.0.0.1:5002/predictions**

## Recording Checklist

### `Task-pre-demo.avi` (Max 5 mins)
Show and run the preliminary basics script explaining Tensors, Datasets & DataLoaders, Transforms, Neural Network Architecture, Optimizer/Backprop, and Save/Load:

```bash
uv run --frozen python scripts/preliminary_basics_demo.py
```

### `Task-1-demo.avi` (Garment Classifier Website + Container Logs + Postman)
1. Show `cog.yaml`, `Dockerfile`, and `compose.cog.yaml`, then run `cog build --use-cog-base-image=false` and `docker compose -f compose.cog.yaml up -d --wait`.
2. Open **http://127.0.0.1:8000**, classify `Sneaker`, `Shirt` (baseline vs. optimized disagreement), and `Studio tee (light bg)`, and show the **HPO & Benchmarks** tab.
3. In a second terminal, exec into the running Cog container and stream live prediction logs while clicking **Classify garment** in the browser:

   ```bash
   docker compose -f compose.cog.yaml exec cog sh
   id
   tail -F /tmp/garment-predictions.jsonl
   ```

4. Prepare a local garment payload for Postman:

   ```bash
   uv run --frozen python scripts/prepare_postman.py frontend/assets/shirt.png
   ```

   Import `docs/postman/Atelier.postman_collection.json` and `artifacts/postman/local.postman_environment.json` into Postman Desktop, select the environment, send **Cog readiness**, and send **Classify uploaded garment** (`POST http://127.0.0.1:5002/predictions`). Expand `output.baseline` and `output.optimized` in the response.

### `Tasks-code-explained.avi` (Max 3 mins, with spoken narration)
Walk concisely through the core AI classification code blocks:
- `backend/app/architecture.py`: `QuickstartMLP`, `GarmentConvNet` (internal normalization + conv/BN/GELU blocks), and `prepare_garment_tensor` (border polarity inversion + square crop).
- `backend/app/training.py`: 54k/6k split, `train_one_epoch`, `evaluate_loader`, `run_trial`, and `save_study_artifacts`.
- `backend/app/model.py` & `run.py`: SHA-256 verification, `DualGarmentClassifier.predict`, and `Runner.run` JSONL logging.
