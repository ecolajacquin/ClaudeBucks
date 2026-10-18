"""Claude Bucks Pico display: JSON over USB, animated 128x64 OLED."""
import json
import math
import select
import sys
from time import sleep_ms, ticks_diff, ticks_ms

from oled import OLED_1inch3
from sprite import Clawd, SPRITE_W, SPRITE_H

DISCONNECT_TIMEOUT_MS = 15_000
FRAME_INTERVAL_MS = 180
MAX_MESSAGE_LENGTH = 256


oled = OLED_1inch3()
clawd = Clawd()
poller = select.poll()
poller.register(sys.stdin, select.POLLIN)

last_received = None
last_used = None
last_budget = None
last_status = "waiting"
input_buffer = ""


# A native-resolution lowercase cent sign: "c" with a stroke through it.
# MicroPython's built-in text font is ASCII-only, so this is pixel-drawn.
_CENT_GLYPH = (
    "0001000",
    "0001000",
    "0011110",
    "0101000",
    "0101000",
    "0101000",
    "0101000",
    "0011110",
    "0001000",
)


def currency(x, y):
    """Draw a 7x9 lowercase cent sign (¢)."""
    for yy, row in enumerate(_CENT_GLYPH):
        for xx, value in enumerate(row):
            if value == "1":
                oled.pixel(x + xx, y + yy, 1)


def amount(x, y, value):
    # 7px cent sign + 3px gap + 8px/character font.
    # Even ¢1000.00 stays to the left of the dashboard Clawd.
    currency(x, y)
    oled.text("{:.2f}".format(value), x + 10, y, 1)


def header(status):
    oled.text("CLAUDE BUCKS", 2, 2, 1)
    oled.hline(0, 13, 128, 1)
    oled.text({"ok": "+", "stale": "~", "error": "!"}.get(status, ""), 119, 2, 1)


def draw_dashboard(now):
    used = last_used
    budget = last_budget
    remaining = max(0.0, budget-used)
    percent = min(100, max(0, used*100.0/budget))
    oled.fill(0)
    header(last_status)
    oled.rect(2, 20, 76, 11, 1)
    width = round(72*percent/100)
    if width:
        oled.fill_rect(4, 22, width, 7, 1)
    oled.text("{:.0f}%".format(percent), 81, 21, 1)
    clawd.draw(oled, 102, 32, scale=1, now=now)
    oled.text("USED", 2, 38, 1)
    amount(34, 38, used)
    oled.text("LEFT", 2, 51, 1)
    amount(34, 51, remaining)
    oled.show()


def draw_companion(now):
    oled.fill(0)
    # No headings: just an enlarged, centered Clawd and his effects.
    scale = 2
    x = (128 - SPRITE_W*scale)//2
    y = (64 - SPRITE_H*scale)//2 + 3
    clawd.draw(oled, x, y, scale=scale, now=now)
    oled.show()


def parse_message(message):
    global last_received, last_used, last_budget, last_status
    try:
        data = json.loads(message)
        used = float(data["used"])
        budget = float(data["budget"])
        status = data.get("status", "ok")
        if not math.isfinite(used) or not math.isfinite(budget):
            raise ValueError("nonfinite number")
        if used < 0 or budget <= 0:
            raise ValueError("invalid usage or budget")
        if status not in ("ok", "stale", "error"):
            status = "error"
        last_used = used
        last_budget = budget
        last_status = status
        last_received = ticks_ms()
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        print("Invalid data:", exc)


def main():
    global input_buffer
    previous_frame = ticks_ms() - FRAME_INTERVAL_MS
    previous_mode = None
    while True:
        now = ticks_ms()
        if poller.poll(0):
            char = sys.stdin.read(1)
            if char == "\n":
                if input_buffer.strip():
                    parse_message(input_buffer.strip())
                input_buffer = ""
            elif char and char != "\r":
                input_buffer += char
                if len(input_buffer) > MAX_MESSAGE_LENGTH:
                    input_buffer = ""

        connected = (last_received is not None and
                     ticks_diff(now, last_received) < DISCONNECT_TIMEOUT_MS)
        mode = "dashboard" if connected else "sleep" if last_received is not None else "waiting"
        clawd.set_sleeping(mode != "dashboard", now)
        clawd.update(now)

        if (mode != previous_mode or
                ticks_diff(now, previous_frame) >= FRAME_INTERVAL_MS):
            previous_mode = mode
            previous_frame = now
            if mode == "dashboard":
                draw_dashboard(now)
            else:
                draw_companion(now)
        sleep_ms(25)


main()
