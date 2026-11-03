"""The web service delegates inference to the local Cog HTTP service."""

import threading
from urllib.parse import urlsplit

import httpx

from .cog_transport import encode_image
from .config import Settings
from .model import BIOCLIP
from .schemas import Identification


class ModelBusy(Exception):
    """Cog is already serving a direct API or website prediction."""


class CogClassifier:
    name = f"{BIOCLIP.name} + ResNet50 (Cog)"

    def __init__(self, config: Settings):
        url = urlsplit(config.cog_url)
        if (
            url.scheme != "http"
            or url.hostname not in {"cog", "127.0.0.1", "localhost", "::1"}
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
        ):
            raise ValueError("CAT_ID_COG_URL must identify the local Cog service.")
        self.url = config.cog_url.rstrip("/")
        self.status = "loading" if config.load_model else "disabled"
        self.device = "cpu"
        self.error = None
        self.lock = threading.Lock()

    def load(self):
        self.refresh_health()

    def refresh_health(self):
        if self.status == "disabled":
            return
        try:
            response = httpx.get(f"{self.url}/health-check", timeout=3, trust_env=False)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
                raise ValueError("Malformed Cog health response.")
            status = payload["status"]
            self.status = "ready" if status in {"READY", "BUSY"} else "loading"
            self.error = None
            if status == "SETUP_FAILED":
                self.status = "error"
                self.error = "The Cog model could not start. Check the Cog container log."
        except (httpx.HTTPError, ValueError):
            self.status = "error"
            self.error = "The local Cog service is unavailable. Start the assignment containers."

    def predict(self, image) -> dict:
        response = httpx.post(
            f"{self.url}/predictions",
            json={"input": {"image": encode_image(image)}},
            timeout=120,
            trust_env=False,
        )
        if response.status_code == 409:
            raise ModelBusy
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "succeeded":
            raise RuntimeError("Cog did not complete the prediction.")
        # Validate the internal boundary before passing data to the browser.
        return Identification.model_validate(body["output"]).model_dump(exclude_none=True)
