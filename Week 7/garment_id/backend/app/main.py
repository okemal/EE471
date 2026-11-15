"""Same-origin local FastAPI web application for Atelier garment classification."""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .catalogue import garment_catalogue, get_garment
from .cog_client import CogClassifier, ModelBusy
from .config import ROOT, Settings, settings
from .images import InvalidImage, decode_image
from .model import DualGarmentClassifier
from .schemas import BenchmarkReport, Catalogue, GarmentDetail, Health, Identification

logger = logging.getLogger(__name__)
BENCHMARK_PATH: Path = ROOT / "backend" / "app" / "data" / "benchmark.json"


def _load_benchmark_data(path=BENCHMARK_PATH) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def create_app(
    config: Settings = settings, classifier=None, benchmark_path=BENCHMARK_PATH
) -> FastAPI:
    """Create the FastAPI application wired to either direct PyTorch inference or Cog."""
    engine = (
        classifier
        if classifier is not None
        else (CogClassifier(config) if config.cog_url else DualGarmentClassifier(config))
    )

    @asynccontextmanager
    async def lifespan(app):
        task = None
        if config.load_model and classifier is None:
            task = asyncio.create_task(run_in_threadpool(engine.load))
        yield
        if task is not None:
            await task

    app = FastAPI(
        title="Atelier · Garment Classifier & HPO Studio",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.classifier = engine
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
        benchmark = _load_benchmark_data(benchmark_path)
        baseline_acc = getattr(engine, "baseline_accuracy", None)
        optimized_acc = getattr(engine, "optimized_accuracy", None)
        if benchmark:
            baseline_acc = baseline_acc or benchmark["baseline"]["test_accuracy"]
            optimized_acc = optimized_acc or benchmark["optimized"]["test_accuracy"]
        return {
            "status": engine.status,
            "device": engine.device,
            "model": getattr(engine, "name", DualGarmentClassifier.name),
            "class_count": len(garment_catalogue()),
            "error": engine.error,
            "offline": config.offline,
            "max_upload_bytes": config.max_upload_bytes,
            "dataset": "FashionMNIST · 10 garment classes",
            "baseline_accuracy": baseline_acc,
            "optimized_accuracy": optimized_acc,
        }

    @app.get("/api/ready")
    async def ready():
        if isinstance(engine, CogClassifier):
            await run_in_threadpool(engine.refresh_health)
        if engine.status != "ready":
            raise HTTPException(503, "The local garment classifier is not ready yet.")
        return {"status": "ready"}

    @app.get("/api/garments", response_model=Catalogue)
    async def garments():
        benchmark = _load_benchmark_data(benchmark_path)
        per_class = (
            {row["id"]: row for row in benchmark.get("per_class_accuracy", [])} if benchmark else {}
        )
        enriched = []
        for item in garment_catalogue():
            row = per_class.get(item["id"])
            enriched.append(
                {
                    **item,
                    "baseline_accuracy": row["baseline_accuracy"] if row else None,
                    "optimized_accuracy": row["optimized_accuracy"] if row else None,
                }
            )
        return {"garments": enriched, "dataset": "FashionMNIST (Zalando Research)"}

    @app.get("/api/garments/{garment_id}", response_model=GarmentDetail)
    async def garment_detail(garment_id: str):
        item = get_garment(garment_id)
        if item is None:
            raise HTTPException(404, "This garment category is not in the catalogue.")
        benchmark = _load_benchmark_data(benchmark_path)
        row = None
        if benchmark:
            row = next(
                (r for r in benchmark.get("per_class_accuracy", []) if r["id"] == garment_id), None
            )
        return {
            "garment": {
                **item,
                "baseline_accuracy": row["baseline_accuracy"] if row else None,
                "optimized_accuracy": row["optimized_accuracy"] if row else None,
            },
            "baseline_accuracy": row["baseline_accuracy"] if row else None,
            "optimized_accuracy": row["optimized_accuracy"] if row else None,
        }

    @app.get("/api/benchmarks", response_model=BenchmarkReport)
    async def benchmarks():
        benchmark = _load_benchmark_data(benchmark_path)
        if benchmark is None:
            raise HTTPException(404, "Benchmark results are not generated yet.")
        return benchmark

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
                "Another garment photo is being examined. Please try again in a moment.",
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
            logger.exception("Local garment inference failed")
            raise HTTPException(
                503,
                "The local model could not finish this image. Try again or check the server log.",
            ) from None
        finally:
            if image is not None:
                image.close()
            engine.lock.release()
        result["elapsed_ms"] = round((time.perf_counter() - start) * 1000)
        result["model"] = getattr(engine, "name", DualGarmentClassifier.name)
        result["score_note"] = (
            "Softmax probabilities come from independent FashionMNIST baseline and HPO-optimized "
            "models trained on 28x28 grayscale studio garments."
        )
        return result

    app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
    return app


app = create_app()
