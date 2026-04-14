import type { TreeNode } from "../data/harnessTree";

type Props = {
  nodes: TreeNode[];
  selected: string;
  expanded: Set<string>;
  onSelect: (node: TreeNode) => void;
  onToggle: (path: string) => void;
  depth?: number;
};

export function FileTree({
  nodes,
  selected,
  expanded,
  onSelect,
  onToggle,
  depth = 0,
}: Props) {
  return (
    <ul className="tree-list" style={{ paddingLeft: depth === 0 ? 0 : "1.1rem" }}>
      {nodes.map((node) => {
        const isDir = node.kind === "dir";
        const isOpen = expanded.has(node.path);
        const isSelected = node.path === selected;

        return (
          <li key={node.path} className="tree-item">
            <button
              className={[
                "tree-node",
                isSelected ? "tree-node--selected" : "",
                isDir ? "tree-node--dir" : `tree-node--${node.kind}`,
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => {
                onSelect(node);
                if (isDir) onToggle(node.path);
              }}
            >
              <span className="tree-icon" aria-hidden>
                {isDir ? (isOpen ? "▾" : "▸") : node.kind === "symlink" ? "⇢" : "·"}
              </span>
              <span className="tree-name">{node.name}</span>
            </button>

            {isDir && isOpen && node.children && (
              <FileTree
                nodes={node.children}
                selected={selected}
                expanded={expanded}
                onSelect={onSelect}
                onToggle={onToggle}
                depth={depth + 1}
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}
