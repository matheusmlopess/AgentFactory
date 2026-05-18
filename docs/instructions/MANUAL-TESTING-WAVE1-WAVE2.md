# Manual Testing Guide — Wave 1 & Wave 2
<!-- version: 1.0.0 -->

Step-by-step commands to manually verify every feature implemented in Wave 1
(foundation bugs #132–#136) and Wave 2 (security hardening + gap mitigations).

## Setup (once)

```bash
# Terminal 1 — repo (controls which code runs via editable install)
cd /home/magooo/repo/AgentFactory.old

# Terminal 2 — test environment
rm -rf /tmp/af-test && mkdir /tmp/af-test && cd /tmp/af-test
agentfactory-gen init
agentfactory-gen deploy my-agent
```

---

## Wave 1 features

Switch branch before running these:

```bash
# Terminal 1
git checkout feature/wave1-foundation-bugs
```

### 1 — `--version` flag (#133)

```bash
agentfactory-gen --version
# Expected: agentfactory-gen, version 0.3.2
```

### 2 — `audit` exit code split (#132)

Untracked files are warnings (exit 0). Broken resources are fatal (exit 1).

```bash
# Untracked file → exit 0
echo "stray content" > .ai/agents/my-agent/orphan.md
agentfactory-gen audit my-agent
echo "Exit: $?"
# Expected: exit 0, message about untracked file

# Broken resource → exit 1
echo '{"name":"my-agent","version":"1.0.0","resources":{"skills":["skills/missing.md"]},"dependencies":{}}' \
  > .ai/agents/my-agent/agent-manifest.json
agentfactory-gen audit my-agent
echo "Exit: $?"
# Expected: exit 1, broken resource message
```

### 3 — `import-skill` from SKILL.md only (#134, open-standard)

Open-standard skills (agentskills.io) only require `name` + `description`.
AgentFactory auto-generates `skill-manifest.json` from the frontmatter.

```bash
# Reset agent first
agentfactory-gen deploy my-agent 2>/dev/null; true

mkdir -p lean-skill
printf -- '---\nname: lean-skill\ndescription: Open-standard minimal skill\n---\n# lean-skill\n' \
  > lean-skill/SKILL.md

agentfactory-gen import-skill lean-skill --to my-agent
# Expected: success — auto-generates skill-manifest.json

cat .ai/agents/my-agent/skills/lean-skill/skill-manifest.json
# Expected: {"name": "lean-skill", "description": "Open-standard minimal skill"}
# Note: no "version" or "triggers" keys — they are optional per the open standard
```

### 4 — `import-skill` rejects missing description

```bash
mkdir -p bad-skill
printf -- '---\nname: bad-skill\n---\n' > bad-skill/SKILL.md

agentfactory-gen import-skill bad-skill --to my-agent
echo "Exit: $?"
# Expected: exit 1, error mentions "description"
```

### 5 — `wrap --print-path` (#136)

```bash
agentfactory-gen wrap my-agent --print-path
# Expected: last line of output is the zip path, e.g. /tmp/af-test/my-agent-v1.0.0.zip

agentfactory-gen -q wrap my-agent --print-path
# Expected: ONLY the zip path — quiet suppresses everything else
```

### 6 — `import --project-root` conflict detection (#135)

```bash
mkdir -p /tmp/other-project
agentfactory-gen init --project-root /tmp/other-project
agentfactory-gen deploy conflict-agent
agentfactory-gen wrap conflict-agent

# Simulate agent already installed in target project
mkdir -p /tmp/other-project/.ai/agents
cp -r .ai/agents/conflict-agent /tmp/other-project/.ai/agents/

# Import should detect conflict in TARGET, not CWD
agentfactory-gen import conflict-agent-v1.0.0.zip --project-root /tmp/other-project
echo "Exit: $?"
# Expected: exit 1, conflict detected in /tmp/other-project
```

---

## Wave 2 features

Switch branch before running these:

```bash
# Terminal 1
git checkout feature/wave2-gap-mitigations
```

### 7 — `audit --fix`

```bash
echo "orphan" > .ai/agents/my-agent/orphan2.md
agentfactory-gen audit my-agent
# Expected: warns about untracked file, exits 0

agentfactory-gen audit my-agent --fix
# Expected: syncs orphan2.md into manifest, re-audits clean

agentfactory-gen audit my-agent
# Expected: clean
```

### 8 — `wrap --dry-run` (#143)

```bash
agentfactory-gen wrap my-agent --dry-run
ls *.zip 2>/dev/null || echo "No zip written"
# Expected: lists what would be bundled — NO .zip file is created
```

### 9 — Invalid project root error (brief / adapter add)

```bash
agentfactory-gen brief --project-root /tmp/not-a-project
# Expected: "not an AgentFactory project (no .ai/ directory found)"

agentfactory-gen adapter add gemini --project-root /tmp/not-a-project
# Expected: same error
```

### 10 — `import-skill --project-root`

```bash
mkdir -p lean-skill
printf -- '---\nname: lean-skill\ndescription: Cross-project skill\n---\n' \
  > lean-skill/SKILL.md

# Import into a different project
agentfactory-gen import-skill lean-skill --to my-agent \
  --project-root /tmp/other-project
# Expected: skill installed into /tmp/other-project, not CWD

# Invalid root gives a clear error
agentfactory-gen import-skill lean-skill --to my-agent \
  --project-root /tmp/not-a-project
echo "Exit: $?"
# Expected: exit 1, invalid project root error
```

### 11 — Scripts gate: shebang detection (#144)

```bash
# Build a zip with a shebang script in commands/
mkdir -p shebang-agent/commands
printf '#!/usr/bin/env python3\nprint("hello")\n' > shebang-agent/commands/run.py
echo '{"name":"shebang-agent","version":"1.0.0","resources":{},"dependencies":{}}' \
  > shebang-agent/agent-manifest.json
cd shebang-agent && zip -r ../shebang-agent.zip . && cd ..

agentfactory-gen import shebang-agent.zip
# Expected: prompts "Bundle contains executable files... Proceed? [y/N]"
# Type n → aborts

agentfactory-gen import shebang-agent.zip --allow-scripts
# Expected: imports without prompting
```

### 12 — Gemini `skills` symlink (2026 open-standard alignment)

```bash
ls -la .gemini/skills
# Expected: symlink → ../../.ai/skills  (was .gemini/tools/ before alignment)

grep "Available Skills" .ai/adapters/gemini/brief.md
# Expected: "## Available Skills" header

grep "Use when:" .ai/adapters/gemini/brief.md
# Expected: "- Use when:" fields  (was "- Input:" before alignment)
```

---

## Notes

- Features 1–6 require `feature/wave1-foundation-bugs` to be checked out in the repo.
- Features 7–12 require `feature/wave2-gap-mitigations`.
- After all PRs merge to `main`, all 12 tests work from a single `git checkout main`.
- SKILL.md frontmatter **must start at column 1** — no leading spaces before `---`.
  The parser now tolerates leading whitespace (`.lstrip()` fix), but the closing `---`
  must also be at column 1 for standard YAML compatibility.
