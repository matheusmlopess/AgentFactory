# <Feature Name>
<!-- version: 1.0.0 -->

Issue: #NNN · Phase N of <epic or context>

One-sentence description of what this feature is and what it enables.

---

## 1. Overview

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  PURPOSE                                                               │
  │                                                                        │
  │  <What problem does this solve?>                                      │
  │                                                                        │
  │  What it unlocks:                                                      │
  │    · <downstream feature or issue>   (#NNN)                           │
  │    · <downstream feature or issue>   (#NNN)                           │
  └──────────────────────────────────────────────────────────────────────┘
```

<2–3 sentences expanding on the problem and the chosen solution.>

---

## 2. Architecture

### 2.1 File layout

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  FILE LAYOUT                                                           │
  └──────────────────────────────────────────────────────────────────────┘

  path/to/types.ts           ← type definitions
  path/to/main-module.ts     ← core logic
  path/to/component.tsx      ← UI component (if applicable)
  path/to/config.json        ← configuration (if applicable)
```

### 2.2 Component / module hierarchy

```
  <ParentModule>
    └─ <ChildModule>          ← owns <what state / responsibility>
         └─ <LeafModule>      ← reads <what hook / prop>
```

### 2.3 Data flow

```
  <Trigger / entry point>
       │
       ▼
  <Step 1>
       │
       ├─ <condition A>
       │     │
       │     ▼
       │  <outcome A>
       │
       └─ <condition B>
             │
             ▼
          <outcome B>
```

---

## 3. Configuration

### 3.1 Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VAR_NAME` | Yes/No | `value` | What it controls |

### 3.2 Config files

```
  path/to/config.json         ← what it configures
```

```jsonc
{
  "key": "value"   // annotation
}
```

---

## 4. How It Works

### 4.1 <Main flow name>

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  <FLOW TITLE>                                                          │
  └──────────────────────────────────────────────────────────────────────┘

  <Actor/Component>           <Other Actor>           <External System>
       │                           │                         │
       │── <action> ─────────────►│                         │
       │                           │── <action> ────────────►│
       │                           │◄── <response> ──────────│
       │◄── <response> ────────────│                         │
```

### 4.2 <Secondary flow or edge case>

<prose explanation of a secondary behaviour, edge case, or algorithm>

---

## 5. Usage Examples

### 5.1 <Common use case>

```bash
# <What this command does>
<command here>
```

### 5.2 <Code example / integration>

```tsx
// <Context for this snippet>
import { useSomething } from "../context/SomeContext";

export function Example() {
  const { value } = useSomething();
  return <div>{value}</div>;
}
```

---

## 6. Integration Points

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  INTEGRATION MAP                                                       │
  └──────────────────────────────────────────────────────────────────────┘

  Called by:
    <module / workflow>  ──►  this feature
    <CI job>             ──►  this feature

  Calls:
    this feature  ──►  <external API / module>
    this feature  ──►  <config file / script>

  Output:
    <artifact path or side-effect>
```

---

## 7. Troubleshooting

```
  ┌──────────────────────────────────────┬───────────────────────────────┐
  │  Symptom                              │  Fix                           │
  ├──────────────────────────────────────┼───────────────────────────────┤
  │  <symptom>                            │  <fix>                         │
  ├──────────────────────────────────────┼───────────────────────────────┤
  │  <symptom>                            │  <fix>                         │
  └──────────────────────────────────────┴───────────────────────────────┘
```
