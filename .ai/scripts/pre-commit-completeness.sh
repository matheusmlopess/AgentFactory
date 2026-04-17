#!/usr/bin/env bash
# pre-commit-completeness.sh — SKILL.md completeness warning hook
# <!-- version: 1.0.0 -->
#
# Install:
#   cp .ai/scripts/pre-commit-completeness.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Bypass:
#   SKIP_COMPLETENESS_WARN=1 git commit ...
#
# The hook warns when a SKILL.md file is staged, prompts to confirm,
# and prints the CLI command to run the completeness check.
# Non-interactive environments (CI) detect no TTY and pass through.

set -euo pipefail

# ---------------------------------------------------------------------------
# Find staged SKILL.md files
# ---------------------------------------------------------------------------
SKILL_FILES=$(git diff --cached --name-only 2>/dev/null \
  | grep -E '^\.ai/skills/.*/SKILL\.md$' || true)

[[ -z "$SKILL_FILES" ]] && exit 0

# ---------------------------------------------------------------------------
# Already bypassed?
# ---------------------------------------------------------------------------
if [[ "${SKIP_COMPLETENESS_WARN:-0}" == "1" ]]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Print warning
# ---------------------------------------------------------------------------
echo ""
echo "  ⚠  SKILL.md staged for commit:"
while IFS= read -r f; do
  # Extract skill name from path .ai/skills/<name>/SKILL.md
  skill_name=$(echo "$f" | sed -E 's|\.ai/skills/([^/]+)/SKILL\.md|\1|')
  echo "     $f"
  echo "     → python3 .ai/scripts/skill-completeness-check.py --skill ${skill_name}"
done <<< "$SKILL_FILES"
echo ""
echo "  Running the check ensures the trimmed version preserves all"
echo "  functional atoms (commands, decision paths, error cases)."
echo "  Score must be ≥ 90% to pass CI."
echo ""

# ---------------------------------------------------------------------------
# Interactive prompt — skip if no TTY (CI, pipes, non-interactive shells)
# ---------------------------------------------------------------------------
if [[ ! -t 1 ]] || [[ ! -t 0 ]]; then
  # Non-interactive: pass through silently
  exit 0
fi

read -r -p "  Continue without running completeness check? [y/N] " REPLY
echo ""
case "$REPLY" in
  [yY][eE][sS]|[yY]) exit 0 ;;
  *) echo "  Commit aborted. Run the check above, then re-commit."; exit 1 ;;
esac
