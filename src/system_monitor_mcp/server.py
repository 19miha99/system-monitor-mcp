"""Desktop Commander MCP Server — entry point.

Comprehensive system monitoring and desktop control for Claude:
- System monitoring: CPU, RAM, disk, network, processes, battery, temperatures
- Window management: list, focus, move, resize, minimize, maximize, close
- Desktop control: screenshots, clipboard, notifications, display info
- App management: launch apps, search installed software, startup programs
"""

from .app import mcp

# Import all tool modules — this registers their @mcp.tool() decorated functions
from . import monitor  # noqa: F401  — 10 system monitoring tools
from . import windows  # noqa: F401  — 5 window management tools
from . import desktop  # noqa: F401  — 5 desktop control tools
from . import apps  # noqa: F401  — 3 app management tools


def main():
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
