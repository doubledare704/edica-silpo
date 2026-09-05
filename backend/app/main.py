import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import agent, stores
from .config import settings
from .logging_config import configure_logging

configure_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)

app = FastAPI(title="Silpo Smart Shopper Agent")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory for mock audio files if present
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(stores.router)
app.include_router(agent.router)
