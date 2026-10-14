from __future__ import annotations

import os

import pytest

import ironkit as ik
from ironkit._script import Command, parse
from ironkit.backends.fake import FakeBackend


def test_parse() -> None:
    assert parse("c c g-20,+0 c") == [
        Command("c"),
        Command("c"),
        Command("g", (-20, 0, True)),
        Command("c"),
    ]
    assert parse("g100,200") == [Command("g", (100, 200, False))]
    assert parse("k'enter' w'hi there' h'ctrl, c' s0.5 p1") == [
        Command("k", ("enter",)),
        Command("w", ("hi there",)),
        Command("h", ("ctrl, c",)),
        Command("s", (0.5,)),
        Command("p", (1.0,)),
    ]
    assert parse("f2(c f3(r))") == [Command("f", (2,), (Command("c"), Command("f", (3,), (Command("r"),))))]


@pytest.mark.parametrize(
    ("script", "message"),
    [
        ("x", "not a valid command"),
        ("g10", "comma"),
        ("g+10,10", "sign"),
        ("k enter", "quoted string"),
        ("f2(c", "close parentheses"),
        ("f2 c", "open parenthesis"),
    ],
)
def test_parse_errors(script: str, message: str) -> None:
    with pytest.raises(ik.ScriptError, match=message):
        parse(script)


def test_run(fake: FakeBackend, tmp_cwd: os.PathLike[str]) -> None:
    ik.move_to(500, 500)
    ik.run("g100,100 c g+10,-10 l m r su sd k'a' w'xy' h'ctrl,v' d200,200 d-50,+0 f2(c) ss ss")
    assert ik.position() == ik.Point(150, 200)
    assert fake.typed == ["x", "y"]
    presses = [e[1] for e in fake.events if e[0] == "button" and e[2]]
    assert presses == ["left", "left", "middle", "right", "left", "left", "left", "left"]
    assert [e for e in fake.events if e[0] == "scroll"] == [("scroll", 0, 1), ("scroll", 0, -1)]
    assert sorted(os.listdir(tmp_cwd)) == ["screenshot0.png", "screenshot1.png"]


def test_run_restores_pause(fake: FakeBackend) -> None:
    before = ik.config.pause
    ik.run("p0 c")
    assert ik.config.pause == before
