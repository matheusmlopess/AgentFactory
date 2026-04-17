import type { TreeNode } from "../data/harnessTree";

type Props = {
  node: TreeNode;
};

const KIND_LABEL: Record<string, string> = {
  dir: "directory",
  file: "file",
  symlink: "symlink",
};

export function DocPane({ node }: Props) {
  return (
    <article className="doc-pane">
      <header className="doc-header">
        <span className={`badge badge-kind badge-kind--${node.kind}`}>
          {KIND_LABEL[node.kind]}
        </span>
        {node.tag && (
          <span className="badge badge-tag">{node.tag}</span>
        )}
      </header>

      <code className="doc-path">{node.path}</code>
      <h3 className="doc-title">{node.name.replace(" →", "")}</h3>
      <p className="doc-description">{node.description}</p>
    </article>
  );
}
