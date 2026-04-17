// registry.ts — mock agent listing data (Phase 1 static scaffold)
// Replace with API calls once backend (FastAPI + PostgreSQL) is deployed.
// <!-- version: 1.0.0 -->

import type { AgentListing } from "../types/registry";

export const REGISTRY_AGENTS: AgentListing[] = [
  {
    slug: "git-workflow-agent",
    version: "2.3.0",
    description:
      "Full git workflow automation: feature branching, semantic versioning, PR management, and changelog generation. Wraps the git-versioning skill with opinionated defaults.",
    author: "matheusmlopess",
    downloads: 1_284,
    published_at: "2026-03-12T09:14:00Z",
    tags: ["git", "versioning", "workflow", "ci"],
    is_public: true,
    zip_url: "#",
    manifest: {
      name: "git-workflow-agent",
      version: "2.3.0",
      description: "Git workflow automation with semantic versioning and PR management.",
      skills: ["git-versioning", "diff-visualizer"],
      commands: ["git-workflow"],
      adapters: ["claude", "codex"],
    },
  },
  {
    slug: "code-reviewer",
    version: "1.1.2",
    description:
      "Structured code review agent. Analyses diffs, checks for security patterns, enforces style guides, and produces a scored review report. Works with GitHub PRs via the gh CLI.",
    author: "af-community",
    downloads: 876,
    published_at: "2026-03-28T14:30:00Z",
    tags: ["code-review", "security", "github", "pr"],
    is_public: true,
    zip_url: "#",
    manifest: {
      name: "code-reviewer",
      version: "1.1.2",
      description: "Structured PR code review with security and style checks.",
      skills: ["diff-visualizer"],
      commands: ["review-pr"],
      adapters: ["claude", "gemini"],
    },
  },
  {
    slug: "docs-writer",
    version: "1.0.0",
    description:
      "Documentation generation agent. Reads source code and existing docs, identifies gaps, and produces markdown documentation with consistent structure and version markers.",
    author: "af-community",
    downloads: 542,
    published_at: "2026-04-01T11:05:00Z",
    tags: ["docs", "markdown", "writing"],
    is_public: true,
    zip_url: "#",
    manifest: {
      name: "docs-writer",
      version: "1.0.0",
      description: "Automated documentation generation from source code and existing docs.",
      skills: [],
      commands: ["write-docs"],
      adapters: ["claude"],
    },
  },
  {
    slug: "test-scaffold",
    version: "1.2.1",
    description:
      "Unit and integration test scaffolding agent. Analyses existing code, identifies untested paths, and generates pytest / Jest test skeletons with 80% coverage targets.",
    author: "af-community",
    downloads: 391,
    published_at: "2026-04-05T08:22:00Z",
    tags: ["testing", "pytest", "jest", "coverage"],
    is_public: true,
    zip_url: "#",
    manifest: {
      name: "test-scaffold",
      version: "1.2.1",
      description: "Test skeleton generation targeting 80% coverage.",
      skills: [],
      commands: ["scaffold-tests"],
      adapters: ["claude", "codex", "gemini"],
    },
  },
  {
    slug: "deploy-agent",
    version: "0.9.0",
    description:
      "Deployment pipeline agent for Railway, Render, and Fly.io. Reads project structure, generates platform configs, and guides through first-deploy and rollback procedures.",
    author: "matheusmlopess",
    downloads: 218,
    published_at: "2026-04-10T16:45:00Z",
    tags: ["deploy", "railway", "render", "infra"],
    is_public: true,
    zip_url: "#",
    manifest: {
      name: "deploy-agent",
      version: "0.9.0",
      description: "Deployment automation for Railway, Render, and Fly.io.",
      skills: [],
      commands: ["deploy"],
      adapters: ["claude"],
    },
  },
];
