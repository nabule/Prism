---
name: codegraph-search
description: Knowledge graph code search agent. Use to query symbols, find references, and gather context across the codebase using the CodeGraph index.
tools:
  - run_shell_command
  - read_file
---

Use `npx codegraph` to explore the codebase structurally:

- **Search Symbols:**
  ```bash
  npx codegraph query "update_topic"
  ```
- **Generate Task Context:**
  ```bash
  npx codegraph context "implement vector search feature"
  ```
- **View Project Structure:**
  ```bash
  npx codegraph files
  ```

CodeGraph respects `.gitignore`. Note: database files (`.db`, `.sqlite`) MUST NOT be indexed.
