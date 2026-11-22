"""Sample image and audio fixture helpers for Task 1 MediaPipe demos."""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from mediapipe_demos.models import PROJECT_ROOT, ensure_model

WEEK8_INPUT_PHOTOS = PROJECT_ROOT.parent / "input_photos"
DEFAULT_SAMPLES_DIR = PROJECT_ROOT / ".cache" / "samples"

REMOTE_SAMPLE_URLS: dict[str, str] = {
    "thumbs_up.jpg": (
        "https://storage.googleapis.com/mediapipe-tasks/gesture_recognizer/thumbs_up.jpg"
    ),
    "victory.jpg": (
        "https://storage.googleapis.com/mediapipe-tasks/gesture_recognizer/victory.jpg"
    ),
    "woman_hands.jpg": (
        "https://storage.googleapis.com/mediapipe-tasks/hand_landmarker/woman_hands.jpg"
    ),
    "cat_and_dog.jpg": (
        "https://storage.googleapis.com/mediapipe-tasks/object_detector/cat_and_dog.jpg"
    ),
    "burger.jpg": ("https://storage.googleapis.com/mediapipe-tasks/image_classifier/burger.jpg"),
}

DEFAULT_TTS_PROMPT = (
    "Hello from Izmir Institute of Technology. This is the EE 471 Week 8 MediaPipe demonstration."
)


def samples_dir() -> Path:
    """Return the local cache directory for downloaded and synthesized samples."""
    override = os.environ.get("MEDIAPIPE_DEMOS_SAMPLE_DIR")
    target = Path(override) if override else DEFAULT_SAMPLES_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def input_photo(filename: str) -> Path:
    """Return a path inside `Week 8/input_photos/`."""
    path = WEEK8_INPUT_PHOTOS / filename
    if not path.is_file():
        raise FileNotFoundError(f"Expected Week 8 input photo not found: {path}")
    return path


def ensure_sample_image(filename: str, *, cache_dir: Path | None = None) -> Path:
    """Ensure a sample image exists locally, downloading official MediaPipe assets if needed."""
    if (WEEK8_INPUT_PHOTOS / filename).is_file():
        return WEEK8_INPUT_PHOTOS / filename

    target_dir = cache_dir or samples_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / filename

    if filename == "burger_crop.jpg":
        if destination.is_file() and destination.stat().st_size > 0:
            return destination
        source = ensure_sample_image("burger.jpg", cache_dir=target_dir)
        with Image.open(source) as img:
            w, h = img.size
            crop = img.crop((int(w * 0.12), int(h * 0.12), int(w * 0.88), int(h * 0.88)))
            crop.convert("RGB").save(destination, format="JPEG", quality=92)
        return destination

    if destination.is_file() and destination.stat().st_size > 0:
        return destination

    if filename not in REMOTE_SAMPLE_URLS:
        raise KeyError(f"Unknown sample image {filename!r}")

    if os.environ.get("MEDIAPIPE_DEMOS_OFFLINE") == "1":
        raise FileNotFoundError(f"Offline mode enabled and sample missing: {destination}")

    part = destination.with_suffix(destination.suffix + ".part")
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        resp = client.get(REMOTE_SAMPLE_URLS[filename])
        resp.raise_for_status()
        part.write_bytes(resp.content)
    part.replace(destination)
    return destination


def write_wav_pcm16(path: Path, samples: np.ndarray, sample_rate_hz: int) -> Path:
    """Write a mono float32 array in [-1, 1] to a 16-bit PCM WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(int(sample_rate_hz))
        wav_file.writeframes(pcm16.tobytes())
    return path


def read_wav_float32(path: Path) -> tuple[np.ndarray, int]:
    """Read a mono or stereo 16-bit PCM WAV file into float32 mono samples in [-1, 1]."""
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sampwidth = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        raw = wav_file.readframes(wav_file.getnframes())
    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM WAV, got {sampwidth * 8}-bit: {path}")
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, sample_rate


def resample_linear(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample a 1-D float32 audio signal using linear interpolation."""
    arr = np.asarray(samples, dtype=np.float32)
    if src_rate == dst_rate or arr.size == 0:
        return arr
    dst_len = max(1, int(round(arr.size * dst_rate / src_rate)))
    src_positions = np.linspace(0.0, arr.size - 1, num=arr.size, dtype=np.float64)
    dst_positions = np.linspace(0.0, arr.size - 1, num=dst_len, dtype=np.float64)
    return np.interp(dst_positions, src_positions, arr).astype(np.float32)


def synthesize_music_wav(path: Path, sample_rate_hz: int = 16000, duration_s: float = 2.4) -> Path:
    """Generate a deterministic harmonic piano-like arpeggio WAV for audio classification."""
    num_samples = int(sample_rate_hz * duration_s)
    t = np.linspace(0.0, duration_s, num=num_samples, endpoint=False, dtype=np.float32)
    notes_hz = [261.63, 329.63, 392.00, 523.25, 392.00, 329.63]  # C-major arpeggio
    signal = np.zeros_like(t)
    step = duration_s / len(notes_hz)
    for idx, freq in enumerate(notes_hz):
        start = idx * step
        local_t = np.maximum(0.0, t - start)
        active = (t >= start) & (t < start + step * 1.4)
        envelope = np.exp(-3.5 * local_t) * np.minimum(1.0, local_t / 0.015)
        harmonic = (
            1.00 * np.sin(2.0 * np.pi * freq * local_t)
            + 0.45 * np.sin(2.0 * np.pi * (2.0 * freq) * local_t)
            + 0.20 * np.sin(2.0 * np.pi * (3.0 * freq) * local_t)
        )
        signal += np.where(active, envelope * harmonic, 0.0)
    peak = float(np.max(np.abs(signal))) or 1.0
    signal = 0.75 * signal / peak
    return write_wav_pcm16(path, signal, sample_rate_hz)


def ensure_music_16k_wav(*, cache_dir: Path | None = None) -> Path:
    """Ensure the synthesized 16 kHz musical arpeggio WAV fixture exists."""
    target_dir = cache_dir or samples_dir()
    destination = target_dir / "music_16k.wav"
    if not destination.is_file() or destination.stat().st_size == 0:
        synthesize_music_wav(destination, sample_rate_hz=16000)
    return destination


def ensure_speech_16k_wav(
    *,
    prompt: str = DEFAULT_TTS_PROMPT,
    cache_dir: Path | None = None,
    tts_model_path: Path | None = None,
) -> Path:
    """Ensure a 16 kHz speech WAV fixture exists, synthesizing via MediaPipe TTS if absent."""
    target_dir = cache_dir or samples_dir()
    destination = target_dir / "speech_16k.wav"
    if destination.is_file() and destination.stat().st_size > 0:
        return destination

    import mediapipe as mp

    model_file = ensure_model("text_to_speech", model_path=tts_model_path)
    tts_cache = Path(tempfile.gettempdir()) / "mediapipe_tts_cache"
    tts_cache.mkdir(parents=True, exist_ok=True)
    options = mp.tasks.audio.TextToSpeechOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(model_file),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        ),
        cache_dir=str(tts_cache),
    )
    with mp.tasks.audio.TextToSpeech.create_from_options(options) as tts:
        result = tts.synthesize(prompt)
        samples_16k = resample_linear(
            np.asarray(result.samples, dtype=np.float32),
            int(result.sample_rate_hz),
            16000,
        )
    return write_wav_pcm16(destination, samples_16k, 16000)
