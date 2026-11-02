from dataclasses import replace

from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_valid_image_returns_cited_profile_without_image(client, engine, jpeg):
    response = client.post("/api/identify", content=jpeg, headers={"content-type": "image/jpeg"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "matched"
    assert data["knowledge"]["live"] is False
    assert data["knowledge"]["source_url"].startswith("https://")
    assert "not probabilities" in data["score_note"]
    assert "image" not in data and "filename" not in data
    assert response.headers["cache-control"] == "no-store"
    assert engine.calls == 1


def test_decode_content_not_content_type(client, engine):
    response = client.post(
        "/api/identify", content=b"<script>bad</script>", headers={"content-type": "image/jpeg"}
    )
    assert response.status_code == 422
    assert engine.calls == 0
    assert not engine.lock.locked()


def test_unsupported_media_type(client, engine, jpeg):
    assert (
        client.post(
            "/api/identify", content=jpeg, headers={"content-type": "text/plain"}
        ).status_code
        == 415
    )
    assert engine.calls == 0


def test_declared_oversize_rejected(client, engine):
    response = client.post(
        "/api/identify",
        content=b"x",
        headers={"content-type": "image/jpeg", "content-length": "999999999"},
    )
    assert response.status_code == 413
    assert engine.calls == 0


def test_stream_size_limit_even_with_lying_content_length(config, engine):
    with TestClient(
        create_app(replace(config, max_upload_bytes=32), engine), base_url="http://localhost"
    ) as client:
        response = client.post(
            "/api/identify",
            content=b"x" * 33,
            headers={"content-type": "image/jpeg", "content-length": "1"},
        )
        assert response.status_code == 413
    assert not engine.lock.locked()
    assert engine.calls == 0


def test_single_request_admission_control(client, engine, jpeg):
    engine.lock.acquire()
    try:
        response = client.post(
            "/api/identify", content=jpeg, headers={"content-type": "image/jpeg"}
        )
        assert response.status_code == 429
        assert response.headers["retry-after"] == "3"
        assert engine.calls == 0
    finally:
        engine.lock.release()


def test_model_error_is_safe_and_releases_lock(client, engine, jpeg):
    engine.fail = True
    response = client.post("/api/identify", content=jpeg, headers={"content-type": "image/jpeg"})
    assert response.status_code == 503
    assert "test-only" not in response.text
    assert not engine.lock.locked()


def test_not_ready_is_explicit_not_fake_inference(client, engine, jpeg):
    engine.status = "loading"
    response = client.post("/api/identify", content=jpeg, headers={"content-type": "image/jpeg"})
    assert response.status_code == 503
    assert client.get("/api/ready").status_code == 503
    assert engine.calls == 0


def test_cross_origin_and_untrusted_host_rejected(client, jpeg):
    response = client.post(
        "/api/identify",
        content=jpeg,
        headers={"content-type": "image/jpeg", "origin": "https://evil.example"},
    )
    assert response.status_code == 403
    response = client.get("/api/health", headers={"host": "attacker.example"})
    assert response.status_code == 400


def test_same_origin_works(client, jpeg):
    response = client.post(
        "/api/identify",
        content=jpeg,
        headers={"content-type": "image/jpeg", "origin": "http://localhost"},
    )
    assert response.status_code == 200


def test_known_species_only(client):
    assert len(client.get("/api/species").json()["species"]) == 41
    assert client.get("/api/species/domestic-cat").status_code == 200
    assert client.get("/api/species/arbitrary-attacker-page").status_code == 404


def test_static_site_has_restrictive_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "A familiar face." in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "object-src 'none'" in response.headers["content-security-policy"]
    assert "camera=()" in response.headers["permissions-policy"]
    assert client.get("/.env").status_code == 404
    assert client.get("/backend/app/config.py").status_code == 404


def test_malformed_and_wrong_scheme_origins_fail_closed(client, jpeg):
    for origin in ("https://[", "null", "https://localhost"):
        response = client.post(
            "/api/identify", content=jpeg, headers={"content-type": "image/jpeg", "origin": origin}
        )
        assert response.status_code == 403
