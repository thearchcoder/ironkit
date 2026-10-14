from __future__ import annotations

import os
import re
import time

from ._config import config
from ._errors import WindowNotFoundError
from ._image import Image, ImageLike, Match, pick
from ._screen import Capture, capture, find_one, search, wait_gone
from ._types import Color, Point, PointLike, Region, Size
from .backends import WindowHandle, WindowInfo, WindowState, get_backend

TitleQuery = str | re.Pattern[str]


class Window:
    __slots__ = ("handle",)

    def __init__(self, handle: WindowHandle) -> None:
        self.handle = handle

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Window) and other.handle == self.handle

    def __hash__(self) -> int:
        return hash(self.handle)

    def __repr__(self) -> str:
        try:
            return f"Window({self.handle}, {self.title!r})"
        except WindowNotFoundError:
            return f"Window({self.handle}, closed)"

    def info(self) -> WindowInfo:
        return get_backend().window_info(self.handle)

    @property
    def title(self) -> str:
        return self.info().title

    @property
    def region(self) -> Region:
        return self.info().region

    @property
    def left(self) -> int:
        return self.region.left

    @property
    def top(self) -> int:
        return self.region.top

    @property
    def width(self) -> int:
        return self.region.width

    @property
    def height(self) -> int:
        return self.region.height

    @property
    def size(self) -> Size:
        return self.region.size

    @property
    def topleft(self) -> Point:
        return self.region.topleft

    @property
    def center(self) -> Point:
        return self.region.center

    @property
    def pid(self) -> int:
        return self.info().pid

    @property
    def is_active(self) -> bool:
        return self.info().is_active

    @property
    def is_minimized(self) -> bool:
        return self.info().is_minimized

    @property
    def is_maximized(self) -> bool:
        return self.info().is_maximized

    @property
    def is_visible(self) -> bool:
        return self.info().is_visible

    @property
    def is_open(self) -> bool:
        return self.handle in get_backend().list_windows()

    def activate(self) -> Window:
        get_backend().window_activate(self.handle)
        return self

    def minimize(self) -> Window:
        get_backend().window_set_state(self.handle, WindowState.MINIMIZED)
        return self

    def maximize(self) -> Window:
        get_backend().window_set_state(self.handle, WindowState.MAXIMIZED)
        return self

    def restore(self) -> Window:
        get_backend().window_set_state(self.handle, WindowState.NORMAL)
        return self

    def show(self) -> Window:
        get_backend().window_set_state(self.handle, WindowState.SHOWN)
        return self

    def hide(self) -> Window:
        get_backend().window_set_state(self.handle, WindowState.HIDDEN)
        return self

    def close(self) -> None:
        get_backend().window_close(self.handle)

    def move_to(self, x: int, y: int) -> Window:
        r = self.region
        get_backend().window_set_geometry(self.handle, Region(x, y, r.width, r.height))
        return self

    def move_by(self, dx: int, dy: int) -> Window:
        get_backend().window_set_geometry(self.handle, self.region.offset(dx, dy))
        return self

    def resize_to(self, width: int, height: int) -> Window:
        r = self.region
        get_backend().window_set_geometry(self.handle, Region(r.left, r.top, width, height))
        return self

    def resize_by(self, dw: int, dh: int) -> Window:
        r = self.region
        get_backend().window_set_geometry(self.handle, Region(r.left, r.top, r.width + dw, r.height + dh))
        return self

    def set_region(self, region: Region) -> Window:
        get_backend().window_set_geometry(self.handle, region)
        return self

    def point(self, x: int, y: int) -> Point:
        return self.region.point(x, y)

    def screenshot(self, path: str | os.PathLike[str] | None = None) -> Image:
        backend = get_backend()
        if backend.capabilities.window_capture:
            image = Image(backend.window_capture(self.handle), self.region.topleft)
        else:
            image = capture(self.region)
        if path is not None:
            image.save(path)
        return image

    def pixel(self, x: int, y: int) -> Color:
        return self.screenshot().pixel(self.point(x, y))

    def _capture(self) -> Capture:
        return self.screenshot

    def find(
        self,
        image: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        near: PointLike | None = None,
        timeout: float = 0.0,
        interval: float | None = None,
    ) -> Match:
        return find_one(
            self._capture(),
            image,
            confidence=confidence,
            grayscale=grayscale,
            near=near,
            timeout=timeout,
            interval=interval,
        )

    def find_all(
        self,
        image: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        limit: int | None = None,
        timeout: float = 0.0,
        interval: float | None = None,
    ) -> list[Match]:
        matches, _ = search(
            self._capture(),
            image,
            confidence=confidence,
            grayscale=grayscale,
            near=None,
            timeout=timeout,
            interval=interval,
            limit=limit,
        )
        return matches

    def find_or_none(
        self,
        image: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        near: PointLike | None = None,
        timeout: float = 0.0,
        interval: float | None = None,
    ) -> Match | None:
        matches, _ = search(
            self._capture(),
            image,
            confidence=confidence,
            grayscale=grayscale,
            near=near,
            timeout=timeout,
            interval=interval,
            limit=1,
        )
        return pick(matches, near) if matches else None

    def exists(
        self,
        image: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        timeout: float = 0.0,
    ) -> bool:
        return self.find_or_none(image, confidence=confidence, grayscale=grayscale, timeout=timeout) is not None

    def wait_gone(
        self,
        image: ImageLike,
        *,
        timeout: float = 10.0,
        confidence: float | None = None,
        grayscale: bool = False,
        interval: float | None = None,
    ) -> bool:
        return wait_gone(
            self._capture(),
            image,
            confidence=confidence,
            grayscale=grayscale,
            timeout=timeout,
            interval=interval,
        )


def _matches(title: str, query: TitleQuery, exact: bool) -> bool:
    if isinstance(query, re.Pattern):
        return query.search(title) is not None
    if exact:
        return title == query
    return query.casefold() in title.casefold()


class Windows:
    def all(self) -> list[Window]:
        return [Window(h) for h in get_backend().list_windows()]

    def titles(self) -> list[str]:
        backend = get_backend()
        titles: list[str] = []
        for handle in backend.list_windows():
            try:
                titles.append(backend.window_info(handle).title)
            except WindowNotFoundError:
                continue
        return titles

    def active(self) -> Window | None:
        handle = get_backend().active_window()
        return None if handle is None else Window(handle)

    def active_title(self) -> str:
        window = self.active()
        return "" if window is None else window.title

    def at(self, x: int | PointLike, y: int | None = None) -> list[Window]:
        point = Point.of(x) if y is None else Point(int(x), y)
        backend = get_backend()
        found: list[Window] = []
        for handle in backend.list_windows():
            try:
                info = backend.window_info(handle)
            except WindowNotFoundError:
                continue
            if info.is_visible and not info.is_minimized and info.region.contains(point):
                found.append(Window(handle))
        return found

    def find(self, title: TitleQuery = "", *, exact: bool = False, pid: int | None = None) -> list[Window]:
        backend = get_backend()
        found: list[Window] = []
        for handle in backend.list_windows():
            try:
                info = backend.window_info(handle)
            except WindowNotFoundError:
                continue
            if pid is not None and info.pid != pid:
                continue
            if _matches(info.title, title, exact):
                found.append(Window(handle))
        return found

    def get(
        self,
        title: TitleQuery = "",
        *,
        exact: bool = False,
        pid: int | None = None,
        timeout: float = 0.0,
        interval: float | None = None,
    ) -> Window:
        deadline = time.monotonic() + max(0.0, timeout)
        pause = config.find_interval if interval is None else interval
        while True:
            found = self.find(title, exact=exact, pid=pid)
            if found:
                return found[0]
            if time.monotonic() >= deadline:
                query = title.pattern if isinstance(title, re.Pattern) else title
                raise WindowNotFoundError(f"no window with title matching {query!r}")
            time.sleep(max(0.0, min(pause, deadline - time.monotonic())))


windows = Windows()
