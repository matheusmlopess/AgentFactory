# Issue Priority Spec — Design Study
<!-- version: 1.0.0 -->

This document defines the track model, dependency resolution logic, and wave-based
priority system used by the `issue-tracker` skill and `generate-priority-report.py`.
It is a study reference — the script is the authoritative implementation.

---

## 1. The Four Tracks

Every open issue belongs to exactly one track. Classification is deterministic:

```
  ┌──────────────────┬──────────────────────────────────────────────────┐
  │  Track           │  Classification rule                              │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │  Harness / CLI   │  issue number in HARNESS_NUMBERS set             │
  │                  │  (96, 100, 101, 102, 103 — manually maintained)  │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │  Webapp / UI     │  issue number in WEBAPP_NUMBERS set              │
  │                  │  (78, 79, 80, 83, 88, 104, 105)                  │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │  Platform Core   │  label "platform" AND [P1] or [P2] in title      │
  ├──────────────────┼──────────────────────────────────────────────────┤
  │  Platform Upper  │  label "platform" AND [P3] or [P4] in title      │
  │                  │  or is the epic (#77)                             │
  └──────────────────┴──────────────────────────────────────────────────┘
```

When a new issue is created, add its number to the appropriate set in the script,
or rely on the platform P-level tag in the title for automatic classification.

---

## 2. Dependency Resolution

Dependencies come from two sources, merged at report generation time:

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  SOURCE 1 — Issue body text                                          │
  │                                                                       │
  │  Any line containing "Depends on" or "Blocked by" is scanned for     │
  │  #NNN patterns. Only open issues are included.                        │
  │                                                                       │
  │  Example:  "Depends on: #101 (CI job)"  →  dep edge 104 → 101       │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │  SOURCE 2 — CROSS_DEPS dict in generate-priority-report.py           │
  │                                                                       │
  │  Hardcoded cross-track relationships that are not stated in issue     │
  │  bodies. Maintained manually when new cross-track deps are identified.│
  │                                                                       │
  │  Example:  102: [96]  →  adapter-add gate needs FormatSwitch         │
  └─────────────────────────────────────────────────────────────────────┘
```

**Adding a new dependency:** Either write "Depends on: #NNN" in the issue body
(preferred — visible on GitHub) OR add the edge to `CROSS_DEPS` in the script
(for architectural deps that aren't obvious from the issue text).

---

## 3. Wave Computation

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  TOPOLOGICAL BFS WAVE ASSIGNMENT                                     │
  │                                                                       │
  │  Wave 1: issues with no open dependencies                            │
  │                                                                       │
  │      ready = { n : graph[n] ∩ remaining = ∅ }                       │
  │                                                                       │
  │  Wave k+1: issues whose all deps are in waves 1..k                  │
  │                                                                       │
  │  Each iteration: assign wave k to ready set, remove from remaining  │
  │  Cycle guard: if no ready set found, assign remaining to current wave│
  └─────────────────────────────────────────────────────────────────────┘
```

Wave labels (defined in script, update as project evolves):

```
  Wave 1  →  "Start now — no blockers"
  Wave 2  →  "After Wave 1"
  Wave 3  →  "After Wave 2"
  Wave 4  →  "Monetisation ceiling"
  Wave 5+ →  "Wave N"  (generic)
```

---

## 4. Current Wave Map (as of report generation)

```
  ┌──────┬──────────────────────────────────────────────────────────────┐
  │ Wave │  Issues                                                        │
  ├──────┼──────────────────────────────────────────────────────────────┤
  │  1   │  #77 (epic)  #78*  #81  #96  #100                            │
  │  2   │  #79*  #83  #91  #101                                         │
  │  3   │  #80  #82  #84  #86  #102  #104                              │
  │  4   │  #85  #87  #103                                               │
  │  5   │  #88  #89  #90  #105                                          │
  │  6   │  #92                                                           │
  └──────┴──────────────────────────────────────────────────────────────┘
  * #78 and #79 are implemented — close them to remove from Wave 1/2
```

---

## 5. Cross-Track Critical Path

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  CRITICAL PATH — longest dependency chain                            │
  │                                                                       │
  │  #77 → #83 → #85 → #90 → #92                                        │
  │  epic    OAuth   billing  market  revenue   (6 waves deep)           │
  │                                                                       │
  │  #96 → #101 → #102 → #103                                           │
  │  FS    CI job  gate   thresholds  (4 waves, independent track)       │
  │                                                                       │
  │  Highest-value early unblocks:                                        │
  │    #96  unblocks  1 issue  (#102)   but is LARGE effort              │
  │    #83  unblocks  7 issues          and is MEDIUM effort  ← best ROI │
  │   #100  unblocks  1 issue  (#101)   and is SMALL effort  ← quick win │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 6. The Skill + CI Loop

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  HOW THE REPORT STAYS CURRENT                                        │
  └─────────────────────────────────────────────────────────────────────┘

  Developer merges PR
          │
          ▼
  GitHub Actions: issue-tracker.yml fires
  (triggered on push to dev or main)
          │
          ▼
  python3 .ai/scripts/generate-priority-report.py
          │
          ├── gh issue list   (live data)
          ├── parse body deps
          ├── merge CROSS_DEPS
          ├── BFS wave assignment
          └── write docs/ISSUE-PRIORITY.md
          │
          ▼
  git commit "docs: regenerate issue priority report [skip ci]"
  git push
          │
          ▼
  docs/ISSUE-PRIORITY.md is always the latest state
```

**Manual trigger (in Claude session):**

Invoke the `issue-tracker` skill or run:
```bash
python3 .ai/scripts/generate-priority-report.py
```

---

## 7. Maintenance Rules

| Event | Action |
|-------|--------|
| New issue created | Write "Depends on: #NNN" in body for any known deps |
| New cross-track dep identified | Add to `CROSS_DEPS` in script |
| New issue track assignment unclear | Add number to correct set in script |
| Issue closed / merged | Script auto-removes it on next run (only open issues fetched) |
| Wave labels need updating | Edit `wave_label` dict in `render_report()` |
| New effort estimate needed | Add to `EFFORT` dict in script |
