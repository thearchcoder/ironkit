from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import numpy.typing as npt

from .._errors import WindowNotFoundError
from .._types import Button, Monitor, Point, Region
from . import Capabilities, WindowHandle, WindowInfo, WindowState

Pixels = npt.NDArray[np.uint8]


@dataclass
class FakeWindow:
    info: WindowInfo
    pixels: Pixels | None = None
    closed: bool = False


class FakeBackend:
    name = "fake"

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        monitors: list[Monitor] | None = None,
        capabilities: Capabilities | None = None,
    ) -> None:
        self.capabilities = capabilities or Capabilities(window_capture=True)
        self._monitors = monitors or [Monitor(Region(0, 0, width, height), 1.0, True, "fake")]
        self.desktop = self._monitors[0].region
        for monitor in self._monitors[1:]:
            self.desktop = self.desktop.union(monitor.region)
        self.framebuffer: Pixels = np.zeros((self.desktop.height, self.desktop.width, 3), np.uint8)
        self.position = self.desktop.center
        self.events: list[tuple[Any, ...]] = []
        self.pressed_keys: set[str] = set()
        self.pressed_buttons: set[Button] = set()
        self.typed: list[str] = []
        self.swapped = False
        self.windows: dict[WindowHandle, FakeWindow] = {}
        self.active: WindowHandle | None = None
        self._next_handle = 1

    def _clamp(self, x: int, y: int) -> Point:
        d = self.desktop
        return Point(min(max(x, d.left), d.right - 1), min(max(y, d.top), d.bottom - 1))

    def mouse_position(self) -> Point:
        return self.position

    def mouse_move(self, x: int, y: int) -> None:
        self.position = self._clamp(x, y)
        self.events.append(("move", self.position.x, self.position.y))

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        self.position = self._clamp(self.position.x + dx, self.position.y + dy)
        self.events.append(("move_relative", dx, dy))

    def mouse_button(self, button: Button, down: bool, count: int = 1) -> None:
        if down:
            self.pressed_buttons.add(button)
        else:
            self.pressed_buttons.discard(button)
        self.events.append(("button", button.value, down, count))

    def mouse_scroll(self, dx: int, dy: int) -> None:
        self.events.append(("scroll", dx, dy))

    def buttons_swapped(self) -> bool:
        return self.swapped

    def key(self, name: str, down: bool) -> None:
        if down:
            self.pressed_keys.add(name)
        else:
            self.pressed_keys.discard(name)
        self.events.append(("key", name, down))

    def type_char(self, char: str) -> None:
        self.typed.append(char)
        self.events.append(("type", char))

    def monitors(self) -> list[Monitor]:
        return list(self._monitors)

    def capture(self, region: Region) -> Pixels:
        out: Pixels = np.zeros((region.height, region.width, 3), np.uint8)
        inside = region.intersect(self.desktop)
        if inside is None:
            return out
        src = self.framebuffer[
            inside.top - self.desktop.top : inside.bottom - self.desktop.top,
            inside.left - self.desktop.left : inside.right - self.desktop.left,
        ]
        out[
            inside.top - region.top : inside.bottom - region.top,
            inside.left - region.left : inside.right - region.left,
        ] = src
        return out

    def paste(self, pixels: Pixels, at: Point | tuple[int, int]) -> None:
        p = Point.of(at)
        h, w = pixels.shape[:2]
        target = Region(p.x, p.y, w, h).intersect(self.desktop)
        if target is None:
            return
        sx, sy = target.left - p.x, target.top - p.y
        self.framebuffer[
            target.top - self.desktop.top : target.bottom - self.desktop.top,
            target.left - self.desktop.left : target.right - self.desktop.left,
        ] = pixels[sy : sy + target.height, sx : sx + target.width, :3]

    def add_window(
        self,
        title: str,
        region: Region | tuple[int, int, int, int],
        pixels: Pixels | None = None,
        active: bool = True,
        pid: int = 0,
    ) -> WindowHandle:
        handle = self._next_handle
        self._next_handle += 1
        self.windows[handle] = FakeWindow(WindowInfo(title, Region.of(region), pid=pid), pixels)
        if active:
            self.active = handle
        return handle

    def _window(self, handle: WindowHandle) -> FakeWindow:
        window = self.windows.get(handle)
        if window is None or window.closed:
            raise WindowNotFoundError(f"window {handle} no longer exists")
        return window

    def list_windows(self) -> list[WindowHandle]:
        handles = [h for h, w in self.windows.items() if not w.closed]
        if self.active in handles:
            handles.remove(self.active)
            handles.insert(0, self.active)
        return handles

    def active_window(self) -> WindowHandle | None:
        return self.active

    def window_info(self, handle: WindowHandle) -> WindowInfo:
        return replace(self._window(handle).info, is_active=handle == self.active)

    def window_activate(self, handle: WindowHandle) -> None:
        window = self._window(handle)
        window.info = replace(window.info, is_minimized=False, is_visible=True)
        self.active = handle
        self.events.append(("activate", handle))

    def window_set_state(self, handle: WindowHandle, state: WindowState) -> None:
        window = self._window(handle)
        info = window.info
        if state is WindowState.MINIMIZED:
            info = replace(info, is_minimized=True, is_maximized=False)
        elif state is WindowState.MAXIMIZED:
            info = replace(info, is_minimized=False, is_maximized=True, region=self._monitors[0].region)
        elif state is WindowState.NORMAL:
            info = replace(info, is_minimized=False, is_maximized=False)
        elif state is WindowState.HIDDEN:
            info = replace(info, is_visible=False)
        elif state is WindowState.SHOWN:
            info = replace(info, is_visible=True)
        window.info = info
        self.events.append(("state", handle, state.value))

    def window_set_geometry(self, handle: WindowHandle, region: Region) -> None:
        window = self._window(handle)
        window.info = replace(window.info, region=region)
        self.events.append(("geometry", handle, tuple(region)))

    def window_close(self, handle: WindowHandle) -> None:
        self._window(handle).closed = True
        if self.active == handle:
            self.active = None
        self.events.append(("close", handle))

    def window_capture(self, handle: WindowHandle) -> Pixels:
        window = self._window(handle)
        if window.pixels is not None:
            return window.pixels.copy()
        return self.capture(window.info.region)
