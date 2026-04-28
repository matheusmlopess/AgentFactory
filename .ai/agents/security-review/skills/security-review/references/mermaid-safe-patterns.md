<!-- version: 1.0.0 -->
# GitHub-Safe Mermaid Patterns <!-- version: 1.0.0 -->

Hard-won constraints from real GitHub rendering failures. Violating any of these produces a silent parse error on GitHub — the diagram renders as a broken code block.

---

## graph TB / flowchart TD

| Rule | Bad | Good |
|------|-----|------|
| Always quote node labels | `A[foo(bar)]` | `A["foo bar"]` |
| No `(` `)` in unquoted labels | `A[fn()]` | `A["fn call"]` |
| No `<` or `>` unquoted | `A{ESC [ <}` | `A{"ESC bracket"}` |
| No single quotes inside labels | `A['data' event]` | `A["data event"]` |
| No `direction TB` inside subgraph | `subgraph X\n  direction TB` | omit `direction TB` |
| Subgraph label must use `"quotes"` | `subgraph X["Foo (bar)"]` | `subgraph X["Foo bar"]` |
| No `/` in node IDs | `TOOLS[tools/index.ts]` | `TOOLS["ToolRegistry"]` |
| Use `<br/>` not `\n` in quoted labels | `A["foo\nbar"]` | `A["foo<br/>bar"]` |
| Unquoted `\n` IS valid in node labels | `A[foo\nbar]` | valid |

---

## sequenceDiagram

| Rule | Bad | Good |
|------|-----|------|
| No `()` in participant alias | `participant LOOP as agentLoop()` | `participant LOOP as agentLoop` |
| No `/` in participant alias | `participant T as tools/index.ts` | `participant T as ToolRegistry` |
| No spaces in participant alias used as ID | `participant API as Anthropic API` | `participant API as AnthropicAPI` |
| No `<` in loop/alt/opt label | `loop while turns < max` | `loop while turns lt max` |
| No `{` `}` in Note text | `Note over X: state = {kind: 'idle'}` | `Note over X: state kind is idle` |
| No `[` `]` in Note text | `Note over X: arr[0]` | `Note over X: first element` |
| Keep Note text simple prose | complex expressions | plain English description |
| `alt`/`else` labels must be simple | `alt stop === 'end_turn'` | `alt stopReason is end_turn` |

---

## stateDiagram-v2

| Rule | Bad | Good |
|------|-----|------|
| No duplicate `note right of <state>` | two `note right of idle` blocks | second note uses `note left of idle` |
| No `\n` in transition labels | `A --> B : press\nHIT header` | `A --> B : press on header row` |
| No `{` `}` in note text | `drag = {kind: 'idle'}` | `drag kind is idle` |
| No `'` in note text | `kind: 'idle'` | `kind idle` |
| No `*` in note text | `row = round(x / 2) * 2` | `row snapped to even number` |

---

## gantt

| Rule | Bad | Good |
|------|-----|------|
| Section titles: use `-` not `—` | `section Wave 0 — Scaffold` | `section Wave 0 - Scaffold` |
| Task names: no special chars | `/plan wizard` | `plan wizard` |
| Task names: no dots | `v0.3.0` | `v0-3-0` or `release 0.3.0` |

---

## General Rules

1. **Test locally before committing** — paste the diagram into [mermaid.live](https://mermaid.live) to verify before pushing to GitHub.
2. **Prefer `""` for everything** — when in doubt, wrap any label, note, or ID in double quotes.
3. **Avoid Unicode in identifiers** — emoji in node labels usually render, but can break parsers; prefer text alternatives in IDs.
4. **Keep diagrams small** — GitHub renders up to ~50 nodes cleanly; beyond that, split into sub-diagrams.
5. **No HTML tags inside labels** — `<br/>` works inside quoted labels for line breaks, but `<b>` or `<i>` do not.
