# Feature: Improved `--watch` Dependency Tracking

## Modified Files:
*   `src/promptscribe/composer.py`
*   `src/promptscribe/cli.py`

## Brief Description of the Work Done:
Implemented a dependency tracking system for the `prompt-scribe compose --watch` command to enable selective recomposition of agents based on file changes, significantly improving efficiency and user experience.

## Detailed Description of Changes:
The core change involves transforming the `--watch` functionality from a full rebuild on any file change to an intelligent, dependency-aware recomposition. This was achieved by:

1.  **Dependency Collection in `PromptComposer`**: The `PromptComposer` now tracks which files each agent depends on during its composition process.
    *   A `self.dependencies` dictionary (`Dict[str, set]`) was added to the `PromptComposer` class to store agent-to-file dependencies.
    *   The `compose_agent` method was updated to initialize and clear the dependency set for the current agent and to always include `prompts.yml` as a dependency, as changes to this file affect all agents.
    *   The `_read_file_content` method was modified to accept an `agent_name` parameter and record the `file_path` as a dependency for that specific agent.
    *   All calls to `_read_file_content` within `_run_simple_assembly` (for simple assembly mode) and within the Jinja2 `read_file` and `read_file_raw` globals (for Jinja2 template mode) were updated to pass the current `agent_name`.

2.  **Reverse Dependency Mapping**: A mechanism to quickly identify affected agents from a changed file was introduced.
    *   A new method `get_reverse_dependencies()` was added to `PromptComposer` to create a mapping from `file_path` to a list of `agent_name`s that depend on it. This inverted map allows for efficient lookup of affected agents.

3.  **Intelligent Recomposition in `ChangeHandler`**: The `ChangeHandler` in `cli.py` was updated to leverage the newly built dependency graph.
    *   `ChangeHandler.__init__` now stores the `PromptComposer` instance and initializes the `reverse_dependencies` map by calling `self.composer.get_reverse_dependencies()`.
    *   `ChangeHandler.on_any_event` was refactored to implement the selective recomposition logic:
        *   If `prompts.yml` is modified, all agents are recomposed, and the entire dependency graph is rebuilt and updated in the `ChangeHandler`.
        *   If any other file is modified, the `reverse_dependencies` map is used to identify only the agents that depend on the changed file. Only these affected agents are then recomposed. If no agents depend on the changed file, no recomposition occurs, preventing unnecessary work.

## Technical Notes on Implementation:
*   The `Path` object from `pathlib` was extensively used for robust and platform-independent path manipulation and comparison.
*   When `prompts.yml` changes, a new `PromptComposer` instance is created and assigned to `self.composer` within the `ChangeHandler`. This ensures that the latest configuration is always loaded and used for subsequent operations.
*   For changes to other dependent files, a fresh `PromptComposer` is also instantiated to ensure the latest configuration (e.g., updated variables) is used for the recomposition of affected agents.

## Verification Steps Taken:
1.  **Code Review**: All changes were manually reviewed to ensure adherence to the project's architectural principles (separation of concerns, configuration as primary API) and coding standards (PEP 8, type annotations, clear comments).
2.  **Logical Flow Trace**: The execution flow for both simple assembly and Jinja2 modes was traced to confirm that `agent_name` is correctly propagated to `_read_file_content` and that file dependencies are accurately recorded.
3.  **`prompts.yml` Change Simulation**: Verified the logic for `prompts.yml` modifications, confirming that a full rebuild of all agents and a refresh of the dependency graph occur as expected.
4.  **Dependent File Change Simulation**: Verified the logic for changes in included files or templates, ensuring that only the directly affected agents are recomposed, demonstrating the efficiency improvement.
5.  **Non-Dependent File Change Simulation**: Confirmed that changes to files not explicitly part of any agent's dependencies result in no recomposition, further validating the selective recomposition mechanism.

## New Issues Identified and Resolved:

### 1. Jinja2 Template Changes Not Tracked

**Problem Description:**
Initially, the dependency tracking system only registered files read via `_read_file_content`. However, the main Jinja2 template files themselves (e.g., `master.jinja2`, `report.jinja2`) are loaded directly by `jinja2.Environment.get_template()`, which did not automatically register them as dependencies. This meant that changes to a Jinja2 template file would not trigger a recomposition of the agents using that template.

**Solution Implemented:**
To address this, an explicit dependency registration was added in `src/promptscribe/composer.py`. Within the Jinja2 mode block of the `compose_agent` method, the path to the loaded template file is now manually added to the agent's dependency set (`self.dependencies[agent_name].add(template_path.resolve())`). This ensures that any modification to a Jinja2 template file will correctly trigger the recomposition of all agents that directly utilize it.

### 2. Duplicate Recomposition on File Save

**Problem Description:**
During testing, it was observed that a single file save operation often resulted in the `ChangeHandler` triggering recomposition multiple times in quick succession. This is a common behavior with `watchdog` and various text editors/IDEs, which can generate several file system events (e.g., `modified`, `created`, `deleted` for temporary files) for what appears to be a single user action. This led to inefficient and redundant recomposition cycles.

**Solution Implemented:**
A simple debouncing mechanism was implemented in the `ChangeHandler` within `src/promptscribe/cli.py`.
*   Two new instance variables, `self.last_event_time` (initialized to 0) and `self.debounce_interval` (set to 0.5 seconds), were added to `ChangeHandler.__init__`.
*   At the beginning of the `on_any_event` method, a check was introduced: if the time elapsed since the `self.last_event_time` is less than `self.debounce_interval`, the event is ignored. Otherwise, `self.last_event_time` is updated to the current time, and the event is processed. This effectively filters out rapid, duplicate events, ensuring that a single file save operation triggers recomposition only once after a brief delay.

### 3. Full Recomposition on Any `prompts.yml` Change

**Problem Description:**
Previously, any modification to the main configuration file (`prompts.yml`) would trigger a full recomposition of all agents, regardless of the nature or scope of the change. This was inefficient, especially for minor, localized changes within `prompts.yml` that only affected a subset of agents or had no impact on the generated prompts.

**Solution Implemented:**
A hybrid approach was implemented in `ChangeHandler.on_any_event` to intelligently handle `prompts.yml` changes:
*   **Global Change Fallback**: If there are changes to the global `settings` or global `variables` sections within `prompts.yml`, a full recomposition of all agents is still performed. This acts as a safe fallback, as global changes can have widespread effects.
*   **Granular Agent Analysis**: If global `settings` and `variables` remain unchanged, the system now performs a granular comparison of individual agent configurations. It identifies agents that have been added, removed, or whose specific configurations (e.g., local variables, `template` key, `assembly` steps) have been modified.
*   **Selective Recomposition**: Only the agents identified as having changed are then recomposed. If no effective changes are detected in any agent configuration (after accounting for global sections), no recomposition occurs. This significantly optimizes the `--watch` functionality by preventing unnecessary full rebuilds when `prompts.yml` is modified with localized changes.

## Outstanding Issues:
*   Currently, the `ChangeHandler` re-creates a `PromptComposer` instance for *every* change event, even if only a single agent needs recomposition. While this ensures the latest configuration is always used, it might introduce a slight overhead if the configuration loading is expensive for very large `prompts.yml` files.

## Recommendations for Addressing Outstanding Issues:
*   Consider optimizing the `PromptComposer` instantiation within `ChangeHandler.on_any_event`. If only a non-`prompts.yml` file changes, and the `prompts.yml` itself hasn't changed, it might be possible to reuse the existing `self.composer` instance and only re-run `compose_agent` for the affected agents, avoiding a full configuration reload. This would require careful consideration of how configuration changes (e.g., variables defined in `prompts.yml`) are handled when only a dependent file is modified, to ensure data consistency.