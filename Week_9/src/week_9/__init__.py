"""EE471 Week 9 package for Hugging Face Transformers demos and Chapter 2 exercises.

Exports the unified CLI entry point (`main`), legacy model metadata (`MODEL_REGISTRY`,
`ModelEntry`), and the object-oriented inference runner (`Week9Tasks`) shared by
the Task 1 CLI demonstrations and the Task 3 Gradio web application.
"""

from __future__ import annotations

from week_9.cli import MODEL_REGISTRY, ModelEntry, main
from week_9.tasks import Week9Tasks

__all__ = ["MODEL_REGISTRY", "ModelEntry", "Week9Tasks", "main"]
