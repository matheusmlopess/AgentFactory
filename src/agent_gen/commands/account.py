"""Account commands: login, logout, whoami.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

import click

from . import _remote
from ._group import _echo, cli
from ._remote import _api_json, _token_path, _write_token


@cli.command()
@click.option("--no-browser", is_flag=True, help="Print the URL instead of opening a browser.")
def login(no_browser: bool):
    """Sign in to the AgentFactory API with a one-time code (device login)."""
    import time
    import webbrowser

    start = _api_json("POST", "/auth/cli/device", {})
    url = start.get("verification_uri_complete") or start["verification_uri"]
    click.echo(f"[librarian] Open {start['verification_uri']} and enter the code: {start['user_code']}")
    if not no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    interval = float(start.get("interval", 5))
    deadline = time.monotonic() + int(start.get("expires_in", 600))
    while time.monotonic() < deadline:
        time.sleep(interval)
        poll = _api_json("POST", "/auth/cli/poll", {"device_code": start["device_code"]})
        if poll.get("status") == "authorized" and poll.get("token"):
            path = _write_token(poll["token"])
            handle = (poll.get("user") or {}).get("github_handle", "?")
            click.echo(f"[librarian] Signed in as {handle}. Token saved to {path} (mode 600).")
            return
        if poll.get("status") == "expired":
            raise click.ClickException("Login code expired or already used. Run 'agentfactory-gen login' again.")
    raise click.ClickException("Login timed out. Run 'agentfactory-gen login' again.")


@cli.command()
def logout():
    """Revoke this machine's API token and delete it."""
    path = _token_path()
    if not path.exists():
        click.echo("[librarian] Not signed in.")
        return
    try:
        _api_json("POST", "/auth/cli/logout", {}, auth=True)
    except click.ClickException as exc:
        _echo(f"[librarian] Could not revoke the token on the server ({exc.message}); deleting it locally.", err=True)
    path.unlink()
    click.echo("[librarian] Signed out.")


@cli.command()
def whoami():
    """Show the account the saved API token belongs to."""
    if not _token_path().exists():
        raise click.ClickException("Not signed in. Run 'agentfactory-gen login'.")
    me = _api_json("GET", "/auth/me", auth=True)
    click.echo(f"{me.get('github_handle')} ({me.get('plan')}) · {_remote.REGISTRY_URL}")
