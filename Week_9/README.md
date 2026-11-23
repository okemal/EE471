# Week 9 — Hugging Face Transformers Suite, Gradio Demo & Chapter 2 Exercises

Complete Python 3.14 package for the **EE471 Week 9** in-class exercises:

- **Task 1**: Ten Hugging Face inference demonstrations (`week-9 task1 <name>` or `week-9 task1 all`).
- **Task 3**: Shared OOP [`Week9Tasks`](src/week_9/tasks.py) module and 10-tab Gradio 6 interactive web app (`week-9 app`).
- **Task 4**: Five Chapter 2 model & tokenizer demonstrations (`week-9 task4 <name>` or `week-9 task4 all`).
- **Legacy pre-assignment demos**: `smollm2`, `opus-mt-fr-en`, `vit`, and `whisper` remain preserved with their original CLI flags and Python APIs.

## Models & Checkpoints

| Task | CLI Subcommand | `Week9Tasks` Method | Hugging Face Checkpoint |
| --- | --- | --- | --- |
| Sentiment analysis | `task1 sentiment` | `analyze_sentiment` | `distilbert/distilbert-base-uncased-finetuned-sst-2-english` |
| Zero-shot classification | `task1 zero-shot` | `classify_zero_shot` | `typeform/distilbert-base-uncased-mnli` |
| Text generation | `task1 generate` | `complete_text` | `HuggingFaceTB/SmolLM2-360M` |
| Mask filling | `task1 fill-mask` | `fill_mask` | `google-bert/bert-base-cased` |
| Named entity recognition | `task1 ner` | `recognize_entities` | `dslim/bert-base-NER` |
| Question answering (NER check) | `task1 qa` | `answer_question` | `deepset/roberta-base-squad2` |
| Summarization | `task1 summarize` | `summarize` | `google-t5/t5-small` |
| French-to-English translation | `task1 translate` | `translate_text` | `Helsinki-NLP/opus-mt-fr-en` |
| Image classification | `task1 image` | `classify_image` | `google/vit-base-patch16-224` |
| Speech recognition | `task1 asr` | `transcribe_audio` | `openai/whisper-large-v3` |
| Legacy FR→EN translation | `opus-mt-fr-en` | — | `Helsinki-NLP/opus-mt-fr-en` |

`Week9Tasks` keeps **at most one active model bundle** in GPU memory at a time and serializes model switches with a lock.

## Setup & Online vs. Offline Execution

1. **Install dependencies** with [`uv`](https://docs.astral.sh/uv/):

   ```bash
   cd Week_9
   uv sync --frozen
   ```

2. **Optional Hugging Face token** (recommended for faster initial downloads; never commit `.env`):

   ```bash
   touch .env
   chmod 600 .env
   # Set HF_TOKEN=<your-read-only-token> inside .env
   ```

3. **Initial online run (populates `~/.cache/huggingface/hub`):**
   On a fresh checkout, run once with network access so all required checkpoints are cached locally:

   ```bash
   uv run --frozen week-9 task1 all
   uv run --frozen week-9 task4 all
   ```

4. **Subsequent offline runs (`HF_HUB_OFFLINE=1`):**
   Once the cache is populated, every Task 1, Task 3, and Task 4 command runs completely offline without Hub access:

   ```bash
   HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 all
   HF_HUB_OFFLINE=1 uv run --frozen week-9 task4 all
   HF_HUB_OFFLINE=1 uv run --frozen week-9 app
   ```

   If a checkpoint is missing from the local cache during an offline run, `Week9Tasks` raises a descriptive error naming the checkpoint to fetch online.

## Usage

### Task 1 & Task 4 CLI

```bash
# List all commands
uv run --frozen week-9 list

# Run individual Task 1 demos (or 'all')
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 sentiment
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 zero-shot
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 generate
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 fill-mask
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 ner
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 qa
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 summarize
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 translate
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 image
HF_HUB_OFFLINE=1 uv run --frozen week-9 task1 asr

# Run individual Task 4 demos (or 'all')
HF_HUB_OFFLINE=1 uv run --frozen week-9 task4 load-save
HF_HUB_OFFLINE=1 uv run --frozen week-9 task4 encode-decode
HF_HUB_OFFLINE=1 uv run --frozen week-9 task4 pad
HF_HUB_OFFLINE=1 uv run --frozen week-9 task4 truncate
HF_HUB_OFFLINE=1 uv run --frozen week-9 task4 special-tokens
```

### Task 3 Gradio Demo & Python API

```bash
HF_HUB_OFFLINE=1 uv run --frozen week-9 app
# Opens on http://127.0.0.1:7860
```

```python
from week_9 import Week9Tasks

tasks = Week9Tasks()
print(tasks.analyze_sentiment().items)
print(tasks.translate_text().translated_text)
```

### Legacy Pre-Assignment Commands

```bash
uv run --frozen week-9 smollm2
uv run --frozen week-9 opus-mt-fr-en
uv run --frozen week-9 vit
uv run --frozen week-9 whisper
```

## Bundled Media Assets & Attributions

Both sample files live in [`src/week_9/assets/`](src/week_9/assets/) and are cataloged in [`src/week_9/assets/credits.json`](src/week_9/assets/credits.json):

- **`dog.jpg`**: [`Golden_Retriever_Dukedestiny01_drvd.jpg`](https://commons.wikimedia.org/wiki/File:Golden_Retriever_Dukedestiny01_drvd.jpg) by Janneke Vreugdenhil (derivative work by Anka Friedrich), **Public domain** (copied unchanged from the Week 6 sample asset).
- **`librispeech_sample.wav`**: 5.50-second mono 16 kHz 16-bit PCM WAV excerpt (`0.00s–5.50s`) extracted from `distil-whisper/librispeech_long` (`clean` / `validation[0]`), originally from the [LibriSpeech ASR corpus](https://www.openslr.org/12/) by Vassil Panayotov et al., licensed under **CC BY 4.0**.

## Development & Verification

```bash
cd Week_9
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
HF_HUB_OFFLINE=1 uv run --frozen pytest -q -m "not live"
```
