from __future__ import annotations

import time

import pytest

import ironkit as ik
from ironkit.backends.fake import FakeBackend


def moves(fake: FakeBackend) -> list[tuple[object, ...]]:
    return [e for e in fake.events if e[0] == "move"]


def buttons(fake: FakeBackend) -> list[tuple[object, ...]]:
    return [e for e in fake.events if e[0] == "button"]


def test_move_to_and_position(fake: FakeBackend) -> None:
    ik.move_to(100, 200)
    assert ik.position() == ik.Point(100, 200)
    assert ik.mouse.position == ik.Point(100, 200)


def test_move_partial_coordinates(fake: FakeBackend) -> None:
    ik.move_to(100, 200)
    ik.move_to(x=300)
    assert ik.position() == ik.Point(300, 200)
    ik.move_to(y=50)
    assert ik.position() == ik.Point(300, 50)


def test_move_accepts_points_regions_and_tuples(fake: FakeBackend) -> None:
    ik.move_to(ik.Point(5, 6))
    assert ik.position() == ik.Point(5, 6)
    ik.move_to((7, 8))
    assert ik.position() == ik.Point(7, 8)
    ik.move_to(ik.Region(100, 100, 20, 10))
    assert ik.position() == ik.Point(110, 105)
    with pytest.raises(TypeError):
        ik.move_to(ik.Point(1, 1), 5)


def test_move_by(fake: FakeBackend) -> None:
    ik.move_to(100, 100)
    ik.move_by(10, -20)
    assert ik.position() == ik.Point(110, 80)


def test_raw_relative_move(fake: FakeBackend) -> None:
    ik.move_to(100, 100)
    ik.move_by(30, 40, raw=True)
    assert ("move_relative", 30, 40) in fake.events
    assert ik.position() == ik.Point(130, 140)


def test_raw_relative_move_with_duration_sums_exactly(fake: FakeBackend) -> None:
    ik.move_to(500, 500)
    ik.move_by(97, -13, raw=True, duration=0.15)
    deltas = [e for e in fake.events if e[0] == "move_relative"]
    assert len(deltas) > 1
    assert sum(int(str(e[1])) for e in deltas) == 97
    assert sum(int(str(e[2])) for e in deltas) == -13


def test_tweened_move_reaches_target(fake: FakeBackend) -> None:
    ik.move_to(0 + 10, 10)
    fake.events.clear()
    ik.move_to(500, 300, duration=0.15, ease=ik.ease.in_out_quad)
    steps = moves(fake)
    assert len(steps) > 3
    assert steps[-1] == ("move", 500, 300)


def test_short_duration_is_instant(fake: FakeBackend) -> None:
    fake.events.clear()
    ik.move_to(50, 50, duration=0.01)
    assert moves(fake) == [("move", 50, 50)]


def test_click_variants(fake: FakeBackend) -> None:
    ik.click(10, 20)
    assert ik.position() == ik.Point(10, 20)
    assert buttons(fake) == [("button", "left", True, 1), ("button", "left", False, 1)]
    fake.events.clear()
    ik.double_click()
    assert [e[3] for e in buttons(fake)] == [1, 1, 2, 2]
    fake.events.clear()
    ik.triple_click(button="right")
    assert {e[1] for e in buttons(fake)} == {"right"}
    assert len(buttons(fake)) == 6
    fake.events.clear()
    ik.right_click()
    ik.middle_click()
    ik.left_click()
    assert [e[1] for e in buttons(fake) if e[2]] == ["right", "middle", "left"]


def test_click_interval(fake: FakeBackend) -> None:
    began = time.monotonic()
    ik.click(clicks=3, interval=0.05)
    assert time.monotonic() - began >= 0.09


def test_primary_secondary_respect_swapped_buttons(fake: FakeBackend) -> None:
    ik.click(button=ik.Button.PRIMARY)
    ik.click(button=ik.Button.SECONDARY)
    fake.swapped = True
    ik.click(button="primary")
    assert [e[1] for e in buttons(fake) if e[2]] == ["left", "right", "right"]


def test_mouse_down_up_and_hold(fake: FakeBackend) -> None:
    ik.mouse_down(button="right")
    assert ik.Button.RIGHT in fake.pressed_buttons
    ik.mouse_up(button="right")
    assert not fake.pressed_buttons
    with ik.mouse.hold():
        assert ik.Button.LEFT in fake.pressed_buttons
    assert not fake.pressed_buttons


def test_drag(fake: FakeBackend) -> None:
    ik.move_to(10, 10)
    fake.events.clear()
    ik.drag_to(100, 100)
    assert fake.events[0] == ("button", "left", True, 1)
    assert fake.events[-1] == ("button", "left", False, 1)
    assert ik.position() == ik.Point(100, 100)
    ik.drag_by(-50, 25, button="middle")
    assert ik.position() == ik.Point(50, 125)
    assert not fake.pressed_buttons


def test_drag_releases_button_on_error(fake: FakeBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(x: int, y: int) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(fake, "mouse_move", boom)
    with pytest.raises(RuntimeError):
        ik.drag_to(5, 5)
    assert not fake.pressed_buttons


def test_scroll(fake: FakeBackend) -> None:
    ik.scroll(3)
    ik.scroll(-2, 100, 100)
    ik.hscroll(4)
    assert [e for e in fake.events if e[0] == "scroll"] == [("scroll", 0, 3), ("scroll", 0, -2), ("scroll", 4, 0)]
    assert ik.position() == ik.Point(100, 100)


def test_failsafe(fake: FakeBackend) -> None:
    fake.position = ik.Point(0, 0)
    with pytest.raises(ik.FailSafeError):
        ik.click()
    with ik.config.override(failsafe=False):
        ik.click()
    with ik.config.override(failsafe_points=[(5, 5)]):
        ik.click()
        fake.position = ik.Point(5, 5)
        with pytest.raises(ik.FailSafeError):
            ik.press("a")


def test_failsafe_during_glide(fake: FakeBackend) -> None:
    ik.move_to(400, 400)
    original = fake.mouse_move
    calls = {"n": 0}

    def hijack(x: int, y: int) -> None:
        calls["n"] += 1
        original(x, y)
        if calls["n"] == 3:
            fake.position = ik.Point(0, 0)

    fake.mouse_move = hijack
    with pytest.raises(ik.FailSafeError):
        ik.move_to(800, 800, duration=0.3)


def test_pause_applies_once_per_call(fake: FakeBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    from ironkit import _input

    slept: list[float] = []
    monkeypatch.setattr(_input.time, "sleep", slept.append)
    with ik.config.override(pause=0.05):
        ik.click(100, 100)
        ik.drag_by(10, 10)
    assert slept == [0.05, 0.05]


def test_write_and_special_characters(fake: FakeBackend) -> None:
    ik.write("Hi!\n\tok")
    assert fake.typed == ["H", "i", "!", "o", "k"]
    keys = [e[1] for e in fake.events if e[0] == "key" and e[2]]
    assert keys == ["enter", "tab"]


def test_write_list_of_keys(fake: FakeBackend) -> None:
    ik.write(["a", "left", "enter"])
    assert [e[1] for e in fake.events if e[0] == "key" and e[2]] == ["a", "left", "enter"]


def test_press(fake: FakeBackend) -> None:
    ik.press("enter")
    ik.press("a", "b", times=2)
    ik.press(["x", "y"])
    downs = [e[1] for e in fake.events if e[0] == "key" and e[2]]
    assert downs == ["enter", "a", "b", "a", "b", "x", "y"]
    assert not fake.pressed_keys
    with pytest.raises(ik.InvalidKeyError):
        ik.press("bogus")


def test_key_down_up_and_hold(fake: FakeBackend) -> None:
    ik.key_down("shift")
    assert "shift" in fake.pressed_keys
    ik.key_up("shift")
    with ik.hold("ctrl", "alt"):
        assert {"ctrl", "alt"} <= fake.pressed_keys
    assert not fake.pressed_keys
    assert [e[1] for e in fake.events if e[0] == "key" and not e[2]][-2:] == ["alt", "ctrl"]


def test_hold_releases_on_error(fake: FakeBackend) -> None:
    with pytest.raises(RuntimeError), ik.hold(ik.Key.SHIFT):
        raise RuntimeError
    assert not fake.pressed_keys


def test_hotkey_order(fake: FakeBackend) -> None:
    ik.hotkey("ctrl", "shift", "esc")
    seq = [(e[1], e[2]) for e in fake.events if e[0] == "key"]
    assert seq == [
        ("ctrl", True),
        ("shift", True),
        ("escape", True),
        ("escape", False),
        ("shift", False),
        ("ctrl", False),
    ]


def test_log_screenshots(fake: FakeBackend, tmp_path: object) -> None:
    from pathlib import Path

    folder = Path(str(tmp_path))
    with ik.config.override(log_screenshots=True, log_screenshots_dir=folder, log_screenshots_limit=2):
        ik.click(5, 5)
        ik.press("a")
        ik.write("b")
    assert len(list(folder.glob("*.png"))) == 2
