#!/usr/bin/env bash
# MVP walkthrough against a local API (#204):
#   API up → local account + token → init/deploy/describe/wrap → publish → registry lists it
#   → import --from-registry in a second project (checksum verified) → audit clean.
#
# Everything lives in a temporary workspace; your real ~/.agentfactory is never touched.
# Usage: scripts/e2e-local.sh [--keep]     (--keep leaves the API running and the workspace on disk)
# Needs: agentfactory-gen and agentfactory-api on PATH (pip install -e ".[api]" in a venv, or
#        uv tool install --editable '.[api]').
set -euo pipefail

KEEP=0; [ "${1:-}" = "--keep" ] && KEEP=1
PORT="${E2E_PORT:-8765}"
API="http://127.0.0.1:${PORT}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/af-e2e.XXXXXX")"
AF="${AGENTFACTORY_GEN:-agentfactory-gen}"
AFAPI="${AGENTFACTORY_API:-agentfactory-api}"

step() { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mFAIL: %s\033[0m\n' "$*" >&2; exit 1; }

export AGENTFACTORY_ENV=dev
export DATABASE_URL="sqlite:///${WORK}/data/agentfactory.db"
export REGISTRY_STORAGE_DIR="${WORK}/data/registry"
export API_PUBLIC_URL="$API"
export AGENTFACTORY_API_URL="$API"
# With --keep the API listens on all interfaces so a browser outside WSL2/containers can reach it.
HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
export CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173${HOST_IP:+,http://${HOST_IP}:5173}"
export HOME="${WORK}/home"           # CLI token lands here, not in your real home
mkdir -p "$HOME" "${WORK}/data"

cleanup() {
  if [ "$KEEP" = 0 ]; then
    [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
    rm -rf "$WORK"
  else
    echo; echo "Kept: API pid ${API_PID:-?} on $API, workspace $WORK"
  fi
}
trap cleanup EXIT

step "Start the API on $API"
BIND=127.0.0.1; [ "$KEEP" = 1 ] && BIND=0.0.0.0
"$AFAPI" serve --host "$BIND" --port "$PORT" >"${WORK}/api.log" 2>&1 &
API_PID=$!
for _ in $(seq 1 50); do curl -sf "$API/health" >/dev/null && break; sleep 0.2; done
curl -sf "$API/health" >/dev/null || { cat "${WORK}/api.log"; fail "API did not start"; }

step "Local account + API token (stands in for agentfactory-gen login)"
"$AFAPI" users add --github-handle e2e-dev --plan pro >/dev/null
mkdir -p "$HOME/.agentfactory"
"$AFAPI" tokens add --github-handle e2e-dev --label e2e > "$HOME/.agentfactory/token"
chmod 600 "$HOME/.agentfactory/token"
"$AF" whoami

step "Publisher project: build and publish 'e2e-demo'"
mkdir -p "${WORK}/publisher" && cd "${WORK}/publisher"
"$AF" -q init >/dev/null
"$AF" -q deploy e2e-demo >/dev/null
"$AF" describe e2e-demo --desc "End-to-end demo agent" >/dev/null
"$AF" -q wrap e2e-demo
"$AF" publish e2e-demo

step "Registry lists it"
curl -sf "$API/registry?q=e2e" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert [u["name"] for u in d]==["e2e-demo"], d; print("registry:", d[0]["name"], d[0]["latest_version"])'
curl -sf "$API/registry/e2e-demo" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("sha256:", d["sha256"][:16], "…  zip_url:", d["zip_url"])'

step "Consumer project: import --from-registry"
mkdir -p "${WORK}/consumer" && cd "${WORK}/consumer"
"$AF" -q init >/dev/null
OUT="$("$AF" import --from-registry e2e-demo 2>&1)" || { echo "$OUT"; fail "import failed"; }
echo "$OUT" | grep -q "checksum auto-verified" || { echo "$OUT"; fail "checksum was not verified"; }
[ -f .ai/agents/e2e-demo/agent-manifest.json ] || fail "agent not installed"
"$AF" audit e2e-demo

step "Re-publishing the same version is refused (immutable versions)"
cd "${WORK}/publisher"
if "$AF" publish e2e-demo >/dev/null 2>&1; then fail "duplicate version was accepted"; fi
echo "409 as expected"

printf '\n\033[1;32mMVP walkthrough passed.\033[0m\n'
if [ "$KEEP" = 1 ]; then
  WEBAPP="$(cd "$(dirname "$0")/../.." && pwd)/agentfactory-webapp"
  echo "Browse it (webapp checkout next to this repo):"
  echo "  cd $WEBAPP"
  echo "  VITE_AGENTFACTORY_API_URL=http://localhost:${PORT} npm run dev -- --host"
  echo "  open http://localhost:5173/AgentFactory/registry"
  [ -n "$HOST_IP" ] && echo "  (WSL2: if localhost resets, use http://${HOST_IP}:${PORT} and http://${HOST_IP}:5173 instead)"
fi
