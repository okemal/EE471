"""MediaPipe Face Landmarker demo (478 3D landmarks, blendshapes & 4x4 pose matrix)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mediapipe as mp

from mediapipe_demos.common import build_demo_parser, output_dir, print_header
from mediapipe_demos.models import ensure_model
from mediapipe_demos.samples import input_photo
from mediapipe_demos.visualize import draw_landmark_points, load_rgb_image, save_rgb_image


def run_demo(
    *,
    model_path: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Detect 478 face landmarks, top blendshapes, and transformation matrix."""
    resolved_model = ensure_model("face_landmarker", model_path=model_path)
    image_path = input_path if input_path is not None else input_photo("face-3.png")
    out_dir = output_dir(output_path)
    print_header("Face Landmarker", "vision", resolved_model)

    rgb = load_rgb_image(image_path)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(resolved_model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp_image)

    annotated = draw_landmark_points(
        rgb,
        result.face_landmarks,
        connections=mp.tasks.vision.FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS,
        point_color=(56, 189, 248),
        line_color=(148, 163, 184),
        radius=1,
    )
    annotated_path = save_rgb_image(annotated, out_dir / "face_landmarker.png")

    top_blendshapes: list[dict[str, object]] = []
    if result.face_blendshapes:
        sorted_bs = sorted(result.face_blendshapes[0], key=lambda c: c.score, reverse=True)
        top_blendshapes = [
            {"name": c.category_name, "score": round(float(c.score), 4)} for c in sorted_bs[:5]
        ]

    num_landmarks = len(result.face_landmarks[0]) if result.face_landmarks else 0
    has_matrix = bool(result.facial_transformation_matrixes)
    print(f"Input:           {image_path.name}")
    print(f"Faces detected:  {len(result.face_landmarks)} ({num_landmarks} landmarks)")
    print(f"4x4 pose matrix: {'present' if has_matrix else 'absent'}")
    print(f"Top blendshapes: {top_blendshapes[:3]}")
    print(f"Annotated:       {annotated_path}")

    return {
        "task": "face_landmarker",
        "model": resolved_model.name,
        "input": str(image_path),
        "num_faces": len(result.face_landmarks),
        "num_landmarks": num_landmarks,
        "has_transform_matrix": has_matrix,
        "top_blendshapes": top_blendshapes,
        "output_image": str(annotated_path),
    }


def main() -> None:
    args = build_demo_parser(__doc__).parse_args()
    run_demo(model_path=args.model, input_path=args.input, output_path=args.output_dir)


if __name__ == "__main__":
    main()
