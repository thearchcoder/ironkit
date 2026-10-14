from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest

import ironkit as ik
from ironkit.backends.fake import FakeBackend


def noise(rng: np.random.Generator, h: int, w: int) -> np.ndarray:
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


def test_size_and_contains(fake: FakeBackend) -> None:
    assert ik.screen.size == ik.Size(1920, 1080)
    assert ik.screen.contains(0, 0)
    assert ik.screen.contains((1919, 1079))
    assert not ik.screen.contains(1920, 5)
    assert ik.screen.center == ik.Point(960, 540)


def test_multiple_monitors() -> None:
    monitors = [
        ik.Monitor(ik.Region(0, 0, 1920, 1080), 1.0, True, "a"),
        ik.Monitor(ik.Region(1920, 0, 1280, 1024), 1.25, False, "b"),
    ]
    previous = ik.set_backend(FakeBackend(monitors=monitors))
    try:
        assert ik.desktop() == ik.Region(0, 0, 3200, 1080)
        second = ik.screens()[1]
        assert second.region == monitors[1].region
        assert second.scale == 1.25
        assert ik.screen.region == monitors[0].region
    finally:
        ik.set_backend(previous)


def test_screenshot_and_pixel(fake: FakeBackend, rng: np.random.Generator, tmp_path: Path) -> None:
    fake.framebuffer[:] = noise(rng, 1080, 1920)
    shot = ik.screenshot()
    assert shot.size == ik.Size(1920, 1080)
    part = ik.screenshot(region=(10, 20, 30, 40))
    assert part.origin == ik.Point(10, 20)
    assert np.array_equal(part.pixels, fake.framebuffer[20:60, 10:40])
    assert ik.pixel(15, 25) == ik.Color(*fake.framebuffer[25, 15])
    assert ik.pixel_matches(15, 25, tuple(fake.framebuffer[25, 15]))
    saved = tmp_path / "s.png"
    ik.screenshot(region=(0, 0, 8, 8), path=saved)
    assert saved.exists()
    with pytest.raises(ValueError):
        ik.screenshot(region=(0, 0, 0, 5))


def test_find_on_screen(fake: FakeBackend, rng: np.random.Generator) -> None:
    needle = noise(rng, 16, 24)
    fake.paste(needle, (300, 400))
    match = ik.find(needle)
    assert match.region == ik.Region(300, 400, 24, 16)
    assert ik.exists(needle)
    assert ik.find(needle, region=(250, 350, 200, 200)).region.topleft == ik.Point(300, 400)
    assert ik.find_or_none(needle, region=(0, 0, 100, 100)) is None
    with pytest.raises(ik.ImageNotFoundError):
        ik.find(needle, region=(0, 0, 100, 100))


def test_click_image_by_path(fake: FakeBackend, rng: np.random.Generator, tmp_path: Path) -> None:
    needle = noise(rng, 10, 10)
    fake.paste(needle, (500, 600))
    path = tmp_path / "button.png"
    ik.Image(needle).save(path)
    ik.click(str(path))
    assert ik.position() == ik.Point(505, 605)
    ik.move_to(path)
    assert ik.position() == ik.Point(505, 605)


def test_find_waits_until_timeout(fake: FakeBackend, rng: np.random.Generator) -> None:
    needle = noise(rng, 12, 12)
    timer = threading.Timer(0.2, lambda: fake.paste(needle, (40, 50)))
    timer.start()
    began = time.monotonic()
    match = ik.find(needle, timeout=3, interval=0.02)
    assert 0.15 < time.monotonic() - began < 2
    assert match.region.topleft == ik.Point(40, 50)


def test_find_timeout_expires(fake: FakeBackend, rng: np.random.Generator) -> None:
    began = time.monotonic()
    with pytest.raises(ik.ImageNotFoundError):
        ik.find(noise(rng, 8, 8), timeout=0.2, interval=0.05)
    assert time.monotonic() - began >= 0.2


def test_wait_gone(fake: FakeBackend, rng: np.random.Generator) -> None:
    needle = noise(rng, 12, 12)
    fake.paste(needle, (40, 50))
    assert not ik.wait_gone(needle, timeout=0.1, interval=0.02)
    timer = threading.Timer(0.1, lambda: fake.paste(np.zeros((12, 12, 3), np.uint8), (40, 50)))
    timer.start()
    assert ik.wait_gone(needle, timeout=2, interval=0.02)


def test_find_all_on_screen(fake: FakeBackend, rng: np.random.Generator) -> None:
    needle = noise(rng, 8, 8)
    for x in (10, 200, 900):
        fake.paste(needle, (x, 30))
    assert sorted(m.left for m in ik.find_all(needle)) == [10, 200, 900]


def test_highlight(fake: FakeBackend, tmp_path: Path) -> None:
    image = ik.screen.highlight((10, 10, 50, 50), path=tmp_path / "h.png")
    assert image.pixel(10, 10) == ik.Color(255, 0, 0)
    assert (tmp_path / "h.png").exists()
