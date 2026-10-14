from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from ._errors import InvalidKeyError


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int

    def __iter__(self) -> Iterator[int]:
        yield self.x
        yield self.y

    def __add__(self, other: PointLike) -> Point:
        o = Point.of(other)
        return Point(self.x + o.x, self.y + o.y)

    def __sub__(self, other: PointLike) -> Point:
        o = Point.of(other)
        return Point(self.x - o.x, self.y - o.y)

    @staticmethod
    def of(value: PointLike) -> Point:
        if isinstance(value, Point):
            return value
        x, y = value
        return Point(round(x), round(y))

    def offset(self, dx: int = 0, dy: int = 0) -> Point:
        return Point(self.x + dx, self.y + dy)

    def distance_to(self, other: PointLike) -> float:
        o = Point.of(other)
        return math.hypot(o.x - self.x, o.y - self.y)

    def lerp(self, other: PointLike, t: float) -> Point:
        o = Point.of(other)
        return Point(round(self.x + (o.x - self.x) * t), round(self.y + (o.y - self.y) * t))


PointLike = Point | tuple[int, int] | tuple[float, float]


@dataclass(frozen=True, slots=True)
class Size:
    width: int
    height: int

    def __iter__(self) -> Iterator[int]:
        yield self.width
        yield self.height


@dataclass(frozen=True, slots=True)
class Region:
    left: int
    top: int
    width: int
    height: int

    def __iter__(self) -> Iterator[int]:
        yield self.left
        yield self.top
        yield self.width
        yield self.height

    @staticmethod
    def of(value: RegionLike) -> Region:
        if isinstance(value, Region):
            return value
        left, top, width, height = value
        return Region(int(left), int(top), int(width), int(height))

    @staticmethod
    def from_corners(a: PointLike, b: PointLike) -> Region:
        p, q = Point.of(a), Point.of(b)
        left, top = min(p.x, q.x), min(p.y, q.y)
        return Region(left, top, abs(q.x - p.x), abs(q.y - p.y))

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return Point(self.left + self.width // 2, self.top + self.height // 2)

    @property
    def topleft(self) -> Point:
        return Point(self.left, self.top)

    @property
    def topright(self) -> Point:
        return Point(self.right, self.top)

    @property
    def bottomleft(self) -> Point:
        return Point(self.left, self.bottom)

    @property
    def bottomright(self) -> Point:
        return Point(self.right, self.bottom)

    def contains(self, point: PointLike) -> bool:
        p = Point.of(point)
        return self.left <= p.x < self.right and self.top <= p.y < self.bottom

    def __contains__(self, point: PointLike) -> bool:
        return self.contains(point)

    def intersect(self, other: RegionLike) -> Region | None:
        o = Region.of(other)
        left, top = max(self.left, o.left), max(self.top, o.top)
        right, bottom = min(self.right, o.right), min(self.bottom, o.bottom)
        if right <= left or bottom <= top:
            return None
        return Region(left, top, right - left, bottom - top)

    def union(self, other: RegionLike) -> Region:
        o = Region.of(other)
        left, top = min(self.left, o.left), min(self.top, o.top)
        right, bottom = max(self.right, o.right), max(self.bottom, o.bottom)
        return Region(left, top, right - left, bottom - top)

    def offset(self, dx: int = 0, dy: int = 0) -> Region:
        return Region(self.left + dx, self.top + dy, self.width, self.height)

    def inset(self, amount: int) -> Region:
        return Region(
            self.left + amount,
            self.top + amount,
            max(0, self.width - 2 * amount),
            max(0, self.height - 2 * amount),
        )

    def point(self, x: int, y: int) -> Point:
        return Point(self.left + x, self.top + y)


RegionLike = Region | tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class Color:
    r: int
    g: int
    b: int

    def __iter__(self) -> Iterator[int]:
        yield self.r
        yield self.g
        yield self.b

    @staticmethod
    def of(value: ColorLike) -> Color:
        if isinstance(value, Color):
            return value
        if isinstance(value, str):
            return Color.from_hex(value)
        r, g, b = tuple(value)[:3]
        return Color(int(r), int(g), int(b))

    @staticmethod
    def from_hex(value: str) -> Color:
        text = value.strip().lstrip("#")
        if len(text) == 3:
            text = "".join(c * 2 for c in text)
        if len(text) != 6:
            raise ValueError(f"invalid hex color: {value!r}")
        return Color(int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))

    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def matches(self, other: ColorLike, tolerance: int = 0) -> bool:
        o = Color.of(other)
        return abs(self.r - o.r) <= tolerance and abs(self.g - o.g) <= tolerance and abs(self.b - o.b) <= tolerance


ColorLike = Color | str | tuple[int, int, int] | tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class Monitor:
    region: Region
    scale: float = 1.0
    primary: bool = False
    name: str = ""


class Button(str, Enum):
    LEFT = "left"
    MIDDLE = "middle"
    RIGHT = "right"
    PRIMARY = "primary"
    SECONDARY = "secondary"

    @staticmethod
    def of(value: Button | str) -> Button:
        if isinstance(value, Button):
            return value
        try:
            return Button(value.lower())
        except ValueError:
            raise ValueError(f"invalid mouse button: {value!r}") from None


class Key(str, Enum):
    BACKSPACE = "backspace"
    TAB = "tab"
    ENTER = "enter"
    SPACE = "space"
    ESCAPE = "escape"
    DELETE = "delete"
    INSERT = "insert"
    HOME = "home"
    END = "end"
    PAGEUP = "pageup"
    PAGEDOWN = "pagedown"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    SHIFT = "shift"
    SHIFTLEFT = "shiftleft"
    SHIFTRIGHT = "shiftright"
    CTRL = "ctrl"
    CTRLLEFT = "ctrlleft"
    CTRLRIGHT = "ctrlright"
    ALT = "alt"
    ALTLEFT = "altleft"
    ALTRIGHT = "altright"
    WIN = "win"
    WINRIGHT = "winright"
    COMMAND = "command"
    OPTION = "option"
    OPTIONLEFT = "optionleft"
    OPTIONRIGHT = "optionright"
    FN = "fn"
    CAPSLOCK = "capslock"
    NUMLOCK = "numlock"
    SCROLLLOCK = "scrolllock"
    PRINTSCREEN = "printscreen"
    PAUSE = "pause"
    APPS = "apps"
    HELP = "help"
    SELECT = "select"
    EXECUTE = "execute"
    CLEAR = "clear"
    SLEEP = "sleep"
    NUM0 = "num0"
    NUM1 = "num1"
    NUM2 = "num2"
    NUM3 = "num3"
    NUM4 = "num4"
    NUM5 = "num5"
    NUM6 = "num6"
    NUM7 = "num7"
    NUM8 = "num8"
    NUM9 = "num9"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    DECIMAL = "decimal"
    SEPARATOR = "separator"
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"
    F13 = "f13"
    F14 = "f14"
    F15 = "f15"
    F16 = "f16"
    F17 = "f17"
    F18 = "f18"
    F19 = "f19"
    F20 = "f20"
    F21 = "f21"
    F22 = "f22"
    F23 = "f23"
    F24 = "f24"
    VOLUMEUP = "volumeup"
    VOLUMEDOWN = "volumedown"
    VOLUMEMUTE = "volumemute"
    PLAYPAUSE = "playpause"
    NEXTTRACK = "nexttrack"
    PREVTRACK = "prevtrack"
    STOP = "stop"
    BROWSERBACK = "browserback"
    BROWSERFORWARD = "browserforward"
    BROWSERREFRESH = "browserrefresh"
    BROWSERSTOP = "browserstop"
    BROWSERSEARCH = "browsersearch"
    BROWSERFAVORITES = "browserfavorites"
    BROWSERHOME = "browserhome"
    LAUNCHMAIL = "launchmail"
    LAUNCHMEDIASELECT = "launchmediaselect"
    LAUNCHAPP1 = "launchapp1"
    LAUNCHAPP2 = "launchapp2"
    ACCEPT = "accept"
    CONVERT = "convert"
    NONCONVERT = "nonconvert"
    MODECHANGE = "modechange"
    FINAL = "final"
    HANGUL = "hangul"
    HANJA = "hanja"
    JUNJA = "junja"
    KANA = "kana"
    KANJI = "kanji"
    YEN = "yen"


KeyLike = Key | str

KEY_ALIASES: dict[str, str] = {
    "return": "enter",
    "esc": "escape",
    "del": "delete",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "winleft": "win",
    "super": "win",
    "cmd": "command",
    "control": "ctrl",
    "print": "printscreen",
    "prtsc": "printscreen",
    "prtscr": "printscreen",
    "prntscrn": "printscreen",
    "hanguel": "hangul",
    "menu": "apps",
}

CHAR_KEYS: dict[str, str] = {
    "\n": "enter",
    "\r": "enter",
    "\t": "tab",
    "\b": "backspace",
    "\x1b": "escape",
    " ": "space",
}

_KEY_VALUES = frozenset(k.value for k in Key)


def key_name(key: KeyLike) -> str:
    if isinstance(key, Key):
        return key.value
    if not isinstance(key, str) or not key:
        raise InvalidKeyError(f"invalid key: {key!r}")
    if len(key) == 1:
        return CHAR_KEYS.get(key, key)
    name = key.lower()
    name = KEY_ALIASES.get(name, name)
    if name not in _KEY_VALUES:
        raise InvalidKeyError(f"invalid key: {key!r}")
    return name


def is_valid_key(key: object) -> bool:
    if not isinstance(key, (str, Key)):
        return False
    try:
        key_name(key)
    except InvalidKeyError:
        return False
    return True


class Layout(str, Enum):
    QWERTY = "`1234567890-=qwertyuiop[]\\asdfghjkl;'zxcvbnm,./~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:\"ZXCVBNM<>?"
    QWERTZ = "=1234567890/0qwertzuiop89-asdfghjkl,\\yxcvbnm,.7+!@#$%^&*()?)QWERTZUIOP*(_ASDFGHJKL<|YXCVBNM<>&"


def needs_shift(char: str, layout: Layout = Layout.QWERTY) -> bool:
    if len(char) != 1:
        return False
    chars = layout.value
    half = len(chars) // 2
    index = chars.find(char)
    if index == -1:
        return char.isupper()
    return index >= half and char not in chars[:half]
