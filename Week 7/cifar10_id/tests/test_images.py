"""Image decoding, metadata stripping, and pixel/dimension bound tests."""

import io
from dataclasses import replace

import pytest
from PIL import Image, PngImagePlugin

from backend.app.images import InvalidImage, decode_image


def test_decode_strips_metadata_and_handles_alpha_and_exif(config):
    img = Image.new("RGBA", (120, 80), (20, 90, 200, 128))
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "secret-metadata")
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=info)

    with decode_image(buf.getvalue(), config) as clean:
        assert clean.mode == "RGB"
        assert clean.size == (120, 80)
        assert not clean.info


def test_exif_transpose_applied(config):
    exif = Image.Exif()
    exif[274] = 6  # Rotate 270 clockwise -> 40x80 becomes 80x40
    img = Image.new("RGB", (40, 80), (150, 40, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)

    with decode_image(buf.getvalue(), config) as clean:
        assert clean.size == (80, 40)
        assert not clean.info


def test_decode_rejects_invalid_empty_tiny_animated_and_oversized(config):
    with pytest.raises(InvalidImage, match="first"):
        decode_image(b"", config)

    with pytest.raises(InvalidImage, match="too large"):
        decode_image(b"x" * 100, replace(config, max_upload_bytes=10))

    gif_buf = io.BytesIO()
    f1 = Image.new("RGB", (40, 40), (10, 10, 10))
    f2 = Image.new("RGB", (40, 40), (20, 20, 20))
    f1.save(gif_buf, format="GIF", save_all=True, append_images=[f2])
    with pytest.raises(InvalidImage, match="Other formats"):
        decode_image(gif_buf.getvalue(), config)

    webp_buf = io.BytesIO()
    f1.save(webp_buf, format="WEBP", save_all=True, append_images=[f2])
    with pytest.raises(InvalidImage, match="still photograph"):
        decode_image(webp_buf.getvalue(), config)

    tiny_buf = io.BytesIO()
    Image.new("RGB", (16, 16), (0, 0, 0)).save(tiny_buf, format="PNG")
    with pytest.raises(InvalidImage, match="at least 32 pixels"):
        decode_image(tiny_buf.getvalue(), config)

    large_buf = io.BytesIO()
    Image.new("RGB", (200, 200), (0, 0, 0)).save(large_buf, format="PNG")
    with pytest.raises(InvalidImage, match="20 megapixels"):
        decode_image(large_buf.getvalue(), replace(config, max_pixels=100))

    with pytest.raises(InvalidImage, match="could not be read"):
        decode_image(b"corrupt-bytes", config)
