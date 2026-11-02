"""Refresh attributed Wikimedia example photos; never receives user uploads."""

import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"User-Agent": "FelisLocal/1.0 (educational Felidae field guide; local demo)"}
PHOTOS = {
    "snow-leopard": "Snow leopard",
    "tiger": "Tiger",
    "lion": "Lion",
    "domestic-cat": "Cat",
    "leopard": "Leopard",
    "dog": "Golden Retriever",
}


def read(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=45) as r:
        return r.read()


def api(host, **params):
    return json.loads(
        read(f"https://{host}/w/api.php?" + urllib.parse.urlencode({"format": "json", **params}))
    )


def plain(value):
    return html.unescape(re.sub("<[^>]+>", "", value)).strip()


def main():
    credits = []
    for slug, title in PHOTOS.items():
        page = next(
            iter(
                api(
                    "en.wikipedia.org",
                    action="query",
                    prop="pageimages",
                    titles=title,
                    piprop="original|thumbnail",
                    pithumbsize=1400,
                )["query"]["pages"].values()
            )
        )
        filename = urllib.parse.unquote(
            urllib.parse.urlsplit(page["original"]["source"]).path.split("/")[-1]
        )
        # The main domestic-cat article uses a collage; a single cat is a better example.
        if slug == "domestic-cat":
            filename = "Cat August 2010-4.jpg"
        info = next(
            iter(
                api(
                    "commons.wikimedia.org",
                    action="query",
                    prop="imageinfo",
                    titles="File:" + filename,
                    iiprop="url|extmetadata",
                    iiurlwidth=1400,
                )["query"]["pages"].values()
            )
        )["imageinfo"][0]
        target = ROOT / "frontend" / "assets" / f"{slug}.jpg"
        target.write_bytes(read(info.get("thumburl", info["url"])))
        meta = info["extmetadata"]
        credits.append(
            {
                "id": slug,
                "file": f"/assets/{slug}.jpg",
                "title": filename,
                "artist": plain(meta.get("Artist", {}).get("value", "See source")),
                "license": plain(meta.get("LicenseShortName", {}).get("value", "See source")),
                "license_url": meta.get("LicenseUrl", {}).get("value", ""),
                "source_url": info["descriptionurl"],
                "changes": "Resized by Wikimedia; displayed with cropping.",
            }
        )
        print(slug, target.stat().st_size, credits[-1]["license"], flush=True)
        time.sleep(0.5)
    (ROOT / "frontend/assets/credits.json").write_text(json.dumps(credits, indent=2) + "\n")


if __name__ == "__main__":
    main()
