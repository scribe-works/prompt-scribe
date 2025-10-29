# Prompt Scribe: Development Rules

## 1. Introduction

These are the mandatory rules and principles for development on the Prompt Scribe project. They apply to all contributors, whether human or AI-driven. The purpose of these rules is to maintain architectural integrity, code quality, and long-term project health.

Any code review that identifies a deviation from these rules must mark it as requiring a fix before the changes can be merged.

## 2. Architectural Integrity

-   **Unyielding Adherence to Architecture:** All changes **must** strictly conform to the principles and component boundaries outlined in `docs/en/Development/ARCHITECTURE.md`. The `ARCHITECTURE.md` file is the project's "genome." Before implementing any change, verify that it does not violate the core philosophy or component responsibilities.

## 3. Code Quality and Style

-   **Comment Language:** All code comments **must** be in English.

-   **Comment Philosophy:** Comments should explain the **"why,"** not the "what." Focus on the intent and the reasons for non-obvious design choices. Avoid comments that merely restate what the code does.

-   **Clean Codebase:** Do not commit temporary debug statements or commented-out blocks of code. The final committed code must be production-ready.

-   **Technical Debt:** Use `TODO` or `FIXME` markers sparingly. Each marker must be justified and ideally linked to an issue in the project's issue tracker.

-   **Strict Prohibition of BBCode in UI Calls:**
    -   **Rule:** **Under no circumstances** should BBCode tags (`[tag]...[/tag]`) be used to style variables in strings passed to the `ui` module (e.g., `ui.success('File [bold]${filename}[/bold] saved')`).
    -   **Rationale (CRITICAL):** This is a critical architectural violation. The `ui.py` module is intentionally designed with an **automatic variable highlighting system** that styles quoted strings. Manual BBCode styling bypasses this system, creates inconsistent output, and pollutes the calling code, defeating the core purpose of the UI module. Adherence to this rule is non-negotiable.

## 4. Testing

-   **Mandatory Test Coverage:** Any new feature or modification to existing functionality **must** be accompanied by corresponding unit or integration tests in the `tests/` directory.

-   **Maintaining a Green Build:** Changes that cause existing tests to fail are not permissible. Either the code must be fixed to pass the tests, or the failing tests must be justifiably updated to reflect the new, correct behavior.

## 5. Branching and Commits

-   **Branch Naming:** Branches should be named descriptively, starting with a type prefix (e.g., `feature/`, `fix/`, `refactor/`). Example: `refactor/new-composition-engine`.

-   **Commit Messages:** Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This is essential for automated versioning and changelog generation.
    -   Example: `feat: add simple assembly mode for prompt composition`
    -   Example: `fix: correct output path resolution for relative paths`
    -   Example: `docs: update ARCHITECTURE file with new lifecycle`
