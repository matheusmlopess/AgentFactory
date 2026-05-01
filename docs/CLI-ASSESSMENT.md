<!-- version: 1.0.0 -->
# agentfactory-gen CLI Assessment — v1.0.0 <!-- version: 1.0.0 -->

> Based on live execution of the full `deploy → describe → audit → wrap → import → import-skill → brief` lifecycle during the `security-review` agent transfer from AgentFactory.old to agentfactory-harness on 2026-04-28.

---

## 1. What Works Well

The CLI handles the happy-path lifecycle correctly and with clean output.

| Observation | Detail |
|-------------|--------|
| `deploy` is fast and clean | Scaffolds 5-directory standard in under 1s with a readable summary |
| `describe` is idempotent | Re-running with the same `--desc` does not error |
| `wrap` auto-syncs before packaging | Calling `wrap` without `sync` first still works — it runs sync internally |
| ZIP structure is correct | `references/` subdirectories are preserved; all 6 files included |
| `import` runs audit before registration | Agent is validated before being added to the project — good security posture |
| `import-skill` correctly promotes to `root project` | With no `--to` flag, it places the skill in `.ai/skills/` as intended |
| `brief` recompiles all active adapters in one call | Claude, Codex, and Gemini briefs updated atomically |
| Error messages are actionable | `audit` says "Run 'wrap' or 'sync' to add them" — exactly right |
| Global manifest locking | Concurrent operations are filelock-protected — no race corruption |

---

## 2. Command-by-Command Table

| Command | Status | Observed Behaviour |
|---------|--------|--------------------|
| `deploy` | ✅ | Clean scaffold, manifest created, registered globally |
| `describe` | ✅ | Updates description in manifest correctly |
| `audit` | ✅⚠ | Correctly detects untracked files; exits 1 as expected; but requires manual `sync` first |
| `wrap` | ✅ | Auto-syncs, audits, packages; ZIP structure correct |
| `import` | ✅⚠ | Works cleanly from target CWD; `--project-root` flag resolves against CWD not target (see Gap #4) |
| `import-skill` | ✅⚠ | Promotes skill correctly; `triggers` not propagated from SKILL.md to skill-manifest.json (see Gap #5) |
| `brief` | ✅⚠ | Compiles all adapters; triggers column empty in skill table (see Gap #5) |
| `--version` | ❌ | `agentfactory-gen --version` fails — "No such option: --version" |
| `audit` (post-sync) | ✅ | Clean exit after wrap's internal sync |

---

## 3. Gaps Found During This Lifecycle

### Gap #1 — `audit` requires manual sync before meaningful use

**Observed:** Calling `audit` immediately after creating agent files reports untracked files and exits 1. The message says to run `wrap` or `sync`, which is correct, but it breaks the mental model of `audit` as a "check before you commit" safety net.

**Impact:** A user who runs `audit` before `wrap` gets a false failure. The workflow should be `deploy → populate → sync → audit → wrap`, but this is not documented.

**Fix:** `audit` should auto-run `sync` first (like `wrap` does), or at minimum document in help text that `sync` is a prerequisite.

---

### Gap #2 — `wrap` output goes to CWD; `--out` not obvious

**Observed:** `wrap` created `security-review-v1.0.0.zip` in `/home/magooo/repo/AgentFactory.old/` (CWD), not in the agent directory. This is correct but unintuitive — the ZIP is a peer of the `.ai/` directory.

**Impact:** In a CI/CD context, knowing exactly where the ZIP lands requires reading the success message. The `--out` flag exists but is not shown in the default help summary.

**Fix:** Print the full absolute path of the output ZIP in the success message (it does this), but also add a `--out` note to `wrap --help`.

---

### Gap #3 — `--version` not implemented on root CLI group

**Observed:** `agentfactory-gen --version` exits 1 with "No such option: --version".

**Impact:** A user trying to confirm which version is installed has no standard way to do so. `pip show agentfactory-gen` works but is not the CLI's responsibility.

**Fix:** Add `@click.version_option(version=__version__)` to the root `cli` group in `cli.py`. Should be a 1-line change.

---

### Gap #4 — `import --project-root` resolves before checking target directory

**Observed:** Running `agentfactory-gen import zip --project-root /harness` from the AgentFactory.old directory caused a conflict error because the tool found the source agent (in AgentFactory.old) before applying the `--project-root` flag.

**Impact:** `--project-root` only works reliably when invoked from the target project's directory. It does not fully redirect all operations; the conflict check ran against CWD's `.ai/` first.

**Fix:** When `--project-root` is provided, all path resolution (including the existence check) should use that root exclusively, not CWD.

---

### Gap #5 — `triggers` split across `SKILL.md` and `skill-manifest.json`

**Observed:** After `import-skill` and `brief`, the skill table in `brief.md` shows:
```
| security-review |  | .claude/skills/security-review/SKILL.md |
```
The `triggers` column is blank because `_collect_skills_data()` reads `skill-manifest.json`, which does not have a `triggers` field — only `SKILL.md` frontmatter has it.

**Impact:** The Claude brief's skill table is the primary discovery surface for slash commands. Empty triggers means the AI assistant won't know when to invoke the skill.

**Fix:** `_collect_skills_data()` should also parse the `SKILL.md` frontmatter's `triggers` field as a fallback (or `skill-manifest.json` should include `triggers`). The `deploy`/`sync` pipeline should propagate `triggers` from SKILL.md to manifest automatically.

---

### Gap #6 — No `agentfactory-gen status` command

**Missing:** There is no way to list all deployed agents, their versions, and their audit health in one call.

**Expected:** `agentfactory-gen status` → table of agents with version, last-synced, audit status.

---

### Gap #7 — No `upgrade` command

**Missing:** To update an already-imported agent to a newer version, the user must `uninstall` then `import` again. No in-place upgrade path exists.

**Expected:** `agentfactory-gen upgrade security-review --from-registry security-review@1.1.0`

---

### Gap #8 — Skill completeness oracle and harness doctor are external scripts

**Observed:** `skill-completeness-check.py` and `harness-doctor.sh` are scripts not wired into the CLI. A fresh `pip install agentfactory-gen` user discovers these only by reading the README.

**Fix:** Promote both to CLI subcommands:
- `agentfactory-gen skill validate <name>` — run completeness oracle
- `agentfactory-gen doctor` — run harness health checks

---

### Gap #9 — No pre-import verification command

**Observed:** `import` unpacks and audits in a single step. There is no way to inspect a ZIP's contents or run a dry-run audit before registering.

**Fix:** Add `agentfactory-gen import --dry-run <zip>` that unpacks to a temp directory, audits, reports findings, and exits without registering.

---

## 4. PyPI Desirability Assessment

What a fresh `pip install agentfactory-gen` user gets vs. what requires extra steps:

| Capability | Out of box? | Notes |
|------------|-------------|-------|
| `deploy`, `wrap`, `import`, `brief` | ✅ | Full lifecycle works immediately |
| Multi-adapter briefs (Claude, Codex, Gemini) | ✅ | All compiled on `brief` |
| Agent registry (global manifest) | ✅ | Auto-managed |
| Skill import and global promotion | ✅ | `import-skill` works |
| `--version` flag | ❌ | Not implemented (Gap #3) |
| Skill triggers in brief | ❌ | Empty until Gap #5 is fixed |
| Health check / doctor | ❌ | External script only |
| Skill completeness oracle | ❌ | External script only |
| Agent upgrade in-place | ❌ | No `upgrade` command |
| Dry-run import | ❌ | No `--dry-run` |
| Status overview | ❌ | No `status` command |

**Overall rating:** The core publish-and-consume lifecycle is fully functional and polished. The gaps are all in ergonomics and discoverability, not correctness. A user doing `deploy → populate → wrap → import → brief` succeeds on first try (from the right CWD).

---

## 5. Security Gaps in the CLI Itself

| Gap | Severity | Detail |
|-----|----------|--------|
| No pre-import verification | Medium | Audit runs post-unpack; a malicious ZIP could register before being detected |
| Scripts in imported agents are not sandboxed | Medium | `.ai/agents/<name>/scripts/` contains arbitrary executable code; no review gate |
| `--project-root` path traversal not validated | Low | A path like `../../etc/` would be accepted; should be validated as a real project root |
| No signature / provenance verification on imported ZIPs | Low | Any ZIP claiming to be an agent is accepted; no checksum or signing |

---

## 6. Recommendations

| Priority | Item | Effort |
|----------|------|--------|
| 🔴 P0 | Add `--version` to root CLI group | 15m |
| 🔴 P0 | Fix `triggers` propagation: read SKILL.md frontmatter in `_collect_skills_data()` | 1h |
| 🟡 P1 | Fix `--project-root` to fully redirect all path resolution | 2h |
| 🟡 P1 | `audit` should auto-sync before checking (or document sync prerequisite) | 1h |
| 🟠 P2 | Add `agentfactory-gen doctor` CLI command (wrap harness-doctor.sh logic) | 2h |
| 🟠 P2 | Add `agentfactory-gen skill validate` CLI command (wrap completeness oracle) | 2h |
| 🟠 P2 | Add `agentfactory-gen import --dry-run` | 3h |
| 🔵 P3 | Add `agentfactory-gen status` overview command | 3h |
| 🔵 P3 | Add `agentfactory-gen upgrade <agent>` | 4h |
| 🔵 P3 | ZIP signature / provenance verification on import | 4h |
