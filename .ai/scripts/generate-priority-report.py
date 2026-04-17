#!/usr/bin/env python3
# generate-priority-report.py — Issue Priority & Dependency Report Generator
# <!-- version: 1.0.0 -->
#
# Fetches all open GitHub issues, categorises them into tracks,
# resolves a full dependency graph, computes priority waves, and
# writes docs/ISSUE-PRIORITY.md as a living document.
#
# Usage:
#   python3 .ai/scripts/generate-priority-report.py [--dry-run] [--repo owner/repo]
#
# Requires: gh CLI (authenticated)

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "ISSUE-PRIORITY.md"

DRY_RUN = "--dry-run" in sys.argv
REPO_FLAG = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--repo"), None)

# ---------------------------------------------------------------------------
# Cross-track dependencies not stored in issue bodies
# ---------------------------------------------------------------------------
CROSS_DEPS: dict[int, list[int]] = {
    82:  [83],            # CLI publish/import needs OAuth
    84:  [83],            # RBAC needs OAuth
    85:  [83],            # billing needs OAuth
    86:  [83],            # login/logout needs OAuth
    87:  [81, 84],        # audit history needs registry + RBAC
    88:  [80],            # dep graph needs manifest inspector
    89:  [84, 85],        # enterprise compliance needs RBAC + billing
    90:  [81, 85],        # marketplace needs registry + billing
    91:  [81],            # verified agent badge needs registry
    92:  [89, 90],        # revenue share needs marketplace + compliance
    102: [96],            # adapter-add gate needs FormatSwitch
    103: [102],           # per-adapter thresholds needs gate (already in body)
    104: [101],           # webapp viewer needs CI job (already in body)
    105: [83, 85, 104],   # BYOK pro needs auth + billing + viewer
}

# Issues confirmed implemented — flag for closure
IMPLEMENTED: set[int] = {78, 79}

# Manual effort estimates
EFFORT: dict[int, str] = {
    77: "epic",   78: "medium", 79: "medium", 80: "medium",
    81: "large",  82: "medium", 83: "medium", 84: "large",
    85: "large",  86: "small",  87: "medium", 88: "medium",
    89: "medium", 90: "large",  91: "medium", 92: "large",
    96: "large",  100: "small", 101: "small", 102: "medium",
    103: "small", 104: "small", 105: "medium",
}

# ---------------------------------------------------------------------------
# Track classification
# ---------------------------------------------------------------------------
HARNESS_NUMBERS: set[int] = {96, 100, 101, 102, 103}
WEBAPP_NUMBERS:  set[int] = {78, 79, 80, 83, 88, 104, 105}

def classify_track(number: int, title: str, labels: list[str]) -> str:
    if number in HARNESS_NUMBERS:
        return "harness"
    if number in WEBAPP_NUMBERS:
        return "webapp"
    p = re.search(r"\[P(\d)\]", title)
    p_level = int(p.group(1)) if p else 0
    if "platform" in labels:
        return "platform-core" if p_level <= 2 else "platform-upper"
    return "platform-upper"

TRACK_LABEL = {
    "harness":        "Harness / CLI",
    "webapp":         "Webapp / UI",
    "platform-core":  "Platform Core",
    "platform-upper": "Platform Upper",
}

TRACK_ORDER = ["harness", "webapp", "platform-core", "platform-upper"]

# ---------------------------------------------------------------------------
# Fetch issues
# ---------------------------------------------------------------------------
def fetch_issues() -> list[dict]:
    cmd = ["gh", "issue", "list", "--state", "open", "--limit", "100",
           "--json", "number,title,labels,body"]
    if REPO_FLAG:
        cmd += ["--repo", REPO_FLAG]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error fetching issues: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)

# ---------------------------------------------------------------------------
# Parse dependencies from issue body text
# ---------------------------------------------------------------------------
def parse_body_deps(body: str | None) -> list[int]:
    if not body:
        return []
    deps: list[int] = []
    for line in body.splitlines():
        low = line.lower()
        if "depends on" in low or "blocked by" in low:
            deps += [int(n) for n in re.findall(r"#(\d+)", line)]
    return deps

# ---------------------------------------------------------------------------
# Build full dependency graph
# ---------------------------------------------------------------------------
def build_graph(issues: list[dict]) -> dict[int, set[int]]:
    open_numbers = {i["number"] for i in issues}
    graph: dict[int, set[int]] = {i["number"]: set() for i in issues}

    for issue in issues:
        n = issue["number"]
        # Body-declared deps
        for dep in parse_body_deps(issue.get("body")):
            if dep in open_numbers:
                graph[n].add(dep)
        # Cross-track hardcoded deps
        for dep in CROSS_DEPS.get(n, []):
            if dep in open_numbers:
                graph[n].add(dep)

    return graph

# ---------------------------------------------------------------------------
# Topological wave assignment (BFS from roots)
# ---------------------------------------------------------------------------
def assign_waves(graph: dict[int, set[int]]) -> dict[int, int]:
    waves: dict[int, int] = {}
    remaining = set(graph.keys())

    wave = 1
    while remaining:
        ready = {n for n in remaining if not (graph[n] & remaining)}
        if not ready:
            # cycle guard — assign remaining to last wave
            for n in remaining:
                waves[n] = wave
            break
        for n in ready:
            waves[n] = wave
        remaining -= ready
        wave += 1

    return waves

# ---------------------------------------------------------------------------
# What a wave unblocks
# ---------------------------------------------------------------------------
def compute_unblocks(graph: dict[int, set[int]], number: int) -> list[int]:
    return sorted(n for n, deps in graph.items() if number in deps)

# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def render_report(issues: list[dict]) -> str:
    label_map: dict[int, list[str]] = {
        i["number"]: [l["name"] for l in i.get("labels", [])]
        for i in issues
    }
    title_map: dict[int, str] = {i["number"]: i["title"] for i in issues}

    graph = build_graph(issues)
    waves = assign_waves(graph)

    # Group by track
    tracks: dict[str, list[int]] = {t: [] for t in TRACK_ORDER}
    for issue in issues:
        n = issue["number"]
        t = classify_track(n, issue["title"], label_map[n])
        tracks[t].append(n)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    open_count = len(issues)
    implemented_open = [n for n in IMPLEMENTED if n in {i["number"] for i in issues}]

    lines: list[str] = []

    lines += [
        "# Issue Priority Report",
        "<!-- version: 1.0.0 -->",
        f"<!-- generated: {now} -->",
        f"<!-- open-issues: {open_count} -->",
        "",
        "Living priority matrix — regenerated automatically on every merge to `dev`.",
        "Source: `.ai/scripts/generate-priority-report.py`  |  Spec: `docs/ISSUE-PRIORITY-SPEC.md`",
        "",
    ]

    # ── Ready to close ────────────────────────────────────────────────
    if implemented_open:
        lines += [
            "## ⚠ Ready to Close",
            "",
            "These issues are implemented but still open:",
            "",
        ]
        for n in implemented_open:
            lines.append(f"- **#{n}** {title_map.get(n, '')}")
        lines.append("")

    # ── Track Overview ────────────────────────────────────────────────
    lines += ["## Track Overview", ""]
    lines += [
        "```",
        "  ┌──────────────────┬───────────────────────────────────────────┐",
        "  │  Track           │  Issues                                    │",
        "  ├──────────────────┼───────────────────────────────────────────┤",
    ]
    for track in TRACK_ORDER:
        nums = sorted(tracks[track])
        nums_str = "  ".join(f"#{n}" for n in nums)
        label = TRACK_LABEL[track]
        lines.append(f"  │  {label:<16}│  {nums_str:<43}│")
    lines += [
        "  └──────────────────┴───────────────────────────────────────────┘",
        "```",
        "",
    ]

    # ── Dependency Matrix ─────────────────────────────────────────────
    lines += ["## Dependency Matrix", ""]
    lines += [
        "```",
        f"  {'#':<6}  {'Depends on':<24}  {'Unblocks':<24}  Title",
        f"  {'─'*6}  {'─'*24}  {'─'*24}  {'─'*40}",
    ]
    for issue in sorted(issues, key=lambda i: i["number"]):
        n = issue["number"]
        deps = sorted(graph[n])
        unblocks = compute_unblocks(graph, n)
        dep_str  = " ".join(f"#{d}" for d in deps)  or "—"
        unb_str  = " ".join(f"#{u}" for u in unblocks) or "—"
        title = issue["title"][:45]
        lines.append(f"  #{n:<5}  {dep_str:<24}  {unb_str:<24}  {title}")
    lines += ["```", ""]

    # ── Priority Waves ────────────────────────────────────────────────
    lines += ["## Priority Waves", ""]
    max_wave = max(waves.values()) if waves else 1
    for wave in range(1, max_wave + 1):
        wave_issues = sorted(n for n, w in waves.items() if w == wave)
        wave_label = {1: "Start now — no blockers", 2: "After Wave 1",
                      3: "After Wave 2", 4: "Monetisation ceiling"}.get(wave, f"Wave {wave}")
        lines += [
            f"### Wave {wave} — {wave_label}",
            "",
            "```",
            f"  {'#':<6}  {'Effort':<8}  {'Track':<16}  {'Unblocks':<20}  Title",
            f"  {'─'*6}  {'─'*8}  {'─'*16}  {'─'*20}  {'─'*40}",
        ]
        for n in wave_issues:
            effort   = EFFORT.get(n, "?")
            track    = classify_track(n, title_map[n], label_map[n])
            unblocks = compute_unblocks(graph, n)
            unb_str  = " ".join(f"#{u}" for u in unblocks[:4]) or "—"
            if len(unblocks) > 4:
                unb_str += " …"
            title = title_map[n][:45]
            lines.append(f"  #{n:<5}  {effort:<8}  {TRACK_LABEL[track]:<16}  {unb_str:<20}  {title}")
        lines += ["```", ""]

    # ── Cross-track callouts ──────────────────────────────────────────
    lines += [
        "## Cross-Track Dependencies",
        "",
        "Key dependencies that span tracks — these are the critical path risks:",
        "",
        "```",
        "  #96  FormatSwitch  ──────────────────────►  #102  adapter-add gate",
        "  (harness/CLI)                               (harness/CLI)",
        "",
        "  #83  GitHub OAuth  ─┬────────────────────►  #84  RBAC",
        "  (platform-core)     ├────────────────────►  #85  Pro billing",
        "                      └────────────────────►  #86  login/logout CLI",
        "",
        "  #85  Pro billing   ─┬────────────────────►  #105 BYOK live checker",
        "  (platform-core)     └────────────────────►  #90  marketplace",
        "",
        "  #101 CI job        ──────────────────────►  #104 webapp report viewer",
        "  (harness/CLI)                               (webapp/UI)",
        "```",
        "",
    ]

    # ── Footer ────────────────────────────────────────────────────────
    lines += [
        "---",
        "",
        f"_Generated {now} by `generate-priority-report.py`._",
        "_Run manually: `python3 .ai/scripts/generate-priority-report.py`_",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("Fetching open issues …")
    issues = fetch_issues()
    print(f"  Found {len(issues)} open issues")

    report = render_report(issues)

    if DRY_RUN:
        print("\n" + "─" * 70)
        print(report)
        print("─" * 70)
        print("[dry-run] No file written.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"  Written: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
