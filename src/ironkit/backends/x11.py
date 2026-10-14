from __future__ import annotations

import atexit
import ctypes
import ctypes.util
import threading
import time
from collections.abc import Callable
from ctypes import (
    CFUNCTYPE,
    POINTER,
    Structure,
    Union,
    byref,
    c_char_p,
    c_int,
    c_long,
    c_ubyte,
    c_uint,
    c_ulong,
    c_void_p,
)

import numpy as np
import numpy.typing as npt

from .._errors import BackendError, InvalidKeyError, WindowNotFoundError
from .._types import Button, Monitor, Point, Region
from . import Capabilities, WindowHandle, WindowInfo, WindowState, unsupported

Pixels = npt.NDArray[np.uint8]

Display = c_void_p
XID = c_ulong
Atom = c_ulong
KeySym = c_ulong

_SUCCESS = 0
_ANY_PROPERTY_TYPE = 0
_Z_PIXMAP = 2
_ALL_PLANES = c_ulong(-1).value
_IS_VIEWABLE = 2
_ICONIC_STATE = 3
_CLIENT_MESSAGE = 33
_SUBSTRUCTURE_MASK = (1 << 19) | (1 << 20)
_STATIC_GRAVITY = 10
_REVERT_TO_PARENT = 2


class XErrorEvent(Structure):
    _fields_ = [
        ("type", c_int),
        ("display", Display),
        ("resourceid", XID),
        ("serial", c_ulong),
        ("error_code", c_ubyte),
        ("request_code", c_ubyte),
        ("minor_code", c_ubyte),
    ]


class XImage(Structure):
    _fields_ = [
        ("width", c_int),
        ("height", c_int),
        ("xoffset", c_int),
        ("format", c_int),
        ("data", c_void_p),
        ("byte_order", c_int),
        ("bitmap_unit", c_int),
        ("bitmap_bit_order", c_int),
        ("bitmap_pad", c_int),
        ("depth", c_int),
        ("bytes_per_line", c_int),
        ("bits_per_pixel", c_int),
        ("red_mask", c_ulong),
        ("green_mask", c_ulong),
        ("blue_mask", c_ulong),
    ]


class XWindowAttributes(Structure):
    _fields_ = [
        ("x", c_int),
        ("y", c_int),
        ("width", c_int),
        ("height", c_int),
        ("border_width", c_int),
        ("depth", c_int),
        ("visual", c_void_p),
        ("root", XID),
        ("c_class", c_int),
        ("bit_gravity", c_int),
        ("win_gravity", c_int),
        ("backing_store", c_int),
        ("backing_planes", c_ulong),
        ("backing_pixel", c_ulong),
        ("save_under", c_int),
        ("colormap", XID),
        ("map_installed", c_int),
        ("map_state", c_int),
        ("all_event_masks", c_long),
        ("your_event_mask", c_long),
        ("do_not_propagate_mask", c_long),
        ("override_redirect", c_int),
        ("screen", c_void_p),
    ]


class XRRMonitorInfo(Structure):
    _fields_ = [
        ("name", Atom),
        ("primary", c_int),
        ("automatic", c_int),
        ("noutput", c_int),
        ("x", c_int),
        ("y", c_int),
        ("width", c_int),
        ("height", c_int),
        ("mwidth", c_int),
        ("mheight", c_int),
        ("outputs", c_void_p),
    ]


class _ClientMessageData(Union):
    _fields_ = [("b", ctypes.c_char * 20), ("l", c_long * 5)]


class XClientMessageEvent(Structure):
    _fields_ = [
        ("type", c_int),
        ("serial", c_ulong),
        ("send_event", c_int),
        ("display", Display),
        ("window", XID),
        ("message_type", Atom),
        ("format", c_int),
        ("data", _ClientMessageData),
    ]


class XEvent(Union):
    _fields_ = [("xclient", XClientMessageEvent), ("pad", c_long * 24)]


ErrorHandler = CFUNCTYPE(c_int, Display, POINTER(XErrorEvent))

_NAMED_KEYSYMS: dict[str, str] = {
    "backspace": "BackSpace",
    "tab": "Tab",
    "enter": "Return",
    "space": "space",
    "escape": "Escape",
    "delete": "Delete",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "pageup": "Prior",
    "pagedown": "Next",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "shift": "Shift_L",
    "shiftleft": "Shift_L",
    "shiftright": "Shift_R",
    "ctrl": "Control_L",
    "ctrlleft": "Control_L",
    "ctrlright": "Control_R",
    "alt": "Alt_L",
    "altleft": "Alt_L",
    "altright": "Alt_R",
    "win": "Super_L",
    "winright": "Super_R",
    "command": "Super_L",
    "option": "Alt_L",
    "optionleft": "Alt_L",
    "optionright": "Alt_R",
    "capslock": "Caps_Lock",
    "numlock": "Num_Lock",
    "scrolllock": "Scroll_Lock",
    "printscreen": "Print",
    "pause": "Pause",
    "apps": "Menu",
    "help": "Help",
    "select": "Select",
    "execute": "Execute",
    "clear": "Clear",
    "sleep": "XF86Sleep",
    "add": "KP_Add",
    "subtract": "KP_Subtract",
    "multiply": "KP_Multiply",
    "divide": "KP_Divide",
    "decimal": "KP_Decimal",
    "separator": "KP_Separator",
    "volumeup": "XF86AudioRaiseVolume",
    "volumedown": "XF86AudioLowerVolume",
    "volumemute": "XF86AudioMute",
    "playpause": "XF86AudioPlay",
    "nexttrack": "XF86AudioNext",
    "prevtrack": "XF86AudioPrev",
    "stop": "XF86AudioStop",
    "browserback": "XF86Back",
    "browserforward": "XF86Forward",
    "browserrefresh": "XF86Refresh",
    "browserstop": "XF86Stop",
    "browsersearch": "XF86Search",
    "browserfavorites": "XF86Favorites",
    "browserhome": "XF86HomePage",
    "launchmail": "XF86Mail",
    "launchmediaselect": "XF86AudioMedia",
    "launchapp1": "XF86MyComputer",
    "launchapp2": "XF86Calculator",
    "convert": "Henkan",
    "nonconvert": "Muhenkan",
    "modechange": "Mode_switch",
    "hangul": "Hangul",
    "hanja": "Hangul_Hanja",
    "kana": "Hiragana_Katakana",
    "kanji": "Kanji",
    "yen": "yen",
    **{f"num{i}": f"KP_{i}" for i in range(10)},
    **{f"f{i}": f"F{i}" for i in range(1, 25)},
}

_BUTTONS = {Button.LEFT: 1, Button.MIDDLE: 2, Button.RIGHT: 3}


def _load(name: str, fallback: str) -> ctypes.CDLL:
    path = ctypes.util.find_library(name) or fallback
    try:
        return ctypes.CDLL(path)
    except OSError as error:
        raise BackendError(f"cannot load {path}: install the X11 client libraries ({error})") from None


def _signature(lib: ctypes.CDLL, name: str, restype: object, *argtypes: object) -> None:
    fn = getattr(lib, name)
    fn.restype = restype
    fn.argtypes = list(argtypes)


def _char_keysym(char: str) -> int:
    code = ord(char)
    if 0x20 <= code <= 0x7E or 0xA0 <= code <= 0xFF:
        return code
    return 0x01000000 | code


def _mask_shift(mask: int) -> tuple[int, int]:
    if mask == 0:
        return 0, 0
    shift = (mask & -mask).bit_length() - 1
    bits = bin(mask >> shift).count("1")
    return shift, bits


class X11Backend:
    name = "x11"

    def __init__(self, display: str | None = None) -> None:
        self.capabilities = Capabilities(window_capture=False)
        self._lock = threading.RLock()
        self._x = _load("X11", "libX11.so.6")
        self._xtst = _load("Xtst", "libXtst.so.6")
        try:
            self._xrandr: ctypes.CDLL | None = _load("Xrandr", "libXrandr.so.2")
        except BackendError:
            self._xrandr = None
        self._declare()
        self._x.XInitThreads()
        self._errors: list[int] = []
        self._handler = ErrorHandler(self._on_error)
        self._x.XSetErrorHandler(self._handler)
        self._display = self._x.XOpenDisplay(display.encode() if display else None)
        if not self._display:
            raise BackendError(f"cannot open X display {display or '$DISPLAY'}")
        self._root = self._x.XDefaultRootWindow(self._display)
        self._screen = self._x.XDefaultScreen(self._display)
        self._atoms: dict[str, int] = {}
        self._scratch: dict[int, int] = {}
        self._fallback_iconified: set[int] = set()
        self._fallback_saved: dict[int, Region] = {}
        atexit.register(self.close)

    def _declare(self) -> None:
        x, t = self._x, self._xtst
        _signature(x, "XInitThreads", c_int)
        _signature(x, "XSetErrorHandler", c_void_p, ErrorHandler)
        _signature(x, "XOpenDisplay", Display, c_char_p)
        _signature(x, "XCloseDisplay", c_int, Display)
        _signature(x, "XDefaultRootWindow", XID, Display)
        _signature(x, "XDefaultScreen", c_int, Display)
        _signature(x, "XDisplayWidth", c_int, Display, c_int)
        _signature(x, "XDisplayHeight", c_int, Display, c_int)
        _signature(x, "XFlush", c_int, Display)
        _signature(x, "XSync", c_int, Display, c_int)
        _signature(x, "XFree", c_int, c_void_p)
        _signature(
            x,
            "XQueryPointer",
            c_int,
            Display,
            XID,
            POINTER(XID),
            POINTER(XID),
            POINTER(c_int),
            POINTER(c_int),
            POINTER(c_int),
            POINTER(c_int),
            POINTER(c_uint),
        )
        _signature(x, "XGetPointerMapping", c_int, Display, POINTER(c_ubyte), c_int)
        _signature(x, "XStringToKeysym", KeySym, c_char_p)
        _signature(x, "XKeysymToKeycode", c_ubyte, Display, KeySym)
        _signature(x, "XkbKeycodeToKeysym", KeySym, Display, c_ubyte, c_int, c_int)
        _signature(x, "XDisplayKeycodes", c_int, Display, POINTER(c_int), POINTER(c_int))
        _signature(x, "XGetKeyboardMapping", POINTER(KeySym), Display, c_ubyte, c_int, POINTER(c_int))
        _signature(x, "XChangeKeyboardMapping", c_int, Display, c_int, c_int, POINTER(KeySym), c_int)
        _signature(x, "XGetImage", POINTER(XImage), Display, XID, c_int, c_int, c_uint, c_uint, c_ulong, c_int)
        _signature(x, "XDestroyImage", c_int, POINTER(XImage))
        _signature(x, "XInternAtom", Atom, Display, c_char_p, c_int)
        _signature(x, "XGetAtomName", c_void_p, Display, Atom)
        _signature(
            x,
            "XGetWindowProperty",
            c_int,
            Display,
            XID,
            Atom,
            c_long,
            c_long,
            c_int,
            Atom,
            POINTER(Atom),
            POINTER(c_int),
            POINTER(c_ulong),
            POINTER(c_ulong),
            POINTER(c_void_p),
        )
        _signature(x, "XGetWindowAttributes", c_int, Display, XID, POINTER(XWindowAttributes))
        _signature(
            x,
            "XTranslateCoordinates",
            c_int,
            Display,
            XID,
            XID,
            c_int,
            c_int,
            POINTER(c_int),
            POINTER(c_int),
            POINTER(XID),
        )
        _signature(
            x,
            "XQueryTree",
            c_int,
            Display,
            XID,
            POINTER(XID),
            POINTER(XID),
            POINTER(POINTER(XID)),
            POINTER(c_uint),
        )
        _signature(x, "XFetchName", c_int, Display, XID, POINTER(c_void_p))
        _signature(x, "XGetInputFocus", c_int, Display, POINTER(XID), POINTER(c_int))
        _signature(x, "XSetInputFocus", c_int, Display, XID, c_int, c_ulong)
        _signature(x, "XSendEvent", c_int, Display, XID, c_int, c_long, POINTER(XEvent))
        _signature(x, "XMapRaised", c_int, Display, XID)
        _signature(x, "XMapWindow", c_int, Display, XID)
        _signature(x, "XUnmapWindow", c_int, Display, XID)
        _signature(x, "XRaiseWindow", c_int, Display, XID)
        _signature(x, "XIconifyWindow", c_int, Display, XID, c_int)
        _signature(x, "XMoveResizeWindow", c_int, Display, XID, c_int, c_int, c_uint, c_uint)
        _signature(x, "XDestroyWindow", c_int, Display, XID)
        _signature(t, "XTestFakeMotionEvent", c_int, Display, c_int, c_int, c_int, c_ulong)
        _signature(t, "XTestFakeRelativeMotionEvent", c_int, Display, c_int, c_int, c_ulong)
        _signature(t, "XTestFakeButtonEvent", c_int, Display, c_uint, c_int, c_ulong)
        _signature(t, "XTestFakeKeyEvent", c_int, Display, c_uint, c_int, c_ulong)
        if self._xrandr is not None:
            _signature(self._xrandr, "XRRGetMonitors", POINTER(XRRMonitorInfo), Display, XID, c_int, POINTER(c_int))
            _signature(self._xrandr, "XRRFreeMonitors", None, POINTER(XRRMonitorInfo))

    def _on_error(self, display: int, event: ctypes._Pointer[XErrorEvent]) -> int:
        self._errors.append(int(event.contents.error_code))
        return 0

    def close(self) -> None:
        with self._lock:
            if not self._display:
                return
            self._restore_scratch()
            self._x.XCloseDisplay(self._display)
            self._display = None

    def _flush(self) -> None:
        self._x.XFlush(self._display)

    def _checked(self) -> bool:
        self._x.XSync(self._display, 0)
        failed = bool(self._errors)
        self._errors.clear()
        return not failed

    def mouse_position(self) -> Point:
        with self._lock:
            root, child = XID(), XID()
            rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
            mask = c_uint()
            self._x.XQueryPointer(
                self._display,
                self._root,
                byref(root),
                byref(child),
                byref(rx),
                byref(ry),
                byref(wx),
                byref(wy),
                byref(mask),
            )
            return Point(rx.value, ry.value)

    def mouse_move(self, x: int, y: int) -> None:
        with self._lock:
            self._xtst.XTestFakeMotionEvent(self._display, -1, int(x), int(y), 0)
            self._flush()

    def mouse_move_relative(self, dx: int, dy: int) -> None:
        with self._lock:
            self._xtst.XTestFakeRelativeMotionEvent(self._display, int(dx), int(dy), 0)
            self._flush()

    def mouse_button(self, button: Button, down: bool, count: int = 1) -> None:
        with self._lock:
            self._xtst.XTestFakeButtonEvent(self._display, _BUTTONS[button], int(down), 0)
            self._flush()

    def mouse_scroll(self, dx: int, dy: int) -> None:
        with self._lock:
            for amount, positive, negative in ((dy, 4, 5), (dx, 7, 6)):
                code = positive if amount > 0 else negative
                for _ in range(abs(amount)):
                    self._xtst.XTestFakeButtonEvent(self._display, code, 1, 0)
                    self._xtst.XTestFakeButtonEvent(self._display, code, 0, 0)
            self._flush()

    def buttons_swapped(self) -> bool:
        with self._lock:
            mapping = (c_ubyte * 8)()
            count = self._x.XGetPointerMapping(self._display, mapping, 8)
            return count >= 3 and mapping[0] == 3

    def _scratch_keycode(self, keysym: int) -> int:
        for code, mapped in self._scratch.items():
            if mapped == keysym:
                return code
        low, high = c_int(), c_int()
        self._x.XDisplayKeycodes(self._display, byref(low), byref(high))
        per = c_int()
        count = high.value - low.value + 1
        table = self._x.XGetKeyboardMapping(self._display, low.value, count, byref(per))
        try:
            free = [
                low.value + i
                for i in range(count)
                if all(table[i * per.value + j] == 0 for j in range(per.value)) or (low.value + i) in self._scratch
            ]
        finally:
            self._x.XFree(table)
        if not free:
            raise BackendError("no spare keycode available to type this character")
        code = free[-1 - (len(self._scratch) % min(len(free), 4))]
        syms = (KeySym * 2)(keysym, keysym)
        self._x.XChangeKeyboardMapping(self._display, code, 2, syms, 1)
        self._x.XSync(self._display, 0)
        self._scratch[code] = keysym
        time.sleep(0.01)
        return code

    def _restore_scratch(self) -> None:
        for code in list(self._scratch):
            syms = (KeySym * 2)(0, 0)
            self._x.XChangeKeyboardMapping(self._display, code, 2, syms, 1)
        if self._scratch:
            self._x.XSync(self._display, 0)
        self._scratch.clear()

    def _resolve(self, keysym: int) -> tuple[int, bool]:
        code = int(self._x.XKeysymToKeycode(self._display, keysym))
        if code:
            if self._x.XkbKeycodeToKeysym(self._display, code, 0, 0) == keysym:
                return code, False
            if self._x.XkbKeycodeToKeysym(self._display, code, 0, 1) == keysym:
                return code, True
        return self._scratch_keycode(keysym), False

    def _keysym(self, name: str) -> int:
        if len(name) == 1:
            return _char_keysym(name)
        symbol = _NAMED_KEYSYMS.get(name)
        if symbol is None:
            raise InvalidKeyError(f"key {name!r} is not available on X11")
        keysym = int(self._x.XStringToKeysym(symbol.encode()))
        if not keysym:
            raise InvalidKeyError(f"key {name!r} has no X11 keysym")
        return keysym

    def _send(self, code: int, down: bool) -> None:
        self._xtst.XTestFakeKeyEvent(self._display, code, int(down), 0)

    def key(self, name: str, down: bool) -> None:
        with self._lock:
            keysym = self._keysym(name)
            if len(name) == 1:
                code, shifted = self._resolve(keysym)
            else:
                code = int(self._x.XKeysymToKeycode(self._display, keysym)) or self._scratch_keycode(keysym)
                shifted = False
            shift = int(self._x.XKeysymToKeycode(self._display, self._x.XStringToKeysym(b"Shift_L")))
            if down:
                if shifted:
                    self._send(shift, True)
                self._send(code, True)
            else:
                self._send(code, False)
                if shifted:
                    self._send(shift, False)
            self._flush()

    def type_char(self, char: str) -> None:
        with self._lock:
            code, shifted = self._resolve(_char_keysym(char))
            shift = int(self._x.XKeysymToKeycode(self._display, self._x.XStringToKeysym(b"Shift_L")))
            if shifted:
                self._send(shift, True)
            self._send(code, True)
            self._send(code, False)
            if shifted:
                self._send(shift, False)
            self._flush()

    def monitors(self) -> list[Monitor]:
        with self._lock:
            found: list[Monitor] = []
            if self._xrandr is not None:
                count = c_int()
                info = self._xrandr.XRRGetMonitors(self._display, self._root, 1, byref(count))
                if info:
                    try:
                        for i in range(count.value):
                            m = info[i]
                            name = self._atom_name(int(m.name)) if m.name else f"monitor{i}"
                            found.append(Monitor(Region(m.x, m.y, m.width, m.height), 1.0, bool(m.primary), name))
                    finally:
                        self._xrandr.XRRFreeMonitors(info)
            if not found:
                width = self._x.XDisplayWidth(self._display, self._screen)
                height = self._x.XDisplayHeight(self._display, self._screen)
                found.append(Monitor(Region(0, 0, width, height), 1.0, True, "default"))
            if not any(m.primary for m in found):
                first = found[0]
                found[0] = Monitor(first.region, first.scale, True, first.name)
            return found

    def _atom_name(self, atom: int) -> str:
        pointer = self._x.XGetAtomName(self._display, atom)
        if not pointer:
            return ""
        try:
            return ctypes.string_at(pointer).decode("utf-8", "replace")
        finally:
            self._x.XFree(pointer)

    def _root_region(self) -> Region:
        width = self._x.XDisplayWidth(self._display, self._screen)
        height = self._x.XDisplayHeight(self._display, self._screen)
        return Region(0, 0, width, height)

    def capture(self, region: Region) -> Pixels:
        with self._lock:
            out: Pixels = np.zeros((region.height, region.width, 3), np.uint8)
            inside = region.intersect(self._root_region())
            if inside is None:
                return out
            image = self._x.XGetImage(
                self._display, self._root, inside.left, inside.top, inside.width, inside.height, _ALL_PLANES, _Z_PIXMAP
            )
            if not image:
                self._errors.clear()
                raise BackendError(f"XGetImage failed for region {tuple(inside)}")
            try:
                pixels = self._convert(image.contents)
            finally:
                self._x.XDestroyImage(image)
            top, left = inside.top - region.top, inside.left - region.left
            out[top : top + inside.height, left : left + inside.width] = pixels
            return out

    def _convert(self, image: XImage) -> Pixels:
        width, height, stride, bpp = image.width, image.height, image.bytes_per_line, image.bits_per_pixel
        raw = np.ctypeslib.as_array(ctypes.cast(image.data, POINTER(c_ubyte)), shape=(height * stride,))
        rows = raw.reshape(height, stride)
        if bpp == 32:
            dtype = "<u4" if image.byte_order == 0 else ">u4"
            values = rows[:, : width * 4].copy().view(dtype).reshape(height, width).astype(np.uint32)
        elif bpp == 16:
            dtype = "<u2" if image.byte_order == 0 else ">u2"
            values = rows[:, : width * 2].copy().view(dtype).reshape(height, width).astype(np.uint32)
        elif bpp == 24:
            b = rows[:, : width * 3].reshape(height, width, 3).astype(np.uint32)
            if image.byte_order == 0:
                values = b[:, :, 0] | (b[:, :, 1] << 8) | (b[:, :, 2] << 16)
            else:
                values = (b[:, :, 0] << 16) | (b[:, :, 1] << 8) | b[:, :, 2]
        else:
            raise BackendError(f"unsupported X image format: {bpp} bits per pixel")
        out: Pixels = np.empty((height, width, 3), np.uint8)
        for channel, mask in enumerate((image.red_mask, image.green_mask, image.blue_mask)):
            shift, bits = _mask_shift(int(mask))
            if bits == 0:
                out[:, :, channel] = 0
                continue
            component = (values & np.uint32(mask)) >> np.uint32(shift)
            if bits == 8:
                out[:, :, channel] = component
            else:
                out[:, :, channel] = (component * 255 // ((1 << bits) - 1)).astype(np.uint8)
        return out

    def _atom(self, name: str) -> int:
        atom = self._atoms.get(name)
        if atom is None:
            atom = int(self._x.XInternAtom(self._display, name.encode(), 0))
            self._atoms[name] = atom
        return atom

    def _property(self, window: int, name: str) -> tuple[int, list[int] | bytes] | None:
        actual_type, actual_format = Atom(), c_int()
        items, remaining = c_ulong(), c_ulong()
        data = c_void_p()
        status = self._x.XGetWindowProperty(
            self._display,
            window,
            self._atom(name),
            0,
            1 << 20,
            0,
            _ANY_PROPERTY_TYPE,
            byref(actual_type),
            byref(actual_format),
            byref(items),
            byref(remaining),
            byref(data),
        )
        if status != _SUCCESS or not data.value:
            return None
        try:
            if actual_type.value == 0:
                return None
            count = items.value
            if actual_format.value == 8:
                return int(actual_type.value), ctypes.string_at(data.value, count)
            if actual_format.value == 16:
                return int(actual_type.value), list(ctypes.cast(data, POINTER(ctypes.c_ushort))[:count])
            return int(actual_type.value), [int(v) for v in ctypes.cast(data, POINTER(c_ulong))[:count]]
        finally:
            self._x.XFree(data)

    def _ints(self, window: int, name: str) -> list[int]:
        found = self._property(window, name)
        if found is None or isinstance(found[1], bytes):
            return []
        return found[1]

    def _has_wm(self) -> bool:
        return bool(self._ints(self._root, "_NET_SUPPORTING_WM_CHECK"))

    def _supported(self, name: str) -> bool:
        return self._atom(name) in self._ints(self._root, "_NET_SUPPORTED")

    def _attributes(self, window: int) -> XWindowAttributes | None:
        attrs = XWindowAttributes()
        ok = self._x.XGetWindowAttributes(self._display, window, byref(attrs))
        if not ok or not self._checked():
            return None
        return attrs

    def _tree_windows(self) -> list[int]:
        root, parent = XID(), XID()
        children = POINTER(XID)()
        count = c_uint()
        if not self._x.XQueryTree(self._display, self._root, byref(root), byref(parent), byref(children), byref(count)):
            return []
        try:
            handles = [int(children[i]) for i in range(count.value)]
        finally:
            if children:
                self._x.XFree(children)
        visible: list[int] = []
        for handle in reversed(handles):
            attrs = self._attributes(handle)
            if attrs is None or attrs.override_redirect:
                continue
            if attrs.map_state == _IS_VIEWABLE or handle in self._fallback_iconified:
                visible.append(handle)
        return visible

    def list_windows(self) -> list[WindowHandle]:
        with self._lock:
            stacked = self._ints(self._root, "_NET_CLIENT_LIST_STACKING")
            if stacked:
                return list(reversed(stacked))
            clients = self._ints(self._root, "_NET_CLIENT_LIST")
            if clients:
                return list(reversed(clients))
            return self._tree_windows()

    def active_window(self) -> WindowHandle | None:
        with self._lock:
            active = self._ints(self._root, "_NET_ACTIVE_WINDOW")
            if active:
                return active[0] or None
            focus, revert = XID(), c_int()
            self._x.XGetInputFocus(self._display, byref(focus), byref(revert))
            value = int(focus.value)
            return value if value > 1 and value != self._root else None

    def _title(self, window: int) -> str:
        found = self._property(window, "_NET_WM_NAME")
        if found is not None and isinstance(found[1], bytes):
            return found[1].decode("utf-8", "replace")
        name = c_void_p()
        if self._x.XFetchName(self._display, window, byref(name)) and name.value:
            try:
                return ctypes.string_at(name.value).decode("latin-1")
            finally:
                self._x.XFree(name)
        return ""

    def window_info(self, handle: WindowHandle) -> WindowInfo:
        with self._lock:
            attrs = self._attributes(handle)
            if attrs is None:
                raise WindowNotFoundError(f"window {handle} no longer exists")
            x, y, child = c_int(), c_int(), XID()
            self._x.XTranslateCoordinates(self._display, handle, self._root, 0, 0, byref(x), byref(y), byref(child))
            states = set(self._ints(handle, "_NET_WM_STATE"))
            wm_state = self._ints(handle, "WM_STATE")
            minimized = (
                self._atom("_NET_WM_STATE_HIDDEN") in states
                or (bool(wm_state) and wm_state[0] == _ICONIC_STATE)
                or handle in self._fallback_iconified
            )
            maximized = (
                self._atom("_NET_WM_STATE_MAXIMIZED_VERT") in states
                and self._atom("_NET_WM_STATE_MAXIMIZED_HORZ") in states
            ) or handle in self._fallback_saved
            pid = self._ints(handle, "_NET_WM_PID")
            return WindowInfo(
                title=self._title(handle),
                region=Region(x.value, y.value, attrs.width, attrs.height),
                is_active=self.active_window() == handle,
                is_minimized=minimized,
                is_maximized=maximized,
                is_visible=attrs.map_state == _IS_VIEWABLE,
                pid=pid[0] if pid else 0,
            )

    def _message(self, window: int, target: int, name: str, values: list[int], mask: int) -> None:
        event = XEvent()
        event.xclient.type = _CLIENT_MESSAGE
        event.xclient.send_event = 1
        event.xclient.window = window
        event.xclient.message_type = self._atom(name)
        event.xclient.format = 32
        for i, value in enumerate(values[:5]):
            event.xclient.data.l[i] = value
        self._x.XSendEvent(self._display, target, 0, mask, byref(event))

    def window_activate(self, handle: WindowHandle) -> None:
        with self._lock:
            self._require(handle)
            self._fallback_iconified.discard(handle)
            if self._has_wm():
                current = self.active_window() or 0
                self._message(handle, self._root, "_NET_ACTIVE_WINDOW", [2, 0, current], _SUBSTRUCTURE_MASK)
            else:
                self._x.XMapRaised(self._display, handle)
                self._x.XSync(self._display, 0)
                self._x.XSetInputFocus(self._display, handle, _REVERT_TO_PARENT, 0)
            self._checked()
            self._settle(lambda: self.active_window() == handle)

    def _settle(self, condition: Callable[[], bool], timeout: float = 1.0) -> None:
        self._x.XSync(self._display, 0)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if condition():
                    return
            except WindowNotFoundError:
                return
            time.sleep(0.01)

    def _require(self, handle: int) -> None:
        if self._attributes(handle) is None:
            raise WindowNotFoundError(f"window {handle} no longer exists")

    def _wm_state(self, handle: int, add: bool, *names: str) -> None:
        atoms = [self._atom(n) for n in names] + [0, 0]
        self._message(
            handle, self._root, "_NET_WM_STATE", [1 if add else 0, atoms[0], atoms[1], 2, 0], _SUBSTRUCTURE_MASK
        )

    def window_set_state(self, handle: WindowHandle, state: WindowState) -> None:
        with self._lock:
            self._require(handle)
            wm = self._has_wm()
            if state is WindowState.MINIMIZED:
                if wm:
                    self._x.XIconifyWindow(self._display, handle, self._screen)
                else:
                    self._fallback_iconified.add(handle)
                    self._x.XUnmapWindow(self._display, handle)
            elif state is WindowState.MAXIMIZED:
                if wm:
                    self._wm_state(handle, True, "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ")
                else:
                    info = self.window_info(handle)
                    self._fallback_saved.setdefault(handle, info.region)
                    area = next((m.region for m in self.monitors() if m.region.contains(info.region.center)), None)
                    area = area or self.monitors()[0].region
                    self._x.XMoveResizeWindow(self._display, handle, area.left, area.top, area.width, area.height)
            elif state is WindowState.NORMAL:
                if wm:
                    self._wm_state(handle, False, "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ")
                    if self.window_info(handle).is_minimized:
                        self._x.XMapWindow(self._display, handle)
                        current = self.active_window() or 0
                        self._message(handle, self._root, "_NET_ACTIVE_WINDOW", [2, 0, current], _SUBSTRUCTURE_MASK)
                else:
                    if handle in self._fallback_iconified:
                        self._fallback_iconified.discard(handle)
                        self._x.XMapWindow(self._display, handle)
                    saved = self._fallback_saved.pop(handle, None)
                    if saved is not None:
                        self._x.XMoveResizeWindow(
                            self._display, handle, saved.left, saved.top, saved.width, saved.height
                        )
            elif state is WindowState.HIDDEN:
                self._x.XUnmapWindow(self._display, handle)
            elif state is WindowState.SHOWN:
                self._x.XMapWindow(self._display, handle)
            self._checked()
            self._settle(lambda: self._reached(handle, state))

    def _reached(self, handle: int, state: WindowState) -> bool:
        info = self.window_info(handle)
        if state is WindowState.MINIMIZED:
            return info.is_minimized
        if state is WindowState.MAXIMIZED:
            return info.is_maximized
        if state is WindowState.NORMAL:
            return not info.is_minimized and not info.is_maximized and info.is_visible
        if state is WindowState.HIDDEN:
            return not info.is_visible
        return info.is_visible

    def window_set_geometry(self, handle: WindowHandle, region: Region) -> None:
        with self._lock:
            self._require(handle)
            width, height = max(1, region.width), max(1, region.height)
            if self._has_wm() and self._supported("_NET_MOVERESIZE_WINDOW"):
                flags = _STATIC_GRAVITY | (0xF << 8) | (2 << 12)
                self._message(
                    handle,
                    self._root,
                    "_NET_MOVERESIZE_WINDOW",
                    [flags, region.left, region.top, width, height],
                    _SUBSTRUCTURE_MASK,
                )
            else:
                self._x.XMoveResizeWindow(self._display, handle, region.left, region.top, width, height)
            self._checked()
            target = Region(region.left, region.top, width, height)
            self._settle(lambda: self.window_info(handle).region == target)

    def window_close(self, handle: WindowHandle) -> None:
        with self._lock:
            self._require(handle)
            if self._has_wm() and self._supported("_NET_CLOSE_WINDOW"):
                self._message(handle, self._root, "_NET_CLOSE_WINDOW", [0, 2], _SUBSTRUCTURE_MASK)
            elif self._atom("WM_DELETE_WINDOW") in self._ints(handle, "WM_PROTOCOLS"):
                self._message(handle, handle, "WM_PROTOCOLS", [self._atom("WM_DELETE_WINDOW"), 0], 0)
            else:
                self._x.XDestroyWindow(self._display, handle)
            self._fallback_iconified.discard(handle)
            self._fallback_saved.pop(handle, None)
            self._checked()
            self._settle(lambda: self._attributes(handle) is None)

    def window_capture(self, handle: WindowHandle) -> Pixels:
        raise unsupported(self.name, "capturing a covered window", "use Window.screenshot() on a visible window")
