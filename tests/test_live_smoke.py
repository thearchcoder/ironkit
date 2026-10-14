from __future__ import annotations

import os
import sys
from collections.abc import Iterator

import pytest

import ironkit as ik
from ironkit.backends import Backend, select_backend

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
        reason="needs a display",
    ),
]


@pytest.fixture(scope="module")
def backend() -> Iterator[Backend]:
    instance = select_backend()
    previous = ik.set_backend(instance)
    with ik.config.override(pause=0.0, failsafe=False):
        yield instance
    ik.set_backend(previous)


def test_monitors(backend: Backend) -> None:
    monitors = backend.monitors()
    assert monitors
    assert sum(m.primary for m in monitors) == 1
    assert all(m.region.width > 0 and m.region.height > 0 for m in monitors)


def test_capture(backend: Backend) -> None:
    shot = ik.screenshot(region=(0, 0, 64, 48))
    assert shot.size == ik.Size(64, 48)
    full = ik.screenshot()
    assert full.size == ik.screen.size


def test_mouse_round_trip(backend: Backend) -> None:
    target = ik.screen.region.center.offset(-17, 11)
    ik.move_to(target)
    assert ik.position() == target
    ik.move_by(10, 10)
    assert ik.position() == target.offset(10, 10)


def test_find_what_we_captured(backend: Backend) -> None:
    center = ik.screen.region.center
    shot = ik.screenshot(region=(center.x - 200, center.y - 150, 400, 300))
    needle = shot.crop((center.x - 20, center.y - 20, 40, 40))
    assert shot.exists(needle, confidence=0.9) or needle.pixels.std() == 0


def test_windows_listing_does_not_fail(backend: Backend) -> None:
    for window in ik.windows.all()[:10]:
        assert isinstance(window.title, str)
        assert window.region.width >= 0
