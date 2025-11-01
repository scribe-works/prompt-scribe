"""
promptscribe.cli
~~~~~~~~~~~~~~~~

This module provides the command-line interface for Prompt Scribe,
powered by Typer. It exposes commands for initializing a project,
composing prompts, and watching for file changes.

@copyright: (c) 2025 by The Scribe Works.
"""
import os
import sys
import queue
import time
from importlib import resources
from pathlib import Path
from typing import List
from contextlib import contextmanager

import typer
from typing_extensions import Annotated
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .composer import PromptComposer, PromptScribeError
from .ui import ui

app = typer.Typer(
    name="prompt-scribe",
    help="A powerful, template-based prompt composer for crafting and managing complex instructions for LLMs.",
    add_completion=False,
)


@app.command()
def init(
    path: Annotated[Path, typer.Argument(
        help="The directory to initialize the project in. Defaults to '.prompt_scribe' in the current directory."
    )] = Path(".prompt_scribe"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files if the directory is not empty.",
        rich_help_panel="Customization",
    ),
    scaffold: str = typer.Option(
        "default", 
        "--scaffold", 
        "-s",
        help="The project scaffold to use (e.g., 'default', 'example', 'dev-kit'). Use --list-scaffolds to see all available options.",
        rich_help_panel="Customization",
    ),
    list_scaffolds: bool = typer.Option(
        False,
        "--list-scaffolds",
        help="List all available scaffolds and exit.",
        rich_help_panel="Customization",
    )
):
    """
    Initializes a new Prompt Scribe project with a specified scaffold structure.
    """
    # Discover available scaffolds dynamically
    scaffolds_path = resources.files("promptscribe") / "scaffolds"
    available_scaffolds = []
    if scaffolds_path.is_dir():
        for item in scaffolds_path.iterdir():
            if item.is_dir():
                available_scaffolds.append(item.name)
    
    # If user wants to list scaffolds, show them and exit
    if list_scaffolds:
        if available_scaffolds:
            ui.title("Available scaffolds:")
            for scaffold_name in available_scaffolds:
                print(f"  - {scaffold_name}")
        else:
            ui.info("No scaffolds found.")
        return

    # Validate scaffold option
    if scaffold not in available_scaffolds:
        ui.error(f"Unknown scaffold '{scaffold}'. Available scaffolds: {available_scaffolds}")
        raise typer.Exit(code=1)
    
    ui.title(f"Initializing Prompt Scribe project using '{scaffold}' scaffold...")
    
    base_path = path.resolve()
    
    # For backward compatibility and consistency:
    # - If the default path (".prompt_scribe") is used, create structure directly in that directory
    # - If a custom path is specified, create a ".prompt_scribe" subdirectory within that path
    if path == Path(".prompt_scribe"):
        project_path = base_path
    else:
        project_path = base_path / ".prompt_scribe"
        base_path.mkdir(exist_ok=True)
    
    project_path.mkdir(exist_ok=True)
    
    # Create standard directories unconditionally for all scaffolds
    dirs = ["personas", "includes", "templates"]
    for d in dirs:
        (project_path / d).mkdir(exist_ok=True)
    
    # Copy template files from the specified scaffold
    scaffold_path = resources.files("promptscribe") / "scaffolds" / scaffold
    
    # If the scaffold directory exists, copy all its contents recursively
    if (scaffold_path).is_dir():
        # Copy all scaffold contents to the target project directory
        scaffold_source = scaffold_path
        for item in scaffold_source.rglob("*"):
            if item.is_file():
                # Calculate the relative path from the scaffold directory
                rel_path = item.relative_to(scaffold_source)
                dest_path = project_path / rel_path
                
                # Check if destination file already exists
                if dest_path.exists() and not force:
                    ui.info(f"Skipping existing file: {dest_path.relative_to(Path.cwd())}")
                    continue
                
                # Ensure parent directory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file content
                source_content = item.read_text(encoding="utf-8")
                dest_path.write_text(source_content, encoding="utf-8")
    else:
        # Fallback to old behavior for backward compatibility if needed
        ui.error(f"Scaffold '{scaffold}' not found.")
        raise typer.Exit(code=1)

    ui.success(f"Project initialized at '{project_path}' using '{scaffold}' scaffold")
    ui.info(f"Next steps: customize '{project_path / 'prompts.yml'}' and run 'prompt-scribe compose'")


def _compose_agents(composer: PromptComposer, agent_names: List[str]):
    """Helper function to compose a list of agents."""
    target_agents = agent_names or composer.get_all_agent_names()
    if not target_agents:
        ui.warning("No agents found in configuration. Nothing to compose.")
        return

    for agent_name in target_agents:
        try:
            composer.compose_agent(agent_name)
        except PromptScribeError as e:
            ui.error(f"Error composing agent '{agent_name}': {e}")
            raise typer.Exit(1)


class ChangeHandler(FileSystemEventHandler):
    """Handles file system events and triggers recomposition."""

    def __init__(self, composer: PromptComposer, agent_names: List[str], restart_queue: queue.Queue):
        self.composer = composer
        self.agent_names = agent_names
        self.reverse_dependencies = composer.get_reverse_dependencies()
        self.restart_queue = restart_queue
        
        # Debouncing mechanism
        self.last_event_time = 0
        self.debounce_interval = 0.5  # seconds
    
    def on_any_event(self, event):
        current_time = time.time()
        if (current_time - self.last_event_time) < self.debounce_interval:
            return
        self.last_event_time = current_time

        if event.is_directory or event.event_type not in ['modified', 'created', 'deleted']:
            return
        
        src_path = Path(event.src_path).resolve()
        
        # Ignore events in the output directory
        settings = self.composer.config.get("settings", {})
        output_dir_str = settings.get("output_dir", "composed_prompts")
        output_path = self.composer._resolve_path(output_dir_str)
        if src_path.is_relative_to(output_path):
            return

        ui.info(f"Change detected in '{src_path.relative_to(Path.cwd())}'.")

        try:
            if src_path == self.composer.config_path:
                self.handle_config_change()
            else:
                self.handle_dependency_change(src_path)
        except Exception as e:
            ui.error(f"An error occurred during recomposition: {e}")

    def handle_dependency_change(self, src_path: Path):
        """Handle changes in included files, templates, etc."""
        affected_agents = self.reverse_dependencies.get(src_path)
        if affected_agents:
            ui.info(f"Recomposing affected agents: {', '.join(affected_agents)}")
            # Reload config to catch potential variable changes that affect includes
            fresh_composer = PromptComposer(str(self.composer.config_path))
            _compose_agents(fresh_composer, affected_agents)
        else:
            # If the file is not a direct dependency, just ignore it.
            # This prevents unnecessary recomposition.
            ui.info(f"Change in '{src_path.relative_to(Path.cwd())}' does not affect any known agents. Skipping.")


    def handle_config_change(self):
        """Handle changes in the main prompts.yml file."""
        ui.info("Configuration file changed. Analyzing changes...")

        # 1. Get current watch paths
        old_deps = self.composer.get_all_dependencies()
        old_watch_dirs = {p.parent for p in old_deps}

        # 2. Create a new composer and analyze new dependencies
        fresh_composer = PromptComposer(str(self.composer.config_path))

        with suppress_stdout():
            fresh_composer.analyze_dependencies()
        
        new_deps = fresh_composer.get_all_dependencies()
        new_watch_dirs = {p.parent for p in new_deps}

        # First, determine what needs to be rebuilt, regardless of whether paths change
        agents_to_rebuild = self.find_changed_agents(self.composer.config, fresh_composer.config)
        
        if agents_to_rebuild:
            ui.info(f"Recomposing agents affected by config change: {', '.join(agents_to_rebuild)}")
            _compose_agents(fresh_composer, list(agents_to_rebuild))
        else:
            ui.info("No effective changes detected in agent configurations.")

        # 3. Compare watch paths AND ONLY THEN decide if the watcher needs to be restarted
        if old_watch_dirs != new_watch_dirs:
            ui.info("Watch paths have changed. Signaling for watcher restart.")
            self.restart_queue.put(fresh_composer)
        else:
            # If paths haven't changed, just update the handler's state
            ui.info("Watch paths remain the same.")
            self.composer = fresh_composer
            self.reverse_dependencies = fresh_composer.get_reverse_dependencies()

    def find_changed_agents(self, old_config: dict, new_config: dict) -> set:
        """Compares two config dictionaries to find which agents need rebuilding."""
        agents_to_rebuild = set()
        
        # Global changes trigger a full rebuild of all relevant agents
        if old_config.get('settings') != new_config.get('settings') or \
           old_config.get('variables') != new_config.get('variables'):
            ui.info("Global settings or variables changed. Rebuilding all specified agents.")
            return set(self.agent_names or new_config.get("agents", {}).keys())

        # Agent-specific changes
        old_agents = old_config.get('agents', {})
        new_agents = new_config.get('agents', {})
        all_agent_keys = set(old_agents.keys()) | set(new_agents.keys())
        
        for name in all_agent_keys:
            # If specific agents were requested, only check them
            if self.agent_names and name not in self.agent_names:
                continue
            if old_agents.get(name) != new_agents.get(name):
                agents_to_rebuild.add(name)
        
        return agents_to_rebuild


def _run_watcher(composer: PromptComposer, agent_names: List[str]):
    """Sets up and runs a SINGLE watcher instance.
    Returns a new composer instance if a restart is needed, otherwise None.
    """
    restart_queue = queue.Queue()
    dependencies = composer.get_all_dependencies()
    watch_paths = {p.parent for p in dependencies}

    handler = ChangeHandler(composer, agent_names, restart_queue)
    observer = Observer()
    
    if not watch_paths:
        ui.warning("No dependencies found to watch. Watching only the config file's directory.")
        watch_paths.add(composer.base_dir)

    for path in watch_paths:
        observer.schedule(handler, str(path), recursive=True)
    
    observer.start()
    ui.info(f"Watching for changes in {len(watch_paths)} directories... Press Ctrl+C to stop.")
    try:
        # Block until a restart is signaled
        new_composer = restart_queue.get()
        
        ui.info("Signaled for watcher restart...")
        return new_composer  # Return the new composer to the controlling loop

    except KeyboardInterrupt:
        ui.info("Stopping watcher...")
        return None  # Signal to the controlling loop to exit
    finally:
        if observer.is_alive():
            observer.stop()
            observer.join()
        ui.info("Watcher stopped.")


@contextmanager
def suppress_stdout():
    """A context manager that redirects stdout to devnull using UTF-8 encoding."""
    original_stdout = sys.stdout
    with open(os.devnull, 'w', encoding="utf-8") as devnull:
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = original_stdout


@app.command()
def compose(
    agent_names: Annotated[List[str], typer.Argument(help="Specific agent(s) to compose. If empty, all agents will be composed.")] = None,
    config_path: Annotated[Path, typer.Option("--config", "-c", help="Path to the prompts.yml configuration file or directory containing the project structure. Defaults to '.prompt_scribe/prompts.yml'. Use this option when your project was initialized in a custom location.")] = Path(".prompt_scribe/prompts.yml"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch for file changes and recompose automatically."),
):
    """
    Composes final prompt files from templates and includes.
    """
    # Handle case where user provides a directory path (like 'preview') instead of full config file path
    resolved_path = config_path.resolve()
    
    # If the path is a directory, assume it contains the .prompt_scribe structure
    if resolved_path.is_dir():
        config_file_path = resolved_path / ".prompt_scribe" / "prompts.yml"
    else:
        config_file_path = resolved_path
    
    try:
        composer = PromptComposer(str(config_file_path))
    except FileNotFoundError:
        ui.error(f"Configuration file '{config_file_path}' not found.")
        ui.info("Did you forget to run 'prompt-scribe init'? You can also specify a custom config path with --config/-c.")
        raise typer.Exit(code=1)

    _compose_agents(composer, agent_names or [])

    if watch:
        ui.info("Initial dependency analysis for watch mode...")
        with suppress_stdout():
            composer.analyze_dependencies()

        current_composer = composer
        
        while current_composer:
            current_composer = _run_watcher(current_composer, agent_names or [])
        
        ui.info("Watcher process finished.")