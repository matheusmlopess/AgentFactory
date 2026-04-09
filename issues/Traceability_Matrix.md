# Traceability Matrix for Multi-CLI Agent Imports

## Problem
When importing agent packages from different CLI ecosystems (like Claude, Gemini, and Codex), each tool has unique configuration file structures (e.g., `settings.json`, `.cursorrules`). To prevent data loss or structural corruption, we must trace how these files map to the AgentFactory standard.

## Objective
Create a Traceability Matrix and parsing logic to handle directory and configuration file mapping. If imported agent packages contain `settings.json` or equivalent context configurations, the system must know how to append or map these correctly into the AgentFactory standard without losing context.

## Requirements
- Define a Traceability Matrix for known CLIs (Claude, Gemini, Codex, etc.).
- Implement logic in the Librarian to handle `settings.json` appends or merges when packages are imported or retrofitted.
- Ensure the resulting structure adheres to the 5-Directory Standard.
