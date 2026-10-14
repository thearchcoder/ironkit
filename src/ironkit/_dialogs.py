from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ._errors import IronkitError

__all__ = ["alert", "confirm", "password", "prompt"]


def _tk() -> Any:
    try:
        import tkinter
    except ImportError:
        raise IronkitError("dialogs need tkinter; install your platform's python3-tk package") from None
    return tkinter


def _show(
    text: str,
    title: str,
    buttons: Sequence[str],
    *,
    entry: bool = False,
    default: str = "",
    mask: str | None = None,
    cancel: str | None = None,
    timeout: float | None = None,
) -> str | None:
    tk = _tk()
    root = tk.Tk()
    root.withdraw()
    window = tk.Toplevel(root)
    window.title(title)
    window.resizable(False, False)
    window.attributes("-topmost", True)
    result: list[str | None] = [None]
    value = tk.StringVar(master=window, value=default)

    def finish(choice: str | None) -> None:
        if choice is not None and entry:
            result[0] = None if choice == cancel else value.get()
        else:
            result[0] = choice
        root.quit()

    tk.Label(window, text=text, justify="left", wraplength=420, padx=18, pady=14).pack(anchor="w")
    field = None
    if entry:
        field = tk.Entry(window, textvariable=value, show=mask or "", width=44)
        field.pack(padx=18, fill="x")
        field.select_range(0, "end")
    row = tk.Frame(window)
    row.pack(padx=18, pady=14, anchor="e")
    for label in buttons:
        tk.Button(row, text=label, width=max(8, len(label) + 2), command=lambda c=label: finish(c)).pack(
            side="left", padx=4
        )
    window.bind("<Return>", lambda _e: finish(buttons[0]))
    window.bind("<Escape>", lambda _e: finish(cancel))
    window.protocol("WM_DELETE_WINDOW", lambda: finish(cancel))
    if timeout is not None:
        window.after(int(timeout * 1000), lambda: finish(None))
    window.update_idletasks()
    x = (window.winfo_screenwidth() - window.winfo_reqwidth()) // 2
    y = (window.winfo_screenheight() - window.winfo_reqheight()) // 3
    window.geometry(f"+{x}+{y}")
    window.lift()
    window.focus_force()
    if field is not None:
        field.focus_set()
    try:
        root.mainloop()
    finally:
        root.destroy()
    return result[0]


def alert(text: str = "", title: str = "", button: str = "OK", timeout: float | None = None) -> str | None:
    return _show(text, title, [button], cancel=button, timeout=timeout)


def confirm(
    text: str = "",
    title: str = "",
    buttons: Sequence[str] = ("OK", "Cancel"),
    timeout: float | None = None,
) -> str | None:
    return _show(text, title, list(buttons), timeout=timeout)


def prompt(text: str = "", title: str = "", default: str = "", timeout: float | None = None) -> str | None:
    return _show(text, title, ["OK", "Cancel"], entry=True, default=default, cancel="Cancel", timeout=timeout)


def password(
    text: str = "",
    title: str = "",
    default: str = "",
    mask: str = "*",
    timeout: float | None = None,
) -> str | None:
    return _show(
        text,
        title,
        ["OK", "Cancel"],
        entry=True,
        default=default,
        mask=mask,
        cancel="Cancel",
        timeout=timeout,
    )
