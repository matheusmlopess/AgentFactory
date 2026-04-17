# AgentFactory: HOWTO and Workflow Guide
<!-- version: 1.1.0 -->

This guide provides a detailed look at the core workflows of the AgentFactory, including both ASCII and Mermaid representations.

---

## 1. Deploy Workflow (Scaffolding)

Used to start a fresh agent from scratch.

### ASCII
\`\`\`text
[User] ── agentfactory-gen deploy <name> ──▶ [Librarian]
                                          │
    ┌─────────────────────────────────────┴─────────────────────────────────────┐
    │                                                                           │
    ▼                                                                           ▼
[Create Directories]                                                   [Init Manifest]
  - skills/                                                               - name, version
  - commands/                                                             - resources (empty)
  - docs/                                                                 - dependencies {}
  - scripts/                                                              - git_ref
  - orchestration/                                                        - description
  - .gitkeep (in each)
\`\`\`

### Mermaid
\`\`\`mermaid
graph TD
    A[User: deploy name] --> B[Librarian: init]
    B --> C[Create 5-Dir Structure]
    C --> D[Add .gitkeep to folders]
    D --> E[Write agent-manifest.json]
    E --> F[Output: Ready-to-code agent]
\`\`\`

---

## 2. Retrofit Workflow (Interop & Conversion)

Used to ingest existing projects from Claude, Gemini, or Codex.

### ASCII
\`\`\`text
[User] ── agentfactory-gen retrofit <path> ──▶ [Librarian]
                                            │
    ┌───────────────────────────────────────┴───────────────────────────────────────┐
    │                                                                               │
    ▼                                                                               ▼
[Analyze Structure]                                                        [Propose Mapping]
  - Check triggers (tools/, functions/, etc)                                 - Claude Profile
  - Identify source -> destination                                           - Gemini Profile
                                                                             - Codex Profile
                                                                                    │
                                                                                    ▼
    ┌────────────────── [Approval (Y/n)] ◀──────────────────────────────────────────┘
    │
    ▼
[Execute Migration] ──▶ [Sync & Audit] ──▶ [Manifest Created]
\`\`\`

### Mermaid
\`\`\`mermaid
graph TD
    A[User: retrofit path] --> B[Librarian: propose_retrofit]
    B --> C{Profile Detected?}
    C -->|CLAUDE| D[prompts -> skills, tools -> scripts]
    C -->|GEMINI| E[api_configs -> scripts]
    C -->|CODEX| F[functions -> skills]
    D & E & F --> G[User Approval]
    G -->|Yes| H[Librarian: migrate]
    H --> I[Librarian: sync]
    I --> J[Standardized Agent]
\`\`\`

---

## 3. Wrap Workflow (Bundling)

Used to package an agent into a Portable Unit.

### ASCII
\`\`\`text
[User] ── agentfactory-gen wrap <name> ──▶ [Librarian]
                                        │
    ┌───────────────────────────────────┴───────────────────────────────────┐
    │                                                                       │
    ▼                                                                       ▼
[Librarian.sync]                                                    [Librarian.audit]
  - Crawl resources                                                   - Validate all paths
  - Detect dependencies                                               - Verify dependencies
  - Set orchestration plan                                            - Check metadata
                                                                            │
    ┌────────────────── [Audit Result] ◀────────────────────────────────────┘
    │
    ▼
[✓ Success] ──▶ [Zip manifest + resources] ──▶ [name-v1.0.0.zip]
\`\`\`

### Mermaid
\`\`\`mermaid
graph TD
    A[User: wrap name] --> B[Librarian: sync]
    B --> C[Librarian: audit]
    C -->|Fail| D[Abort: List broken paths]
    C -->|Pass| E[Librarian: wrap]
    E --> F[Output: Portable Unit .zip]
\`\`\`

---

## 4. Import Workflow (The Handshake)

Used to bring a Portable Unit into a new project.

### ASCII
\`\`\`text
[User] ── agentfactory-gen import <zip> ──▶ [Librarian]
                                         │
    ┌────────────────────────────────────┴────────────────────────────────────┐
    │                                                                         │
    ▼                                                                         ▼
[Peek & Unpack]                                                       [Deep Audit]
  - Resolve agent name                                                  - Audit ZIP contents
  - Unpack to agents/<name>/                                            - Rollback if failed
                                                                              │
                                                                              ▼
[Harness Update] ◀── [The Handshake] ◀────────────────────────────────────────┘
  - Append to CLAUDE.md                               - Register in global manifest
  - Append to GEMINI.md                               - Add entry to registry
  - Create/Update AGENTS.md
\`\`\`

### Mermaid
\`\`\`mermaid
graph TD
    A[User: import zip] --> B[Peek Manifest]
    B --> C[Unpack to agents/name/]
    C --> D[Librarian: audit]
    D -->|Fail| E[Rollback: rm -rf directory]
    D -->|Pass| F[Librarian: register_in_project]
    F --> G[Librarian: update_harness_files]
    G --> H[Output: Import Complete Summary]
\`\`\`

---

## 5. Uninstall Workflow (Deregister & Remove)

Used to safely remove an agent.

### ASCII
\`\`\`text
[User] ── agentfactory-gen uninstall <name> ──▶ [Librarian]
                                             │
    ┌────────────────────────────────────────┴────────────────────────────────────────┐
    │                                                                                 │
    ▼                                                                                 ▼
[Deregister]                                                              [Update Harness]
  - Remove entry from global manifest                                       - Update CLAUDE.md
                                                                            - Update GEMINI.md
                                                                            - Update AGENTS.md
                                                                                    │
    ┌─────────────────────────────────── [Cleanup] ◀────────────────────────────────┘
    │
    ▼
[rm -rf agents/<name>] ──▶ [Uninstall Complete]
\`\`\`

### Mermaid
\`\`\`mermaid
graph TD
    A[User: uninstall name] --> B[Librarian: deregister_from_project]
    B --> C[Librarian: update_harness_files]
    C --> D[shutil.rmtree directory]
    D --> E[Uninstall Complete]
\`\`\`

---

## 6. Intelligent Detection (Intelligence Layer)

The background logic that makes metadata and dependency management automated.

### ASCII
\`\`\`text
[Sync Operation] ──▶ [Dependency Scanner]
                        - Scans for <!-- @depends-on: ... -->
                        - Scans Python for 'import utils' -> 'scripts/utils.py'
                                │
                                ▼
                    [Orchestration Picker]
                        - If no plan set, promotes first file in orchestration/
                                │
                                ▼
                    [Skill Manifest Parser]
                        - Injects metadata from 'skills/*/skill-manifest.json'
\`\`\`

### Mermaid
\`\`\`mermaid
graph TD
    A[Sync / Audit] --> B[Dependency Scanner]
    B --> C[Orchestration Picker]
    C --> D[Skill Manifest Parser]
    D --> E[Final Manifest Update]
\`\`\`

---

## 7. Webapp Completeness Viewer

### What it is

The **Skill Completeness** section of the webapp renders pre-generated semantic
reports from `.ai/reports/`. It shows, per skill, how many functional atoms
(commands, decision paths, error cases, etc.) were preserved after the last trim.
No Anthropic API key is needed to *view* results — reports are embedded at build time.

```
  .ai/reports/
    skill-diff-visualizer-completeness.json   ← generated by CLI
    skill-git-versioning-completeness.json

  webapp/scripts/copy-reports.mjs             ← copies reports before vite runs
  webapp/src/data/reports/                    ← embedded into the bundle
  webapp/src/components/CompletenessViewer.tsx← renders the UI
  webapp/src/types/completeness.ts            ← TypeScript types
```

The feature carries a `pro` badge — it is the free read-only tier of the BYOK live
checker planned for #105.

---

### Running locally

**Prerequisites:** Node 18+, npm.

```bash
cd webapp
npm install          # first time only
npm run dev          # starts Vite dev server
```

`npm run dev` runs `copy-reports.mjs` first, which copies any `.ai/reports/*.json`
into `src/data/reports/`, then starts the dev server. Open `http://localhost:5173`
and scroll to the **Skill Completeness** section.

```
  npm run dev
      │
      ▼
  node scripts/copy-reports.mjs
      │   reads:  .ai/reports/skill-*.json
      │   writes: webapp/src/data/reports/
      ▼
  vite (dev server on :5173)
      │
      └── CompletenessViewer reads src/data/reports/ via static import
```

---

### Refreshing reports after a skill trim

When a `SKILL.md` is edited, the cached report in `.ai/reports/` becomes stale.
Regenerate it, then restart the dev server:

**Step 1 — Re-run the completeness check** (requires `ANTHROPIC_API_KEY`):

```bash
# Claude adapter (default 90% threshold)
python3 .ai/scripts/skill-completeness-check.py --skill diff-visualizer --adapter claude

# Or with an explicit threshold override
python3 .ai/scripts/skill-completeness-check.py --skill git-versioning --threshold 95
```

This overwrites `.ai/reports/skill-<name>-completeness.json`.

**Step 2 — Refresh the webapp** (reports are re-copied automatically on restart):

```bash
# If the dev server is already running, stop it (Ctrl-C), then:
npm run dev

# Or just trigger the copy manually without restarting:
node scripts/copy-reports.mjs
# Then the browser hot-reloads the new JSON automatically.
```

```
  SKILL.md edited
      │
      ▼
  python3 .ai/scripts/skill-completeness-check.py --skill <name> --adapter <adapter>
      │
      ▼
  .ai/reports/skill-<name>-completeness.json  (overwritten)
      │
      ▼
  node scripts/copy-reports.mjs
      │
      ▼
  webapp/src/data/reports/  (updated)
      │
      ▼
  Browser refreshes → CompletenessViewer shows new score
```

---

### Adding a new skill's report

When a new skill is imported, no report exists yet. Run the check once to seed it:

```bash
# 1. Import the skill (creates .ai/skills/<name>/SKILL.md)
agentfactory-gen import-skill path/to/skill.zip

# 2. Generate the first report
python3 .ai/scripts/skill-completeness-check.py --skill <name> --adapter claude

# 3. Register it in the webapp component
#    Open: webapp/src/components/CompletenessViewer.tsx
#    Add:  import newReport from "../data/reports/skill-<name>-completeness.json";
#    Add:  "<name>": newReport as CompletenessReport  to the REPORTS object

# 4. Restart dev server
npm run dev
```

> **Note:** Step 3 (editing `REPORTS` in `CompletenessViewer.tsx`) will be automated
> in a future issue — the viewer will auto-discover all JSON files in `src/data/reports/`.

---

### Building for production

```bash
cd webapp
npm run build
```

This runs `copy-reports.mjs` → TypeScript check → Vite bundle. The reports are
**inlined into the bundle** — the static site on GitHub Pages requires no API
calls or server to display completeness results.

```bash
# Preview the production build locally
npm run preview          # serves dist/ on :4173
```

---

### What the viewer shows

| UI element | What it means |
|------------|---------------|
| Skill tabs | One tab per skill with a cached report. Click to switch. |
| Score badge | Percentage of atoms preserved. Green ≥ 95%, amber ≥ 90%, red < 90%. |
| Summary counts | Preserved / degraded / missing atoms at a glance. |
| Filter chips | Filter atom list by type: `command`, `decision path`, `error case`, `data table`, `external ref`, `constraint`. |
| Atom rows | `✓` preserved · `~` degraded · `✗` missing. Degraded/missing rows show the oracle's evidence note. |
| Re-run hint | Copy-pasteable CLI command to refresh the report for that skill. |

---

### Threshold config

Thresholds per adapter live in `.ai/config/completeness.json`:

```json
{
  "completeness": {
    "thresholds": {
      "claude":  90,
      "codex":   95,
      "gemini":  90
    },
    "default": 90
  }
}
```

Edit this file to tighten or loosen the gate for any adapter. The webapp viewer
itself is read-only — it always renders whatever score the last CLI run produced.

---

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| Viewer shows old score after editing SKILL.md | Re-run `skill-completeness-check.py`, then `node scripts/copy-reports.mjs` |
| `npm run dev` shows a stale score | Stop the server, re-run the check, restart |
| `Error: ANTHROPIC_API_KEY not set` | Set `export ANTHROPIC_API_KEY=sk-ant-...` before running the check script |
| New skill not appearing in tabs | Add it to the `REPORTS` object in `CompletenessViewer.tsx` |
| Score shows as `?` in harness-doctor | The report JSON is missing — run the completeness check for that skill |
