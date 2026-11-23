"""EE471 Week 9 package for pre-assignment Hugging Face model demos.

Provides reusable inference helpers and CLI entry points for the four announced
Week 9 models:

- ``week_9.smollm2``: Causal text generation with ``HuggingFaceTB/SmolLM2-360M``
- ``week_9.opus_mt_fr_en``: French-to-English translation with ``Helsinki-NLP/opus-mt-fr-en``
- ``week_9.vit``: Image classification with ``google/vit-base-patch16-224``
- ``week_9.whisper``: Speech recognition with ``openai/whisper-large-v3``
"""

from __future__ import annotations

from week_9.cli import MODEL_REGISTRY, ModelEntry, main

__all__ = ["MODEL_REGISTRY", "ModelEntry", "main"]
