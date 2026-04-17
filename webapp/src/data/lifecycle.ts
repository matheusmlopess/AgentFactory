// lifecycle.ts — full step data for LifecycleStepper
// <!-- version: 1.0.0 -->

export interface LifecycleFile {
  path: string;
  action: "created" | "modified" | "deleted";
}

export interface LifecycleStep {
  id: string;
  command: string;
  title: string;
  summary: string;
  internal: string;
  files: LifecycleFile[];
}

export const LIFECYCLE_STEPS: LifecycleStep[] = [
  {
    id: "deploy",
    command: "agentfactory-gen deploy my-agent",
    title: "Deploy",
    summary: "Scaffold a new agent with the 5-directory standard structure.",
    internal:
      "The Librarian creates the agent directory under .ai/agents/, scaffolds five subdirectories each with a .gitkeep, and writes a minimal agent-manifest.json with empty resource lists and no dependencies.",
    files: [
      { path: ".ai/agents/my-agent/skills/.gitkeep",        action: "created" },
      { path: ".ai/agents/my-agent/commands/.gitkeep",      action: "created" },
      { path: ".ai/agents/my-agent/scripts/.gitkeep",       action: "created" },
      { path: ".ai/agents/my-agent/orchestration/.gitkeep", action: "created" },
      { path: ".ai/agents/my-agent/docs/.gitkeep",          action: "created" },
      { path: ".ai/agents/my-agent/agent-manifest.json",    action: "created" },
    ],
  },
  {
    id: "describe",
    command: "agentfactory-gen describe my-agent --plan",
    title: "Describe",
    summary: "Generate a structured plan or human-readable description of the agent.",
    internal:
      "The Librarian reads agent-manifest.json, resolves all resource paths, and renders either a plain description or a structured --plan block that lists capabilities, dependencies, and orchestration entry points. Useful for onboarding and documentation.",
    files: [
      { path: ".ai/agents/my-agent/agent-manifest.json", action: "modified" },
    ],
  },
  {
    id: "audit",
    command: "agentfactory-gen audit my-agent",
    title: "Audit",
    summary: "Validate all manifest paths, dependencies, and harness health.",
    internal:
      "The Librarian walks every path listed in agent-manifest.json and verifies it exists and is readable. It also checks for dependency cycles, validates semver fields, and flags harness drift (symlinks pointing to missing targets). Returns a scored audit report.",
    files: [],
  },
  {
    id: "wrap",
    command: "agentfactory-gen wrap my-agent",
    title: "Wrap",
    summary: "Bundle the agent into a Portable Unit ZIP for distribution.",
    internal:
      "After passing an internal audit, the Librarian calls sync() to refresh resource lists, then packages the agent directory plus its manifest into a timestamped ZIP. The resulting Portable Unit is self-contained and can be imported into any project running AgentFactory.",
    files: [
      { path: "my-agent-v1.0.0.zip", action: "created" },
    ],
  },
  {
    id: "import",
    command: "agentfactory-gen import my-agent-v1.0.0.zip",
    title: "Import",
    summary: "Unpack and register a Portable Unit into the local harness.",
    internal:
      "The Librarian peeks the ZIP manifest, unpacks to .ai/agents/<name>/, runs a deep audit, then registers the agent in the global agent-manifest.json. It updates all active adapter briefs (CLAUDE.md, AGENTS.md, GEMINI.md) to include the new agent's capabilities.",
    files: [
      { path: ".ai/agents/my-agent/",               action: "created" },
      { path: ".ai/agent-manifest.json",             action: "modified" },
      { path: "CLAUDE.md",                           action: "modified" },
      { path: "AGENTS.md",                           action: "modified" },
    ],
  },
  {
    id: "uninstall",
    command: "agentfactory-gen uninstall my-agent",
    title: "Uninstall",
    summary: "Deregister and remove an agent from the harness.",
    internal:
      "The Librarian removes the agent entry from the global agent-manifest.json, updates all active adapter briefs to strip the agent's capabilities, then deletes the agent directory. Rolls back briefs first so the harness is never left in an inconsistent state.",
    files: [
      { path: ".ai/agents/my-agent/",   action: "deleted" },
      { path: ".ai/agent-manifest.json", action: "modified" },
      { path: "CLAUDE.md",               action: "modified" },
      { path: "AGENTS.md",               action: "modified" },
    ],
  },
];
