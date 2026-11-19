"""The `agentfactory-gen` click group, `_echo` and the logging bridge.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

import logging

import click

from .. import __version__


class _ClickLogHandler(logging.Handler):
    """Shows library warnings (agent_gen.core uses logging, not print) on stderr through click."""

    def emit(self, record: logging.LogRecord) -> None:
        click.echo(f"[librarian] {self.format(record)}", err=True)


def _configure_logging(quiet: bool) -> None:
    lib = logging.getLogger("agent_gen")
    if not any(isinstance(h, _ClickLogHandler) for h in lib.handlers):
        lib.addHandler(_ClickLogHandler())
        lib.propagate = False
    lib.setLevel(logging.ERROR if quiet else logging.WARNING)


@click.group()
@click.version_option(__version__, prog_name="agentfactory-gen")
@click.option("--quiet", "-q", is_flag=True, default=False, help="Suppress informational output.")
@click.pass_context
def cli(ctx: click.Context, quiet: bool):
    """Agent Factory — Librarian-powered agent lifecycle manager."""
    ctx.ensure_object(dict)
    ctx.obj["quiet"] = quiet
    _configure_logging(quiet)


def _echo(msg: str, *, err: bool = False) -> None:
    """Print msg unless the current Click context has quiet=True."""
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.obj and ctx.obj.get("quiet") and not err:
        return
    click.echo(msg, err=err)
