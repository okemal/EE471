# Task 1 — MediaPipe 1.2.3 Python Solutions Showcase

Demonstrates all **22** MediaPipe Tasks solutions listed in the EE471 Week 8 exercise using `mediapipe==1.2.3` on CPU with official public `huggingface.co/litert-community` model bundles (~1.54 GB total, cached in git-ignored `.cache/models/`).

## Layout

- `mediapipe_demos/models.py`: Declarative manifest for all 22 tasks and atomic `httpx` downloader.
- `mediapipe_demos/samples.py`: References `Week 8/input_photos/`, caches official Google MediaPipe sample images (documented in `samples/credits.json`), and synthesizes deterministic speech (`Phonon 31M` -> 16 kHz WAV) and music (`music_16k.wav`) fixtures.
- `mediapipe_demos/visualize.py`: Headless OpenCV/Pillow rendering helpers saving annotated PNGs under `artifacts/outputs/`.
- `demos/*.py`: 22 standalone runnable scripts (one per MediaPipe solution).
- `run_all.py`: Batch downloader and runner generating `artifacts/demo_results.json`.
- `tests/`: Offline unit tests (`test_infrastructure.py`) and 22-task live integration tests (`test_live_demos.py`).

## Commands

```bash
uv sync --frozen
uv run --frozen python run_all.py --list
uv run --frozen python run_all.py --download-only
uv run --frozen python run_all.py --all
uv run --frozen pytest -q
```
