<!-- version: 1.0.0 -->
# AgentFactory Mock Review — security-review Transfer Lifecycle <!-- version: 1.0.0 -->

> Live walkthrough of the `deploy → describe → wrap → import → import-skill → brief` pipeline
> performed on 2026-04-28 using the `security-review` agent transfer from AgentFactory.old
> to agentfactory-harness as the test vehicle.

---

```
╔══════════════════════════════════════════════════════════════════════════════╗
║           security-review AGENT TRANSFER — LIFECYCLE RESULT                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─ OUTCOME ──────────────────────────────────────────────────────────────────┐
│  ✅  Agent IMPORTED and REGISTERED in agentfactory-harness                 │
│  ✅  Skill PROMOTED to global scope (.ai/skills/security-review/)          │
│  ✅  Brief RECOMPILED — skill appears in .ai/adapters/claude/brief.md      │
│  ⚠   Skill triggers column is BLANK in the brief (Gap #5 — not fixed yet) │
└────────────────────────────────────────────────────────────────────────────┘

┌─ STEP-BY-STEP WORKFLOW ─────────────────────────────────────────────────────┐
│                                                                              │
│  AgentFactory.old                                                            │
│  ──────────────                                                              │
│  1. deploy     agentfactory-gen deploy security-review                 ✅   │
│                └─ scaffolds 5-dir standard under .ai/agents/                │
│                                                                              │
│  2. describe   agentfactory-gen describe security-review --desc "..."  ✅   │
│                                                                              │
│  3. populate   Manual — wrote SKILL.md, skill-manifest.json,           ✅   │
│                report-template.md, mermaid-safe-patterns.md,                │
│                SKILL-SECURITY-REVIEW.md                                     │
│                                                                              │
│  4. audit      agentfactory-gen audit security-review                  ⚠    │
│                └─ FAILED — untracked files (Gap #1)                         │
│                └─ WORKAROUND: skipped; wrap auto-syncs internally           │
│                                                                              │
│  5. wrap       agentfactory-gen wrap security-review                   ✅   │
│                └─ auto-synced then packaged                                 │
│                └─ OUTPUT: security-review-v1.0.0.zip (CWD, not agent dir)  │
│                                                                              │
│  agentfactory-harness                                                        │
│  ────────────────────                                                        │
│  6. import     agentfactory-gen import \                               ✅   │
│                  /path/to/security-review-v1.0.0.zip                        │
│                └─ WORKAROUND: ran from harness CWD (not --project-root)     │
│                   --project-root resolves conflict check against CWD        │
│                   (Gap #4) — importing from correct CWD was the fix         │
│                └─ Agent registered in .ai/agent-manifest.json               │
│                └─ Files unpacked to .ai/agents/security-review/             │
│                                                                              │
│  7. import-skill  agentfactory-gen import-skill \                     ✅   │
│                     .ai/agents/security-review/skills/security-review       │
│                   └─ promoted to .ai/skills/security-review/ (global)       │
│                                                                              │
│  8. brief      agentfactory-gen brief                                  ✅   │
│                └─ all 3 adapters recompiled (Claude, Codex, Gemini)         │
│                └─ skill row present in brief.md — but triggers = "" (Gap#5)│
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘

┌─ WORKAROUNDS REQUIRED ──────────────────────────────────────────────────────┐
│                                                                              │
│  Gap #1  audit before sync  →  skipped; used wrap directly (auto-syncs)    │
│  Gap #3  --version missing  →  used pip show agentfactory-gen instead       │
│  Gap #4  --project-root CWD →  cd'd into harness first, dropped the flag   │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘

┌─ ARTEFACTS CREATED ─────────────────────────────────────────────────────────┐
│                                                                              │
│  AgentFactory.old                                                            │
│  ├── .ai/agents/security-review/          ← deployed agent                 │
│  │   ├── agent-manifest.json                                                │
│  │   ├── skills/security-review/                                            │
│  │   │   ├── SKILL.md                     ← 6-step review procedure        │
│  │   │   ├── skill-manifest.json                                            │
│  │   │   └── references/                                                    │
│  │   │       ├── report-template.md       ← {{PLACEHOLDER}} skeleton       │
│  │   │       └── mermaid-safe-patterns.md ← GitHub rendering rules         │
│  │   └── docs/SKILL-SECURITY-REVIEW.md    ← feature doc                   │
│  ├── docs/CLI-ASSESSMENT.md               ← live-run assessment            │
│  └── security-review-v1.0.0.zip           ← portable agent package        │
│                                                                              │
│  agentfactory-harness                                                        │
│  ├── .ai/agents/security-review/          ← imported                       │
│  ├── .ai/skills/security-review/          ← globally promoted              │
│  ├── .ai/agent-manifest.json              ← auto-updated                   │
│  ├── .ai/adapters/claude/brief.md         ← recompiled (skill row present) │
│  └── docs/REVIEW-SECURITY-ARCHITECTURE-2026-04-27.md  ← first review      │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘

┌─ GITHUB ISSUES FILED (matheusmlopess/AgentFactory) ─────────────────────────┐
│                                                                              │
│  CLI ergonomics  #132 audit no auto-sync  #133 --version missing            │
│                  #134 triggers not in brief  #135 --project-root CWD        │
│                  #136 wrap --out hidden  #137 no status  #138 no upgrade    │
│                  #139 scripts not in CLI  #140 no dry-run                   │
│                                                                              │
│  Security        #141 audit post-unpack (Medium)                            │
│                  #142 scripts/ unsandboxed (Medium)                         │
│                  #143 --project-root path traversal (Low)                   │
│                  #144 no ZIP checksum/signature (Low)                       │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘

┌─ ONE KNOWN UNFIXED GAP IN THIS SESSION ─────────────────────────────────────┐
│                                                                              │
│  Gap #5 — triggers column is blank in the compiled brief.                   │
│  Root cause: _collect_skills_data() reads skill-manifest.json, which has    │
│  no triggers field. SKILL.md frontmatter has it but is never parsed.        │
│  Fix tracked in issue #134. Not yet implemented.                            │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

| # | Takeaway |
|---|----------|
| 1 | The core `deploy → wrap → import → brief` path works on first try from the correct CWD |
| 2 | `wrap` is the safe entry point — it auto-syncs, making `audit` redundant as a standalone prerequisite |
| 3 | `--project-root` is broken for cross-repo imports; CWD discipline is the workaround |
| 4 | `triggers` in SKILL.md never reach the compiled brief — AI assistants can't discover skills by keyword |
| 5 | All 9 CLI gaps and 4 security gaps are documented and filed as issues for future sprints |

---

*Generated from live lifecycle execution on 2026-04-28. See `docs/CLI-ASSESSMENT.md` for full command-by-command analysis.*
