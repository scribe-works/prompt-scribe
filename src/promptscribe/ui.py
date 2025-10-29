"""
promptscribe.ui
~~~~~~~~~~~~~~~

This module provides a centralized, theme-based interface for all CLI output,
ensuring visual consistency and clean, readable code across the application.

It is built on top of the 'rich' library and introduces an intelligent,
automatic variable highlighting system to replace manual BBCode styling.

Principles:
1.  Centralization: All CLI output should go through this module.
2.  Semantic Themes: Use themes like `ui.success()` or `ui.error()`
    instead of specifying colors directly.
3.  Automatic Highlighting: Variables (strings in quotes) are
    automatically highlighted, keeping the calling code clean.

@copyright: (c) 2025 by The Scribe Works.
"""

import re
import sys
from typing import Dict, Any

from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# --- Theme Definitions ---

# Defines the visual properties for different types of CLI messages.
# 'accent' is used for variable highlighting.
# 'line' is used when `highlight_entire_line` is True.
THEME_CONFIG_UNICODE: Dict[str, Dict[str, Any]] = {
    "success": {
        "prefix": "✅ ",
        "accent": Style(color="green", bold=False), # Bold can distort colors
        "line": Style(color="green"),
    },
    "error": {
        "prefix": "❌ ",
        "accent": Style(color="red", bold=True),
        "line": Style(color="red"),
    },
    "warning": {
        "prefix": "⚠️ ",
        "accent": Style(color="yellow"),
        "line": Style(color="yellow"),
    },
    "info": {
        "prefix": "ℹ️ ",
        "accent": Style(color="cyan"),
        "line": Style(color="cyan"),
    },
    "title": {
        "prefix": "",
        "accent": Style(bold=True), # Default accent for titles
        "line": Style(bold=True),
    },
}

# Alternative theme configuration for terminals that don't support Unicode
THEME_CONFIG_ASCII: Dict[str, Dict[str, Any]] = {
    "success": {
        "prefix": "[SUCCESS] ",
        "accent": Style(color="green", bold=False),
        "line": Style(color="green"),
    },
    "error": {
        "prefix": "[ERROR] ",
        "accent": Style(color="red", bold=True),
        "line": Style(color="red"),
    },
    "warning": {
        "prefix": "[WARNING] ",
        "accent": Style(color="yellow"),
        "line": Style(color="yellow"),
    },
    "info": {
        "prefix": "[INFO] ",
        "accent": Style(color="cyan"),
        "line": Style(color="cyan"),
    },
    "title": {
        "prefix": "",
        "accent": Style(bold=True),
        "line": Style(bold=True),
    },
}

# --- Default Styles for Complex Components ---

DEFAULT_TABLE_STYLE: Dict[str, Any] = {
    "show_header": True,
    "header_style": "bold magenta",
    "border_style": "dim",
}

DEFAULT_PANEL_STYLE: Dict[str, Any] = {
    "border_style": "dim",
}

DEFAULT_SYNTAX_STYLE: Dict[str, Any] = {
    "theme": "github-dark",
    "line_numbers": False,
    "word_wrap": True,
}

DEFAULT_PROGRESS_STYLE = (
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    TimeRemainingColumn(),
)


class VariableHighlighter(RegexHighlighter):
    """Highlights variables (text in quotes) within a string."""
    # Explicitly define the 'style' attribute with a type hint and a default value.
    style: Style = Style()
    
    highlights = [
        r"(?P<quotes>[\"'])(?P<variable>.*?)(?P=quotes)"
    ]

    def highlight(self, text: Text) -> None:
        """
        Applies highlighting to the matched text.
        We override the default method to apply the style only to the 'variable' group.
        """
        # The 'self.style' will be set on the instance by the UIManager before this is called.
        for pattern in self.highlights:
            for match in re.finditer(pattern, text.plain):
                if "variable" in match.groupdict():
                    text.stylize(self.style, *match.span("variable"))


class UIManager:
    """Manages all CLI output for the application."""

    def __init__(self):
        self._console = Console()
        # Determine if the terminal supports Unicode characters
        self._supports_unicode = self._check_unicode_support()
        # Select the appropriate theme configuration
        self._theme_config = THEME_CONFIG_UNICODE if self._supports_unicode else THEME_CONFIG_ASCII

    def _check_unicode_support(self) -> bool:
        """
        Determines if the current terminal/console supports Unicode characters.
        
        Returns:
            bool: True if Unicode is supported, False otherwise.
        """
        # Check if we're on Windows with legacy console
        if self._console.legacy_windows:
            return False
        
        # Check the encoding - if it's not UTF-8 compatible, assume no Unicode support
        encoding = getattr(sys.stdout, 'encoding', None)
        if not encoding:
            # If we can't determine the encoding, assume it's not Unicode compatible
            return False
        
        # Check if the encoding is UTF-8 or another Unicode encoding
        if 'utf' in encoding.lower():
            return True
        
        # For other encodings (like cp1251 in your case), assume no Unicode support
        return False

    def _print_themed(
        self,
        message: str,
        theme_name: str,
        highlight_entire_line: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Internal method to print a message with a specific theme.

        Args:
            message: The string message to print.
            theme_name: The key of the theme in THEME_CONFIG.
            highlight_entire_line: If True, the entire line gets the theme's
                                   line color. Otherwise, only variables are
                                   highlighted with the accent color.
        """
        if theme_name not in self._theme_config:
            self._console.print(message, **kwargs)
            return

        theme = self._theme_config[theme_name]
        prefix = theme.get("prefix", "")

        # Set up the highlighter with the theme's accent color
        highlighter = VariableHighlighter()
        highlighter.style = theme["accent"]

        # Apply the line style if requested
        style = theme["line"] if highlight_entire_line else Style()

        full_message = Text(f"{prefix}{message}", style=style)

        # Print using the console's highlight mechanism
        self._console.print(highlighter(full_message), **kwargs)

    # --- Public API for Simple Messages ---

    def success(self, message: str, **kwargs: Any) -> None:
        """Prints a success message."""
        self._print_themed(message, "success", **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Prints an error message."""
        self._print_themed(message, "error", highlight_entire_line=True, **kwargs)

    def warning(self, message: str, highlight_entire_line: bool = False, **kwargs: Any) -> None:
        """Prints a warning message."""
        self._print_themed(message, "warning", highlight_entire_line=highlight_entire_line, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Prints an informational message."""
        self._print_themed(message, "info", **kwargs)

    def title(self, message: str, **kwargs: Any) -> None:
        """Prints a title or section header."""
        self._print_themed(message, "title", highlight_entire_line=True, **kwargs)
    
    def code(self, code_string: str, language: str = "bash", **kwargs: Any) -> None:
        """
        Prints a styled code block directly to the console.
        This is a convenience wrapper around create_syntax and render.
        """
        syntax_block = self.create_syntax(code_string, language, **kwargs)
        self.render(syntax_block)

    # --- Public API for Complex Components (Factories) ---

    def create_table(self, *headers: str, **kwargs: Any) -> Table:
        """
        Creates a rich.Table with default application styling.
        Allows overriding defaults via kwargs.
        """
        style_args = DEFAULT_TABLE_STYLE.copy()
        style_args.update(kwargs)
        return Table(*headers, **style_args)

    def create_panel(self, renderable: Any, **kwargs: Any) -> Panel:
        """
        Creates a rich.Panel with default application styling.
        Allows overriding defaults via kwargs.
        """
        style_args = DEFAULT_PANEL_STYLE.copy()
        style_args.update(kwargs)
        return Panel(renderable, **style_args)

    def create_syntax(self, code: str, lexer_name: str, **kwargs: Any) -> Syntax:
        """
        Creates a rich.Syntax object with default application styling.
        Allows overriding defaults via kwargs.
        """
        style_args = DEFAULT_SYNTAX_STYLE.copy()
        style_args.update(kwargs)
        return Syntax(code, lexer_name, **style_args)
    
    def create_progress(self, **kwargs: Any) -> Progress:
        """
        Creates a rich.Progress with default application styling.
        Allows overriding defaults via kwargs.
        """
        # Start with the default columns
        columns = list(DEFAULT_PROGRESS_STYLE)

        # Create a Progress instance with the merged arguments
        return Progress(*columns, console=self._console, **kwargs)

    # --- Universal Render Method ---

    def render(self, renderable: Any, **kwargs: Any) -> None:
        """
        Prints any rich-compatible renderable object to the console.
        This is the preferred way to output complex components.
        """
        self._console.print(renderable, **kwargs)


# --- Singleton Instance ---
# All application code should import and use this single instance.
ui = UIManager()

# --- Public API Functions (for convenience) ---

success = ui.success
error = ui.error
warning = ui.warning
info = ui.info
title = ui.title
code = ui.code
create_table = ui.create_table
create_panel = ui.create_panel
create_syntax = ui.create_syntax
create_progress = ui.create_progress
render = ui.render