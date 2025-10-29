"""
promptscribe.cli
~~~~~~~~~~~~~~~~

This module provides the command-line interface for Prompt Scribe,
powered by Typer. It exposes commands for initializing a project,
composing prompts, and watching for file changes.

@copyright: (c) 2025 by The Scribe Works.
"""
import time
from importlib import resources
from pathlib import Path
from typing import List

import typer
from typing_extensions import Annotated
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .composer import PromptComposer
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
    )
):
    """
    Initializes a new Prompt Scribe project with a default structure.
    """
    ui.title("Initializing Prompt Scribe project structure...")
    
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
    
    # Create subdirectories unconditionally
    dirs = ["personas", "includes", "templates", "composed_prompts"]
    for d in dirs:
        (project_path / d).mkdir(exist_ok=True)
        
    # Copy template files from the package
    template_files_path = resources.files("promptscribe") / "project_template"
    
    files_to_copy = {
        "prompts.yml": "prompts.yml",
        "master.jinja2": "templates/master.jinja2",
        "report.jinja2": "templates/report.jinja2",
        "code-reviewer.md": "personas/code-reviewer.md",
        "development-rules.md": "includes/development-rules.md",
        "source-data.json": "includes/source-data.json",
    }
    
    for source_name, dest_name in files_to_copy.items():
        dest_path = project_path / dest_name
        
        if dest_path.exists() and not force:
            ui.info(f"Skipping existing file: {dest_path.relative_to(Path.cwd())}")
            continue

        source_content = (template_files_path / source_name).read_text(encoding="utf-8")
        dest_path.parent.mkdir(exist_ok=True) # Ensure parent dir exists
        dest_path.write_text(source_content, encoding="utf-8")

    ui.success(f"Project initialized at '{project_path}'")
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
        except Exception:
            # Errors are already printed by the composer, continue to next agent
            ui.error(f"Failed to compose agent '{agent_name}'. Please check the error messages above.")
            pass


class ChangeHandler(FileSystemEventHandler):
    """Handles file system events and triggers recomposition."""

    def __init__(self, composer: PromptComposer, agent_names: List[str]):
        self.composer = composer
        self.agent_names = agent_names
        settings = self.composer.config.get("settings", {})
        output_dir_str = settings.get("output_dir", "composed_prompts")
        self.output_path = self.composer._resolve_path(output_dir_str)
    
    def on_any_event(self, event):
        if event.is_directory or event.event_type not in ['modified', 'created', 'deleted']:
            return
        
        # CRITICAL: Ignore events happening inside the output directory
        src_path = Path(event.src_path).resolve()
        if src_path.is_relative_to(self.output_path):
            return

        ui.info(f"Change detected in '{src_path.relative_to(Path.cwd())}'. Recomposing...")
        try:
            # Re-create composer to reload the config if it changed
            fresh_composer = PromptComposer(str(self.composer.config_path))
            _compose_agents(fresh_composer, self.agent_names)
        except Exception as e:
            ui.error(f"An error occurred during recomposition: {e}")


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
        watch_path = composer.base_dir
        handler = ChangeHandler(composer, agent_names or [])
        observer = Observer()
        observer.schedule(handler, str(watch_path), recursive=True)
        
        observer.start()
        ui.info(f"Watching for changes in '{watch_path}'... Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
        ui.info("Watcher stopped.")