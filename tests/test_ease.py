from __future__ import annotations

import pytest

import ironkit as ik

NAMES = [n for n in ik.ease.__all__ if n not in ("Ease", "point_on_line")]


def test_has_all_31_functions() -> None:
    assert len(NAMES) == 31


@pytest.mark.parametrize("name", NAMES)
def test_endpoints(name: str) -> None:
    fn = getattr(ik.ease, name)
    assert fn(0.0) == pytest.approx(0.0, abs=1e-9)
    assert fn(1.0) == pytest.approx(1.0, abs=1e-9)
    assert fn(-1.0) == pytest.approx(0.0, abs=1e-9)
    assert fn(2.0) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("name", [n for n in NAMES if n.startswith("in_out")])
def test_in_out_symmetric(name: str) -> None:
    fn = getattr(ik.ease, name)
    assert fn(0.5) == pytest.approx(0.5, abs=1e-9)


def test_known_values() -> None:
    assert ik.ease.in_quad(0.5) == 0.25
    assert ik.ease.out_quad(0.5) == 0.75
    assert ik.ease.in_cubic(0.5) == 0.125
    assert ik.ease.point_on_line((0, 0), (10, 10), 0.3) == ik.Point(3, 3)
