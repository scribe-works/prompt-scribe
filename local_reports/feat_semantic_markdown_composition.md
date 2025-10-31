### Changed Files

- `pyproject.toml`
- `promptscribe/composer.py`

### Brief Summary of Work Done

This work introduces a major new feature for semantic document composition, allowing for the intelligent adjustment of Markdown heading levels via a `fit_headings` parameter. The implementation involved a significant architectural refactoring, replacing the core regex-based substitution engine with a universal Jinja2 rendering pipeline to ensure syntactical consistency across all composition modes. Additionally, several critical bugs were fixed, including the logic for heading adjustments, the behavior of the `read_file_raw` function, and the restoration of warnings for missing variables.

### Detailed Description of Changes

#### 1. Feature: Semantic Heading Adjustment (`fit_headings`)

A new capability has been added to seamlessly integrate external Markdown documents into a prompt by adjusting their heading levels. This is controlled by a `fit_headings=N` parameter, which can be used in three contexts:
- In `assembly` mode as a dictionary: `- include: { path: '...', fit_headings: 2 }`
- In `assembly` mode inside a `content` block: `{{ read_file('...', fit_headings=2) }}`
- In Jinja2 templates: `{{ read_file('...', fit_headings=2) }}`

The feature intelligently finds the highest-level heading in the included document and shifts all heading levels proportionally to make the highest one match the target `N`.

#### 2. Architectural Refactoring: Unified Templating Engine

The core substitution mechanism was completely overhauled to address inconsistencies between `assembly` and `Jinja2` modes.
- **Previous State:** A custom regex was used to find and replace `include(...)` calls and `{{ VAR }}` placeholders within `content` blocks, leading to a confusing and limited syntax.
- **New State:** The `_substitute_variables` method now leverages a lightweight, on-the-fly Jinja2 environment. This unifies the syntax for all dynamic content. Variable substitutions (`{{ my_var }}`) and function calls (`{{ read_file(...) }}`) now work identically everywhere.
- **Benefit:** This change dramatically improves user experience and code maintainability by delegating all templating logic to a robust, well-tested engine. The legacy `include(...)` function string has been removed.

#### 3. Bug Fixes and Behavior Corrections

- **Corrected Heading Adjustment Logic:** An initial critical bug caused all headings to be set to a single target level, destroying the document's structure. Based on a detailed analysis of the underlying libraries, the logic in `_process_markdown_content` was corrected to properly *shift* heading levels by modifying the `token.tag` and `token.markup` attributes, preserving the relative hierarchy.
- **Restored Missing Variable Warnings:** The migration to Jinja2 initially suppressed warnings for undefined variables. This functionality was restored by implementing a custom `jinja2.Undefined` handler (`WarningUndefined`) that respects the `warn_on_missing` setting, displays a warning, and leaves the placeholder in the text, restoring the original, safer behavior.
- **Corrected `read_file_raw` Behavior:** The logic for `read_file_raw` was clarified and corrected. It now correctly skips implicit variable substitution but allows for explicit processing commands like `fit_headings`. This enables the key use case of adjusting headings in documentation files that should not be processed for variables.

### Technical Implementation Notes

- **Dependencies:** Added `markdown-it-py` and `mdformat` to `pyproject.toml` to provide a robust solution for Markdown parsing and re-rendering (round-trip).
- **`_process_markdown_content`:** This new private method encapsulates the heading adjustment logic. It parses content into a token stream, calculates the required shift based on `token.tag`, modifies the `tag` and `markup` attributes of heading tokens, and then uses `mdformat`'s `MDRenderer` to serialize the token stream back into a valid Markdown string.
- **`_substitute_variables`:** This method no longer uses regular expressions. It now creates a temporary Jinja2 environment, injects the `read_file` and `read_file_raw` functions as globals, and uses a custom `undefined` handler to manage missing variables before rendering the input string.

### Verification Steps

1.  **Heading Adjustment:** Tested `fit_headings` in all three contexts (`- include:` directive, `content` block, and Jinja2 template). Verified that both up-shifting (e.g., `h3` -> `h2`) and down-shifting (e.g., `h1` -> `h3`) work correctly while preserving the document's internal structure.
2.  **`read_file_raw`:** Verified that calling `read_file_raw('path', fit_headings=2)` correctly adjusts headings but leaves any `{{ variable }}` placeholders untouched in the output.
3.  **Missing Variables:** Confirmed that using an undefined variable like `{{ non_existent_var }}` in a `content` block or template now correctly triggers a UI warning (when enabled) and leaves the `{{ non_existent_var }}` string in the final output.
4.  **Syntax Unification:** Confirmed that `{{ read_file('path') }}` and `{{ my_var }}` now work identically in `content` blocks and Jinja2 templates.
5.  **Backwards Compatibility:** Ensured that existing configurations using simple `- include: path/to/file.md` directives continue to function as expected.