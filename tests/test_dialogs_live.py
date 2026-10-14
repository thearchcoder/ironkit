from __future__ import annotations

import importlib.util
import os
import sys
import threading
from collections.abc import Callable, Iterator

import pytest

import ironkit as ik

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(importlib.util.find_spec("tkinter") is None, reason="needs tkinter"),
    pytest.mark.skipif(sys.platform.startswith("linux") and not os.environ.get("DISPLAY"), reason="needs a display"),
]


@pytest.fixture(scope="module", autouse=True)
def real_backend() -> Iterator[None]:
    from ironkit.backends import select_backend

    previous = ik.set_backend(select_backend())
    with ik.config.override(pause=0.05, failsafe=False):
        yield
    ik.set_backend(previous)


def operate(title: str, steps: Callable[[], None]) -> threading.Thread:
    def run() -> None:
        ik.windows.get(title, exact=True, timeout=5).activate()
        ik.sleep(0.2)
        steps()

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    return worker


def test_alert_times_out() -> None:
    assert ik.alert("closing by itself", title="ironkit-alert", timeout=0.3) is None


def type_and_submit() -> None:
    ik.write("typed by ironkit")
    ik.press("enter")


def test_prompt_receives_typed_text() -> None:
    worker = operate("ironkit-prompt", type_and_submit)
    assert ik.prompt("Type something", title="ironkit-prompt", timeout=10) == "typed by ironkit"
    worker.join(5)


def test_password_returns_default_on_enter() -> None:
    worker = operate("ironkit-password", lambda: ik.press("enter"))
    assert ik.password("Secret?", title="ironkit-password", default="hunter2", timeout=10) == "hunter2"
    worker.join(5)


def test_confirm_escape_cancels() -> None:
    worker = operate("ironkit-confirm", lambda: ik.press("escape"))
    assert ik.confirm("Sure?", title="ironkit-confirm", timeout=10) is None
    worker.join(5)


def test_confirm_enter_picks_first_button() -> None:
    worker = operate("ironkit-choice", lambda: ik.press("enter"))
    assert ik.confirm("Pick", title="ironkit-choice", buttons=["Yes", "No"], timeout=10) == "Yes"
    worker.join(5)
