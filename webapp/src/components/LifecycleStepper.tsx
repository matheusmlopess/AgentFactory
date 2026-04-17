import { useState } from "react";
import { LIFECYCLE_STEPS } from "../data/lifecycle";
import type { LifecycleStep } from "../data/lifecycle";

type StepStatus = "done" | "active" | "pending";

function statusIcon(s: StepStatus): string {
  if (s === "done")   return "✓";
  if (s === "active") return "→";
  return "○";
}

function fileActionClass(action: string): string {
  if (action === "created")  return "lc-file--created";
  if (action === "modified") return "lc-file--modified";
  return "lc-file--deleted";
}

function fileActionLabel(action: string): string {
  if (action === "created")  return "+";
  if (action === "modified") return "~";
  return "−";
}

function DetailPanel({ step, status }: { step: LifecycleStep; status: StepStatus }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(step.command).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div className="lc-detail" role="tabpanel">
      <div className="lc-detail-header">
        <span className={`lc-status-badge lc-status--${status}`}>
          {statusIcon(status)} {status}
        </span>
        <h3 className="lc-detail-title">{step.title}</h3>
        <p className="lc-detail-summary">{step.summary}</p>
      </div>

      {/* Command */}
      <div className="lc-command-block">
        <span className="lc-block-label">Command</span>
        <div className="lc-command-row">
          <code className="lc-command">{step.command}</code>
          <button className="reg-copy-btn" onClick={copy} aria-label="Copy command">
            {copied ? "copied ✓" : "copy"}
          </button>
        </div>
      </div>

      {/* Internal explanation */}
      <div className="lc-internal-block">
        <span className="lc-block-label">What the Librarian does</span>
        <p className="lc-internal-text">{step.internal}</p>
      </div>

      {/* Files */}
      {step.files.length > 0 && (
        <div className="lc-files-block">
          <span className="lc-block-label">Files affected</span>
          <ul className="lc-file-list" aria-label="Files affected">
            {step.files.map((f) => (
              <li key={f.path} className={`lc-file-row ${fileActionClass(f.action)}`}>
                <span className="lc-file-action" aria-label={f.action}>
                  {fileActionLabel(f.action)}
                </span>
                <code className="lc-file-path">{f.path}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {step.files.length === 0 && (
        <div className="lc-files-block">
          <span className="lc-block-label">Files affected</span>
          <p className="lc-no-files">No files written — read-only operation.</p>
        </div>
      )}
    </div>
  );
}

export function LifecycleStepper() {
  const [active, setActive] = useState(0);

  return (
    <section className="lifecycle" id="lifecycle">
      <div className="lifecycle-intro">
        <h2 className="lifecycle-title">Agent Lifecycle</h2>
        <p className="lifecycle-lede">
          Step-by-step walkthrough of how <code>agentfactory-gen</code> manages an
          agent from scaffold to distribution. Click any step to explore it.
        </p>
      </div>

      <div className="lc-panels surface">
        {/* Step rail */}
        <nav className="lc-rail" aria-label="Lifecycle steps">
          {LIFECYCLE_STEPS.map((step, i) => {
            const status: StepStatus =
              i < active ? "done" : i === active ? "active" : "pending";
            return (
              <button
                key={step.id}
                className={`lc-step${i === active ? " lc-step--active" : ""}`}
                onClick={() => setActive(i)}
                aria-selected={i === active}
                role="tab"
              >
                <span className={`lc-step-icon lc-step-icon--${status}`}>
                  {statusIcon(status)}
                </span>
                <span className="lc-step-body">
                  <span className="lc-step-title">{step.title}</span>
                  <code className="lc-step-cmd">{step.command.split(" ").slice(0, 2).join(" ")} …</code>
                </span>
                {i < LIFECYCLE_STEPS.length - 1 && (
                  <span className="lc-connector" aria-hidden="true" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Detail panel */}
        <DetailPanel
          step={LIFECYCLE_STEPS[active]}
          status="active"
        />
      </div>
    </section>
  );
}
