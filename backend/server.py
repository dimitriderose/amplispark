import logging
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger.json import JsonFormatter
from starlette.responses import JSONResponse

from backend.config import CORS_ORIGINS
from backend.middleware import verify_brand_owner  # noqa: F401 — exported for route-level Depends()
from backend.middleware_logging import RequestContextMiddleware

from backend.routers import brands, plans, posts, generation, media, integrations, voice

_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    rename_fields={"asctime": "timestamp", "levelname": "severity"},
))
logging.root.handlers = [_handler]
logging.root.setLevel(logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Amplispark API",
    description="AI-powered social media content generation",
    version="1.0.0",
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "X-User-UID"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("unhandled_exception", extra={
        "path": request.url.path,
        "method": request.method,
        "error": str(exc),
        "type": type(exc).__name__,
    })
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# ── Health ────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "amplifi-backend", "version": "1.0.0"}

# ── Routers ──────────────────────────────────────────────────

app.include_router(brands.router, prefix="/api", dependencies=[Depends(verify_brand_owner)])
app.include_router(plans.router, prefix="/api", dependencies=[Depends(verify_brand_owner)])
app.include_router(posts.router, prefix="/api", dependencies=[Depends(verify_brand_owner)])
app.include_router(generation.router, prefix="/api", dependencies=[Depends(verify_brand_owner)])
app.include_router(media.router, prefix="/api", dependencies=[Depends(verify_brand_owner)])
app.include_router(integrations.router, prefix="/api", dependencies=[Depends(verify_brand_owner)])
# Voice router uses WebSocket — auth injected at endpoint level (not router-level)
# because WebSocket Depends() requires a WebSocket object, not an HTTP Request
app.include_router(voice.router, prefix="/api")

# ── Static frontend (production) ──────────────────────────────
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    from pathlib import Path
    from starlette.responses import FileResponse as _FileResponse

    _index_html = os.path.join(frontend_dist, "index.html")

    # Static assets first (proper caching headers + content-type detection)
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    # SPA catch-all: serve index.html for any non-API, non-file route
    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        # Prevent path traversal — only serve files within frontend_dist
        try:
            Path(file_path).resolve().relative_to(Path(frontend_dist).resolve())
            if os.path.isfile(file_path):
                return _FileResponse(file_path)
        except ValueError:
            pass
        return _FileResponse(_index_html)
