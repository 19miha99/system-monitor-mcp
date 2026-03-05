# System Monitor MCP Server

A Model Context Protocol (MCP) server that provides real-time system monitoring capabilities to AI assistants like Claude. Monitor CPU, RAM, disk, network, processes, and more — directly from your AI conversation.

## Features

| Tool | Description |
|------|-------------|
| `get_system_overview` | CPU, RAM, disk, swap usage and uptime in one call |
| `list_processes` | List processes sorted by CPU/memory with optional filtering |
| `get_process_details` | Deep-dive into a specific process (connections, threads, IO) |
| `get_top_consumers` | Top N processes by CPU or memory |
| `get_network_stats` | Network interfaces, bytes sent/received, connection summary |
| `get_cpu_per_core` | Per-core CPU usage and frequency |
| `kill_process` | Gracefully terminate or force-kill a process by PID |
| `get_battery_status` | Battery level, charging status, time remaining |
| `find_process_by_port` | Find which process is using a specific port |
| `get_temperatures` | Hardware temperature sensors (Linux/macOS) |

## Installation

```bash
# Clone the repository
git clone https://github.com/19miha99/system-monitor-mcp.git
cd system-monitor-mcp

# Install with pip
pip install -e .
```

## Usage with Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "system-monitor": {
      "command": "python",
      "args": ["-m", "system_monitor_mcp.server"],
      "env": {}
    }
  }
}
```

Or if installed as a package:

```json
{
  "mcpServers": {
    "system-monitor": {
      "command": "system-monitor-mcp"
    }
  }
}
```

## Usage with Claude Code

Add to your Claude Code settings:

```bash
claude mcp add system-monitor -- python -m system_monitor_mcp.server
```

## Example Conversations

**"What's eating my CPU?"**
→ Uses `get_top_consumers` to show the top processes by CPU usage.

**"Is port 3000 in use?"**
→ Uses `find_process_by_port` to find and identify the process.

**"Give me a system health check"**
→ Uses `get_system_overview` for a complete snapshot of CPU, RAM, disk, and uptime.

**"Kill that frozen Chrome tab"**
→ Uses `list_processes` to find it, then `kill_process` to terminate it.

## Requirements

- Python 3.10+
- `psutil` — cross-platform system monitoring
- `mcp` — Model Context Protocol SDK

## Platform Support

| Feature | Windows | Linux | macOS |
|---------|---------|-------|-------|
| CPU/RAM/Disk | ✅ | ✅ | ✅ |
| Processes | ✅ | ✅ | ✅ |
| Network | ✅ | ✅ | ✅ |
| Battery | ✅ | ✅ | ✅ |
| Temperatures | ⚠️ Limited | ✅ | ✅ |
| Kill process | ✅ | ✅ | ✅ |

## License

MIT
