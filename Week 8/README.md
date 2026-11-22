# EE471 Week 8 — MediaPipe Solutions & Containerized Pose / Face Classifiers

This directory contains the complete Week 8 deliverables for **EE471 — Modern Software Development Practices and Technologies**:

1. **Task 1 ([task1_mediapipe_demos/](task1_mediapipe_demos/))**: Standalone Python demonstrations of all **22** MediaPipe `1.2.3` solutions across **Audio**, **Decision**, **Retrieval**, **Text**, and **Vision**, backed by official public `litert-community` model bundles cached locally in `.cache/models/`.
2. **Task 2 ([task2_arm_pose/](task2_arm_pose/))**: MediaPipe `PoseLandmarker` arm-up classifier (`"left"`, `"right"`, `"both"`, or `"None"` — anatomical perspective) with a CLI entrypoint, hardened Cog `0.23.1` container (port `5004`), and standalone Docker CLI image, tested on `pose-1.jpg`, `pose-2.jpg`, and `pose-3.jpg`.
3. **Task 3 ([task3_face_direction/](task3_face_direction/))**: MediaPipe `FaceLandmarker` looking-direction classifier (`"left"`, `"right"`, or `"straight"` — viewer-relative perspective via 3D facial transformation matrix + 2D symmetry cross-check) with a CLI entrypoint, hardened Cog `0.23.1` container (port `5005`), and standalone Docker CLI image, tested on `face-1.png`, `face-2.png`, and `face-3.png`.

> **Manual Deliverable Note:** Screen-recorded `.avi` videos (`<solution>.avi` for each of the 22 Task 1 demos, `task-2-demo.avi`, `task-2-explanation.avi`, `task-3-demo.avi`, `task-3-explanation.avi`) are user-recorded deliverables and were not autonomously recorded by the agent. The step-by-step commands and walkthrough guides below support recording every required video cleanly.

---

## Quick Setup & Verification Commands

### Task 1 — All 22 MediaPipe Solutions (`task1_mediapipe_demos/`)

```bash
cd "Week 8/task1_mediapipe_demos"
uv sync --frozen
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen python run_all.py --download-only   # caches ~1.54 GB in .cache/models/
uv run --frozen python run_all.py --all             # runs all 22 demos -> artifacts/demo_results.json
uv run --frozen pytest -q                           # offline + live integration checks
```

Run any individual solution standalone (matching its `.avi` deliverable name):

```bash
uv run --frozen python demos/audio_classifier.py
uv run --frozen python demos/audio_transcriber.py
uv run --frozen python demos/text_to_speech.py
uv run --frozen python demos/decision_maker.py
uv run --frozen python demos/semantic_retriever.py
uv run --frozen python demos/universal_embedder.py
uv run --frozen python demos/language_detector.py
uv run --frozen python demos/text_classifier.py
uv run --frozen python demos/text_embedder.py
uv run --frozen python demos/text_proofreader.py
uv run --frozen python demos/text_summarizer.py
uv run --frozen python demos/face_detector.py
uv run --frozen python demos/face_landmarker.py
uv run --frozen python demos/gesture_recognizer.py
uv run --frozen python demos/hand_landmarker.py
uv run --frozen python demos/holistic_landmarker.py
uv run --frozen python demos/image_classifier.py
uv run --frozen python demos/image_embedder.py
uv run --frozen python demos/image_segmenter.py
uv run --frozen python demos/interactive_segmenter.py
uv run --frozen python demos/object_detector.py
uv run --frozen python demos/pose_landmarker.py
```

### Task 2 — Arm-Up Pose Classifier (`task2_arm_pose/`)

```bash
cd "Week 8/task2_arm_pose"
uv sync --frozen
uv run --frozen python scripts/download_model.py
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen pytest --cov=arm_pose --cov=classify_arm --cov=run --cov-report=term-missing

# Direct CLI verification (expected: left, right, both)
uv run --frozen python classify_arm.py ../input_photos/pose-1.jpg
uv run --frozen python classify_arm.py ../input_photos/pose-2.jpg
uv run --frozen python classify_arm.py ../input_photos/pose-3.jpg

# Cog build, CLI predict, and hardened Compose HTTP verification (port 5004)
cog build --use-cog-base-image=false
cog run ee471-week8-arm-pose:cog -i image=@../input_photos/pose-1.jpg
cog run ee471-week8-arm-pose:cog -i image=@../input_photos/pose-2.jpg
cog run ee471-week8-arm-pose:cog -i image=@../input_photos/pose-3.jpg
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 120
uv run --frozen python scripts/verify_cog.py --url http://127.0.0.1:5004
docker compose -f compose.cog.yaml down

# Standalone Docker CLI verification
docker build -t ee471-week8-arm-pose:cli .
docker run --rm -v "$(pwd)/../input_photos:/inputs:ro" ee471-week8-arm-pose:cli /inputs/pose-1.jpg
```

### Task 3 — Face Looking-Direction Classifier (`task3_face_direction/`)

```bash
cd "Week 8/task3_face_direction"
uv sync --frozen
uv run --frozen python scripts/download_model.py
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen pytest --cov=face_direction --cov=classify_face --cov=run --cov-report=term-missing

# Direct CLI verification (expected: left, right, straight)
uv run --frozen python classify_face.py ../input_photos/face-1.png
uv run --frozen python classify_face.py ../input_photos/face-2.png
uv run --frozen python classify_face.py ../input_photos/face-3.png

# Cog build, CLI predict, and hardened Compose HTTP verification (port 5005)
cog build --use-cog-base-image=false
cog run ee471-week8-face-direction:cog -i image=@../input_photos/face-1.png
cog run ee471-week8-face-direction:cog -i image=@../input_photos/face-2.png
cog run ee471-week8-face-direction:cog -i image=@../input_photos/face-3.png
docker compose -f compose.cog.yaml up -d --wait --wait-timeout 120
uv run --frozen python scripts/verify_cog.py --url http://127.0.0.1:5005
docker compose -f compose.cog.yaml down

# Standalone Docker CLI verification
docker build -t ee471-week8-face-direction:cli .
docker run --rm -v "$(pwd)/../input_photos:/inputs:ro" ee471-week8-face-direction:cli /inputs/face-1.png
```

---

## Screen-Recording Guide for Required `.avi` Deliverables

### 1. Task 1 — 22 MediaPipe Solution Videos (`<solution>.avi`)

For each of the 22 solutions (e.g., `audio_classifier.avi`, `pose_landmarker.avi`):
1. Open `Week 8/task1_mediapipe_demos/demos/<solution>.py` in your editor alongside a terminal.
2. Briefly explain the options (`BaseOptions`, task-specific options, running mode) and input data.
3. Run `uv run --frozen python demos/<solution>.py` and show the printed classifications/metrics.
4. For vision/TTS tasks, open the generated file under `artifacts/outputs/` (annotated PNG or `text_to_speech.wav`) to demonstrate the visual/audio result.

### 2. Task 2 — `task-2-demo.avi` & `task-2-explanation.avi`

- **`task-2-demo.avi`**:
  1. Run `classify_arm.py` on `pose-1.jpg` (`left`), `pose-2.jpg` (`right`), and `pose-3.jpg` (`both`), plus `--json` and `--annotate` to display the highlighted green arm overlays.
  2. Demonstrate containerized inference with `cog run ee471-week8-arm-pose:cog -i image=@../input_photos/pose-1.jpg` (and `pose-2.jpg`, `pose-3.jpg`) and/or `docker compose -f compose.cog.yaml up -d --wait` + `uv run --frozen python scripts/verify_cog.py`.
- **`task-2-explanation.avi`**:
  1. Walk through `arm_pose/config.py` (SHA-256 model integrity check, EXIF-safe image loading).
  2. Walk through `arm_pose/classifier.py` (MediaPipe anatomical indices 11–16 & 23–24, torso-scale normalization, wrist/elbow thresholds rejecting chest-level bent arms).
  3. Walk through `classify_arm.py`, `run.py`, `cog.yaml`, `compose.cog.yaml`, and `Dockerfile`.

### 3. Task 3 — `task-3-demo.avi` & `task-3-explanation.avi`

- **`task-3-demo.avi`**:
  1. Run `classify_face.py` on `face-1.png` (`left`, `-34.71°`), `face-2.png` (`right`, `+32.53°`), and `face-3.png` (`straight`, `-2.43°`), showing the annotated direction arrows under `artifacts/annotated/`.
  2. Demonstrate containerized inference via `cog run ee471-week8-face-direction:cog -i image=@../input_photos/face-1.png` (and `face-2.png`, `face-3.png`) and `compose.cog.yaml` + `scripts/verify_cog.py`.
- **`task-3-explanation.avi`**:
  1. Walk through `face_direction/config.py` (SHA-256 verification and angular thresholds).
  2. Walk through `face_direction/classifier.py` (`extract_head_pose_degrees` from MediaPipe's 4×4 facial transformation matrix, `compute_landmark_asymmetry` nose/cheek cross-check, `compute_viewer_gaze_score` eye-look blendshapes, and `NoFaceDetectedError`).
  3. Walk through `classify_face.py`, `run.py`, `cog.yaml`, `compose.cog.yaml`, and `Dockerfile`.
