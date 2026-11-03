"""Transport and service-boundary regression checks; no model downloads."""

import base64
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.cog_client import CogClassifier
from backend.app.cog_transport import decode_data_uri, encode_image
from backend.app.images import InvalidImage, decode_image
from backend.app.main import create_app


def test_data_uri_preserves_validated_pixels(config, jpeg):
    with decode_image(jpeg, config) as original:
        with decode_data_uri(encode_image(original), config) as decoded:
            assert decoded.tobytes() == original.tobytes()
            assert not decoded.info


@pytest.mark.parametrize(
    "value",
    [
        "http://127.0.0.1/private",
        "https://example.com/cat.jpg",
        "file:///etc/passwd",
        "data:image/svg+xml;base64,PHN2Zy8+",
        "data:image/jpeg;base64,!!!",
        "data:image/jpeg;base64," + base64.b64encode(b"not a picture").decode(),
    ],
)
def test_data_uri_rejects_urls_and_invalid_images(value, config):
    with pytest.raises(InvalidImage):
        decode_data_uri(value, config)


def test_data_uri_bound_before_decode(config):
    with pytest.raises(InvalidImage, match="exceeds"):
        decode_data_uri(
            "data:image/png;base64," + "A" * 1000, replace(config, max_upload_bytes=100)
        )


@pytest.mark.parametrize(
    "url", ["https://example.com", "http://user@localhost:5002", "http://cog:5000/path"]
)
def test_cog_target_must_be_local(config, url):
    with pytest.raises(ValueError):
        CogClassifier(replace(config, cog_url=url))


def test_cog_connection_failure_and_recovery(config, monkeypatch):
    engine = CogClassifier(replace(config, load_model=True, cog_url="http://cog:5000"))

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("test internal hostname")

    monkeypatch.setattr(httpx, "get", unavailable)
    engine.refresh_health()
    assert engine.status == "error" and "internal" not in engine.error
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: httpx.Response(
            200,
            json={"status": "READY"},
            request=httpx.Request("GET", "http://cog:5000/health-check"),
        ),
    )
    engine.refresh_health()
    assert engine.status == "ready" and engine.error is None


def test_cog_busy_does_not_fall_back_to_direct_inference(config, jpeg, monkeypatch):
    engine = CogClassifier(replace(config, load_model=True, cog_url="http://cog:5000"))
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: httpx.Response(
            200,
            json={"status": "BUSY"},
            request=httpx.Request("GET", "http://cog:5000/health-check"),
        ),
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(409))
    with TestClient(create_app(config, engine), base_url="http://localhost") as client:
        result = client.post("/api/identify", content=jpeg, headers={"content-type": "image/jpeg"})
    assert result.status_code == 429
    assert result.headers["retry-after"] == "3"
    assert not engine.lock.locked()


@pytest.mark.parametrize("payload", [[], {"status": []}, {"unexpected": "READY"}])
def test_cog_malformed_health_is_unavailable(config, monkeypatch, payload):
    engine = CogClassifier(replace(config, load_model=True, cog_url="http://cog:5000"))
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: httpx.Response(
            200, json=payload, request=httpx.Request("GET", "http://cog:5000/health-check")
        ),
    )
    engine.refresh_health()
    assert engine.status == "error"
    assert engine.error == "The local Cog service is unavailable. Start the assignment containers."


def test_cog_invalid_response_fails_safely(config, jpeg, monkeypatch):
    engine = CogClassifier(replace(config, load_model=True, cog_url="http://cog:5000"))
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: httpx.Response(
            200,
            json={"status": "READY"},
            request=httpx.Request("GET", "http://cog:5000/health-check"),
        ),
    )
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200,
            json={"status": "succeeded", "output": {"invented": "unvalidated result"}},
            request=httpx.Request("POST", "http://cog:5000/predictions"),
        ),
    )
    with TestClient(create_app(config, engine), base_url="http://localhost") as client:
        result = client.post("/api/identify", content=jpeg, headers={"content-type": "image/jpeg"})
    assert result.status_code == 503
    assert "invented" not in result.text
    assert not engine.lock.locked()
