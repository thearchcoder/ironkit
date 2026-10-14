from __future__ import annotations

import pytest

import ironkit as ik
from ironkit._types import key_name, needs_shift


def test_point_arithmetic() -> None:
    p = ik.Point(3, 4)
    assert p + (1, 1) == ik.Point(4, 5)
    assert p - ik.Point(3, 4) == ik.Point(0, 0)
    assert p.offset(dx=2) == ik.Point(5, 4)
    assert ik.Point(0, 0).distance_to(p) == 5
    assert ik.Point(0, 0).lerp((10, 20), 0.5) == ik.Point(5, 10)
    x, y = p
    assert (x, y) == (3, 4)


def test_region_geometry() -> None:
    r = ik.Region(10, 20, 100, 50)
    assert (r.right, r.bottom) == (110, 70)
    assert r.center == ik.Point(60, 45)
    assert r.size == ik.Size(100, 50)
    assert r.contains((10, 20))
    assert not r.contains((110, 20))
    assert (50, 50) in r
    assert r.intersect((100, 60, 50, 50)) == ik.Region(100, 60, 10, 10)
    assert r.intersect((500, 500, 1, 1)) is None
    assert r.union((0, 0, 5, 5)) == ik.Region(0, 0, 110, 70)
    assert r.inset(5) == ik.Region(15, 25, 90, 40)
    assert r.point(1, 2) == ik.Point(11, 22)
    assert ik.Region.from_corners((5, 5), (0, 0)) == ik.Region(0, 0, 5, 5)


def test_color() -> None:
    c = ik.Color.from_hex("#ff8000")
    assert c == ik.Color(255, 128, 0)
    assert c.hex == "#ff8000"
    assert ik.Color.from_hex("f80") == ik.Color(255, 136, 0)
    assert c.matches((250, 130, 3), tolerance=5)
    assert not c.matches((240, 128, 0), tolerance=5)
    with pytest.raises(ValueError):
        ik.Color.from_hex("#12")


def test_key_names() -> None:
    assert key_name("Return") == "enter"
    assert key_name(ik.Key.F5) == "f5"
    assert key_name("A") == "A"
    assert key_name("\n") == "enter"
    assert key_name("pgdn") == "pagedown"
    with pytest.raises(ik.InvalidKeyError):
        key_name("notakey")
    assert ik.keyboard.is_valid("ctrl")
    assert not ik.keyboard.is_valid("ctrl+c")
    assert not ik.keyboard.is_valid(5)


def test_needs_shift() -> None:
    assert needs_shift("A")
    assert needs_shift("!")
    assert not needs_shift("a")
    assert not needs_shift("1")
    assert needs_shift("Ü")
    assert ik.keyboard.needs_shift("?", ik.Layout.QWERTY)


def test_button_parsing() -> None:
    assert ik.Button.of("LEFT") is ik.Button.LEFT
    with pytest.raises(ValueError):
        ik.Button.of("fourth")
