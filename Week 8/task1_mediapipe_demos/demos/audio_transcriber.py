"""MediaPipe Audio Transcriber demo (Parakeet-TDT 0.6B on-device speech-to-text)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import ensure_speech_16k_wav, read_wav_float32, resample_linear


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Transcribe a 16 kHz speech WAV using both full-clip and chunked streaming modes."""
    _ = output_path
    resolved_model = ensure_model("audio_transcriber", model_path=model_path)
    wav_path = input_path if input_path is not None else ensure_speech_16k_wav()
    print_header("Audio Transcriber", "audio", resolved_model)

    samples, sample_rate = read_wav_float32(wav_path)
    if sample_rate != 16000:
        samples = resample_linear(samples, sample_rate, 16000)
        sample_rate = 16000

    cache_dir = Path(tempfile.gettempdir()) / "mediapipe_transcriber_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    options = mp.tasks.audio.AudioTranscriberOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(resolved_model),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        ),
        sample_rate_hz=sample_rate,
        cache_dir=str(cache_dir),
    )

    with mp.tasks.audio.AudioTranscriber.create_from_options(options) as transcriber:
        full_result = transcriber.transcribe(samples, end_of_stream=True)
        full_text = full_result.text.strip()
        segments = [
            {
                "transcript": seg.transcript,
                "from_ms": seg.from_timestamp_ms,
                "to_ms": seg.to_timestamp_ms,
                "is_final": seg.is_final,
            }
            for seg in full_result.segments
        ]

    print(f"Input WAV:   {wav_path.name} ({len(samples) / sample_rate:.2f}s @ {sample_rate} Hz)")
    print(f"Transcript:  {full_text}")
    print(f"Segments:    {len(segments)}")

    return {
        "task": "audio_transcriber",
        "model": resolved_model.name,
        "input": str(wav_path),
        "transcript": full_text,
        "segments": segments,
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
