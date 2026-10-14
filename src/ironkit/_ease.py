from __future__ import annotations

import math
from collections.abc import Callable

from ._types import Point, PointLike

Ease = Callable[[float], float]

__all__ = [
    "Ease",
    "in_back",
    "in_bounce",
    "in_circ",
    "in_cubic",
    "in_elastic",
    "in_expo",
    "in_out_back",
    "in_out_bounce",
    "in_out_circ",
    "in_out_cubic",
    "in_out_elastic",
    "in_out_expo",
    "in_out_quad",
    "in_out_quart",
    "in_out_quint",
    "in_out_sine",
    "in_quad",
    "in_quart",
    "in_quint",
    "in_sine",
    "linear",
    "out_back",
    "out_bounce",
    "out_circ",
    "out_cubic",
    "out_elastic",
    "out_expo",
    "out_quad",
    "out_quart",
    "out_quint",
    "out_sine",
    "point_on_line",
]


def _clamp(t: float) -> float:
    return 0.0 if t <= 0.0 else 1.0 if t >= 1.0 else t


def _out(ease_in: Ease, t: float) -> float:
    return 1.0 - ease_in(1.0 - t)


def _in_out(ease_in: Ease, t: float) -> float:
    if t < 0.5:
        return ease_in(2.0 * t) / 2.0
    return 1.0 - ease_in(2.0 - 2.0 * t) / 2.0


def point_on_line(a: PointLike, b: PointLike, t: float) -> Point:
    return Point.of(a).lerp(b, t)


def linear(t: float) -> float:
    return _clamp(t)


def in_quad(t: float) -> float:
    t = _clamp(t)
    return t * t


def out_quad(t: float) -> float:
    return _out(in_quad, _clamp(t))


def in_out_quad(t: float) -> float:
    return _in_out(in_quad, _clamp(t))


def in_cubic(t: float) -> float:
    t = _clamp(t)
    return t * t * t


def out_cubic(t: float) -> float:
    return _out(in_cubic, _clamp(t))


def in_out_cubic(t: float) -> float:
    return _in_out(in_cubic, _clamp(t))


def in_quart(t: float) -> float:
    t = _clamp(t)
    return t**4


def out_quart(t: float) -> float:
    return _out(in_quart, _clamp(t))


def in_out_quart(t: float) -> float:
    return _in_out(in_quart, _clamp(t))


def in_quint(t: float) -> float:
    t = _clamp(t)
    return t**5


def out_quint(t: float) -> float:
    return _out(in_quint, _clamp(t))


def in_out_quint(t: float) -> float:
    return _in_out(in_quint, _clamp(t))


def in_sine(t: float) -> float:
    t = _clamp(t)
    return 1.0 - math.cos(t * math.pi / 2.0)


def out_sine(t: float) -> float:
    return _out(in_sine, _clamp(t))


def in_out_sine(t: float) -> float:
    return _in_out(in_sine, _clamp(t))


def in_expo(t: float) -> float:
    t = _clamp(t)
    return 0.0 if t == 0.0 else 2.0 ** (10.0 * t - 10.0)


def out_expo(t: float) -> float:
    return _out(in_expo, _clamp(t))


def in_out_expo(t: float) -> float:
    return _in_out(in_expo, _clamp(t))


def in_circ(t: float) -> float:
    t = _clamp(t)
    return 1.0 - math.sqrt(1.0 - t * t)


def out_circ(t: float) -> float:
    return _out(in_circ, _clamp(t))


def in_out_circ(t: float) -> float:
    return _in_out(in_circ, _clamp(t))


def in_elastic(t: float) -> float:
    t = _clamp(t)
    if t in (0.0, 1.0):
        return t
    return -(2.0 ** (10.0 * t - 10.0)) * math.sin((10.0 * t - 10.75) * (2.0 * math.pi / 3.0))


def out_elastic(t: float) -> float:
    return _out(in_elastic, _clamp(t))


def in_out_elastic(t: float) -> float:
    return _in_out(in_elastic, _clamp(t))


def in_back(t: float) -> float:
    t = _clamp(t)
    c1 = 1.70158
    return (c1 + 1.0) * t * t * t - c1 * t * t


def out_back(t: float) -> float:
    return _out(in_back, _clamp(t))


def in_out_back(t: float) -> float:
    return _in_out(in_back, _clamp(t))


def out_bounce(t: float) -> float:
    t = _clamp(t)
    n, d = 7.5625, 2.75
    if t < 1.0 / d:
        return n * t * t
    if t < 2.0 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375


def in_bounce(t: float) -> float:
    return 1.0 - out_bounce(1.0 - _clamp(t))


def in_out_bounce(t: float) -> float:
    return _in_out(in_bounce, _clamp(t))
