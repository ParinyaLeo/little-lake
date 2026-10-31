"""Paint the island backgrounds for Little Lake as pixel art.

    pip install pillow
    python tools/make_backgrounds.py

Writes assets/frost.png, assets/desert.png, assets/forest.png and assets/secret.png (480x200 art pixels scaled 4x
with nearest-neighbour to 1920x800), a water mask per island in tools/water_masks/ (white = open water, used by
play_test.py to check that the bobber lands on water), and a contact sheet shots/backgrounds_contact.png.
Every scene uses fixed random seeds, so running the script again gives the same files.

Pillow is only used by this tool. The game itself just loads the PNG files.

Layout shared by every scene (art pixels): horizon at HZ, a wooden dock in the lower-left with a crate at CRATE
for the fisherman, and a mooring post at the dock's right end. The game draws the fisherman at FISHER
(top-left of his 28x36 grid, in image pixels, 6 image pixels per fisherman pixel): see SCENES in js/fishing.js.
"""
import math
import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
W, H, UP = 480, 200, 4
HZ = 88                                   # horizon: water from here down
FISHER = (58, 100)                        # fisherman grid origin in art pixels (x 4 = image pixels for js/fishing.js)
CRATE = (51, 131, 21, 23)                 # x, y, w, h of the seat under him
DECK = (0, 140, 107, 20)                  # deck top surface x, y, w, h; front beam below it
POSTS = [6, 40, 74]                       # posts under the deck
MOOR = (99, 128, 8)                       # mooring post: x, top, width
MAX_COLORS = 28
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
SKY, SHORE, WATER, SOLID = 0, 1, 2, 3     # what each pixel is (only WATER counts as water in the mask)


def hexc(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


class Art:
    def __init__(self, palette, seed):
        self.c = {k: hexc(v) for k, v in palette.items()}
        self.px = [[(0, 0, 0)] * W for _ in range(H)]
        self.kind = [[SKY] * W for _ in range(H)]
        self.r = random.Random(seed)

    def put(self, x, y, col, kind=SOLID):
        x, y = int(x), int(y)
        if 0 <= x < W and 0 <= y < H:
            self.px[y][x] = self.c[col] if isinstance(col, str) else col
            self.kind[y][x] = kind

    def rect(self, x, y, w, h, col, kind=SOLID):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                self.put(xx, yy, col, kind)

    def ellipse(self, cx, cy, rx, ry, col, kind=SOLID, top_only=False):
        for yy in range(int(cy - ry), int(cy + ry) + 1):
            for xx in range(int(cx - rx), int(cx + rx) + 1):
                if ((xx - cx) / max(rx, .5)) ** 2 + ((yy - cy) / max(ry, .5)) ** 2 <= 1 and (not top_only or yy <= cy):
                    self.put(xx, yy, col, kind)

    def dither(self, x, y, t, cols):
        """Ordered dithering between neighbouring colours of a gradient (t from 0 to 1)."""
        t = max(0.0, min(1.0, t)) * (len(cols) - 1)
        i = int(t)
        f = t - i
        return cols[min(i + 1, len(cols) - 1)] if f * 16 > BAYER[y % 4][x % 4] + .5 else cols[i]

    def save(self, name):
        img = Image.new("RGB", (W, H))
        img.putdata([p for row in self.px for p in row])
        n = len(img.getcolors(W * H))
        assert n <= MAX_COLORS, f"{name}: {n} colours (max {MAX_COLORS})"
        big = img.resize((W * UP, H * UP), Image.NEAREST).quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        out = ROOT / "assets" / f"{name}.png"
        big.save(out, optimize=True)
        mask = Image.new("1", (W, H))
        mask.putdata([1 if k == WATER else 0 for row in self.kind for k in row])
        (ROOT / "tools" / "water_masks").mkdir(exist_ok=True)
        mask.save(ROOT / "tools" / "water_masks" / f"{name}.png", optimize=True)
        print(f"{out.relative_to(ROOT)}: {n} colours, {out.stat().st_size // 1024} KB")
        return big.convert("RGB")


def waves(seed, terms):
    """Smooth 1-D noise: a sum of sines with random phases. terms = [(amplitude, frequency), ...]"""
    r = random.Random(seed)
    ph = [r.random() * 6.283 for _ in terms]
    return lambda x: sum(a * math.sin(x * f + p) for (a, f), p in zip(terms, ph))


# ---------------------------------------------------------------- layers shared by every scene
def sky(a, cols, bottom=HZ):
    for y in range(bottom):
        for x in range(W):
            a.put(x, y, a.dither(x, y, y / (bottom - 1), cols), SKY)


def cloud(a, cx, cy, size, light, mid, shade):
    r = a.r
    blobs = [(cx + r.uniform(-1, 1) * size * 1.3, cy + r.uniform(-.4, .2) * size, size * r.uniform(.45, .8)) for _ in range(6)]
    blobs.append((cx, cy, size * .8))
    inside = lambda x, y: y <= cy + size * .35 and any((x - bx) ** 2 + (y - by) ** 2 * 1.6 <= br * br for bx, by, br in blobs)
    for y in range(int(cy - size * 1.6), int(cy + size)):
        for x in range(int(cx - size * 2.6), int(cx + size * 2.6)):
            if inside(x, y):
                col = shade if y > cy + size * .12 else light if not inside(x, y - 2) else mid
                a.put(x, y, col, SKY)


def ridge(a, top, bottom, lit, dark, cap=None, cap_depth=0, kind=SHORE, x0=0, x1=W):
    """A hill or mountain line: top(x) gives the ridge height; slopes facing left are lit."""
    for x in range(x0, x1):
        t = int(top(x))
        face = lit if top(x - 1) > top(x + 1) - .3 else dark
        for y in range(max(t, 0), bottom):
            col = face
            if cap and y < t + cap_depth + (x * 7 % 3):
                col = cap
            a.put(x, y, col, kind)


def water(a, cols, ripple, sparkle, top=HZ):
    """Calm water: streaky horizontal runs, darker at the horizon, lighter toward the viewer."""
    r = a.r
    for y in range(top, H):
        t = (y - top) / (H - top - 1)
        x = 0
        while x < W:
            run = r.randint(3, 16)
            idx = max(0, min(len(cols) - 1, round(t * (len(cols) - 1) + r.uniform(-.7, .7))))
            for xx in range(x, min(W, x + run)):
                a.put(xx, y, cols[idx], WATER)
            x += run
    a.rect(0, top, W, 1, cols[0], WATER)


def reflect(a, cols_by_light, depth=24, top=HZ):
    """Soft reflections of the shore: whole horizontal streaks, every third row left open, thinning out with depth."""
    for d in range(depth):
        if d % 3 == 2:
            continue
        y = top + 1 + d
        src = top - 1 - int(d * 1.2)
        wob = round(math.sin(y * 1.7) * 1.5)
        for x in range(W):
            sx = x + wob
            if not (0 <= sx < W) or a.kind[src][sx] != SHORE:
                continue
            seg = (x + d * 5) // 7
            if (seg * 7 + d * 3) % 5 == 0 or (d > depth * .45 and (seg + d) % 3 == 0):
                continue
            p = a.px[src][sx]
            lum = .3 * p[0] + .59 * p[1] + .11 * p[2]
            a.put(x, y, cols_by_light[0] if lum < 90 else cols_by_light[1] if lum < 170 else cols_by_light[2], WATER)


def ripples(a, light, sparkle, n=260, top=HZ, avoid=None):
    r = a.r
    for _ in range(n):
        y = r.randint(top + 2, H - 1)
        ln = 2 + int((y - top) / (H - top) * 10 * r.uniform(.5, 1.2))
        x = r.randint(0, W - 1)
        if avoid and avoid(x, y):
            continue
        for xx in range(x, x + ln):
            if 0 <= xx < W and a.kind[y][xx] == WATER:
                a.put(xx, y, light, WATER)
        if ln > 5 and r.random() < .35:
            a.put(x + ln // 2, y, sparkle, WATER)


def underwater_rocks(a, col, spots):
    """Dark shapes under the clear water, like the harbour picture (solid middle, dithered edge)."""
    for cx, cy, rx, ry in spots:
        for y in range(int(cy - ry), int(cy + ry) + 1):
            for x in range(int(cx - rx), int(cx + rx) + 1):
                if not (0 <= x < W and 0 <= y < H) or a.kind[y][x] != WATER:
                    continue
                v = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 + .15 * math.sin(x * .5 + y)
                if v <= .65 or (v <= 1 and BAYER[y % 4][x % 4] < (1 - v) * 40):
                    a.put(x, y, col, WATER)


def dock(a, plank, plank2, seam, beam, light, post, post_dark, rope, deco=None):
    """Wooden dock in the lower-left with posts, a mooring post and a crate for the fisherman."""
    x0, y0, w, h = DECK
    for y in range(y0, y0 + h):
        row, ly = (y - y0) // 4, (y - y0) % 4             # boards 4 pixels deep, running left to right
        for x in range(x0, x0 + w):
            col = plank if row % 2 else plank2
            if ly == 3 or (x + row * 17) % 29 == 0:
                col = seam                                # gaps between boards and board ends
            elif ly == 0 and (x + row * 5) % 9:
                col = light if row % 2 else plank         # sunlit board edges
            a.put(x, y, col)
    a.rect(x0, y0, w, 1, light)
    a.rect(x0, y0 + h, w, 6, beam)
    for x in range(x0 + 5, x0 + w, 12):
        a.rect(x, y0 + h, 1, 6, seam)
    a.rect(x0, y0 + h + 5, w, 1, seam)
    for px in POSTS:                                    # posts under the deck, into the water
        a.rect(px, y0 + h + 6, 6, H - y0 - h - 6, post)
        a.rect(px, y0 + h + 6, 1, H - y0 - h - 6, light)
        a.rect(px + 5, y0 + h + 6, 1, H - y0 - h - 6, post_dark)
        a.rect(px - 2, H - 6, 10, 1, light, WATER)      # little ripple where it meets the water
    mx, mt, mw = MOOR                                   # mooring post at the end of the dock
    a.rect(mx, mt, mw, H - mt, post)
    a.rect(mx, mt, 1, H - mt, light)
    a.rect(mx + mw - 2, mt, 2, H - mt, post_dark)
    a.rect(mx, mt, mw, 2, light)
    a.rect(mx + 1, mt + 1, mw - 2, 1, plank)
    for ry in (mt + 20, mt + 23):
        a.rect(mx - 1, ry, mw + 2, 2, rope)
        a.rect(mx - 1, ry + 1, mw + 2, 1, plank2)
    a.rect(mx - 3, H - 5, mw + 6, 1, light, WATER)
    cx, cy, cw, ch = CRATE                              # the crate he sits on
    a.rect(cx, cy, cw, ch, plank2)
    a.rect(cx, cy, cw, 3, light)
    a.rect(cx, cy + 3, cw, 1, seam)
    for yy in range(cy + 9, cy + ch, 6):
        a.rect(cx, yy, cw, 1, seam)
    a.rect(cx, cy, 1, ch, seam)
    a.rect(cx + cw - 1, cy, 1, ch, seam)
    a.rect(cx + cw // 2 - 1, cy + 5, 3, 3, rope)
    if deco:
        deco(a)


# ---------------------------------------------------------------- small hand-made shapes
def pine(a, x, base, height, dark, mid, snow=None, kind=SHORE):
    tiers = max(3, int(height / 6))
    for i in range(tiers):
        ty = base - height + i * height / tiers
        wd = 2 + (i + 1) * height / tiers * .45
        for yy in range(int(ty), int(ty + height / tiers + 2)):
            k = (yy - ty) / (height / tiers + 2)
            half = wd * (.35 + .65 * k)
            for xx in range(int(x - half), int(x + half) + 1):
                col = mid if xx < x else dark
                if snow and yy < ty + 1.5 + (xx % 3 == 0):
                    col = snow
                a.put(xx, yy, col, kind)
    a.rect(x - 1, base, 2, 2, dark, kind)


def round_tree(a, x, base, size, dark, mid, light, trunk, kind=SHORE):
    a.rect(x - 1, base - size * .6, 2, size * .6, trunk, kind)
    for (dx, dy, rr) in ((0, -size * 1.1, size * .55), (-size * .4, -size * .8, size * .45), (size * .4, -size * .8, size * .45)):
        for yy in range(int(base + dy - rr), int(base + dy + rr) + 1):
            for xx in range(int(x + dx - rr), int(x + dx + rr) + 1):
                if (xx - x - dx) ** 2 + (yy - base - dy) ** 2 <= rr * rr:
                    rel = (xx - x - dx) + (yy - base - dy)
                    a.put(xx, yy, light if rel < -rr * .7 else mid if rel < rr * .3 else dark, kind)


def palm(a, x, base, height, lean, trunk, trunk2, frond, frond2, kind=SHORE):
    tx, ty = x, base
    for i in range(int(height)):
        k = i / height
        tx = x + lean * k * k
        ty = base - i
        a.rect(tx - 1, ty, 3, 1, trunk if i % 3 else trunk2, kind)
    for ang in (-160, -130, -95, -60, -25, 10, 200):
        rad = math.radians(ang)
        ln = height * .55
        for j in range(int(ln)):
            fx = tx + math.cos(rad) * j
            fy = ty + math.sin(rad) * j * .6 + (j / ln) ** 2 * ln * .45
            a.rect(fx, fy, 2, 2 if j < ln * .7 else 1, frond if j % 4 else frond2, kind)
    a.rect(tx - 1, ty, 3, 3, trunk2, kind)


def cactus(a, x, base, height, col, dark, light, kind=SHORE):
    a.rect(x - 2, base - height, 5, height, col, kind)
    a.rect(x - 2, base - height, 1, height, light, kind)
    a.rect(x + 2, base - height, 1, height, dark, kind)
    a.rect(x - 1, base - height - 1, 3, 1, col, kind)
    for side, hy, hh in ((-1, .55, .35), (1, .45, .3)):
        ax = x + side * 5
        a.rect(min(x, ax), base - height * hy, 5, 3, col, kind)
        a.rect(ax - 1, base - height * hy - height * hh, 3, height * hh, col, kind)
        a.rect(ax - 1, base - height * hy - height * hh, 1, height * hh, light, kind)


def rock(a, cx, cy, rx, ry, light, mid, dark, kind=SOLID, waterline=None):
    for y in range(int(cy - ry), int(cy + ry) + 1):
        for x in range(int(cx - rx), int(cx + rx) + 1):
            dx, dy = (x - cx) / rx, (y - cy) / ry
            if dx * dx + dy * dy <= 1 and y <= cy + ry * .4:
                col = light if dx + dy < -.6 else mid if dx + dy < .4 else dark
                a.put(x, y, col, kind)
    if waterline:
        a.rect(cx - rx - 1, cy + ry * .4 + 1, rx * 2 + 3, 1, waterline, WATER)


def floe(a, cx, cy, wd, top, side, shade):
    """Flat ice floe: snowy top, blue-white side, dark waterline."""
    for y in range(3):
        a.rect(cx - wd / 2 + (2 - y), cy + y, wd - (2 - y) * 2, 1, top)
    a.rect(cx - wd / 2, cy + 3, wd, 2, side)
    a.rect(cx - wd / 2 + 1, cy + 5, wd - 2, 1, shade, WATER)


# ---------------------------------------------------------------- scenes
def frost():
    a = Art({
        "s0": "#6fa9e2", "s1": "#86b9ea", "s2": "#a0caf0", "s3": "#bcdbf5", "s4": "#d8ebfa",
        "white": "#ffffff", "snow": "#e6f1fb", "snowsh": "#c3d7ec",
        "mlit": "#a9c3de", "mdark": "#7f9dc0",
        "pine": "#1f4a44", "pine2": "#2f6758",
        "w0": "#1f6f9e", "w1": "#2585b0", "w2": "#2f9fc4", "w3": "#3fbad3", "w4": "#5fd0de",
        "rip": "#a8eaf4", "rdark": "#1d5f72", "rmid": "#5c9ec0", "rlight": "#bfe2f2",
        "plank": "#9a7a5c", "plank2": "#86684d", "seam": "#4e3a2a", "beam": "#6b5038",
    }, seed=11)
    sky(a, ["s0", "s1", "s2", "s3", "s4"])
    for cx, cy, s in ((60, 22, 9), (210, 14, 7), (400, 26, 8)):
        cloud(a, cx, cy, s, "white", "snow", "snowsh")
    peaks = [(-10, 44), (60, 34), (135, 46), (215, 28), (300, 16), (372, 36), (440, 24), (500, 40)]
    jag = waves(1, [(1.5, .4), (1, .9)])
    for x in range(W):                                   # snowy mountains: lit on the left of each peak
        top, px, py = min((py + abs(x - px) * .75 + jag(x), px, py) for px, py in peaks)
        for y in range(int(top), HZ):
            snow = y < py + 10 + 3 * math.sin(x * .7) and y < top + 9
            a.put(x, y, ("white" if x <= px else "snowsh") if snow else ("mlit" if x <= px else "mdark"), SHORE)
    hill = waves(2, [(4, .03), (2, .09)])
    ridge(a, lambda x: 74 + hill(x), HZ, "snow", "snowsh")
    r = random.Random(3)
    x = 120
    while x < W:
        pine(a, x, HZ - 2 + r.randint(0, 2), r.randint(12, 26), "pine", "pine2", snow="white")
        x += r.randint(7, 15)
    for x in range(0, 110, 9):
        pine(a, x + r.randint(0, 3), HZ - 3, r.randint(8, 14), "pine", "pine2", snow="white")
    a.rect(0, HZ - 2, W, 2, "snow", SHORE)
    water(a, ["w0", "w1", "w2", "w3", "w4"], "rip", "white")
    reflect(a, ["rdark", "rmid", "w4"])
    underwater_rocks(a, "w1", [(250, 190, 26, 6), (420, 186, 34, 8), (330, 168, 18, 4)])
    ripples(a, "rip", "white")
    for cx, cy, wd in ((370, 104, 34), (452, 128, 24), (318, 176, 20), (200, 112, 16), (470, 170, 30)):
        floe(a, cx, cy, wd, "white", "snowsh", "rdark")

    def snowy(a):
        x0, y0, w, h = DECK
        for x in range(x0, x0 + w):
            depth = 2 + (x * 7 % 5 == 0) + (x % 11 == 0)
            a.rect(x, y0, 1, depth, "white" if x % 6 else "snow")
            if x % 13 == 3:
                a.rect(x, y0 + h, 1, 3, "white")           # drips on the beam
        for px in POSTS:
            a.rect(px - 1, y0 + h + 6, 8, 2, "white")
        mx, mt, mw = MOOR
        a.rect(mx - 1, mt - 2, mw + 2, 3, "white")
        a.rect(CRATE[0], CRATE[1] - 1, CRATE[2], 3, "white")
    dock(a, "plank", "plank2", "seam", "beam", "snowsh", "plank2", "seam", "mdark", snowy)
    return a


def desert():
    a = Art({
        "s0": "#ff9f45", "s1": "#ffb658", "s2": "#ffcb72", "s3": "#ffdd94", "s4": "#ffedbd",
        "sun": "#fff7d6", "sunring": "#ffe28a",
        "dune": "#eeb86c", "dune2": "#d99a52", "cliff": "#e8803f", "cliff2": "#b85a2c", "strata": "#f7a35f",
        "sand": "#f6d692", "trunk": "#8a5a2e", "trunk2": "#5f3c1d", "frond": "#3f9a3e", "frond2": "#2b6e2f",
        "w0": "#13849a", "w1": "#1b9fae", "w2": "#26b8bd", "w3": "#3dd1c9", "w4": "#6ee6d6",
        "rip": "#b6fff2", "white": "#ffffff",
        "plank": "#c79c68", "plank2": "#ad8452", "seam": "#5d4027",
    }, seed=21)
    sky(a, ["s0", "s1", "s2", "s3", "s4"])
    a.ellipse(380, 32, 19, 19, "sunring", SKY)
    a.ellipse(380, 32, 15, 15, "sun", SKY)
    for cx, cy, s in ((90, 26, 7), (250, 16, 6)):
        cloud(a, cx, cy, s, "sun", "s4", "s3")
    dn = waves(4, [(6, .018), (3, .05)])
    ridge(a, lambda x: 66 + dn(x), HZ, "dune", "dune2")
    for x in range(300, W):                              # sandstone mesa with stripes
        t = 34 + 5 * math.sin(x * .07) + (max(0, 330 - x) * 1.4) + (3 if x % 17 < 2 else 0)
        for y in range(int(t), HZ):
            col = "cliff" if (x // 6) % 4 else "cliff2"
            if (y - int(t)) % 11 in (3, 4):
                col = "strata"
            if x > 300 and math.sin(x * .07) > .6 and col == "cliff":
                col = "cliff2"
            a.put(x, y, col, SHORE)
    near = waves(5, [(3, .04), (1.5, .11)])
    ridge(a, lambda x: 80 + near(x), HZ, "sand", "dune", x1=310)
    a.rect(0, HZ - 3, W, 3, "sand", SHORE)
    r = random.Random(6)
    for x, ht, ln in ((150, 26, 4), (176, 20, -3), (262, 30, 5), (420, 24, -4)):
        palm(a, x, HZ - 2, ht, ln, "trunk", "trunk2", "frond", "frond2")
    for x, ht in ((120, 12), (215, 15), (240, 9), (350, 13)):
        cactus(a, x, HZ - 1, ht, "frond", "frond2", "w4")
    water(a, ["w0", "w1", "w2", "w3", "w4"], "rip", "white")
    reflect(a, ["w0", "w0", "w4"])
    underwater_rocks(a, "w2", [(260, 188, 30, 6), (410, 180, 26, 6)])
    ripples(a, "rip", "white")
    for cx, cy, rx, ry in ((448, 150, 18, 12), (472, 162, 12, 10), (360, 110, 9, 5)):
        rock(a, cx, cy, rx, ry, "strata", "cliff", "cliff2", waterline="rip")

    def weathered(a):
        x0, y0, w, h = DECK
        for x in range(3, w, 17):
            a.rect(x, y0 + 4 + x % 5, 3, 1, "sand")              # sand blown onto the planks
    dock(a, "plank", "plank2", "seam", "trunk", "sand", "plank2", "trunk2", "dune2", weathered)
    return a


def forest():
    a = Art({
        "s0": "#3fa7e6", "s1": "#5ab8ec", "s2": "#7ccaf0", "s3": "#a4dcf5", "s4": "#cdeefa",
        "white": "#ffffff", "beam": "#e9f8ff",
        "hill": "#5f9f8e", "hill2": "#4a8a7a",
        "t0": "#16492b", "t1": "#256b38", "t2": "#3b8a42", "t3": "#62b04c",
        "rock": "#7a8a86", "rock2": "#535f5e", "moss": "#79b84a",
        "w0": "#0f5260", "w1": "#156a74", "w2": "#1d8488", "w3": "#2a9e98", "w4": "#47b8a6",
        "rip": "#9be6d6",
        "plank": "#8c6a46", "plank2": "#74563a", "seam": "#3c2a1b", "fall": "#bfe9f6",
    }, seed=31)
    sky(a, ["s0", "s1", "s2", "s3", "s4"])
    for x0, bw in ((20, 16), (110, 10)):                  # soft sunbeams from the top-left, fading out
        for y in range(0, 64):
            for x in range(x0 + y // 2, x0 + y // 2 + bw):
                if 0 <= x < W and BAYER[y % 4][x % 4] < 3.5 * (1 - y / 64) ** 2 + .2:
                    a.put(x, y, "beam", SKY)
    for cx, cy, s in ((300, 18, 8), (440, 30, 6)):
        cloud(a, cx, cy, s, "white", "s4", "s3")
    hl = waves(7, [(8, .02), (4, .06)])
    ridge(a, lambda x: 46 + hl(x), HZ, "hill", "hill2")
    for x in range(374, 428):                             # rocky cliff with a small waterfall
        t = 34 + max(0, abs(x - 400) - 18) * 1.4 + (2 if x % 7 < 3 else 0)
        for y in range(int(t), HZ):
            a.put(x, y, "rock2" if x > 404 or (y + x // 2) % 9 == 0 else "rock", SHORE)
        a.rect(x, t, 1, 2 + (x % 3 == 0), "moss", SHORE)
    for y in range(36, HZ - 2):
        for x in range(396, 404):
            a.put(x, y, "white" if (x * 3 + y) % 5 == 0 or x in (396, 403) else "fall", SHORE)
    r = random.Random(8)
    for layer, (base, size, cols) in enumerate(((HZ - 18, 9, ("t1", "t2", "t3")), (HZ - 8, 11, ("t0", "t1", "t2")), (HZ - 1, 8, ("t0", "t1", "t3")))):
        x = r.randint(-6, 4)
        while x < W:
            if not (380 < x < 420 and layer < 2):
                if r.random() < .5:
                    pine(a, x, base + r.randint(-2, 2), size * 2.6 + r.randint(-3, 4), cols[0], cols[1])
                else:
                    round_tree(a, x, base + r.randint(-2, 2), size + r.randint(-2, 2), cols[0], cols[1], cols[2], "seam")
            x += r.randint(6, 12)
    a.rect(388, HZ - 3, 26, 3, "white", SHORE)            # foam at the bottom of the fall
    water(a, ["w0", "w1", "w2", "w3", "w4"], "rip", "white")
    reflect(a, ["w0", "t1", "w4"])
    underwater_rocks(a, "w1", [(240, 188, 28, 6), (430, 178, 24, 7)])
    ripples(a, "rip", "white")
    for cx, cy, rx, ry in ((452, 150, 16, 10), (474, 158, 10, 8), (345, 106, 8, 4)):
        rock(a, cx, cy, rx, ry, "rock", "rock2", "seam", waterline="rip")
        a.rect(cx - rx * .6, cy - ry + 1, rx * 1.1, 2, "moss")

    def mossy(a):
        x0, y0, w, h = DECK
        for x in range(0, w, 3):
            if (x * 7) % 5 < 3:
                a.rect(x, y0 + h, 3, 1 + (x % 2), "moss")
        for x in (12, 13, 14, 46, 47, 80, 81, 82):
            a.rect(x, y0 + 1, 1, 2, "t3")
        for px in POSTS:
            a.rect(px, y0 + h + 6, 6, 3, "moss")
        a.rect(MOOR[0], MOOR[1] + 2, MOOR[2], 2, "moss")
    dock(a, "plank", "plank2", "seam", "rock2", "t3", "plank2", "seam", "rock", mossy)
    return a


def secret():
    a = Art({
        "s0": "#0a0820", "s1": "#141034", "s2": "#1f1848", "s3": "#2c2160", "s4": "#3d2c78",
        "star": "#fffbe0", "star2": "#a99fe8", "moon": "#fff3c8", "moon2": "#e6d49a", "halo": "#4e3c92",
        "hill": "#1d1745", "tree": "#0d0b1f", "tree2": "#17132f", "ruin": "#3e3868", "ruin2": "#5e58a0",
        "w0": "#0b1e44", "w1": "#102b5c", "w2": "#163a72", "glow": "#2fc4d8", "glow2": "#8af4f0",
        "pur": "#7a4bc8", "pur2": "#b98af0", "fly": "#efff8a",
        "plank": "#4c3b3e", "plank2": "#3a2c30", "seam": "#1a1216", "moss": "#2f6a52",
    }, seed=41)
    sky(a, ["s0", "s1", "s2", "s3", "s4"])
    a.ellipse(360, 40, 27, 27, "halo", SKY)
    for y in range(13, 68):                               # dithered halo edge
        for x in range(330, 391):
            d = math.hypot(x - 360, y - 40)
            if 27 < d < 33 and (x + y) % 2 == 0:
                a.put(x, y, "halo", SKY)
    a.ellipse(360, 40, 20, 20, "moon", SKY)
    for cx, cy, rr in ((352, 34, 4), (368, 46, 3), (364, 30, 2), (350, 48, 2)):
        a.ellipse(cx, cy, rr, rr, "moon2", SKY)
    r = random.Random(42)
    for _ in range(120):
        x, y = r.randint(0, W - 1), r.randint(0, HZ - 25)
        if a.kind[y][x] == SKY and a.px[y][x] not in (a.c["moon"], a.c["halo"], a.c["moon2"]):
            a.put(x, y, "star" if r.random() < .4 else "star2", SKY)
    for x, y in ((60, 18), (190, 30), (280, 12), (440, 22)):
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            a.put(x + dx, y + dy, "star", SKY)
    hl = waves(9, [(9, .016), (4, .05)])
    ridge(a, lambda x: 58 + hl(x), HZ, "hill", "hill")
    for x, ht, wd in ((300, 22, 5), (312, 14, 5), (342, 26, 5), (330, 8, 4)):   # moonlit ruins
        a.rect(x, HZ - ht, wd, ht, "ruin", SHORE)
        a.rect(x, HZ - ht, 1, ht, "ruin2", SHORE)
        a.rect(x - 1, HZ - ht, wd + 2, 2, "ruin2", SHORE)
    for x in range(300, 348):                             # broken arch on the columns
        if x < 318 or x > 336:
            a.put(x, HZ - 24 - int(4 * math.sin((x - 300) / 48 * math.pi)), "ruin2", SHORE)
            a.put(x, HZ - 23 - int(4 * math.sin((x - 300) / 48 * math.pi)), "ruin", SHORE)
    x = -4
    while x < W:
        if not 292 < x < 352:
            pine(a, x, HZ - 1, r.randint(14, 30), "tree", "tree2")
        x += r.randint(6, 13)
    a.rect(0, HZ - 2, W, 2, "tree", SHORE)
    water(a, ["w0", "w1", "w2", "w1"], "glow", "glow2")
    for y in range(HZ, H):                                # glowing lake: cyan in the middle, purple at the edges
        for x in range(W):
            if a.kind[y][x] != WATER:
                continue
            dc = math.hypot((x - 250) / 150, (y - 150) / 45)
            dp = math.hypot((x - 430) / 90, (y - 120) / 30)
            th = BAYER[y % 4][x % 4] / 16
            if dc < .55 and th < (.55 - dc) * 1.4:
                a.put(x, y, "glow", WATER)
            elif dc < 1 and th < (1 - dc) * .5:
                a.put(x, y, "w2", WATER)
            elif dp < 1 and th < (1 - dp) * .7:
                a.put(x, y, "pur", WATER)
    for d in range(2, H - HZ - 4, 2):                     # moon reflection
        wd = 14 - d * .12
        off = round(math.sin(d * 1.3) * 2)
        a.rect(360 - wd / 2 + off, HZ + d, max(2, wd), 1, "moon2" if d % 4 else "moon", WATER)
    reflect(a, ["tree", "w0", "ruin"])
    ripples(a, "glow2", "pur2", n=180)
    for _ in range(40):                                   # fireflies over the shore and the water
        x, y = r.randint(110, W - 1), r.randint(HZ - 30, H - 10)
        a.put(x, y, "fly", a.kind[y][x] if a.kind[y][x] != SOLID else SOLID)
        if r.random() < .4:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                a.put(x + dx, y + dy, "pur2" if y > HZ else "halo", a.kind[y + dy][x + dx])
    for cx, cy, rx, ry in ((450, 150, 14, 10), (472, 160, 10, 8)):
        rock(a, cx, cy, rx, ry, "ruin2", "ruin", "hill", waterline="glow")

    def old(a):
        x0, y0, w, h = DECK
        for x in range(0, w, 4):
            if (x * 5) % 7 < 3:
                a.rect(x, y0 + h, 4, 2, "moss")
        a.rect(30, y0 + 6, 6, 1, "seam")                  # a broken plank
        a.rect(MOOR[0], MOOR[1] + 2, MOOR[2], 2, "moss")
        a.rect(16, y0 - 14, 3, 14, "plank2")              # little lantern post on the dock
        a.rect(14, y0 - 18, 7, 5, "seam")
        a.rect(15, y0 - 17, 5, 3, "fly")
    dock(a, "plank", "plank2", "seam", "seam", "ruin", "plank2", "seam", "ruin", old)
    return a


def main():
    sheets = []
    for name, paint in (("frost", frost), ("desert", desert), ("forest", forest), ("secret", secret)):
        sheets.append(paint().save(name))
    harbor = Image.open(ROOT / "assets" / "harbor.jpg").convert("RGB")
    thumbs = [harbor] + sheets
    tw = 480
    th = [round(t.height * tw / t.width) for t in thumbs]
    sheet = Image.new("RGB", (tw * len(thumbs) + 8 * (len(thumbs) + 1), max(th) + 16), (34, 34, 34))
    for i, t in enumerate(thumbs):
        sheet.paste(t.resize((tw, th[i]), Image.NEAREST), (8 + i * (tw + 8), 8))
    (ROOT / "shots").mkdir(exist_ok=True)
    sheet.save(ROOT / "shots" / "backgrounds_contact.png")
    print("shots/backgrounds_contact.png")


if __name__ == "__main__":
    main()
