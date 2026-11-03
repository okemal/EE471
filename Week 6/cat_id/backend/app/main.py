"""Same-origin local web app. Run one worker so only one GPU model is loaded."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .catalogue import get_species, species_catalogue
from .cog_client import CogClassifier, ModelBusy
from .config import ROOT, Settings, settings
from .images import InvalidImage, decode_image
from .knowledge import KnowledgeService
from .model import BIOCLIP, Classifier
from .schemas import Catalogue, Health, Identification, SpeciesDetail

logger = logging.getLogger(__name__)


def create_app(config: Settings = settings, classifier=None) -> FastAPI:
    engine = (
        classifier
        if classifier is not None
        else (CogClassifier(config) if config.cog_url else Classifier(config))
    )
    knowledge = KnowledgeService(config.wikipedia_enabled and not config.offline)

    @asynccontextmanager
    async def lifespan(app):
        task = None
        if config.load_model and classifier is None:
            task = asyncio.create_task(run_in_threadpool(engine.load))
        yield
        if task is not None:
            await task

    app = FastAPI(
        title="Felis · Local species identifier",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.classifier = engine
    app.state.knowledge = knowledge
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    @app.middleware("http")
    async def browser_security(request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            allowed_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin and origin != allowed_origin
            ):
                return JSONResponse(
                    {"detail": "Cross-origin uploads are not allowed."}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; "
            "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health", response_model=Health)
    async def health():
        if isinstance(engine, CogClassifier):
            await run_in_threadpool(engine.refresh_health)
        return {
            "status": engine.status,
            "device": engine.device,
            "model": getattr(engine, "name", BIOCLIP.name),
            "species_count": len(species_catalogue()),
            "error": engine.error,
            "offline": config.offline,
            "max_upload_bytes": config.max_upload_bytes,
            "taxonomy": "IUCN CCTF 2017 · 41 species concepts",
        }

    @app.get("/api/ready")
    async def ready():
        if isinstance(engine, CogClassifier):
            await run_in_threadpool(engine.refresh_health)
        if engine.status != "ready":
            raise HTTPException(503, "The local model is not ready yet.")
        return {"status": "ready"}

    @app.get("/api/species", response_model=Catalogue)
    async def species():
        return {"species": species_catalogue(), "taxonomy": "IUCN CCTF 2017"}

    @app.get("/api/species/{species_id}", response_model=SpeciesDetail)
    async def species_detail(species_id: str):
        item = get_species(species_id)
        if item is None:
            raise HTTPException(404, "This species is not in the field guide.")
        return {"species": item, "knowledge": await knowledge.get(item)}

    @app.post(
        "/api/identify",
        response_model=Identification,
        response_model_exclude_none=True,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    media: {"schema": {"type": "string", "format": "binary"}}
                    for media in (
                        "image/jpeg",
                        "image/png",
                        "image/webp",
                        "application/octet-stream",
                    )
                },
            }
        },
        responses={
            413: {"description": "Image exceeds the byte limit"},
            415: {"description": "Unsupported Content-Type"},
            422: {"description": "Invalid, animated, or oversized decoded image"},
            429: {"description": "Another image is being processed"},
            503: {"description": "Model unavailable or inference failed"},
        },
    )
    async def identify(request: Request):
        media_type = request.headers.get("content-type", "").split(";")[0]
        if media_type not in {"image/jpeg", "image/png", "image/webp", "application/octet-stream"}:
            raise HTTPException(415, "Upload a JPEG, PNG, or WebP image as the request body.")
        size_header = request.headers.get("content-length")
        if size_header is not None:
            try:
                declared_size = int(size_header)
            except ValueError:
                raise HTTPException(400, "Invalid upload length.") from None
            if declared_size < 0:
                raise HTTPException(400, "Invalid upload length.")
            if declared_size > config.max_upload_bytes:
                raise HTTPException(413, "This image is too large. Choose a file under 10 MB.")
        if isinstance(engine, CogClassifier):
            await run_in_threadpool(engine.refresh_health)
        if engine.status != "ready":
            raise HTTPException(
                503, engine.error or "The local model is warming up. Please try again shortly."
            )
        if not engine.lock.acquire(blocking=False):
            raise HTTPException(
                429,
                "Another photo is being examined. Please try again in a moment.",
                headers={"Retry-After": "3"},
            )
        start = time.perf_counter()
        image = None
        try:
            data = bytearray()
            async with asyncio.timeout(30):
                async for chunk in request.stream():
                    if len(data) + len(chunk) > config.max_upload_bytes:
                        raise HTTPException(
                            413, "This image is too large. Choose a file under 10 MB."
                        )
                    data.extend(chunk)
            image = await run_in_threadpool(decode_image, bytes(data), config)
            data.clear()
            result = await run_in_threadpool(engine.predict, image)
        except InvalidImage as exc:
            raise HTTPException(422, str(exc)) from None
        except ModelBusy:
            raise HTTPException(
                429,
                "The Cog model is busy. Please try again shortly.",
                headers={"Retry-After": "3"},
            ) from None
        except TimeoutError:
            raise HTTPException(408, "The upload took too long. Please try again.") from None
        except HTTPException:
            raise
        except Exception:
            logger.exception("Local inference failed")
            raise HTTPException(
                503,
                "The local model could not finish this image. Try again or check the server log.",
            ) from None
        finally:
            if image is not None:
                image.close()
            engine.lock.release()
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000)
        result["model"] = getattr(engine, "name", BIOCLIP.name)
        result["score_note"] = (
            "Cosine similarities compare this photo with catalogue descriptions. "
            "They are not probabilities or verified confidence."
        )
        if result["status"] == "matched":
            result["knowledge"] = await knowledge.get(result["candidates"][0]["species"])
        return result

    app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
    return app


app = create_app()
