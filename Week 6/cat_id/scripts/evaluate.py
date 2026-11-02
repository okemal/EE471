"""Small functional smoke evaluation against a running local API.

Examples are illustrative and may overlap the models' training data. This is
not a held-out benchmark or an estimate of real-world accuracy. No threshold
is fitted here. Optional downloaded cases come from fetch_evaluation.py.
"""

import io
import json
import os
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("CAT_ID_TEST_URL", "http://127.0.0.1:8000")


def main():
    cases = []
    expected_names = {
        "domestic-cat": "Felis catus",
        "tiger": "Panthera tigris",
        "snow-leopard": "Panthera uncia",
        "lion": "Panthera leo",
        "leopard": "Panthera pardus",
        "dog": None,
    }
    credits = json.loads((ROOT / "frontend/assets/credits.json").read_text())
    for item in credits:
        cases.append(
            {
                "id": item["id"],
                "expected": expected_names[item["id"]],
                "source_url": item["source_url"],
                "data": (ROOT / "frontend" / item["file"].lstrip("/")).read_bytes(),
            }
        )
    manifest = ROOT / ".cache/evaluation/manifest.json"
    if manifest.exists():
        for item in json.loads(manifest.read_text()):
            cases.append({**item, "data": (ROOT / item["file"]).read_bytes()})

    noise = Image.fromarray(
        np.random.default_rng(471).integers(0, 256, (256, 256, 3), dtype=np.uint8)
    )
    text_image = Image.new("RGB", (512, 256), "white")
    ImageDraw.Draw(text_image).text((30, 100), "This is a document, not an animal.", fill="black")
    for name, image in [
        ("blank-white", Image.new("RGB", (256, 256), "white")),
        ("blank-black", Image.new("RGB", (256, 256), "black")),
        ("random-noise", noise),
        ("text-document", text_image),
    ]:
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        cases.append(
            {
                "id": name,
                "expected": None,
                "source_url": "synthetic test fixture",
                "data": buffer.getvalue(),
            }
        )

    results = []
    with httpx.Client(timeout=180) as client:
        health = client.get(BASE + "/api/health").json()
        if health["status"] != "ready":
            raise SystemExit("Wait for /api/ready before running evaluation.")
        for case in cases:
            response = client.post(
                BASE + "/api/identify",
                content=case["data"],
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
            result = response.json()
            candidates = [
                {"name": c["species"]["scientific_name"], "similarity": c["similarity"]}
                for c in result["candidates"]
            ]
            correct = (
                result["status"] == "no_match"
                if case["expected"] is None
                else bool(candidates and candidates[0]["name"] == case["expected"])
            )
            record = {
                "case": case["id"],
                "expected": case["expected"],
                "source_url": case["source_url"],
                "status": result["status"],
                "candidates": candidates,
                "expected_outcome": correct,
                "diagnostics": result["diagnostics"],
                "elapsed_ms": result["elapsed_ms"],
            }
            results.append(record)
            print(json.dumps(record), flush=True)
    output = Path(os.getenv("CAT_ID_ARTIFACT_DIR", str(ROOT / "artifacts"))) / "evaluation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "health": health,
                "cases": results,
                "notice": "Illustrative smoke cases, not a representative or held-out accuracy benchmark.",
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Saved {len(results)} cases to {output}")


if __name__ == "__main__":
    main()
