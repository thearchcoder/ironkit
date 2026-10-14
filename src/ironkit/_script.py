from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from ._config import config
from ._errors import IronkitError
from ._types import Button

__all__ = ["Command", "ScriptError", "parse", "run"]


class ScriptError(IronkitError):
    pass


@dataclass(frozen=True)
class Command:
    name: str
    args: tuple[object, ...] = ()
    body: tuple[Command, ...] = field(default=())


_COMMAND = re.compile(r"su|sd|ss|c|l|m|r|g|d|k|w|h|f|s|a|p")
_NUMBER = re.compile(r"\s*([+-]?\d+(?:\.\d+)?)")
_QUOTED = re.compile(r"\s*'(.*?)'", re.DOTALL)
_COMMA = re.compile(r"\s*,")
_OPEN = re.compile(r"\s*\(")


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def fail(self, message: str) -> ScriptError:
        return ScriptError(f"invalid command at index {self.pos}: {message}")

    def expect(self, pattern: re.Pattern[str], what: str) -> re.Match[str]:
        found = pattern.match(self.text, self.pos)
        if found is None:
            raise self.fail(f"{what} was expected")
        self.pos = found.end()
        return found

    def number(self) -> str:
        return self.expect(_NUMBER, "a number").group(1)

    def block(self) -> str:
        self.expect(_OPEN, "an open parenthesis")
        start = self.pos
        depth = 1
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return self.text[start : self.pos - 1]
        raise self.fail("not enough close parentheses")

    def commands(self) -> list[Command]:
        result: list[Command] = []
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
                continue
            found = _COMMAND.match(self.text, self.pos)
            if found is None:
                raise self.fail(f"{self.text[self.pos]!r} is not a valid command")
            name = found.group(0)
            self.pos = found.end()
            result.append(self.arguments(name))
        return result

    def arguments(self, name: str) -> Command:
        if name in ("c", "l", "m", "r", "su", "sd", "ss"):
            return Command(name)
        if name in ("g", "d"):
            x = self.number()
            self.expect(_COMMA, "a comma")
            y = self.number()
            x_signed, y_signed = x[0] in "+-", y[0] in "+-"
            if x_signed != y_signed:
                raise self.fail("x and y must both have a +/- sign or neither")
            return Command(name, (int(float(x)), int(float(y)), x_signed))
        if name in ("s", "p"):
            return Command(name, (float(self.number()),))
        if name in ("k", "w", "h", "a"):
            return Command(name, (self.expect(_QUOTED, "a quoted string").group(1),))
        count = int(float(self.number()))
        return Command(name, (count,), tuple(_Parser(self.block()).commands()))


def parse(text: str) -> list[Command]:
    return _Parser(text).commands()


def _execute(commands: list[Command] | tuple[Command, ...], shots: list[int]) -> None:
    from ._dialogs import alert
    from ._input import keyboard, mouse
    from ._screen import screen

    for command in commands:
        name, args = command.name, command.args
        if name == "c":
            mouse.click(button=Button.PRIMARY)
        elif name == "l":
            mouse.click(button=Button.LEFT)
        elif name == "m":
            mouse.click(button=Button.MIDDLE)
        elif name == "r":
            mouse.click(button=Button.RIGHT)
        elif name == "su":
            mouse.scroll(1)
        elif name == "sd":
            mouse.scroll(-1)
        elif name == "ss":
            screen.screenshot(path=f"screenshot{shots[0]}.png")
            shots[0] += 1
        elif name == "s":
            time.sleep(float(str(args[0])))
        elif name == "p":
            config.pause = float(str(args[0]))
        elif name in ("g", "d"):
            x, y, relative = int(str(args[0])), int(str(args[1])), bool(args[2])
            if name == "g":
                if relative:
                    mouse.move_by(x, y)
                else:
                    mouse.move_to(x, y)
            elif relative:
                mouse.drag_by(x, y)
            else:
                mouse.drag_to(x, y)
        elif name == "k":
            keyboard.press(str(args[0]))
        elif name == "w":
            keyboard.write(str(args[0]))
        elif name == "h":
            keyboard.hotkey(*[k for k in str(args[0]).replace(" ", "").split(",") if k])
        elif name == "a":
            alert(str(args[0]))
        elif name == "f":
            for _ in range(int(str(args[0]))):
                _execute(command.body, shots)


def run(script: str) -> None:
    commands = parse(script)
    with config.override(pause=config.pause):
        _execute(commands, [0])
