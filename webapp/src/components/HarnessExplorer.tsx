import { useState } from "react";
import { harnessTree, type TreeNode } from "../data/harnessTree";
import { FileTree } from "./FileTree";
import { DocPane } from "./DocPane";

const DEFAULT_EXPANDED = new Set([".ai", ".ai/adapters", ".ai/agents"]);

export function HarnessExplorer() {
  const [selected, setSelected] = useState<TreeNode>(harnessTree);
  const [expanded, setExpanded] = useState<Set<string>>(DEFAULT_EXPANDED);

  const toggle = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  return (
    <section className="explorer" id="explorer">
      <div className="explorer-intro">
        <p className="section-label">Harness Explorer</p>
        <h2>Browse the <code>.ai/</code> structure</h2>
        <p className="explorer-lede">
          Select any node to see what it does and how it fits into the AgentFactory harness.
        </p>
      </div>

      <div className="explorer-panels surface">
        <nav className="explorer-tree" aria-label="Harness file tree">
          <FileTree
            nodes={[harnessTree]}
            selected={selected.path}
            expanded={expanded}
            onSelect={setSelected}
            onToggle={toggle}
          />
        </nav>
        <DocPane node={selected} />
      </div>
    </section>
  );
}
