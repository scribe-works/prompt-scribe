# feat: Improve variable substitution and file handling

## Changed Files:
- `src/promptscribe/composer.py`

## Brief Description of Work Done:
This task involved a significant refactoring of the `PromptComposer` class in `src/promptscribe/composer.py`. The primary goal was to enhance the flexibility and predictability of variable substitution and file inclusion mechanisms, addressing several critical issues related to `output_file` priority, recursive variable resolution, and a more intuitive approach to file embedding.

## Detailed Description of Changes:

1.  **Corrected Global `output_file` Priority Logic:**
    *   **Problem:** The system prematurely defaulted to a generated output filename, ignoring global `output_file` settings.
    *   **Solution:** The logic within `compose_agent` was refactored to establish a clear priority chain: agent-specific `output_file` > global `output_file` > default generated name. This ensures that global settings are respected when no agent-specific override is provided.

2.  **Implemented Multi-Pass Variable Substitution:**
    *   **Problem:** Variables referencing other variables (e.g., `persone: "personas/{{ _agent_name }}.md"`) were not correctly resolved because the `_agent_name` variable was added *after* the initial variable resolution pass.
    *   **Solution:** A new key step was introduced in `compose_agent` after the initial variable resolution and `_agent_name` injection. This step iterates through all resolved variables and applies `_substitute_variables` again to any string values, ensuring that all inter-variable references are fully resolved.

3.  **Refactored `_substitute_variables` for `include()` and `include_raw()` Directives:**
    *   **Problem:** The previous `file:` prefix for file inclusion was clunky and created confusion. The `include` and `include_raw` mechanisms in simple assembly mode were rigid.
    *   **Solution:** The `_substitute_variables` method was significantly enhanced. Its regular expression was updated to recognize new `include('path/to/file')` and `include_raw('path/to/file')` directives. The `replacer` function was modified to handle these directives, allowing direct file content embedding with optional recursive variable substitution (for `include()`) or raw inclusion (for `include_raw()`). This provides a more consistent and powerful way to embed file content across the system.

4.  **Simplified `_run_simple_assembly` Method:**
    *   **Problem:** The `_run_simple_assembly` method contained specific, redundant logic for handling `include` and `include_raw` steps.
    *   **Solution:** With the enhancements to `_substitute_variables`, the `_run_simple_assembly` method was simplified. It now passes all step values directly to `_substitute_variables`, leveraging the centralized and more powerful substitution mechanism. This reduces complexity and improves maintainability within the assembly logic.

## Technical Notes on Implementation:
*   All code comments were ensured to be in English, adhering to project guidelines.
*   The changes were implemented incrementally, with each logical step being applied and verified.
*   The `_agent_name` variable is now safely retrieved using `variables.get('_agent_name', '')` within the `replacer` function to prevent potential errors if it's not present.

## Verification Steps Taken:
*   Each `replace` operation was confirmed as successful by the tool.
*   The logical flow of changes was reviewed against the provided problem descriptions and proposed solutions.
*   The updated code structure aligns with the architectural principles of separation of concerns, ensuring `composer.py` remains focused on business logic without direct console output.

## Transition from `${VAR}` to `{{ VAR }}` Syntax

### Changed Files:
- `src/promptscribe/composer.py`

### Brief Description of Work Done:
This task involved transitioning the variable substitution syntax from `${VAR}` to `{{ VAR }}` to bring consistency with Jinja2 templating syntax and improve readability. The regular expression patterns and documentation were updated to reflect this change.

### Detailed Description of Changes:

1. **Updated Regular Expression Pattern:**
   * **Problem:** The system was using `${VAR}` syntax for variable substitution, which differs from Jinja2's `{{ VAR }}` syntax, creating inconsistency.
   * **Solution:** Updated the regular expression pattern in `_substitute_variables` to recognize `{{ VAR }}` syntax instead of `${VAR}`. The new pattern `r"\{\{\s*(?P<var>[a-zA-Z0-9_]+)\s*\}\}"` matches variables in the format `{{ VAR_NAME }}` with optional whitespace.

2. **Updated Documentation and Comments:**
   * **Problem:** The function docstrings and comments still referenced the old `${VAR}` syntax.
   * **Solution:** Updated all relevant documentation and comments to reflect the new `{{ VAR }}` syntax for consistency.

## New Feature: Per-Agent Configuration Settings for `warn_on_missing_variables` and `substitute_in_included_files`

### Changed Files:
- `src/promptscribe/composer.py`
- `src\promptscribe\scaffolds\example\prompts.yml`
- `src\promptscribe\scaffolds\default\prompts.yml`

### Brief Description of Work Done:
This task added support for per-agent configuration settings, allowing different agents to have different behaviors for variable warnings and file substitution. Specifically, both `warn_on_missing_variables` and `substitute_in_included_files` can now be configured globally or overridden at the agent level, providing more granular control over agent behavior.

### Detailed Description of Changes:

1. **Added Local Configuration for `warn_on_missing_variables`:**
   * **Problem:** Previously, warnings for undefined variables were controlled only globally through settings, making it impossible to have fine-grained control per agent.
   * **Solution:** Added a new setting `warn_on_missing_variables` that can be configured per agent. The system follows the priority: agent-specific setting > global setting > default (True). This allows specific agents to disable warnings when working with templates that intentionally contain undefined variables, such as shell scripts.

2. **Enhanced Local Configuration for `substitute_in_included_files`:**
   * **Problem:** The `substitute_in_included_files` setting was only available globally, limiting the flexibility for mixed workflows that needed different behaviors for different agents.
   * **Solution:** Extended the `substitute_in_included_files` setting to support per-agent configuration. Each agent can now override the global behavior, following the same priority: agent-specific setting > global setting > default (True).

3. **Fixed Timing Issue in Configuration Context:**
   * **Problem:** The initial implementation had a critical flaw where `_settings` were added to variables *after* the `_resolve_variables` call, meaning the settings were not available during the initial variable substitution phase.
   * **Solution:** Modified the `compose_agent` method to determine the settings *before* calling `_resolve_variables`. Updated `_resolve_variables` to accept an `extra_context` parameter, allowing settings to be passed directly to the variable resolution context. This ensures that `_settings` are available immediately when variable substitution begins.

4. **Updated Scaffolds:**
   * **Problem:** New settings were not documented in the example and default configuration scaffolds.
   * **Solution:** Added `warn_on_missing_variables` to the example scaffold with documentation. Added commented-out `warn_on_missing_variables` to the default scaffold as an example.

### Technical Notes on Implementation:
*   The `_resolve_variables` method was updated to accept an `extra_context` parameter, maintaining backward compatibility with a default value of `None`.
*   Settings are stored in a `_settings` dictionary within the variables, containing both `warn_on_missing` and `substitute_in_includes` flags.
*   The `_substitute_variables` method checks the `variables.get('_settings', {}).get('warn_on_missing', True)` flag before issuing warnings about undefined variables.
*   Both `_run_simple_assembly` and Jinja2 functions now use the agent-specific setting for `substitute_in_includes` via `variables.get('_settings', {}).get('substitute_in_includes', True)`.

### Verification Steps Taken:
*   All changes were confirmed as successful by the tool.
*   The logical flow was reviewed to ensure the timing issue was fixed - settings are determined and passed to `_resolve_variables` before variable substitution begins.
*   The updated code structure maintains the architectural principle of separation of concerns.

## Remaining Unresolved Issues:
None. All identified problems have been addressed.

## Recommendations for Addressing Remaining Issues:
N/A
