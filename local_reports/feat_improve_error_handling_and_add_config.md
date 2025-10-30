# feat: improve error handling and add variable substitution config

This report details the work undertaken to enhance the Prompt Scribe application's error handling mechanism and introduce a new configuration option for controlling variable substitution in included files.

## Modified Files:

*   `src/promptscribe/composer.py`
*   `src/promptscribe/scaffolds/example/prompts.yml`
*   `src/promptscribe/scaffolds/default/prompts.yml`
*   `src/promptscribe/cli.py`

## Summary of Changes:

### 1. Re-introduction of `_raw` methods and `substitute_in_included_files` setting

**Problem:**
The previous refactoring removed the `include_raw` functionality and introduced a default behavior where all included files (via `include` in simple assembly mode or `read_file` in Jinja2 mode) would attempt variable substitution. This led to "noisy" warnings for files that intentionally used `${...}` syntax for purposes other than variable placeholders, as well as a lack of explicit control for users who wished to include raw file content.

**Solution:**
To address this, the following changes were implemented:
*   **`include_raw` in Simple Assembly Mode:** The `include_raw` directive was re-introduced in the `_run_simple_assembly` method. This allows users to explicitly include file content without any variable substitution, preventing unwanted warnings.
*   **`read_file_raw` in Jinja2 Mode:** A new global function `read_file_raw` was added to the Jinja2 environment. This function mirrors the behavior of `include_raw`, enabling Jinja2 templates to read files without variable substitution.
*   **`settings.substitute_in_included_files` Configuration:** A new global setting, `substitute_in_included_files` (defaulting to `true`), was added to `prompts.yml`. This setting provides a project-wide control over whether `include` (simple assembly) and `read_file` (Jinja2) should perform variable substitution. If set to `false`, these methods will behave like their `_raw` counterparts, including file content without substitution.
*   **Documentation Updates:** The `src/promptscribe/scaffolds/example/prompts.yml` and `src/promptscribe/scaffolds/default/prompts.yml` files were updated to include examples and comments for the new `substitute_in_included_files` setting, ensuring users are aware of this new functionality.

### 2. Improved Error Handling with `PromptScribeError`

**Problem:**
The application's error handling was inconsistent. Errors originating from the `composer.py` module were either silently passed (`except Exception: pass` in `cli.py`) or re-raised as generic Python exceptions, making debugging difficult and user feedback less informative.

**Solution:**
A custom exception class, `PromptScribeError`, was introduced to centralize and standardize error reporting:
*   **`PromptScribeError` Definition:** A new class `PromptScribeError(Exception)` was defined in `src/promptscribe/composer.py`.
*   **Composer Error Wrapping:** All significant error conditions within `composer.py` (e.g., `FileNotFoundError`, `yaml.YAMLError`, `RecursionError`, `jinja2.TemplateNotFound`, and other generic `Exception`s) are now caught and re-raised as `PromptScribeError`. This ensures that any error originating from the core composition logic is consistently wrapped in our custom exception.
*   **CLI Error Handling:** The `_compose_agents` method in `src/promptscribe/cli.py` was modified to specifically catch `PromptScribeError`. When caught, an informative error message is displayed to the user using `ui.error`, and the application exits with a non-zero status code (`typer.Exit(1)`), providing clear feedback on composition failures.

## Conclusion:

These changes significantly improve the robustness and user-friendliness of Prompt Scribe. Users now have fine-grained control over variable substitution in included files, and the application provides clearer, more consistent error messages, making it easier to diagnose and resolve issues.