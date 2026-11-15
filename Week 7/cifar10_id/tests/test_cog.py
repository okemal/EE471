"""Cog transport and HTTP proxy boundary tests."""

import base64
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.cog_client import CogClassifier
from backend.app.cog_transport import decode_data_uri, encode_image
from backend.app.images import InvalidImage, decode_image
from backend.app.main import create_app


def test_data_uri_preserves_validated_pixels(config, png_bytes):
    with decode_image(png_bytes, config) as original:
        with decode_data_uri(encode_image(original), config) as decoded:
            assert decoded.tobytes() == original.tobytes()
            assert not decoded.info


@pytest.mark.parametrize(
    "value",
    [
        12345,
        "http://127.0.0.1/private",
        "https://example.com/cat.png",
        "file:///etc/passwd",
        "data:image/svg+xml;base64,PHN2Zy8+",
        "data:image/png;base64,!!!",
        "data:image/png;base64," + base64.b64encode(b"not a picture").decode(),
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
    "url", ["https://example.com", "http://user@localhost:5003", "http://cog:5000/path"]
)
def test_cog_target_must_be_local(config, url):
    with pytest.raises(ValueError):
        CogClassifier(replace(config, cog_url=url))


def test_cog_health_states_and_recovery(config, monkeypatch):
    disabled = CogClassifier(replace(config, load_model=False, cog_url="http://cog:5000"))
    disabled.refresh_health()
    assert disabled.status == "disabled"

    engine = CogClassifier(replace(config, load_model=True, cog_url="http://cog:5000"))
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("internal"))
    )
    engine.load()
    assert engine.status == "error" and "internal" not in engine.error

    for cog_state, expected_status in [
        ("STARTING", "loading"),
        ("SETUP_FAILED", "error"),
        ("READY", "ready"),
        ("BUSY", "ready"),
    ]:
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, s=cog_state, **k: httpx.Response(
                200,
                json={"status": s},
                request=httpx.Request("GET", "http://cog:5000/health-check"),
            ),
        )
        engine.refresh_health()
        assert engine.status == expected_status


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


def test_cog_busy_and_invalid_and_valid_predictions(
    config, png_bytes, monkeypatch, engine, benchmark_file
):
    cog = CogClassifier(replace(config, load_model=True, cog_url="http://cog:5000"))
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
    with TestClient(
        create_app(config, cog, benchmark_path=benchmark_file), base_url="http://localhost"
    ) as client:
        assert (
            client.post(
                "/api/identify", content=png_bytes, headers={"content-type": "image/png"}
            ).status_code
            == 429
        )
    assert not cog.lock.locked()

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200,
            json={"status": "failed", "error": "boom"},
            request=httpx.Request("POST", "http://cog:5000/predictions"),
        ),
    )
    with TestClient(
        create_app(config, cog, benchmark_path=benchmark_file), base_url="http://localhost"
    ) as client:
        assert (
            client.post(
                "/api/identify", content=png_bytes, headers={"content-type": "image/png"}
            ).status_code
            == 503
        )

    fake_output = engine.predict(decode_image(png_bytes, config))
    fake_output.update(elapsed_ms=15, model="Cog", score_note="note")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200,
            json={"status": "succeeded", "output": fake_output},
            request=httpx.Request("POST", "http://cog:5000/predictions"),
        ),
    )
    with TestClient(
        create_app(config, cog, benchmark_path=benchmark_file), base_url="http://localhost"
    ) as client:
        res = client.post("/api/identify", content=png_bytes, headers={"content-type": "image/png"})
        assert res.status_code == 200
        assert cog.baseline_accuracy == 0.56
        assert cog.optimized_accuracy == 0.91
