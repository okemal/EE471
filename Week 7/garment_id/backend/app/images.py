"""Validate and sanitize uploaded image bytes before inference."""

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from .config import Settings

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class InvalidImage(ValueError):
    """A safe, user-readable image validation error."""


def decode_image(data: bytes, settings: Settings) -> Image.Image:
    """Decode JPEG, PNG, or WebP bytes safely and strip all metadata."""
    if not data:
        raise InvalidImage("Choose a JPEG, PNG, or WebP photograph first.")
    if len(data) > settings.max_upload_bytes:
        raise InvalidImage("This image is too large. Choose a file under 10 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in ALLOWED_FORMATS:
                    raise InvalidImage(
                        "Use a JPEG, PNG, or WebP image. Other formats are not supported."
                    )
                if getattr(source, "n_frames", 1) != 1:
                    raise InvalidImage("Use a still photograph rather than an animated image.")
                width, height = source.size
                if (
                    width * height > settings.max_pixels
                    or max(width, height) > settings.max_dimension
                ):
                    raise InvalidImage(
                        "The image is too large to decode safely. "
                        "Resize it to 20 megapixels or less."
                    )
                if min(width, height) < settings.min_dimension:
                    raise InvalidImage(
                        "This image is too small. Use an image at least "
                        f"{settings.min_dimension} pixels on each side."
                    )
                source.verify()
            with Image.open(BytesIO(data)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                rgba = oriented.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                image = Image.alpha_composite(background, rgba).convert("RGB")
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                # Copy raw RGB bytes so EXIF, comments, and filenames do not survive.
                return Image.frombytes("RGB", image.size, image.tobytes())
    except InvalidImage:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidImage(
            "This file could not be read as a safe image. Try another JPEG, PNG, or WebP."
        ) from exc
