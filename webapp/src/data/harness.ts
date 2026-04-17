export type FeatureCard = {
  title: string;
  detail: string;
  status: "ready" | "next";
};

export type Step = {
  command: string;
  title: string;
  detail: string;
};

export const featureCards: FeatureCard[] = [
  {
    title: "Harness Explorer",
    detail: "Interactive `.ai/` tree and contextual documentation panels land in Phase 1.",
    status: "ready",
  },
  {
    title: "Manifest Inspector",
    detail: "Typed manifest walkthrough and lifecycle stepper follow in adjacent issues.",
    status: "next",
  },
  {
    title: "Registry Platform",
    detail: "Public registry, publish/import flows, and team workspace features build on this scaffold.",
    status: "next",
  },
];

export const lifecycleSteps: Step[] = [
  {
    command: "agentfactory-gen init",
    title: "Initialize",
    detail: "Scaffold the shared harness, adapters, and root symlinks.",
  },
  {
    command: "agentfactory-gen deploy my-agent",
    title: "Deploy",
    detail: "Create the standard 5-directory agent structure and manifest shell.",
  },
  {
    command: "agentfactory-gen audit my-agent",
    title: "Audit",
    detail: "Validate manifests, dependencies, path safety, and harness drift.",
  },
  {
    command: "agentfactory-gen wrap my-agent",
    title: "Wrap",
    detail: "Build a portable unit for distribution or registry upload.",
  },
];
