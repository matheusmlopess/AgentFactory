import { useState } from "react";
import {
  MANIFEST_MINIMAL,
  MANIFEST_FULL,
  MANIFEST_FIELDS,
} from "../data/manifest";

type Variant = "minimal" | "full";

function getAnnotation(key: string): string {
  return MANIFEST_FIELDS.find((f) => f.key === key)?.annotation ?? "";
}

function JsonLine({
  depth,
  keyName,
  value,
  comma,
}: {
  depth: number;
  keyName?: string;
  value: unknown;
  comma: boolean;
}) {
  const indent = "  ".repeat(depth);
  const annotation = keyName ? getAnnotation(keyName) : "";

  if (value === null || typeof value !== "object") {
    const rendered =
      typeof value === "string" ? `"${value}"` : String(value);
    return (
      <div className="mj-line" title={annotation || undefined}>
        <span className="mj-indent">{indent}</span>
        {keyName && (
          <>
            <span className="mj-key" data-annotated={!!annotation}>
              "{keyName}"
            </span>
            <span className="mj-colon">: </span>
          </>
        )}
        <span className="mj-value">{rendered}</span>
        {comma && <span className="mj-comma">,</span>}
        {annotation && <span className="mj-annotation"> // {annotation}</span>}
      </div>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <div className="mj-line" title={annotation || undefined}>
          <span className="mj-indent">{indent}</span>
          {keyName && (
            <>
              <span className="mj-key" data-annotated={!!annotation}>"{keyName}"</span>
              <span className="mj-colon">: </span>
            </>
          )}
          <span className="mj-bracket">[]</span>
          {comma && <span className="mj-comma">,</span>}
          {annotation && <span className="mj-annotation"> // {annotation}</span>}
        </div>
      );
    }
    return (
      <>
        <div className="mj-line" title={annotation || undefined}>
          <span className="mj-indent">{indent}</span>
          {keyName && (
            <>
              <span className="mj-key" data-annotated={!!annotation}>"{keyName}"</span>
              <span className="mj-colon">: </span>
            </>
          )}
          <span className="mj-bracket">[</span>
          {annotation && <span className="mj-annotation"> // {annotation}</span>}
        </div>
        {value.map((item, i) => (
          <JsonLine
            key={i}
            depth={depth + 1}
            value={item}
            comma={i < value.length - 1}
          />
        ))}
        <div className="mj-line">
          <span className="mj-indent">{indent}</span>
          <span className="mj-bracket">]</span>
          {comma && <span className="mj-comma">,</span>}
        </div>
      </>
    );
  }

  // object
  const entries = Object.entries(value as Record<string, unknown>);
  return (
    <>
      <div className="mj-line" title={annotation || undefined}>
        <span className="mj-indent">{indent}</span>
        {keyName && (
          <>
            <span className="mj-key" data-annotated={!!annotation}>"{keyName}"</span>
            <span className="mj-colon">: </span>
          </>
        )}
        <span className="mj-bracket">{"{"}</span>
        {annotation && <span className="mj-annotation"> // {annotation}</span>}
      </div>
      {entries.map(([k, v], i) => (
        <JsonLine
          key={k}
          depth={depth + 1}
          keyName={k}
          value={v}
          comma={i < entries.length - 1}
        />
      ))}
      <div className="mj-line">
        <span className="mj-indent">{indent}</span>
        <span className="mj-bracket">{"}"}</span>
        {comma && <span className="mj-comma">,</span>}
      </div>
    </>
  );
}

export function ManifestInspector() {
  const [variant, setVariant] = useState<Variant>("minimal");
  const [copied, setCopied] = useState(false);

  const data = variant === "minimal" ? MANIFEST_MINIMAL : MANIFEST_FULL;
  const json = JSON.stringify(data, null, 2);

  function copy() {
    navigator.clipboard.writeText(json).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  const entries = Object.entries(data);

  return (
    <section className="manifest-inspector" id="manifest">
      <div className="manifest-intro">
        <h2 className="manifest-title">Manifest Inspector</h2>
        <p className="manifest-lede">
          The <code>agent-manifest.json</code> is the single source of truth for
          every agent — its resources, dependencies, and metadata. Hover any
          highlighted key for an explanation.
        </p>
      </div>

      <div className="manifest-panel surface">
        {/* Toolbar */}
        <div className="manifest-toolbar">
          <div className="manifest-variants" role="group" aria-label="Manifest variant">
            <button
              className={`mf-variant-btn${variant === "minimal" ? " mf-variant-btn--active" : ""}`}
              onClick={() => setVariant("minimal")}
            >
              Minimal
            </button>
            <button
              className={`mf-variant-btn${variant === "full" ? " mf-variant-btn--active" : ""}`}
              onClick={() => setVariant("full")}
            >
              Full — intelligence layer
            </button>
          </div>
          <button className="reg-copy-btn" onClick={copy} aria-label="Copy JSON">
            {copied ? "copied ✓" : "copy JSON"}
          </button>
        </div>

        {/* Annotated JSON */}
        <div className="mj-viewer" role="region" aria-label="Manifest JSON">
          <div className="mj-line">
            <span className="mj-bracket">{"{"}</span>
          </div>
          {entries.map(([k, v], i) => (
            <JsonLine
              key={k}
              depth={1}
              keyName={k}
              value={v}
              comma={i < entries.length - 1}
            />
          ))}
          <div className="mj-line">
            <span className="mj-bracket">{"}"}</span>
          </div>
        </div>

        {/* Field legend */}
        <div className="mj-legend">
          <span className="mj-legend-item">
            <span className="mj-key" data-annotated="true">key</span>
            hover for annotation
          </span>
          <span className="mj-legend-item mj-annotation-sample">
            // inline annotation
          </span>
        </div>
      </div>
    </section>
  );
}
