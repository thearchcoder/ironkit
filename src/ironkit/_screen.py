from __future__ import annotations

import os
import time
from collections.abc import Callable

from ._config import config
from ._image import Image, ImageLike, Match, locate_all, not_found, pick
from ._types import Color, ColorLike, Monitor, Point, PointLike, Region, RegionLike, Size, point_from
from .backends import get_backend

Capture = Callable[[], Image]


def search(
    capture: Capture,
    needle: ImageLike,
    *,
    confidence: float | None,
    grayscale: bool,
    near: PointLike | None,
    timeout: float,
    interval: float | None,
    limit: int | None = None,
) -> tuple[list[Match], float]:
    target = Image.of(needle)
    deadline = time.monotonic() + max(0.0, timeout)
    pause = config.find_interval if interval is None else interval
    while True:
        matches, best = locate_all(
            capture(),
            target,
            confidence=confidence,
            grayscale=grayscale,
            limit=None if near is not None else limit,
        )
        if matches or time.monotonic() >= deadline:
            return matches, best
        time.sleep(max(0.0, min(pause, deadline - time.monotonic())))


def find_one(
    capture: Capture,
    needle: ImageLike,
    *,
    confidence: float | None,
    grayscale: bool,
    near: PointLike | None,
    timeout: float,
    interval: float | None,
) -> Match:
    matches, best = search(
        capture,
        needle,
        confidence=confidence,
        grayscale=grayscale,
        near=near,
        timeout=timeout,
        interval=interval,
        limit=1,
    )
    if not matches:
        raise not_found(needle, best, confidence)
    return pick(matches, near)


def wait_gone(
    capture: Capture,
    needle: ImageLike,
    *,
    confidence: float | None,
    grayscale: bool,
    timeout: float,
    interval: float | None,
) -> bool:
    target = Image.of(needle)
    deadline = time.monotonic() + max(0.0, timeout)
    pause = config.find_interval if interval is None else interval
    while True:
        matches, _ = locate_all(capture(), target, confidence=confidence, grayscale=grayscale, limit=1)
        if not matches:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(max(0.0, min(pause, deadline - time.monotonic())))


def capture(region: RegionLike) -> Image:
    r = Region.of(region)
    if r.width <= 0 or r.height <= 0:
        raise ValueError(f"cannot capture an empty region {tuple(r)}")
    return Image(get_backend().capture(r), r.topleft)


class Screen:
    def __init__(self, index: int | None = None) -> None:
        self._index = index

    def __repr__(self) -> str:
        label = "primary" if self._index is None else str(self._index)
        return f"Screen({label})"

    @property
    def monitor(self) -> Monitor:
        monitors = get_backend().monitors()
        if self._index is None:
            return next((m for m in monitors if m.primary), monitors[0])
        return monitors[self._index]

    @property
    def region(self) -> Region:
        return self.monitor.region

    @property
    def size(self) -> Size:
        return self.region.size

    @property
    def scale(self) -> float:
        return self.monitor.scale

    @property
    def center(self) -> Point:
        return self.region.center

    def contains(self, x: int | PointLike, y: int | None = None) -> bool:
        point = point_from(x, y)
        return self.region.contains(point)

    def screenshot(self, region: RegionLike | None = None, path: str | os.PathLike[str] | None = None) -> Image:
        image = capture(self.region if region is None else region)
        if path is not None:
            image.save(path)
        return image

    def pixel(self, x: int | PointLike, y: int | None = None) -> Color:
        point = point_from(x, y)
        return capture(Region(point.x, point.y, 1, 1)).pixel(point)

    def pixel_matches(
        self,
        x: int | PointLike,
        y: int | None = None,
        color: ColorLike = (0, 0, 0),
        tolerance: int = 0,
    ) -> bool:
        return self.pixel(x, y).matches(color, tolerance)

    def _capture_for(self, region: RegionLike | None) -> Capture:
        area = self.region if region is None else Region.of(region)
        return lambda: capture(area)

    def find(
        self,
        image: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        region: RegionLike | None = None,
        near: PointLike | None = None,
        timeout: float = 0.0,
        interval: float | None = None,
    ) -> Match:
        return find_one(
            self._capture_for(region),
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
        region: RegionLike | None = None,
        limit: int | None = None,
        timeout: float = 0.0,
        interval: float | None = None,
    ) -> list[Match]:
        matches, _ = search(
            self._capture_for(region),
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
        region: RegionLike | None = None,
        near: PointLike | None = None,
        timeout: float = 0.0,
        interval: float | None = None,
    ) -> Match | None:
        matches, _ = search(
            self._capture_for(region),
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
        region: RegionLike | None = None,
        timeout: float = 0.0,
        interval: float | None = None,
    ) -> bool:
        found = self.find_or_none(
            image,
            confidence=confidence,
            grayscale=grayscale,
            region=region,
            timeout=timeout,
            interval=interval,
        )
        return found is not None

    def wait_gone(
        self,
        image: ImageLike,
        *,
        timeout: float = 10.0,
        confidence: float | None = None,
        grayscale: bool = False,
        region: RegionLike | None = None,
        interval: float | None = None,
    ) -> bool:
        return wait_gone(
            self._capture_for(region),
            image,
            confidence=confidence,
            grayscale=grayscale,
            timeout=timeout,
            interval=interval,
        )

    def highlight(
        self,
        region: RegionLike,
        color: ColorLike = "#ff0000",
        thickness: int = 2,
        path: str | os.PathLike[str] | None = None,
    ) -> Image:
        image = self.screenshot().outline(region, color, thickness)
        if path is not None:
            image.save(path)
        return image


def screens() -> list[Screen]:
    return [Screen(i) for i in range(len(get_backend().monitors()))]


def desktop() -> Region:
    monitors = get_backend().monitors()
    area = monitors[0].region
    for monitor in monitors[1:]:
        area = area.union(monitor.region)
    return area


screen = Screen()
