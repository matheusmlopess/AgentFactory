# Registry CLI — publish & import --from-registry
<!-- version: 1.0.0 -->

Issue: #82 · Phase 1 Foundation of the AgentFactory production platform (#77)

Two CLI commands that connect `agentfactory-gen` to the public agent registry: `publish` uploads a wrapped agent, and `import --from-registry` downloads and installs one.

---

## 1. Overview

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  PURPOSE                                                               │
  │                                                                        │
  │  Agents wrapped as Portable Units (.zip) can now be shared via the   │
  │  public registry at agentfactory.dev without manual file transfer.   │
  │                                                                        │
  │  What it unlocks:                                                      │
  │    · agentfactory-gen login / logout CLI auth    (#86)                │
  │    · private org workspaces + RBAC               (#84)                │
  │    · marketplace — paid agent listings           (#90)                │
  └──────────────────────────────────────────────────────────────────────┘
```

The registry CLI sits on top of the existing wrap/import pipeline. `publish` reads from a ZIP that `wrap` already created; `import --from-registry` downloads a ZIP and feeds it into the same `unpack → audit → register` path that `import <zip>` already uses. No new librarian logic was introduced — only the HTTP transport layer is new.

Dependency chain:
```
  #81 registry backend (done)
       │
       ▼
  #82 CLI publish + import --from-registry  ← this feature
       │
       ├──► #86 agentfactory-gen login / logout
       └──► #84 private workspaces (--private flag, Phase 2)
```

---

## 2. Architecture

### 2.1 File layout

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  FILE LAYOUT                                                           │
  └──────────────────────────────────────────────────────────────────────┘

  src/agent_gen/cli.py
    ├── REGISTRY_URL                      ← base URL constant (env-overridable)
    ├── _registry_publish(manifest, zip)  ← POST multipart to /registry/publish
    ├── _registry_fetch(slug)             ← GET entry + download ZIP bytes
    ├── _attach_auth_header(req)          ← reads ~/.agentfactory/token if present
    ├── publish  command                  ← new CLI command
    └── import   command                  ← extended with --from-registry

  ~/.agentfactory/token                   ← auth token (written by login, Phase 2)
```

### 2.2 Command structure

```
  agentfactory-gen
   │
   ├── publish <name>
   │     ├── --version OVERRIDE    override the version from manifest
   │     └── --tag TAG             discovery tag (repeatable)
   │
   └── import [ZIP_PATH]
         ├── --from-git URL        clone + retrofit + import
         └── --from-registry SLUG  download from registry + import  ← new
               supports: my-agent
                         my-agent@1.2.0   (pinned version)
```

### 2.3 HTTP layer

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  HTTP LAYER                                                            │
  └──────────────────────────────────────────────────────────────────────┘

  _registry_publish()
    POST {REGISTRY_URL}/registry/publish
    Content-Type: multipart/form-data; boundary=AgentFactoryBoundary
    Authorization: Bearer <token>  (if ~/.agentfactory/token exists)

    Body parts:
      ├── name="manifest"   Content-Type: application/json
      │     { "name": "...", "version": "...", "description": "...", "tags": [...] }
      └── name="file"       Content-Type: application/zip
            filename=<name>-v<version>.zip

  _registry_fetch()
    GET {REGISTRY_URL}/registry/<name>[/<version>]
    Authorization: Bearer <token>  (if present)
    → 200: { "name": "...", "version": "...", "zip_url": "https://..." }
    → 404: ClickException "Agent '<slug>' not found"

    Then: GET <zip_url> (no auth — presigned URL or CDN)
    → bytes written to NamedTemporaryFile, fed into existing import pipeline
```

---

## 3. Configuration

### 3.1 Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENTFACTORY_REGISTRY_URL` | No | `https://agentfactory.dev` | Override for self-hosted registry |

### 3.2 Auth token

```
  ~/.agentfactory/token       ← plain text, single line: the JWT or API key
                                 written by: agentfactory-gen login  (Phase 2, #86)
                                 read by:    _attach_auth_header()
                                 absent:     commands work for public registry
                                             (unauthenticated reads / writes rejected by server)
```

---

## 4. How It Works

### 4.1 Publish flow

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  PUBLISH FLOW                                                          │
  └──────────────────────────────────────────────────────────────────────┘

  agentfactory-gen publish my-agent [--version X] [--tag T]
       │
       ▼
  Load  .ai/agents/my-agent/agent-manifest.json
       │
       ├── description == "" ?
       │     YES → ClickException "description required"  ✗ STOP
       │     NO  → continue
       │
       ▼
  version = --version override  OR  manifest["version"]
  zip_name = my-agent-v{version}.zip
       │
       ├── ./{zip_name} exists?
       │     NO  → ClickException "run wrap first"  ✗ STOP
       │     YES → continue
       │
       ▼
  Build publish manifest:
    { name, version, description, tags: [...] }
       │
       ▼
  _attach_auth_header()  →  add Bearer token if ~/.agentfactory/token present
       │
       ▼
  POST {REGISTRY_URL}/registry/publish
    multipart: manifest JSON  +  ZIP binary
       │
       ├── HTTPError  → ClickException "Registry error <code>: <detail>"
       ├── URLError   → ClickException "Registry unreachable: <reason>"
       └── 200 OK     → continue
       │
       ▼
  echo "Published: {REGISTRY_URL}/registry/my-agent@{version}"  ✓ DONE
```

### 4.2 Import --from-registry flow

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  IMPORT --FROM-REGISTRY FLOW                                           │
  └──────────────────────────────────────────────────────────────────────┘

  agentfactory-gen import --from-registry my-agent[@version]
       │
       ▼
  Validate mutual exclusion
  (ZIP_PATH / --from-git / --from-registry are exclusive)
       │
       ▼
  echo "Fetching 'my-agent' from registry..."
       │
       ▼
  _registry_fetch("my-agent[@version]")
    ├── parse slug: name="my-agent", version=None or "1.2.0"
    ├── GET {REGISTRY_URL}/registry/my-agent[/1.2.0]
    │     ├── 404 → ClickException "not found"  ✗ STOP
    │     └── 200 → entry = { name, version, zip_url }
    └── GET entry["zip_url"]  →  zip_bytes
       │
       ▼
  Write zip_bytes → NamedTemporaryFile (suffix=".zip", delete=False)
  _cleanup = lambda: os.unlink(tmp.name)
       │
       ▼
  ─ ─ ─ ─ ─ ─  Existing import pipeline  ─ ─ ─ ─ ─ ─
       │
       ▼
  Peek archive → read agent-manifest.json → name
       │
       ├── .ai/agents/{name}/ exists?
       │     YES → sys.exit(1) "already exists"  ✗ STOP
       │     NO  → continue
       │
       ▼
  Librarian.unpack(zip_path, temp_dir/{name})
       │
       ▼
  librarian.audit()
       │
       ├── broken_resources / broken_dependencies / invalid_skill_manifests?
       │     YES → sys.exit(1) "Audit FAILED"  ✗ STOP
       │     NO  → continue
       │
       ▼
  shutil.move(temp_dir/{name} → .ai/agents/{name})
       │
       ▼
  Librarian.register_in_project(manifest, project_root)
       │
       ▼
  _cleanup()  →  delete NamedTemporaryFile
       │
       ▼
  Print summary: N skills, N commands, ...  ✓ DONE
```

### 4.3 Auth token attachment

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  AUTH FLOW                                                             │
  └──────────────────────────────────────────────────────────────────────┘

  _attach_auth_header(req)
       │
       ├── ~/.agentfactory/token  exists?
       │     NO  → do nothing (unauthenticated request)
       │     YES → req.add_header("Authorization", "Bearer <token>")
       │
       ▼
  Caller proceeds with urllib.request.urlopen(req)
```

---

## 5. Usage Examples

### 5.1 Full publish lifecycle (from scratch)

```bash
# 1. Create and describe the agent
agentfactory-gen deploy my-agent
agentfactory-gen describe my-agent --desc "A natural language search agent"

# 2. Add content to skills/, scripts/ etc., then wrap
agentfactory-gen wrap my-agent

# 3. Publish to the registry
agentfactory-gen publish my-agent
# Published: https://agentfactory.dev/registry/my-agent@1.0.0
```

### 5.2 Publish with version override and tags

```bash
agentfactory-gen publish my-agent --version 1.2.0 --tag nlp --tag retrieval
# Looks for: my-agent-v1.2.0.zip in cwd
# Published: https://agentfactory.dev/registry/my-agent@1.2.0
```

### 5.3 Import latest version of an agent

```bash
agentfactory-gen import --from-registry my-agent
# Fetches latest, installs to .ai/agents/my-agent/
```

### 5.4 Import a pinned version

```bash
agentfactory-gen import --from-registry my-agent@1.2.0
# Fetches exactly v1.2.0
```

### 5.5 Quiet mode (CI / scripts)

```bash
agentfactory-gen --quiet publish my-agent
agentfactory-gen --quiet import --from-registry my-agent
```

### 5.6 Self-hosted registry

```bash
export AGENTFACTORY_REGISTRY_URL=https://registry.internal.example.com
agentfactory-gen publish my-agent
agentfactory-gen import --from-registry my-agent
```

### 5.7 Combine --project-root with --from-registry

```bash
agentfactory-gen import --from-registry my-agent --project-root /path/to/project
```

---

## 6. All Scenarios

### Scenario 1 — Happy path: first publish

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SCENARIO 1: FIRST PUBLISH                                             │
  │  Pre-condition: agent deployed, described, wrapped                     │
  └──────────────────────────────────────────────────────────────────────┘

  Developer                    CLI                        Registry
      │                          │                            │
      │── publish my-agent ─────►│                            │
      │                          │── load manifest            │
      │                          │── check description ✓      │
      │                          │── find my-agent-v1.0.0.zip │
      │                          │── POST /registry/publish ─►│
      │                          │                            │── store ZIP
      │                          │◄── 200 OK ─────────────────│
      │◄── Published: .../my-agent@1.0.0 ────────────────────│
```

### Scenario 2 — Republish with new version

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SCENARIO 2: REPUBLISH WITH NEW VERSION                                │
  │  Pre-condition: agent already published at v1.0.0                     │
  └──────────────────────────────────────────────────────────────────────┘

  Developer                    CLI                        Registry
      │                          │                            │
      │  (edit agent files)      │                            │
      │── wrap my-agent ────────►│── creates my-agent-v1.1.0.zip          │
      │                          │                            │
      │── publish my-agent ─────►│                            │
      │    --version 1.1.0       │── finds my-agent-v1.1.0.zip            │
      │                          │── POST /registry/publish ─►│
      │◄── Published: .../my-agent@1.1.0 ─────────────────────│

  Note: --version must match the ZIP name on disk.
  If wrapping to a non-default version, use:
    agentfactory-gen wrap my-agent  (updates manifest version first)
```

### Scenario 3 — Import latest version

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SCENARIO 3: IMPORT LATEST                                             │
  │  Pre-condition: agent not yet in .ai/agents/                          │
  └──────────────────────────────────────────────────────────────────────┘

  Developer                    CLI                        Registry
      │                          │                            │
      │── import                 │                            │
      │    --from-registry ─────►│                            │
      │    my-agent              │── GET /registry/my-agent ─►│
      │                          │◄── { zip_url: "..." } ─────│
      │                          │── GET <zip_url> ───────────►CDN
      │                          │◄── ZIP bytes ──────────────│
      │                          │── write temp file          │
      │                          │── unpack → audit → register│
      │◄── Import Complete ───────│                            │
      │    .ai/agents/my-agent/  │                            │
```

### Scenario 4 — Import pinned version

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SCENARIO 4: IMPORT PINNED VERSION                                     │
  │  Slug format: <name>@<version>                                         │
  └──────────────────────────────────────────────────────────────────────┘

  Developer                    CLI                        Registry
      │                          │                            │
      │── import                 │                            │
      │    --from-registry ─────►│                            │
      │    my-agent@1.2.0        │── parse: name="my-agent"  │
      │                          │          version="1.2.0"  │
      │                          │── GET /registry/my-agent/1.2.0 ───────►│
      │                          │◄── { version:"1.2.0", zip_url } ───────│
      │                          │── download + install v1.2.0            │
      │◄── Imported my-agent v1.2.0 ──────────────────────────│
```

### Scenario 5 — Error: not wrapped yet

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SCENARIO 5: PUBLISH BEFORE WRAP                                       │
  │  Pre-condition: agent deployed but wrap never run                      │
  └──────────────────────────────────────────────────────────────────────┘

  Developer                    CLI
      │                          │
      │── publish my-agent ─────►│── load manifest ✓
      │                          │── check description ✓
      │                          │── find my-agent-v1.0.0.zip
      │                          │     NOT FOUND  ✗
      │◄── Error ─────────────────│
      │  "No wrapped archive found: my-agent-v1.0.0.zip
      │   Run 'agentfactory-gen wrap my-agent' first."

  Fix: agentfactory-gen wrap my-agent
```

### Scenario 6 — Error: missing description

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SCENARIO 6: MISSING DESCRIPTION                                       │
  │  Pre-condition: manifest description is empty string                   │
  └──────────────────────────────────────────────────────────────────────┘

  Developer                    CLI
      │                          │
      │── publish my-agent ─────►│── load manifest ✓
      │                          │── check description
      │                          │     description == ""  ✗
      │◄── Error ─────────────────│
      │  "Manifest 'description' is required for publishing.
      │   Run 'agentfactory-gen describe my-agent --desc \"...\"' first."

  Note: No HTTP call is made. Validation is fully local.
  Fix:  agentfactory-gen describe my-agent --desc "What this agent does"
```

### Scenario 7 — Error: agent already imported

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SCENARIO 7: AGENT ALREADY EXISTS                                      │
  │  Pre-condition: .ai/agents/my-agent/ already present                  │
  └──────────────────────────────────────────────────────────────────────┘

  Developer                    CLI                        Registry
      │                          │                            │
      │── import                 │                            │
      │    --from-registry ─────►│── GET /registry/my-agent ─►│
      │    my-agent              │◄── 200 + zip_url ──────────│
      │                          │── download ZIP             │
      │                          │── peek manifest → name="my-agent"
      │                          │── check .ai/agents/my-agent/
      │                          │     EXISTS  ✗
      │◄── Error (stderr) ────────│
      │  "'my-agent' already exists at .ai/agents/my-agent.
      │   Remove it first or rename the incoming bundle."

  Fix: agentfactory-gen uninstall my-agent
       agentfactory-gen import --from-registry my-agent
```

### Scenario 8 — Error: network failure or 404

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SCENARIO 8: NETWORK FAILURE / NOT FOUND                               │
  └──────────────────────────────────────────────────────────────────────┘

  8a. Slug not found (404)
  ─────────────────────────────────────────────────────────────────────
  Developer                    CLI                        Registry
      │                          │                            │
      │── import                 │                            │
      │    --from-registry ─────►│── GET /registry/typo-name ►│
      │    typo-name             │                            │── 404
      │                          │◄── HTTPError 404 ───────────│
      │◄── Error: "Agent 'typo-name' not found in registry."  │

  8b. Registry unreachable
  ─────────────────────────────────────────────────────────────────────
  Developer                    CLI
      │                          │
      │── publish my-agent ─────►│── POST /registry/publish
      │                          │     URLError (connection refused / timeout)
      │◄── Error: "Registry unreachable: <reason>"

  8c. Auth error (401)
  ─────────────────────────────────────────────────────────────────────
  Developer                    CLI                        Registry
      │                          │                            │
      │── publish my-agent ─────►│── POST /registry/publish ─►│
      │                          │                            │── 401
      │◄── Error: "Registry error 401: Unauthorized"
      │
      Cause: token missing, expired, or revoked
      Fix:   agentfactory-gen login   (Phase 2, #86)
```

---

## 7. Integration Points

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  INTEGRATION MAP                                                       │
  └──────────────────────────────────────────────────────────────────────┘

  Called by:
    Developer CLI         ──►  publish, import --from-registry
    CI/CD publish job     ──►  agentfactory-gen --quiet publish <name>

  Calls:
    publish  ──►  Librarian._load_manifest()          (agent manifest read)
             ──►  _registry_publish()                  (HTTP POST)
             ──►  _attach_auth_header()                (token injection)

    import   ──►  _registry_fetch()                    (HTTP GET + download)
             ──►  _attach_auth_header()                (token injection)
             ──►  Librarian.unpack()                   (ZIP extraction)
             ──►  librarian.audit()                    (integrity check)
             ──►  Librarian.register_in_project()      (manifest update)

  Unlocks (future phases):
    publish --private  ──►  #84 private org workspaces
    agentfactory-gen login  ──►  #86 writes ~/.agentfactory/token
    marketplace listings    ──►  #90 paid agent listings
```

---

## 8. Troubleshooting

```
  ┌──────────────────────────────────────────┬───────────────────────────────────────┐
  │  Symptom                                  │  Fix                                   │
  ├──────────────────────────────────────────┼───────────────────────────────────────┤
  │  "No wrapped archive found: name-v*.zip" │  agentfactory-gen wrap <name>          │
  ├──────────────────────────────────────────┼───────────────────────────────────────┤
  │  "Manifest 'description' is required"    │  agentfactory-gen describe <name>      │
  │                                           │    --desc "What this agent does"       │
  ├──────────────────────────────────────────┼───────────────────────────────────────┤
  │  "Registry unreachable"                  │  Check network connection              │
  │                                           │  Verify AGENTFACTORY_REGISTRY_URL      │
  ├──────────────────────────────────────────┼───────────────────────────────────────┤
  │  "Registry error 401: Unauthorized"      │  agentfactory-gen login   (#86)        │
  │                                           │  Or set ~/.agentfactory/token manually │
  ├──────────────────────────────────────────┼───────────────────────────────────────┤
  │  "Registry error 404" on publish         │  Registry endpoint config mismatch;   │
  │                                           │  check AGENTFACTORY_REGISTRY_URL       │
  ├──────────────────────────────────────────┼───────────────────────────────────────┤
  │  "Agent '<name>' not found in registry"  │  Check slug spelling; browse           │
  │                                           │  agentfactory.dev/registry             │
  ├──────────────────────────────────────────┼───────────────────────────────────────┤
  │  "'<name>' already exists" on import     │  agentfactory-gen uninstall <name>     │
  │                                           │  Then re-run import --from-registry    │
  ├──────────────────────────────────────────┼───────────────────────────────────────┤
  │  ZIP downloaded but audit fails          │  Agent bundle is corrupt or missing    │
  │                                           │  required files; contact publisher     │
  └──────────────────────────────────────────┴───────────────────────────────────────┘
```
