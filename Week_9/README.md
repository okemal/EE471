# Week 9 — Pre-Assignment Hugging Face Model Demos

Reusable Python 3.14 modules and CLI entry points for the four announced EE471 Week 9 Hugging Face models. Because the full assignment specification has not been announced yet, this package establishes a clean, tested, credential-safe foundation ready to build on.

## Announced Models

| CLI Command | Module | Hugging Face Checkpoint | Task | Default Precision (CUDA / CPU) |
| --- | --- | --- | --- | --- |
| `smollm2` | [`src/week_9/smollm2.py`](src/week_9/smollm2.py) | `HuggingFaceTB/SmolLM2-360M` | Causal text generation | `bfloat16` (fallback `float16`) / `float32` |
| `opus-mt-fr-en` | [`src/week_9/opus_mt_fr_en.py`](src/week_9/opus_mt_fr_en.py) | `Helsinki-NLP/opus-mt-fr-en` | French-to-English machine translation | `float32` / `float32` |
| `vit` | [`src/week_9/vit.py`](src/week_9/vit.py) | `google/vit-base-patch16-224` | ImageNet-1K image classification | `float32` / `float32` |
| `whisper` | [`src/week_9/whisper.py`](src/week_9/whisper.py) | `openai/whisper-large-v3` | Automatic speech recognition | `float16` / `float32` |

Supporting modules:

- [`src/week_9/config.py`](src/week_9/config.py) — `.env` loading (`python-dotenv`), `HF_TOKEN` resolution, automatic PyTorch device/dtype selection (`cuda` -> `mps` -> `cpu`), and logging setup.
- [`src/week_9/cli.py`](src/week_9/cli.py) — Unified `week-9` CLI dispatcher and model registry (`MODEL_REGISTRY`).

## Setup & Credentials

1. Install dependencies with [`uv`](https://docs.astral.sh/uv/):

   ```bash
   cd Week_9
   uv sync
   ```

2. Configure your Hugging Face access token in a local, git-ignored `Week_9/.env` file (never commit `.env` or hardcode tokens in source files):

   ```bash
   cp .env.example .env
   chmod 600 .env
   # Edit .env and set HF_TOKEN=<your-read-only-token>
   ```

   Environment variables already exported in your shell take precedence over `Week_9/.env` (`override=False`). `HF_TOKEN` is loaded automatically via [`week_9.config.get_hf_token`](src/week_9/config.py) so authenticated requests avoid Hugging Face Hub rate limits.

## Usage

### Unified CLI (`week-9`)

```bash
# List all announced models
uv run week-9 list

# 1. Text generation (SmolLM2-360M)
uv run week-9 smollm2
uv run week-9 smollm2 --prompt "Explain pointers in C:" --max-new-tokens 128

# 2. French-to-English translation (OPUS-MT)
uv run week-9 opus-mt-fr-en
uv run week-9 opus-mt-fr-en --text "Bonjour tout le monde !"

# 3. Image classification (ViT-Base)
uv run week-9 vit
uv run week-9 vit --image /path/to/photo.jpg --top-k 5

# 4. Speech recognition (Whisper Large v3)
uv run week-9 whisper
uv run week-9 whisper --audio /path/to/speech.wav --language auto --show-timestamps
```

Every model module can also be executed directly with `python -m`:

```bash
uv run python -m week_9.smollm2 --help
uv run python -m week_9.opus_mt_fr_en --help
uv run python -m week_9.vit --help
uv run python -m week_9.whisper --help
```

### Library API

Each module avoids import-time side effects and exposes typed, reusable functions returning frozen dataclasses:

```python
from week_9.opus_mt_fr_en import translate_text
from week_9.smollm2 import generate_text
from week_9.vit import classify_image
from week_9.whisper import transcribe_audio

translation = translate_text("Je voudrais un café, s'il vous plaît.")
print(translation.translated_text)
```

## Key Fixes Applied to the Initial Scripts

- **Credential hygiene**: Removed hardcoded `access_token` literals from all four scripts, stored `HF_TOKEN` in git-ignored `Week_9/.env` (`chmod 600`), and added `.env.example` plus local `.gitignore`.
- **Valid PEP 8 module naming**: Renamed `src/week_9/opus-mt-fr-en.py` to `src/week_9/opus_mt_fr_en.py` so it is a valid importable Python module (while keeping `opus-mt-fr-en` as the CLI subcommand).
- **Device & dtype portability**: Replaced hardcoded `"cuda"` calls in `smollm2.py` and `opus_mt_fr_en.py` and CPU-only execution in `vit.py` with `resolve_device()` (`cuda` -> `mps` -> `cpu`) and `resolve_dtype()` (using native `bfloat16` for SmolLM2 and `float16` for Whisper on CUDA, and `float32` on CPU).
- **Inference safety & memory efficiency**: Added `model.eval()` and `with torch.inference_mode():` across all four models (fixing autograd graph allocation in `vit.py`).
- **SmolLM2 tokenization**: Replaced `tokenizer.encode(...)` with `tokenizer(..., return_tensors="pt")` so `attention_mask` is passed to `model.generate(...)`, and explicitly supplied `pad_token_id=tokenizer.eos_token_id` when unset.
- **ViT image loading & output**: Added request timeouts, `response.raise_for_status()`, context managers to close HTTP responses and image buffers, `.convert("RGB")` normalization, local file support, and softmax top-k probabilities.
- **Whisper Transformers 5.x compatibility**: Cleared deprecated `model.generation_config.forced_decoder_ids`, disabled WordPiece space cleanup (`clean_up_tokenization_spaces=False`) for Whisper's BPE tokenizer, and passed explicit `generate_kwargs` (`task` and `language`).
- **Modularity & documentation**: Separated model loading, inference, and CLI parsing behind `if __name__ == "__main__":`, added full Python 3.14 type hints and Google-style docstrings, and configured Ruff + Pytest.

## Development & Verification

```bash
cd Week_9
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```
