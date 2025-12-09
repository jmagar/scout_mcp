"""Colorful console logging formatter with EST timestamps."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

# ANSI color codes
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    # Foreground colors
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    # Bright foreground colors
    "bright_black": "\033[90m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
    # Background colors
    "bg_red": "\033[41m",
    "bg_green": "\033[42m",
    "bg_yellow": "\033[43m",
    "bg_blue": "\033[44m",
}

# Log level colors
LEVEL_COLORS = {
    "DEBUG": COLORS["bright_black"],
    "INFO": COLORS["bright_green"],
    "WARNING": COLORS["bright_yellow"],
    "ERROR": COLORS["bright_red"],
    "CRITICAL": COLORS["bg_red"] + COLORS["white"] + COLORS["bold"],
}

# Component colors for logger names
COMPONENT_COLORS = {
    "scout_mcp.server": COLORS["bright_cyan"],
    "scout_mcp.services.pool": COLORS["bright_magenta"],
    "scout_mcp.tools.scout": COLORS["bright_blue"],
    "scout_mcp.resources": COLORS["cyan"],
    "scout_mcp.middleware": COLORS["yellow"],
    "scout_mcp.config": COLORS["green"],
    "default": COLORS["white"],
}

EST = ZoneInfo("America/New_York")


class ColorfulFormatter(logging.Formatter):
    """Colorful log formatter with EST timestamps and component highlighting."""

    def __init__(self, use_colors: bool = True) -> None:
        """Initialize the formatter.

        Args:
            use_colors: Whether to use ANSI colors.
        """
        super().__init__()
        self.use_colors = use_colors

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.use_colors:
            return text
        return f"{color}{text}{COLORS['reset']}"

    def _get_component_color(self, name: str) -> str:
        """Get color for a logger name/component."""
        for prefix, color in COMPONENT_COLORS.items():
            if prefix != "default" and name.startswith(prefix):
                return color
        return COMPONENT_COLORS["default"]

    def _format_timestamp(self, record: logging.LogRecord) -> str:
        """Format timestamp in EST with nice formatting."""
        dt = datetime.fromtimestamp(record.created, tz=EST)
        time_str = dt.strftime("%H:%M:%S")
        date_str = dt.strftime("%m/%d")
        ms_str = f".{int(record.msecs):03d}"
        return f"{time_str}{ms_str} {date_str}"

    def _format_level(self, record: logging.LogRecord) -> str:
        """Format log level with color and fixed width."""
        level = record.levelname
        color = LEVEL_COLORS.get(level, COLORS["white"])
        padded = f"{level:<8}"
        return self._colorize(padded, color)

    def _format_component(self, record: logging.LogRecord) -> str:
        """Format component/logger name with color."""
        name = record.name
        # Shorten common prefixes
        if name.startswith("scout_mcp."):
            name = name[10:]  # Remove "scout_mcp." prefix
        color = self._get_component_color(record.name)
        return self._colorize(f"{name:<20}", color)

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors and EST timestamp."""
        # Timestamp (dim)
        timestamp = self._format_timestamp(record)
        timestamp = self._colorize(timestamp, COLORS["dim"])

        # Level (colored by severity)
        level = self._format_level(record)

        # Component/logger name (colored by type)
        component = self._format_component(record)

        # Separator
        sep = self._colorize("|", COLORS["dim"])

        # Message
        message = record.getMessage()

        # Highlight specific patterns in messages
        message = self._highlight_message(message)

        # Format final line
        return f"{timestamp} {sep} {level} {sep} {component} {sep} {message}"

    def _highlight_message(self, message: str) -> str:
        """Highlight specific patterns in log messages."""
        if not self.use_colors:
            return message

        # Highlight tool names
        if "tool:" in message.lower() or "scout" in message.lower():
            # Highlight "scout" when it appears as a tool name
            message = message.replace(
                "tool:scout",
                f"{COLORS['bright_cyan']}tool:scout{COLORS['reset']}",
            )

        # Highlight resource URIs
        if "://" in message:
            import re

            # Match URIs like tootie://path or scout://host/path
            uri_pattern = r"(\w+://[^\s]+)"
            message = re.sub(
                uri_pattern,
                f"{COLORS['bright_blue']}\\1{COLORS['reset']}",
                message,
            )

        # Highlight durations
        if "ms" in message:
            import re

            # Match patterns like "123.45ms" or "1000ms"
            ms_pattern = r"(\d+\.?\d*ms)"
            message = re.sub(
                ms_pattern,
                f"{COLORS['bright_yellow']}\\1{COLORS['reset']}",
                message,
            )

        # Highlight SSH connection info
        if "@" in message and ":" in message:
            import re

            # Match user@host:port patterns
            ssh_pattern = r"(\w+@[\w\.\-]+:\d+)"
            message = re.sub(
                ssh_pattern,
                f"{COLORS['bright_magenta']}\\1{COLORS['reset']}",
                message,
            )

        # Highlight host names in parentheses
        if "pool_size=" in message:
            import re

            pool_pattern = r"(pool_size=\d+)"
            message = re.sub(
                pool_pattern,
                f"{COLORS['cyan']}\\1{COLORS['reset']}",
                message,
            )

        return message


class MCPRequestFormatter(ColorfulFormatter):
    """Extended formatter with MCP request/response details."""

    def format(self, record: logging.LogRecord) -> str:
        """Format with additional MCP-specific highlighting."""
        # Get base format
        base = super().format(record)

        # Add extra visual indicators for specific events
        message = record.getMessage().lower()

        if not self.use_colors:
            return base

        # Add emoji-style indicators
        if "starting" in message or "ready" in message:
            return f"{COLORS['bright_green']}>>>{COLORS['reset']} {base}"
        elif "shutting down" in message or "shutdown" in message:
            return f"{COLORS['bright_red']}<<<{COLORS['reset']} {base}"
        elif "error" in message or "failed" in message:
            return f"{COLORS['bright_red']}!!{COLORS['reset']}  {base}"
        elif "warning" in message or "slow" in message:
            return f"{COLORS['bright_yellow']}!{COLORS['reset']}   {base}"
        elif "completed" in message or "succeeded" in message:
            return f"{COLORS['bright_green']}OK{COLORS['reset']}  {base}"
        elif "opening" in message or "creating" in message:
            return f"{COLORS['bright_cyan']}+{COLORS['reset']}   {base}"
        elif "closing" in message or "removing" in message:
            return f"{COLORS['bright_yellow']}-{COLORS['reset']}   {base}"
        elif "reusing" in message:
            return f"{COLORS['bright_magenta']}~{COLORS['reset']}   {base}"

        return f"    {base}"
