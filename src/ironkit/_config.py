from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from ._errors import FailSafeError
from ._types import Point, PointLike
from .backends import get_backend


def _default_failsafe_points() -> list[Point]:
    return [Point(0, 0)]


@dataclass
class Config:
    pause: float = 0.1
    failsafe: bool = True
    failsafe_points: list[Point] = field(default_factory=_default_failsafe_points)
    minimum_duration: float = 0.1
    minimum_sleep: float = 0.01
    darwin_catch_up_time: float = 0.01
    confidence: float = 0.999
    find_interval: float = 0.1
    log_screenshots: bool = False
    log_screenshots_limit: int | None = 10
    log_screenshots_dir: Path = field(default_factory=Path)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "failsafe_points":
            value = [Point.of(p) for p in value]
        elif name == "log_screenshots_dir":
            value = Path(value)
        object.__setattr__(self, name, value)

    @contextmanager
    def override(self, **changes: Any) -> Iterator[Config]:
        names = {f.name for f in fields(self)}
        unknown = set(changes) - names
        if unknown:
            raise AttributeError(f"unknown config option(s): {', '.join(sorted(unknown))}")
        saved = {name: getattr(self, name) for name in changes}
        try:
            for name, value in changes.items():
                setattr(self, name, value)
            yield self
        finally:
            for name, value in saved.items():
                setattr(self, name, value)

    def is_failsafe_point(self, point: PointLike) -> bool:
        return Point.of(point) in self.failsafe_points

    def check_failsafe(self) -> None:
        if not self.failsafe:
            return
        backend = get_backend()
        if not backend.capabilities.read_cursor:
            return
        position = backend.mouse_position()
        if position in self.failsafe_points:
            raise FailSafeError(
                f"fail-safe triggered: mouse moved to {tuple(position)}; set ironkit.config.failsafe = False to disable"
            )


config = Config()
