# Issue: Enforce Schema Validation for `skill-manifest.json`

## Description
The Librarian's intelligence layer (`_parse_skill_manifests`) currently reads any valid JSON from a `skill-manifest.json` file and blindly injects it into the agent manifest's `skills_metadata`.

## Gap Analysis
There is no validation to ensure the parsed JSON actually conforms to a usable skill standard. If a user creates a `skill-manifest.json` missing required fields (like `name` or `description`), it will pass the Librarian's sync but fail downstream when an LLM tries to interpret the tool.

## Proposed Solution
- Define a standard schema (e.g., using `dataclasses`, `pydantic`, or standard `jsonschema`).
- Require fields like `name` and `description` (and potentially `parameters`).
- Make `agent-gen audit` flag invalid skill manifests.

## Acceptance Criteria
- [ ] Schema validation added to `_parse_skill_manifests`.
- [ ] `audit` command reports skill manifests that fail validation.
- [ ] Missing required fields prevent successful `wrap`.