"""Acquire a small, openly sourced smoke set; not a representative accuracy benchmark.

Photos are ignored cache files. Their provenance is saved beside them. This
script never processes or uploads user files. Run once with internet access.
"""

import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_assets import api, plain, read

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "cheetah": ("Cheetah", "Acinonyx jubatus"),
    "jaguar": ("Jaguar", "Panthera onca"),
    "caracal": ("Caracal", "Caracal caracal"),
    "eurasian-lynx": ("Eurasian lynx", "Lynx lynx"),
    "pallas-cat": ("Pallas's cat", "Otocolobus manul"),
    "fox": ("Red fox", None),
    "hyena": ("Spotted hyena", None),
    "raccoon": ("Raccoon", None),
    "red-panda": ("Red panda", None),
    "horse": ("Horse", None),
    "sunflower": ("Helianthus annuus", None),
}


def main():
    directory = ROOT / ".cache/evaluation"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    manifest_path = directory / "manifest.json"
    for slug, (title, expected) in CASES.items():
        try:
            page = next(
                iter(
                    api(
                        "en.wikipedia.org",
                        action="query",
                        prop="pageimages",
                        titles=title,
                        piprop="original",
                        redirects=1,
                    )["query"]["pages"].values()
                )
            )
            filename = urllib.parse.unquote(
                urllib.parse.urlsplit(page["original"]["source"]).path.split("/")[-1]
            )
            info = next(
                iter(
                    api(
                        "commons.wikimedia.org",
                        action="query",
                        prop="imageinfo",
                        titles="File:" + filename,
                        iiprop="url|extmetadata",
                        iiurlwidth=800,
                    )["query"]["pages"].values()
                )
            )["imageinfo"][0]
            target = directory / f"{slug}.jpg"
            if not target.exists():
                target.write_bytes(read(info.get("thumburl", info["url"])))
            meta = info["extmetadata"]
            manifest.append(
                {
                    "id": slug,
                    "file": str(target.relative_to(ROOT)),
                    "expected": expected,
                    "source_url": info["descriptionurl"],
                    "artist": plain(meta.get("Artist", {}).get("value", "See source")),
                    "license": plain(meta.get("LicenseShortName", {}).get("value", "See source")),
                }
            )
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            print(slug, "ready", flush=True)
        except Exception as exc:
            print(slug, type(exc).__name__, str(exc), flush=True)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
