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
        self.dependencies: Dict[str, set] = {}  # agent -> {file_path}

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

    def _read_file_content(self, file_path_str: str, agent_name: str) -> str:
        """Reads content from a file, handling potential errors and recording dependencies."""
        try:
            file_path = self._resolve_path(file_path_str)
            if agent_name and agent_name in self.dependencies:
                self.dependencies[agent_name].add(file_path)
            return file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            ui.warning(f"File not found during substitution: '{file_path_str}'")
            return "" 
        except Exception as e:
            ui.error(f"Failed to read file '{file_path_str}': {e}")
            raise PromptScribeError(f"Failed to read file '{file_path_str}': {e}")

    def _resolve_variables(self, agent_name: str, extra_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resolves and merges global and agent-specific variables.

        Args:
            agent_name: The name of the agent.
            extra_context: Additional context to pass to substitution, like settings.

        Returns:
            A dictionary of resolved variables.
        """
        agent_config = self.config.get("agents", {}).get(agent_name, {})
        global_vars = self.config.get("variables", {}).copy()
        agent_vars = agent_config.get("variables", {}).copy()

        # 1. Merge basic variables
        merged_vars = {**global_vars, **agent_vars}

        # 2. Inject system variables EARLY so they can be used in other variables
        merged_vars['_agent_name'] = agent_name

        # 3. Inject extra context (like _settings) if provided
        if extra_context:
            for key, value in extra_context.items():
                merged_vars[key] = value

        # 4. Eagerly resolve all string variables.
        # We use a fresh dictionary for the final resolved values.
        # We pass 'merged_vars' as context so variables can refer to each other.
        final_vars = {}
        for key, value in merged_vars.items():
            if isinstance(value, str):
                # Recursively resolve the value using the full merged context
                final_vars[key] = self._substitute_variables(value, merged_vars)
            else:
                final_vars[key] = value

        return final_vars

    def _substitute_variables(self, text: str, variables: Dict[str, Any], depth: int = 0) -> str:
        """
        Recursively substitutes {{ VAR }} placeholders in the text.

        Args:
            text: The string to perform substitutions on.
            variables: A dictionary of available variables.
            depth: The current recursion depth to prevent infinite loops.

        Returns:
            Text with placeholders replaced by their values.
        """
        if depth > MAX_SUBSTITUTION_DEPTH:
            raise PromptScribeError("Maximum substitution depth exceeded. Check for circular references.")

        # CORRECTED REGEX using VERBOSE mode for readability and safety.
        # It matches either:
        # 1. include('path') or include_raw('path')
        # 2. {{ VAR_NAME }}
        pattern = re.compile(r"""
            include(?P<raw>_raw)?\((['"])(?P<path>.*?)\2\)|  # Group: include func
            \{\{\s*(?P<var>[a-zA-Z0-9_]+)\s*\}\}                     # Group: variable
        """, re.VERBOSE)

        substitute_in_includes = variables.get('_settings', {}).get('substitute_in_includes', True)

        def replacer(match):
            # Case 1: include(...) matched
            if match.group('path') is not None:
                is_raw = bool(match.group('raw'))
                raw_path = match.group('path')
                
                # Recursively resolve variables inside the path itself (e.g. include('{{ my_doc }}'))
                file_path = self._substitute_variables(raw_path, variables, depth + 1)
                
                agent_name = variables.get('_agent_name', '')
                content = self._read_file_content(file_path, agent_name)

                if is_raw or not substitute_in_includes:
                    return content
                # If not raw, recursively substitute variables inside the included content
                return self._substitute_variables(content, variables, depth + 1)

            # Case 2: {{ VAR }} matched
            elif match.group('var') is not None:
                var_name = match.group('var')
                if var_name in variables:
                    value = variables[var_name]
                    # Recursively resolve the variable's value
                    return self._substitute_variables(str(value), variables, depth + 1)
                # Check the warn_on_missing setting before showing warning
                if variables.get('_settings', {}).get('warn_on_missing', True):
                    ui.warning(f"Variable '{var_name}' found in text but not in config. Leaving it untouched.")
                return match.group(0)

            return match.group(0)

        return pattern.sub(replacer, text)

    def _run_simple_assembly(self, agent_config: dict, variables: dict, agent_name: str) -> str:
        """
        Builds the prompt from a sequence of assembly steps.

        Args:
            agent_config: The configuration for the specific agent.
            variables: The resolved variables for the agent.
            agent_name: The name of the agent being composed.

        Returns:
            The fully assembled prompt as a string.
        """
        parts = []
        assembly_steps = agent_config.get('assembly', [])
        substitute_in_includes = variables.get('_settings', {}).get('substitute_in_includes', True)

        for step in assembly_steps:
            if not isinstance(step, dict) or not step:
                continue
            
            key, value = next(iter(step.items()))
            
            # Explicit 'include' key support (legacy but useful for clarity)
            if key == 'include' or key == 'include_raw':
                # Resolve the path (it might be a variable like '{{ rules }}')
                resolved_path = self._substitute_variables(str(value), variables)
                file_content = self._read_file_content(resolved_path, agent_name)
                
                if key == 'include' and substitute_in_includes:
                    parts.append(self._substitute_variables(file_content, variables))
                else:
                    parts.append(file_content)

            # 'content', 'separator', 'h1'...'h6' support
            else:
                # Everything else goes through generic substitution.
                # This enables include('...') inside 'content' automatically.
                processed_value = self._substitute_variables(str(value), variables)

                if key == 'content':
                    parts.append(processed_value)
                elif key == 'separator':
                    parts.append(processed_value)
                elif key.startswith('h') and key[1:].isdigit():
                    level = int(key[1:])
                    parts.append(f"{'#' * level} {processed_value}")
        
        return "\n\n".join(p.strip() for p in parts if p)

    def get_reverse_dependencies(self) -> Dict[Path, List[str]]:
        """
        Generates a reverse mapping from file paths to agent names that depend on them.

        Returns:
            A dictionary where keys are file paths and values are lists of agent names.
        """
        reverse_deps: Dict[Path, List[str]] = {}
        for agent_name, file_paths in self.dependencies.items():
            for file_path in file_paths:
                if file_path not in reverse_deps:
                    reverse_deps[file_path] = []
                reverse_deps[file_path].append(agent_name)
        return reverse_deps

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

        self.dependencies[agent_name] = {self.config_path}
        ui.title(f"Composing agent: '{agent_name}'")

        # Determine if warnings should be shown for this agent (global > local)
        settings = self.config.get("settings", {})
        warn_setting = agent_config.get(
            'warn_on_missing_variables', 
            settings.get('warn_on_missing_variables', True)
        )
        
        # Determine if variable substitution should happen in included files for this agent (global > local)
        substitute_in_includes_setting = agent_config.get(
            'substitute_in_included_files', 
            settings.get('substitute_in_included_files', True)
        )
        
        # Prepare extra context with settings for _resolve_variables
        extra_context = {
            '_settings': {
                'warn_on_missing': warn_setting,
                'substitute_in_includes': substitute_in_includes_setting
            }
        }
        
        # 1. Resolve variables (now includes _agent_name and settings for substitution)
        variables = self._resolve_variables(agent_name, extra_context)
        
        final_prompt = ""

        # 2. Composition Mode
        if 'assembly' in agent_config:
            ui.info("Using simple assembly mode.")
            final_prompt = self._run_simple_assembly(agent_config, variables, agent_name)
        else:
            ui.info("Using Jinja2 template mode.")
            # ... (Jinja2 setup code) ...
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
                ui.error(f"Agent '{agent_name}' missing template definition.")
                raise PromptScribeError(f"Agent '{agent_name}' missing template.")

            templates_dir = self._resolve_path(settings.get("templates_dir", "templates"))
            env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates_dir)), autoescape=False)
            
            # Jinja2 helpers that match our new internal logic
            substitute_in_includes = variables.get('_settings', {}).get('substitute_in_includes', True)
            env.globals['read_file'] = lambda p: self._substitute_variables(self._read_file_content(p, agent_name), variables) if substitute_in_includes else self._read_file_content(p, agent_name)
            env.globals['read_file_raw'] = lambda p: self._read_file_content(p, agent_name)

            try:
                self.dependencies[agent_name].add((templates_dir / template_name).resolve())
                final_prompt = env.get_template(template_name).render(variables)
            except Exception as e:
                ui.error(f"Jinja2 rendering failed: {e}")
                raise PromptScribeError(f"Jinja2 rendering failed: {e}")

        # 3. Output File Determination (CORRECTED PRIORITY)
        output_dir = self._resolve_path(self._substitute_variables(settings.get("output_dir", "composed_prompts"), variables))
        
        # Priority: Local > Global > Default
        output_file_template = agent_config.get('output_file') or settings.get('output_file')

        if output_file_template:
            output_file_name = self._substitute_variables(output_file_template, variables)
            if '/' in output_file_name or '\\' in output_file_name:
                 output_file_path = self._resolve_path(output_file_name)
            else:
                 output_file_path = output_dir / output_file_name
        else:
            output_file_path = output_dir / f"{agent_name}.md"

        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        output_file_path.write_text(final_prompt, encoding="utf-8")

        ui.success(f"Successfully composed prompt for '{agent_name}' -> '{output_file_path.relative_to(Path.cwd())}'")
