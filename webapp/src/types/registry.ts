// registry.ts — types for the public agent registry
// <!-- version: 1.0.0 -->

export interface AgentListing {
  slug: string;
  version: string;
  description: string;
  author: string;
  downloads: number;
  published_at: string; // ISO 8601
  tags: string[];
  is_public: boolean;
  manifest: AgentManifestPreview;
  zip_url: string;
}

export interface AgentManifestPreview {
  name: string;
  version: string;
  description: string;
  skills: string[];
  commands: string[];
  adapters: string[];
}
