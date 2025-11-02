### Changed Files

- `src/promptscribe/cli.py`
- `src/promptscribe/composer.py`

### Brief Description

A series of significant improvements and fixes were made aimed at increasing performance, stability and code cleanliness. The main changes affected the composition engine (`composer.py`) and watch mode logic (`cli.py`).

### Detailed Description of Changes

#### 1. Fixed critical bug in `watch` mode (`cli.py`)

- **Problem:** The application would crash if an agent was deleted from the `prompts.yml` configuration file while in watch mode.
- **Solution:** Added logic in `ChangeHandler.handle_config_change` to filter the list of affected agents before rebuilding, keeping only those that exist in the new configuration. This prevents attempts to access non-existent agents and ensures stable operation.

#### 2. Performance refactor of composition engine (`composer.py`)

- **Problem:** A new instance of `jinja2.Environment` was created for each variable substitution (`{{ ... }}`), causing significant performance losses in loops (e.g. when processing multiple variables or build steps).
- **Solution:** The substitution mechanism was completely redesigned. Now a single instance of `jinja2.Environment` is created during `PromptComposer` initialization and reused for all operations. Context for error messages is passed dynamically through the object's property, which preserved the informativeness of warnings without performance loss.

#### 3. Improved error handling (`composer.py`)

- **Problem:** The method `_substitute_variables` used too broad an `except Exception` block, which could catch unwanted system exceptions (e.g. `KeyboardInterrupt`).
- **Solution:** The block was replaced with a more specific `except (jinja2.TemplateError, TypeError) as e:`, making error handling more predictable and safe.

#### 4. Semantic refactoring and improved readability (`composer.py`)

- **Problem:** The `context_info` parameter in `_substitute_variables` had an unclear purpose and was used incorrectly, leading to useless log messages.
- **Solution:** Based on deep analysis of the original intent, the parameter was renamed to `file_path_context` and its use was limited to cases where a file path can actually be specified. This made warnings about missing variables much more informative, as they now point to the specific file where the variable was found.
- **Elimination of duplication:** In `_run_simple_assembly`, duplicate file reading logic was eliminated by transitioning to use the common helper `_get_and_process_file_content`.

### Technical Notes on Implementation

The key decision for the performance refactor was using a shared dictionary `_subst_context` in the `PromptComposer` instance. This dictionary is updated before each call to `_substitute_variables`, passing the current context (file path) to the `WarningUndefined` handler, which allowed combining high performance with informative errors.

All changes were made incrementally, with explicit confirmation of each stage to ensure full control and understanding of the process.

### Verification Steps Taken

- All changes were made after detailed discussion and obtaining explicit agreement.
- The logic of fixes and refactoring was verified based on provided scenarios and code analysis.
- In accordance with the instruction, automated tests were not created during this session.

### Remaining Unresolved Tasks

- Automated tests need to be added for the fixed `watch` mode bug to prevent regressions in the future.
- It is recommended to cover the updated logic in `composer.py` with tests for formal verification of correctness and performance.
