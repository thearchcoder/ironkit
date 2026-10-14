from __future__ import annotations

import contextlib
import ctypes
import sys
import threading
import time
from collections.abc import Callable
from ctypes import POINTER, Structure, Union, byref, c_int, c_long, c_short, c_uint, c_void_p, sizeof
from ctypes import wintypes as w

import numpy as np
import numpy.typing as npt

from .._errors import BackendError, InvalidKeyError, UnsupportedPlatformError, WindowNotFoundError
from .._types import Button, Monitor, Point, Region
from . import Capabilities, WindowHandle, WindowInfo, WindowState

if sys.platform != "win32":
    raise UnsupportedPlatformError("the windows backend only runs on Windows")

Pixels = npt.NDArray[np.uint8]

ULONG_PTR = ctypes.c_size_t

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008
WHEEL_DELTA = 120
SM_SWAPBUTTON = 23
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0
BI_RGB = 0
PW_RENDERFULLCONTENT = 2
MONITORINFOF_PRIMARY = 1
MDT_EFFECTIVE_DPI = 0
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
SW_HIDE = 0
SW_MAXIMIZE = 3
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
WM_CLOSE = 0x0010
VK_MENU = 0x12
VK_SHIFT = 0x10


class MOUSEINPUT(Structure):
    _fields_ = [
        ("dx", w.LONG),
        ("dy", w.LONG),
        ("mouseData", w.DWORD),
        ("dwFlags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(Structure):
    _fields_ = [
        ("wVk", w.WORD),
        ("wScan", w.WORD),
        ("dwFlags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(Structure):
    _fields_ = [("uMsg", w.DWORD), ("wParamL", w.WORD), ("wParamH", w.WORD)]


class _INPUTUNION(Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(Structure):
    _fields_ = [("type", w.DWORD), ("union", _INPUTUNION)]


class MONITORINFOEXW(Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("rcMonitor", w.RECT),
        ("rcWork", w.RECT),
        ("dwFlags", w.DWORD),
        ("szDevice", w.WCHAR * 32),
    ]


class BITMAPINFOHEADER(Structure):
    _fields_ = [
        ("biSize", w.DWORD),
        ("biWidth", w.LONG),
        ("biHeight", w.LONG),
        ("biPlanes", w.WORD),
        ("biBitCount", w.WORD),
        ("biCompression", w.DWORD),
        ("biSizeImage", w.DWORD),
        ("biXPelsPerMeter", w.LONG),
        ("biYPelsPerMeter", w.LONG),
        ("biClrUsed", w.DWORD),
        ("biClrImportant", w.DWORD),
    ]


class BITMAPINFO(Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 3)]


MONITORENUMPROC = ctypes.WINFUNCTYPE(w.BOOL, w.HMONITOR, w.HDC, POINTER(w.RECT), w.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

_VK: dict[str, int] = {
    "backspace": 0x08,
    "tab": 0x09,
    "clear": 0x0C,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "kana": 0x15,
    "hangul": 0x15,
    "junja": 0x17,
    "final": 0x18,
    "hanja": 0x19,
    "kanji": 0x19,
    "escape": 0x1B,
    "convert": 0x1C,
    "nonconvert": 0x1D,
    "accept": 0x1E,
    "modechange": 0x1F,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "select": 0x29,
    "execute": 0x2B,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "help": 0x2F,
    "win": 0x5B,
    "command": 0x5B,
    "winright": 0x5C,
    "apps": 0x5D,
    "sleep": 0x5F,
    "multiply": 0x6A,
    "add": 0x6B,
    "separator": 0x6C,
    "subtract": 0x6D,
    "decimal": 0x6E,
    "divide": 0x6F,
    "numlock": 0x90,
    "scrolllock": 0x91,
    "shiftleft": 0xA0,
    "shiftright": 0xA1,
    "ctrlleft": 0xA2,
    "ctrlright": 0xA3,
    "altleft": 0xA4,
    "option": 0x12,
    "optionleft": 0xA4,
    "altright": 0xA5,
    "optionright": 0xA5,
    "browserback": 0xA6,
    "browserforward": 0xA7,
    "browserrefresh": 0xA8,
    "browserstop": 0xA9,
    "browsersearch": 0xAA,
    "browserfavorites": 0xAB,
    "browserhome": 0xAC,
    "volumemute": 0xAD,
    "volumedown": 0xAE,
    "volumeup": 0xAF,
    "nexttrack": 0xB0,
    "prevtrack": 0xB1,
    "stop": 0xB2,
    "playpause": 0xB3,
    "launchmail": 0xB4,
    "launchmediaselect": 0xB5,
    "launchapp1": 0xB6,
    "launchapp2": 0xB7,
    **{f"num{i}": 0x60 + i for i in range(10)},
    **{f"f{i}": 0x6F + i for i in range(1, 25)},
}

_EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D, 0x6F, 0x90, 0xA3, 0xA5}

_BUTTON_FLAGS = {
    Button.LEFT: (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    Button.RIGHT: (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    Button.MIDDLE: (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


def _dll(name: str) -> ctypes.WinDLL:
    return ctypes.WinDLL(name, use_last_error=True)


def _signature(lib: ctypes.WinDLL, name: str, restype: object, *argtypes: object) -> None:
    fn = getattr(lib, name)
    fn.restype = restype
    fn.argtypes = list(argtypes)


def _enable_dpi_awareness(user32: ctypes.WinDLL) -> None:
    try:
        if user32.SetProcessDpiAwarenessContext(c_void_p(-4)):
            return
    except AttributeError:
        pass
    try:
        if _dll("shcore").SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass
    with contextlib.suppress(AttributeError):
        user32.SetProcessDPIAware()


class WindowsBackend:
    name = "windows"

    def __init__(self) -> None:
        self.capabilities = Capabilities(window_capture=True)
        self._lock = threading.RLock()
        self._user32 = _dll("user32")
        self._gdi32 = _dll("gdi32")
        self._kernel32 = _dll("kernel32")
        try:
            self._dwmapi: ctypes.WinDLL | None = _dll("dwmapi")
        except OSError:
            self._dwmapi = None
        try:
            self._shcore: ctypes.WinDLL | None = _dll("shcore")
        except OSError:
            self._shcore = None
        _enable_dpi_awareness(self._user32)
        self._declare()

    def _declare(self) -> None:
        u, g = self._user32, self._gdi32
        _signature(u, "SendInput", c_uint, c_uint, POINTER(INPUT), c_int)
        _signature(u, "GetCursorPos", w.BOOL, POINTER(w.POINT))
        _signature(u, "SetCursorPos", w.BOOL, c_int, c_int)
        _signature(u, "GetSystemMetrics", c_int, c_int)
        _signature(u, "VkKeyScanW", c_short, w.WCHAR)
        _signature(u, "MapVirtualKeyW", c_uint, c_uint, c_uint)
        _signature(u, "EnumDisplayMonitors", w.BOOL, w.HDC, POINTER(w.RECT), MONITORENUMPROC, w.LPARAM)
        _signature(u, "GetMonitorInfoW", w.BOOL, w.HMONITOR, POINTER(MONITORINFOEXW))
        _signature(u, "GetDC", w.HDC, w.HWND)
        _signature(u, "ReleaseDC", c_int, w.HWND, w.HDC)
        _signature(u, "EnumWindows", w.BOOL, WNDENUMPROC, w.LPARAM)
        _signature(u, "IsWindow", w.BOOL, w.HWND)
        _signature(u, "IsWindowVisible", w.BOOL, w.HWND)
        _signature(u, "IsIconic", w.BOOL, w.HWND)
        _signature(u, "IsZoomed", w.BOOL, w.HWND)
        _signature(u, "GetWindowTextLengthW", c_int, w.HWND)
        _signature(u, "GetWindowTextW", c_int, w.HWND, w.LPWSTR, c_int)
        _signature(u, "GetWindowRect", w.BOOL, w.HWND, POINTER(w.RECT))
        _signature(u, "GetWindowThreadProcessId", w.DWORD, w.HWND, POINTER(w.DWORD))
        _signature(u, "GetForegroundWindow", w.HWND)
        _signature(u, "SetForegroundWindow", w.BOOL, w.HWND)
        _signature(u, "BringWindowToTop", w.BOOL, w.HWND)
        _signature(u, "ShowWindow", w.BOOL, w.HWND, c_int)
        _signature(u, "SetWindowPos", w.BOOL, w.HWND, w.HWND, c_int, c_int, c_int, c_int, c_uint)
        _signature(u, "PostMessageW", w.BOOL, w.HWND, c_uint, w.WPARAM, w.LPARAM)
        _signature(u, "PrintWindow", w.BOOL, w.HWND, w.HDC, c_uint)
        _signature(u, "AttachThreadInput", w.BOOL, w.DWORD, w.DWORD, w.BOOL)
        _signature(self._kernel32, "GetCurrentThreadId", w.DWORD)
        _signature(g, "CreateCompatibleDC", w.HDC, w.HDC)
        _signature(g, "CreateCompatibleBitmap", w.HBITMAP, w.HDC, c_int, c_int)
        _signature(g, "SelectObject", w.HGDIOBJ, w.HDC, w.HGDIOBJ)
        _signature(g, "BitBlt", w.BOOL, w.HDC, c_int, c_int, c_int, c_int, w.HDC, c_int, c_int, w.DWORD)
        _signature(g, "GetDIBits", c_int, w.HDC, w.HBITMAP, c_uint, c_uint, c_void_p, POINTER(BITMAPINFO), c_uint)
        _signature(g, "DeleteObject", w.BOOL, w.HGDIOBJ)
        _signature(g, "DeleteDC", w.BOOL, w.HDC)
        if self._dwmapi is not None:
            _signature(self._dwmapi, "DwmGetWindowAttribute", c_long, w.HWND, w.DWORD, c_void_p, w.DWORD)
        if self._shcore is not None:
            _signature(self._shcore, "GetDpiForMonitor", c_long, w.HMONITOR, c_int, POINTER(c_uint), POINTER(c_uint))

    def _send(self, *inputs: INPUT) -> None:
        array = (INPUT * len(inputs))(*inputs)
        sent = self._user32.SendInput(len(inputs), array, sizeof(INPUT))
        if sent != len(inputs):
            raise BackendError(
                f"SendInput was blocked (error {ctypes.get_last_error()}); "
                "input cannot reach windows running as administrator unless this script is elevated too"
            )

    def _mouse_input(self, flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
        event = INPUT(type=INPUT_MOUSE)
        event.union.mi = MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, 0)
        return event

    def _key_input(self, vk: int, scan: int, flags: int) -> INPUT:
        event = INPUT(type=INPUT_KEYBOARD)
        event.union.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        return event

    def mouse_position(self) -> Point:
        point = w.POINT()
        self._user32.GetCursorPos(byref(point))
        return Point(point.x, point.y)

    def mouse_move(self, x: int, y: int) -> None:
        with self._lock:
            self._user32.SetCursorPos(int(x), int(y))

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        with self._lock:
            self._send(self._mouse_input(MOUSEEVENTF_MOVE, int(dx), int(dy)))

    def mouse_button(self, button: Button, down: bool, count: int = 1) -> None:
        with self._lock:
            press, release = _BUTTON_FLAGS[button]
            self._send(self._mouse_input(press if down else release))

    def mouse_scroll(self, dx: int, dy: int) -> None:
        with self._lock:
            if dy:
                self._send(self._mouse_input(MOUSEEVENTF_WHEEL, data=dy * WHEEL_DELTA))
            if dx:
                self._send(self._mouse_input(MOUSEEVENTF_HWHEEL, data=dx * WHEEL_DELTA))

    def buttons_swapped(self) -> bool:
        return bool(self._user32.GetSystemMetrics(SM_SWAPBUTTON))

    def _vk_event(self, vk: int, down: bool) -> INPUT:
        scan = self._user32.MapVirtualKeyW(vk, 0)
        flags = 0 if down else KEYEVENTF_KEYUP
        if vk in _EXTENDED:
            flags |= KEYEVENTF_EXTENDEDKEY
        if scan:
            return self._key_input(vk, scan, flags | KEYEVENTF_SCANCODE)
        return self._key_input(vk, 0, flags)

    def _unicode_events(self, char: str, down: bool) -> list[INPUT]:
        units = char.encode("utf-16-le")
        flags = KEYEVENTF_UNICODE | (0 if down else KEYEVENTF_KEYUP)
        return [self._key_input(0, int.from_bytes(units[i : i + 2], "little"), flags) for i in range(0, len(units), 2)]

    def _layout_key(self, char: str) -> tuple[int, list[int]] | None:
        if len(char.encode("utf-16-le")) != 2:
            return None
        result = self._user32.VkKeyScanW(char)
        if result == -1:
            return None
        vk, state = result & 0xFF, (result >> 8) & 0xFF
        if state & ~1:
            return None
        return vk, [VK_SHIFT] if state & 1 else []

    def key(self, name: str, down: bool) -> None:
        with self._lock:
            if len(name) == 1:
                layout = self._layout_key(name)
                if layout is None:
                    self._send(*self._unicode_events(name, down))
                    return
                vk, modifiers = layout
                if down:
                    self._send(*[self._vk_event(m, True) for m in modifiers], self._vk_event(vk, True))
                else:
                    self._send(self._vk_event(vk, False), *[self._vk_event(m, False) for m in reversed(modifiers)])
                return
            vk = _VK.get(name)
            if vk is None:
                raise InvalidKeyError(f"key {name!r} is not available on Windows")
            self._send(self._vk_event(vk, down))

    def type_char(self, char: str) -> None:
        with self._lock:
            layout = self._layout_key(char)
            if layout is None:
                self._send(*self._unicode_events(char, True), *self._unicode_events(char, False))
                return
            vk, modifiers = layout
            self._send(
                *[self._vk_event(m, True) for m in modifiers],
                self._vk_event(vk, True),
                self._vk_event(vk, False),
                *[self._vk_event(m, False) for m in reversed(modifiers)],
            )

    def monitors(self) -> list[Monitor]:
        found: list[Monitor] = []

        def collect(handle: int, hdc: int, rect: object, data: int) -> bool:
            info = MONITORINFOEXW()
            info.cbSize = sizeof(MONITORINFOEXW)
            if self._user32.GetMonitorInfoW(handle, byref(info)):
                r = info.rcMonitor
                found.append(
                    Monitor(
                        Region(r.left, r.top, r.right - r.left, r.bottom - r.top),
                        self._monitor_scale(handle),
                        bool(info.dwFlags & MONITORINFOF_PRIMARY),
                        info.szDevice,
                    )
                )
            return True

        callback = MONITORENUMPROC(collect)
        self._user32.EnumDisplayMonitors(None, None, callback, 0)
        if not found:
            width, height = self._user32.GetSystemMetrics(0), self._user32.GetSystemMetrics(1)
            found.append(Monitor(Region(0, 0, width, height), 1.0, True, "primary"))
        return found

    def _monitor_scale(self, handle: int) -> float:
        if self._shcore is None:
            return 1.0
        x, y = c_uint(), c_uint()
        if self._shcore.GetDpiForMonitor(handle, MDT_EFFECTIVE_DPI, byref(x), byref(y)) != 0:
            return 1.0
        return x.value / 96.0

    def _read_bitmap(self, memory_dc: int, bitmap: int, width: int, height: int) -> Pixels:
        info = BITMAPINFO()
        info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB
        buffer = (ctypes.c_ubyte * (width * height * 4))()
        rows = self._gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, byref(info), DIB_RGB_COLORS)
        if rows != height:
            raise BackendError(f"GetDIBits failed (error {ctypes.get_last_error()})")
        bgra = np.frombuffer(buffer, np.uint8).reshape(height, width, 4)
        return np.ascontiguousarray(bgra[:, :, 2::-1])

    def capture(self, region: Region) -> Pixels:
        with self._lock:
            screen_dc = self._user32.GetDC(None)
            memory_dc = self._gdi32.CreateCompatibleDC(screen_dc)
            bitmap = self._gdi32.CreateCompatibleBitmap(screen_dc, region.width, region.height)
            previous = self._gdi32.SelectObject(memory_dc, bitmap)
            try:
                ok = self._gdi32.BitBlt(
                    memory_dc,
                    0,
                    0,
                    region.width,
                    region.height,
                    screen_dc,
                    region.left,
                    region.top,
                    SRCCOPY | CAPTUREBLT,
                )
                if not ok:
                    raise BackendError(f"BitBlt failed (error {ctypes.get_last_error()})")
                return self._read_bitmap(memory_dc, bitmap, region.width, region.height)
            finally:
                self._gdi32.SelectObject(memory_dc, previous)
                self._gdi32.DeleteObject(bitmap)
                self._gdi32.DeleteDC(memory_dc)
                self._user32.ReleaseDC(None, screen_dc)

    def _cloaked(self, handle: int) -> bool:
        if self._dwmapi is None:
            return False
        value = c_int()
        result = self._dwmapi.DwmGetWindowAttribute(handle, DWMWA_CLOAKED, byref(value), sizeof(value))
        return result == 0 and value.value != 0

    def _title(self, handle: int) -> str:
        length = self._user32.GetWindowTextLengthW(handle)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(handle, buffer, length + 1)
        return buffer.value

    def list_windows(self) -> list[WindowHandle]:
        found: list[WindowHandle] = []

        def collect(handle: int, data: int) -> bool:
            if handle and self._user32.IsWindowVisible(handle) and not self._cloaked(handle) and self._title(handle):
                found.append(int(handle))
            return True

        callback = WNDENUMPROC(collect)
        self._user32.EnumWindows(callback, 0)
        return found

    def active_window(self) -> WindowHandle | None:
        handle = self._user32.GetForegroundWindow()
        return int(handle) if handle else None

    def _require(self, handle: int) -> None:
        if not self._user32.IsWindow(handle):
            raise WindowNotFoundError(f"window {handle} no longer exists")

    def _rect(self, handle: int) -> w.RECT:
        rect = w.RECT()
        self._user32.GetWindowRect(handle, byref(rect))
        return rect

    def _bounds(self, handle: int) -> Region:
        rect = w.RECT()
        if self._dwmapi is None or self._dwmapi.DwmGetWindowAttribute(
            handle, DWMWA_EXTENDED_FRAME_BOUNDS, byref(rect), sizeof(rect)
        ):
            rect = self._rect(handle)
        return Region(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

    def window_info(self, handle: WindowHandle) -> WindowInfo:
        self._require(handle)
        pid = w.DWORD()
        self._user32.GetWindowThreadProcessId(handle, byref(pid))
        return WindowInfo(
            title=self._title(handle),
            region=self._bounds(handle),
            is_active=self.active_window() == handle,
            is_minimized=bool(self._user32.IsIconic(handle)),
            is_maximized=bool(self._user32.IsZoomed(handle)),
            is_visible=bool(self._user32.IsWindowVisible(handle)),
            pid=int(pid.value),
        )

    def window_activate(self, handle: WindowHandle) -> None:
        with self._lock:
            self._require(handle)
            if self._user32.IsIconic(handle):
                self._user32.ShowWindow(handle, SW_RESTORE)
            if self._user32.SetForegroundWindow(handle) and self.active_window() == handle:
                self._user32.BringWindowToTop(handle)
                return
            foreground = self._user32.GetForegroundWindow()
            other = self._user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
            mine = self._kernel32.GetCurrentThreadId()
            attached = bool(other) and other != mine and bool(self._user32.AttachThreadInput(mine, other, True))
            try:
                self._user32.SetForegroundWindow(handle)
                self._user32.BringWindowToTop(handle)
            finally:
                if attached:
                    self._user32.AttachThreadInput(mine, other, False)
            if self.active_window() != handle:
                self._send(self._vk_event(VK_MENU, True), self._vk_event(VK_MENU, False))
                self._user32.SetForegroundWindow(handle)
                self._user32.BringWindowToTop(handle)
            self._settle(lambda: self.active_window() == handle)

    def _settle(self, condition: Callable[[], bool], timeout: float = 1.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.01)

    def window_set_state(self, handle: WindowHandle, state: WindowState) -> None:
        with self._lock:
            self._require(handle)
            command = {
                WindowState.MINIMIZED: SW_MINIMIZE,
                WindowState.MAXIMIZED: SW_MAXIMIZE,
                WindowState.NORMAL: SW_RESTORE,
                WindowState.HIDDEN: SW_HIDE,
                WindowState.SHOWN: SW_SHOW,
            }[state]
            self._user32.ShowWindow(handle, command)

    def window_set_geometry(self, handle: WindowHandle, region: Region) -> None:
        with self._lock:
            self._require(handle)
            if self._user32.IsZoomed(handle) or self._user32.IsIconic(handle):
                self._user32.ShowWindow(handle, SW_RESTORE)
            outer, inner = self._rect(handle), self._bounds(handle)
            left = inner.left - outer.left
            top = inner.top - outer.top
            right = outer.right - inner.right
            bottom = outer.bottom - inner.bottom
            ok = self._user32.SetWindowPos(
                handle,
                None,
                region.left - left,
                region.top - top,
                region.width + left + right,
                region.height + top + bottom,
                SWP_NOZORDER | SWP_NOACTIVATE,
            )
            if not ok:
                raise BackendError(f"SetWindowPos failed (error {ctypes.get_last_error()})")

    def window_close(self, handle: WindowHandle) -> None:
        with self._lock:
            self._require(handle)
            self._user32.PostMessageW(handle, WM_CLOSE, 0, 0)
            self._settle(lambda: not self._user32.IsWindow(handle))

    def window_capture(self, handle: WindowHandle) -> Pixels:
        with self._lock:
            self._require(handle)
            outer, inner = self._rect(handle), self._bounds(handle)
            width, height = outer.right - outer.left, outer.bottom - outer.top
            if width <= 0 or height <= 0:
                raise BackendError("window has no visible area to capture")
            screen_dc = self._user32.GetDC(None)
            memory_dc = self._gdi32.CreateCompatibleDC(screen_dc)
            bitmap = self._gdi32.CreateCompatibleBitmap(screen_dc, width, height)
            previous = self._gdi32.SelectObject(memory_dc, bitmap)
            try:
                if not self._user32.PrintWindow(handle, memory_dc, PW_RENDERFULLCONTENT):
                    raise BackendError(f"PrintWindow failed (error {ctypes.get_last_error()})")
                pixels = self._read_bitmap(memory_dc, bitmap, width, height)
            finally:
                self._gdi32.SelectObject(memory_dc, previous)
                self._gdi32.DeleteObject(bitmap)
                self._gdi32.DeleteDC(memory_dc)
                self._user32.ReleaseDC(None, screen_dc)
            top, left = inner.top - outer.top, inner.left - outer.left
            return np.ascontiguousarray(pixels[top : top + inner.height, left : left + inner.width])
