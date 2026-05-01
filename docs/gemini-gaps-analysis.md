# Gemini CLI Gap Analysis: AgentFactory.old

This document provides a deep dive into the architectural and configuration gaps between the current state of the `AgentFactory.old` repository and the requirements for a native, high-performance Gemini CLI experience.

## 1. Structure & Discovery Gaps

### Definition: Skill Discovery
Gemini CLI uses a **Convention-over-Configuration** approach for discovering agent capabilities. It scans specific directories at session startup to register "skills" (sets of instructions, scripts, and documentation).

### The Gap: Non-Standard Tooling Path
The project currently uses a directory named `.gemini/tools/`. Gemini CLI, however, exclusively looks for `.gemini/skills/` (local) or `~/.gemini/skills/` (global).

*   **Current State:** `.gemini/tools/diff-visualizer/`
*   **Expected State:** `.gemini/skills/diff-visualizer/`
*   **Example Failure Scenario:**
    User: "Run the diff visualizer."
    Gemini: "I don't have a tool or skill named 'diff-visualizer' registered."

### Box-Drawing: Skill Discovery Workflow
```text
┌──────────────────────────┐      ┌──────────────────────────┐
│ Gemini Starts Session    │─────▶│ Scans .gemini/skills/    │
└──────────────────────────┘      └──────────────────────────┘
             │                                 │
             ▼                                 ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│ FAIL: Finds 'tools/'     │      │ SUCCESS: Registers       │
│ Logic: Path Ignored      │      │ 'diff-visualizer'        │
└──────────────────────────┘      └──────────────────────────┘
```

---

## 2. Configuration & Metadata Gaps

### Definition: Settings vs. Config
Gemini CLI's primary configuration file is `settings.json`. It controls model selection, security (auth), and UI preferences. The project currently uses `config.json`, which is not a recognized filename for the CLI.

### The Gap: Property Mismatch
The `config.json` in the project contains a `tools_dir` property. Gemini CLI does not support a custom `tools_dir` via JSON; it relies on directory naming conventions or explicit `gemini skills link` commands.

*   **Current `config.json`:**
    ```json
    {
      "model": "gemini-2.0-flash",
      "tools_dir": "tools"
    }
    ```
*   **Gemini Standard `settings.json`:**
    ```json
    {
      "model": "gemini-2.0-flash",
      "context": { "fileName": ["GEMINI.md"] }
    }
    ```

---

## 3. Command & Interactivity Gaps

### Definition: Slash Commands
Slash commands are lightweight, pre-defined executable scripts or instruction sets that can be triggered via a `/` prefix (e.g., `/test`). They are defined as `.toml` files in `.gemini/commands/`.

### The Gap: Instructional Commands vs. Executable Commands
`GEMINI.md` lists `/completeness-check` and `/git-workflow`. However, these are merely **textual descriptions** within a Markdown file. They are not registered with the CLI's command runner.

*   **Example Execution Gap:**
    User types: `/completeness-check`
    Gemini Result: "Unknown command. Did you mean /help?"

### Box-Drawing: Command Execution Scenario
```text
┌───────────────────────┐      ┌──────────────────────────┐      ┌───────────────────────┐
│ User: /git-workflow   │─────▶│ Gemini CLI checks        │─────▶│ Shell: git checkout   │
└───────────────────────┘      │ .gemini/commands/*.toml  │      │ feature/branch...     │
                               └──────────────────────────┘      └───────────────────────┘
                                            │
                                            ▼
                               ┌──────────────────────────┐
                               │ FAIL: No .toml found     │
                               │ Result: "Unknown Cmd"    │
                               └──────────────────────────┘
```

---

## 4. MCP (Model Context Protocol) Gaps

### Definition: MCP Servers
MCP allows the CLI to connect to external data sources (like GitHub, Google Drive, or local DBs). These are configured in the `mcpServers` block of `settings.json`.

### The Gap: Disconnected Configuration
The repo has a `.mcp.json` file. Gemini CLI will never read this file. Any automation or data-fetching logic reliant on these servers will be unavailable during the session.

---

## 5. Issue Matrix & Deep Find Gaps

### Deep Find: The "Doctor" Conflict
The script `.ai/scripts/harness-doctor.sh` explicitly checks for `adapters/gemini/tools`.
```bash
"${AI_ROOT}/adapters/gemini/tools"
```
If we move the folder to `skills/` to satisfy Gemini CLI, the `harness-doctor.sh` script (the project's own health check) will fail. This creates a circular dependency error.

### Issue Matrix (Comprehensive)

| ID | Topic | Gap | Definition | Severity |
|:---|:---|:---|:---|:---|
| G-01 | **Structure** | Skill Dir Path | Gemini only looks for `skills/`, not `tools/`. | **Critical** |
| G-02 | **Config** | Filename | `config.json` is ignored; `settings.json` is required. | **Major** |
| G-03 | **Config** | Unsupported Prop | `tools_dir` property is not a valid Gemini setting. | **Major** |
| G-04 | **Commands** | Missing .toml | Commands in `GEMINI.md` are not executable. | **Major** |
| G-05 | **MCP** | Registry Path | `.mcp.json` is not a standard Gemini registry. | **Minor** |
| G-06 | **Logic** | Harness Health | Project health check expects the wrong path. | **Major** |
| G-07 | **Context** | Token Budget | `GEMINI.md` is too large (approaching 6k bytes). | **Warning** |

---

## Summary Recommendations
To achieve a "Native" experience, the project must move from **Instructional Context** (Markdown descriptions) to **Functional Configuration** (JSON settings, TOML commands, and standard Directory structures).
