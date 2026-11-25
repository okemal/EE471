"""Gradio 6 interactive web demo for all ten EE471 Week 9 Hugging Face tasks.

Exposes :func:`create_app` to construct a 10-tab ``gradio.Blocks`` interface
backed by a single shared :class:`~week_9.tasks.Week9Tasks` instance so switching
tabs automatically evicts the previous checkpoint on GPU-constrained hosts.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any, Final

import gradio as gr
from PIL import Image

from week_9.config import configure_logging
from week_9.tasks import (
    DEFAULT_AUDIO_PATH,
    DEFAULT_FILL_MASK_TEXT,
    DEFAULT_GENERATION_MAX_WORDS,
    DEFAULT_GENERATION_PROMPT,
    DEFAULT_IMAGE_PATH,
    DEFAULT_NER_QA_CONTEXT,
    DEFAULT_QA_QUESTIONS,
    DEFAULT_SENTIMENT_TEXTS,
    DEFAULT_SUMMARIZATION_TEXT,
    DEFAULT_TRANSLATION_TEXT,
    DEFAULT_ZERO_SHOT_LABELS,
    DEFAULT_ZERO_SHOT_TEXT,
    Week9Tasks,
)

DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 7860


def _format_error(exc: Exception) -> str:
    """Format a validation or runtime exception as a user-facing Gradio message."""
    return f"Error: {exc}"


def create_app(tasks: Week9Tasks | None = None) -> gr.Blocks:
    """Build the 10-tab Gradio Blocks application backed by ``Week9Tasks``.

    Args:
        tasks: Optional pre-configured :class:`Week9Tasks` runner (useful for
            dependency injection in unit tests or custom device selection).
            Creates a new lazy instance when ``None``.

    Returns:
        A configured ``gradio.Blocks`` application ready for ``.queue().launch()``.
    """
    runner = tasks if tasks is not None else Week9Tasks()

    # ------------------------------------------------------------------
    # Gradio event callbacks (each delegates directly to ``Week9Tasks``)
    # ------------------------------------------------------------------

    def run_sentiment(sentences_text: str) -> str:
        """Run sentiment analysis on newline-separated input sentences."""
        try:
            result = runner.analyze_sentiment(sentences_text)
        except (ValueError, RuntimeError) as exc:
            return _format_error(exc)
        lines = [f"Model: {result.model_id} ({result.device})", ""]
        for idx, item in enumerate(result.items, start=1):
            lines.append(f"{idx}. [{item.label} | {item.score:.4f}] {item.text}")
        return "\n".join(lines)

    def run_zero_shot(text: str, labels_csv: str) -> str:
        """Rank comma-separated candidate labels via zero-shot NLI."""
        try:
            result = runner.classify_zero_shot(text, labels_csv)
        except (ValueError, RuntimeError) as exc:
            return _format_error(exc)
        lines = [f"Model: {result.model_id} ({result.device})", ""]
        for rank, item in enumerate(result.labels, start=1):
            lines.append(f"{rank}. {item.label}: {item.score:.4f}")
        return "\n".join(lines)

    def run_generation(prompt: str, max_words: int) -> str:
        """Generate two distinct complete sentences within ``max_words``."""
        try:
            result = runner.complete_text(prompt, max_words=int(max_words))
        except (ValueError, RuntimeError) as exc:
            return _format_error(exc)
        lines = [
            f"Model: {result.model_id} ({result.device}) | Max words: {result.max_words}",
            "",
        ]
        for idx, comp in enumerate(result.completions, start=1):
            lines.append(f"Completion {idx} ({comp.word_count} words):\n{comp.text}\n")
        return "\n".join(lines).strip()

    def run_fill_mask(text: str, top_k: int) -> str:
        """Predict top-k token replacements for a single ``[…]`` or ``[MASK]`` gap."""
        try:
            result = runner.fill_mask(text, top_k=int(top_k))
        except (ValueError, RuntimeError) as exc:
            return _format_error(exc)
        lines = [f"Model: {result.model_id} ({result.device})", ""]
        for rank, cand in enumerate(result.candidates, start=1):
            lines.append(f"{rank}. '{cand.token_str}' ({cand.score:.4f}) -> {cand.sequence}")
        return "\n".join(lines)

    def run_ner(text: str) -> str:
        """Extract grouped person, organization, and location spans from ``text``."""
        try:
            result = runner.recognize_entities(text)
        except (ValueError, RuntimeError) as exc:
            return _format_error(exc)
        lines = [f"Model: {result.model_id} ({result.device})", ""]
        if not result.entities:
            lines.append("No named entities detected.")
            return "\n".join(lines)
        lines.append(
            f"Subject (PER): {', '.join(result.persons) or 'None'} | "
            f"Organization (ORG): {', '.join(result.organizations) or 'None'} | "
            f"Location (LOC): {', '.join(result.locations) or 'None'}"
        )
        lines.append("")
        for ent in result.entities:
            lines.append(
                f"- [{ent.entity_group}] {ent.text!r} "
                f"(chars {ent.start}:{ent.end}, score {ent.score:.4f})"
            )
        return "\n".join(lines)

    def run_qa(context: str, questions_text: str) -> str:
        """Answer newline-separated questions and cross-check answers against NER."""
        try:
            result = runner.answer_question(questions_text, context)
        except (ValueError, RuntimeError) as exc:
            return _format_error(exc)
        lines = [
            f"QA Model: {result.model_id} | NER Model: {result.ner_model_id} ({result.device})",
            "",
        ]
        for idx, item in enumerate(result.items, start=1):
            status = "AGREED" if item.agreed else "DISAGREED"
            ner_desc = (
                f"{item.ner_entity!r} [{item.ner_group}]" if item.ner_entity is not None else "None"
            )
            lines.append(
                f"{idx}. Q: {item.question}\n"
                f"   QA Answer: {item.answer!r} (score {item.score:.4f})\n"
                f"   NER Span : {ner_desc}\n"
                f"   Status   : {status}\n"
            )
        return "\n".join(lines).strip()

    def run_summarize(text: str) -> str:
        """Condense ``text`` into a short summary using T5."""
        try:
            result = runner.summarize(text)
        except (ValueError, RuntimeError) as exc:
            return _format_error(exc)
        return f"Model: {result.model_id} ({result.device})\n\nSummary:\n{result.summary_text}"

    def run_translate(text: str) -> str:
        """Translate French ``text`` into English using OPUS-MT."""
        try:
            result = runner.translate_text(text)
        except (ValueError, RuntimeError) as exc:
            return _format_error(exc)
        return (
            f"Model: {result.model_id} ({result.device})\n\n"
            f"English Translation:\n{result.translated_text}"
        )

    def run_image(image: Image.Image | str | None, top_k: int) -> str:
        """Classify an uploaded or default image into ImageNet-1K categories."""
        if image is None:
            return "Error: Please provide or upload an image."
        try:
            result = runner.classify_image(image, top_k=int(top_k))
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            return _format_error(exc)
        lines = [f"Model: {result.model_id} ({result.device})", ""]
        for rank, pred in enumerate(result.predictions, start=1):
            lines.append(f"{rank}. {pred.label}: {pred.probability:.2%}")
        return "\n".join(lines)

    def run_asr(audio_path: Any) -> str:
        """Transcribe an uploaded or default audio clip with Whisper Large v3."""
        if isinstance(audio_path, dict):
            audio_path = audio_path.get("path") or audio_path.get("name")
        if not audio_path:
            return "Error: Please provide or upload an audio file."
        try:
            result = runner.transcribe_audio(audio_path)
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            return _format_error(exc)
        lines = [
            f"Model: {result.model_id} ({result.device}, {result.dtype})",
            "",
            f"Transcript:\n{result.text}",
        ]
        if result.chunks:
            lines.append("\nTimestamps:")
            for chunk in result.chunks:
                start = f"{chunk.start_s:5.2f}s" if chunk.start_s is not None else " ?.??s"
                end = f"{chunk.end_s:5.2f}s" if chunk.end_s is not None else " ?.??s"
                lines.append(f"[{start} -> {end}] {chunk.text}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Ten-tab Gradio UI layout prefilled with Week 9 assignment inputs
    # ------------------------------------------------------------------

    with gr.Blocks(title="EE471 Week 9 — Hugging Face Transformers Demo") as demo:
        gr.Markdown(
            "# EE471 Week 9 — Hugging Face Transformers Suite\n"
            "Interactive Gradio demo backed by the shared `Week9Tasks` OOP class. "
            "One active model is kept on GPU at a time."
        )

        with gr.Tab("1. Sentiment"):
            with gr.Row():
                sent_in = gr.Textbox(
                    label="Input Sentences (one per line)",
                    value="\n".join(DEFAULT_SENTIMENT_TEXTS),
                    lines=4,
                )
                sent_out = gr.Textbox(label="Sentiment Output", lines=6)
            gr.Button("Analyze Sentiment", variant="primary").click(
                run_sentiment, inputs=sent_in, outputs=sent_out
            )

        with gr.Tab("2. Zero-Shot"):
            with gr.Row():
                with gr.Column():
                    zs_text = gr.Textbox(label="Input Text", value=DEFAULT_ZERO_SHOT_TEXT, lines=3)
                    zs_labels = gr.Textbox(
                        label="Candidate Labels (comma-separated)",
                        value=", ".join(DEFAULT_ZERO_SHOT_LABELS),
                    )
                zs_out = gr.Textbox(label="Ranked Candidate Scores", lines=6)
            gr.Button("Classify Zero-Shot", variant="primary").click(
                run_zero_shot, inputs=[zs_text, zs_labels], outputs=zs_out
            )

        with gr.Tab("3. Generation"):
            with gr.Row():
                with gr.Column():
                    gen_prompt = gr.Textbox(
                        label="Incomplete Prompt",
                        value=DEFAULT_GENERATION_PROMPT,
                        lines=3,
                    )
                    gen_max_words = gr.Slider(
                        label="Maximum Total Words (including prompt)",
                        minimum=10,
                        maximum=60,
                        step=1,
                        value=DEFAULT_GENERATION_MAX_WORDS,
                    )
                gen_out = gr.Textbox(label="Two Distinct Completions", lines=8)
            gr.Button("Generate Completions", variant="primary").click(
                run_generation, inputs=[gen_prompt, gen_max_words], outputs=gen_out
            )

        with gr.Tab("4. Fill-Mask"):
            with gr.Row():
                with gr.Column():
                    fm_text = gr.Textbox(
                        label="Masked Sentence (use one […] or [MASK] gap)",
                        value=DEFAULT_FILL_MASK_TEXT,
                        lines=2,
                    )
                    fm_topk = gr.Slider(
                        label="Top-K Candidates", minimum=1, maximum=10, step=1, value=5
                    )
                fm_out = gr.Textbox(label="Predicted Candidates", lines=7)
            gr.Button("Fill Mask", variant="primary").click(
                run_fill_mask, inputs=[fm_text, fm_topk], outputs=fm_out
            )

        with gr.Tab("5. NER"):
            with gr.Row():
                ner_in = gr.Textbox(
                    label="Passage",
                    value=DEFAULT_NER_QA_CONTEXT,
                    lines=4,
                )
                ner_out = gr.Textbox(label="Detected Entities", lines=8)
            gr.Button("Recognize Entities", variant="primary").click(
                run_ner, inputs=ner_in, outputs=ner_out
            )

        with gr.Tab("6. QA & NER Check"):
            with gr.Row():
                with gr.Column():
                    qa_context = gr.Textbox(
                        label="Context Passage",
                        value=DEFAULT_NER_QA_CONTEXT,
                        lines=4,
                    )
                    qa_questions = gr.Textbox(
                        label="Questions (one per line)",
                        value="\n".join(DEFAULT_QA_QUESTIONS),
                        lines=4,
                    )
                qa_out = gr.Textbox(label="QA Answers vs NER Spans", lines=10)
            gr.Button("Answer & Validate Against NER", variant="primary").click(
                run_qa, inputs=[qa_context, qa_questions], outputs=qa_out
            )

        with gr.Tab("7. Summarization"):
            with gr.Row():
                sum_in = gr.Textbox(
                    label="Source Paragraph",
                    value=DEFAULT_SUMMARIZATION_TEXT,
                    lines=6,
                )
                sum_out = gr.Textbox(label="T5 Summary", lines=6)
            gr.Button("Summarize", variant="primary").click(
                run_summarize, inputs=sum_in, outputs=sum_out
            )

        with gr.Tab("8. Translation (FR→EN)"):
            with gr.Row():
                tr_in = gr.Textbox(
                    label="French Text",
                    value=DEFAULT_TRANSLATION_TEXT,
                    lines=4,
                )
                tr_out = gr.Textbox(label="English Translation", lines=4)
            gr.Button("Translate to English", variant="primary").click(
                run_translate, inputs=tr_in, outputs=tr_out
            )

        with gr.Tab("9. Image (ViT)"):
            with gr.Row():
                with gr.Column():
                    img_in = gr.Image(
                        label="Input Image (default: credited Golden Retriever sample)",
                        value=str(DEFAULT_IMAGE_PATH),
                        type="pil",
                    )
                    img_topk = gr.Slider(
                        label="Top-K Labels", minimum=1, maximum=10, step=1, value=5
                    )
                img_out = gr.Textbox(label="ImageNet Predictions", lines=8)
            gr.Button("Classify Image", variant="primary").click(
                run_image, inputs=[img_in, img_topk], outputs=img_out
            )

        with gr.Tab("10. Speech (Whisper)"):
            with gr.Row():
                asr_in = gr.Audio(
                    label="Input Audio (default: credited LibriSpeech excerpt)",
                    value=str(DEFAULT_AUDIO_PATH),
                    type="filepath",
                )
                asr_out = gr.Textbox(label="Whisper Transcript", lines=8)
            gr.Button("Transcribe Audio", variant="primary").click(
                run_asr, inputs=asr_in, outputs=asr_out
            )

    return demo


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the Week 9 Gradio server."""
    parser = argparse.ArgumentParser(description="Launch the Week 9 Gradio interactive demo.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server host (default: %(default)s).")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Server port (default: %(default)s)."
    )
    parser.add_argument("--device", default=None, help="PyTorch device override (auto, cuda, cpu).")
    parser.add_argument("--share", action="store_true", help="Create a public Gradio share link.")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable informational logging."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI options and launch the Week 9 Gradio web server.

    Args:
        argv: Optional sequence of command-line arguments. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit status code (``0`` on clean shutdown).
    """
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    tasks = Week9Tasks(device=args.device)
    demo = create_app(tasks)
    demo.queue(max_size=16).launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
