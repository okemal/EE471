"""Download and SHA-256 verify pose_landmarker_full.task for Week 8 Task 2."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arm_pose.config import MODEL_FILENAME, MODEL_SHA256, MODEL_URL, sha256_file  # noqa: E402


def main() -> None:
    destination = ROOT / "models" / MODEL_FILENAME
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_file() and sha256_file(destination) == MODEL_SHA256:
        print(f"[ok] Verified model already present: {destination}")
        return

    # Reuse Task 1 cached model if present to avoid redundant network traffic.
    task1_cached = ROOT.parent / "task1_mediapipe_demos" / ".cache" / "models" / MODEL_FILENAME
    if task1_cached.is_file() and sha256_file(task1_cached) == MODEL_SHA256:
        shutil.copy2(task1_cached, destination)
        print(f"[copied] Verified model from Task 1 cache -> {destination}")
        return

    part = destination.with_suffix(destination.suffix + ".part")
    print(f"[download] {MODEL_URL} -> {destination}")
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        with client.stream("GET", MODEL_URL) as response:
            response.raise_for_status()
            with part.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    handle.write(chunk)
    actual = sha256_file(part)
    if actual != MODEL_SHA256:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch: expected {MODEL_SHA256}, got {actual}")
    part.replace(destination)
    print(f"[ok] Downloaded and verified {destination} ({actual[:12]}...)")


if __name__ == "__main__":
    main()
