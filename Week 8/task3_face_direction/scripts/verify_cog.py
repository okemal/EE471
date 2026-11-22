"""Live HTTP verification against the running Task 3 Cog container."""

from __future__ import annotations

import argparse
import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
INPUT_PHOTOS = ROOT.parent / "input_photos"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5005")
    args = parser.parse_args()

    cases = [
        ("face-1.png", "left"),
        ("face-2.png", "right"),
        ("face-3.png", "straight"),
    ]
    records: list[dict[str, str]] = []

    with httpx.Client(base_url=args.url, timeout=60.0, trust_env=False) as client:
        health = client.get("/health-check")
        health.raise_for_status()
        assert health.json()["status"] in ("READY", "BUSY"), health.text

        schema = client.get("/openapi.json")
        schema.raise_for_status()
        assert "/predictions" in schema.json()["paths"]

        for filename, expected in cases:
            payload = base64.b64encode((INPUT_PHOTOS / filename).read_bytes()).decode("ascii")
            resp = client.post(
                "/predictions",
                json={"input": {"image": f"data:image/png;base64,{payload}"}},
            )
            resp.raise_for_status()
            body = resp.json()
            assert body["status"] == "succeeded", body.get("error")
            predicted = body["output"]
            assert predicted == expected, f"{filename}: expected {expected!r}, got {predicted!r}"
            records.append({"image": filename, "expected": expected, "predicted": predicted})
            print(f"{filename}: {predicted} (expected {expected})")

    destination = ROOT / "artifacts" / "cog" / "verification.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "verified_at": datetime.now(UTC).isoformat(),
                "url": args.url,
                "cases": records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Verified Task 3 Cog HTTP API. Evidence: {destination}")


if __name__ == "__main__":
    main()
