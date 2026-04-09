# HTML Template — Diff Visualizer
<!-- version: 1.1.0 -->

Complete HTML template used by the `diff-visualizer` skill.
Replace every `{{PLACEHOLDER}}` token before writing to `assets/`.

## Placeholders

| Token | Value |
|-------|-------|
| `{{OLD_VERSION}}` | Old git tag (e.g. `v2.0.0`) |
| `{{NEW_VERSION}}` | New git tag or `HEAD` |
| `{{GENERATED_DATE}}` | ISO date (e.g. `2026-04-04`) |
| `{{OLD_DIAGRAM}}` | Complete Mermaid flowchart text for OLD state |
| `{{NEW_DIAGRAM}}` | Complete Mermaid flowchart text for NEW state |
| `{{OLD_SKILL_COUNT}}` | Integer |
| `{{NEW_SKILL_COUNT}}` | Integer |
| `{{OLD_STEP_COUNT}}` | Integer or `—` |
| `{{NEW_STEP_COUNT}}` | Integer or `—` |
| `{{CHANGED_FILES_COUNT}}` | Integer |
| `{{NEW_COUNT}}` | Integer |
| `{{MODIFIED_COUNT}}` | Integer |
| `{{REMOVED_COUNT}}` | Integer |
| `{{UNCHANGED_COUNT}}` | Integer |
| `{{CHANGE_TABLE}}` | Pre-built `<tr>` rows (see SKILL.md Step 5) |

---

## Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>specbuilder-agent — diff {{OLD_VERSION}} → {{NEW_VERSION}}</title>

  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />

  <script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.0/mermaid.min.js"
          integrity="sha512-+n8w4I7jRKKrqdljETlOVzCNE7yZTG+LrXhHvP/LV6BXCL2h18Y5v73O3BVFR0cYHqTFvLHYDmFWn1K6lFtg=="
          crossorigin="anonymous" referrerpolicy="no-referrer"></script>

  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:           #0a0b0f;
      --surface:      #111318;
      --surface-2:    #1a1d24;
      --border:       #1f2430;
      --border-2:     #2a303e;
      --text:         #e2e8f0;
      --text-muted:   #64748b;
      --text-dim:     #94a3b8;

      --new:          #22c55e;
      --new-bg:       #052e16;
      --new-text:     #dcfce7;

      --modified:     #f59e0b;
      --modified-bg:  #1c1507;
      --modified-text:#fef3c7;

      --kept:         #60a5fa;
      --kept-bg:      #0c1a2e;
      --kept-text:    #dbeafe;

      --removed:      #f87171;
      --removed-bg:   #1c0707;
      --removed-text: #fee2e2;

      --font-body:    'Plus Jakarta Sans', system-ui, sans-serif;
      --font-mono:    'JetBrains Mono', 'Fira Code', monospace;
      --radius:       10px;
      --radius-sm:    6px;
    }

    html { font-size: 16px; }

    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: var(--font-body);
      line-height: 1.6;
      min-height: 100vh;
      overflow-x: hidden;
      position: relative;
    }

    body::before {
      content: '';
      position: fixed;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      opacity: 0.03;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)'/%3E%3C/svg%3E");
      background-repeat: repeat;
      background-size: 300px 300px;
    }

    .page-wrapper { position: relative; z-index: 1; }

    /* ── Header ──────────────────────────────────────────────── */
    .header {
      padding: 2.5rem 2rem 1.5rem;
      border-bottom: 1px solid var(--border);
      max-width: 1400px;
      margin: 0 auto;
    }

    .header-eyebrow {
      font-size: 0.7rem;
      font-family: var(--font-mono);
      color: var(--text-muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 0.4rem;
    }

    .header-heading {
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      line-height: 1.2;
    }

    .v-old  { color: var(--kept); }
    .v-new  { color: var(--new); }
    .v-arr  { color: var(--text-muted); margin: 0 0.3em; }

    .header-meta {
      font-size: 0.75rem;
      font-family: var(--font-mono);
      color: var(--text-muted);
      margin-top: 0.5rem;
    }

    /* ── Pill row ────────────────────────────────────────────── */
    .pills {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      padding: 1.25rem 2rem;
      max-width: 1400px;
      margin: 0 auto;
      border-bottom: 1px solid var(--border);
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.28rem 0.75rem;
      border-radius: 999px;
      font-size: 0.76rem;
      font-weight: 600;
      font-family: var(--font-mono);
      border: 1px solid transparent;
    }

    .pill-new      { background: var(--new-bg);      color: var(--new-text);      border-color: var(--new); }
    .pill-modified { background: var(--modified-bg); color: var(--modified-text); border-color: var(--modified); }
    .pill-removed  { background: var(--removed-bg);  color: var(--removed-text);  border-color: var(--removed); }
    .pill-kept     { background: var(--kept-bg);     color: var(--kept-text);     border-color: var(--kept); }
    .pill-neutral  { background: var(--surface-2);   color: var(--text-dim);      border-color: var(--border-2); }

    .dot {
      width: 7px; height: 7px;
      border-radius: 50%; flex-shrink: 0;
    }
    .dot-new      { background: var(--new); }
    .dot-modified { background: var(--modified); }
    .dot-removed  { background: var(--removed); }
    .dot-kept     { background: var(--kept); }

    /* ── View toggle ─────────────────────────────────────────── */
    .toggle-bar {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 0.4rem;
      padding: 1rem 2rem 0;
      max-width: 1400px;
      margin: 0 auto;
    }

    .toggle-label {
      font-size: 0.72rem;
      font-family: var(--font-mono);
      color: var(--text-muted);
      margin-right: 0.3rem;
    }

    .toggle-btn {
      background: var(--surface);
      border: 1px solid var(--border-2);
      color: var(--text-muted);
      font-family: var(--font-mono);
      font-size: 0.72rem;
      padding: 0.28rem 0.7rem;
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: all 0.15s;
    }

    .toggle-btn:hover { border-color: var(--kept); color: var(--kept-text); }
    .toggle-btn.active { background: var(--kept-bg); border-color: var(--kept); color: var(--kept-text); }

    /* ── Panels ──────────────────────────────────────────────── */
    .main {
      max-width: 1400px;
      margin: 0 auto;
      padding: 1.5rem 2rem 3rem;
    }

    .panels {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.25rem;
    }

    .panels.new-only { grid-template-columns: 1fr; }
    .panels.new-only .panel-old { display: none; }

    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .panel-header {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .panel-eyebrow {
      font-size: 0.65rem;
      font-family: var(--font-mono);
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .eyebrow-old { color: var(--kept); }
    .eyebrow-new { color: var(--new); }

    .panel-version {
      font-size: 1.1rem;
      font-weight: 700;
      font-family: var(--font-mono);
    }

    .pv-old { color: var(--kept); }
    .pv-new { color: var(--new); }

    /* ── Stats row ───────────────────────────────────────────── */
    .stats {
      display: flex;
      border-bottom: 1px solid var(--border);
    }

    .stat {
      flex: 1;
      padding: 0.7rem 1rem;
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      gap: 0.1rem;
    }

    .stat:last-child { border-right: none; }

    .stat-label {
      font-size: 0.62rem;
      font-family: var(--font-mono);
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.07em;
    }

    .stat-value {
      font-size: 1.15rem;
      font-weight: 700;
      font-family: var(--font-mono);
      color: var(--text);
    }

    /* ── Diagram area ────────────────────────────────────────── */
    .diagram-wrap {
      padding: 1.5rem 1.25rem;
      flex: 1;
      min-height: 280px;
      overflow-x: auto;
    }

    .diagram-wrap .mermaid { display: block; width: 100%; }
    .diagram-wrap .mermaid svg { max-width: 100%; height: auto; }

    /* ── Legend ──────────────────────────────────────────────── */
    .legend {
      margin-top: 1.5rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.25rem;
    }

    .section-label {
      font-size: 0.65rem;
      font-family: var(--font-mono);
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.09em;
      margin-bottom: 0.85rem;
    }

    .legend-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 0.7rem;
    }

    .legend-item {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      padding: 0.55rem 0.9rem;
      border-radius: var(--radius-sm);
      border-left: 3px solid transparent;
      flex: 1 1 180px;
    }

    .li-new      { border-left-color: var(--new);      background: color-mix(in srgb, var(--new-bg) 70%, var(--surface-2)); }
    .li-modified { border-left-color: var(--modified); background: color-mix(in srgb, var(--modified-bg) 70%, var(--surface-2)); }
    .li-kept     { border-left-color: var(--kept);     background: color-mix(in srgb, var(--kept-bg) 70%, var(--surface-2)); }
    .li-removed  { border-left-color: var(--removed);  background: color-mix(in srgb, var(--removed-bg) 70%, var(--surface-2)); }

    .li-tag {
      font-size: 0.72rem;
      font-weight: 700;
      font-family: var(--font-mono);
      letter-spacing: 0.04em;
    }

    .li-new      .li-tag { color: var(--new-text); }
    .li-modified .li-tag { color: var(--modified-text); }
    .li-kept     .li-tag { color: var(--kept-text); }
    .li-removed  .li-tag { color: var(--removed-text); }

    .li-desc { font-size: 0.7rem; color: var(--text-muted); }

    /* ── Change table ────────────────────────────────────────── */
    .table-section {
      margin-top: 1.5rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
    }

    .table-section-header {
      padding: 0.9rem 1.25rem;
      border-bottom: 1px solid var(--border);
      font-size: 0.65rem;
      font-family: var(--font-mono);
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.09em;
    }

    .change-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.82rem;
    }

    .change-table thead th {
      padding: 0.6rem 1.25rem;
      text-align: left;
      font-size: 0.65rem;
      font-family: var(--font-mono);
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border-bottom: 1px solid var(--border);
      background: var(--surface-2);
    }

    .change-table tbody tr {
      border-bottom: 1px solid var(--border);
      transition: background 0.1s;
    }

    .change-table tbody tr:last-child { border-bottom: none; }
    .change-table tbody tr:hover { background: var(--surface-2); }

    .change-table td { padding: 0.6rem 1.25rem; vertical-align: middle; }

    .table-skill   { font-family: var(--font-mono); font-weight: 500; color: var(--text); }
    .table-version { font-family: var(--font-mono); font-size: 0.76rem; color: var(--text-dim); }
    .table-notes   { font-size: 0.76rem; color: var(--text-muted); }
    .na            { color: var(--text-muted); font-family: var(--font-mono); }

    .badge {
      display: inline-block;
      padding: 0.18rem 0.55rem;
      border-radius: 999px;
      font-size: 0.65rem;
      font-weight: 700;
      font-family: var(--font-mono);
      letter-spacing: 0.04em;
      text-transform: uppercase;
      border: 1px solid transparent;
    }

    .badge-new       { background: var(--new-bg);      color: var(--new-text);      border-color: var(--new); }
    .badge-modified  { background: var(--modified-bg); color: var(--modified-text); border-color: var(--modified); }
    .badge-removed   { background: var(--removed-bg);  color: var(--removed-text);  border-color: var(--removed); }
    .badge-unchanged { background: var(--kept-bg);     color: var(--kept-text);     border-color: var(--kept); }

    /* ── Footer ──────────────────────────────────────────────── */
    .footer {
      border-top: 1px solid var(--border);
      padding: 1.25rem 2rem;
      max-width: 1400px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .footer-l, .footer-r {
      font-size: 0.7rem;
      font-family: var(--font-mono);
      color: var(--text-muted);
    }

    .footer-l strong, .footer-r strong { color: var(--text-dim); }

    /* ── Responsive ──────────────────────────────────────────── */
    @media (max-width: 900px) {
      .panels { grid-template-columns: 1fr; }
      .header-heading { font-size: 1.5rem; }
    }

    @media (max-width: 600px) {
      .header, .pills, .toggle-bar, .main, .footer { padding-left: 1rem; padding-right: 1rem; }
      .stats { flex-direction: column; }
      .stat { border-right: none; border-bottom: 1px solid var(--border); }
      .stat:last-child { border-bottom: none; }
    }
  </style>
</head>

<body>
<div class="page-wrapper">

  <!-- Header -->
  <header class="header">
    <div class="header-eyebrow">specbuilder-agent &mdash; diff report</div>
    <h1 class="header-heading">
      <span class="v-old">{{OLD_VERSION}}</span>
      <span class="v-arr">→</span>
      <span class="v-new">{{NEW_VERSION}}</span>
    </h1>
    <div class="header-meta">Generated {{GENERATED_DATE}} &nbsp;·&nbsp; diff-visualizer v1.0.0</div>
  </header>

  <!-- Summary pills -->
  <div class="pills">
    <span class="pill pill-new"><span class="dot dot-new"></span>{{NEW_COUNT}} new</span>
    <span class="pill pill-modified"><span class="dot dot-modified"></span>{{MODIFIED_COUNT}} modified</span>
    <span class="pill pill-removed"><span class="dot dot-removed"></span>{{REMOVED_COUNT}} removed</span>
    <span class="pill pill-kept"><span class="dot dot-kept"></span>{{UNCHANGED_COUNT}} unchanged</span>
    <span class="pill pill-neutral">{{CHANGED_FILES_COUNT}} files changed</span>
  </div>

  <!-- View toggle -->
  <div class="toggle-bar">
    <span class="toggle-label">View:</span>
    <button class="toggle-btn active" id="btn-both" onclick="setView('both')">Side by Side</button>
    <button class="toggle-btn" id="btn-new" onclick="setView('new')">New Only</button>
  </div>

  <!-- Panels -->
  <main class="main">
    <div class="panels" id="panels">

      <!-- OLD panel -->
      <div class="panel panel-old">
        <div class="panel-header">
          <div>
            <div class="panel-eyebrow eyebrow-old">Before</div>
            <div class="panel-version pv-old">{{OLD_VERSION}}</div>
          </div>
        </div>
        <div class="stats">
          <div class="stat">
            <span class="stat-label">Skills</span>
            <span class="stat-value">{{OLD_SKILL_COUNT}}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Pipeline Steps</span>
            <span class="stat-value">{{OLD_STEP_COUNT}}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Tag</span>
            <span class="stat-value" style="font-size:0.8rem;">{{OLD_VERSION}}</span>
          </div>
        </div>
        <div class="diagram-wrap">
          <pre class="mermaid">
{{OLD_DIAGRAM}}
          </pre>
        </div>
      </div>

      <!-- NEW panel -->
      <div class="panel panel-new">
        <div class="panel-header">
          <div>
            <div class="panel-eyebrow eyebrow-new">After</div>
            <div class="panel-version pv-new">{{NEW_VERSION}}</div>
          </div>
        </div>
        <div class="stats">
          <div class="stat">
            <span class="stat-label">Skills</span>
            <span class="stat-value">{{NEW_SKILL_COUNT}}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Pipeline Steps</span>
            <span class="stat-value">{{NEW_STEP_COUNT}}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Tag</span>
            <span class="stat-value" style="font-size:0.8rem;">{{NEW_VERSION}}</span>
          </div>
        </div>
        <div class="diagram-wrap">
          <pre class="mermaid">
{{NEW_DIAGRAM}}
          </pre>
        </div>
      </div>

    </div><!-- /.panels -->

    <!-- Legend -->
    <div class="legend">
      <div class="section-label">Node color legend</div>
      <div class="legend-grid">
        <div class="legend-item li-new">
          <span class="li-tag">NEW</span>
          <span class="li-desc">Skill added since {{OLD_VERSION}}</span>
        </div>
        <div class="legend-item li-modified">
          <span class="li-tag">MODIFIED</span>
          <span class="li-desc">SKILL.md changed — version bumped</span>
        </div>
        <div class="legend-item li-kept">
          <span class="li-tag">UNCHANGED</span>
          <span class="li-desc">No changes between versions</span>
        </div>
        <div class="legend-item li-removed">
          <span class="li-tag">REMOVED</span>
          <span class="li-desc">Present at {{OLD_VERSION}}, absent now</span>
        </div>
      </div>
    </div>

    <!-- Change table -->
    <div class="table-section">
      <div class="table-section-header">File-by-file change breakdown</div>
      <table class="change-table">
        <thead>
          <tr>
            <th>Skill</th>
            <th>Status</th>
            <th>Old Version</th>
            <th>New Version</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {{CHANGE_TABLE}}
        </tbody>
      </table>
    </div>

  </main>

  <!-- Footer -->
  <footer class="footer">
    <div class="footer-l">
      <strong>specbuilder-agent</strong> &nbsp;·&nbsp;
      diff <strong>{{OLD_VERSION}}</strong> → <strong>{{NEW_VERSION}}</strong>
    </div>
    <div class="footer-r">Generated <strong>{{GENERATED_DATE}}</strong> by diff-visualizer v1.0.0</div>
  </footer>

</div><!-- /.page-wrapper -->

<script>
  function setView(mode) {
    const panels = document.getElementById('panels');
    const btnBoth = document.getElementById('btn-both');
    const btnNew  = document.getElementById('btn-new');
    if (mode === 'new') {
      panels.classList.add('new-only');
      btnNew.classList.add('active');
      btnBoth.classList.remove('active');
    } else {
      panels.classList.remove('new-only');
      btnBoth.classList.add('active');
      btnNew.classList.remove('active');
    }
  }

  mermaid.initialize({
    startOnLoad: true,
    theme: 'dark',
    themeVariables: {
      background:         '#0a0b0f',
      primaryColor:       '#1e293b',
      primaryTextColor:   '#e2e8f0',
      primaryBorderColor: '#2a303e',
      lineColor:          '#475569',
      secondaryColor:     '#111318',
      tertiaryColor:      '#1a1d24',
      fontFamily:         'JetBrains Mono, monospace',
      fontSize:           '13px'
    },
    flowchart: { curve: 'basis', padding: 20, htmlLabels: false },
    securityLevel: 'loose'
  });
</script>

</body>
</html>
```
