# Issue: Enhance Librarian Intelligence Layer with AST Parsing

## Description
The current implementation of the Librarian's intelligence layer (`_analyze_dependencies`) uses basic regular expressions to detect Python imports and Markdown dependencies. While functional for simple cases, it has limitations:
1. It only detects imports at the beginning of a line.
2. it doesn't handle aliased imports (e.g., `import utils as u`).
3. it may falsely identify imports within string literals or comments (though the current regex tries to be strict).

## Proposal
Replace the regex-based Python import detection with an AST-based scanner for `.py` files.
- Use the `ast` module to traverse the parse tree and identify `Import` and `ImportFrom` nodes.
- Correctly resolve relative imports within the `scripts/` directory.

## Success Criteria
- [ ] AST parsing implemented for Python files.
- [ ] Test cases added for aliased and multiline imports.
- [ ] No regression in performance for large agent projects.
