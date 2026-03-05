"""FastMCP application instance — shared across all tool modules."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Desktop Commander",
    instructions=(
        "Comprehensive desktop control and system monitoring. "
        "Manage windows, capture screenshots, control clipboard, "
        "monitor CPU/RAM/disk/network, manage processes, and more."
    ),
)
