"""Prepare a real image upload for Postman's JSON-based Cog inference request.

Generated files contain image pixels and belong in ignored artifacts/, not Git.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.cog_transport import encode_image  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.images import decode_image  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "image", nargs="?", type=Path, default=ROOT / "frontend/assets/domestic-cat.jpg"
    )
    args = parser.parse_args()
    with args.image.open("rb") as source:
        raw = source.read(settings.max_upload_bytes + 1)
    with decode_image(raw, settings) as image:
        data_uri = encode_image(image)
    output = ROOT / "artifacts/postman"
    output.mkdir(parents=True, exist_ok=True)
    environment = {
        "name": "Felis local image upload",
        "_postman_variable_scope": "environment",
        "values": [
            {"key": "cog_url", "value": "http://127.0.0.1:5002", "enabled": True},
            {"key": "image_data_uri", "value": data_uri, "enabled": True},
        ],
    }
    (output / "local.postman_environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    (output / "request.json").write_text(json.dumps({"input": {"image": data_uri}}) + "\n")
    print("Import docs/postman/Felis.postman_collection.json")
    print(f"Also import {output / 'local.postman_environment.json'}")
    print("Select the local environment in Postman and send the Classify uploaded image request.")


if __name__ == "__main__":
    main()
