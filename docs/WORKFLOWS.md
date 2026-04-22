# AgentFactory — Workflow Diagrams
<!-- version: 1.1.0 -->

Architecture, lifecycle, and pipeline diagrams for AgentFactory.
See [README](../README.md) for installation and quick start.

---

## 1. Overall Architecture

```mermaid
graph TD
    subgraph root["Project Root"]
        CM[CLAUDE.md]
        AM["AGENTS.md / CODEX.md"]
        GM[GEMINI.md]
        CL[.claude]
        GE[.gemini]
        CD[.codex]
    end

    subgraph harness[".ai/ — Unified Harness"]
        AF["AgentFactory.md (master compiled brief)"]
        MF["agent-manifest.json (global registry)"]

        subgraph adapters["adapters/"]
            ACA_B["claude/brief.md (compiled)"]
            AGE_B["gemini/brief.md (compiled)"]
            ACO_B["codex/brief.md (compiled)"]
        end

        subgraph shared["shared/"]
            RU[rules/]
            SK[skills/]
            CMD[commands/]
            AG[agents/]
            MEM["memory/ — milestones.md"]
        end
    end

    CM -->|symlink| ACA_B
    AM -->|symlink| ACO_B
    GM -->|symlink| AGE_B
    CL -->|symlink to adapter dir| adapters
    GE -->|symlink to adapter dir| adapters
    CD -->|symlink to adapter dir| adapters

    RU -->|compiled into| ACA_B
    RU -->|compiled into| ACO_B
    RU -->|compiled into| AGE_B
    CMD -->|compiled into| ACA_B
    SK -->|compiled into| ACA_B
    SK -->|compiled into| ACO_B
    SK -->|compiled into| AGE_B
    AF -->|preamble injected into| ACA_B
    AF -->|preamble injected into| ACO_B
    AF -->|preamble injected into| AGE_B
```

> **Note:** Root files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) are symlinks to
> per-adapter compiled briefs — **not** to `AgentFactory.md` directly. This is the
> FormatSwitch model introduced in #96. `AgentFactory.md` is a full master compiled
> brief that is also the preamble source for every adapter brief.

---

## 2. Brief Compilation Pipeline (`agentfactory-gen brief`)

```mermaid
flowchart TD
    subgraph sources["Input Sources (.ai/)"]
        SK[skills/]
        AG[agents/]
        CMD[commands/]
        RU[rules/]
        AF["AgentFactory.md\n(preamble extracted)"]
    end

    SK & AG & CMD & RU & AF --> COLLECT["_compile_adapter_briefs()\ncollect data dict"]

    COLLECT --> RC["_render_brief() × adapter"]

    RC --> CB["claude/brief.md\ncontext_char_limit: 4000"]
    RC --> COB["codex/brief.md\ncontext_char_limit: 2000"]
    RC --> GB["gemini/brief.md\ncontext_char_limit: 4000"]

    CB --> |sections| CS["## Harness\n## Project Context\n## Skills\n## Commands\n## Agents\n## Rules"]
    COB --> |sections| COS["## Harness\n## Project Context\n(truncated if > 2000)\n## Skills\n## Agents\n## Rules"]
    GB --> |sections| GS["## Harness\n## Project Context\n## Skills\n## Agents\n## Rules"]

    COLLECT --> AFCOMP["_compile_agentfactory_md()\nupsert @commands + @rules into AgentFactory.md"]
    AFCOMP --> AF
```

---

## 3. Agent Lifecycle

```mermaid
flowchart LR
    A([Start]) --> B["agentfactory-gen deploy name"]
    B --> C["Scaffold 5-dir structure\nskills commands docs\nscripts orchestration"]
    C --> D["Init agent-manifest.json\nvia Librarian.init"]

    D --> E["agentfactory-gen describe\n--desc --plan"]
    E --> F["Update manifest metadata"]

    F --> G["Develop\nadd skills commands docs"]

    G --> H["agentfactory-gen audit name"]
    H --> I{Clean?}
    I -->|"broken deps or missing files"| G
    I -->|pass| J["agentfactory-gen wrap name"]

    J --> K["Librarian.sync\ncrawl disk to manifest"]
    K --> L["Librarian.audit\nvalidate all paths"]
    L --> M{Audit pass?}
    M -->|fail| G
    M -->|pass| N["Compress to name-vX.Y.Z.zip\nPortable Unit"]

    N --> O[Share ZIP]
    O --> P["agentfactory-gen import zip"]
    P --> Q["Unpack into .ai/agents/name"]
    Q --> R[Audit imported bundle]
    R --> S["Register in global manifest"]
    S --> T([Agent ready])

    T --> U["agentfactory-gen uninstall name"]
    U --> V["Remove dir\nDeregister from manifest"]
```

---

## 4. Remote Import Pipeline (`--from-git`)

```mermaid
flowchart TD
    A["agentfactory-gen import --from-git URL"] --> B{"Valid URL scheme?\nhttps git@ ssh"}
    B -->|no| ERR1([Error: invalid URL])
    B -->|yes| C["git clone --quiet URL"]
    C --> D{Clone success?}
    D -->|no| ERR2([Error: clone failed])
    D -->|yes| E["Extract context\nfrom README.md + CLAUDE.md"]

    E --> F["propose_retrofit\ndetect profile"]
    F --> G{Profile detected?}
    G -->|"claude / gemini / codex"| H["Warn if multiple\nprofiles matched"]
    G -->|auto| I[Apply auto-rules]
    H --> J["Librarian.migrate\nremap dirs to 5-dir standard"]
    I --> J

    J --> K["Auto-stub skill-manifest.json files"]
    K --> L["Init agent-manifest.json\ninject description from context"]
    L --> M["Librarian.wrap\ncompress to ZIP"]
    M --> N[Unpack + Audit]
    N --> O{Audit pass?}
    O -->|fail| ERR3([Error: abort import])
    O -->|pass| P[Register in global manifest]
    P --> Q[Cleanup temp dir]
    Q --> R([Import complete — Agent ready])
```

---

## 5. Librarian Intelligence Layer

```mermaid
flowchart TD
    A["Crawl agent root\nTRACKED_DIRS"] --> B["Update resources in manifest"]
    B --> C["_detect_dependencies\nper resource file"]
    C --> D{File type?}
    D -->|.py| E["AST import parser\nextract module names"]
    D -->|".md / other"| F["Regex scan\nfor @depends-on: markers"]
    E --> G["Write dependencies map to manifest"]
    F --> G
    G --> H["_detect_orchestration\nfirst file in orchestration/"]
    H --> I["_update_skills_metadata\nparse skill-manifest.json files"]
    I --> J[Save manifest]

    J --> K["validate\ncheck all resource paths exist"]
    K --> L["Check broken dependencies\ncross-file refs missing on disk"]
    L --> M["Check untracked files\non disk but not in manifest"]
    M --> N["Check missing skill-manifest.json"]
    N --> O["Check skill version drift\nskill-manifest vs SKILL.md frontmatter"]
    O --> P["_check_repo_state\nlatest tag + remote URL match"]
    P --> Q([Return audit report])
```

---

## 6. Multi-CLI Harness — Adapter Wiring

```mermaid
graph LR
    SK["skills/"]
    CMD["commands/"]

    subgraph claude[".ai/adapters/claude/"]
        CS["skills symlink"]
        CC["commands symlink"]
        CSET["settings.json"]
    end

    subgraph gemini[".ai/adapters/gemini/"]
        GT["tools symlink"]
        GCFG["config.json"]
    end

    subgraph codex[".ai/adapters/codex/"]
        CP["prompts symlink"]
        CCFG["config.toml"]
    end

    CS -->|symlink| SK
    CC -->|symlink| CMD
    GT -->|symlink| SK
    CP -->|symlink| CMD

    CLAUDE([Claude Code]) --> CS
    CLAUDE --> CC
    GEMINI([Gemini CLI]) --> GT
    CODEX([Codex CLI]) --> CP
```

---

## 7. CI Pipeline (every push / PR)

```mermaid
flowchart TD
    A(["Push or PR to dev / main"]) --> B

    subgraph ci["ci.yml"]
        B["Job: lint — ruff check src/"] --> C{Lint pass?}
        C -->|fail| STOP1([Block — fix lint errors])
        C -->|pass| D

        D["Job: test matrix\nPython 3.11 + 3.12 in parallel"]
        D --> E["pip install -e .[dev]"]
        E --> F["pytest --cov=agent_gen --cov-fail-under=80"]
        F --> G{"Tests + Coverage >= 80%?"}
        G -->|fail| STOP2([Block — fix tests or add coverage])
        G -->|pass| H(["Status check green — Tests + Coverage"])
    end

    H --> I{Is this a PR to dev?}
    I -->|yes| J[Branch protection gate requires green status]
    J --> K([PR can be merged])
```

---

## 8. CD Pipeline (on version tag)

```mermaid
flowchart TD
    A(["git tag vX.Y.Z\ngit push origin vX.Y.Z"]) --> B

    subgraph release["release.yml"]
        B["Job: build"] --> C["pip install build"]
        C --> D["python -m build"]
        D --> E["Produce dist/ — wheel + sdist"]
        E --> F["Upload artifacts to Actions store"]

        F --> G["Job: github-release\nruns after build"]
        G --> H["Extract release notes from CHANGELOG.md"]
        H --> I["Create GitHub Release\nattach wheel + sdist"]

        F --> J["Job: pypi-publish\nruns after build"]
        J --> K["OIDC trusted publish\nno token secret needed"]
        K --> L(["Published to PyPI\npypi.org/project/agentfactory-gen"])
    end

    I --> M([Release visible on GitHub Releases page])
```

---

## 9. Traceability / Milestone Update Workflow

```mermaid
flowchart TD
    A(["Work starts on an issue"]) --> B["Create feature branch\nfix/feat/docs/upgrade"]
    B --> C[Implement changes]
    C --> D["Push branch — Open PR"]
    D --> E["CI runs\nlint + tests + coverage"]
    E --> F{CI green?}
    F -->|no| C
    F -->|yes| G[PR review + merge]

    G --> H["Update .ai/memory/milestones.md\nStep 8.5 of git-versioning skill"]
    H --> I["Move issue row\nPending to Completed"]
    I --> J["Fill Branch / PR / Commit"]
    J --> K{Is this a release commit?}
    K -->|yes| L["Stamp Tag column\nfor all shipped items"]
    K -->|no| M["Bump milestones.md\nversion marker PATCH"]
    L --> M
    M --> N["git tag vX.Y.Z\ntriggers CD pipeline"]
    N --> O(["GitHub Release + PyPI publish"])
```
