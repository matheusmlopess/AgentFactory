# AgentFactory: HOWTO and Workflow Guide

This guide provides a detailed look at the core workflows of the AgentFactory, including both ASCII and Mermaid representations.

---

## 1. Deploy Workflow (Scaffolding)

Used to start a fresh agent from scratch.

### ASCII
\`\`\`text
[User] ── agent-gen deploy <name> ──▶ [Librarian]
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
[User] ── agent-gen retrofit <path> ──▶ [Librarian]
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
[User] ── agent-gen wrap <name> ──▶ [Librarian]
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
[User] ── agent-gen import <zip> ──▶ [Librarian]
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
[User] ── agent-gen uninstall <name> ──▶ [Librarian]
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
