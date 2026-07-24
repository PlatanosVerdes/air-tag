"""FastAPI app: serves the Leaflet map and a small JSON API over stored points."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import Store
from .poller import Poller

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).parent
INDEX_HTML = BASE_DIR / "templates" / "map.html"
store = Store(config.DB_PATH)
poller = Poller(store)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await store.init()
    poller.start()
    yield
    await poller.stop()


app = FastAPI(title="air-tag", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/api/status")
async def status() -> dict:
    st = await store.stats()
    return {
        "configured": config.is_configured(),
        "poll_interval": config.POLL_INTERVAL,
        "last_error": poller.last_error,
        "tz": config.TZ,
        **st,
    }


@app.get("/api/points")
async def points(
    since: int | None = Query(None, description="unix seconds, inclusive"),
    until: int | None = Query(None, description="unix seconds, inclusive"),
    days: int | None = Query(None, description="shortcut: last N days"),
) -> JSONResponse:
    if since is None and days is not None:
        since = int(time.time()) - days * 86400
    rows = await store.points(since=since, until=until)
    return JSONResponse(rows)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(INDEX_HTML)
