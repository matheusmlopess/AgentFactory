import { useState, useMemo } from "react";
import { REGISTRY_AGENTS } from "../data/registry";
import type { AgentListing } from "../types/registry";

function formatDownloads(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function AgentCard({
  agent,
  selected,
  onClick,
}: {
  agent: AgentListing;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={`reg-card${selected ? " reg-card--selected" : ""}`}
      onClick={onClick}
    >
      <div className="reg-card-header">
        <span className="reg-card-slug">{agent.slug}</span>
        <span className="reg-card-version">v{agent.version}</span>
      </div>
      <p className="reg-card-desc">{agent.description}</p>
      <div className="reg-card-footer">
        <span className="reg-card-author">@{agent.author}</span>
        <span className="reg-card-downloads">
          ↓ {formatDownloads(agent.downloads)}
        </span>
      </div>
      <div className="reg-card-tags">
        {agent.tags.slice(0, 4).map((t) => (
          <span key={t} className="reg-tag">{t}</span>
        ))}
      </div>
    </button>
  );
}

function DetailPane({ agent }: { agent: AgentListing }) {
  const installCmd = `agentfactory-gen import --from-registry ${agent.slug}`;
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(installCmd).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div className="reg-detail">
      <div className="reg-detail-header">
        <div className="reg-detail-title-row">
          <h3 className="reg-detail-slug">{agent.slug}</h3>
          <span className="reg-detail-version">v{agent.version}</span>
        </div>
        <p className="reg-detail-meta">
          by <strong>@{agent.author}</strong> · published {formatDate(agent.published_at)} · {agent.downloads.toLocaleString()} downloads
        </p>
      </div>

      <p className="reg-detail-desc">{agent.description}</p>

      <div className="reg-detail-tags">
        {agent.tags.map((t) => (
          <span key={t} className="reg-tag">{t}</span>
        ))}
      </div>

      {/* Install command */}
      <div className="reg-install">
        <span className="reg-install-label">Install</span>
        <div className="reg-install-row">
          <code className="reg-install-cmd">{installCmd}</code>
          <button className="reg-copy-btn" onClick={copy}>
            {copied ? "copied ✓" : "copy"}
          </button>
        </div>
      </div>

      {/* Manifest preview */}
      <div className="reg-manifest">
        <p className="reg-manifest-label">Manifest</p>
        <div className="reg-manifest-grid">
          {agent.manifest.skills.length > 0 && (
            <div className="reg-manifest-row">
              <span className="reg-manifest-key">skills</span>
              <span className="reg-manifest-val">
                {agent.manifest.skills.join(", ")}
              </span>
            </div>
          )}
          {agent.manifest.commands.length > 0 && (
            <div className="reg-manifest-row">
              <span className="reg-manifest-key">commands</span>
              <span className="reg-manifest-val">
                {agent.manifest.commands.join(", ")}
              </span>
            </div>
          )}
          {agent.manifest.adapters.length > 0 && (
            <div className="reg-manifest-row">
              <span className="reg-manifest-key">adapters</span>
              <span className="reg-manifest-val">
                {agent.manifest.adapters.join(", ")}
              </span>
            </div>
          )}
          <div className="reg-manifest-row">
            <span className="reg-manifest-key">version</span>
            <span className="reg-manifest-val">{agent.manifest.version}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function RegistryBrowser() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<AgentListing>(REGISTRY_AGENTS[0]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return REGISTRY_AGENTS;
    return REGISTRY_AGENTS.filter(
      (a) =>
        a.slug.includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.tags.some((t) => t.includes(q)) ||
        a.author.toLowerCase().includes(q)
    );
  }, [query]);

  return (
    <section className="registry" id="registry">
      <div className="registry-intro">
        <h2 className="registry-title">Agent Registry</h2>
        <p className="registry-lede">
          Browse and import Portable Unit agent bundles published by the community.
          Install any agent with a single CLI command.
        </p>
      </div>

      {/* Search bar */}
      <div className="reg-search-row">
        <input
          className="reg-search"
          type="search"
          placeholder="Search agents by name, tag, or author…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="reg-count">
          {filtered.length} agent{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Two-panel layout */}
      <div className="reg-panels surface">
        {/* Card list */}
        <div className="reg-list">
          {filtered.length === 0 ? (
            <p className="reg-empty">No agents match "{query}"</p>
          ) : (
            filtered.map((agent) => (
              <AgentCard
                key={agent.slug}
                agent={agent}
                selected={agent.slug === selected?.slug}
                onClick={() => setSelected(agent)}
              />
            ))
          )}
        </div>

        {/* Detail pane */}
        <div className="reg-detail-wrap">
          {selected ? (
            <DetailPane agent={selected} />
          ) : (
            <p className="reg-empty">Select an agent to see details.</p>
          )}
        </div>
      </div>
    </section>
  );
}
