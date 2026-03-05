# Desktop Commander MCP Server

A comprehensive Model Context Protocol (MCP) server that gives AI assistants like Claude **full control over your desktop** — monitor system resources, manage windows, capture screenshots, control the clipboard, launch applications, and more.

**23 tools** across 4 categories, turning Claude into a true desktop assistant.

## Why Desktop Commander?

Claude is powerful, but blind and handless on your desktop. Desktop Commander fixes that:

- **"What's eating my CPU?"** — instantly see top resource consumers
- **"Take a screenshot"** — Claude can actually *see* your screen
- **"Arrange my windows side by side"** — window management by natural language
- **"Copy this to clipboard"** — seamless data transfer
- **"Is port 3000 in use?"** — debug development issues
- **"Open VS Code in my project folder"** — launch apps with context

## Tools

### System Monitoring (10 tools)

| Tool | Description |
|------|-------------|
| `get_system_overview` | CPU, RAM, disk, swap usage and uptime in one call |
| `list_processes` | List processes sorted by CPU/memory with optional filtering |
| `get_process_details` | Deep-dive into a specific process (connections, threads, IO) |
| `get_top_consumers` | Top N processes by CPU or memory |
| `get_network_stats` | Network interfaces, bytes sent/received, connection summary |
| `get_cpu_per_core` | Per-core CPU usage and frequency |
| `kill_process` | Gracefully terminate or force-kill a process (with safety guards) |
| `get_battery_status` | Battery level, charging status, time remaining |
| `find_process_by_port` | Find which process is using a specific port |
| `get_temperatures` | Hardware temperature sensors |

### Window Management (5 tools)

| Tool | Description |
|------|-------------|
| `list_windows` | List all visible windows with title, position, size, PID, and state |
| `focus_window` | Bring a window to the foreground by title or handle |
| `arrange_window` | Move and/or resize a window to exact pixel coordinates |
| `set_window_state` | Minimize, maximize, or restore a window |
| `close_window` | Gracefully close a window |

### Desktop Control (5 tools)

| Tool | Description |
|------|-------------|
| `capture_screenshot` | Screenshot full screen or a specific window (returns file path or base64) |
| `read_clipboard` | Read text content from the system clipboard |
| `write_clipboard` | Write text to the system clipboard |
| `send_notification` | Show a desktop toast notification |
| `get_display_info` | Monitor info: resolution, DPI, scaling, multi-monitor layout |

### Application Management (3 tools)

| Tool | Description |
|------|-------------|
| `launch_application` | Start a program, open a file, or open a URL |
| `search_installed_apps` | Search installed software (from Windows registry) |
| `get_startup_programs` | List programs configured to run at startup |

## Installation

```bash
git clone https://github.com/19miha99/system-monitor-mcp.git
cd system-monitor-mcp
pip install -e .
```

## Usage with Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "desktop-commander": {
      "command": "python",
      "args": ["-m", "system_monitor_mcp.server"]
    }
  }
}
```

## Usage with Claude Code

```bash
claude mcp add desktop-commander -- python -m system_monitor_mcp.server
```

## Example Workflows

### System Health Check
> "Give me a complete system health check"

Claude calls `get_system_overview`, `get_top_consumers`, `get_network_stats` and gives you a comprehensive report.

### Debug a Slow Computer
> "My computer is slow, what's going on?"

Claude checks `get_top_consumers` for CPU and memory, identifies the culprit, and offers to `kill_process` if needed.

### Window Arrangement
> "Put Chrome on the left half and VS Code on the right half of my screen"

Claude uses `list_windows` to find them, `get_display_info` to know the screen size, then `arrange_window` to position each one.

### Port Conflict Resolution
> "Something is using port 8080, find and kill it"

Claude calls `find_process_by_port(8080)`, shows you what's there, and `kill_process` to free the port.

### Visual Debugging
> "Take a screenshot and tell me what you see"

Claude uses `capture_screenshot`, then reads the image to analyze what's on screen.

### App Launcher
> "Open my project in VS Code"

Claude calls `launch_application("code", args=["C:/Users/you/project"])`.

## Architecture

```
src/system_monitor_mcp/
├── app.py          # FastMCP instance (shared across modules)
├── server.py       # Entry point — imports all tool modules
├── helpers.py      # Shared utilities (format_bytes, format_uptime)
├── monitor.py      # 10 system monitoring tools
├── windows.py      # 5 window management tools
├── desktop.py      # 5 desktop control tools (screenshots, clipboard, etc.)
└── apps.py         # 3 application management tools
```

## Requirements

- **Python 3.10+**
- **psutil** — cross-platform system monitoring
- **mcp** — Model Context Protocol SDK
- **Pillow** — screenshot capture
- **pywin32** — Windows API access (auto-installed on Windows)

## Platform Support

| Category | Windows | Linux | macOS |
|----------|---------|-------|-------|
| System Monitoring | Full | Full | Full |
| Window Management | Full | Planned | Planned |
| Screenshots | Full | Planned | Planned |
| Clipboard | Full | Planned | Planned |
| Notifications | Full | Planned | Planned |
| App Management | Full | Planned | Planned |

Primary platform: **Windows**. Cross-platform support for desktop features is planned.

## Safety

- System-critical processes (PID 0, 1, 4) cannot be killed
- The server refuses to kill its own process
- Windows are closed gracefully via WM_CLOSE (not force-terminated)
- All operations provide clear error messages on failure

## License

MIT
