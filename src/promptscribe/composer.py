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
from typing import Any, Callable, Dict, List

import jinja2
import yaml
from markdown_it import MarkdownIt
from mdformat.renderer import MDRenderer

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
            raise PromptScribeError(
                f"Configuration file not found at '{self.config_path}'"
            )
        self.base_dir = self.config_path.parent
        self.config = self._load_config()
        self.dependencies: Dict[str, set] = {}  # agent -> {file_path}

        # Initialize Markdown tools once for efficiency
        self.md_parser = MarkdownIt()
        self.md_renderer = MDRenderer()

        # Substitution context for the shared Jinja environment.
        # This dictionary will be updated before each substitution call to provide
        # a file path context to the WarningUndefined handler.
        self._subst_context = {"file_path": None, "warn": True}
        
        # Capture 'self' for use within the nested class, allowing the Undefined handler
        # to access the composer instance's dynamic context.
        composer_instance = self
        class WarningUndefined(jinja2.Undefined):
            """Custom Undefined class to show contextual warnings but not crash."""
            def __str__(self):
                context = composer_instance._subst_context
                if context["warn"]:
                    location = f" (in file '{context['file_path']}')" if context['file_path'] else ""
                    ui.warning(f"Variable '{self._undefined_name}' is not defined in 'prompts.yml'{location}. Leaving it untouched.")
                return f"{{{{ {self._undefined_name} }}}}"
        
        # A single, reusable Jinja2 environment for all string substitutions.
        # Its 'undefined' handler is configured to use the dynamic context from '_subst_context'.
        self.subst_env = jinja2.Environment(undefined=WarningUndefined, autoescape=False)

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

    def _process_markdown_content(self, content: str, fit_level: int) -> str:
        """
        Analyzes Markdown content, shifts heading levels to fit a target level,
        and renders it back to a Markdown string.

        Args:
            content: The Markdown content to process.
            fit_level: The target level for the highest heading in the content.

        Returns:
            The processed Markdown content with adjusted headings.
        """
        tokens = self.md_parser.parse(content)

        highest_level_found = 7
        for token in tokens:
            if token.type == 'heading_open':
                current_level = int(token.tag[1:])
                highest_level_found = min(highest_level_found, current_level)

        if highest_level_found == 7:
            return content

        shift_delta = fit_level - highest_level_found
        if shift_delta == 0:
            return content

        for token in tokens:
            if token.type in ('heading_open', 'heading_close'):
                current_level = int(token.tag[1:])
                new_level = min(max(1, current_level + shift_delta), 6)
                token.tag = f'h{new_level}'
                if token.markup and (token.markup.startswith('#') or token.markup in ('=', '-')):
                    token.markup = '#' * new_level

        return self.md_renderer.render(tokens, self.md_parser.options, {})

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

        merged_vars = {**global_vars, **agent_vars}
        merged_vars['_agent_name'] = agent_name
        if extra_context:
            merged_vars.update(extra_context)

        final_vars = {}
        for key, value in merged_vars.items():
            if isinstance(value, str):
                final_vars[key] = self._substitute_variables(
                    value, merged_vars
                )
            else:
                final_vars[key] = value

        return final_vars

    def _get_and_process_file_content(self, path: str, agent_name: str, **kwargs: Any) -> str:
        """
        Core helper to read and apply initial processing to a file's content.
        This is the single source of truth for file reading logic.
        """        
        # Step 1: Read the file content
        content = self._read_file_content(path, agent_name)
        
        # Step 2: Apply heading processing if requested
        fit_level = kwargs.get('fit_headings')
        if fit_level is not None:
            content = self._process_markdown_content(content, int(fit_level))
            
        return content

    def _get_jinja_helpers(self, agent_name: str, variables: Dict[str, Any]) -> Dict[str, Callable]:
        """
        A factory that creates and returns file reading helper functions
        for a Jinja2 environment. This centralizes the logic and avoids code duplication.
        """
        def read_file_wrapper(path: str, **kwargs: Any) -> str:
            """Reads, processes, and substitutes variables in a file."""
            if isinstance(path, jinja2.Undefined):
                ui.warning(f"Path variable '{path._undefined_name}' is not defined in 'prompts.yml'. Skipping file read.")
                return ""
            
            if not isinstance(path, str) or not path.strip():
                ui.warning(f"Invalid path provided to 'read_file': '{path}'. Skipping file read.")
                return ""
            
            content = self._get_and_process_file_content(path, agent_name, **kwargs)
            substitute = variables.get('_settings', {}).get('substitute_in_includes', True)
            if substitute:
                return self._substitute_variables(content, variables, file_path_context=path)
            return content
        
        def read_file_raw_wrapper(path: str, **kwargs: Any) -> str:
            """Reads and processes a file, but skips variable substitution."""
            if isinstance(path, jinja2.Undefined):
                ui.warning(f"Path variable '{path._undefined_name}' is not defined in 'prompts.yml'. Skipping file read.")
                return ""
            
            if not isinstance(path, str) or not path.strip():
                ui.warning(f"Invalid path provided to 'read_file_raw': '{path}'. Skipping file read.")
                return ""
               
            return self._get_and_process_file_content(path, agent_name, **kwargs)

        return {
            'read_file': read_file_wrapper,
            'read_file_raw': read_file_raw_wrapper,
        }
    
    def _substitute_variables(self, text: str, variables: Dict[str, Any], file_path_context: str = None) -> str:
        """
        Renders a string using a shared, reusable Jinja2 environment for performance.
        It allows for consistent variable and function syntax (e.g., {{ my_var }},
        {{ read_file(...) }}) across all parts of the configuration.
        """
        # Configure the context for the shared environment's undefined handler
        self._subst_context["file_path"] = file_path_context
        self._subst_context["warn"] = variables.get('_settings', {}).get('warn_on_missing', True)

        # Helpers need to be updated for each call as they depend on the variable context
        helpers = self._get_jinja_helpers(variables.get('_agent_name', ''), variables)
        self.subst_env.globals.update(helpers)

        try:
            template = self.subst_env.from_string(text)
            return template.render(variables)
        except (jinja2.TemplateError, TypeError) as e:
            ui.error(f"Error during string substitution: {e}")
            return text  # Return original text on failure

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

        for step in assembly_steps:
            if not isinstance(step, dict) or not step:
                continue
            key, value = next(iter(step.items()))

            if key == 'include' or key == 'include_raw':
                path, fit_level = "", None
                is_raw = (key == 'include_raw')

                if isinstance(value, dict):
                    path = value.get('path', '')
                    if not is_raw and (fit_level_val := value.get('fit_headings')):
                        fit_level = int(fit_level_val)
                elif isinstance(value, str):
                    path = value
                else:
                    # ИЗМЕНЕНО: Предупреждение о неверном типе значения
                    ui.warning(f"Invalid value for '{key}' step: '{value}'. Skipping.")
                    continue
                
                if not path:
                    # ИЗМЕНЕНО: Предупреждение о пустом пути до подстановки
                    ui.warning(f"Empty path provided to '{key}' step: '{value}'. Skipping.")
                    continue
                
                resolved_path = self._substitute_variables(path, variables)
                
                # ДОБАВЛЕНО: Проверка на случай, если путь стал пустым ПОСЛЕ подстановки
                if not resolved_path or not resolved_path.strip():
                    original_path_context = f" (from original path: '{path}')" if path != resolved_path else ""
                    ui.warning(f"Invalid path provided to '{key}' step{original_path_context}. Skipping.")
                    continue

                kwargs = {'fit_headings': fit_level} if fit_level is not None else {}
                file_content = self._get_and_process_file_content(resolved_path, agent_name, **kwargs)

                if not is_raw and variables.get('_settings', {}).get('substitute_in_includes', True):
                    # БЕЗ ИЗМЕНЕНИЙ: Использование file_path_context, как в вашем коде
                    parts.append(self._substitute_variables(file_content, variables, file_path_context=resolved_path))
                else:
                    parts.append(file_content)
            else:
                # All other keys (content, h1, etc.) are processed by the Jinja-powered substituter
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

    def analyze_dependencies(self) -> None:
        """Runs a dry run of all agents to populate the dependency map."""
        for agent_name in self.get_all_agent_names():
            try:
                self.compose_agent(agent_name, dry_run=True)
            except PromptScribeError as e:
                # In a dry run, we can tolerate some errors, but we should warn.
                ui.warning(f"Could not fully analyze dependencies for agent '{agent_name}': {e}")

    def get_all_dependencies(self) -> set[Path]:
        """Returns a set of all unique file paths that agents depend on."""
        all_deps = set()
        for deps in self.dependencies.values():
            all_deps.update(deps)
        return all_deps

    def compose_agent(self, agent_name: str, dry_run: bool = False) -> None:
        """
        Composes and saves the prompt for a single agent.

        Args:
            agent_name: The name of the agent to compose.
            dry_run: If True, populates dependencies without writing files.
        """
        agent_config = self.config.get("agents", {}).get(agent_name)
        if not agent_config:
            ui.error(f"Agent '{agent_name}' not found in configuration.")
            raise PromptScribeError(f"Agent '{agent_name}' not found in configuration.")

        self.dependencies[agent_name] = {self.config_path}
        ui.title(f"Composing agent: '{agent_name}'")

        settings = self.config.get("settings", {})
        extra_context = {
            '_settings': {
                'warn_on_missing': agent_config.get(
                    'warn_on_missing_variables', settings.get('warn_on_missing_variables', True)
                ),
                'substitute_in_includes': agent_config.get(
                    'substitute_in_included_files', settings.get('substitute_in_included_files', True)
                )
            }
        }
        variables = self._resolve_variables(agent_name, extra_context)
        final_prompt = ""

        if 'assembly' in agent_config:
            ui.info("Using simple assembly mode.")
            final_prompt = self._run_simple_assembly(agent_config, variables, agent_name)
        else:
            ui.info("Using Jinja2 template mode.")
            template_path_str = agent_config.get('template') or settings.get('template')

            if not template_path_str:
                ui.error(f"Agent '{agent_name}' missing template definition.")
                raise PromptScribeError(f"Agent '{agent_name}' missing template.")

            template_name = self._substitute_variables(template_path_str, variables)
            ui.info(f"Using template: '{template_name}'")

            templates_dir = self._resolve_path(settings.get("templates_dir", "templates"))
            env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates_dir)), autoescape=False)
            
            helpers = self._get_jinja_helpers(agent_name, variables)
            env.globals.update(helpers)

            try:
                self.dependencies[agent_name].add((templates_dir / template_name).resolve())
                final_prompt = env.get_template(template_name).render(variables)
            except Exception as e:
                ui.error(f"Jinja2 rendering failed: {e}")
                raise PromptScribeError(f"Jinja2 rendering failed: {e}")

        if not dry_run:
            output_dir_template = settings.get("output_dir", "composed_prompts")
            output_dir = self._resolve_path(self._substitute_variables(output_dir_template, variables))
            
            output_file_template = agent_config.get('output_file') or settings.get('output_file')
            if output_file_template:
                output_file_name = self._substitute_variables(output_file_template, variables)
                output_file_path = self._resolve_path(output_file_name) if ('/' in output_file_name or '\\' in output_file_name) else (output_dir / output_file_name)
            else:
                output_file_path = output_dir / f"{agent_name}.md"

            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            output_file_path.write_text(final_prompt, encoding="utf-8")

            ui.success(f"Successfully composed prompt for '{agent_name}' -> '{output_file_path.relative_to(Path.cwd())}'")