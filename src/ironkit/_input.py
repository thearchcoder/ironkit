from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from ._config import config
from ._ease import Ease, linear
from ._types import CHAR_KEYS, Button, KeyLike, Layout, Point, is_valid_key, key_name, needs_shift
from .backends import Backend, get_backend

_state = threading.local()
_logged: list[Path] = []


def _log_screenshot(name: str) -> None:
    from ._screen import screen

    directory = config.log_screenshots_dir
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
    path = directory / f"{stamp}_{name}.png"
    screen.screenshot(path=path)
    _logged.append(path)
    limit = config.log_screenshots_limit
    while limit is not None and len(_logged) > limit:
        oldest = _logged.pop(0)
        oldest.unlink(missing_ok=True)


@contextmanager
def action(name: str) -> Iterator[Backend]:
    depth: int = getattr(_state, "depth", 0)
    backend = get_backend()
    if depth == 0:
        config.check_failsafe()
        if config.log_screenshots:
            _log_screenshot(name)
    _state.depth = depth + 1
    try:
        yield backend
    finally:
        _state.depth = depth
    if depth == 0 and config.pause > 0:
        time.sleep(config.pause)


def resolve_point(x: Any = None, y: int | float | None = None) -> Point | None:
    if x is None and y is None:
        return None
    if isinstance(x, (int, float)) or (x is None and isinstance(y, (int, float))):
        current = get_backend().mouse_position() if x is None or y is None else Point(0, 0)
        return Point(
            round(x) if x is not None else current.x,
            round(y) if y is not None else current.y,
        )
    if y is not None:
        raise TypeError("y must be omitted when x is a point, region, match, window or image")
    if isinstance(x, Point):
        return x
    if isinstance(x, (str, os.PathLike)):
        from ._screen import screen

        return screen.find(x).center
    center = getattr(x, "center", None)
    if center is not None:
        return Point.of(center)
    if isinstance(x, (tuple, list)) and len(x) == 2:
        return Point.of((x[0], x[1]))
    raise TypeError(f"cannot use {type(x).__name__} as a screen position")


def _catch_up(backend: Backend) -> None:
    if backend.name == "macos" and config.darwin_catch_up_time > 0:
        time.sleep(config.darwin_catch_up_time)


class Mouse:
    @property
    def position(self) -> Point:
        return get_backend().mouse_position()

    def _physical(self, button: Button | str) -> Button:
        b = Button.of(button)
        if b in (Button.LEFT, Button.MIDDLE, Button.RIGHT):
            return b
        swapped = get_backend().buttons_swapped()
        if b is Button.PRIMARY:
            return Button.RIGHT if swapped else Button.LEFT
        return Button.LEFT if swapped else Button.RIGHT

    def _glide(self, backend: Backend, target: Point, duration: float, ease: Ease) -> None:
        if duration < config.minimum_duration or not backend.capabilities.read_cursor:
            backend.mouse_move(target.x, target.y)
            _catch_up(backend)
            return
        start = backend.mouse_position()
        began = time.monotonic()
        last = start
        while True:
            elapsed = time.monotonic() - began
            if elapsed >= duration:
                break
            step = start.lerp(target, ease(elapsed / duration))
            if step != last:
                if config.failsafe:
                    current = backend.mouse_position()
                    if current != last and config.is_failsafe_point(current):
                        config.check_failsafe()
                backend.mouse_move(step.x, step.y)
                _catch_up(backend)
                last = step
            time.sleep(config.minimum_sleep)
        backend.mouse_move(target.x, target.y)
        _catch_up(backend)

    def _glide_relative(self, backend: Backend, dx: int, dy: int, duration: float, ease: Ease) -> None:
        if duration < config.minimum_duration:
            backend.mouse_move_relative(dx, dy)
            return
        began = time.monotonic()
        done = Point(0, 0)
        goal = Point(dx, dy)
        while True:
            elapsed = time.monotonic() - began
            if elapsed >= duration:
                break
            want = Point(0, 0).lerp(goal, ease(elapsed / duration))
            delta = want - done
            if delta != Point(0, 0):
                backend.mouse_move_relative(delta.x, delta.y)
                done = want
            time.sleep(config.minimum_sleep)
        rest = goal - done
        if rest != Point(0, 0):
            backend.mouse_move_relative(rest.x, rest.y)

    def move_to(
        self,
        x: Any = None,
        y: int | float | None = None,
        *,
        duration: float = 0.0,
        ease: Ease = linear,
    ) -> Point:
        with action("move_to") as backend:
            target = resolve_point(x, y)
            if target is not None:
                self._glide(backend, target, duration, ease)
            return backend.mouse_position() if backend.capabilities.read_cursor else target or Point(0, 0)

    def move_by(
        self,
        dx: int = 0,
        dy: int = 0,
        *,
        duration: float = 0.0,
        ease: Ease = linear,
        raw: bool = False,
    ) -> None:
        with action("move_by") as backend:
            if raw:
                self._glide_relative(backend, int(dx), int(dy), duration, ease)
            else:
                target = backend.mouse_position().offset(int(dx), int(dy))
                self._glide(backend, target, duration, ease)

    def drag_to(
        self,
        x: Any = None,
        y: int | float | None = None,
        *,
        button: Button | str = Button.LEFT,
        duration: float = 0.0,
        ease: Ease = linear,
    ) -> None:
        with action("drag_to") as backend:
            target = resolve_point(x, y)
            physical = self._physical(button)
            backend.mouse_button(physical, True)
            try:
                if target is not None:
                    self._glide(backend, target, duration, ease)
            finally:
                backend.mouse_button(physical, False)

    def drag_by(
        self,
        dx: int = 0,
        dy: int = 0,
        *,
        button: Button | str = Button.LEFT,
        duration: float = 0.0,
        ease: Ease = linear,
    ) -> None:
        with action("drag_by") as backend:
            target = backend.mouse_position().offset(int(dx), int(dy))
            self.drag_to(target, button=button, duration=duration, ease=ease)

    def click(
        self,
        x: Any = None,
        y: int | float | None = None,
        *,
        clicks: int = 1,
        interval: float = 0.0,
        button: Button | str = Button.LEFT,
        duration: float = 0.0,
        ease: Ease = linear,
    ) -> None:
        with action("click") as backend:
            target = resolve_point(x, y)
            if target is not None:
                self._glide(backend, target, duration, ease)
            physical = self._physical(button)
            for i in range(clicks):
                backend.mouse_button(physical, True, i + 1)
                backend.mouse_button(physical, False, i + 1)
                if interval > 0 and i < clicks - 1:
                    time.sleep(interval)

    def left_click(self, x: Any = None, y: int | float | None = None, *, duration: float = 0.0) -> None:
        self.click(x, y, button=Button.LEFT, duration=duration)

    def right_click(self, x: Any = None, y: int | float | None = None, *, duration: float = 0.0) -> None:
        self.click(x, y, button=Button.RIGHT, duration=duration)

    def middle_click(self, x: Any = None, y: int | float | None = None, *, duration: float = 0.0) -> None:
        self.click(x, y, button=Button.MIDDLE, duration=duration)

    def double_click(
        self,
        x: Any = None,
        y: int | float | None = None,
        *,
        button: Button | str = Button.LEFT,
        interval: float = 0.0,
        duration: float = 0.0,
    ) -> None:
        self.click(x, y, clicks=2, interval=interval, button=button, duration=duration)

    def triple_click(
        self,
        x: Any = None,
        y: int | float | None = None,
        *,
        button: Button | str = Button.LEFT,
        interval: float = 0.0,
        duration: float = 0.0,
    ) -> None:
        self.click(x, y, clicks=3, interval=interval, button=button, duration=duration)

    def down(self, x: Any = None, y: int | float | None = None, *, button: Button | str = Button.LEFT) -> None:
        with action("mouse_down") as backend:
            target = resolve_point(x, y)
            if target is not None:
                self._glide(backend, target, 0.0, linear)
            backend.mouse_button(self._physical(button), True)

    def up(self, x: Any = None, y: int | float | None = None, *, button: Button | str = Button.LEFT) -> None:
        with action("mouse_up") as backend:
            target = resolve_point(x, y)
            if target is not None:
                self._glide(backend, target, 0.0, linear)
            backend.mouse_button(self._physical(button), False)

    @contextmanager
    def hold(self, button: Button | str = Button.LEFT) -> Iterator[Mouse]:
        self.down(button=button)
        try:
            yield self
        finally:
            self.up(button=button)

    def scroll(self, amount: int, x: Any = None, y: int | float | None = None) -> None:
        with action("scroll") as backend:
            target = resolve_point(x, y)
            if target is not None:
                self._glide(backend, target, 0.0, linear)
            backend.mouse_scroll(0, int(amount))

    def hscroll(self, amount: int, x: Any = None, y: int | float | None = None) -> None:
        with action("hscroll") as backend:
            target = resolve_point(x, y)
            if target is not None:
                self._glide(backend, target, 0.0, linear)
            backend.mouse_scroll(int(amount), 0)


def _flatten(keys: Iterable[KeyLike | Iterable[KeyLike]]) -> list[str]:
    names: list[str] = []
    for key in keys:
        if isinstance(key, str):
            names.append(key_name(key))
        else:
            names.extend(key_name(k) for k in key)
    return names


class Keyboard:
    def write(self, text: str | Iterable[KeyLike], interval: float = 0.0) -> None:
        with action("write") as backend:
            items: list[str] = list(text) if isinstance(text, str) else _flatten([text])
            typing = isinstance(text, str)
            for i, item in enumerate(items):
                if typing and item not in CHAR_KEYS:
                    backend.type_char(item)
                else:
                    name = key_name(item)
                    backend.key(name, True)
                    backend.key(name, False)
                if interval > 0 and i < len(items) - 1:
                    time.sleep(interval)

    def press(self, *keys: KeyLike | Iterable[KeyLike], times: int = 1, interval: float = 0.0) -> None:
        names = _flatten(keys)
        with action("press") as backend:
            for n in range(times):
                for i, name in enumerate(names):
                    backend.key(name, True)
                    backend.key(name, False)
                    last = n == times - 1 and i == len(names) - 1
                    if interval > 0 and not last:
                        time.sleep(interval)

    def down(self, key: KeyLike) -> None:
        name = key_name(key)
        with action("key_down") as backend:
            backend.key(name, True)

    def up(self, key: KeyLike) -> None:
        name = key_name(key)
        with action("key_up") as backend:
            backend.key(name, False)

    @contextmanager
    def hold(self, *keys: KeyLike | Iterable[KeyLike]) -> Iterator[Keyboard]:
        names = _flatten(keys)
        backend = get_backend()
        pressed: list[str] = []
        try:
            with action("hold"):
                for name in names:
                    backend.key(name, True)
                    pressed.append(name)
            yield self
        finally:
            for name in reversed(pressed):
                backend.key(name, False)

    def hotkey(self, *keys: KeyLike | Iterable[KeyLike], interval: float = 0.0) -> None:
        names = _flatten(keys)
        with action("hotkey") as backend:
            pressed: list[str] = []
            try:
                for name in names:
                    backend.key(name, True)
                    pressed.append(name)
                    if interval > 0:
                        time.sleep(interval)
            finally:
                for i, name in enumerate(reversed(pressed)):
                    backend.key(name, False)
                    if interval > 0 and i < len(pressed) - 1:
                        time.sleep(interval)

    @staticmethod
    def is_valid(key: object) -> bool:
        return is_valid_key(key)

    @staticmethod
    def needs_shift(char: str, layout: Layout = Layout.QWERTY) -> bool:
        return needs_shift(char, layout)


mouse = Mouse()
keyboard = Keyboard()


def position() -> Point:
    return mouse.position
