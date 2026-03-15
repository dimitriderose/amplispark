import logging
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import CORS_ORIGINS
from backend.middleware import verify_brand_owner  # noqa: F401 — exported for route-level Depends()

from backend.routers import brands, plans, posts, generation, media, integrations, voice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Amplifi API",
    description="AI-powered social media content generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(voice.router, prefix="/api", dependencies=[Depends(verify_brand_owner)])

# ── Static frontend (production) ──────────────────────────────
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    from starlette.responses import FileResponse as _FileResponse

    _index_html = os.path.join(frontend_dist, "index.html")
    _resolved_dist = os.path.realpath(frontend_dist)

    # Static assets first (proper caching headers + content-type detection)
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    # SPA catch-all: serve index.html for any non-API, non-file route
    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        resolved = os.path.realpath(file_path)
        # Prevent path traversal — only serve files within frontend_dist
        if (resolved.startswith(_resolved_dist + os.sep) or resolved == _resolved_dist) and os.path.isfile(resolved):
            return _FileResponse(resolved)
        return _FileResponse(_index_html)
