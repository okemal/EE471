"""Real Cog HTTP smoke check; records output without echoing input image bytes."""

import argparse
import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5002")
    args = parser.parse_args()
    records = []
    with httpx.Client(base_url=args.url, timeout=180, trust_env=False) as client:
        health = client.get("/health-check")
        health.raise_for_status()
        assert health.json()["status"] == "READY", health.text
        schema = client.get("/openapi.json")
        schema.raise_for_status()
        assert "/predictions" in schema.json()["paths"]
        for name, expected in [
            ("domestic-cat", "Felis catus"),
            ("tiger", "Panthera tigris"),
            ("dog", None),
        ]:
            payload = base64.b64encode((ROOT / f"frontend/assets/{name}.jpg").read_bytes()).decode()
            response = client.post(
                "/predictions", json={"input": {"image": f"data:image/jpeg;base64,{payload}"}}
            )
            response.raise_for_status()
            body = response.json()
            assert body["status"] == "succeeded", body.get("error")
            result = body["output"]
            assert result["baseline"]["weights"] == "IMAGENET1K_V1"
            assert len(result["baseline"]["top_classes"]) == 3
            if expected is None:
                assert result["status"] == "no_match" and not result["candidates"]
            else:
                assert result["status"] == "matched"
                assert result["candidates"][0]["species"]["scientific_name"] == expected
            records.append({"case": name, "output": result, "logs": body.get("logs", "")})
            print(f"{name}: {result['status']}; ResNet50: {result['baseline']['predicted_class']}")
        # This is a string input, so the runtime must never fetch a submitted URL.
        rejected = client.post(
            "/predictions", json={"input": {"image": "http://127.0.0.1/private"}}
        )
        assert rejected.json()["status"] == "failed"
        assert "URLs are not accepted" in rejected.json()["error"]
    destination = ROOT / "artifacts/cog/verification.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "verified_at": datetime.now(UTC).isoformat(),
                "url": args.url,
                "cases": records,
                "remote_url_rejected": True,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Verified Cog inference and URL rejection. Evidence: {destination}")


if __name__ == "__main__":
    main()
