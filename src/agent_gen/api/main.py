"""AgentFactory API — FastAPI application entry point."""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from .db import init_db
from .jwt_utils import check_config
from .routers import auth, license, registry

_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    check_config()
    init_db()
    yield


app = FastAPI(
    title="AgentFactory API",
    description="Backend for the AgentFactory platform: auth, registry, and license validation.",
    version=__version__,
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
app.include_router(registry.router)


@app.get("/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok"}


def run() -> None:
    """Entry point for the `agentfactory-api` command (see `agentfactory-api --help`)."""
    _cli()


def _build_cli():
    import click

    @click.group(invoke_without_command=True)
    @click.pass_context
    def cli(ctx: click.Context) -> None:
        """AgentFactory API server and admin commands. With no command: `serve`."""
        if ctx.invoked_subcommand is None:
            ctx.invoke(serve)

    @cli.command()
    @click.option("--host", default="127.0.0.1", show_default=True)
    @click.option("--port", default=8000, show_default=True, type=int)
    @click.option("--dev", is_flag=True, help="Auto-reload on code changes (development only).")
    def serve(host: str, port: int, dev: bool) -> None:
        """Run the API with uvicorn."""
        import uvicorn

        check_config()
        uvicorn.run("agent_gen.api.main:app", host=host, port=port, reload=dev)

    @cli.group()
    def keys() -> None:
        """Issue and revoke license keys (stored hashed in the database)."""

    @keys.command("add")
    @click.option("--plan", required=True, type=click.Choice(["free", "pro", "team", "enterprise"]))
    @click.option("--user-id", default=None, help="Optional users.id the key belongs to.")
    def keys_add(plan: str, user_id: str | None) -> None:
        """Create a key and print it once; only its hash is stored."""
        from .db import issue_license_key

        init_db()
        click.echo(issue_license_key(plan, user_id))

    @cli.group()
    def tokens() -> None:
        """Issue and revoke API tokens for the CLI (`~/.agentfactory/token`) until device login lands."""

    @tokens.command("add")
    @click.option("--user-id", default=None, help="users.id of the token owner.")
    @click.option("--github-handle", default=None, help="Look the owner up by GitHub handle instead.")
    @click.option("--label", default="", help="Free-text label, e.g. the machine name.")
    @click.option("--ttl-days", default=90, show_default=True, type=int, help="0 = no expiry.")
    def tokens_add(user_id: str | None, github_handle: str | None, label: str, ttl_days: int) -> None:
        """Create a token and print it once; only its hash is stored."""
        from .db import get_conn, issue_api_token

        init_db()
        if not user_id and github_handle:
            with get_conn() as conn:
                row = conn.execute("SELECT id FROM users WHERE github_handle = ?", (github_handle,)).fetchone()
            user_id = row["id"] if row else None
        if not user_id:
            raise click.ClickException("Unknown user: sign in once through the webapp, then pass --user-id or --github-handle.")
        try:
            click.echo(issue_api_token(user_id, label, ttl_days or None))
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

    @tokens.command("revoke")
    @click.argument("token")
    def tokens_revoke(token: str) -> None:
        """Revoke an API token."""
        from .db import revoke_api_token

        init_db()
        if not revoke_api_token(token):
            raise click.ClickException("No active token matches.")
        click.echo("revoked")

    @keys.command("revoke")
    @click.argument("key")
    def keys_revoke(key: str) -> None:
        """Revoke an issued key."""
        from .db import revoke_license_key

        init_db()
        if not revoke_license_key(key):
            raise click.ClickException("No active key matches.")
        click.echo("revoked")

    return cli


def _cli() -> None:
    _build_cli()()
