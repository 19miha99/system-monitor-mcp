"""System Monitor MCP Server.

Provides tools for real-time system monitoring:
- CPU, RAM, disk usage
- Process listing and management
- Network statistics
- System information
"""

import datetime
import os
import platform
import signal
import sys
from typing import Any

import psutil
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "System Monitor",
    instructions="Real-time system monitoring — CPU, RAM, disk, network, and process management",
)


def _format_bytes(n: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _format_uptime(seconds: float) -> str:
    """Convert seconds to human-readable uptime."""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


# ── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_system_overview() -> dict[str, Any]:
    """Get a high-level overview of the system: CPU, RAM, disk, swap, and uptime.

    Returns current utilization percentages and absolute values for all major
    system resources in a single call.
    """
    cpu_freq = psutil.cpu_freq()
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    boot = psutil.boot_time()
    uptime = datetime.datetime.now().timestamp() - boot

    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append(
                {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "filesystem": part.fstype,
                    "total": _format_bytes(usage.total),
                    "used": _format_bytes(usage.used),
                    "free": _format_bytes(usage.free),
                    "percent": usage.percent,
                }
            )
        except PermissionError:
            continue

    return {
        "platform": platform.platform(),
        "hostname": platform.node(),
        "cpu": {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "usage_percent": psutil.cpu_percent(interval=0.5),
            "frequency_mhz": round(cpu_freq.current, 1) if cpu_freq else None,
        },
        "memory": {
            "total": _format_bytes(vm.total),
            "available": _format_bytes(vm.available),
            "used": _format_bytes(vm.used),
            "percent": vm.percent,
        },
        "swap": {
            "total": _format_bytes(swap.total),
            "used": _format_bytes(swap.used),
            "percent": swap.percent,
        },
        "disks": disks,
        "uptime": _format_uptime(uptime),
        "boot_time": datetime.datetime.fromtimestamp(boot).isoformat(),
    }


@mcp.tool()
def list_processes(
    sort_by: str = "cpu",
    limit: int = 20,
    filter_name: str | None = None,
) -> list[dict[str, Any]]:
    """List running processes sorted by resource usage.

    Args:
        sort_by: Sort criterion — "cpu", "memory", "pid", or "name". Default: "cpu".
        limit: Maximum number of processes to return (1-100). Default: 20.
        filter_name: Optional substring filter on process name (case-insensitive).
    """
    limit = max(1, min(limit, 100))
    sort_key_map = {
        "cpu": "cpu_percent",
        "memory": "memory_percent",
        "pid": "pid",
        "name": "name",
    }
    sort_key = sort_key_map.get(sort_by, "cpu_percent")

    procs = []
    for p in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_percent", "status", "username", "create_time"]
    ):
        try:
            info = p.info
            if filter_name and filter_name.lower() not in (info["name"] or "").lower():
                continue
            procs.append(
                {
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": info["cpu_percent"] or 0.0,
                    "memory_percent": round(info["memory_percent"] or 0.0, 2),
                    "status": info["status"],
                    "user": info["username"],
                    "started": (
                        datetime.datetime.fromtimestamp(info["create_time"]).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if info["create_time"]
                        else None
                    ),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    reverse = sort_key != "name"
    procs.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=reverse)
    return procs[:limit]


@mcp.tool()
def get_process_details(pid: int) -> dict[str, Any]:
    """Get detailed information about a specific process by PID.

    Args:
        pid: The process ID to inspect.

    Returns detailed info including command line, open files, connections,
    threads, memory maps summary, and environment variables count.
    """
    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return {"error": f"No process found with PID {pid}"}

    with p.oneshot():
        try:
            mem_info = p.memory_info()
            io_counters = None
            try:
                io_counters = p.io_counters()
            except (psutil.AccessDenied, AttributeError):
                pass

            connections = []
            try:
                for conn in p.net_connections():
                    connections.append(
                        {
                            "fd": conn.fd,
                            "family": str(conn.family),
                            "type": str(conn.type),
                            "local": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                            "remote": (
                                f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None
                            ),
                            "status": conn.status,
                        }
                    )
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            children = []
            try:
                for child in p.children():
                    children.append({"pid": child.pid, "name": child.name()})
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            return {
                "pid": p.pid,
                "name": p.name(),
                "exe": p.exe() if hasattr(p, "exe") else None,
                "cmdline": p.cmdline(),
                "status": p.status(),
                "username": p.username(),
                "cpu_percent": p.cpu_percent(interval=0.3),
                "memory": {
                    "rss": _format_bytes(mem_info.rss),
                    "vms": _format_bytes(mem_info.vms),
                    "percent": round(p.memory_percent(), 2),
                },
                "threads": p.num_threads(),
                "io": (
                    {
                        "read_bytes": _format_bytes(io_counters.read_bytes),
                        "write_bytes": _format_bytes(io_counters.write_bytes),
                    }
                    if io_counters
                    else None
                ),
                "connections": connections[:20],
                "children": children,
                "created": datetime.datetime.fromtimestamp(p.create_time()).isoformat(),
            }
        except psutil.AccessDenied:
            return {"pid": pid, "error": "Access denied — insufficient permissions"}


@mcp.tool()
def get_top_consumers(resource: str = "cpu", count: int = 10) -> list[dict[str, Any]]:
    """Get the top N processes consuming the most CPU or memory.

    Args:
        resource: "cpu" or "memory". Default: "cpu".
        count: Number of top processes to return (1-50). Default: 10.
    """
    count = max(1, min(count, 50))
    attr = "cpu_percent" if resource == "cpu" else "memory_percent"

    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda x: x.get(attr, 0) or 0, reverse=True)
    results = []
    for info in procs[:count]:
        results.append(
            {
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": info["cpu_percent"] or 0.0,
                "memory_percent": round(info["memory_percent"] or 0.0, 2),
            }
        )
    return results


@mcp.tool()
def get_network_stats() -> dict[str, Any]:
    """Get network interface statistics: bytes sent/received, active connections summary."""
    net_io = psutil.net_io_counters()
    per_nic = psutil.net_io_counters(pernic=True)

    interfaces = {}
    for name, counters in per_nic.items():
        interfaces[name] = {
            "bytes_sent": _format_bytes(counters.bytes_sent),
            "bytes_recv": _format_bytes(counters.bytes_recv),
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
            "errors_in": counters.errin,
            "errors_out": counters.errout,
        }

    conn_stats = {}
    try:
        for conn in psutil.net_connections(kind="inet"):
            status = conn.status
            conn_stats[status] = conn_stats.get(status, 0) + 1
    except psutil.AccessDenied:
        conn_stats = {"error": "Access denied — run as administrator for connection details"}

    return {
        "total": {
            "bytes_sent": _format_bytes(net_io.bytes_sent),
            "bytes_recv": _format_bytes(net_io.bytes_recv),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        },
        "interfaces": interfaces,
        "connections_by_status": conn_stats,
    }


@mcp.tool()
def get_cpu_per_core() -> dict[str, Any]:
    """Get CPU usage percentage for each individual core.

    Useful for identifying unbalanced workloads or thermal throttling on specific cores.
    """
    per_core = psutil.cpu_percent(interval=0.5, percpu=True)
    freq_per_core = psutil.cpu_freq(percpu=True) or []

    cores = []
    for i, usage in enumerate(per_core):
        core = {"core": i, "usage_percent": usage}
        if i < len(freq_per_core):
            core["frequency_mhz"] = round(freq_per_core[i].current, 1)
        cores.append(core)

    return {
        "overall_percent": psutil.cpu_percent(interval=0),
        "cores": cores,
        "load_avg": (
            list(psutil.getloadavg())
            if hasattr(psutil, "getloadavg")
            else "Not available on Windows"
        ),
    }


@mcp.tool()
def kill_process(pid: int, force: bool = False) -> dict[str, str]:
    """Terminate or kill a process by PID.

    Args:
        pid: The process ID to terminate.
        force: If True, send SIGKILL (force kill). If False, send SIGTERM (graceful). Default: False.

    Returns confirmation or error message.
    """
    dangerous_pids = {0, 1, 4}  # system-critical PIDs
    if pid in dangerous_pids:
        return {"error": f"Refusing to kill system-critical process (PID {pid})"}

    if pid == os.getpid():
        return {"error": "Refusing to kill own process"}

    try:
        p = psutil.Process(pid)
        name = p.name()

        if force:
            p.kill()  # SIGKILL
            action = "Force killed"
        else:
            p.terminate()  # SIGTERM
            action = "Terminated"

        return {"status": "success", "message": f"{action} process '{name}' (PID {pid})"}

    except psutil.NoSuchProcess:
        return {"error": f"No process found with PID {pid}"}
    except psutil.AccessDenied:
        return {"error": f"Access denied — cannot kill PID {pid}. Try running as administrator."}


@mcp.tool()
def get_battery_status() -> dict[str, Any]:
    """Get battery status (for laptops).

    Returns charge percentage, time remaining, and power source.
    """
    battery = psutil.sensors_battery()
    if battery is None:
        return {"status": "No battery detected (desktop or unsupported)"}

    secs_left = battery.secsleft
    if secs_left == psutil.POWER_TIME_UNLIMITED:
        time_left = "Charging / AC power"
    elif secs_left == psutil.POWER_TIME_UNKNOWN:
        time_left = "Unknown"
    else:
        time_left = _format_uptime(secs_left)

    return {
        "percent": battery.percent,
        "plugged_in": battery.power_plugged,
        "time_remaining": time_left,
    }


@mcp.tool()
def find_process_by_port(port: int) -> dict[str, Any]:
    """Find which process is using a specific network port.

    Args:
        port: The port number to search for.

    Useful for debugging "port already in use" errors.
    """
    results = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port:
                proc_info = {"port": port, "status": conn.status, "pid": conn.pid}
                if conn.pid:
                    try:
                        p = psutil.Process(conn.pid)
                        proc_info["name"] = p.name()
                        proc_info["cmdline"] = " ".join(p.cmdline()[:5])
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                results.append(proc_info)
    except psutil.AccessDenied:
        return {"error": "Access denied — run as administrator to see port bindings"}

    if not results:
        return {"message": f"No process found on port {port}"}
    return {"port": port, "processes": results}


@mcp.tool()
def get_temperatures() -> dict[str, Any]:
    """Get CPU and hardware temperature sensors (Linux/macOS).

    Note: Limited support on Windows — may require third-party drivers.
    """
    if not hasattr(psutil, "sensors_temperatures"):
        return {"error": "Temperature monitoring not available on this platform"}

    temps = psutil.sensors_temperatures()
    if not temps:
        return {"message": "No temperature sensors found (common on Windows without drivers)"}

    result = {}
    for chip, entries in temps.items():
        result[chip] = [
            {
                "label": e.label or "unlabeled",
                "current": e.current,
                "high": e.high,
                "critical": e.critical,
            }
            for e in entries
        ]
    return result


def main():
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
