# ironkit

Reliable cross-platform desktop automation for Python. Mouse, keyboard, screenshots, image search, windows and dialogs, behind one small typed API.

ironkit covers everything [PyAutoGUI](https://github.com/asweigart/pyautogui) does, and fixes the parts that make PyAutoGUI scripts flaky:

- **Typed objects** instead of bare tuples: `Point`, `Region`, `Color`, `Match`, `Window`.
- **Consistent errors.** `find()` always raises `ImageNotFoundError`, and tells you the best confidence it saw. Use `find_or_none()` or `exists()` when you'd rather check.
- **Built-in waiting.** Every search takes `timeout=`, so `sleep(2)` and hope is no longer needed.
- **Confidence matching without OpenCV.** A numpy implementation of normalized cross-correlation is built in, and OpenCV is used automatically when installed.
- **Windows on every platform**, not just Windows: list, find, activate, move, resize, minimize, maximize, close, and search for images inside a window.
- **Game-friendly input on Windows.** Keys are sent as scan codes, and `move_by(..., raw=True)` sends raw relative mouse movement.
- **Correct coordinates on scaled displays.** Per-monitor DPI awareness on Windows, and Retina-aware screenshots on macOS, so `click(find(...))` lands where you expect.
- **Unicode typing** on every platform.
- **No compiled dependencies.** The core needs only numpy. Windows and X11 use `ctypes`; macOS uses pyobjc.

## Install

```bash
pip install ironkit
pip install "ironkit[vision]"
pip install "ironkit[pil]"
```

`vision` adds OpenCV for faster matching. `pil` adds Pillow for image formats other than PNG, which is built in.

## Quick start

```python
import ironkit as ik

ik.move_to(500, 300, duration=0.4, ease=ik.ease.out_quad)
ik.click()
ik.write("Hello from ironkit!\n")
ik.hotkey("ctrl", "s")

button = ik.find("save_button.png", confidence=0.9, timeout=5)
button.click()

win = ik.windows.get("Notepad", timeout=10)
win.activate().move_to(100, 100).resize_to(800, 600)
win.find("ok.png").click()

if ik.pixel(10, 10).matches("#ff0000", tolerance=20):
    ik.press(ik.Key.ESCAPE)
```

Anything with a position can be clicked: `ik.click(x, y)`, `ik.click(point)`, `ik.click(match)`, `ik.click(region)`, `ik.click(window)` or `ik.click("image.png")`.

## API overview

### Mouse (`ik.mouse`)

| Call | Notes |
| --- | --- |
| `ik.position()` / `ik.mouse.position` | Current cursor `Point` |
| `move_to(x, y, duration=, ease=)` | Also accepts a point, region, match, window or image path |
| `move_by(dx, dy, duration=, ease=, raw=False)` | `raw=True` sends relative motion that games read |
| `drag_to(...)`, `drag_by(...)` | `button=` defaults to left |
| `click(x, y, clicks=, interval=, button=)` | `left_click`, `right_click`, `middle_click`, `double_click`, `triple_click` |
| `mouse_down()`, `mouse_up()`, `with ik.mouse.hold():` | |
| `scroll(amount)`, `hscroll(amount)` | Positive scrolls up or right |

Buttons: `ik.Button.LEFT`, `MIDDLE`, `RIGHT`, `PRIMARY`, `SECONDARY` (the last two respect swapped mouse buttons), or plain strings.

### Keyboard (`ik.keyboard`)

| Call | Notes |
| --- | --- |
| `write("text", interval=)` | Types any Unicode text; `\n` and `\t` press Enter and Tab |
| `write(["a", "left", "enter"])` | A list is pressed key by key |
| `press("enter")`, `press("a", "b", times=3)` | |
| `hotkey("ctrl", "shift", "esc")` | Pressed in order, released in reverse |
| `key_down(key)`, `key_up(key)`, `with ik.hold("shift"):` | Keys are always released, even on errors |
| `ik.keyboard.is_valid(key)`, `ik.keyboard.needs_shift(char)` | |

Keys are `ik.Key` members or their string names (`"enter"`, `"f5"`, `"num7"`, `"volumeup"`…). PyAutoGUI's aliases such as `"return"`, `"esc"`, `"pgdn"` and `"prtsc"` work too.

### Screen and images

| Call | Notes |
| --- | --- |
| `ik.screen.size`, `.region`, `.scale`, `.contains(x, y)` | Primary monitor |
| `ik.screens()`, `ik.desktop()` | Every monitor, and the combined virtual desktop |
| `screenshot(region=, path=)` | Returns an `Image` |
| `pixel(x, y)`, `pixel_matches(x, y, color, tolerance=)` | |
| `find(image, confidence=, grayscale=, region=, near=, timeout=)` | Returns a `Match` or raises `ImageNotFoundError` |
| `find_all(...)`, `find_or_none(...)`, `exists(...)`, `wait_gone(...)` | |
| `ik.screen.highlight(region, path=)` | Screenshot with the region outlined |

An `Image` remembers where it was captured, so `Image.pixel`, `Image.crop` and the regions of the matches it returns all use screen coordinates. Images load from PNG with no extra dependencies, or from any format when Pillow or OpenCV is installed. They convert to and from numpy (`to_numpy()`) and Pillow (`to_pil()`, `Image.from_pil()`).

A `Match` has `.region`, `.center`, `.confidence`, `.click()`, `.double_click()`, `.right_click()` and `.move_to()`.

### Windows (`ik.windows` and `ik.Window`)

| Call | Notes |
| --- | --- |
| `windows.all()`, `windows.titles()` | Top-level windows, front to back |
| `windows.active()`, `windows.active_title()` | |
| `windows.find(title, exact=False, pid=)` | Substring (case-insensitive), exact, or `re.compile(...)` |
| `windows.get(title, timeout=)` | Waits for the window, or raises `WindowNotFoundError` |
| `windows.at(x, y)` | Windows under a point |

A `Window` has:

- **Properties:** `title`, `region`, `left`, `top`, `width`, `height`, `size`, `center`, `pid`, `is_active`, `is_minimized`, `is_maximized`, `is_visible` and `is_open`.
- **Chainable methods:** `activate()`, `minimize()`, `maximize()`, `restore()`, `show()`, `hide()`, `move_to()`, `move_by()`, `resize_to()` and `resize_by()`.
- **Other methods:** `close()`, `point(x, y)` (converts window-relative coordinates to screen coordinates), `screenshot()`, `pixel(x, y)` (window-relative), `find()`, `find_all()`, `exists()` and `wait_gone()`.

### Dialogs (`ik.dialogs`)

`alert(text)`, `confirm(text, buttons=)`, `prompt(text, default=)` and `password(text, mask="*")`. They need Tk, which most Python installs include.

### Settings (`ik.config`)

| Setting | Default | Meaning |
| --- | --- | --- |
| `pause` | `0.1` | Seconds to wait after every mouse or keyboard call |
| `failsafe` | `True` | Raise `FailSafeError` when the cursor sits on a fail-safe point |
| `failsafe_points` | `[(0, 0)]` | Move the mouse to the top-left corner to abort a runaway script |
| `confidence` | `0.999` | Default match threshold |
| `find_interval` | `0.1` | Seconds between retries while waiting for an image or window |
| `minimum_duration` | `0.1` | Moves shorter than this happen instantly |
| `minimum_sleep` | `0.01` | Step size of animated moves |
| `log_screenshots`, `log_screenshots_dir`, `log_screenshots_limit` | off, `.`, `10` | Save a screenshot before every action |

Change a setting for one block only with `with ik.config.override(pause=0, failsafe=False): ...`.

### Utilities

- **Timing:** `ik.sleep(seconds)`, `ik.countdown(seconds)`
- **Mouse inspection:** `ik.inspect()` prints the live cursor position and color in the terminal; `ik.inspector()` opens the same readout in a small window.
- **Diagnostics:** `ik.info()`, `ik.print_info()`, `ik.capabilities()`, `ik.version()`
- **Scripting:** `ik.run("g100,200 c w'hello' k'enter'")` runs PyAutoGUI's `run()` mini-language. It supports every command (`c l m r su sd ss g d k w h s p a f`).

## Coming from PyAutoGUI

| PyAutoGUI | ironkit |
| --- | --- |
| `moveTo`, `moveRel` / `move` | `move_to`, `move_by` |
| `dragTo`, `dragRel` / `drag` | `drag_to`, `drag_by` |
| `mouseDown`, `mouseUp` | `mouse_down`, `mouse_up` |
| `typewrite` / `write` | `write` |
| `keyDown`, `keyUp`, `hold` | `key_down`, `key_up`, `hold` |
| `hotkey` / `shortcut` | `hotkey` |
| `size`, `onScreen` | `screen.size`, `screen.contains` |
| `locateOnScreen`, `locateCenterOnScreen` | `find(...)`, `find(...).center` |
| `locateAllOnScreen`, `locate`, `locateAll` | `find_all`, `Image.find`, `Image.find_all` |
| `locateOnWindow`, `screenshotWindow` | `Window.find`, `Window.screenshot` |
| `pixelMatchesColor` | `pixel_matches` |
| `useImageNotFoundException(False)` | `find_or_none` / `exists` |
| `getActiveWindow`, `getWindowsWithTitle`, `getAllWindows`, `getAllTitles`, `getWindowsAt` | `windows.active`, `windows.find`, `windows.all`, `windows.titles`, `windows.at` |
| `PAUSE`, `FAILSAFE`, `FAILSAFE_POINTS` | `config.pause`, `config.failsafe`, `config.failsafe_points` |
| `easeInOutQuad`, … | `ease.in_out_quad`, … |
| `displayMousePosition`, `mouseInfo` | `inspect`, `inspector` |
| `getInfo`, `printInfo` | `info`, `print_info` |

## Platform support

| | Windows 10/11 | macOS | Linux (X11) | Linux (Wayland) |
| --- | --- | --- | --- | --- |
| Mouse and keyboard | ✅ | ✅ | ✅ | Use XWayland |
| Screenshots and image search | ✅ | ✅ | ✅ | Use XWayland |
| Windows | ✅ (with capture of covered windows) | ✅ | ✅ (EWMH, or no window manager) | Use XWayland |

**Coordinates** are the operating system's native cursor coordinates: physical pixels on Windows and X11, and points on macOS. Screenshots always come back at that same resolution, so a match's coordinates can be clicked directly on every platform.

**macOS** needs two permissions for the app that runs your script (Terminal, your IDE, or Python itself):
- Accessibility, for input and window control
- Screen Recording, for screenshots

ironkit raises `PermissionDeniedError` naming the exact setting when one is missing. macOS has no per-window hide, so `hide()` and `show()` act on the window's whole app.

**Windows** blocks input to programs running as administrator unless your script is elevated too. ironkit raises a clear `BackendError` when that happens.

**Linux** needs the X11 client libraries (`libX11`, `libXtst`, `libXrandr`), which come with any desktop install. Native Wayland support is planned. Until then, ironkit works with every app running under XWayland.

To pick a backend explicitly, set `IRONKIT_BACKEND=windows|macos|x11|fake`.

## Testing your own automation

`ironkit.backends.fake.FakeBackend` is an in-memory screen, mouse, keyboard and window manager. It lets you test automation scripts without touching the real desktop:

```python
import ironkit as ik
from ironkit.backends.fake import FakeBackend

fake = FakeBackend(1280, 720)
ik.set_backend(fake)
fake.paste(button_pixels, (300, 200))
my_script()
assert ("button", "left", True, 1) in fake.events
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check src tests
uv run pyright
xvfb-run -a uv run pytest -m live
```

Tests marked `live` drive the real display, so they are skipped by default.

## License

Public domain under [The Unlicense](LICENSE).
