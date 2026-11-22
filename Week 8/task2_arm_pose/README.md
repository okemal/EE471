# Task 2 — Arm-Up Pose Classifier (MediaPipe + Docker / Cog)

Detects body pose using MediaPipe `PoseLandmarker` (`pose_landmarker_full.task`) and classifies which anatomical arm is raised: `"left"`, `"right"`, `"both"`, or `"None"`.

## Verification Results on Provided Photos

| Image | Expected | Predicted | Left Wrist Above | Right Wrist Above |
|---|---|---|---|---|
| `pose-1.jpg` | `left` | `left` | `+0.875` (up) | `-1.210` (down) |
| `pose-2.jpg` | `right` | `right` | `-0.165` (down) | `+0.475` (up) |
| `pose-3.jpg` | `both` | `both` | `+0.783` (up) | `+0.783` (up) |

## Usage

```bash
uv sync --frozen
uv run --frozen python scripts/download_model.py
uv run --frozen python classify_arm.py ../input_photos/pose-1.jpg

# Containerized via Cog (port 5004)
cog build --use-cog-base-image=false
cog run ee471-week8-arm-pose:cog -i image=@../input_photos/pose-1.jpg
docker compose -f compose.cog.yaml up -d --wait
uv run --frozen python scripts/verify_cog.py --url http://127.0.0.1:5004
docker compose -f compose.cog.yaml down
```
