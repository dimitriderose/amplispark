import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import CORS_ORIGINS

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

app.include_router(brands.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(posts.router, prefix="/api")
app.include_router(generation.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(voice.router, prefix="/api")

# ── Static frontend (production) ──────────────────────────────
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    from starlette.responses import FileResponse as _FileResponse

    _index_html = os.path.join(frontend_dist, "index.html")

    # SPA catch-all: serve index.html for any non-API, non-file route
    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # If a real file exists, serve it (JS, CSS, images, etc.)
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return _FileResponse(file_path)
        # Otherwise serve index.html so the SPA router handles it
        return _FileResponse(_index_html)

    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
