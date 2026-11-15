"""Bounded data-URI transport between the web frontend/server and Cog container."""

import base64
import binascii
import io

from PIL import Image

from .config import Settings
from .images import InvalidImage, decode_image

DATA_PREFIXES = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")


def decode_data_uri(value: str, config: Settings) -> Image.Image:
    """Validate and decode a base64 JPEG, PNG, or WebP data URI with strict size bounds."""
    if not isinstance(value, str):
        raise InvalidImage("Supply a base64 JPEG, PNG, or WebP data URI string.")
    maximum = 4 * ((config.max_upload_bytes + 2) // 3) + max(map(len, DATA_PREFIXES))
    if len(value) > maximum:
        raise InvalidImage("The encoded image exceeds the 10 MB upload limit.")
    if not value.startswith(DATA_PREFIXES):
        raise InvalidImage("Supply a base64 JPEG, PNG, or WebP data URI; URLs are not accepted.")
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
    except (binascii.Error, ValueError):
        raise InvalidImage("The image is not valid base64.") from None
    return decode_image(raw, config)


def encode_image(image: Image.Image) -> str:
    """Losslessly encode a sanitized RGB PIL image as a PNG data URI."""
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
