# Multi-Repo Development Workflow
<!-- version: 1.0.0 -->

Issue: #114 context · Architecture decision after webapp separation (2026-04-21)

Reference document for developing AgentFactory across two repositories.
Read alongside `docs/FEATURE-AUTH.md` and `docs/FEATURE-WORKFLOW.md`.

---

## 1. Repository Map

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  TWO-REPO ARCHITECTURE                                                 │
  └──────────────────────────────────────────────────────────────────────┘

  github.com/matheusmlopess/AgentFactory          ← PUBLIC  (this repo)
  ┌─────────────────────────────────────────────────────────────────────┐
  │  src/agent_gen/         ← CLI commands (agentfactory-gen)            │
  │  src/agent_gen/api/     ← FastAPI backend (auth, registry, billing)  │
  │  src/tests/             ← pytest suite (CLI + API)                   │
  │  .ai/                   ← AgentFactory harness (skills, briefs)      │
  │  docs/                  ← Architecture specs, feature docs, workflow  │
  │  api/openapi.yaml        ← API contract (source of truth for webapp) │
  │  docker-compose.yml      ← Full-stack local dev (api + db)           │
  └─────────────────────────────────────────────────────────────────────┘

  github.com/matheusmlopess/agentfactory-webapp   ← PRIVATE
  ┌─────────────────────────────────────────────────────────────────────┐
  │  src/                   ← React + TypeScript webapp                  │
  │  src/lib/api-types.ts   ← Generated from api/openapi.yaml (CLI repo) │
  │  src/lib/apiClient.ts   ← Typed fetch wrapper                       │
  │  .ai/                   ← AgentFactory harness (webapp dev context)  │
  │  docs/                  ← Webapp-specific feature docs               │
  └─────────────────────────────────────────────────────────────────────┘
```

### The seam: the REST API

```
  ┌────────────────────┐   HTTP / REST   ┌──────────────────────────────┐
  │  agentfactory-api  │◄───────────────►│  webapp (React)               │
  │  (FastAPI)         │                 │                               │
  │  localhost:8000    │                 │  localhost:5173               │
  │  api.agentfactory.dev (prod)         │  pages.github.io (pages)     │
  └────────────────────┘                 └──────────────────────────────┘
```

The API contract lives in `api/openapi.yaml` in this repo. The webapp generates
TypeScript types from it. Neither side hard-codes request/response shapes by hand.

---

## 2. Development Modes

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  MODE                  COMMAND                    USE WHEN            │
  ├─────────────────────────────────────────────────────────────────────┤
  │  Frontend-only         npm run dev                No backend needed   │
  │  (demo / mock)         (VITE_AUTH_API_URL unset)  UI work, components │
  │                                                                       │
  │  Full-stack local      docker compose up          Auth + API work     │
  │                        VITE_AUTH_API_URL=          integration testing │
  │                          http://localhost:8000                        │
  │                                                                       │
  │  Production            Deploy via CI               Merges to main     │
  │                        api.agentfactory.dev                           │
  └─────────────────────────────────────────────────────────────────────┘
```

Frontend-only mode is the default. The webapp runs against mock data and never
makes a network request unless `VITE_AUTH_API_URL` is set. This means pure UI
work never requires the CLI repo to be running.

---

## 3. Day-to-Day Workflow

### Pure webapp work (UI, components, styles)

```
  cd ~/repo/agentfactory-webapp
  git checkout -b feature/<issue>-<slug>
  npm run dev                       ← demo mode, no backend

  # work, commit, PR → merge to main
  # webapp deploys to GitHub Pages automatically
```

### Pure CLI/backend work (harness commands, API routes)

```
  cd ~/repo/AgentFactory.old
  git checkout -b feature/<issue>-<slug>

  # harness commands:
  agentfactory-gen <command>

  # API backend:
  pip install -e ".[dev,api]"
  uvicorn agent_gen.api.main:app --reload --port 8000

  # test:
  python3 -m pytest src/tests/
```

### Cross-cutting feature (e.g. a new API endpoint consumed by the webapp)

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  CROSS-CUTTING FEATURE PROTOCOL                                       │
  │                                                                       │
  │  1. Open issue in CLI repo for the backend endpoint                  │
  │  2. Open linked issue in webapp repo for the frontend                │
  │     body: "Depends on: CLI#<n>"                                      │
  │                                                                       │
  │  3. CLI repo: update api/openapi.yaml with the new endpoint schema   │
  │  4. CLI repo: implement FastAPI route + tests                        │
  │  5. CLI repo: merge + regenerate types:                              │
  │       cd ~/repo/agentfactory-webapp                                  │
  │       npx openapi-ts --input http://localhost:8000/openapi.json      │
  │                      --output src/lib/api-types.ts                   │
  │  6. Webapp repo: implement UI against generated types                │
  │  7. Webapp repo: merge                                               │
  │                                                                       │
  │  Rule: backend merges first, types regenerate, frontend follows.     │
  │  Never code against hand-written types.                              │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Issue Tracking Convention

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  ISSUE → REPO ASSIGNMENT                                              │
  │                                                                       │
  │  CLI repo (public)                                                    │
  │  ─────────────────                                                    │
  │  · agentfactory-gen command changes                                  │
  │  · FastAPI backend routes, auth, billing, RBAC                       │
  │  · Platform epic coordination (#77 and descendants)                  │
  │  · CLI-side of cross-cutting features (backend half)                 │
  │                                                                       │
  │  Webapp repo (private)                                                │
  │  ─────────────────────                                                │
  │  · React components, routing, state management                       │
  │  · Webapp-only features (converter, BYOK checker, UI views)          │
  │  · Webapp CI, build tooling, Vitest setup                            │
  │  · Webapp-side of cross-cutting features (frontend half)             │
  └─────────────────────────────────────────────────────────────────────┘
```

Cross-cutting feature issues reference each other:

```
  CLI repo #125:  feat: POST /api/completeness endpoint
  Webapp repo #7: feat: BYOK live checker UI
                  body: "Depends on: CLI#125"
```

---

## 5. Generating TypeScript Types from OpenAPI

After any backend change, regenerate the webapp's type bindings:

```bash
# From the webapp repo root:
npx openapi-ts \
  --input https://raw.githubusercontent.com/matheusmlopess/AgentFactory/dev/api/openapi.yaml \
  --output src/lib/api-types.ts \
  --client fetch

# Or against a running local backend:
npx openapi-ts \
  --input http://localhost:8000/openapi.json \
  --output src/lib/api-types.ts \
  --client fetch
```

Commit `src/lib/api-types.ts`. Never edit it by hand — it is a generated file.

---

## 6. Full-Stack Local Dev

```bash
# Clone both repos side by side (once):
cd ~/repo
git clone https://github.com/matheusmlopess/AgentFactory.git agentfactory-cli
git clone https://github.com/matheusmlopess/agentfactory-webapp.git agentfactory-webapp

# Start the full stack (from CLI repo):
cd ~/repo/agentfactory-cli
cp .env.example .env               # fill in GITHUB_CLIENT_ID / SECRET / JWT_SECRET
docker compose up                  # starts api (port 8000) + db (port 5432)

# Start the webapp (from webapp repo):
cd ~/repo/agentfactory-webapp
VITE_AUTH_API_URL=http://localhost:8000 npm run dev
```

The `docker-compose.yml` in this repo starts:

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  DOCKER COMPOSE SERVICES                                               │
  │                                                                        │
  │  api   ── FastAPI (uvicorn, hot-reload in dev)  port 8000             │
  │  db    ── PostgreSQL 16                          port 5432             │
  │                                                                        │
  │  webapp is NOT in this compose — it runs independently in the         │
  │  private repo. Point VITE_AUTH_API_URL at the api service.            │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 7. Release Coordination

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  RELEASE FLOW                                                         │
  │                                                                       │
  │  CLI / backend                  Webapp                                │
  │  ──────────────────             ──────────────────                    │
  │  git tag v3.0.0                 merge to main                        │
  │  → PyPI release (agentfactory-gen)   → GitHub Pages deploy           │
  │  → Docker image pushed               (or VPS deploy hook)            │
  │                                                                       │
  │  No hard version coupling between repos. The API contract             │
  │  (openapi.yaml) is the compatibility boundary.                        │
  │                                                                       │
  │  Breaking API change → bump major version in openapi.yaml +          │
  │  regenerate webapp types before deploying backend.                   │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Environment Variables Reference

### CLI repo / backend

| Variable | Required | Description |
|---|---|---|
| `GITHUB_CLIENT_ID` | Yes (live) | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | Yes (live) | GitHub OAuth app client secret |
| `JWT_SECRET` | Yes (live) | HS256 signing secret (32+ chars) |
| `DATABASE_URL` | No | SQLite `sqlite:///./agentfactory.db` (default) or `postgresql://...` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `http://localhost:5173`) |
| `AGENTFACTORY_LICENSE_KEY` | No | CLI paid-feature license key |

### Webapp repo

| Variable | Required | Description |
|---|---|---|
| `VITE_AUTH_API_URL` | No | Points to backend. Unset = demo mode |

---

## 9. Current Wave Map

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  WAVE 1 — Start now                                                   │
  ├─────────────────────────────────────────────────────────────────────┤
  │  #114  FastAPI auth backend          CLI repo   ← in progress        │
  │  WA#1  Webapp architecture upgrade   Webapp     ← independent        │
  │  WA#2  Agent converter (Phase A)     Webapp     ← independent        │
  │                                                                       │
  │  WAVE 2 — After Wave 1                                                │
  ├─────────────────────────────────────────────────────────────────────┤
  │  #82   CLI publish + import-registry  CLI repo                       │
  │  #84   RBAC workspaces               CLI repo                        │
  │  #86   agentfactory-gen login/logout  CLI repo                       │
  │  #91   Verified agent badge           CLI repo                       │
  │                                                                       │
  │  WAVE 3 — After Wave 2                                                │
  ├─────────────────────────────────────────────────────────────────────┤
  │  #85   Pro billing (Stripe)           CLI repo                       │
  │  #87   Audit history dashboard        CLI + Webapp                   │
  │                                                                       │
  │  WAVE 4+                                                              │
  ├─────────────────────────────────────────────────────────────────────┤
  │  #88  Dependency graph viz            CLI + Webapp                   │
  │  #89  Enterprise compliance export    CLI + Webapp                   │
  │  #90  Marketplace                     CLI + Webapp                   │
  │  WA#4 BYOK live checker              Webapp (after #85)             │
  └─────────────────────────────────────────────────────────────────────┘
```

---

_See also: `docs/FEATURE-AUTH.md` (OAuth contract) · `docs/FEATURE-WORKFLOW.md` (8-step lifecycle)_
