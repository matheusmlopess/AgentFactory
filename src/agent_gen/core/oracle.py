"""Optional completeness oracle for the compiled-brief preamble (#126).

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import logging
from pathlib import Path

from .constants import HARNESS_ROOT

logger = logging.getLogger(__name__)


def _run_preamble_oracle(original: str, truncated: str, project_root: str) -> int | None:
    """Run phases 1+2 of the completeness oracle on truncated preamble vs original.

    Returns score (0-100) or None if oracle is unavailable or errors.
    Prints result to stderr. Never raises.
    """
    try:
        script_path = Path(project_root) / HARNESS_ROOT / "scripts" / "skill-completeness-check.py"
        if not script_path.exists():
            return None
        import importlib.util

        spec = importlib.util.spec_from_file_location("_oracle", script_path)
        if spec is None or spec.loader is None:
            return None
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        if not hasattr(oracle, "make_client"):
            return None  # project still has a pre-2.1 oracle script
        try:
            # Claude subscription (Claude Code CLI) first, ANTHROPIC_API_KEY as the optional fallback.
            client = oracle.make_client()
        except oracle.ClaudeAccessError:
            return None
        model = oracle._DEFAULT_MODEL
        atoms = oracle.phase1_extract_atoms(client, original, model)
        results = oracle.phase2_verify_atoms(client, atoms, truncated, model)
        score, _ = oracle.compute_score(atoms, results)
        logger.warning("⚠ preamble completeness: %s%%", score)
        return score
    except Exception:
        logger.debug("preamble oracle unavailable", exc_info=True)
        return None
