import httpx
import pytest

from backend.app.catalogue import get_species
from backend.app.knowledge import KnowledgeService


def fake_upstream(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


async def test_live_summary_is_cited_and_cached(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "en.wikipedia.org"
        assert request.url.path == "/api/rest_v1/page/summary/Cat"
        return httpx.Response(
            200, json={"type": "standard", "title": "Cat", "extract": "A cat is a small mammal."}
        )

    fake_upstream(monkeypatch, handler)
    service = KnowledgeService()
    species = get_species("domestic-cat")
    result = await service.get(species)
    assert result["live"] is True
    assert result["license"] == "CC BY-SA 4.0"
    assert result["source_url"] == "https://en.wikipedia.org/wiki/Cat"
    assert result == await service.get(species)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429),
        httpx.Response(503),
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json={"query": {"pages": [{"missing": True}]}}),
        httpx.Response(200, content=b"x" * 100_001),
        httpx.Response(200, json={"type": "standard", "title": "Cat", "extract": []}),
        httpx.Response(
            200, json={"type": "disambiguation", "title": "Cat", "extract": "Ambiguous"}
        ),
        httpx.Response(200, json=[]),
    ],
)
async def test_network_and_content_failures_use_curated_fallback(monkeypatch, response):
    fake_upstream(monkeypatch, lambda request: response)
    species = get_species("tiger")
    result = await KnowledgeService().get(species)
    assert result["live"] is False
    assert result["text"] == species["summary"]


async def test_offline_never_contacts_wikipedia(monkeypatch):
    def handler(request):
        pytest.fail("Unexpected external call")

    fake_upstream(monkeypatch, handler)
    assert (await KnowledgeService(enabled=False).get(get_species("lion")))["live"] is False
