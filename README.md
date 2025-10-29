# Prompt Scribe

![The Scribe Works Logo](https://raw.githubusercontent.com/TheScribeWorks/prompt-scribe/main/docs/assets/logo.png)

A powerful, template-based prompt composer for crafting and managing complex instructions for LLMs.

---

## The Problem

Managing large, multi-part prompts for Large Language Models can be messy. You often combine a persona, rules, context from different files, and a specific query. Doing this manually by copy-pasting is tedious and error-prone.

## The Solution

**Prompt Scribe** automates this process. It uses a simple YAML configuration and the powerful Jinja2 templating engine to compose your final prompts from various source files, ready to be used in any LLM chat or API.

## Key Features

-   **Template-Based:** Use Jinja2 templates for maximum flexibility.
-   **Modular:** Split your prompts into reusable parts (personas, includes, rules).
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
    This will read `.prompt_scribe/prompts.yml`, process the `example-code-reviewer` agent, and generate the final prompt in `.prompt_scribe/composed_prompts/`.

3.  **Use the output:**
    Open the generated file, copy the content, and paste it into your LLM chat interface.

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

The `prompts.yml` file is the heart of your project. It resolves all paths relative to its own location.

```yaml
# Global settings for all agents
settings:
  personas_dir: "personas"
  includes_dir: "includes"
  templates_dir: "templates"
  output_dir: "composed_prompts"

# Map of agents to be composed
agents:
  example-code-reviewer:
    # Jinja2 template to use for rendering
    template: master.jinja2
    # The final output file name
    output_file: example_code_reviewer.md
    # The persona section, available as `persona` in the template
    persona:
      file: personas/code-reviewer.md
    # A list of content sections, available as `sections` in the template
    sections:
      - title: "📜 Key Development Rules"
        prologue: "These are the mandatory rules and principles for this project."
        file: includes/development-rules.md
      - title: "📄 Code Snippet for Review"
        # You can also include content directly
        content: |
          ```python
          def hello_world():
              print("Hello, Scribe!")
          ```
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.