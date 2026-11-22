"""Screen geometry shared by every platform: which edge the pointer is on, where it comes in on
the other computer, and where an injected move lands.

Monitors are rectangles (x, y, w, h) in one global space, top-left origin, y down. A side is
"left", "right", "top" or "bottom" of the whole arrangement; a point is on the right edge when
it's at the right of its own monitor and no monitor continues to the right at that height.
"""

SIDES = ("left", "right", "top", "bottom")
OPPOSITE = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}


class Screens(object):
    def __init__(self, rects):
        self.rects = [tuple(float(v) for v in r) for r in rects if r[2] > 0 and r[3] > 0] or [(0.0, 0.0, 1920.0, 1080.0)]
        xs = [r[0] for r in self.rects]
        ys = [r[1] for r in self.rects]
        self.left = min(xs)
        self.top = min(ys)
        self.right = max(r[0] + r[2] for r in self.rects)
        self.bottom = max(r[1] + r[3] for r in self.rects)

    def public(self):
        return [list(r) for r in self.rects]

    # ---- lookups -----------------------------------------------------------
    def at(self, x, y):
        for r in self.rects:
            if r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]:
                return r
        return None

    def nearest(self, x, y):
        best, bd = None, None
        for r in self.rects:
            cx = min(max(x, r[0]), r[0] + r[2] - 1)
            cy = min(max(y, r[1]), r[1] + r[3] - 1)
            d = (cx - x) ** 2 + (cy - y) ** 2
            if bd is None or d < bd:
                best, bd = r, d
        return best

    def clamp(self, x, y):
        r = self.at(x, y)
        if r:
            return x, y
        r = self.nearest(x, y)
        return min(max(x, r[0]), r[0] + r[2] - 1), min(max(y, r[1]), r[1] + r[3] - 1)

    # ---- edges -------------------------------------------------------------
    def on_edge(self, x, y, side, slack=1.0):
        """Is (x, y) on the outer `side` edge (nothing beyond it in that direction)?"""
        r = self.at(x, y) or self.nearest(x, y)
        if side == "right":
            return x >= r[0] + r[2] - slack and not self.at(r[0] + r[2] + 0.5, y)
        if side == "left":
            return x <= r[0] + slack - 1 and not self.at(r[0] - 0.5, y)
        if side == "bottom":
            return y >= r[1] + r[3] - slack and not self.at(x, r[1] + r[3] + 0.5)
        if side == "top":
            return y <= r[1] + slack - 1 and not self.at(x, r[1] - 0.5)
        return False

    def frac(self, x, y, side):
        """Where along the whole arrangement's `side` the point is, 0..1."""
        if side in ("left", "right"):
            return _f(y, self.top, self.bottom)
        return _f(x, self.left, self.right)

    def entry(self, side, frac, inset=1.0):
        """The point on our `side` edge at `frac` along it, `inset` pixels inside."""
        frac = min(max(frac, 0.0), 1.0)
        if side in ("left", "right"):
            y = self.top + frac * (self.bottom - self.top)
            rows = [r for r in self.rects if r[1] <= y < r[1] + r[3]]
            if not rows:  # a gap between monitors: use the nearest one
                r = self.nearest(self.left if side == "left" else self.right - 1, y)
                rows = [r]
                y = min(max(y, r[1]), r[1] + r[3] - 1)
            if side == "left":
                r = min(rows, key=lambda r: r[0])
                return r[0] + inset, y
            r = max(rows, key=lambda r: r[0] + r[2])
            return r[0] + r[2] - 1 - inset, y
        x = self.left + frac * (self.right - self.left)
        cols = [r for r in self.rects if r[0] <= x < r[0] + r[2]]
        if not cols:
            r = self.nearest(x, self.top if side == "top" else self.bottom - 1)
            cols = [r]
            x = min(max(x, r[0]), r[0] + r[2] - 1)
        if side == "top":
            r = min(cols, key=lambda r: r[1])
            return x, r[1] + inset
        r = max(cols, key=lambda r: r[1] + r[3])
        return x, r[1] + r[3] - 1 - inset

    def step(self, x, y, dx, dy, exits=()):
        """Move the pointer by (dx, dy) as the injecting side.

        Returns (nx, ny, exit_side, frac): exit_side is set when the move pushes past one of
        the `exits` edges (the side the driving computer is on), and the pointer should go home.
        """
        nx, ny = x + dx, y + dy
        if self.at(nx, ny):
            return nx, ny, None, 0.0
        for side in exits:
            pushing = (side == "right" and dx > 0) or (side == "left" and dx < 0) or \
                      (side == "bottom" and dy > 0) or (side == "top" and dy < 0)
            if not pushing:
                continue
            # Leaving through that edge: from it, or a big move that lands past it.
            ex, ey = self.clamp(nx, ny)
            if self.on_edge(x, y, side, slack=1.5) or self.on_edge(ex, ey, side, slack=1.5):
                fx, fy = (x, y) if self.on_edge(x, y, side, slack=1.5) else (ex, ey)
                return fx, fy, side, self.frac(fx, fy, side)
        # Off every monitor: stop at the edge of the one the pointer is on (it slides along it).
        r = self.at(x, y) or self.nearest(x, y)
        cx = min(max(nx, r[0]), r[0] + r[2] - 1)
        cy = min(max(ny, r[1]), r[1] + r[3] - 1)
        return cx, cy, None, 0.0


def _f(v, a, b):
    if b - a <= 1:
        return 0.5
    return min(max((v - a) / float(b - a - 1), 0.0), 1.0)


# ---- arrangement: other computers' screens placed around ours ----------------------
# A layout puts each screen of another computer somewhere in our coordinate space, like
# Windows display settings does with monitors: {"r": [x, y, w, h] in its own coordinates,
# "at": [x, y] where its top-left sits in ours}. Crossing an edge lands on whichever of its
# screens is really beyond that point, at the matching spot along the edge.

INSET = 2.0


def beyond(rects, x, y, side, tol=3.0):
    """The rect (x, y, w, h) just past our `side` edge at (x, y), or None."""
    best = None
    for r in rects:
        rx, ry, rw, rh = r[0], r[1], r[2], r[3]
        if side in ("left", "right"):
            if not (ry <= y < ry + rh):
                continue
            if side == "right" and rx >= x - tol:
                key = rx
            elif side == "left" and rx + rw <= x + 1 + tol:
                key = -(rx + rw)
            else:
                continue
        else:
            if not (rx <= x < rx + rw):
                continue
            if side == "bottom" and ry >= y - tol:
                key = ry
            elif side == "top" and ry + rh <= y + 1 + tol:
                key = -(ry + rh)
            else:
                continue
        if best is None or key < best[0]:
            best = (key, r)
    return best[1] if best else None


def landing(r, x, y, side):
    """Where a pointer leaving our `side` edge at (x, y) lands on rect r (same space), just inside."""
    rx, ry, rw, rh = r[0], r[1], r[2], r[3]
    cx = min(max(x, rx), rx + rw - 1)
    cy = min(max(y, ry), ry + rh - 1)
    if side == "right":
        return rx + INSET, cy
    if side == "left":
        return rx + rw - 1 - INSET, cy
    if side == "bottom":
        return cx, ry + INSET
    return cx, ry + rh - 1 - INSET


def placed(item):
    """A layout item -> its rect in our space."""
    return [float(item["at"][0]), float(item["at"][1]), float(item["r"][2]), float(item["r"][3])]


def to_remote(item, x, y):
    """A point in our space on a placed screen -> the same point in that computer's coordinates."""
    return [x - item["at"][0] + item["r"][0], y - item["at"][1] + item["r"][1]]


def default_layout(mine, theirs, side):
    """Their whole arrangement as one block on `side` of ours, centred along it."""
    me, them = Screens(mine), Screens(theirs)
    tw, th = them.right - them.left, them.bottom - them.top
    mw, mh = me.right - me.left, me.bottom - me.top
    if side == "left":
        ox, oy = me.left - tw, me.top + (mh - th) / 2.0
    elif side == "top":
        ox, oy = me.left + (mw - tw) / 2.0, me.top - th
    elif side == "bottom":
        ox, oy = me.left + (mw - tw) / 2.0, me.bottom
    else:
        ox, oy = me.right, me.top + (mh - th) / 2.0
    return [{"r": list(r), "at": [round(r[0] - them.left + ox), round(r[1] - them.top + oy)]} for r in them.rects]


def side_of(mine, items):
    """Which side of ours a layout mostly sits on (for computers that only know sides)."""
    me = Screens(mine)
    cx = sum(i["at"][0] + i["r"][2] / 2.0 for i in items) / max(1, len(items))
    cy = sum(i["at"][1] + i["r"][3] / 2.0 for i in items) / max(1, len(items))
    mx, my = (me.left + me.right) / 2.0, (me.top + me.bottom) / 2.0
    w, h = max(1.0, me.right - me.left), max(1.0, me.bottom - me.top)
    dx, dy = (cx - mx) / w, (cy - my) / h
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def inverse(mine, items):
    """Our screens placed in their space, from our layout of theirs: each of ours goes next to
    the screen of theirs it touches most."""
    out = []
    for m in Screens(mine).rects:
        best = None
        for it in items:
            t = placed(it)
            ox = min(m[0] + m[2], t[0] + t[2]) - max(m[0], t[0])
            oy = min(m[1] + m[3], t[1] + t[3]) - max(m[1], t[1])
            touch = max(ox, 0) + max(oy, 0) if (ox >= -3 or oy >= -3) else 0
            dist = abs((m[0] + m[2] / 2) - (t[0] + t[2] / 2)) + abs((m[1] + m[3] / 2) - (t[1] + t[3] / 2))
            score = (touch, -dist)
            if best is None or score > best[0]:
                best = (score, it, t)
        if best:
            it, t = best[1], best[2]
            out.append({"r": list(m), "at": [round(m[0] - t[0] + it["r"][0]), round(m[1] - t[1] + it["r"][1])]})
    return out
