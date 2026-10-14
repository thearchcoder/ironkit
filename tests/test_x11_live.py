from __future__ import annotations

import ctypes
import os
import sys
import time
from collections.abc import Iterator
from ctypes import POINTER, Structure, byref, c_char_p, c_int, c_long, c_uint, c_ulong, c_void_p

import numpy as np
import pytest

import ironkit as ik

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"), reason="needs X11"),
]

KEY_PRESS, KEY_RELEASE, BUTTON_PRESS = 2, 3, 4
EVENT_MASK = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3)


class XKeyEvent(Structure):
    _fields_ = [
        ("type", c_int),
        ("serial", c_ulong),
        ("send_event", c_int),
        ("display", c_void_p),
        ("window", c_ulong),
        ("root", c_ulong),
        ("subwindow", c_ulong),
        ("time", c_ulong),
        ("x", c_int),
        ("y", c_int),
        ("x_root", c_int),
        ("y_root", c_int),
        ("state", c_uint),
        ("detail", c_uint),
        ("same_screen", c_int),
    ]


class XEvent(ctypes.Union):
    _fields_ = [("type", c_int), ("xkey", XKeyEvent), ("pad", c_long * 24)]


class Client:
    def __init__(self) -> None:
        self.x = ctypes.CDLL("libX11.so.6")
        self.x.XOpenDisplay.restype = c_void_p
        self.x.XOpenDisplay.argtypes = [c_char_p]
        self.x.XDefaultRootWindow.restype = c_ulong
        self.x.XDefaultRootWindow.argtypes = [c_void_p]
        self.x.XCreateSimpleWindow.restype = c_ulong
        self.x.XCreateSimpleWindow.argtypes = [
            c_void_p,
            c_ulong,
            c_int,
            c_int,
            c_uint,
            c_uint,
            c_uint,
            c_ulong,
            c_ulong,
        ]
        for name in ("XStoreName",):
            getattr(self.x, name).argtypes = [c_void_p, c_ulong, c_char_p]
        for name in ("XMapWindow", "XDestroyWindow", "XRaiseWindow"):
            getattr(self.x, name).argtypes = [c_void_p, c_ulong]
        self.x.XSelectInput.argtypes = [c_void_p, c_ulong, c_long]
        self.x.XSync.argtypes = [c_void_p, c_int]
        self.x.XPending.argtypes = [c_void_p]
        self.x.XNextEvent.argtypes = [c_void_p, POINTER(XEvent)]
        self.x.XLookupString.argtypes = [POINTER(XKeyEvent), c_char_p, c_int, POINTER(c_ulong), c_void_p]
        self.x.XSetInputFocus.argtypes = [c_void_p, c_ulong, c_int, c_ulong]
        self.x.XCloseDisplay.argtypes = [c_void_p]
        self.display = self.x.XOpenDisplay(None)
        self.root = self.x.XDefaultRootWindow(self.display)
        self.windows: list[int] = []

    def window(self, title: str, x: int, y: int, w: int, h: int, color: int) -> int:
        handle = self.x.XCreateSimpleWindow(self.display, self.root, x, y, w, h, 0, 0, color)
        self.x.XStoreName(self.display, handle, title.encode())
        self.x.XSelectInput(self.display, handle, EVENT_MASK)
        self.x.XMapWindow(self.display, handle)
        self.x.XSync(self.display, 0)
        self.windows.append(handle)
        time.sleep(0.05)
        return handle

    def focus(self, handle: int) -> None:
        self.x.XRaiseWindow(self.display, handle)
        self.x.XSetInputFocus(self.display, handle, 2, 0)
        self.x.XSync(self.display, 0)

    def events(self, settle: float = 0.15) -> list[tuple[int, str, int, int, int]]:
        time.sleep(settle)
        self.x.XSync(self.display, 0)
        found: list[tuple[int, str, int, int, int]] = []
        event = XEvent()
        while self.x.XPending(self.display):
            self.x.XNextEvent(self.display, byref(event))
            if event.type in (KEY_PRESS, KEY_RELEASE):
                buffer = ctypes.create_string_buffer(16)
                sym = c_ulong()
                count = self.x.XLookupString(byref(event.xkey), buffer, 16, byref(sym), None)
                text = buffer.raw[:count].decode("latin-1")
                found.append((event.type, text, int(sym.value), event.xkey.state, event.xkey.detail))
            elif event.type == BUTTON_PRESS:
                found.append((event.type, "", 0, event.xkey.state, event.xkey.detail))
        return found

    def close(self) -> None:
        for handle in self.windows:
            self.x.XDestroyWindow(self.display, handle)
        self.x.XSync(self.display, 0)
        self.x.XCloseDisplay(self.display)


@pytest.fixture(scope="module")
def backend() -> Iterator[object]:
    from ironkit.backends.x11 import X11Backend

    instance = X11Backend()
    previous = ik.set_backend(instance)
    with ik.config.override(pause=0.0, failsafe=False):
        yield instance
    ik.set_backend(previous)
    instance.close()


@pytest.fixture
def client() -> Iterator[Client]:
    c = Client()
    yield c
    c.close()


def typed_text(events: list[tuple[int, str, int, int, int]]) -> str:
    return "".join(text for kind, text, _, _, _ in events if kind == KEY_PRESS)


def test_monitor_and_screen(backend: object) -> None:
    monitors = ik.get_backend().monitors()
    assert monitors
    assert any(m.primary for m in monitors)
    assert ik.screen.size.width > 0


def test_mouse_move_and_relative(backend: object) -> None:
    ik.move_to(200, 150)
    assert ik.position() == ik.Point(200, 150)
    ik.move_by(25, -10)
    assert ik.position() == ik.Point(225, 140)
    ik.move_by(5, 5, raw=True)
    assert ik.position() == ik.Point(230, 145)
    ik.move_to(400, 300, duration=0.2, ease=ik.ease.out_quad)
    assert ik.position() == ik.Point(400, 300)


def test_capture_window_colors_and_find(backend: object, client: Client) -> None:
    client.window("ironkit-red", 50, 60, 120, 80, 0xFF0000)
    client.window("ironkit-blue", 300, 60, 40, 30, 0x0000FF)
    time.sleep(0.2)
    red = ik.windows.get("ironkit-red").region
    blue = ik.windows.get("ironkit-blue").region
    assert red.size == ik.Size(120, 80)
    assert ik.pixel(red.center) == ik.Color(255, 0, 0)
    assert ik.pixel(blue.center) == ik.Color(0, 0, 255)
    shot = ik.screenshot(region=red)
    assert shot.pixel(red.topleft) == ik.Color(255, 0, 0)
    needle = np.zeros((30, 40, 3), np.uint8)
    needle[:, :] = (0, 0, 255)
    assert ik.find(needle).region == blue


def test_capture_outside_screen_is_black(backend: object) -> None:
    size = ik.screen.size
    part = ik.screenshot(region=(size.width - 5, 0, 10, 10))
    assert part.size == ik.Size(10, 10)
    assert part.pixel(size.width + 2, 5) == ik.Color(0, 0, 0)


def test_keyboard_typing(backend: object, client: Client) -> None:
    handle = client.window("ironkit-keys", 100, 100, 200, 100, 0x00FF00)
    client.focus(handle)
    client.events()
    ik.write("Hello, World! 123 ~_+")
    assert typed_text(client.events()) == "Hello, World! 123 ~_+"


def test_unicode_typing_uses_scratch_keycode(backend: object, client: Client) -> None:
    handle = client.window("ironkit-unicode", 100, 100, 200, 100, 0x00FF00)
    client.focus(handle)
    client.events()
    ik.write("é")
    events = client.events()
    syms = [sym for kind, _, sym, _, _ in events if kind == KEY_PRESS]
    assert 0xE9 in syms


def test_named_keys_and_hotkey(backend: object, client: Client) -> None:
    handle = client.window("ironkit-named", 100, 100, 200, 100, 0x00FF00)
    client.focus(handle)
    client.events()
    ik.press("enter", "tab", "f5", "left", "num7")
    ik.hotkey("ctrl", "a")
    events = [e for e in client.events() if e[0] == KEY_PRESS]
    syms = [sym for _, _, sym, _, _ in events]
    assert syms[:4] == [0xFF0D, 0xFF09, 0xFFC2, 0xFF51]
    assert syms[4] in (0xFFB7, 0xFF95)
    assert syms[5] == 0xFFE3
    assert events[6][2] == 0x61
    assert events[6][3] & 4


def test_mouse_buttons_and_scroll(backend: object, client: Client) -> None:
    handle = client.window("ironkit-mouse", 100, 100, 200, 200, 0x777777)
    client.focus(handle)
    time.sleep(0.1)
    client.events()
    ik.click(ik.windows.get("ironkit-mouse"))
    ik.right_click()
    ik.middle_click()
    ik.scroll(2)
    ik.scroll(-1)
    ik.hscroll(1)
    buttons = [detail for kind, _, _, _, detail in client.events() if kind == BUTTON_PRESS]
    assert buttons == [1, 3, 2, 4, 4, 5, 7]


def test_window_listing_and_control(backend: object, client: Client) -> None:
    client.window("ironkit-alpha", 10, 10, 100, 100, 0x112233)
    victim = Client()
    victim.window("ironkit-beta", 400, 300, 150, 120, 0x445566)
    titles = ik.windows.titles()
    assert "ironkit-alpha" in titles
    assert "ironkit-beta" in titles
    beta = ik.windows.get("ironkit-beta")
    assert beta.size == ik.Size(150, 120)
    assert beta.is_visible
    assert beta in ik.windows.at(beta.center)
    beta.activate()
    assert ik.windows.active() == beta
    beta.move_to(420, 310).resize_to(160, 130)
    time.sleep(0.05)
    assert beta.region == ik.Region(420, 310, 160, 130)
    beta.minimize()
    assert beta.is_minimized
    beta.restore()
    time.sleep(0.05)
    assert not beta.is_minimized
    assert beta.is_visible
    beta.maximize()
    time.sleep(0.05)
    assert beta.is_maximized
    assert ik.screen.region.intersect(beta.region) == beta.region
    assert beta.width >= ik.screen.size.width * 0.9
    beta.restore()
    time.sleep(0.05)
    assert beta.size == ik.Size(160, 130)
    assert beta.topleft.distance_to((420, 310)) < 40
    beta.hide()
    time.sleep(0.05)
    assert not beta.is_visible
    beta.show()
    time.sleep(0.05)
    assert beta.is_visible
    beta.close()
    time.sleep(0.05)
    assert not beta.is_open
