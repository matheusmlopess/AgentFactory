"""agentfactory-gen CLI — entry point.

Commands live in `agent_gen.commands` (one module per group, split in #190). Importing them registers them on the
`cli` group. Names that used to live here are re-exported so `from agent_gen.cli import ...` keeps working.
"""

from __future__ import annotations

from .commands._group import _ClickLogHandler, _configure_logging, _echo, cli  # noqa: F401
from .commands._paths import _agent_root, _assert_valid_project_root, _assert_within_root  # noqa: F401
from .commands._remote import (  # noqa: F401
    DEFAULT_API_URL,
    REGISTRY_URL,
    _api_json,
    _attach_auth_header,
    _registry_fetch,
    _registry_publish,
    _require_safe_url,
    _resolve_api_url,
    _token_path,
    _write_token,
)
from .commands._sources import (  # noqa: F401
    _clone_and_prepare,
    _find_agent_dir,
    _normalize_git_url,
    _verify_publisher_signature,
)
from .commands.account import login, logout, whoami  # noqa: F401
from .commands.agents import audit, deploy, describe, publish, retrofit, sign, uninstall, wrap  # noqa: F401
from .commands.orchestrate import (  # noqa: F401
    _WORKFLOW_SUFFIXES,
    _resolve_workflow_path,
    orchestrate_group,
    orchestrate_init,
    orchestrate_list,
    orchestrate_run,
    orchestrate_validate,
)
from .commands.project import (  # noqa: F401
    _adapter_completeness_gate,
    _load_completeness_threshold,
    adapter_add,
    adapter_group,
    brief_cmd,
    init_project,
)
from .commands.transfer import export_agent, import_agent, import_skill  # noqa: F401
