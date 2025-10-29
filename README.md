<table>
  <tr>
    <td align="center" style="border: none; padding: 0;">
      <img src="https://raw.githubusercontent.com/scribe-works/prompt-scribe/main/docs/assets/logo.png" alt="The Scribe Works Logo" width="200"/>
    </td>
    <td style="border: none; padding: 0; vertical-align: middle;">
      <h1>Prompt Scribe</h1>
      <p>A powerful, template-based prompt composer for crafting and managing complex instructions for LLMs.</p>
    </td>
  </tr>
</table>

---

## The Problem

Managing large, multi-part prompts for Large Language Models can be messy. You often combine a persona, rules, context from different files, and a specific query. Doing this manually by copy-pasting is tedious and error-prone.

## The Solution

**Prompt Scribe** automates this process. It uses a simple YAML configuration with powerful features like variables, file includes, and two different composition modes to build your final prompts, ready to be used in any LLM chat or API.

## Key Features

-   **Declarative & Flexible:** Configure prompts with a clear, intuitive YAML structure.
-   **Two Composition Modes:**
    -   **Simple Assembly:** Sequentially build prompts from content blocks, file includes, and headers.
    -   **Jinja2 Templating:** Use the full power of Jinja2 for complex logic and transformations.
-   **Variable System:** Define global and agent-specific variables with support for overriding and recursive substitution (`${VAR}`).
-   **Safe Initialization:** Creates a dedicated `.prompt_scribe/` directory to avoid cluttering your project root.
-   **Watch Mode:** Automatically recompose prompts when source files change.
-   **Beautiful CLI:** A clean, helpful command-line interface.

## Installation

```bash
pip install prompt-scribe
```

## Quick Start

1.  **Initialize a new project:**
    Navigate to your project directory and run:
    ```bash
    prompt-scribe init
    ```
    This will create a self-contained `.prompt_scribe/` directory with a default structure:
    ```
    .
    └── .prompt_scribe/
        ├── composed_prompts/
        ├── includes/
        │   └── development-rules.md
        ├── personas/
        │   └── code-reviewer.md
        ├── templates/
        │   └── master.jinja2
        └── prompts.yml
    ```

2.  **Compose your prompts:**
    Run the compose command from your project root:
    ```bash
    prompt-scribe compose
    ```
    This will read `.prompt_scribe/prompts.yml`, process all defined agents, and generate the final prompts in `.prompt_scribe/composed_prompts/`.

3.  **Use the output:**
    Open the generated files, copy the content, and paste it into your LLM chat interface.

## Usage

### Composing Prompts

-   **Compose all agents**:
    ```bash
    prompt-scribe compose
    ```
-   **Compose specific agents**:
    ```bash
    prompt-scribe compose agent-one agent-two
    ```
-   **Watch for changes** and automatically recompose:
    ```bash
    prompt-scribe compose --watch
    ```

## Configuration (`.prompt_scribe/prompts.yml`)

The `prompts.yml` file is the heart of your project. It resolves all paths relative to its own location. It supports variables, two different composition modes, and smart output path handling.

```yaml
# Global settings for all agents
settings:
  # The output directory for the composed prompts.
  output_dir: "composed_prompts"
  # The directory where Jinja2 templates are located.
  templates_dir: "templates"
  # A global template to be used by agents that don't specify their own.
  template: "master.jinja2"

# Global variables available to all agents.
# These can be overridden by agent-specific variables.
variables:
  project_name: "Prompt Scribe"
  rules_path: "includes/development-rules.md"
  persona_path: "personas/code-reviewer.md"
  # Example of an absolute path. Replace with a real path on your system.
  architecture_doc: "path/to/your/ARCHITECTURE.md"

agents:
  # --- Example 1: A comprehensive agent using the "Simple Assembler" ---
  code-reviewer:
    variables:
      # This overrides the global 'project_name' for this agent only.
      project_name: "DocuScribe"

    assembly:
      # 1. You can include content directly from a file via a variable.
      - include: persona_path
      - separator: "---"
      # 2. You can also have inline content with variable substitution.
      - content: |
          You are a senior AI developer for the `${project_name}` project.
          Your main task is to provide a thorough and constructive code review.
      - separator: "---"
      # 3. Use headers and include other files.
      - h2: "📜 Key Development Rules"
      - include: rules_path
      - separator: "---"
      # 4. Include a file using an absolute path variable.
      - h2: "📄 Project Architecture"
      - include: architecture_doc

  # --- Example 2: An agent that uses the GLOBAL template defined in settings ---
  global-template-agent:
    # This agent has no 'assembly' or 'template' key, so it falls back
    # to using the global 'template: master.jinja2' from the settings.
    output_file: "global_template_example.md"
    variables:
      main_title: "Global Template Report"
      report_type: "daily"
      data_source_file: "includes/development-rules.md"

  # --- Example 3: An agent that OVERRIDES the global template ---
  advanced-report-generator:
    template: "report.jinja2" # This agent provides its own template.
    # The output path can be relative and go outside the default output_dir.
    output_file: "../custom_outputs/final_report.txt"
    variables:
      report_type: "weekly"
      # This variable can be used inside the Jinja2 template, for example, to load data.
      data_source: "includes/source-data.json"
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
