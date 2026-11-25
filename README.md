# EE471 — Modern Software Development Practices and Technologies

Course portfolio for **EE471**, organized chronologically by weekly in-class exercises and projects. Each assignment directory is self-contained with its own setup instructions, source code, and verification tests.

## Assignment Index

| Week | Task / Section | Location | Stack & Highlights | Default Port(s) | Documentation |
| --- | --- | --- | --- | --- | --- |
| Weeks 1–2 | Cap-flipping puzzle & Git workflow | [`conform.py`](conform.py) | Python (`pleaseConform`, `pleaseConformOnepass`, `announce`) | CLI | — |
| Week 3 | Library OOP foundations | [`Week3/`](Week3/README.md) | Python 3.12+ (`MediaItem`, `Book`, `DVD`, `LibraryCollection`) | CLI | [Week3 README](Week3/README.md) |
| Week 4 | Sec 1 · Web Calculator | [`Week4/section_1/`](Week4/section_1/README.md) | Flask, HTML/CSS/JS, Figma design, `POST /api/calculate` | `5000` | [Week4 README](Week4/README.md) · [Prompts](Week4/section_1/PROMPTS.md) |
| Week 4 | Sec 2 · Library Collection | [`Week4/section_2/`](Week4/section_2/README.md) | Flask REST API (`/api/items`, CRUD, checkout/return) & SPA | `5000` | [Section 2 README](Week4/section_2/README.md) · [Prompts](Week4/section_2/PROMPTS.md) |
| Week 5 | Task 1 · Vocal Speech Studio | [`Week-5-task-1/`](Week-5-task-1/README.md) | Flask, Azure Speech REST & SDK, WebSocket live diarization (`uv`) | `5000` | [README](Week-5-task-1/README.md) · [Workflow](Week-5-task-1/WORKFLOW.md) · [Walkthrough](Week-5-task-1/docs/CODE_WALKTHROUGH.md) |
| Week 5 | Task 2 · Voice Calculator | [`Week-5-task-2/`](Week-5-task-2/README.md) | Flask, Azure STT/TTS REST, Web Audio `AudioWorklet` | `5000` | [README](Week-5-task-2/README.md) · [Guide](Week-5-task-2/DOCUMENTATION.md) |
| Week 6 | Task 1 · Dockerized Speech Apps | [`Week 6/speech_docker/`](Week%206/speech_docker/README.md) | Docker Compose, Gunicorn, non-root read-only containers, file secrets | `5000`, `5001` | [Week 6 README](Week%206/README.md) · [README](Week%206/speech_docker/README.md) · [Testing](Week%206/speech_docker/TESTING.md) |
| Week 6 | Task 2 · Felis Cat Classifier | [`Week 6/cat_id/`](Week%206/cat_id/README.md) | FastAPI + Cog (`ResNet50` + `OpenCLIP` + `BioCLIP 2.5`), 41 Felidae profiles | `8000`, `5002` | [README](Week%206/cat_id/README.md) · [Assignment](Week%206/cat_id/docs/assignment.md) · [Testing](Week%206/cat_id/docs/testing.md) |
| Week 7 | Task 1 · Atelier Garment Classifier | [`Week 7/garment_id/`](Week%207/garment_id/README.md) | FashionMNIST dual-model (`QuickstartMLP` vs HPO `GarmentConvNet`), FastAPI + Cog | `8000`, `5002` | [Week 7 README](Week%207/README.md) · [Report](Week%207/REPORT.md) · [PDF Report](Week%207/report/week7_performance_report.pdf) |
| Week 7 | Task 2 · Vision10 CIFAR-10 Classifier | [`Week 7/cifar10_id/`](Week%207/cifar10_id/README.md) | CIFAR-10 dual-model (`TutorialCifarNet` vs HPO `CifarResNet9`), FastAPI + Cog | `8001`, `5003` | [README](Week%207/cifar10_id/README.md) · [Model Study](Week%207/cifar10_id/docs/model.md) · [Testing](Week%207/cifar10_id/docs/testing.md) |
| Week 8 | Task 1 · 22 MediaPipe Solutions | [`Week 8/task1_mediapipe_demos/`](Week%208/task1_mediapipe_demos/README.md) | `mediapipe==1.2.3` across Audio, Decision, Retrieval, Text, and Vision (`uv`) | CLI | [Week 8 README](Week%208/README.md) · [Task 1 README](Week%208/task1_mediapipe_demos/README.md) |
| Week 8 | Task 2 · Arm-Up Pose Classifier | [`Week 8/task2_arm_pose/`](Week%208/task2_arm_pose/README.md) | MediaPipe `PoseLandmarker` (`left`/`right`/`both`/`None`), CLI + Docker/Cog | `5004` | [Task 2 README](Week%208/task2_arm_pose/README.md) |
| Week 8 | Task 3 · Face Direction Classifier | [`Week 8/task3_face_direction/`](Week%208/task3_face_direction/README.md) | MediaPipe `FaceLandmarker` (`left`/`right`/`straight`), CLI + Docker/Cog | `5005` | [Task 3 README](Week%208/task3_face_direction/README.md) |
| Week 9 | Transformers, Gradio & Tokenizers | [`Week_9/`](Week_9/README.md) | Hugging Face Transformers (`Week9Tasks` OOP, 10 tasks), Gradio 6 UI, Ch. 2 tokenizers (`uv`) | `7860` | [Week 9 README](Week_9/README.md) |

---

## Shared Prerequisites & Credentials

- **Python**: Python 3.11–3.14 (`uv` is used for dependency locking in Weeks 5–9; standard `pip` / `venv` is supported in Week 4 and Week 5 Task 2).
- **Azure Speech Services (Weeks 5 & 6 Task 1)**: Live speech features require `AZURE_SPEECH_KEY` (or `AZURE_API_KEY_1`) and `AZURE_SPEECH_REGION` in a local, git-ignored `.env` file (see project `.env.example` templates). Automated test suites mock Azure and run offline without credentials.
- **Docker, Cog, and Node.js**:
  - **Docker Desktop / Engine + Compose** and **Cog (`0.23.1`)** are used in Week 6 and Week 7. For `Week 6/cat_id`, allocate at least 10 GiB of memory to the Docker VM when running CPU BioCLIP inference.
  - **Node.js** runs browser-side unit tests (`node --test`) in Week 5 Task 2 / Week 6 Task 1 and syntax checks (`node --check`) in Weeks 6–7.

---

## Weekly Summaries & Quick Commands

### Weeks 1–2 — Algorithmic Warmup & Git Workflow ([`conform.py`](conform.py))

Implements minimal cap-flipping command announcements in one pass (`pleaseConformOnepass`) and with bareheaded (`H`) group handling (`pleaseConform`).

```bash
python3 conform.py
```

### Week 3 — Object-Oriented Programming ([`Week3/`](Week3/README.md))

Defines the `MediaItem`, `Book`, `DVD`, and `LibraryCollection` hierarchy in `custom_classes.py` and simulates checkout behavior in `main.py`.

```bash
cd Week3 && python3 main.py
```

### Week 4 — Web UI & Flask REST Backends ([`Week4/`](Week4/README.md))

Two independent Figma-to-Flask exercises:
- **Section 1** ([`Week4/section_1/`](Week4/section_1/README.md)): Calculator web app backed by `POST /api/calculate` using `Calculator` (`custom_classes.py`).
- **Section 2** ([`Week4/section_2/`](Week4/section_2/README.md)): Library management SPA backed by REST endpoints (`GET/POST/PUT/PATCH/DELETE /api/items`, `/checkout`, `/return`) and domain exceptions (`ItemNotFoundError`, `ItemStateError`).

```bash
cd Week4/section_1 && python3 -m pip install -r requirements.txt && python3 app.py
# or
cd Week4/section_2 && python3 -m pip install -r requirements.txt && python3 app.py
```

### Week 5 — Cloud Speech Services & Merge Workflows

- **Task 1 — Vocal Speech Studio** ([`Week-5-task-1/`](Week-5-task-1/README.md)): Built across sequential `text-to-speech` and `speech-to-text` feature branches with documented merge-conflict resolution ([`WORKFLOW.md`](Week-5-task-1/WORKFLOW.md)), then extended with continuous SDK translation, pronunciation assessment, and real-time WebSocket speaker diarization.
  ```bash
  cd Week-5-task-1 && uv sync && uv run pytest
  uv run flask --app app run --host 127.0.0.1 --port 5000
  ```
- **Task 2 — Voice Calculator** ([`Week-5-task-2/`](Week-5-task-2/README.md)): Extends the Week 4 calculator with browser `AudioWorklet` PCM WAV capture, Azure STT command parsing, and ordered Azure TTS spoken feedback.
  ```bash
  cd Week-5-task-2
  python3 -m unittest discover -s tests -v
  node --test tests/commands.test.mjs
  ```

### Week 6 — Containerization & Cog Model Serving ([`Week 6/`](Week%206/README.md))

- **Task 1 — Dockerized Speech Apps** ([`Week 6/speech_docker/`](Week%206/speech_docker/README.md)): Packages `Week-5-task-1` (port `5000`) and `Week-5-task-2` (port `5001`) behind Gunicorn in hardened, non-root, read-only containers with Docker Compose file secrets (`configure.py`).
- **Task 2 — Felis Cat Classifier** ([`Week 6/cat_id/`](Week%206/cat_id/README.md)): Classifies uploaded photos using a FastAPI gateway (`127.0.0.1:8000`) delegating to a Cog inference container (`127.0.0.1:5002/predictions`) running TorchVision `ResNet50` (`IMAGENET1K_V1`) alongside an `OpenCLIP ViT-B/32` non-cat gate and `BioCLIP 2.5 Huge` over 41 IUCN CCTF 2017 Felidae species profiles.

### Week 7 — PyTorch Classification, HPO & Cog ([`Week 7/`](Week%207/README.md))

Compares baseline PyTorch tutorial networks against hyperparameter-optimized CNNs side by side in FastAPI + Cog containers, summarized in [`Week 7/REPORT.md`](Week%207/REPORT.md) and [`Week 7/report/week7_performance_report.pdf`](Week%207/report/week7_performance_report.pdf):
- **Task 1 — Atelier (`garment_id`)**: FashionMNIST `QuickstartMLP` (`64.28%`) vs. HPO-tuned `GarmentConvNet` (`94.61%`, `+30.33 pp`) on ports `8000` (Web) and `5002` (Cog).
- **Task 2 — Vision10 (`cifar10_id`)**: CIFAR-10 `TutorialCifarNet` (`55.80%`) vs. HPO-tuned `CifarResNet9` (`92.49%`, `+36.69 pp`) on ports `8001` (Web) and `5003` (Cog).

```bash
cd "Week 7/garment_id" && uv run --frozen ruff check . && uv run --frozen pytest -q
cd "Week 7/cifar10_id" && uv run --frozen ruff check . && uv run --frozen pytest -q
```

### Week 8 — MediaPipe Solutions & Containerized Pose / Face Classifiers ([`Week 8/`](Week%208/README.md))

Demonstrates all 22 MediaPipe `1.2.3` Python solutions and packages two MediaPipe vision classifiers with Docker and Cog:
- **Task 1 — 22 MediaPipe Solutions** ([`Week 8/task1_mediapipe_demos/`](Week%208/task1_mediapipe_demos/README.md)): Standalone runnable scripts across Audio (`AudioClassifier`, `AudioTranscriber`, `TextToSpeech`), Decision (`DecisionMaker`), Retrieval (`SemanticRetriever`, `UniversalEmbedder`), Text (`LanguageDetector`, `TextClassifier`, `TextEmbedder`, `TextProofreader`, `TextSummarizer`), and Vision (11 tasks) using official public `litert-community` bundles.
- **Task 2 — Arm-Up Pose Classifier** ([`Week 8/task2_arm_pose/`](Week%208/task2_arm_pose/README.md)): Classifies `"left"`, `"right"`, `"both"`, or `"None"` via MediaPipe `PoseLandmarker` (`pose-1..3.jpg` -> `left`, `right`, `both`), containerized with Cog (`5004`) and standalone Docker CLI.
- **Task 3 — Face Direction Classifier** ([`Week 8/task3_face_direction/`](Week%208/task3_face_direction/README.md)): Classifies `"left"`, `"right"`, or `"straight"` via MediaPipe `FaceLandmarker` 3D head-pose matrix (`face-1..3.png` -> `left`, `right`, `straight`), containerized with Cog (`5005`) and standalone Docker CLI.

```bash
cd "Week 8/task1_mediapipe_demos" && uv run --frozen ruff check . && uv run --frozen pytest -q
cd "Week 8/task2_arm_pose" && uv run --frozen ruff check . && uv run --frozen pytest -q
cd "Week 8/task3_face_direction" && uv run --frozen ruff check . && uv run --frozen pytest -q
```

### Week 9 — Hugging Face Transformers, Gradio Demo & Tokenizers ([`Week_9/`](Week_9/README.md))

Implements the Hugging Face LLM Course Chapter 1 and Chapter 2 exercises in a unified Python 3.14 package:
- **Tasks 1 & 3 — Shared OOP Inference & Gradio 6 Web App**: [`Week9Tasks`](Week_9/src/week_9/tasks.py) runs sentiment analysis, zero-shot NLI, constrained SmolLM2 text generation, BERT mask filling, Unicode-accurate NER, RoBERTa QA validation, T5 summarization, French-to-English OPUS-MT translation, ViT image classification, and Whisper Large v3 ASR through both `week-9 task1 <name>` and a 10-tab Gradio interface (`week-9 app` on `127.0.0.1:7860`) while keeping a single model bundle on the GPU at a time.
- **Task 4 — Chapter 2 Model & Tokenizer Exercises**: [`task4.py`](Week_9/src/week_9/task4.py) demonstrates `save_pretrained` / local offline reload, WordPiece encoding & decoding, batch padding with `attention_mask`, sequence truncation, and automatic `[CLS]`/`[SEP]` plus custom `<EE471>` special-token embedding resizing (`week-9 task4 <name>`).

```bash
cd Week_9 && uv run --frozen ruff check . && HF_HUB_OFFLINE=1 uv run --frozen pytest -q -m "not live"
```

---

## Repository Notes

- **Course materials & transcripts**: Local assignment PDFs (`course_materials/`) and archived AI coding transcripts (`transcripts/`) are excluded via [`.gitignore`](.gitignore).
- **License**: Application source code is licensed under the [MIT License](LICENSE); model weights, fonts, and bundled images carry their respective attributions documented within each project.
