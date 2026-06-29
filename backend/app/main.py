"""
Application entry point.

Creates the FastAPI application, mounts routes, and serves static files
for the minimal UI.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from backend.app.database import init_db
from backend.app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="Chat Service",
    description="One-to-one messaging REST API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)

# Serve minimal UI
frontend_path = os.path.join(os.path.dirname(__file__), "../../frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_ui():
        return FileResponse(os.path.join(frontend_path, "index.html"))
