// manifest.ts — sample agent-manifest.json variants for ManifestInspector
// <!-- version: 1.0.0 -->

export interface ManifestField {
  key: string;
  annotation: string;
}

export const MANIFEST_FIELDS: ManifestField[] = [
  { key: "name",               annotation: "Unique agent identifier. Used as directory name and registry slug." },
  { key: "version",            annotation: "Semantic version (MAJOR.MINOR.PATCH). Bumped on every wrap." },
  { key: "description",        annotation: "Human-readable summary. Appears in CLAUDE.md and registry listings." },
  { key: "orchestration_plan", annotation: "Entry point the LLM executes first. Usually a plan.json or main.py." },
  { key: "resources",          annotation: "Tracked file lists per category. Paths are relative to the agent root." },
  { key: "skills",             annotation: "Skill manifests or SKILL.md files this agent declares." },
  { key: "commands",           annotation: "CLI command documentation files (one per slash-command)." },
  { key: "scripts",            annotation: "Executable scripts the LLM can invoke." },
  { key: "orchestration",      annotation: "Workflow definition files (plan.json, etc.)." },
  { key: "docs",               annotation: "Documentation files included in the bundle." },
  { key: "dependencies",       annotation: "Cross-resource dependency map. Keyed by resource path." },
  { key: "imported_at",        annotation: "ISO 8601 timestamp set at import time. Not set on deploy." },
  { key: "git_ref",            annotation: "Git commit SHA at time of import — provenance tracking." },
  { key: "skills_metadata",    annotation: "Arbitrary metadata per skill subdirectory (injected by intelligence layer)." },
];

export const MANIFEST_MINIMAL = {
  name: "my-agent",
  version: "1.0.0",
  description: "A minimal AgentFactory-compatible agent.",
  resources: {
    skills:        [],
    commands:      [],
    scripts:       [],
    orchestration: [],
    docs:          [],
  },
};

export const MANIFEST_FULL = {
  name: "git-workflow-agent",
  version: "2.3.0",
  description: "Git workflow automation with semantic versioning and PR management.",
  orchestration_plan: "orchestration/plan.json",
  resources: {
    skills: [
      "skills/git-versioning/skill-manifest.json",
      "skills/diff-visualizer/skill-manifest.json",
    ],
    commands:      ["commands/git-workflow.md"],
    scripts:       ["scripts/bump.py", "scripts/changelog.py"],
    orchestration: ["orchestration/plan.json"],
    docs:          ["docs/CLAUDE.md"],
  },
  dependencies: {
    "scripts/changelog.py": ["scripts/bump.py"],
  },
  skills_metadata: {
    "skills/git-versioning": {
      version: "1.3.1",
      triggers: "bump version, tag release, open PR",
    },
  },
  imported_at: "2026-04-14T17:32:45Z",
  git_ref:     "3d83de5",
};
