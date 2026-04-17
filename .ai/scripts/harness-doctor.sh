#!/usr/bin/env bash
# harness-doctor — Live Harness Health Check (AgentFactory #19)
# <!-- version: 1.0.0 -->
#
# Usage:
#   harness-doctor [--target <cli>] [--quiet] [--ci] [--json] [--snapshot-only]
#
# Exit codes:
#   0  all checks pass (clean)
#   1  warnings present
#   2  critical violations found
#
# Reads harness structure from .ai/ in the current working directory.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
TARGET_CLI=""
QUIET=0
CI_MODE=0
JSON_OUTPUT=0
SNAPSHOT_ONLY=0
COMPLETENESS_CHECK=0
AI_ROOT=".ai"
SNAPSHOT_PATH="${AI_ROOT}/.harness-health.json"

# Token budget thresholds (bytes / approx chars-per-token ratio)
WARN_THRESHOLD=6000    # ~1500 tokens
CRITICAL_THRESHOLD=12000  # ~3000 tokens

EXIT_CODE=0
declare -a WARNINGS=()
declare -a CRITICALS=()

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)       TARGET_CLI="$2"; shift 2 ;;
    --quiet)        QUIET=1; shift ;;
    --ci)           CI_MODE=1; shift ;;
    --json)         JSON_OUTPUT=1; shift ;;
    --snapshot-only) SNAPSHOT_ONLY=1; shift ;;
    --completeness) COMPLETENESS_CHECK=1; shift ;;
    *) echo "[harness-doctor] Unknown option: $1" >&2; exit 2 ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { [[ $QUIET -eq 0 ]] && echo "$1" || true; }
warn()  { WARNINGS+=("$1");  [[ $QUIET -eq 0 ]] && echo "  ⚠  $1" || true; }
crit()  { CRITICALS+=("$1"); [[ $QUIET -eq 0 ]] && echo "  ✘  $1" >&2 || true; }
ok()    { [[ $QUIET -eq 0 ]] && echo "  ✓  $1" || true; }

file_size() { wc -c < "$1" 2>/dev/null || echo 0; }

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

check_harness_root() {
  if [[ ! -d "${AI_ROOT}" ]]; then
    crit "Harness root '${AI_ROOT}/' not found — run 'agentfactory-gen init' first."
    return
  fi
  ok "Harness root '${AI_ROOT}/' present"
}

check_source_of_truth() {
  local ctx="${AI_ROOT}/AgentFactory.md"
  if [[ ! -f "${ctx}" ]]; then
    warn "AgentFactory.md missing — context file not found"
    return
  fi
  local size; size=$(file_size "${ctx}")
  if (( size > CRITICAL_THRESHOLD )); then
    crit "AgentFactory.md is ${size} bytes — exceeds critical token budget (${CRITICAL_THRESHOLD})"
  elif (( size > WARN_THRESHOLD )); then
    warn "AgentFactory.md is ${size} bytes — approaching token budget (warn at ${WARN_THRESHOLD})"
  else
    ok "AgentFactory.md size: ${size} bytes"
  fi
}

check_global_manifest() {
  local manifest="${AI_ROOT}/agent-manifest.json"
  if [[ ! -f "${manifest}" ]]; then
    crit "Global agent-manifest.json missing"
    return
  fi
  if ! python3 -m json.tool "${manifest}" > /dev/null 2>&1; then
    crit "Global agent-manifest.json is invalid JSON"
  else
    ok "Global agent-manifest.json valid"
  fi
}

check_milestones() {
  local m="${AI_ROOT}/memory/milestones.md"
  if [[ ! -f "${m}" ]]; then
    warn "milestones.md missing — traceability matrix not initialised"
    return
  fi
  ok "milestones.md present"
}

check_adapter_wiring() {
  local missing=0
  for link in \
    "${AI_ROOT}/adapters/claude/commands" \
    "${AI_ROOT}/adapters/claude/skills" \
    "${AI_ROOT}/adapters/gemini/tools" \
    "${AI_ROOT}/adapters/codex/prompts"; do
    if [[ ! -e "${link}" ]]; then
      warn "Adapter symlink missing: ${link}"
      missing=1
    fi
  done
  [[ $missing -eq 0 ]] && ok "Adapter capability symlinks present"
}

check_skills_budget() {
  local skills_dir="${AI_ROOT}/skills"
  if [[ ! -d "${skills_dir}" ]]; then return; fi
  local total=0
  while IFS= read -r -d '' f; do
    total=$(( total + $(file_size "$f") ))
  done < <(find "${skills_dir}" -name "SKILL.md" -print0 2>/dev/null)
  if (( total > CRITICAL_THRESHOLD * 3 )); then
    crit "Total global skills size: ${total} bytes — critical token budget"
  elif (( total > WARN_THRESHOLD * 3 )); then
    warn "Total global skills size: ${total} bytes — warning token budget"
  else
    ok "Global skills total size: ${total} bytes"
  fi
}

check_version_markers() {
  local missing=0
  while IFS= read -r -d '' f; do
    if ! grep -q '<!-- version:' "$f" 2>/dev/null; then
      warn "Missing version marker: ${f}"
      missing=1
    fi
  done < <(find "${AI_ROOT}/rules" "${AI_ROOT}/skills" -name "*.md" -print0 2>/dev/null)
  [[ $missing -eq 0 ]] && ok "Version markers present in all rules/*.md and skills/*.md"
}

check_skills_completeness() {
  [[ $COMPLETENESS_CHECK -eq 0 ]] && return
  if ! command -v python3 &>/dev/null; then
    warn "Skill completeness: python3 not found — skipping"
    return
  fi
  if ! python3 -c "import anthropic" 2>/dev/null; then
    warn "Skill completeness: anthropic SDK not installed — skipping"
    return
  fi
  if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    warn "Skill completeness: ANTHROPIC_API_KEY not set — skipping"
    return
  fi
  local skills_dir="${AI_ROOT}/skills"
  if [[ ! -d "${skills_dir}" ]]; then return; fi
  while IFS= read -r -d '' skill_dir; do
    local name; name=$(basename "${skill_dir}")
    local out="${AI_ROOT}/reports/skill-${name}-completeness.json"
    local stderr_out rc score reason
    stderr_out=$(python3 "${AI_ROOT}/scripts/skill-completeness-check.py" \
        --skill "${name}" --adapter claude --out "${out}" --quiet 2>&1) && rc=0 || rc=$?
    score=$(python3 -c "import json; d=json.load(open('${out}')); print(d['score'])" 2>/dev/null || echo "?")
    if [[ $rc -eq 0 ]]; then
      ok "Skill completeness: ${name} (${score}%)"
    elif [[ $rc -eq 2 ]]; then
      reason=$(echo "${stderr_out}" | grep -o 'Error:[^'$'\033'']*' | head -1 | sed 's/\x1b\[[0-9;]*m//g' || echo "API error")
      warn "Skill completeness skipped: ${name} — ${reason}"
    else
      warn "Skill completeness below threshold: ${name} (${score}%)"
    fi
  done < <(find "${skills_dir}" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
}

# ---------------------------------------------------------------------------
# Run checks
# ---------------------------------------------------------------------------
log ""
log "═══════════════════════════════════════"
log "  harness-doctor v1.0.0"
log "  Target: ${TARGET_CLI:-all CLIs}"
log "═══════════════════════════════════════"
log ""

check_harness_root
check_source_of_truth
check_global_manifest
check_milestones
check_adapter_wiring
check_skills_budget
check_version_markers
check_skills_completeness

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
WARN_COUNT=${#WARNINGS[@]}
CRIT_COUNT=${#CRITICALS[@]}

if [[ $CRIT_COUNT -gt 0 ]]; then
  EXIT_CODE=2
elif [[ $WARN_COUNT -gt 0 ]]; then
  EXIT_CODE=1
fi

log ""
if [[ $EXIT_CODE -eq 0 ]]; then
  log "✓ Harness is healthy (0 warnings, 0 critical)"
elif [[ $EXIT_CODE -eq 1 ]]; then
  log "⚠ ${WARN_COUNT} warning(s) — review before next release"
else
  log "✘ ${CRIT_COUNT} critical violation(s) — fix before pushing" >&2
fi
log ""

# ---------------------------------------------------------------------------
# Write JSON snapshot
# ---------------------------------------------------------------------------
if [[ $SNAPSHOT_ONLY -eq 1 ]] || [[ $CI_MODE -eq 1 ]]; then
  python3 - <<PYEOF
import json, datetime
snap = {
    "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "exit_code": ${EXIT_CODE},
    "warnings": ${WARN_COUNT},
    "criticals": ${CRIT_COUNT},
    "warning_messages": $(printf '%s\n' "${WARNINGS[@]+"${WARNINGS[@]}"}" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().splitlines()))"),
    "critical_messages": $(printf '%s\n' "${CRITICALS[@]+"${CRITICALS[@]}"}" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().splitlines()))"),
}
with open("${SNAPSHOT_PATH}", "w") as f:
    json.dump(snap, f, indent=2)
print(f"[harness-doctor] Snapshot written to ${SNAPSHOT_PATH}")
PYEOF
fi

if [[ $JSON_OUTPUT -eq 1 ]]; then
  python3 -c "
import json
print(json.dumps({
    'exit_code': ${EXIT_CODE},
    'warnings': ${WARN_COUNT},
    'criticals': ${CRIT_COUNT},
}))
"
fi

exit ${EXIT_CODE}
