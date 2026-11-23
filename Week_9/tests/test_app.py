from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from week_9.app import create_app
from week_9.opus_mt_fr_en import TranslationResult
from week_9.tasks import (
    EnFrTranslationResult,
    FillMaskResult,
    GeneratedCompletion,
    MaskCandidate,
    NamedEntity,
    NerResult,
    QaValidationItem,
    QaValidationResult,
    SentimentAnalysisResult,
    SentimentItem,
    SummarizationResult,
    TextGenerationTaskResult,
    Week9Tasks,
    ZeroShotResult,
    ZeroShotScore,
)
from week_9.vit import ClassificationResult, Prediction
from week_9.whisper import TranscriptChunk, TranscriptionResult


def test_create_app_wires_all_ten_tabs_and_callbacks(tmp_path: Path) -> None:
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"RIFF")

    class FakeTasks(Week9Tasks):
        def analyze_sentiment(self, texts: Any = "") -> SentimentAnalysisResult:
            if isinstance(texts, str) and not texts.strip():
                raise ValueError("texts must be non-empty")
            return SentimentAnalysisResult("m", "cpu", (SentimentItem("Great", "POSITIVE", 0.99),))

        def classify_zero_shot(
            self, text: str = "", candidate_labels: Any = "", **_: Any
        ) -> ZeroShotResult:
            return ZeroShotResult("m", "cpu", text, (ZeroShotScore("finance", 0.91),))

        def complete_text(self, prompt: str = "", **_: Any) -> TextGenerationTaskResult:
            return TextGenerationTaskResult(
                "m",
                "cpu",
                prompt,
                35,
                (
                    GeneratedCompletion(f"{prompt} one.", 10),
                    GeneratedCompletion(f"{prompt} two.", 10),
                ),
            )

        def fill_mask(self, text: str = "", **_: Any) -> FillMaskResult:
            return FillMaskResult(
                "m",
                "cpu",
                text,
                text,
                (MaskCandidate("transformers", 1, 0.8, "To understand transformers."),),
            )

        def recognize_entities(self, text: str = "", **_: Any) -> NerResult:
            return NerResult("m", "cpu", text, (NamedEntity("Nate", "PER", 0.99, 5, 9),))

        def answer_question(
            self, questions: Any = "", context: str = "", **_: Any
        ) -> QaValidationResult:
            return QaValidationResult(
                "qa",
                "ner",
                "cpu",
                context,
                (NamedEntity("Nate", "PER", 0.99, 5, 9),),
                (QaValidationItem("Name?", "Nate", 0.95, 5, 9, "Nate", "PER", True),),
            )

        def summarize(self, text: str = "", **_: Any) -> SummarizationResult:
            return SummarizationResult("m", "cpu", text, "Short summary.")

        def translate_text(self, text: str = "", **_: Any) -> TranslationResult:
            return TranslationResult("m", "cpu", text, "This course is produced by Hugging Face.")

        def translate_to_french(self, text: str = "", **_: Any) -> EnFrTranslationResult:
            return EnFrTranslationResult("m", "cpu", text, "Traduction française.")

        def classify_image(self, image_source: Any = None, **_: Any) -> ClassificationResult:
            pred = Prediction("golden retriever", 207, 0.94)
            return ClassificationResult("m", "cpu", "img", pred, (pred,))

        def transcribe_audio(self, audio_source: Any = None, **_: Any) -> TranscriptionResult:
            return TranscriptionResult(
                "m",
                "cpu",
                "float16",
                str(audio_source),
                "Hello from Whisper.",
                (TranscriptChunk(0.0, 2.0, "Hello from Whisper."),),
            )

    demo = create_app(FakeTasks())
    fn_outputs = []
    for dep in demo.fns.values():
        fn = dep.fn
        if fn is None:
            continue
        name = fn.__name__
        if name == "run_sentiment":
            assert "POSITIVE" in fn("Great")
            assert fn("").startswith("Error:")
        elif name == "run_zero_shot":
            assert "finance" in fn("Text", "finance")
        elif name == "run_generation":
            assert "Completion 2" in fn("Prompt", 35)
        elif name == "run_fill_mask":
            assert "transformers" in fn("Text […] end", 5)
        elif name == "run_ner":
            assert "Nate" in fn("I am Nate.")
        elif name == "run_qa":
            assert "AGREED" in fn("I am Nate.", "Name?")
        elif name == "run_summarize":
            assert "Short summary." in fn("Long text")
        elif name == "run_translate":
            assert "This course is produced by Hugging Face." in fn(
                "Ce cours est produit par Hugging Face."
            )
        elif name == "run_image":
            assert "golden retriever" in fn(Image.new("RGB", (8, 8)), 5)
            assert fn(None, 5).startswith("Error:")
        elif name == "run_asr":
            assert "Hello from Whisper." in fn(str(audio_file))
            assert fn(None).startswith("Error:")
        fn_outputs.append(name)

    assert len(fn_outputs) == 10
