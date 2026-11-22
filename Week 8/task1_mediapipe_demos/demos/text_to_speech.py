"""MediaPipe Text-to-Speech demo (Phonon 31M CPU neural speech synthesis)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp
import numpy as np

from mediapipe_demos.common import build_demo_parser, output_dir, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import DEFAULT_TTS_PROMPT, write_wav_pcm16


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
    prompt: str = DEFAULT_TTS_PROMPT,
) -> dict[str, object]:
    """Synthesize speech to a 24 kHz mono WAV and demonstrate chunked streaming synthesis."""
    _ = input_path
    resolved_model = ensure_model("text_to_speech", model_path=model_path)
    out_dir = output_dir(output_path)
    print_header("Text-to-Speech", "audio", resolved_model)

    cache_dir = Path(tempfile.gettempdir()) / "mediapipe_tts_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    options = mp.tasks.audio.TextToSpeechOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(resolved_model),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        ),
        cache_dir=str(cache_dir),
    )

    with mp.tasks.audio.TextToSpeech.create_from_options(options) as tts:
        voices = [v.voice_id for v in tts.list_voices()]
        result = tts.synthesize(prompt)
        samples = np.asarray(result.samples, dtype=np.float32)
        sample_rate = int(result.sample_rate_hz)

        stream_chunks = list(
            tts.synthesize_stream("MediaPipe streams audio sentences incrementally on device.")
        )

    wav_file = write_wav_pcm16(out_dir / "text_to_speech.wav", samples, sample_rate)
    duration_s = round(len(samples) / max(sample_rate, 1), 2)
    print(f"Prompt:        {prompt}")
    print(f"Voices found:  {voices[:5]} (total {len(voices)})")
    print(f"Synthesized:   {duration_s:.2f}s @ {sample_rate} Hz -> {wav_file}")
    print(f"Stream chunks: {len(stream_chunks)} chunk(s)")

    return {
        "task": "text_to_speech",
        "model": resolved_model.name,
        "voices": voices,
        "sample_rate_hz": sample_rate,
        "duration_s": duration_s,
        "stream_chunks": len(stream_chunks),
        "output_wav": str(wav_file),
    }


def main() -> None:
    parser = build_demo_parser(__doc__, supports_input=False)
    parser.add_argument("--text", default=DEFAULT_TTS_PROMPT, help="Text prompt to synthesize.")
    args = parser.parse_args()
    run_demo(model_path=args.model, output_path=args.output_dir, prompt=args.text)


if __name__ == "__main__":
    main()
