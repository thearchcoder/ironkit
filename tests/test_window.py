from __future__ import annotations

import re
import threading

import numpy as np
import pytest

import ironkit as ik
from ironkit.backends.fake import FakeBackend


@pytest.fixture
def apps(fake: FakeBackend) -> dict[str, int]:
    return {
        "notepad": fake.add_window("Untitled - Notepad", (100, 100, 400, 300), pid=10),
        "browser": fake.add_window("Docs - Browser", (300, 200, 800, 600), pid=20),
    }


def test_listing(apps: dict[str, int]) -> None:
    assert len(ik.windows.all()) == 2
    assert set(ik.windows.titles()) == {"Untitled - Notepad", "Docs - Browser"}
    active = ik.windows.active()
    assert active is not None
    assert active.handle == apps["browser"]
    assert ik.windows.active_title() == "Docs - Browser"


def test_find_and_get(apps: dict[str, int]) -> None:
    assert [w.handle for w in ik.windows.find("notepad")] == [apps["notepad"]]
    assert ik.windows.find("notepad", exact=True) == []
    assert ik.windows.find("Untitled - Notepad", exact=True)[0].handle == apps["notepad"]
    assert ik.windows.find(re.compile(r"^Docs"))[0].handle == apps["browser"]
    assert ik.windows.find(pid=20)[0].handle == apps["browser"]
    assert ik.windows.get("browser").title == "Docs - Browser"
    with pytest.raises(ik.WindowNotFoundError):
        ik.windows.get("missing")


def test_get_waits_for_window(fake: FakeBackend) -> None:
    threading.Timer(0.1, lambda: fake.add_window("Late", (0, 0, 10, 10))).start()
    assert ik.windows.get("late", timeout=2, interval=0.02).title == "Late"


def test_at(apps: dict[str, int]) -> None:
    assert {w.handle for w in ik.windows.at(350, 250)} == set(apps.values())
    assert [w.handle for w in ik.windows.at(150, 150)] == [apps["notepad"]]
    assert ik.windows.at(5, 5) == []


def test_properties_and_actions(fake: FakeBackend, apps: dict[str, int]) -> None:
    win = ik.windows.get("notepad")
    assert win.region == ik.Region(100, 100, 400, 300)
    assert (win.left, win.top, win.width, win.height) == (100, 100, 400, 300)
    assert win.center == ik.Point(300, 250)
    assert win.pid == 10
    assert not win.is_active
    assert win.activate().is_active
    win.minimize()
    assert win.is_minimized
    win.restore()
    assert not win.is_minimized
    win.maximize()
    assert win.is_maximized
    win.hide()
    assert not win.is_visible
    win.show()
    assert win.is_visible
    win.move_to(10, 20).resize_to(200, 100)
    assert win.region == ik.Region(10, 20, 200, 100)
    win.move_by(5, 5).resize_by(10, -10)
    assert win.region == ik.Region(15, 25, 210, 90)
    assert win.point(1, 2) == ik.Point(16, 27)
    assert win.is_open
    win.close()
    assert not win.is_open
    with pytest.raises(ik.WindowNotFoundError):
        _ = win.title
    assert "closed" in repr(win)


def test_window_equality(apps: dict[str, int]) -> None:
    a = ik.windows.get("notepad")
    b = ik.windows.find("Notepad")[0]
    assert a == b
    assert len({a, b}) == 1


def test_window_image_search(fake: FakeBackend, rng: np.random.Generator) -> None:
    content = rng.integers(0, 256, (300, 400, 3), dtype=np.uint8)
    handle = fake.add_window("Game", (100, 100, 400, 300), pixels=content)
    win = ik.Window(handle)
    needle = content[50:70, 80:110].copy()
    match = win.find(needle)
    assert match.region == ik.Region(180, 150, 30, 20)
    assert win.exists(needle)
    assert win.pixel(80, 50) == ik.Color(*content[50, 80])
    assert len(win.find_all(needle)) == 1
    assert win.find_or_none(np.zeros((5, 5, 3), np.uint8) + 7) is None
    assert win.screenshot().origin == ik.Point(100, 100)


def test_click_window_center(fake: FakeBackend, apps: dict[str, int]) -> None:
    ik.click(ik.windows.get("notepad"))
    assert ik.position() == ik.Point(300, 250)
