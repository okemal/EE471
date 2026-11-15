"""Generate bundled FashionMNIST sample images, hero collage, and credits.json."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from torchvision import datasets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.catalogue import garment_catalogue  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.model import DualGarmentClassifier  # noqa: E402


def _upscale_sample(img: Image.Image, size: int = 224) -> Image.Image:
    """Upscale a 28x28 FashionMNIST sample cleanly for crisp editorial thumbnails."""
    rgb = img.convert("RGB")
    return rgb.resize((size, size), Image.Resampling.BICUBIC)


def main() -> None:
    assets_dir = ROOT / "frontend" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    test_set = datasets.FashionMNIST(root=str(settings.data_dir), train=False, download=True)
    classifier = DualGarmentClassifier(settings)
    classifier.load()
    if classifier.status != "ready":
        raise RuntimeError(f"Models must be trained first: {classifier.error}")

    catalogue = garment_catalogue()
    selected_imgs: dict[str, Image.Image] = {}

    for item in catalogue:
        cid = item["id"]
        target_idx = item["class_index"]
        fallback_img = None
        chosen_img = None

        # Prefer samples where optimized is confidently correct; for 'shirt', pick one
        # where baseline disagrees while optimized succeeds to illustrate HPO benefits.
        for sample_idx in range(len(test_set)):
            raw_img, label = test_set[sample_idx]
            if int(label) != target_idx:
                continue
            rgb = raw_img.convert("RGB")
            if fallback_img is None:
                fallback_img = rgb
            pred = classifier.predict(rgb)
            opt_ok = (
                pred["optimized"]["predicted_id"] == cid and pred["optimized"]["confidence"] > 0.78
            )
            base_ok = pred["baseline"]["predicted_id"] == cid
            if cid == "shirt":
                if opt_ok and not base_ok:
                    chosen_img = rgb
                    break
            elif opt_ok and base_ok:
                chosen_img = rgb
                break

        final_raw = chosen_img or fallback_img
        assert final_raw is not None
        selected_imgs[cid] = final_raw
        _upscale_sample(final_raw, 224).save(assets_dir / f"{cid}.png", format="PNG")

    # Create a light-background studio tee sample to verify automatic polarity inversion.
    tee_inverted = ImageOps.invert(selected_imgs["t-shirt-top"].convert("L")).convert("RGB")
    tee_canvas = Image.new("RGB", (280, 280), (245, 244, 238))
    tee_scaled = tee_inverted.resize((210, 210), Image.Resampling.BICUBIC)
    tee_canvas.paste(tee_scaled, (35, 35))
    tee_canvas.save(assets_dir / "studio-tee.png", format="PNG")

    # Build a clean 3x2 hero showcase mosaic from 6 distinct garment classes.
    hero_ids = ["sneaker", "dress", "pullover", "ankle-boot", "bag", "trouser"]
    hero = Image.new("RGB", (900, 675), (23, 40, 33))
    draw = ImageDraw.Draw(hero)
    tile_w, tile_h = 260, 260
    start_x, start_y = 42, 60
    gap = 18
    for pos, cid in enumerate(hero_ids):
        col = pos % 3
        row = pos // 3
        x = start_x + col * (tile_w + gap)
        y = start_y + row * (tile_h + gap)
        tile = selected_imgs[cid].resize((tile_w, tile_h), Image.Resampling.BICUBIC)
        hero.paste(tile, (x, y))
        draw.rectangle([x, y, x + tile_w, y + tile_h], outline=(62, 92, 76), width=2)
    hero.save(assets_dir / "hero-fashion.png", format="PNG")

    credits = [
        {
            "title": "FashionMNIST Test Samples (Classes 0–9)",
            "source": "Zalando Research / TorchVision",
            "license": "MIT License",
            "notes": (
                "28x28 grayscale garment silhouettes extracted directly from the held-out "
                "FashionMNIST test split."
            ),
        },
        {
            "title": "Studio Light-Background Tee (studio-tee.png)",
            "source": "Derived from FashionMNIST Test Split",
            "license": "MIT License",
            "notes": (
                "Light-studio inverted sample demonstrating automatic border-polarity "
                "inversion during preprocessing."
            ),
        },
        {
            "title": "Hero Garment Showcase (hero-fashion.png)",
            "source": "Derived from FashionMNIST Test Split",
            "license": "MIT License",
            "notes": (
                "Six-tile editorial grid showcasing Sneaker, Dress, Pullover, Ankle boot, "
                "Bag, and Trouser samples."
            ),
        },
        {
            "title": "DM Sans & Fraunces Typefaces",
            "source": "Google Fonts (bundled locally)",
            "license": "SIL Open Font License 1.1",
            "notes": (
                "Local variable font binaries in frontend/assets/fonts/ with no external "
                "runtime font requests."
            ),
        },
    ]
    (assets_dir / "credits.json").write_text(json.dumps(credits, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(selected_imgs) + 2} sample images and credits.json in {assets_dir}")


if __name__ == "__main__":
    main()
