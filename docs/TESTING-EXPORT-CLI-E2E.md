# End-to-End Test Guide — `agentfactory-gen export`
<!-- version: 1.0.0 -->

PR: #180 · Pairs with `docs/FEATURE-EXPORT-CLI.md`

How to validate the `export` command end-to-end by hand: preconditions, steps,
expected output, validation checks, and failure indicators. Uses a **local bare
repo** as the "remote" so no GitHub access is required.

---

## Preconditions

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ 1. git ≥ 2.x on PATH                  git --version                       │
  │ 2. Python ≥ 3.10                      python3 --version                   │
  │ 3. The CLI (this branch), either:                                         │
  │      pip install -e .                 → `agentfactory-gen`                 │
  │      or run from source:             PYTHONPATH=src python3 -m agent_gen.cli│
  │ 4. (only for real --pr) gh installed + authenticated:  gh auth status     │
  │ 5. Unit tests green:                 PYTHONPATH=src pytest src/tests/test_export.py -q │
  └──────────────────────────────────────────────────────────────────────────┘
```

> The examples below use `RUN` as a stand-in for the CLI:
> `RUN(){ PYTHONPATH=src python3 -m agent_gen.cli "$@"; }` (run from the repo root).

---

## T0 — Build the fixture (a fake "remote" + a local agent)

```bash
T=$(mktemp -d)
# source repo with the agent at agent/
mkdir -p "$T/source/agent/skills"
cd "$T/source" && git init -q && git config user.email a@a && git config user.name a
echo '{"name":"demo","version":"1.0.0","resources":{}}' > agent/agent-manifest.json
echo 'OLD skill' > agent/skills/do.md
git add -A && git commit -qm init
# bare clone = the pushable remote
git clone -q --bare "$T/source" "$T/remote.git"
# a project with an imported + EDITED agent (source recorded)
mkdir -p "$T/proj/.ai/agents/demo/skills"
printf '{"name":"demo","version":"1.1.0","resources":{},"source":{"git":"file://%s"}}' "$T/remote.git" \
  > "$T/proj/.ai/agents/demo/agent-manifest.json"
echo 'NEW improved skill' > "$T/proj/.ai/agents/demo/skills/do.md"
echo 'brand new file'      > "$T/proj/.ai/agents/demo/skills/extra.md"
```

**Expected:** no errors; `$T/remote.git` exists; `$T/proj/.ai/agents/demo/` has the edited files.

---

## T1 — Happy path: export to the recorded source (push, no PR)

| | |
|---|---|
| **Steps** | `RUN export demo --project-root "$T/proj" --no-pr` |
| **Expected** | `Cloning file://…/remote.git` → `Applying 'demo' → agent` → `Committed: <sha> agent(demo): sync …` → `Pushed 'agentfactory/export-demo'.` |
| **Validate** | `git --git-dir="$T/remote.git" branch` lists `agentfactory/export-demo` |
| **Validate** | clone the branch and check content: |

```bash
git clone -q "$T/remote.git" "$T/v" -b agentfactory/export-demo
grep -q 'NEW improved skill' "$T/v/agent/skills/do.md"   && echo OK-modified
test -f "$T/v/agent/skills/extra.md"                      && echo OK-added
python3 -c "import json;assert json.load(open('$T/v/agent/agent-manifest.json'))['version']=='1.1.0'" && echo OK-manifest
```
**Expected:** `OK-modified`, `OK-added`, `OK-manifest`.

---

## T2 — Explicit `--git` overrides / no recorded source

| | |
|---|---|
| **Steps** | strip `source` from the manifest, then `RUN export demo --git "file://$T/remote.git" --branch t/explicit --project-root "$T/proj" --no-pr` |
| **Expected** | exit 0; branch `t/explicit` lands in the remote with the same content |

---

## T3 — `--no-push` writes a patch (offline)

| | |
|---|---|
| **Steps** | `RUN export demo --project-root "$T/proj" --no-push` |
| **Expected** | `--no-push: patch written to demo-export.patch` |
| **Validate** | `test -s "$T/proj/demo-export.patch" && head -1 "$T/proj/demo-export.patch"` → a `From <sha>` git-format-patch header |

---

## T4 — No-op when source already matches

| | |
|---|---|
| **Pre** | merge/ff the export branch into the remote's default branch (so it matches local), or re-export onto a branch already containing the changes |
| **Steps** | `RUN export demo --project-root "$T/proj" --no-pr` |
| **Expected** | `No changes to export — the source already matches. ✓` and **exit 0** (nothing pushed) |

---

## T5 — Error & edge cases

```
  ┌─ case ───────────────────────┬─ command ───────────────────────────────┬─ expected ─────────────┐
  │ missing agent                │ RUN export ghost --project-root "$T/proj"│ exit≠0 "not found"      │
  │ no source + no --git         │ (source stripped) RUN export demo …      │ exit≠0 "No source repo" │
  │ bad URL                      │ RUN export demo --git https://nope.invalid/x.git │ exit≠0 "git clone failed"│
  │ path traversal               │ RUN export demo --subpath ../etc …       │ exit≠0 "must not contain '..'"│
  │ local path as --git          │ RUN export demo --git "$T/source" …      │ accepted (→ file:// URL)│
  └──────────────────────────────┴──────────────────────────────────────────┴─────────────────────────┘
```

---

## Validation checks (summary)

```
  ✔ exit code 0 on success, non-zero on every error path
  ✔ branch agentfactory/export-<name> created on the remote (T1)
  ✔ modified + added + deleted files all reflected on the branch (T1)
  ✔ source default branch UNCHANGED (export never touches it)
  ✔ project working tree UNCHANGED — temp clone removed (ls "$T/proj"; no stray dirs)
  ✔ --no-push yields an appliable patch (T3)
  ✔ no-op path is exit 0, no push (T4)
  ✔ commit author = AgentFactory <agentfactory@local> (git log on the branch)
```

---

## Common failure indicators

```
  ┌─ symptom ────────────────────────────┬─ likely cause ───────────────────────────────┐
  │ "No such command 'export'"           │ running pip-installed old build, not this src │
  │                                      │   → use PYTHONPATH=src python3 -m agent_gen.cli│
  │ clone fails on file://               │ bare repo path wrong / not created (redo T0)  │
  │ push "denied"/"read-only"            │ remote not writable (use bare repo, or --no-push)│
  │ PR step errors but branch present    │ gh missing/unauth — open PR manually (expected)│
  │ deletions not propagated             │ check the local agent actually omits the file │
  │ stray temp dir after a crash         │ /tmp/agentfactory_export_* — safe to delete   │
  └──────────────────────────────────────┴───────────────────────────────────────────────┘
```

---

## Confirming the implementation is correct

```
  1. PYTHONPATH=src pytest src/tests/test_export.py -q          → 5 passed
  2. PYTHONPATH=src pytest src/tests -q                          → only the 2 pre-existing
                                                                   live gemini/codex auth
                                                                   tests fail (unrelated)
  3. T1 round-trips a real edit onto a branch with correct content
  4. T5 produces the exact error strings + non-zero exit for every bad input
  5. After all runs: `git -C "$T/proj" status` (if a repo) and `ls "$T/proj"`
     show no stray files beyond the optional demo-export.patch
```

Cleanup: `rm -rf "$T"`.
