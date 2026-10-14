from __future__ import annotations

import importlib
import os
import sys
import threading
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from .._errors import UnsupportedFeatureError, UnsupportedPlatformError
from .._types import Button, Monitor, Point, Region

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    Pixels = npt.NDArray[np.uint8]

__all__ = [
    "Backend",
    "Capabilities",
    "WindowHandle",
    "WindowInfo",
    "WindowState",
    "get_backend",
    "load_backend",
    "select_backend",
    "set_backend",
    "unsupported",
]

WindowHandle = int


@dataclass(frozen=True, slots=True)
class Capabilities:
    read_cursor: bool = True
    relative_mouse: bool = True
    unicode_typing: bool = True
    screen_capture: bool = True
    window_list: bool = True
    window_control: bool = True
    window_capture: bool = False


class WindowState(str, Enum):
    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    HIDDEN = "hidden"
    SHOWN = "shown"


@dataclass(frozen=True, slots=True)
class WindowInfo:
    title: str
    region: Region
    is_active: bool = False
    is_minimized: bool = False
    is_maximized: bool = False
    is_visible: bool = True
    pid: int = 0


class Backend(Protocol):
    name: str
    capabilities: Capabilities

    def mouse_position(self) -> Point: ...

    def mouse_move(self, x: int, y: int) -> None: ...

    def mouse_move_relative(self, dx: int, dy: int) -> None: ...

    def mouse_button(self, button: Button, down: bool, count: int = 1) -> None: ...

    def mouse_scroll(self, dx: int, dy: int) -> None: ...

    def buttons_swapped(self) -> bool: ...

    def key(self, name: str, down: bool) -> None: ...

    def type_char(self, char: str) -> None: ...

    def monitors(self) -> list[Monitor]: ...

    def capture(self, region: Region) -> Pixels: ...

    def list_windows(self) -> list[WindowHandle]: ...

    def active_window(self) -> WindowHandle | None: ...

    def window_info(self, handle: WindowHandle) -> WindowInfo: ...

    def window_activate(self, handle: WindowHandle) -> None: ...

    def window_set_state(self, handle: WindowHandle, state: WindowState) -> None: ...

    def window_set_geometry(self, handle: WindowHandle, region: Region) -> None: ...

    def window_close(self, handle: WindowHandle) -> None: ...

    def window_capture(self, handle: WindowHandle) -> Pixels: ...


def unsupported(backend: str, feature: str, hint: str = "") -> UnsupportedFeatureError:
    message = f"{feature} is not supported by the {backend} backend"
    return UnsupportedFeatureError(f"{message}; {hint}" if hint else message)


_BACKENDS = {
    "windows": ("ironkit.backends.windows", "WindowsBackend"),
    "macos": ("ironkit.backends.macos", "MacBackend"),
    "x11": ("ironkit.backends.x11", "X11Backend"),
    "fake": ("ironkit.backends.fake", "FakeBackend"),
}

_lock = threading.Lock()
_current: Backend | None = None


def load_backend(name: str) -> Backend:
    try:
        module_name, class_name = _BACKENDS[name]
    except KeyError:
        choices = ", ".join(sorted(_BACKENDS))
        raise UnsupportedPlatformError(f"unknown backend {name!r}; choose one of: {choices}") from None
    module = importlib.import_module(module_name)
    backend: Backend = getattr(module, class_name)()
    return backend


def select_backend() -> Backend:
    forced = os.environ.get("IRONKIT_BACKEND")
    if forced:
        return load_backend(forced.lower())
    if sys.platform == "win32":
        return load_backend("windows")
    if sys.platform == "darwin":
        return load_backend("macos")
    if os.environ.get("DISPLAY"):
        return load_backend("x11")
    if os.environ.get("WAYLAND_DISPLAY"):
        raise UnsupportedPlatformError("native Wayland is not supported yet; run under XWayland with DISPLAY set")
    raise UnsupportedPlatformError(f"no display found for platform {sys.platform!r}; set DISPLAY or IRONKIT_BACKEND")


def get_backend() -> Backend:
    global _current
    if _current is None:
        with _lock:
            if _current is None:
                _current = select_backend()
    return _current


def set_backend(backend: Backend | str | None) -> Backend | None:
    global _current
    with _lock:
        previous = _current
        _current = load_backend(backend) if isinstance(backend, str) else backend
    return previous
