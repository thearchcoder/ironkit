from __future__ import annotations

import platform
import sys
import time
from typing import Any, TextIO

from ._errors import IronkitError, UnsupportedFeatureError
from .backends import get_backend

__all__ = ["capabilities", "countdown", "info", "inspect", "inspector", "print_info", "sleep", "version"]


def version() -> str:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as package_version

    try:
        return package_version("ironkit")
    except PackageNotFoundError:
        return "unknown"


def sleep(seconds: float) -> None:
    time.sleep(seconds)


def countdown(seconds: int, out: TextIO | None = None) -> None:
    stream = out or sys.stdout
    for remaining in range(int(seconds), 0, -1):
        stream.write(f"{remaining} ")
        stream.flush()
        time.sleep(1)
    stream.write("\n")
    stream.flush()


def capabilities() -> dict[str, bool]:
    caps = get_backend().capabilities
    return {name: bool(getattr(caps, name)) for name in caps.__dataclass_fields__}


def info() -> dict[str, Any]:
    backend = get_backend()
    monitors = backend.monitors()
    return {
        "ironkit": version(),
        "python": platform.python_version(),
        "platform": sys.platform,
        "os": platform.platform(),
        "backend": backend.name,
        "monitors": [
            {"region": tuple(m.region), "scale": m.scale, "primary": m.primary, "name": m.name} for m in monitors
        ],
        "capabilities": capabilities(),
    }


def print_info(out: TextIO | None = None) -> None:
    stream = out or sys.stdout
    for key, value in info().items():
        stream.write(f"{key}: {value}\n")


def inspect(interval: float = 0.05, out: TextIO | None = None) -> None:
    backend = get_backend()
    if not backend.capabilities.read_cursor:
        raise UnsupportedFeatureError(f"the {backend.name} backend cannot read the cursor position")
    from ._screen import screen

    stream = out or sys.stdout
    stream.write("Press Ctrl-C to quit.\n")
    last = ""
    try:
        while True:
            position = backend.mouse_position()
            try:
                color = screen.pixel(position)
                color_text = f"RGB({color.r:3d}, {color.g:3d}, {color.b:3d}) {color.hex}"
            except IronkitError:
                color_text = "RGB(unavailable)"
            line = f"X: {position.x:5d}  Y: {position.y:5d}  {color_text}"
            if line != last:
                stream.write("\r" + line.ljust(len(last)))
                stream.flush()
                last = line
            time.sleep(interval)
    except KeyboardInterrupt:
        stream.write("\n")
        stream.flush()


def inspector(interval: float = 0.05) -> None:
    backend = get_backend()
    if not backend.capabilities.read_cursor:
        raise UnsupportedFeatureError(f"the {backend.name} backend cannot read the cursor position")
    from ._dialogs import _tk
    from ._screen import screen

    tk = _tk()
    root = tk.Tk()
    root.title("ironkit inspector")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    text = tk.StringVar(master=root)
    swatch = tk.Label(root, width=4, height=2, relief="sunken")
    swatch.pack(side="left", padx=10, pady=10)
    tk.Label(root, textvariable=text, font=("TkFixedFont", 11), justify="left").pack(side="left", padx=(0, 10))
    copied = tk.StringVar(master=root, value="Press C to copy X,Y and H to copy hex.")
    tk.Label(root, textvariable=copied).pack(side="bottom", pady=(0, 6))
    state: dict[str, str] = {"xy": "", "hex": ""}

    def refresh() -> None:
        position = backend.mouse_position()
        try:
            color = screen.pixel(position)
            state["hex"] = color.hex
            text.set(f"X: {position.x}  Y: {position.y}\nRGB: {color.r}, {color.g}, {color.b}\nHex: {color.hex}")
            swatch.configure(background=color.hex)
        except IronkitError:
            text.set(f"X: {position.x}  Y: {position.y}\nRGB: unavailable")
        state["xy"] = f"{position.x},{position.y}"
        root.after(int(interval * 1000), refresh)

    def copy(kind: str) -> None:
        root.clipboard_clear()
        root.clipboard_append(state[kind])
        copied.set(f"Copied {state[kind]}")

    root.bind("<c>", lambda _e: copy("xy"))
    root.bind("<h>", lambda _e: copy("hex"))
    refresh()
    root.mainloop()
