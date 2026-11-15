"""FastAPI application, upload boundary, security header, and route tests."""

from dataclasses import replace

from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_valid_image_returns_side_by_side_comparison(client, engine, png_bytes):
    response = client.post(
        "/api/identify", content=png_bytes, headers={"content-type": "image/png"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "matched"
    assert data["baseline"]["architecture"] == "TutorialCifarNet"
    assert data["optimized"]["architecture"] == "CifarResNet9"
    assert data["comparison"]["agreement"] is True
    assert "image" not in data and "filename" not in data
    assert response.headers["cache-control"] == "no-store"
    assert engine.calls == 1


def test_decode_content_not_content_type(client, engine):
    response = client.post(
        "/api/identify", content=b"<script>bad</script>", headers={"content-type": "image/png"}
    )
    assert response.status_code == 422
    assert engine.calls == 0
    assert not engine.lock.locked()


def test_unsupported_media_type(client, engine, jpeg_bytes):
    response = client.post(
        "/api/identify", content=jpeg_bytes, headers={"content-type": "text/plain"}
    )
    assert response.status_code == 415
    assert engine.calls == 0


def test_invalid_and_oversized_content_length_rejected(client, engine):
    for bad_len, expected in [("abc", 400), ("-1", 400), ("999999999", 413)]:
        response = client.post(
            "/api/identify",
            content=b"x",
            headers={"content-type": "image/png", "content-length": bad_len},
        )
        assert response.status_code == expected
    assert engine.calls == 0


def test_stream_size_limit_even_with_lying_content_length(config, engine, benchmark_file):
    with TestClient(
        create_app(replace(config, max_upload_bytes=32), engine, benchmark_path=benchmark_file),
        base_url="http://localhost",
    ) as limited_client:
        response = limited_client.post(
            "/api/identify",
            content=b"x" * 33,
            headers={"content-type": "image/png", "content-length": "1"},
        )
        assert response.status_code == 413
    assert not engine.lock.locked()
    assert engine.calls == 0


def test_single_request_admission_control(client, engine, png_bytes):
    engine.lock.acquire()
    try:
        response = client.post(
            "/api/identify", content=png_bytes, headers={"content-type": "image/png"}
        )
        assert response.status_code == 429
        assert response.headers["retry-after"] == "3"
        assert engine.calls == 0
    finally:
        engine.lock.release()


def test_model_error_is_safe_and_releases_lock(client, engine, png_bytes):
    engine.fail = True
    response = client.post(
        "/api/identify", content=png_bytes, headers={"content-type": "image/png"}
    )
    assert response.status_code == 503
    assert "test-only" not in response.text
    assert not engine.lock.locked()


def test_not_ready_returns_503(client, engine, png_bytes):
    engine.status = "loading"
    assert (
        client.post(
            "/api/identify", content=png_bytes, headers={"content-type": "image/png"}
        ).status_code
        == 503
    )
    assert client.get("/api/ready").status_code == 503
    assert engine.calls == 0


def test_ready_and_health_routes(client):
    assert client.get("/api/ready").status_code == 200
    health = client.get("/api/health").json()
    assert health["status"] == "ready"
    assert health["class_count"] == 10
    assert health["baseline_accuracy"] == 0.56
    assert health["optimized_accuracy"] == 0.91


def test_cross_origin_and_untrusted_host_rejected(client, png_bytes):
    for origin in ("https://evil.example", "https://[", "null", "https://localhost"):
        response = client.post(
            "/api/identify",
            content=png_bytes,
            headers={"content-type": "image/png", "origin": origin},
        )
        assert response.status_code == 403
    assert client.get("/api/health", headers={"host": "attacker.example"}).status_code == 400


def test_same_origin_works(client, png_bytes):
    response = client.post(
        "/api/identify",
        content=png_bytes,
        headers={"content-type": "image/png", "origin": "http://localhost"},
    )
    assert response.status_code == 200


def test_catalogue_and_benchmarks_routes(client, config, engine, tmp_path):
    items = client.get("/api/classes").json()["classes"]
    assert len(items) == 10
    assert items[0]["optimized_accuracy"] == 0.91
    assert client.get("/api/classes/airplane").status_code == 200
    assert client.get("/api/classes/nonexistent").status_code == 404
    bench = client.get("/api/benchmarks")
    assert bench.status_code == 200
    assert len(bench.json()["trials"]) == 2

    with TestClient(
        create_app(config, engine, benchmark_path=tmp_path / "missing.json"),
        base_url="http://localhost",
    ) as no_bench_client:
        assert no_bench_client.get("/api/benchmarks").status_code == 404


def test_static_site_has_restrictive_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Ten natural scenes." in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "object-src 'none'" in response.headers["content-security-policy"]
    assert "camera=()" in response.headers["permissions-policy"]
    assert client.get("/.env").status_code == 404
    assert client.get("/backend/app/config.py").status_code == 404
