"""Desktop tools — screenshots, clipboard, notifications, display info."""

import base64
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .app import mcp
from .helpers import WINDOWS

if WINDOWS:
    import ctypes
    import ctypes.wintypes

    import win32clipboard
    import win32con
    import win32gui
    import win32ui


# ── Screenshots ──────────────────────────────────────────────────────────────


def _screenshot_full() -> Path:
    """Capture the full screen using GDI (no Pillow dependency for capture)."""
    from PIL import ImageGrab

    img = ImageGrab.grab()
    path = Path(tempfile.gettempdir()) / "desktop_commander_screenshot.png"
    img.save(str(path))
    return path


def _screenshot_window(hwnd: int) -> Path:
    """Capture a specific window by handle."""
    from PIL import Image

    try:
        rect = win32gui.GetWindowRect(hwnd)
    except Exception as e:
        raise RuntimeError(f"Cannot get window rect: {e}")

    width = rect[2] - rect[0]
    height = rect[3] - rect[1]
    if width <= 0 or height <= 0:
        raise RuntimeError("Window has zero or negative size (possibly minimized)")

    # Use GDI to capture
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)

    result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
    if result == 0:
        # Fallback to BitBlt
        save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

    bmp_info = bitmap.GetInfo()
    bmp_bits = bitmap.GetBitmapBits(True)

    img = Image.frombuffer("RGB", (bmp_info["bmWidth"], bmp_info["bmHeight"]), bmp_bits, "raw", "BGRX", 0, 1)

    path = Path(tempfile.gettempdir()) / "desktop_commander_window.png"
    img.save(str(path))

    # Cleanup
    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    return path


@mcp.tool()
def capture_screenshot(
    window_title: str | None = None,
    hwnd: int | None = None,
    as_base64: bool = False,
) -> dict[str, Any]:
    """Capture a screenshot of the full screen or a specific window.

    Args:
        window_title: Capture only the window matching this title substring.
        hwnd: Capture a specific window by handle. Takes priority over window_title.
        as_base64: If True, return the image as a base64 string instead of a file path.

    Returns the file path to the saved PNG screenshot (or base64 data).
    Claude can then read the image file to see what's on screen.
    """
    if not WINDOWS:
        return {"error": "Screenshot capture is only supported on Windows"}

    try:
        if hwnd is not None or window_title is not None:
            target = hwnd
            if target is None:
                from .windows import list_windows

                matches = list_windows(filter_title=window_title)
                if not matches:
                    return {"error": f"No window found matching '{window_title}'"}
                target = matches[0]["hwnd"]
            path = _screenshot_window(target)
        else:
            path = _screenshot_full()

        result = {"status": "success", "path": str(path), "size_bytes": path.stat().st_size}

        if as_base64:
            with open(path, "rb") as f:
                result["base64"] = base64.b64encode(f.read()).decode("ascii")

        return result

    except Exception as e:
        return {"error": f"Screenshot failed: {e}"}


# ── Clipboard ────────────────────────────────────────────────────────────────


@mcp.tool()
def read_clipboard() -> dict[str, Any]:
    """Read the current text content from the system clipboard.

    Returns the clipboard text, or an error if the clipboard is empty or
    contains non-text data.
    """
    if not WINDOWS:
        return {"error": "Clipboard access is only supported on Windows"}

    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return {"status": "success", "text": data, "length": len(data)}
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                text = data.decode("utf-8", errors="replace")
                return {"status": "success", "text": text, "length": len(text)}
            else:
                # List available formats
                formats = []
                fmt = 0
                while True:
                    fmt = win32clipboard.EnumClipboardFormats(fmt)
                    if fmt == 0:
                        break
                    try:
                        name = win32clipboard.GetClipboardFormatName(fmt)
                    except Exception:
                        name = f"format_{fmt}"
                    formats.append(name)
                return {
                    "status": "no_text",
                    "message": "Clipboard contains non-text data",
                    "available_formats": formats[:10],
                }
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        return {"error": f"Failed to read clipboard: {e}"}


@mcp.tool()
def write_clipboard(text: str) -> dict[str, str]:
    """Write text to the system clipboard.

    Args:
        text: The text string to place on the clipboard.
    """
    if not WINDOWS:
        return {"error": "Clipboard access is only supported on Windows"}

    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return {
            "status": "success",
            "message": f"Copied {len(text)} characters to clipboard",
        }
    except Exception as e:
        return {"error": f"Failed to write to clipboard: {e}"}


# ── Notifications ────────────────────────────────────────────────────────────


@mcp.tool()
def send_notification(title: str, message: str, duration_sec: int = 5) -> dict[str, str]:
    """Send a desktop toast notification.

    Args:
        title: Notification title.
        message: Notification body text.
        duration_sec: How long to show the notification (1-30 seconds). Default: 5.

    Useful for alerting the user when a long-running task completes.
    """
    if not WINDOWS:
        return {"error": "Notifications are only supported on Windows"}

    duration_sec = max(1, min(duration_sec, 30))

    # Use PowerShell for reliable Windows toast notifications
    # Escape special characters for PowerShell
    safe_title = title.replace("'", "''").replace('"', '`"')
    safe_message = message.replace("'", "''").replace('"', '`"')

    ps_script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.BalloonTipTitle = '{safe_title}'
    $notify.BalloonTipText = '{safe_message}'
    $notify.BalloonTipIcon = 'Info'
    $notify.Visible = $true
    $notify.ShowBalloonTip({duration_sec * 1000})
    Start-Sleep -Seconds {duration_sec + 1}
    $notify.Dispose()
    """

    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return {"status": "success", "message": f"Notification sent: {title}"}
    except Exception as e:
        return {"error": f"Failed to send notification: {e}"}


# ── Display Info ─────────────────────────────────────────────────────────────


@mcp.tool()
def get_display_info() -> dict[str, Any]:
    """Get display/monitor information: resolution, DPI, number of monitors.

    Returns details about all connected monitors including their resolution,
    position, and whether they are the primary display.
    """
    if not WINDOWS:
        return {"error": "Display info is only supported on Windows"}

    try:
        monitors = []

        def monitor_callback(hmonitor, hdc, lprect, lparam):
            info = {"handle": hmonitor}
            rect = lprect.contents
            info["x"] = rect.left
            info["y"] = rect.top
            info["width"] = rect.right - rect.left
            info["height"] = rect.bottom - rect.top

            # Check if primary
            monitor_info = win32gui.GetMonitorInfo(hmonitor)  # type: ignore[attr-defined]
            info["is_primary"] = bool(monitor_info.get("Flags", 0) & 1)
            info["device"] = monitor_info.get("Device", "")

            monitors.append(info)
            return True

        # Use ctypes for EnumDisplayMonitors
        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.c_double,
        )

        # Simpler approach using win32api
        import win32api

        for i, monitor in enumerate(win32api.EnumDisplayMonitors()):
            hmonitor, _, rect = monitor
            mon_info = win32api.GetMonitorInfo(hmonitor)
            monitors.append(
                {
                    "monitor": i,
                    "x": rect[0],
                    "y": rect[1],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                    "is_primary": bool(mon_info.get("Flags", 0) & 1),
                    "device": mon_info.get("Device", ""),
                }
            )

        # Get DPI
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
        except AttributeError:
            dpi = 96  # default

        # Get virtual screen size (all monitors combined)
        virtual_width = ctypes.windll.user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        virtual_height = ctypes.windll.user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

        return {
            "monitors": monitors,
            "monitor_count": len(monitors),
            "dpi": dpi,
            "scale_factor": round(dpi / 96 * 100),
            "virtual_screen": {"width": virtual_width, "height": virtual_height},
        }

    except Exception as e:
        return {"error": f"Failed to get display info: {e}"}
