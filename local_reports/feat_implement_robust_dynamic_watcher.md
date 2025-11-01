### Modified Files

-   `src/promptscribe/cli.py`
-   `src/promptscribe/composer.py`

### Brief Description of Work Done

A new, robust version of the `--watch` mode was implemented and debugged. The main goal was to ensure tracking of dependency files located outside the main project directory and to implement a dynamic watcher restart mechanism when the `prompts.yml` configuration file changes.

### Detailed Description of Changes

Work was carried out in several key stages to address fundamental problems in the initial implementation:

1.  **Analysis of all dependencies:**
    *   A method `analyze_dependencies` and a flag `dry_run` for the `compose_agent` method were added to the `PromptComposer` class.
    *   This allowed performing "trial" builds of all agents without writing to disk with the sole purpose of creating a complete map of all files the project depends on, including templates, `include`-files and the `prompts.yml` file itself, regardless of their location in the file system.

2.  **Implementation of dynamic watcher restart:**
    *   **Change detection:** `ChangeHandler` now tracks changes in `prompts.yml` and compares the old set of watched directories with the new one.
    *   **Inter-thread communication:** The initial attempt to restart via exceptions proved unviable due to `watchdog` working in a separate thread. The problem was solved by implementing a standard pattern using `queue.Queue` for safe transmission of the restart signal from the worker thread to the main thread.
    *   **Control loop:** Instead of unreliable recursion, a main control loop `while` was implemented in the `compose` command that manages the watcher's lifecycle. This solved the problem of multiple stop messages when exiting via `Ctrl+C`.

3.  **Suppressing console "noise":**
    *   A problem was identified where `analyze_dependencies` printed numerous warnings and informational messages from all agents to the console, cluttering the output.
    *   After discussing several approaches, the cleanest and most reliable solution was chosen: using a `suppress_stdout` context manager to completely redirect standard output (`stdout`) to `os.devnull` during dependency analysis.

4.  **Ensuring cross-platform stability:**
    *   During testing, a `UnicodeEncodeError` was discovered on the Windows platform occurring when attempting to write Unicode characters to `os.devnull` with the default system encoding. The problem was solved by explicitly specifying `encoding="utf-8"` when opening `os.devnull`, which guarantees the robustness of the solution on various platforms.

### Technical Notes on Implementation

-   **Control loop instead of recursion:** Transitioning from recursive calls of `_run_watcher` to a `while current_composer:` loop in `compose` is a key architectural improvement ensuring correct state management and clean application exit.
-   **Output suppression via `contextmanager`:** Implementation of `suppress_stdout` using `@contextmanager` is an idiomatic and safe way to temporarily change global state (like `sys.stdout`), guaranteeing its restoration even in case of errors.
-   **Build priority:** The logic in `handle_config_change` was designed so that affected agents are always rebuilt first and only then is a decision made about whether a watcher restart is necessary. This ensures that each configuration change immediately reflects in the generated files.

### Verification Steps Taken

-   Verified that changes in files located outside the `.prompt_scribe` directory are correctly tracked and trigger rebuilds of related agents.
-   Tested dynamic restart: a dependency from a new, previously untracked directory was added to and removed from `prompts.yml` during `--watch` operation. Confirmed that the watcher correctly restarts with the new set of paths.
-   Verified correct exit from `--watch` mode via `Ctrl+C` after several restart cycles; the "avalanche" of `Watcher stopped` messages has been eliminated.
-   Confirmed that console output is completely absent during dependency analysis execution (both at initial launch and during subsequent changes to `prompts.yml`).
-   Verified that warnings from agents with incorrect configuration appear only during their direct build process, not during background analysis.