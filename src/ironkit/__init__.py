from __future__ import annotations

from . import _dialogs as dialogs
from . import _ease as ease
from ._config import Config, config
from ._errors import (
    BackendError,
    FailSafeError,
    ImageNotFoundError,
    InvalidKeyError,
    IronkitError,
    PermissionDeniedError,
    UnsupportedFeatureError,
    UnsupportedPlatformError,
    WindowNotFoundError,
)
from ._image import Image, Match
from ._input import Keyboard, Mouse, keyboard, mouse, position
from ._screen import Screen, desktop, screen, screens
from ._script import ScriptError, run
from ._tools import capabilities, countdown, info, inspect, inspector, print_info, sleep, version
from ._types import KEY_ALIASES, Button, Color, Key, Layout, Monitor, Point, Region, Size
from ._window import Window, Windows, windows
from .backends import Capabilities, WindowState, get_backend, set_backend

__version__ = version()

move_to = mouse.move_to
move_by = mouse.move_by
drag_to = mouse.drag_to
drag_by = mouse.drag_by
click = mouse.click
left_click = mouse.left_click
right_click = mouse.right_click
middle_click = mouse.middle_click
double_click = mouse.double_click
triple_click = mouse.triple_click
mouse_down = mouse.down
mouse_up = mouse.up
scroll = mouse.scroll
hscroll = mouse.hscroll

write = keyboard.write
press = keyboard.press
key_down = keyboard.down
key_up = keyboard.up
hold = keyboard.hold
hotkey = keyboard.hotkey

screenshot = screen.screenshot
pixel = screen.pixel
pixel_matches = screen.pixel_matches
find = screen.find
find_all = screen.find_all
find_or_none = screen.find_or_none
exists = screen.exists
wait_gone = screen.wait_gone

alert = dialogs.alert
confirm = dialogs.confirm
prompt = dialogs.prompt
password = dialogs.password

__all__ = [
    "KEY_ALIASES",
    "BackendError",
    "Button",
    "Capabilities",
    "Color",
    "Config",
    "FailSafeError",
    "Image",
    "ImageNotFoundError",
    "InvalidKeyError",
    "IronkitError",
    "Key",
    "Keyboard",
    "Layout",
    "Match",
    "Monitor",
    "Mouse",
    "PermissionDeniedError",
    "Point",
    "Region",
    "Screen",
    "ScriptError",
    "Size",
    "UnsupportedFeatureError",
    "UnsupportedPlatformError",
    "Window",
    "WindowNotFoundError",
    "WindowState",
    "Windows",
    "alert",
    "capabilities",
    "click",
    "config",
    "confirm",
    "countdown",
    "desktop",
    "dialogs",
    "double_click",
    "drag_by",
    "drag_to",
    "ease",
    "exists",
    "find",
    "find_all",
    "find_or_none",
    "get_backend",
    "hold",
    "hotkey",
    "hscroll",
    "info",
    "inspect",
    "inspector",
    "key_down",
    "key_up",
    "keyboard",
    "left_click",
    "middle_click",
    "mouse",
    "mouse_down",
    "mouse_up",
    "move_by",
    "move_to",
    "password",
    "pixel",
    "pixel_matches",
    "position",
    "press",
    "print_info",
    "prompt",
    "right_click",
    "run",
    "screen",
    "screens",
    "screenshot",
    "scroll",
    "set_backend",
    "sleep",
    "triple_click",
    "version",
    "wait_gone",
    "windows",
    "write",
]
