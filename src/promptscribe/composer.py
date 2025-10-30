"""
promptscribe.composer
~~~~~~~~~~~~~~~~~~~~~

This module contains the core logic for composing prompts.
It reads a YAML configuration file, processes different sections
(persona, includes, etc.), and uses the Jinja2 templating engine
to generate the final prompt files.

@copyright: (c) 2025 by The Scribe Works.
"""
import re
from pathlib import Path
from typing import Any, Dict, List

import jinja2
import yaml

from .ui import ui

MAX_SUBSTITUTION_DEPTH = 10


class PromptScribeError(Exception):
    """Custom exception for errors originating from Prompt Scribe composer."""
    pass


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
            raise PromptScribeError(f"Configuration file not found at '{self.config_path}'")
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
            raise PromptScribeError(f"Error parsing YAML file: {e}")
        except Exception as e:
            ui.error(f"Failed to read config file: {e}")
            raise PromptScribeError(f"Failed to read config file: {e}")

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
            ui.warning(f"File not found during substitution: '{file_path_str}'")
            return "" # Return empty string if file not found
        except Exception as e:
            ui.error(f"Failed to read file '{file_path_str}': {e}")
            raise PromptScribeError(f"Failed to read file '{file_path_str}': {e}")

    def _resolve_variables(self, agent_name: str) -> Dict[str, Any]:
        """
        Resolves and merges global and agent-specific variables.

        Args:
            agent_name: The name of the agent.

        Returns:
            A dictionary of resolved variables.
        """
        agent_config = self.config.get("agents", {}).get(agent_name, {})
        global_vars = self.config.get("variables", {}).copy()
        agent_vars = agent_config.get("variables", {}).copy()
        
        # Merge global and agent variables, agent vars take precedence
        merged_vars = {**global_vars, **agent_vars}
        
        return merged_vars

    def _substitute_variables(self, text: str, variables: Dict[str, Any], depth: int = 0) -> str:
        """
        Recursively substitutes ${VAR} placeholders in the text.

        Args:
            text: The string to perform substitutions on.
            variables: A dictionary of available variables.
            depth: The current recursion depth to prevent infinite loops.

        Returns:
            Text with placeholders replaced by their values.
        """
        if depth > MAX_SUBSTITUTION_DEPTH:
            raise PromptScribeError("Maximum variable substitution depth exceeded. Check for circular references.")

        # Regex to find ${VAR_NAME} with standard variable name characters.
        pattern = re.compile(r'\${([a-zA-Z0-9_]+)}')

        def replacer(match):
            var_name = match.group(1)
            if var_name in variables:
                value = variables[var_name]
                # Recursively substitute variables within the value itself
                return self._substitute_variables(str(value), variables, depth + 1)
            ui.warning(f"Variable '{var_name}' found in text but not in config. Leaving it untouched.")
            return match.group(0)

        return pattern.sub(replacer, text)

    def _run_simple_assembly(self, agent_config: dict, variables: dict) -> str:
        """
        Builds the prompt from a sequence of assembly steps.

        Args:
            agent_config: The configuration for the specific agent.
            variables: The resolved variables for the agent.

        Returns:
            The fully assembled prompt as a string.
        """
        parts = []
        assembly_steps = agent_config.get('assembly', [])
        
        substitute_in_includes = self.config.get("settings", {}).get("substitute_in_included_files", True)

        for step in assembly_steps:
            if not isinstance(step, dict) or not step:
                continue
            
            if len(step) > 1:
                ui.warning(f"Assembly step has multiple keys, only the first will be used: {list(step.keys())}")

            key, value = next(iter(step.items()))
            
            if key == 'include':
                path_from_vars = variables.get(str(value))
                if not path_from_vars:
                    ui.warning(f"In 'include' step, variable '{value}' not found or is empty.")
                    continue
                
                resolved_path = self._substitute_variables(str(path_from_vars), variables)
                file_content = self._read_file_content(resolved_path)
                
                if substitute_in_includes:
                    substituted_content = self._substitute_variables(file_content, variables)
                    parts.append(substituted_content)
                else:
                    parts.append(file_content)

            elif key == 'include_raw':
                # For 'include_raw', we do the same as include but DO NOT substitute variables in the file content.
                path_from_vars = variables.get(str(value))
                if not path_from_vars:
                    ui.warning(f"In 'include_raw' step, variable '{value}' not found or is empty.")
                    continue
                
                resolved_path = self._substitute_variables(str(path_from_vars), variables)
                file_content = self._read_file_content(resolved_path)
                parts.append(file_content) # Append raw content
            
            else:
                # For all other keys ('content', 'h2', 'separator'), the value is a string
                # that needs variable substitution.
                processed_value = self._substitute_variables(str(value), variables)

                if key == 'content':
                    parts.append(processed_value)
                elif key == 'separator':
                    parts.append(processed_value)
                elif key.startswith('h') and key[1:].isdigit():
                    level = int(key[1:])
                    parts.append(f"{'#' * level} {processed_value}")
        
        return "\n\n".join(p.strip() for p in parts if p)

    def compose_agent(self, agent_name: str) -> None:
        """
        Composes and saves the prompt for a single agent.

        Args:
            agent_name: The name of the agent to compose.
        """
        agent_config = self.config.get("agents", {}).get(agent_name)
        if not agent_config:
            ui.error(f"Agent '{agent_name}' not found in configuration.")
            raise PromptScribeError(f"Agent '{agent_name}' not found in configuration.")

        ui.title(f"Composing agent: '{agent_name}'")

        # 1. Resolve variables
        variables = self._resolve_variables(agent_name)
        
        final_prompt = ""
        settings = self.config.get("settings", {})

        # 2. Determine mode: 'assembly' is explicit. If not present, we default to the more
        # powerful Jinja2 templating mode, which allows for greater flexibility.
        if 'assembly' in agent_config:
            # Simple Assembly Mode
            ui.info("Using simple assembly mode.")
            final_prompt = self._run_simple_assembly(agent_config, variables)
        
        else:
            # Jinja2 Mode (default)
            ui.info("Using Jinja2 template mode.")

            # Determine template name: local > global
            local_template = agent_config.get('template')
            global_template = settings.get('template')
            
            template_name = ""
            if local_template:
                template_name = self._substitute_variables(local_template, variables)
                ui.info(f"Using agent-specific template: '{template_name}'")
            elif global_template:
                template_name = self._substitute_variables(global_template, variables)
                ui.info(f"Using global template: '{template_name}'")
            else:
                ui.error(f"Agent '{agent_name}' is in template mode but no local or global template is defined.")
                raise PromptScribeError(f"Agent '{agent_name}' is in template mode but no local or global template is defined.")

            # Setup Jinja environment
            templates_dir_str = settings.get("templates_dir", "templates")
            templates_dir = self._resolve_path(templates_dir_str)
            
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(searchpath=str(templates_dir)),
                autoescape=False
            )

            substitute_in_includes = settings.get("substitute_in_included_files", True)

            def read_file_and_substitute(path: str) -> str:
                """
                Reads a file and substitutes ${VAR} style variables, depending on the
                'substitute_in_included_files' setting.
                """
                file_content = self._read_file_content(path)
                if substitute_in_includes:
                    return self._substitute_variables(file_content, variables)
                return file_content

            env.globals['read_file'] = read_file_and_substitute
            env.globals['read_file_raw'] = self._read_file_content
            
            try:
                template = env.get_template(template_name)
                final_prompt = template.render(variables)
            except jinja2.TemplateNotFound:
                ui.error(f"Jinja2 template '{template_name}' not found in '{templates_dir}'.")
                raise PromptScribeError(f"Jinja2 template '{template_name}' not found in '{templates_dir}'.")
            except Exception as e:
                ui.error(f"Error rendering Jinja2 template: {e}")
                raise PromptScribeError(f"Error rendering Jinja2 template: {e}")

        # 3. Determine output file path and save
        output_dir_str = settings.get("output_dir", "composed_prompts")
        
        resolved_output_dir_str = self._substitute_variables(output_dir_str, variables)
        output_dir = self._resolve_path(resolved_output_dir_str)

        output_file_name = agent_config.get('output_file')
        if output_file_name:
            output_file_name = self._substitute_variables(output_file_name, variables)
            # If the output_file is a path (relative or absolute), resolve it.
            # Otherwise, treat it as a filename to be placed in the output_dir.
            if '/' in output_file_name or '\\' in output_file_name:
                output_file_path = self._resolve_path(output_file_name)
            else:
                output_file_path = output_dir / output_file_name
        else:
            # If not specified, generate from agent name and place in output_dir
            output_file_name = f"{agent_name}.md"
            output_file_path = output_dir / output_file_name

        # Ensure the target directory exists before writing
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        output_file_path.write_text(final_prompt, encoding="utf-8")

        ui.success(f"Successfully composed prompt for '{agent_name}' -> '{output_file_path.relative_to(Path.cwd())}'")
