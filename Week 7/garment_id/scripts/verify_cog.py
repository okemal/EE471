"""Real Cog HTTP verification against a running FashionMNIST Cog container."""

import argparse
import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5002")
    args = parser.parse_args()
    records = []
    with httpx.Client(base_url=args.url, timeout=120, trust_env=False) as client:
        health = client.get("/health-check")
        health.raise_for_status()
        assert health.json()["status"] == "READY", health.text
        schema = client.get("/openapi.json")
        schema.raise_for_status()
        assert "/predictions" in schema.json()["paths"]

        cases = [
            ("sneaker", "Sneaker"),
            ("shirt", "Shirt"),
            ("ankle-boot", "Ankle boot"),
            ("studio-tee", "T-shirt/top"),
        ]
        for name, expected_label in cases:
            payload = base64.b64encode((ROOT / f"frontend/assets/{name}.png").read_bytes()).decode()
            response = client.post(
                "/predictions", json={"input": {"image": f"data:image/png;base64,{payload}"}}
            )
            response.raise_for_status()
            body = response.json()
            assert body["status"] == "succeeded", body.get("error")
            result = body["output"]
            assert result["baseline"]["architecture"] == "QuickstartMLP"
            assert result["optimized"]["architecture"] == "GarmentConvNet"
            assert result["optimized"]["predicted_class"] == expected_label, result
            records.append({"case": name, "output": result})
            print(
                f"{name}: optimized={result['optimized']['predicted_class']} "
                f"({result['optimized']['confidence']:.3f}) | "
                f"baseline={result['baseline']['predicted_class']} "
                f"({result['baseline']['confidence']:.3f})"
            )

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
        + "\n",
        encoding="utf-8",
    )
    print(f"Verified Cog inference and URL rejection. Evidence: {destination}")


if __name__ == "__main__":
    main()
