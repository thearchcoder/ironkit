from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt

from .._errors import (
    BackendError,
    InvalidKeyError,
    PermissionDeniedError,
    UnsupportedPlatformError,
    WindowNotFoundError,
)
from .._types import Button, Monitor, Point, Region
from . import Capabilities, WindowHandle, WindowInfo, WindowState

if sys.platform != "darwin":
    raise UnsupportedPlatformError("the macos backend only runs on macOS")

try:
    import AppKit
    import ApplicationServices as AX
    import Quartz
except ImportError as error:
    raise BackendError(
        "the macOS backend needs pyobjc: pip install pyobjc-framework-Quartz "
        "pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa"
    ) from error

Pixels = npt.NDArray[np.uint8]

_KEYCODES: dict[str, int] = {
    "a": 0x00,
    "s": 0x01,
    "d": 0x02,
    "f": 0x03,
    "h": 0x04,
    "g": 0x05,
    "z": 0x06,
    "x": 0x07,
    "c": 0x08,
    "v": 0x09,
    "b": 0x0B,
    "q": 0x0C,
    "w": 0x0D,
    "e": 0x0E,
    "r": 0x0F,
    "y": 0x10,
    "t": 0x11,
    "1": 0x12,
    "2": 0x13,
    "3": 0x14,
    "4": 0x15,
    "6": 0x16,
    "5": 0x17,
    "=": 0x18,
    "9": 0x19,
    "7": 0x1A,
    "-": 0x1B,
    "8": 0x1C,
    "0": 0x1D,
    "]": 0x1E,
    "o": 0x1F,
    "u": 0x20,
    "[": 0x21,
    "i": 0x22,
    "p": 0x23,
    "l": 0x25,
    "j": 0x26,
    "'": 0x27,
    "k": 0x28,
    ";": 0x29,
    "\\": 0x2A,
    ",": 0x2B,
    "/": 0x2C,
    "n": 0x2D,
    "m": 0x2E,
    ".": 0x2F,
    "`": 0x32,
    "enter": 0x24,
    "tab": 0x30,
    "space": 0x31,
    "backspace": 0x33,
    "escape": 0x35,
    "command": 0x37,
    "win": 0x37,
    "winright": 0x36,
    "shift": 0x38,
    "shiftleft": 0x38,
    "capslock": 0x39,
    "alt": 0x3A,
    "altleft": 0x3A,
    "option": 0x3A,
    "optionleft": 0x3A,
    "ctrl": 0x3B,
    "ctrlleft": 0x3B,
    "shiftright": 0x3C,
    "altright": 0x3D,
    "optionright": 0x3D,
    "ctrlright": 0x3E,
    "fn": 0x3F,
    "decimal": 0x41,
    "multiply": 0x43,
    "add": 0x45,
    "clear": 0x47,
    "numlock": 0x47,
    "divide": 0x4B,
    "subtract": 0x4E,
    "num0": 0x52,
    "num1": 0x53,
    "num2": 0x54,
    "num3": 0x55,
    "num4": 0x56,
    "num5": 0x57,
    "num6": 0x58,
    "num7": 0x59,
    "num8": 0x5B,
    "num9": 0x5C,
    "yen": 0x5D,
    "kana": 0x68,
    "help": 0x72,
    "insert": 0x72,
    "home": 0x73,
    "pageup": 0x74,
    "delete": 0x75,
    "end": 0x77,
    "pagedown": 0x79,
    "left": 0x7B,
    "right": 0x7C,
    "down": 0x7D,
    "up": 0x7E,
    "f1": 0x7A,
    "f2": 0x78,
    "f3": 0x63,
    "f4": 0x76,
    "f5": 0x60,
    "f6": 0x61,
    "f7": 0x62,
    "f8": 0x64,
    "f9": 0x65,
    "f10": 0x6D,
    "f11": 0x67,
    "f12": 0x6F,
    "f13": 0x69,
    "f14": 0x6B,
    "f15": 0x71,
    "f16": 0x6A,
    "f17": 0x40,
    "f18": 0x4F,
    "f19": 0x50,
    "f20": 0x5A,
}

_SHIFTED: dict[str, str] = {
    "~": "`",
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
    ")": "0",
    "_": "-",
    "+": "=",
    "{": "[",
    "}": "]",
    "|": "\\",
    ":": ";",
    '"': "'",
    "<": ",",
    ">": ".",
    "?": "/",
}

_MEDIA_KEYS = {"volumeup": 0, "volumedown": 1, "volumemute": 7, "playpause": 16, "nexttrack": 17, "prevtrack": 18}

_MODIFIER_FLAGS = {
    0x38: 0x20000,
    0x3C: 0x20000,
    0x3B: 0x40000,
    0x3E: 0x40000,
    0x3A: 0x80000,
    0x3D: 0x80000,
    0x37: 0x100000,
    0x36: 0x100000,
    0x3F: 0x800000,
}

_MOUSE_TYPES = {
    Button.LEFT: (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGEventLeftMouseDragged, 0),
    Button.RIGHT: (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGEventRightMouseDragged, 1),
    Button.MIDDLE: (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, Quartz.kCGEventOtherMouseDragged, 2),
}


def _downscale(pixels: Pixels, width: int, height: int) -> Pixels:
    h, w = pixels.shape[:2]
    if (w, h) == (width, height):
        return pixels
    if w % width == 0 and h % height == 0 and w // width == h // height:
        factor = w // width
        blocks = pixels[: height * factor, : width * factor].reshape(height, factor, width, factor, 3)
        return np.ascontiguousarray(blocks.mean(axis=(1, 3)).round().astype(np.uint8))
    rows = (np.arange(height) * h / height).astype(int)
    cols = (np.arange(width) * w / width).astype(int)
    return np.ascontiguousarray(pixels[rows][:, cols])


def _cgimage_pixels(image: Any) -> Pixels:
    width = Quartz.CGImageGetWidth(image)
    height = Quartz.CGImageGetHeight(image)
    stride = Quartz.CGImageGetBytesPerRow(image)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image))
    raw = np.frombuffer(bytes(data), np.uint8).reshape(height, stride)[:, : width * 4].reshape(height, width, 4)
    order = Quartz.CGImageGetBitmapInfo(image) & Quartz.kCGBitmapByteOrderMask
    if order == Quartz.kCGBitmapByteOrder32Little:
        return np.ascontiguousarray(raw[:, :, 2::-1])
    return np.ascontiguousarray(raw[:, :, 1:4])


class MacBackend:
    name = "macos"

    def __init__(self) -> None:
        self.capabilities = Capabilities(window_capture=True)
        self._lock = threading.RLock()
        self._pressed: set[Button] = set()
        self._flags = 0
        self._saved: dict[int, Region] = {}
        self._trusted = False

    def _require_accessibility(self) -> None:
        if self._trusted:
            return
        if not AX.AXIsProcessTrusted():
            options = {AX.kAXTrustedCheckOptionPrompt: True}
            AX.AXIsProcessTrustedWithOptions(options)
            raise PermissionDeniedError(
                "macOS blocked input: allow this app (Terminal, your IDE or Python) in "
                "System Settings > Privacy & Security > Accessibility, then restart it"
            )
        self._trusted = True

    def _require_screen_recording(self) -> None:
        preflight = getattr(Quartz, "CGPreflightScreenCaptureAccess", None)
        if preflight is not None and not preflight():
            request = getattr(Quartz, "CGRequestScreenCaptureAccess", None)
            if request is not None:
                request()
            raise PermissionDeniedError(
                "macOS blocked screen capture: allow this app in "
                "System Settings > Privacy & Security > Screen Recording, then restart it"
            )

    def _post(self, event: Any) -> None:
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _location(self) -> tuple[float, float]:
        point = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        return float(point.x), float(point.y)

    def mouse_position(self) -> Point:
        x, y = self._location()
        return Point(round(x), round(y))

    def _move_event(self, x: float, y: float) -> Any:
        dragging = next((b for b in (Button.LEFT, Button.RIGHT, Button.MIDDLE) if b in self._pressed), None)
        if dragging is None:
            event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y), 0)
        else:
            _, _, drag_type, number = _MOUSE_TYPES[dragging]
            event = Quartz.CGEventCreateMouseEvent(None, drag_type, (x, y), number)
        Quartz.CGEventSetFlags(event, self._flags)
        return event

    def mouse_move(self, x: int, y: int) -> None:
        with self._lock:
            self._require_accessibility()
            self._post(self._move_event(float(x), float(y)))

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        with self._lock:
            self._require_accessibility()
            x, y = self._location()
            event = self._move_event(x + dx, y + dy)
            Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventDeltaX, int(dx))
            Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventDeltaY, int(dy))
            self._post(event)

    def mouse_button(self, button: Button, down: bool, count: int = 1) -> None:
        with self._lock:
            self._require_accessibility()
            press, release, _, number = _MOUSE_TYPES[button]
            event = Quartz.CGEventCreateMouseEvent(None, press if down else release, self._location(), number)
            Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, max(1, count))
            Quartz.CGEventSetFlags(event, self._flags)
            self._post(event)
            if down:
                self._pressed.add(button)
            else:
                self._pressed.discard(button)

    def mouse_scroll(self, dx: int, dy: int) -> None:
        with self._lock:
            self._require_accessibility()
            event = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 2, int(dy), -int(dx))
            Quartz.CGEventSetFlags(event, self._flags)
            self._post(event)

    def buttons_swapped(self) -> bool:
        return False

    def _media_key(self, code: int, down: bool) -> None:
        state = 0xA if down else 0xB
        make = (
            AppKit.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_
        )
        event = make(14, (0, 0), state << 8, 0, 0, None, 8, (code << 16) | (state << 8), -1)
        self._post(event.CGEvent())

    def _key_event(self, keycode: int, down: bool) -> None:
        flag = _MODIFIER_FLAGS.get(keycode, 0)
        if flag:
            self._flags = self._flags | flag if down else self._flags & ~flag
        event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
        Quartz.CGEventSetFlags(event, self._flags)
        self._post(event)

    def key(self, name: str, down: bool) -> None:
        with self._lock:
            self._require_accessibility()
            if name in _MEDIA_KEYS:
                self._media_key(_MEDIA_KEYS[name], down)
                return
            shifted = False
            base = name
            if len(name) == 1:
                if name in _SHIFTED:
                    base, shifted = _SHIFTED[name], True
                elif name.isupper():
                    base, shifted = name.lower(), True
            keycode = _KEYCODES.get(base)
            if keycode is None:
                if len(name) == 1:
                    if down:
                        self._unicode(name)
                    return
                raise InvalidKeyError(f"key {name!r} is not available on macOS")
            if down:
                if shifted:
                    self._key_event(0x38, True)
                self._key_event(keycode, True)
            else:
                self._key_event(keycode, False)
                if shifted:
                    self._key_event(0x38, False)

    def _unicode(self, char: str) -> None:
        units = len(char.encode("utf-16-le")) // 2
        for down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
            Quartz.CGEventKeyboardSetUnicodeString(event, units, char)
            Quartz.CGEventSetFlags(event, self._flags)
            self._post(event)

    def type_char(self, char: str) -> None:
        with self._lock:
            self._require_accessibility()
            self._unicode(char)

    def monitors(self) -> list[Monitor]:
        error, ids, count = Quartz.CGGetActiveDisplayList(32, None, None)
        if error:
            raise BackendError(f"CGGetActiveDisplayList failed ({error})")
        main = Quartz.CGMainDisplayID()
        found: list[Monitor] = []
        for display in ids[:count]:
            bounds = Quartz.CGDisplayBounds(display)
            mode = Quartz.CGDisplayCopyDisplayMode(display)
            scale = 1.0
            if mode is not None and Quartz.CGDisplayModeGetWidth(mode):
                scale = Quartz.CGDisplayModeGetPixelWidth(mode) / Quartz.CGDisplayModeGetWidth(mode)
            region = Region(
                round(bounds.origin.x), round(bounds.origin.y), round(bounds.size.width), round(bounds.size.height)
            )
            found.append(Monitor(region, float(scale), display == main, f"display{display}"))
        return found

    def capture(self, region: Region) -> Pixels:
        with self._lock:
            self._require_screen_recording()
            rect = Quartz.CGRectMake(region.left, region.top, region.width, region.height)
            image = Quartz.CGWindowListCreateImage(
                rect, Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID, Quartz.kCGWindowImageDefault
            )
            if image is None:
                raise BackendError("screen capture failed; check Screen Recording permission")
            return _downscale(_cgimage_pixels(image), region.width, region.height)

    def _window_dicts(self, options: int, relative: int = 0) -> list[Any]:
        found = Quartz.CGWindowListCopyWindowInfo(options, relative)
        return list(found or [])

    def _describe(self, handle: int) -> Any:
        found = self._window_dicts(Quartz.kCGWindowListOptionIncludingWindow, handle)
        if not found:
            raise WindowNotFoundError(f"window {handle} no longer exists")
        return found[0]

    def _title(self, info: Any) -> str:
        return str(info.get(Quartz.kCGWindowName) or info.get(Quartz.kCGWindowOwnerName) or "")

    def _bounds(self, info: Any) -> Region:
        b = info[Quartz.kCGWindowBounds]
        return Region(round(b["X"]), round(b["Y"]), round(b["Width"]), round(b["Height"]))

    def list_windows(self) -> list[WindowHandle]:
        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        return [
            int(info[Quartz.kCGWindowNumber])
            for info in self._window_dicts(options, Quartz.kCGNullWindowID)
            if info.get(Quartz.kCGWindowLayer, 0) == 0 and self._title(info)
        ]

    def active_window(self) -> WindowHandle | None:
        app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        pid = app.processIdentifier()
        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        for info in self._window_dicts(options, Quartz.kCGNullWindowID):
            if info.get(Quartz.kCGWindowOwnerPID) == pid and info.get(Quartz.kCGWindowLayer, 0) == 0:
                return int(info[Quartz.kCGWindowNumber])
        return None

    def _ax_value(self, element: Any, attribute: str) -> Any:
        error, value = AX.AXUIElementCopyAttributeValue(element, attribute, None)
        return None if error else value

    def _ax_point(self, element: Any, attribute: str, kind: int) -> tuple[float, float] | None:
        value = self._ax_value(element, attribute)
        if value is None:
            return None
        ok, point = AX.AXValueGetValue(value, kind, None)
        if not ok:
            return None
        if kind == AX.kAXValueCGPointType:
            return float(point.x), float(point.y)
        return float(point.width), float(point.height)

    def _ax_window(self, handle: int) -> Any:
        info = self._describe(handle)
        pid = int(info[Quartz.kCGWindowOwnerPID])
        bounds = self._bounds(info)
        title = info.get(Quartz.kCGWindowName)
        app = AX.AXUIElementCreateApplication(pid)
        candidates = self._ax_value(app, "AXWindows") or []
        best = None
        for window in candidates:
            position = self._ax_point(window, "AXPosition", AX.kAXValueCGPointType)
            size = self._ax_point(window, "AXSize", AX.kAXValueCGSizeType)
            if position is None or size is None:
                continue
            same = (round(position[0]), round(position[1]), round(size[0]), round(size[1])) == tuple(bounds)
            if same and (not title or self._ax_value(window, "AXTitle") == title):
                return window
            if same and best is None:
                best = window
        if best is None and candidates:
            best = candidates[0]
        if best is None:
            raise WindowNotFoundError(f"window {handle} is not reachable through the Accessibility API")
        return best

    def window_info(self, handle: WindowHandle) -> WindowInfo:
        info = self._describe(handle)
        minimized = False
        try:
            minimized = bool(self._ax_value(self._ax_window(handle), "AXMinimized"))
        except WindowNotFoundError:
            minimized = not bool(info.get(Quartz.kCGWindowIsOnscreen, False))
        return WindowInfo(
            title=self._title(info),
            region=self._bounds(info),
            is_active=self.active_window() == handle,
            is_minimized=minimized,
            is_maximized=handle in self._saved,
            is_visible=bool(info.get(Quartz.kCGWindowIsOnscreen, False)),
            pid=int(info.get(Quartz.kCGWindowOwnerPID, 0)),
        )

    def _app(self, handle: int) -> Any:
        pid = int(self._describe(handle)[Quartz.kCGWindowOwnerPID])
        return AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)

    def _settle(self, condition: Callable[[], bool], timeout: float = 1.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if condition():
                    return
            except WindowNotFoundError:
                return
            time.sleep(0.02)

    def window_activate(self, handle: WindowHandle) -> None:
        with self._lock:
            self._require_accessibility()
            window = self._ax_window(handle)
            AX.AXUIElementSetAttributeValue(window, "AXMinimized", False)
            app = self._app(handle)
            if app is not None:
                app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
            AX.AXUIElementPerformAction(window, "AXRaise")
            self._settle(lambda: self.active_window() == handle)

    def _set_frame(self, window: Any, region: Region) -> None:
        position = AX.AXValueCreate(AX.kAXValueCGPointType, Quartz.CGPointMake(region.left, region.top))
        size = AX.AXValueCreate(AX.kAXValueCGSizeType, Quartz.CGSizeMake(region.width, region.height))
        AX.AXUIElementSetAttributeValue(window, "AXPosition", position)
        AX.AXUIElementSetAttributeValue(window, "AXSize", size)

    def window_set_state(self, handle: WindowHandle, state: WindowState) -> None:
        with self._lock:
            self._require_accessibility()
            window = self._ax_window(handle)
            if state is WindowState.MINIMIZED:
                AX.AXUIElementSetAttributeValue(window, "AXMinimized", True)
            elif state is WindowState.MAXIMIZED:
                current = self._bounds(self._describe(handle))
                self._saved.setdefault(handle, current)
                area = next((m.region for m in self.monitors() if m.region.contains(current.center)), None)
                self._set_frame(window, area or self.monitors()[0].region)
            elif state is WindowState.NORMAL:
                AX.AXUIElementSetAttributeValue(window, "AXMinimized", False)
                saved = self._saved.pop(handle, None)
                if saved is not None:
                    self._set_frame(window, saved)
            elif state is WindowState.HIDDEN:
                app = self._app(handle)
                if app is not None:
                    app.hide()
            elif state is WindowState.SHOWN:
                app = self._app(handle)
                if app is not None:
                    app.unhide()

    def window_set_geometry(self, handle: WindowHandle, region: Region) -> None:
        with self._lock:
            self._require_accessibility()
            self._set_frame(self._ax_window(handle), region)
            self._settle(lambda: self._bounds(self._describe(handle)) == region)

    def window_close(self, handle: WindowHandle) -> None:
        with self._lock:
            self._require_accessibility()
            button = self._ax_value(self._ax_window(handle), "AXCloseButton")
            if button is None:
                raise BackendError("this window has no close button")
            AX.AXUIElementPerformAction(button, "AXPress")
            self._saved.pop(handle, None)
            self._settle(lambda: not self._window_dicts(Quartz.kCGWindowListOptionIncludingWindow, handle))

    def window_capture(self, handle: WindowHandle) -> Pixels:
        with self._lock:
            self._require_screen_recording()
            bounds = self._bounds(self._describe(handle))
            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull,
                Quartz.kCGWindowListOptionIncludingWindow,
                handle,
                Quartz.kCGWindowImageBoundsIgnoreFraming,
            )
            if image is None:
                raise BackendError("window capture failed; check Screen Recording permission")
            return _downscale(_cgimage_pixels(image), bounds.width, bounds.height)
