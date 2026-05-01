<!-- version: 1.0.0 -->
# Report Template — security-review skill <!-- version: 1.0.0 -->

Fill-in-the-blanks skeleton. Every `{{TOKEN}}` must be substituted before writing the final report.

---

## Output: `docs/REVIEW-SECURITY-ARCHITECTURE-{{DATE}}.md`

```markdown
<!-- version: {{REPORT_VERSION}} -->
# {{PROJECT_NAME}} — Security & Architecture Review — {{DATE}}

> {{SCOPE_LINE}}

---

## Table of Contents

1. [Component Status Matrix](#1-component-status-matrix)
2. [System Architecture Diagram](#2-system-architecture-diagram)
3. [Primary Flow Diagram](#3-primary-flow-diagram)
4. [Data Pipeline Diagram](#4-data-pipeline-diagram)
5. [Input Event Routing](#5-input-event-routing)
6. [Key State Machine](#6-key-state-machine)
7. [Dispatch Flow](#7-dispatch-flow)
8. [Roadmap](#8-roadmap)
9. [Security Gaps](#9-security-gaps)
10. [Design Gaps & Open Ends](#10-design-gaps--open-ends)
11. [Recommendations Priority List](#11-recommendations-priority-list)

---

## 1. Component Status Matrix

| # | File | Wave | Status | Working | Notes |
|---|------|------|--------|---------|-------|
{{COMPONENT_TABLE_ROWS}}

Legend: ✅ fully working · ✅⚠ working with caveats · ⚠️ partially working · ❌ not implemented

**Summary: {{IMPLEMENTED_COUNT}}/{{TOTAL_COUNT}} implemented. Of these, {{SEC_FLAG_COUNT}} have security flags, {{CAVEAT_COUNT}} have design caveats.**

---

## 2. System Architecture Diagram

```mermaid
{{ARCH_DIAGRAM}}
```

---

## 3. Primary Flow Diagram

```mermaid
{{PRIMARY_FLOW_DIAGRAM}}
```

{{PRIMARY_FLOW_NOTE}}

---

## 4. Data Pipeline Diagram

```mermaid
{{PIPELINE_DIAGRAM}}
```

{{PIPELINE_NOTE}}

---

## 5. Input Event Routing

```mermaid
{{INPUT_ROUTING_DIAGRAM}}
```

{{INPUT_ROUTING_NOTE}}

---

## 6. Key State Machine

```mermaid
{{STATE_MACHINE_DIAGRAM}}
```

{{STATE_MACHINE_NOTE}}

---

## 7. Dispatch Flow

```mermaid
{{DISPATCH_DIAGRAM}}
```

{{DISPATCH_NOTE}}

---

## 8. Roadmap

```mermaid
{{ROADMAP_DIAGRAM}}
```

---

## 9. Security Gaps

{{SEV1_FINDINGS}}

{{SEV2_FINDINGS}}

---

## 10. Design Gaps & Open Ends

{{DESIGN_GAPS}}

---

## 11. Recommendations Priority List

| Priority | Item | Effort | Wave/Sprint |
|----------|------|--------|-------------|
{{RECOMMENDATIONS_ROWS}}

---

*Review generated from full source read of {{FILE_COUNT}} files in {{PROJECT_NAME}} @ {{PROJECT_VERSION}}.*
```

---

## Token Reference

| Token | Source | Example |
|-------|--------|---------|
| `{{DATE}}` | Today's date | `2026-04-28` |
| `{{REPORT_VERSION}}` | `1.0.0` new, `1.N.0` update | `1.0.0` |
| `{{PROJECT_NAME}}` | `package.json` name or repo dir | `agentfactory-harness` |
| `{{SCOPE_LINE}}` | Summary of files scanned | `Full pass covering all 37 source files across Waves 0–2.` |
| `{{COMPONENT_TABLE_ROWS}}` | Step 1 output | `\| 1 \| src/... \| 0 \| done \| ✅ \| ... \|` |
| `{{IMPLEMENTED_COUNT}}` | Count status≠planned | `22` |
| `{{TOTAL_COUNT}}` | Total rows | `37` |
| `{{SEC_FLAG_COUNT}}` | Count with SEC in notes | `4` |
| `{{CAVEAT_COUNT}}` | Count with caveat working status | `6` |
| `{{ARCH_DIAGRAM}}` | Step 3 diagram 1 | `graph TB ...` |
| `{{PRIMARY_FLOW_DIAGRAM}}` | Step 3 diagram 2 | `sequenceDiagram ...` |
| `{{PIPELINE_DIAGRAM}}` | Step 3 diagram 3 | `flowchart TD ...` |
| `{{INPUT_ROUTING_DIAGRAM}}` | Step 3 diagram 4 | `flowchart TD ...` |
| `{{STATE_MACHINE_DIAGRAM}}` | Step 3 diagram 5 | `stateDiagram-v2 ...` |
| `{{DISPATCH_DIAGRAM}}` | Step 3 diagram 6 | `flowchart TD ...` |
| `{{ROADMAP_DIAGRAM}}` | Step 3 diagram 7 | `gantt ...` |
| `{{SEV1_FINDINGS}}` | Step 4 SEV-1 sections | `### 🔴 SEV-1 — BashTool ...` |
| `{{SEV2_FINDINGS}}` | Step 4 SEV-2 sections | `### 🟡 SEV-2 — No AbortController ...` |
| `{{DESIGN_GAPS}}` | Step 4 D-N sections | `### D-1 — Unbounded lines array ...` |
| `{{RECOMMENDATIONS_ROWS}}` | Step 5 rows | `\| 🔴 P0 \| Restrict BashTool \| 1h \| now \|` |
| `{{FILE_COUNT}}` | Total source files read | `37` |
| `{{PROJECT_VERSION}}` | From package.json/pyproject | `v0.3.0` |

---

## Finding Section Templates

### SEV-1 Section

```markdown
### 🔴 SEV-1 — {{FINDING_TITLE}}

**File:** `{{FILE_PATH}}`

```{{LANG}}
{{CODE_SNIPPET}}
```

**Attack surface:**
- {{ATTACK_BULLET_1}}
- {{ATTACK_BULLET_2}}

**Remediation:**
- {{FIX_BULLET_1}}
- {{FIX_BULLET_2}}
```

### SEV-2 Section

```markdown
### 🟡 SEV-2 — {{FINDING_TITLE}}

**File:** `{{FILE_PATH}}`

{{DESCRIPTION}}

**Remediation:**
- {{FIX_BULLET_1}}
```

### Design Gap Section

```markdown
### D-{{N}} — {{FINDING_TITLE}}

**File:** `{{FILE_PATH}}:{{LINE}}`

```{{LANG}}
{{CODE_SNIPPET}}
```

{{PROBLEM_DESCRIPTION}}

**Remediation:** {{FIX_DESCRIPTION}}
```
