import { useState, useMemo, useCallback } from "react";

const PRICING = {
  claude_sonnet_input: 3.0,
  claude_sonnet_output: 15.0,
  claude_opus_input: 15.0,
  claude_opus_output: 75.0,
  codex_input: 2.5,
  gemini_input: 0.15,
};

const CONTEXT_WINDOWS = { claude: 200000, codex: 200000, gemini: 1000000 };

const BASE_FILES = {
  "harness.json": { min: 50, max: 125, tier: 1, category: "manifest" },
  "ARCHITECTURE.md": { min: 750, max: 1500, tier: 3, category: "core" },
  "DOMAIN.md": { min: 500, max: 1250, tier: 3, category: "core" },
  "CONSTRAINTS.md": { min: 250, max: 750, tier: 1, category: "core" },
  "STANDARDS.md": { min: 500, max: 1000, tier: 1, category: "core" },
  "AGENTS.md": { min: 250, max: 750, tier: 3, category: "core" },
};

const HANDOFF_FILES = {
  "SESSION.md": { min: 125, max: 500, tier: 1, category: "handoff" },
  "session-state.json": { min: 125, max: 500, tier: 1, category: "handoff" },
  "DECISIONS.md": { min: 125, max: 500, tier: 2, category: "handoff", perEntry: 150 },
  "HANDOFF_PROTOCOL.md": { min: 250, max: 500, tier: 0, category: "handoff" },
  "CONFLICT_RESOLUTION.md": { min: 125, max: 250, tier: 0, category: "handoff" },
  "bootstrap adapter": { min: 125, max: 250, tier: 1, category: "handoff" },
};

const RULE_FILE = { min: 250, max: 750, tier: 2, category: "rules" };
const SKILL_FILES = {
  "SKILL.md": { min: 250, max: 750 },
  "checklist.md": { min: 125, max: 500 },
  "reference.md": { min: 500, max: 2000 },
  "examples.md": { min: 250, max: 1000 },
};
const SKILL_MANIFEST = { min: 200, max: 500, tier: 1, category: "skills" };
const CLI_INSTRUCTION = { min: 250, max: 750, tier: 1, category: "cli" };
const AGENT_MEMORY = { min: 250, max: 750, tier: 2, category: "cli" };

function lerp(min, max, t) { return Math.round(min + (max - min) * t); }

function calcScenario(config) {
  const { clis, skills, rules, decisions, docSize, optimized, activeSkills, activeRules } = config;
  const isMulti = clis.length > 1;
  const t = docSize;
  let tiers = { 0: 0, 1: 0, 2: 0, 3: 0 };
  let breakdown = {};

  const add = (name, tokens, tier) => {
    tiers[tier] = (tiers[tier] || 0) + tokens;
    breakdown[name] = { tokens, tier };
  };

  // Always loaded
  Object.entries(BASE_FILES).forEach(([name, f]) => {
    const tokens = lerp(f.min, f.max, t);
    add(name, tokens, optimized ? f.tier : 1);
  });

  add("CLI instruction file", lerp(CLI_INSTRUCTION.min, CLI_INSTRUCTION.max, t), 1);

  // Rules
  for (let i = 0; i < rules; i++) {
    const tokens = lerp(RULE_FILE.min, RULE_FILE.max, t);
    const loaded = optimized ? (i < activeRules) : true;
    add(`rule-${i + 1}`, loaded ? tokens : 0, optimized ? 2 : 1);
  }

  // Skills
  if (optimized) {
    add("MANIFEST.md", lerp(SKILL_MANIFEST.min, SKILL_MANIFEST.max, t), 1);
    for (let i = 0; i < skills; i++) {
      if (i < activeSkills) {
        let total = 0;
        Object.entries(SKILL_FILES).forEach(([, sf]) => { total += lerp(sf.min, sf.max, t); });
        add(`skill-${i + 1} (loaded)`, total, 2);
      }
    }
  } else {
    for (let i = 0; i < skills; i++) {
      let total = 0;
      Object.entries(SKILL_FILES).forEach(([, sf]) => { total += lerp(sf.min, sf.max, t); });
      add(`skill-${i + 1}`, total, 1);
    }
  }

  // Handoff
  if (isMulti) {
    add("SESSION.md", lerp(HANDOFF_FILES["SESSION.md"].min, HANDOFF_FILES["SESSION.md"].max, t), 1);
    add("session-state.json", lerp(HANDOFF_FILES["session-state.json"].min, HANDOFF_FILES["session-state.json"].max, t), 1);
    
    const decTokens = optimized
      ? Math.min(decisions, 30) * HANDOFF_FILES["DECISIONS.md"].perEntry
      : decisions * HANDOFF_FILES["DECISIONS.md"].perEntry;
    add("DECISIONS.md", decTokens, 2);
    
    if (!optimized) {
      add("HANDOFF_PROTOCOL.md", lerp(HANDOFF_FILES["HANDOFF_PROTOCOL.md"].min, HANDOFF_FILES["HANDOFF_PROTOCOL.md"].max, t), 1);
      add("CONFLICT_RESOLUTION.md", lerp(HANDOFF_FILES["CONFLICT_RESOLUTION.md"].min, HANDOFF_FILES["CONFLICT_RESOLUTION.md"].max, t), 1);
    }
    add("bootstrap adapter", lerp(HANDOFF_FILES["bootstrap adapter"].min, HANDOFF_FILES["bootstrap adapter"].max, t), 1);
  }

  // Agent memory (Claude only)
  if (clis.includes("claude")) {
    add("agent-memory", lerp(AGENT_MEMORY.min, AGENT_MEMORY.max, t), 2);
  }

  let totalByTier = {};
  let totalAll = 0;
  if (optimized) {
    totalByTier = { ...tiers };
    totalAll = tiers[1] + tiers[2]; // Tier 3 on-demand, Tier 0 excluded
  } else {
    totalAll = Object.values(tiers).reduce((a, b) => a + b, 0);
    totalByTier = { 1: totalAll };
  }

  const typicalLoad = optimized ? tiers[1] + tiers[2] : totalAll;
  const fullLoad = Object.values(tiers).reduce((a, b) => a + b, 0);

  return { tiers, breakdown, typicalLoad, fullLoad, isMulti };
}

function Bar({ value, max, color, label, sub, height = 28 }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#8a8a9a", marginBottom: 2, fontFamily: "'JetBrains Mono', monospace" }}>
        <span>{label}</span>
        <span>{sub}</span>
      </div>
      <div style={{ background: "#1a1a2e", borderRadius: 4, height, overflow: "hidden", position: "relative" }}>
        <div style={{
          width: `${pct}%`, height: "100%", background: color,
          borderRadius: 4, transition: "width 0.5s cubic-bezier(0.4,0,0.2,1)",
          display: "flex", alignItems: "center", paddingLeft: 8,
          fontSize: 11, color: "#fff", fontWeight: 600, fontFamily: "'JetBrains Mono', monospace",
          minWidth: value > 0 ? 40 : 0,
        }}>
          {value > 0 && `${value.toLocaleString()}`}
        </div>
      </div>
    </div>
  );
}

function Gauge({ value, max, label, color, warn, danger }) {
  const pct = (value / max) * 100;
  const status = pct > danger ? "🔴" : pct > warn ? "⚠️" : "✅";
  return (
    <div style={{ textAlign: "center", padding: "12px 8px" }}>
      <div style={{ position: "relative", width: 80, height: 80, margin: "0 auto 8px" }}>
        <svg viewBox="0 0 36 36" style={{ transform: "rotate(-90deg)" }}>
          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none" stroke="#1a1a2e" strokeWidth="3" />
          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none" stroke={pct > danger ? "#ff4757" : pct > warn ? "#ffa502" : color}
            strokeWidth="3" strokeDasharray={`${pct}, 100`}
            style={{ transition: "stroke-dasharray 0.6s cubic-bezier(0.4,0,0.2,1)" }} />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#e8e8f0", fontFamily: "'JetBrains Mono', monospace" }}>{pct.toFixed(1)}%</span>
        </div>
      </div>
      <div style={{ fontSize: 11, color: "#8a8a9a", fontFamily: "'JetBrains Mono', monospace" }}>{status} {label}</div>
    </div>
  );
}

function CostCard({ label, value, sub, accent }) {
  return (
    <div style={{ background: "#12121f", border: "1px solid #2a2a3e", borderRadius: 8, padding: "14px 16px", flex: 1, minWidth: 130 }}>
      <div style={{ fontSize: 10, color: "#6a6a7a", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4, fontFamily: "'JetBrains Mono', monospace" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: accent || "#e8e8f0", fontFamily: "'JetBrains Mono', monospace" }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "#5a5a6a", marginTop: 2, fontFamily: "'JetBrains Mono', monospace" }}>{sub}</div>}
    </div>
  );
}

function Slider({ label, value, onChange, min, max, step = 1, suffix = "" }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: "#8a8a9a", fontFamily: "'JetBrains Mono', monospace" }}>{label}</span>
        <span style={{ fontSize: 11, color: "#00d2ff", fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{value}{suffix}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(Number(e.target.value))}
        style={{ width: "100%", accentColor: "#00d2ff", height: 4, cursor: "pointer" }} />
    </div>
  );
}

function Toggle({ label, value, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, cursor: "pointer" }} onClick={() => onChange(!value)}>
      <div style={{
        width: 36, height: 20, borderRadius: 10, background: value ? "#00d2ff" : "#2a2a3e",
        position: "relative", transition: "background 0.2s",
      }}>
        <div style={{
          width: 16, height: 16, borderRadius: 8, background: "#fff", position: "absolute",
          top: 2, left: value ? 18 : 2, transition: "left 0.2s",
        }} />
      </div>
      <span style={{ fontSize: 11, color: value ? "#e8e8f0" : "#6a6a7a", fontFamily: "'JetBrains Mono', monospace" }}>{label}</span>
    </div>
  );
}

function CliToggle({ cli, active, onChange }) {
  const colors = { claude: "#ff6b35", codex: "#00d2ff", gemini: "#a855f7" };
  return (
    <div onClick={() => onChange(cli)} style={{
      padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
      fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: 0.5,
      background: active ? colors[cli] + "22" : "#1a1a2e",
      border: `1.5px solid ${active ? colors[cli] : "#2a2a3e"}`,
      color: active ? colors[cli] : "#5a5a6a",
      transition: "all 0.2s",
    }}>
      {cli}
    </div>
  );
}

const PRESETS = {
  "Fresh single": { clis: ["claude"], skills: 1, rules: 5, decisions: 0, docSize: 0.3, switchesPerDay: 1 },
  "Mature single": { clis: ["claude"], skills: 5, rules: 5, decisions: 0, docSize: 0.6, switchesPerDay: 1 },
  "Fresh multi": { clis: ["claude", "gemini"], skills: 1, rules: 5, decisions: 5, docSize: 0.3, switchesPerDay: 3 },
  "Mature multi": { clis: ["claude", "codex", "gemini"], skills: 5, rules: 5, decisions: 20, docSize: 0.6, switchesPerDay: 5 },
  "Worst case": { clis: ["claude", "codex", "gemini"], skills: 10, rules: 5, decisions: 100, docSize: 1.0, switchesPerDay: 10 },
};

export default function HarnessBenchmark() {
  const [clis, setClis] = useState(["claude"]);
  const [skills, setSkills] = useState(1);
  const [rules, setRules] = useState(5);
  const [decisions, setDecisions] = useState(0);
  const [docSize, setDocSize] = useState(0.3);
  const [optimized, setOptimized] = useState(false);
  const [activeSkills, setActiveSkills] = useState(1);
  const [activeRules, setActiveRules] = useState(2);
  const [switchesPerDay, setSwitchesPerDay] = useState(1);
  const [model, setModel] = useState("claude_sonnet_input");

  const toggleCli = useCallback((cli) => {
    setClis(prev => prev.includes(cli) ? (prev.length > 1 ? prev.filter(c => c !== cli) : prev) : [...prev, cli]);
  }, []);

  const applyPreset = useCallback((key) => {
    const p = PRESETS[key];
    setClis(p.clis); setSkills(p.skills); setRules(p.rules);
    setDecisions(p.decisions); setDocSize(p.docSize); setSwitchesPerDay(p.switchesPerDay);
  }, []);

  const config = useMemo(() => ({
    clis, skills, rules, decisions, docSize, optimized,
    activeSkills: Math.min(activeSkills, skills),
    activeRules: Math.min(activeRules, rules),
  }), [clis, skills, rules, decisions, docSize, optimized, activeSkills, activeRules]);

  const result = useMemo(() => calcScenario(config), [config]);

  const unoptResult = useMemo(() => calcScenario({ ...config, optimized: false }), [config]);
  const optResult = useMemo(() => calcScenario({ ...config, optimized: true }), [config]);

  const currentResult = optimized ? optResult : unoptResult;
  const tokens = currentResult.typicalLoad;
  const pricePer1M = PRICING[model] || 3.0;
  const costPerInit = (tokens / 1_000_000) * pricePer1M;
  const costPerDay = costPerInit * switchesPerDay;
  const costPerMonth = costPerDay * 22;

  const savings = unoptResult.typicalLoad - optResult.typicalLoad;
  const savingsPct = unoptResult.typicalLoad > 0 ? ((savings / unoptResult.typicalLoad) * 100) : 0;

  const contextPcts = {};
  clis.forEach(cli => {
    contextPcts[cli] = (tokens / CONTEXT_WINDOWS[cli]) * 100;
  });

  const breakdownEntries = Object.entries(currentResult.breakdown)
    .filter(([, v]) => v.tokens > 0)
    .sort((a, b) => b[1].tokens - a[1].tokens);

  const tierColors = { 0: "#5a5a6a", 1: "#00d2ff", 2: "#ffa502", 3: "#a855f7" };
  const tierLabels = { 0: "Excluded", 1: "Tier 1 · Always", 2: "Tier 2 · Task-matched", 3: "Tier 3 · On-demand" };

  return (
    <div style={{ background: "#0a0a14", color: "#e8e8f0", minHeight: "100vh", fontFamily: "'JetBrains Mono', monospace", padding: "24px 20px" }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 10, color: "#00d2ff", textTransform: "uppercase", letterSpacing: 3, marginBottom: 4 }}>AI Harness</div>
          <h1 style={{ fontSize: 26, fontWeight: 800, margin: 0, color: "#e8e8f0", lineHeight: 1.2 }}>
            Bootstrap Token Benchmark
          </h1>
          <p style={{ fontSize: 12, color: "#5a5a6a", margin: "6px 0 0", lineHeight: 1.5 }}>
            Simulate token cost and context utilization for every harness configuration.
          </p>
        </div>

        {/* Presets */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 20 }}>
          {Object.keys(PRESETS).map(key => (
            <button key={key} onClick={() => applyPreset(key)} style={{
              padding: "5px 12px", borderRadius: 5, border: "1px solid #2a2a3e", background: "#12121f",
              color: "#8a8a9a", fontSize: 10, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
              textTransform: "uppercase", letterSpacing: 0.5,
            }}>{key}</button>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 24 }}>

          {/* Controls */}
          <div>
            <div style={{ background: "#12121f", border: "1px solid #1e1e32", borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 12 }}>Active CLIs</div>
              <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
                {["claude", "codex", "gemini"].map(cli => (
                  <CliToggle key={cli} cli={cli} active={clis.includes(cli)} onChange={toggleCli} />
                ))}
              </div>

              <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 12 }}>Parameters</div>
              <Slider label="Skills" value={skills} onChange={setSkills} min={0} max={15} />
              <Slider label="Rules" value={rules} onChange={setRules} min={1} max={10} />
              <Slider label="Decisions" value={decisions} onChange={setDecisions} min={0} max={200} />
              <Slider label="Doc verbosity" value={docSize} onChange={setDocSize} min={0} max={1} step={0.1} suffix={docSize < 0.4 ? " lean" : docSize < 0.7 ? " mid" : " verbose"} />
              <Slider label="Switches/day" value={switchesPerDay} onChange={setSwitchesPerDay} min={1} max={20} suffix="/d" />
            </div>

            <div style={{ background: "#12121f", border: "1px solid #1e1e32", borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 12 }}>Optimization</div>
              <Toggle label="Tiered bootstrap" value={optimized} onChange={setOptimized} />
              {optimized && (
                <>
                  <Slider label="Skills loaded (task-matched)" value={Math.min(activeSkills, skills)} onChange={setActiveSkills} min={0} max={skills} />
                  <Slider label="Rules loaded (task-matched)" value={Math.min(activeRules, rules)} onChange={setActiveRules} min={1} max={rules} />
                </>
              )}
            </div>

            <div style={{ background: "#12121f", border: "1px solid #1e1e32", borderRadius: 10, padding: 16 }}>
              <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 12 }}>Pricing Model</div>
              <select value={model} onChange={e => setModel(e.target.value)} style={{
                width: "100%", padding: "6px 8px", background: "#1a1a2e", border: "1px solid #2a2a3e",
                borderRadius: 5, color: "#e8e8f0", fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
              }}>
                <option value="claude_sonnet_input">Sonnet input ($3/MTok)</option>
                <option value="claude_opus_input">Opus input ($15/MTok)</option>
                <option value="codex_input">Codex input ($2.5/MTok)</option>
                <option value="gemini_input">Gemini input ($0.15/MTok)</option>
              </select>
            </div>
          </div>

          {/* Results */}
          <div>
            {/* Cost cards */}
            <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
              <CostCard label="Bootstrap tokens" value={tokens.toLocaleString()} sub={`${(tokens / 1000).toFixed(1)}K`} accent="#00d2ff" />
              <CostCard label="Cost / init" value={`$${costPerInit.toFixed(4)}`} sub={`@ $${pricePer1M}/MTok`} accent="#ffa502" />
              <CostCard label="Cost / day" value={`$${costPerDay.toFixed(3)}`} sub={`${switchesPerDay} switches`} />
              <CostCard label="Cost / month" value={`$${costPerMonth.toFixed(2)}`} sub="22 workdays" accent={costPerMonth > 5 ? "#ff4757" : "#22cc88"} />
            </div>

            {/* Optimization comparison */}
            {(
              <div style={{ background: "#12121f", border: "1px solid #1e1e32", borderRadius: 10, padding: 16, marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5 }}>Eager vs Tiered</div>
                  {savings > 0 && (
                    <div style={{ fontSize: 11, color: "#22cc88", fontWeight: 600 }}>
                      {savingsPct.toFixed(0)}% reduction · {savings.toLocaleString()} tokens saved
                    </div>
                  )}
                </div>
                <Bar value={unoptResult.typicalLoad} max={Math.max(unoptResult.typicalLoad, 60000)} color={optimized ? "#3a3a4e" : "#ff6b35"} label="Eager (load all)" sub={`${unoptResult.typicalLoad.toLocaleString()} tokens`} />
                <Bar value={optResult.typicalLoad} max={Math.max(unoptResult.typicalLoad, 60000)} color={optimized ? "#22cc88" : "#3a3a4e"} label="Tiered (task-matched)" sub={`${optResult.typicalLoad.toLocaleString()} tokens`} />
              </div>
            )}

            {/* Context gauges */}
            <div style={{ background: "#12121f", border: "1px solid #1e1e32", borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 8 }}>Context Window Utilization</div>
              <div style={{ display: "flex", justifyContent: "center", gap: 16, flexWrap: "wrap" }}>
                {clis.map(cli => (
                  <Gauge key={cli} value={tokens} max={CONTEXT_WINDOWS[cli]} label={cli.toUpperCase()} color="#00d2ff" warn={10} danger={15} />
                ))}
              </div>
            </div>

            {/* Tier breakdown (when optimized) */}
            {optimized && (
              <div style={{ background: "#12121f", border: "1px solid #1e1e32", borderRadius: 10, padding: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 12 }}>Tier Breakdown</div>
                {[1, 2, 3, 0].filter(t => currentResult.tiers[t] > 0).map(t => (
                  <Bar key={t} value={currentResult.tiers[t]}
                    max={Math.max(...Object.values(currentResult.tiers), 1)}
                    color={tierColors[t]} label={tierLabels[t]}
                    sub={`${currentResult.tiers[t].toLocaleString()} tokens`} />
                ))}
              </div>
            )}

            {/* File breakdown */}
            <div style={{ background: "#12121f", border: "1px solid #1e1e32", borderRadius: 10, padding: 16 }}>
              <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 12 }}>
                File Breakdown ({breakdownEntries.length} files)
              </div>
              <div style={{ maxHeight: 320, overflowY: "auto" }}>
                {breakdownEntries.map(([name, { tokens: t, tier }]) => (
                  <div key={name} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", borderBottom: "1px solid #1a1a2e" }}>
                    {optimized && (
                      <div style={{ width: 8, height: 8, borderRadius: 4, background: tierColors[tier], flexShrink: 0 }} />
                    )}
                    <span style={{ fontSize: 11, color: "#8a8a9a", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
                    <span style={{ fontSize: 11, color: "#e8e8f0", fontWeight: 600, flexShrink: 0 }}>{t.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Warnings */}
            {(() => {
              const warnings = [];
              const ctxPct = (tokens / 200000) * 100;
              if (ctxPct > 15) warnings.push({ level: "🔴", msg: `Bootstrap consumes ${ctxPct.toFixed(1)}% of Claude/Codex context — over 15% threshold` });
              else if (ctxPct > 10) warnings.push({ level: "⚠️", msg: `Bootstrap consumes ${ctxPct.toFixed(1)}% of context — approaching 10% target` });
              if (decisions > 30 && !optimized) warnings.push({ level: "🔴", msg: `${decisions} decisions without rotation — ${(decisions * 150).toLocaleString()} tokens growing unbounded` });
              if (skills > 5 && !optimized) warnings.push({ level: "⚠️", msg: `${skills} skills loaded eagerly — consider tiered bootstrap with MANIFEST.md` });
              if (clis.length === 1 && decisions > 0) warnings.push({ level: "💡", msg: `DECISIONS.md not needed in single-CLI mode` });
              if (warnings.length === 0) warnings.push({ level: "✅", msg: "All metrics within healthy bounds" });
              return (
                <div style={{ marginTop: 16, background: "#12121f", border: "1px solid #1e1e32", borderRadius: 10, padding: 16 }}>
                  <div style={{ fontSize: 10, color: "#5a5a6a", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 10 }}>Diagnostics</div>
                  {warnings.map((w, i) => (
                    <div key={i} style={{ fontSize: 11, color: "#c8c8d0", padding: "4px 0", lineHeight: 1.5 }}>
                      {w.level} {w.msg}
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        </div>
      </div>
    </div>
  );
}
