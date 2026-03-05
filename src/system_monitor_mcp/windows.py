"""Window management tools — list, focus, move, resize, minimize, maximize, close windows."""

from typing import Any

from .app import mcp
from .helpers import WINDOWS

if WINDOWS:
    import ctypes
    import ctypes.wintypes

    import win32con
    import win32gui
    import win32process


def _get_window_info(hwnd: int) -> dict[str, Any] | None:
    """Extract info from a window handle."""
    if not win32gui.IsWindowVisible(hwnd):
        return None
    title = win32gui.GetWindowText(hwnd)
    if not title:
        return None

    try:
        rect = win32gui.GetWindowRect(hwnd)
    except Exception:
        rect = (0, 0, 0, 0)

    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        pid = None

    placement = win32gui.GetWindowPlacement(hwnd)
    state_map = {
        win32con.SW_SHOWMINIMIZED: "minimized",
        win32con.SW_SHOWMAXIMIZED: "maximized",
        win32con.SW_SHOWNORMAL: "normal",
    }
    state = state_map.get(placement[1], "normal")

    return {
        "hwnd": hwnd,
        "title": title,
        "pid": pid,
        "x": rect[0],
        "y": rect[1],
        "width": rect[2] - rect[0],
        "height": rect[3] - rect[1],
        "state": state,
    }


@mcp.tool()
def list_windows(filter_title: str | None = None) -> list[dict[str, Any]]:
    """List all visible windows with their title, position, size, PID, and state.

    Args:
        filter_title: Optional substring filter on window title (case-insensitive).

    Returns a list of visible windows. Useful for finding which applications are open
    and their window handles (hwnd) for use with other window tools.
    """
    if not WINDOWS:
        return [{"error": "Window management is only supported on Windows"}]

    results = []

    def enum_callback(hwnd, _):
        info = _get_window_info(hwnd)
        if info is None:
            return True
        if filter_title and filter_title.lower() not in info["title"].lower():
            return True
        results.append(info)
        return True

    win32gui.EnumWindows(enum_callback, None)
    return results


@mcp.tool()
def focus_window(title: str | None = None, hwnd: int | None = None) -> dict[str, str]:
    """Bring a window to the foreground (activate it).

    Args:
        title: Substring of the window title to find and focus (case-insensitive).
        hwnd: Exact window handle. Takes priority over title if both provided.

    Provide either title or hwnd. If title matches multiple windows, the first match is focused.
    """
    if not WINDOWS:
        return {"error": "Window management is only supported on Windows"}

    if hwnd is None and title is None:
        return {"error": "Provide either 'title' or 'hwnd'"}

    target = hwnd
    if target is None:
        windows = list_windows(filter_title=title)
        if not windows:
            return {"error": f"No window found matching '{title}'"}
        target = windows[0]["hwnd"]

    try:
        # If minimized, restore first
        placement = win32gui.GetWindowPlacement(target)
        if placement[1] == win32con.SW_SHOWMINIMIZED:
            win32gui.ShowWindow(target, win32con.SW_RESTORE)

        win32gui.SetForegroundWindow(target)
        return {"status": "success", "message": f"Focused window (hwnd={target})"}
    except Exception as e:
        return {"error": f"Failed to focus window: {e}"}


@mcp.tool()
def arrange_window(
    title: str | None = None,
    hwnd: int | None = None,
    x: int | None = None,
    y: int | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, str]:
    """Move and/or resize a window.

    Args:
        title: Substring of the window title (case-insensitive).
        hwnd: Exact window handle. Takes priority over title.
        x: New X position (left edge). None = keep current.
        y: New Y position (top edge). None = keep current.
        width: New width in pixels. None = keep current.
        height: New height in pixels. None = keep current.
    """
    if not WINDOWS:
        return {"error": "Window management is only supported on Windows"}

    if hwnd is None and title is None:
        return {"error": "Provide either 'title' or 'hwnd'"}

    target = hwnd
    if target is None:
        windows = list_windows(filter_title=title)
        if not windows:
            return {"error": f"No window found matching '{title}'"}
        target = windows[0]["hwnd"]

    try:
        # Restore if maximized/minimized so we can move it
        win32gui.ShowWindow(target, win32con.SW_RESTORE)

        rect = win32gui.GetWindowRect(target)
        new_x = x if x is not None else rect[0]
        new_y = y if y is not None else rect[1]
        new_w = width if width is not None else (rect[2] - rect[0])
        new_h = height if height is not None else (rect[3] - rect[1])

        win32gui.MoveWindow(target, new_x, new_y, new_w, new_h, True)
        return {
            "status": "success",
            "message": f"Window moved to ({new_x}, {new_y}) size {new_w}x{new_h}",
        }
    except Exception as e:
        return {"error": f"Failed to arrange window: {e}"}


@mcp.tool()
def set_window_state(
    state: str,
    title: str | None = None,
    hwnd: int | None = None,
) -> dict[str, str]:
    """Minimize, maximize, or restore a window.

    Args:
        state: "minimize", "maximize", or "restore".
        title: Substring of the window title (case-insensitive).
        hwnd: Exact window handle. Takes priority over title.
    """
    if not WINDOWS:
        return {"error": "Window management is only supported on Windows"}

    if hwnd is None and title is None:
        return {"error": "Provide either 'title' or 'hwnd'"}

    state_map = {
        "minimize": win32con.SW_MINIMIZE,
        "maximize": win32con.SW_MAXIMIZE,
        "restore": win32con.SW_RESTORE,
    }
    if state not in state_map:
        return {"error": f"Invalid state '{state}'. Use: minimize, maximize, restore"}

    target = hwnd
    if target is None:
        windows = list_windows(filter_title=title)
        if not windows:
            return {"error": f"No window found matching '{title}'"}
        target = windows[0]["hwnd"]

    try:
        win32gui.ShowWindow(target, state_map[state])
        return {"status": "success", "message": f"Window {state}d (hwnd={target})"}
    except Exception as e:
        return {"error": f"Failed to {state} window: {e}"}


@mcp.tool()
def close_window(
    title: str | None = None,
    hwnd: int | None = None,
) -> dict[str, str]:
    """Close a window gracefully by sending WM_CLOSE.

    Args:
        title: Substring of the window title (case-insensitive).
        hwnd: Exact window handle. Takes priority over title.
    """
    if not WINDOWS:
        return {"error": "Window management is only supported on Windows"}

    if hwnd is None and title is None:
        return {"error": "Provide either 'title' or 'hwnd'"}

    target = hwnd
    window_title = f"hwnd={target}"
    if target is None:
        windows = list_windows(filter_title=title)
        if not windows:
            return {"error": f"No window found matching '{title}'"}
        target = windows[0]["hwnd"]
        window_title = windows[0]["title"]

    try:
        win32gui.PostMessage(target, win32con.WM_CLOSE, 0, 0)
        return {"status": "success", "message": f"Sent close to '{window_title}'"}
    except Exception as e:
        return {"error": f"Failed to close window: {e}"}
