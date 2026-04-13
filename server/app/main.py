from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.database import init_auth_database
from app.core.config import ensure_directories, get_settings
from app.services.state import AppContainer

settings = get_settings()
ensure_directories(settings)
container = AppContainer(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_auth_database()
    container.startup()
    try:
        yield
    finally:
        container.shutdown()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)
app.state.container = container

allow_credentials = settings.cors_allow_origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

web_ui_dir = Path(__file__).resolve().parents[1] / "web_ui"
if web_ui_dir.exists():
    app.mount("/web-client", StaticFiles(directory=str(web_ui_dir), html=True), name="web-client")


@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    if web_ui_dir.exists():
        return RedirectResponse(url="/web-client")
    return RedirectResponse(url="/docs")
