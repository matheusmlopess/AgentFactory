"""Librarian — manifest integrity engine for the Agent Factory.

The implementation lives in `agent_gen.core` (split in #189). This module keeps the public import surface:
`from agent_gen.librarian import Librarian, MANIFEST_FILE, validate_name, ...` works as before.
"""

from __future__ import annotations

from .core.briefs import (  # noqa: F401
    _FORMAT_REGISTRY,
    _FORMATTER_DISPATCH,
    _collect_project_context,
    _fit_context_to_budget,
    _fmt_agents_list,
    _fmt_commands_list,
    _fmt_harness_identity,
    _fmt_rules_list,
    _fmt_skills_blocks,
    _fmt_skills_table,
    _fmt_skills_tools,
)
from .core.constants import CONTEXT_FILE, HARNESS_ROOT, MANIFEST_FILE, TRACKED_DIRS  # noqa: F401
from .core.harness import HarnessMixin
from .core.manifest import ManifestMixin
from .core.oracle import _run_preamble_oracle  # noqa: F401
from .core.registry import ProjectRegistryMixin
from .core.retrofit import (
    CONVERSION_PROFILES,  # noqa: F401
    RetrofitMixin,
)
from .core.safety import (  # noqa: F401
    _NAME_RE,
    _atomic_write_json,
    _inspect_zip,
    _safe_extract,
    _sanitize_for_markdown,
    _workflow_has_shell_steps,
    safe_child,
    validate_name,
)
from .core.skills import SkillsMixin
from .core.text import _extract_first_paragraph, _git_ref  # noqa: F401


class Librarian(ManifestMixin, SkillsMixin, RetrofitMixin, ProjectRegistryMixin, HarnessMixin):
    """Manifest integrity engine."""
