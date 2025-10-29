# Report: Refactoring of the Prompt Composition Engine

This report details the significant refactoring of the prompt composition system as per the project plan.

## Modified Files

The following files were created or modified during this task:

- `src/promptscribe/composer.py`
- `src/promptscribe/project_template/prompts.yml`
- `src/promptscribe/project_template/master.jinja2`
- `README.md`
- `tests/conftest.py` (Note: Work on test implementation was paused by request)

## Summary of Changes

The core logic for prompt composition was completely overhauled to introduce a more flexible, powerful, and intuitive declarative system. The key achievements are detailed below.

### 1. Architectural Shift: Two Composition Modes

The primary change was the introduction of two distinct modes for prompt generation, moving away from a single, rigid Jinja2-based structure.

- **Simple Assembly Mode:** Activated by the `assembly` key in an agent's configuration. This mode builds prompts by sequentially processing a list of simple steps (`content`, `include`, `separator`, `h1`-`h6`). It is designed for straightforward, linear prompt construction without complex logic.

- **Jinja2 Template Mode:** This is now the **default mode** for any agent that does not have an `assembly` key. This design choice simplifies configuration and clearly delineates the two systems.

### 2. Enhanced Jinja2 Templating

The capabilities of the Jinja2 mode were significantly enhanced:

- **Global Template:** A global `template` can now be defined in the `settings` section of `prompts.yml`. Agents in template mode will use this global template by default unless they specify a local `template` key, allowing for easy configuration of projects with a consistent structure.

- **`read_file()` Function:** To make templates more powerful and self-sufficient, a custom `read_file()` function has been injected into the Jinja2 environment. This allows templates to directly read the content of any file using a path provided by a variable (e.g., `{{ read_file(data_source_path) }}`), eliminating the need for a hybrid assembly/template approach.

### 3. Advanced Variable System

A robust variable system was implemented:

- **Scope:** Both global variables (under the root `variables` key) and agent-specific variables are supported.
- **Overriding:** Agent-specific variables take precedence over global ones.
- **Substitution:** A recursive substitution mechanism was implemented, allowing any value in the configuration (and in included files) to reference variables using the `${VAR}` syntax.

### 4. Configuration and Documentation Updates

To support the new architecture, project documentation and templates were updated:

- **`prompts.yml` Template:** The example configuration file was completely rewritten to be more comprehensive, demonstrating all new features, including variable overrides, absolute paths, the global template fallback, and examples for both assembly and Jinja2 modes.

- **`README.md`:** The main documentation was updated to accurately describe the new architecture and provide a clear, up-to-date configuration example.
