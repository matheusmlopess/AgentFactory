#!/usr/bin/env python3
"""CLI entry point for the supervisor-harness agent.

Usage:
    python run.py "install nginx and configure firewall"
    python run.py "install nginx" --dry-run
    python run.py "install nginx" --execute
"""
from __future__ import annotations

import json
import logging
import sys

import anthropic

from agent_gen.supervisor import HarnessRunner, Supervisor

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    request = sys.argv[1]
    execute = "--execute" in sys.argv
    dry_run = "--dry-run" in sys.argv

    client = anthropic.Anthropic()
    supervisor = Supervisor(client)

    print(f"\nPlanning workflow for: {request}\n")
    ctx, workflow = supervisor.plan(request)

    print(json.dumps(workflow.model_dump(), indent=2))

    if execute or dry_run:
        harness = HarnessRunner(supervisor, dry_run=dry_run)
        evidence, final_workflow = harness.run(ctx, workflow)

        print("\n--- Execution Evidence ---")
        for ev in evidence:
            status = "OK" if ev.succeeded else f"FAIL({ev.exit_code})"
            print(f"  [{status}] {ev.command}")

        if final_workflow.mode == "remediating":
            print("\n--- Remediated Workflow ---")
            print(json.dumps(final_workflow.model_dump(), indent=2))


if __name__ == "__main__":
    main()
