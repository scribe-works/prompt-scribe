"""
promptscribe.composer
~~~~~~~~~~~~~~~~~~~~~

This module contains the core logic for composing prompts.
It reads a YAML configuration file, processes different sections
(persona, includes, etc.), and uses the Jinja2 templating engine
to generate the final prompt files.

@copyright: (c) 2025 by The Scribe Works.
"""
from pathlib import Path
from typing import Any, Dict, List

import jinja2
import yaml

from .ui import ui


class PromptComposer:
    """Orchestrates the prompt composition process."""

    def __init__(self, config_path: str = ".prompt_scribe/prompts.yml"):
        """
        Initializes the composer.

        Args:
            config_path: Path to the main YAML configuration file.
        """
        self.config_path = Path(config_path).resolve()
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found at '{self.config_path}'")
        self.base_dir = self.config_path.parent
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads and validates the main YAML configuration file."""
        ui.info(f"Loading configuration from '{self.config_path.relative_to(Path.cwd())}'")
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            ui.error(f"Error parsing YAML file: {e}")
            raise
        except Exception as e:
            ui.error(f"Failed to read config file: {e}")
            raise

    def get_all_agent_names(self) -> List[str]:
        """Returns a list of all configured agent names."""
        return list(self.config.get("agents", {}).keys())

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolves a path relative to the config file's location."""
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return (self.base_dir / path).resolve()

    def _read_file_content(self, file_path_str: str) -> str:
        """Reads content from a file, handling potential errors."""
        try:
            file_path = self._resolve_path(file_path_str)
            return file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            ui.error(f"File not found: '{file_path_str}'")
            raise
        except Exception as e:
            ui.error(f"Failed to read file '{file_path_str}': {e}")
            raise

    def compose_agent(self, agent_name: str) -> None:
        """
        Composes and saves the prompt for a single agent.

        Args:
            agent_name: The name of the agent to compose.
        """
        agent_config = self.config.get("agents", {}).get(agent_name)
        if not agent_config:
            ui.error(f"Agent '{agent_name}' not found in configuration.")
            return

        ui.title(f"Composing agent: '{agent_name}'")

        # Prepare context for Jinja2
        context: Dict[str, Any] = {}

        # 1. Process Persona
        if "persona" in agent_config and "file" in agent_config["persona"]:
            persona_data = agent_config["persona"].copy()
            persona_data["content"] = self._read_file_content(persona_data["file"])
            context["persona"] = persona_data

        # 2. Process Sections
        processed_sections = []
        for section in agent_config.get("sections", []):
            section_copy = section.copy()
            if "file" in section_copy:
                section_copy["content"] = self._read_file_content(section_copy["file"])
            elif "content" not in section_copy:
                ui.warning(f"Section '{section_copy.get('title', 'Untitled')}' has no 'file' or 'content'. Skipping.")
                continue
            processed_sections.append(section_copy)
        context["sections"] = processed_sections

        # 3. Render Template
        settings = self.config.get("settings", {})
        templates_dir_str = settings.get("templates_dir", "templates")
        templates_dir = self._resolve_path(templates_dir_str)
        
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(searchpath=templates_dir),
            autoescape=False
        )
        template_name = agent_config.get("template", "default.jinja2")
        template = env.get_template(template_name)
        
        final_prompt = template.render(context)

        # 4. Save Output
        output_dir_str = settings.get("output_dir", "composed_prompts")
        output_dir = self._resolve_path(output_dir_str)
        output_dir.mkdir(exist_ok=True)
        
        output_file_path = output_dir / agent_config["output_file"]
        output_file_path.write_text(final_prompt, encoding="utf-8")

        ui.success(f"Successfully composed prompt for '{agent_name}' -> '{output_file_path.relative_to(Path.cwd())}'")