import io
from dataclasses import replace

import pytest
from PIL import Image

from backend.app.images import InvalidImage, decode_image


def image_bytes(mode="RGB", size=(100, 80), fmt="PNG", **kwargs):
    output = io.BytesIO()
    Image.new(mode, size).save(output, fmt, **kwargs)
    return output.getvalue()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_supported_formats_become_clean_rgb(config, fmt):
    result = decode_image(image_bytes(fmt=fmt), config)
    assert result.mode == "RGB"
    assert result.size == (100, 80)
    assert result.info == {}


@pytest.mark.parametrize(
    "data", [b"", b"not an image", b"<svg><script>alert(1)</script></svg>", b"\xff\xd8\xff"]
)
def test_invalid_images_rejected(config, data):
    with pytest.raises(InvalidImage):
        decode_image(data, config)


def test_size_and_dimensions_rejected_before_decode(config, jpeg):
    with pytest.raises(InvalidImage, match="too large"):
        decode_image(jpeg, replace(config, max_upload_bytes=10))
    with pytest.raises(InvalidImage, match="20 megapixels"):
        decode_image(jpeg, replace(config, max_pixels=100))
    with pytest.raises(InvalidImage, match="too small"):
        decode_image(image_bytes(size=(10, 10)), config)


def test_animated_webp_rejected(config):
    output = io.BytesIO()
    Image.new("RGB", (80, 80), "red").save(
        output,
        "WEBP",
        save_all=True,
        append_images=[Image.new("RGB", (80, 80), "blue")],
        duration=100,
        loop=0,
    )
    with pytest.raises(InvalidImage, match="still photograph"):
        decode_image(output.getvalue(), config)


def test_transparent_pixels_composited_on_white(config):
    image = decode_image(image_bytes(mode="RGBA"), config)
    assert image.getpixel((0, 0)) == (255, 255, 255)


def test_exif_orientation_applied_and_metadata_removed(config):
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private metadata"
    result = decode_image(image_bytes(fmt="JPEG", exif=exif), config)
    assert result.size == (80, 100)
    assert not result.info
    assert not result.getexif()


def test_large_valid_photo_downsampled(config):
    image = decode_image(image_bytes(size=(2000, 1000)), config)
    assert image.size == (1600, 800)


def test_truncated_photo_rejected(config, jpeg):
    with pytest.raises(InvalidImage):
        decode_image(jpeg[:-100], config)


def test_gif_content_rejected_even_if_named_jpeg(config):
    with pytest.raises(InvalidImage, match="formats"):
        decode_image(image_bytes(fmt="GIF"), config)
