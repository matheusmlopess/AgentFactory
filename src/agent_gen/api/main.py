"""AgentFactory API — FastAPI application entry point."""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import auth, license

_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


app = FastAPI(
    title="AgentFactory API",
    description="Backend for the AgentFactory platform: auth, registry, and license validation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(license.router)


@app.get("/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok"}


def run() -> None:
    """Entry point for `agentfactory-api` CLI command."""
    import uvicorn
    uvicorn.run("agent_gen.api.main:app", host="0.0.0.0", port=8000, reload=True)
