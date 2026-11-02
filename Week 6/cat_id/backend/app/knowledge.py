"""Optional, bounded Wikipedia enrichment keyed only by the curated catalogue.

Failures always fall back to the local profile. Uploads, names, and image
embeddings never leave the process; only a known article title is requested.
"""

import asyncio
import json
import time
from urllib.parse import quote

import httpx


class KnowledgeService:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.cache: dict[str, tuple[float, dict]] = {}
        self.lock = asyncio.Lock()

    async def get(self, species: dict) -> dict:
        fallback = {
            "text": species["summary"],
            "source": "Curated field guide",
            "source_url": species["source_url"],
            "live": False,
            "license": None,
            "retrieved_at": None,
        }
        if not self.enabled:
            return fallback
        key = species["id"]
        cached = self.cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        # Bound concurrent upstream traffic and re-check after waiting.
        async with self.lock:
            cached = self.cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            try:
                async with asyncio.timeout(5):
                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(4, connect=2),
                        follow_redirects=False,
                        headers={
                            "User-Agent": "FelisLocal/1.0 (local educational Felidae identifier)"
                        },
                    ) as client:
                        title = quote(species["wikipedia_title"].replace(" ", "_"), safe="")
                        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + title
                        async with client.stream("GET", url) as response:
                            response.raise_for_status()
                            body = bytearray()
                            async for chunk in response.aiter_bytes():
                                if len(body) + len(chunk) > 100_000:
                                    raise ValueError("Oversized knowledge response")
                                body.extend(chunk)
                        page = json.loads(body)
                        if not isinstance(page, dict) or page.get("type") != "standard":
                            raise ValueError("Not a species article")
                        extract = page.get("extract")
                        if not isinstance(extract, str) or not extract.strip():
                            raise ValueError("Missing article extract")
                        if not isinstance(page.get("title"), str) or not page["title"]:
                            raise ValueError("Missing article title")
                        extract = extract.strip()
                        result = {
                            "text": extract[:1800],
                            "source": "Wikipedia",
                            "source_url": "https://en.wikipedia.org/wiki/"
                            + quote(page["title"].replace(" ", "_")),
                            "live": True,
                            "license": "CC BY-SA 4.0",
                            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        }
                        self.cache[key] = (time.monotonic() + 86400, result)
                        return result
            except (httpx.HTTPError, TimeoutError, ValueError, KeyError, IndexError, TypeError):
                # Brief negative caching prevents a failed service slowing every identification.
                self.cache[key] = (time.monotonic() + 60, fallback)
                return fallback
