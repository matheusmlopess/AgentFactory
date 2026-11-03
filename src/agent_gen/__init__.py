"""AgentFactory — agent_gen package.

The package version has one source: ``version`` in pyproject.toml. Installed copies read it
from package metadata; a plain source checkout (no install) reads pyproject.toml directly.
"""
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path


def _read_version() -> str:
    try:
        return _pkg_version("agentfactory-gen")
    except PackageNotFoundError:
        pass
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        import tomllib

        return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, ValueError):
        return "0.0.0+unknown"


__version__ = _read_version()
