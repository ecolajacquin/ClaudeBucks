"""Clawd bitmap based on the original uploaded mascot, not a generic robot.

The original orange/white silhouette was reduced to a 25x21, 1-bit bitmap.
Draws correctly at scale=1 (dashboard) and scale=2 (waiting/sleep).
"""
import random
from time import ticks_add, ticks_diff, ticks_ms

SPRITE_W = 25
SPRITE_H = 21

# 1-bit silhouette traced from the original uploaded Clawd image.
# Eye cutouts are NOT baked into this bitmap: animations draw both eyes below.
# This prevents black ghost pixels beside the right eye when it moves/blinks.
# Lower four rows keep four separate feet and three clear negative-space gaps.
_BODY = (
    '0000000000000000000000000',
    '0001111111111111111111000',
    '0001111111111111111111000',
    '0001111111111111111111000',
    '0001111111111111111111000',
    '0111111111111111111111110',
    '0111111111111111111111110',
    '0111111111111111111111110',
    '0111111111111111111111110',
    '0111111111111111111111110',
    '0111111111111111111111110',
    '0011111111111111111111100',
    '0001111111111111111111000',
    '0001111111111111111111000',
    '0001111111111111111111000',
    '0001111111111111111111000',
    '0001110011000000110011000',
    '0001110011000000110011000',
    '0001110011000000110011000',
    '0001110011000000110011000',
    '0000000000000000000000000',
)


# Sleep tuning: sleeping Clawd stays mostly still and keeps his eyes closed.
# Nap frequency is intentionally lower than before, but all awake antics remain.
FIRST_NAP_MIN_MS = 90_000
FIRST_NAP_MAX_MS = 180_000
NEXT_NAP_MIN_MS = 150_000
NEXT_NAP_MAX_MS = 300_000
NAP_MIN_MS = 15_000
NAP_MAX_MS = 30_000

# Deep-sleep interruptions should be rare, not part of the regular pose cycle.
SLEEP_TWITCH_MIN_MS = 75_000
SLEEP_TWITCH_MAX_MS = 180_000
SLEEP_PEEK_MIN_MS = 180_000
SLEEP_PEEK_MAX_MS = 360_000


class Clawd:
    def __init__(self):
        now = ticks_ms()
        self.sleeping = False
        self.forced_sleeping = False
        self.napping = False
        self.pose = 'idle'
        self.started = now
        self.duration = 750
        self.next_nap = ticks_add(
            now, random.randint(FIRST_NAP_MIN_MS, FIRST_NAP_MAX_MS)
        )
        self.nap_end = None
        self.next_twitch = ticks_add(
            now, random.randint(SLEEP_TWITCH_MIN_MS, SLEEP_TWITCH_MAX_MS)
        )
        self.next_peek = ticks_add(
            now, random.randint(SLEEP_PEEK_MIN_MS, SLEEP_PEEK_MAX_MS)
        )

    def set_sleeping(self, value, now=None):
        """Set deep sleep for disconnected/waiting screens.

        Passing False does NOT cancel a spontaneous connected-mode nap.
        """
        if now is None:
            now = ticks_ms()
        value = bool(value)
        if value == self.forced_sleeping:
            return

        self.forced_sleeping = value
        self.napping = False
        self.sleeping = value
        self.pose = 'doze' if value else 'wake'
        self.started = now
        self.duration = 700
        if value:
            # Reset the rare-event timers at the start of deep sleep.
            self.next_twitch = ticks_add(
                now, random.randint(SLEEP_TWITCH_MIN_MS, SLEEP_TWITCH_MAX_MS)
            )
            self.next_peek = ticks_add(
                now, random.randint(SLEEP_PEEK_MIN_MS, SLEEP_PEEK_MAX_MS)
            )
        if not value:
            self.next_nap = ticks_add(
                now, random.randint(FIRST_NAP_MIN_MS, FIRST_NAP_MAX_MS)
            )

    def update(self, now=None):
        if now is None:
            now = ticks_ms()

        # Occasionally nap even while connected. The caller must keep
        # polling USB; animation scheduling never sleeps or blocks.
        if not self.forced_sleeping:
            if self.napping:
                if ticks_diff(now, self.nap_end) >= 0:
                    self.napping = False
                    self.sleeping = False
                    self.pose = 'wake'
                    self.started = now
                    self.duration = 700
                    self.next_nap = ticks_add(
                        now, random.randint(NEXT_NAP_MIN_MS, NEXT_NAP_MAX_MS)
                    )
            elif ticks_diff(now, self.next_nap) >= 0:
                self.napping = True
                self.sleeping = True
                self.pose = 'doze'
                self.started = now
                self.duration = 900
                self.nap_end = ticks_add(
                    now, random.randint(NAP_MIN_MS, NAP_MAX_MS)
                )

        if ticks_diff(now, self.started) < self.duration:
            return
        if self.sleeping:
            if self.forced_sleeping and ticks_diff(now, self.next_peek) >= 0:
                # Briefly open his eyes only every few minutes in deep sleep.
                self.pose, self.duration = 'peek', 320
                self.next_peek = ticks_add(
                    now, random.randint(SLEEP_PEEK_MIN_MS, SLEEP_PEEK_MAX_MS)
                )
            elif self.forced_sleeping and ticks_diff(now, self.next_twitch) >= 0:
                # A one-frame twitch is also rare; never twitch in short naps.
                self.pose, self.duration = 'twitch', 180
                self.next_twitch = ticks_add(
                    now, random.randint(SLEEP_TWITCH_MIN_MS, SLEEP_TWITCH_MAX_MS)
                )
            else:
                # Long, calm poses. No rapid flickering or fake waking.
                self.pose, self.duration = random.choice((
                    ('sleep', 7000), ('sleep', 8500), ('breathe', 5500),
                    ('snore', 6500), ('dream', 7000), ('doze', 6500),
                ))
        else:
            self.pose, self.duration = random.choice((
                ('idle', 1200), ('idle', 800), ('blink', 160),
                ('hop', 280), ('dance_l', 250), ('dance_r', 250),
                ('look_l', 400), ('look_r', 400),
                ('heart', 900), ('spark', 650),
            ))
        self.started = now

    @staticmethod
    def _paint(fb, x, y, w, h, color=1):
        # Clamp rectangles: no off-screen negative coordinates.
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(128, int(x + w))
        y1 = min(64, int(y + h))
        if x1 > x0 and y1 > y0:
            fb.fill_rect(x0, y0, x1 - x0, y1 - y0, color)

    def draw(self, fb, x, y, scale=1, now=None):
        if now is None:
            now = ticks_ms()
        s = int(scale)
        x, y = int(x), int(y)
        elapsed = ticks_diff(now, self.started)
        p = self.pose
        if p == 'hop':
            y -= (2 if elapsed < 140 else 1) * s
        elif p in ('dance_l', 'twitch'):
            x -= s
        elif p == 'dance_r':
            x += s
        elif p == 'breathe' and (now // 2700) % 2:
            # Subtle 1-screen-pixel breathing, instead of moving the
            # whole enlarged sprite two pixels every 0.75 seconds.
            y += 1

        paint = self._paint
        # Draw original, recognizable silhouette using horizontal runs.
        for yy, bits in enumerate(_BODY):
            begin = -1
            for xx in range(SPRITE_W + 1):
                on = xx < SPRITE_W and bits[xx] == '1'
                if on and begin < 0:
                    begin = xx
                elif not on and begin >= 0:
                    paint(fb, x + begin*s, y + yy*s, (xx-begin)*s, s)
                    begin = -1

        # Both eyes are drawn identically over the SOLID body bitmap.
        # The old bitmap contained uneven eye holes (right eye had an
        # extra black pixel), which survived as a ghost when eyes moved.
        closed = (self.sleeping and p != 'peek') or p == 'blink'
        eye_x_positions = (6, 18)
        if closed:
            for eye_x in eye_x_positions:
                paint(fb, x + eye_x*s, y + 7*s, 2*s, s, 0)
        else:
            dx = -1 if p == 'look_l' else 1 if p == 'look_r' else 0
            for eye_x in eye_x_positions:
                paint(fb, x + (eye_x + dx)*s, y + 6*s, 2*s, 2*s, 0)

        # Little particle effects, bounded to the screen. Never draw off-edge.
        # At dashboard scale on the right, the left side has more room.
        ex = x - 9 if x > 80 else x + SPRITE_W*s + 3
        ey = y - 2
        if self.sleeping and p in ('sleep', 'snore', 'doze'):
            self._z(fb, ex, ey)
            if p == 'snore':
                self._z(fb, ex + (-8 if x > 80 else 8), ey - 8)
        elif self.sleeping and p == 'dream':
            paint(fb, ex, ey, 5, 5, 1)
            paint(fb, ex+1, ey+1, 3, 3, 0)
        elif not self.sleeping and p in ('heart', 'spark'):
            if p == 'spark':
                paint(fb, ex+2, ey, 1, 6)
                paint(fb, ex, ey+2, 5, 1)
            else:
                paint(fb, ex, ey, 2, 2)
                paint(fb, ex+3, ey, 2, 2)
                paint(fb, ex+1, ey+2, 3, 2)
                paint(fb, ex+2, ey+4, 1, 1)

    def _z(self, fb, x, y):
        for dx, dy, w in ((0,0,5),(3,1,1),(2,2,1),(1,3,1),(0,4,5)):
            self._paint(fb, x+dx, y+dy, w, 1)
