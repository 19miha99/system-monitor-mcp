"""Application management tools — launch apps, find installed software, startup programs."""

import os
import subprocess
import winreg
from pathlib import Path
from typing import Any

from .app import mcp
from .helpers import WINDOWS


@mcp.tool()
def launch_application(
    command: str,
    args: list[str] | None = None,
    working_dir: str | None = None,
    wait: bool = False,
) -> dict[str, Any]:
    """Launch an application or open a file/URL.

    Args:
        command: Path to executable, application name, file path, or URL.
            Examples: "notepad", "C:/Program Files/app.exe", "https://google.com",
            "C:/Users/file.txt" (opens with default app).
        args: Optional list of command-line arguments.
        working_dir: Working directory for the process. Default: user's home.
        wait: If True, wait for the process to complete and return output. Default: False.

    For URLs and files, uses the system's default handler (like double-clicking).
    """
    if not WINDOWS:
        return {"error": "Application launching is only supported on Windows"}

    args = args or []
    working_dir = working_dir or os.path.expanduser("~")

    try:
        # Check if it's a URL or file to open with default handler
        if command.startswith(("http://", "https://", "file://")):
            os.startfile(command)
            return {"status": "success", "message": f"Opened URL: {command}"}

        # Check if it's a file path (open with default app)
        path = Path(command)
        if path.exists() and path.is_file() and not command.lower().endswith(".exe"):
            os.startfile(str(path))
            return {"status": "success", "message": f"Opened file: {command}"}

        # Launch as executable
        full_cmd = [command] + args

        if wait:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {
                "status": "success",
                "return_code": result.returncode,
                "stdout": result.stdout[:5000] if result.stdout else "",
                "stderr": result.stderr[:2000] if result.stderr else "",
            }
        else:
            proc = subprocess.Popen(
                full_cmd,
                cwd=working_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {
                "status": "success",
                "message": f"Launched '{command}'",
                "pid": proc.pid,
            }

    except FileNotFoundError:
        return {"error": f"Application not found: '{command}'"}
    except subprocess.TimeoutExpired:
        return {"error": f"Application timed out after 30 seconds"}
    except Exception as e:
        return {"error": f"Failed to launch application: {e}"}


def _scan_registry_apps(root_key, sub_key: str) -> list[dict[str, str]]:
    """Scan a registry uninstall key for installed applications."""
    apps = []
    try:
        with winreg.OpenKey(root_key, sub_key) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as app_key:
                        try:
                            name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                        except OSError:
                            i += 1
                            continue

                        app_info = {"name": name}
                        for field in ("DisplayVersion", "Publisher", "InstallLocation", "InstallDate"):
                            try:
                                app_info[field.lower()] = winreg.QueryValueEx(app_key, field)[0]
                            except OSError:
                                pass
                        apps.append(app_info)
                    i += 1
                except OSError:
                    break
    except OSError:
        pass
    return apps


@mcp.tool()
def search_installed_apps(query: str | None = None, limit: int = 30) -> list[dict[str, str]]:
    """Search installed applications on this computer.

    Args:
        query: Optional search term to filter by app name (case-insensitive).
            If not provided, returns all installed apps.
        limit: Maximum number of results (1-200). Default: 30.

    Reads from the Windows registry uninstall keys.
    """
    if not WINDOWS:
        return [{"error": "Only supported on Windows"}]

    limit = max(1, min(limit, 200))

    apps = []
    # Check both 64-bit and 32-bit registry paths
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sub in (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ):
            apps.extend(_scan_registry_apps(root, sub))

    # Deduplicate by name
    seen = set()
    unique = []
    for app in apps:
        name = app["name"].strip().lower()
        if name not in seen:
            seen.add(name)
            unique.append(app)

    # Filter
    if query:
        q = query.lower()
        unique = [a for a in unique if q in a["name"].lower()]

    # Sort by name
    unique.sort(key=lambda x: x["name"].lower())
    return unique[:limit]


@mcp.tool()
def get_startup_programs() -> list[dict[str, Any]]:
    """List programs configured to run at Windows startup.

    Reads from registry Run keys and the Startup folder.
    Returns program names and their launch commands.
    """
    if not WINDOWS:
        return [{"error": "Only supported on Windows"}]

    programs = []

    # Registry startup entries
    run_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "machine"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "user"),
    ]

    for root, key_path, scope in run_keys:
        try:
            with winreg.OpenKey(root, key_path) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        programs.append(
                            {
                                "name": name,
                                "command": value,
                                "source": f"registry ({scope})",
                            }
                        )
                        i += 1
                    except OSError:
                        break
        except OSError:
            continue

    # Startup folder
    startup_folder = Path(os.environ.get("APPDATA", "")) / (
        r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    if startup_folder.exists():
        for item in startup_folder.iterdir():
            if item.is_file():
                programs.append(
                    {
                        "name": item.stem,
                        "command": str(item),
                        "source": "startup folder",
                    }
                )

    return programs
