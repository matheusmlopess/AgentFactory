import { useState } from "react";
import type { CompletenessReport, AtomType, AtomStatus } from "../types/completeness";
import diffReport from "../data/reports/skill-diff-visualizer-completeness.json";
import gitReport from "../data/reports/skill-git-versioning-completeness.json";

const REPORTS: Record<string, CompletenessReport> = {
  "diff-visualizer": diffReport as CompletenessReport,
  "git-versioning": gitReport as CompletenessReport,
};

const STATUS_ICON: Record<AtomStatus, string> = {
  preserved: "✓",
  degraded: "~",
  missing: "✗",
};

const TYPE_LABELS: Record<AtomType, string> = {
  decision_path: "decision path",
  command: "command",
  error_case: "error case",
  data_table: "data table",
  external_ref: "external ref",
  constraint: "constraint",
};

type FilterValue = AtomType | "all";

export function CompletenessViewer() {
  const skills = Object.keys(REPORTS);
  const [activeSkill, setActiveSkill] = useState<string>(skills[0]);
  const [filter, setFilter] = useState<FilterValue>("all");

  const report = REPORTS[activeSkill];
  const atomTypes = [...new Set(report.atoms.map((a) => a.type))] as AtomType[];
  const filtered =
    filter === "all" ? report.atoms : report.atoms.filter((a) => a.type === filter);

  const scoreClass =
    report.score >= 95 ? "score--high" : report.score >= 90 ? "score--mid" : "score--low";

  const rerunCmd = `python3 .ai/scripts/skill-completeness-check.py --skill ${report.skill}`;

  return (
    <section className="completeness" id="completeness">
      <div className="completeness-intro">
        <span className="badge badge-pro">pro</span>
        <h2 className="completeness-title">Skill Completeness</h2>
        <p className="completeness-lede">
          Pre-generated semantic reports showing how much functional capability each{" "}
          <code>SKILL.md</code> retained after its last trim. Powered by the two-phase LLM
          oracle — no API key required to view cached results.
        </p>
      </div>

      {/* Skill selector tabs */}
      <div className="skill-tabs" role="tablist">
        {skills.map((sk) => (
          <button
            key={sk}
            role="tab"
            aria-selected={sk === activeSkill}
            className={`skill-tab${sk === activeSkill ? " skill-tab--active" : ""}`}
            onClick={() => {
              setActiveSkill(sk);
              setFilter("all");
            }}
          >
            {sk}
          </button>
        ))}
      </div>

      {/* Results panel */}
      <div className="results-panel surface">
        {/* Score header */}
        <div className="results-header">
          <div className={`score-badge ${scoreClass}`}>
            <span className="score-value">{report.score}%</span>
            <span className="score-label">{report.passed ? "passed" : "failed"}</span>
          </div>

          <div className="results-meta">
            <span className="results-skill">{report.skill}</span>
            <span className="results-versions">
              {report.old_version} → {report.new_version}
            </span>
            <span className="results-date">
              {new Date(report.generated_at).toLocaleDateString()}
            </span>
          </div>

          <div className="summary-counts">
            <span className="count count--preserved">
              <span className="count-icon">✓</span>
              {report.summary.preserved} preserved
            </span>
            {report.summary.degraded > 0 && (
              <span className="count count--degraded">
                <span className="count-icon">~</span>
                {report.summary.degraded} degraded
              </span>
            )}
            {report.summary.missing > 0 && (
              <span className="count count--missing">
                <span className="count-icon">✗</span>
                {report.summary.missing} missing
              </span>
            )}
          </div>
        </div>

        {/* Filter bar */}
        <div className="filter-bar">
          <button
            className={`filter-chip${filter === "all" ? " filter-chip--active" : ""}`}
            onClick={() => setFilter("all")}
          >
            all ({report.atoms.length})
          </button>
          {atomTypes.map((t) => {
            const count = report.atoms.filter((a) => a.type === t).length;
            return (
              <button
                key={t}
                className={`filter-chip${filter === t ? " filter-chip--active" : ""}`}
                onClick={() => setFilter(t)}
              >
                {TYPE_LABELS[t]} ({count})
              </button>
            );
          })}
        </div>

        {/* Atom list */}
        <ul className="atom-list">
          {filtered.map((atom) => (
            <li key={atom.id} className={`atom-row atom-row--${atom.status}`}>
              <span className={`atom-status atom-status--${atom.status}`}>
                {STATUS_ICON[atom.status]}
              </span>
              <div className="atom-body">
                <span className="atom-type">{TYPE_LABELS[atom.type]}</span>
                <span className="atom-desc">{atom.description}</span>
                {atom.status !== "preserved" && (
                  <span className="atom-evidence">{atom.evidence}</span>
                )}
              </div>
            </li>
          ))}
        </ul>

        {/* Re-run hint */}
        <div className="rerun-hint">
          <span className="rerun-label">Re-run locally:</span>
          <code className="rerun-cmd">{rerunCmd}</code>
        </div>
      </div>
    </section>
  );
}
