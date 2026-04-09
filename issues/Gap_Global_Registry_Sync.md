# Issue: Sync Global Registry on Local Agent Updates

## Description
When an agent is imported, it is registered in the project's global `agent-manifest.json` and injected into `AGENTS.md`. 

## Gap Analysis
If a user subsequently updates the agent's local metadata (e.g., via `agent-gen describe <name> --desc "New description"`), the *global* registry and harness files (`AGENTS.md`, `GEMINI.md`) become out of sync. The only way to update them currently is to re-wrap and re-import the agent.

## Proposed Solution
- When an agent's local manifest is updated via `describe` or `sync`, trigger a check.
- If the agent is currently registered in the project's global manifest, automatically update its entry and run `Librarian.update_harness_files()`.

## Acceptance Criteria
- [ ] `agent-gen describe` updates the global project registry if the agent is installed.
- [ ] `agent-gen sync/wrap` updates the global project registry if metadata drifts.
- [ ] Harness files reflect changes immediately without requiring re-import.