"""Shared declarations for the Librarian mixins.

`Librarian` (agent_gen.librarian) composes ManifestMixin, SkillsMixin, RetrofitMixin, ProjectRegistryMixin and
HarnessMixin. Each mixin calls methods that another one defines; declaring them here lets mypy check every mixin
on its own. At runtime this class adds nothing but the two instance attributes' annotations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any


class LibrarianBase:
    agent_root: Path
    manifest_path: Path

    if TYPE_CHECKING:  # implemented by the mixins; declared for the type checker only

        def sync(self) -> dict: ...
        def _load_manifest(self) -> dict: ...
        @staticmethod
        def _parse_skill_md_version(skill_md_path: Path) -> str: ...

        @classmethod
        def update_harness_files(cls, project_root: str) -> None: ...

        @classmethod
        def _global_manifest_path(cls, project_root: str) -> Path: ...

        @classmethod
        def _get_lock(cls, project_root: str) -> Any: ...
