# Task 3 — Face Looking-Direction Classifier (MediaPipe + Docker / Cog)

Detects facial geometry and 3D head orientation using MediaPipe `FaceLandmarker` (`face_landmarker.task`) and classifies viewer-relative looking direction: `"left"`, `"right"`, or `"straight"`.

## Verification Results on Provided Photos

| Image | Expected | Predicted | 3D Yaw (deg) | 2D Asymmetry | Signal Source |
|---|---|---|---|---|---|
| `face-1.png` | `left` | `left` | `-34.71°` | `-0.6656` | `pose_matrix` |
| `face-2.png` | `right` | `right` | `+32.53°` | `+0.6017` | `pose_matrix` |
| `face-3.png` | `straight` | `straight` | `-2.43°` | `-0.0249` | `pose_matrix` |

## Usage

```bash
uv sync --frozen
uv run --frozen python scripts/download_model.py
uv run --frozen python classify_face.py ../input_photos/face-1.png

# Containerized via Cog (port 5005)
cog build --use-cog-base-image=false
cog run ee471-week8-face-direction:cog -i image=@../input_photos/face-1.png
docker compose -f compose.cog.yaml up -d --wait
uv run --frozen python scripts/verify_cog.py --url http://127.0.0.1:5005
docker compose -f compose.cog.yaml down
```
