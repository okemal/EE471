"""Image decoding, dimension bounds, EXIF stripping, and format validation tests."""

import io
from dataclasses import replace

import pytest
from PIL import Image

from backend.app.images import InvalidImage, decode_image


def _encode(img: Image.Image, fmt: str, **kwargs) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def test_valid_formats_strip_metadata_and_composite_alpha(config):
    rgba = Image.new("RGBA", (64, 64), (255, 0, 0, 0))
    exif = Image.Exif()
    exif[271] = "CameraCorp"
    for fmt in ("PNG", "WEBP"):
        decoded = decode_image(_encode(rgba, fmt, exif=exif.tobytes()), config)
        assert decoded.mode == "RGB"
        assert decoded.getpixel((0, 0)) == (255, 255, 255)
        assert not decoded.info

    rgb = Image.new("RGB", (2000, 1800), (10, 20, 30))
    resized = decode_image(_encode(rgb, "JPEG", exif=exif.tobytes()), config)
    assert max(resized.size) == 1600
    assert not resized.info


def test_rejects_empty_oversize_small_corrupt_and_unsupported(config):
    with pytest.raises(InvalidImage, match="first"):
        decode_image(b"", config)
    with pytest.raises(InvalidImage, match="too large"):
        decode_image(b"x" * 100, replace(config, max_upload_bytes=10))
    with pytest.raises(InvalidImage, match="Other formats"):
        decode_image(_encode(Image.new("RGB", (64, 64)), "GIF"), config)
    with pytest.raises(InvalidImage, match="28 pixels"):
        decode_image(_encode(Image.new("RGB", (20, 20)), "PNG"), config)
    with pytest.raises(InvalidImage, match="20 megapixels"):
        decode_image(_encode(Image.new("RGB", (64, 64)), "PNG"), replace(config, max_dimension=32))
    with pytest.raises(InvalidImage, match="could not be read"):
        decode_image(b"\x89PNG\r\n\x1a\ncorrupted", config)


def test_rejects_animated_webp(config):
    frames = [Image.new("RGB", (40, 40), color) for color in ("red", "blue")]
    buf = io.BytesIO()
    frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:])
    with pytest.raises(InvalidImage, match="animated"):
        decode_image(buf.getvalue(), config)
