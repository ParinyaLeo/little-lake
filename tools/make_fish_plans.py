"""Tool only (never loaded by the game): draws the 9 creature body plans used by drawFish() in js/state.js.

Each plan is a 24x16 grid of palette letters:  . empty   O outline   B body   D dark back   L light belly
F fin / tentacle   G fin edge   S accent (the fish's `stripe` colour)   W white shine   (pupils are O).
`python tools/make_fish_plans.py`          prints the JavaScript `FISH_PLANS` table to paste into js/state.js
`python tools/make_fish_plans.py --write`  rewrites that table in js/state.js between the PLANS markers
Shapes are drawn in `main` (they get an automatic 1px outline) and `extra` (thin parts such as tentacles and legs, no outline).
"""
import math, re, sys
from pathlib import Path

W, H = 24, 16

class Plan:
    def __init__(self):
        self.main = {}; self.extra = {}
    def px(self, x, y, k, layer="main"):
        if 0 <= x < W and 0 <= y < H: (self.main if layer == "main" else self.extra)[(x, y)] = k
    def ell(self, cx, cy, rx, ry, k, layer="main", ymin=-99, ymax=99, xmin=-99, xmax=99):
        for y in range(H):
            for x in range(W):
                if ymin <= y <= ymax and xmin <= x <= xmax and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1: self.px(x, y, k, layer)
    def rect(self, x0, y0, x1, y1, k, layer="main"):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1): self.px(x, y, k, layer)
    def line(self, pts, k, layer="extra"):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(abs(x1 - x0), abs(y1 - y0), 1)
            for i in range(n + 1): self.px(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n), k, layer)
    def rows(self):
        g = [["."] * W for _ in range(H)]
        for (x, y), k in self.main.items(): g[y][x] = k
        for y in range(H):                                   # 1px outline around the main shapes (4-neighbours)
            for x in range(W):
                if g[y][x] == "." and any(0 <= x + dx < W and 0 <= y + dy < H and (x + dx, y + dy) in self.main for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))): g[y][x] = "O"
        for (x, y), k in self.extra.items(): g[y][x] = k
        return ["".join(r) for r in g]

def jellyfish():
    p = Plan()
    p.ell(11.5, 8, 8.5, 6.5, "B", ymax=7)                               # dome
    p.rect(3, 8, 20, 8, "L")                                           # bell margin
    for x in range(3, 21): p.px(x, 1, "D") if (x, 1) in p.main else None
    for x in range(5, 19): p.px(x, 2, "D") if (x, 2) in p.main else None
    p.px(7, 3, "W"); p.px(8, 3, "W"); p.px(7, 4, "W")
    for (x, y) in [(10, 5), (13, 5), (11, 6), (12, 6)]: p.px(x, y, "S")  # the four rings of a moon jelly
    for x in range(4, 20, 2): p.px(x, 9, "G", "extra")                  # scalloped skirt
    for x0, ln in [(5, 6), (8, 5), (15, 5), (18, 6)]:                   # thin wavy tentacles
        for i in range(ln): p.px(x0 + (i % 2), 10 + i, "F", "extra")
    for i in range(5):                                                  # frilly oral arms
        p.px(10, 9 + i, "L", "extra"); p.px(13, 9 + i, "L", "extra"); p.px(11 + (i % 2), 9 + i, "S", "extra")
    return p

def crab():
    p = Plan()
    p.ell(11.5, 9.5, 8, 4.5, "B")                                       # wide shell
    p.ell(11.5, 12.2, 7, 1.5, "L", ymin=11)                              # pale underside
    for x in range(5, 19):
        if (x, 6) in p.main and p.main[(x, 6)] == "B": p.px(x, 6, "D")
    for (x, y) in [(8, 8), (11, 7), (13, 8), (10, 10), (15, 10), (7, 10)]: p.px(x, y, "S")   # shell spots
    p.px(9, 6, "W"); p.px(10, 6, "W")
    for sx in (-1, 1):                                                  # raised claws: arm + pincer with a notch
        cx = 11.5 + sx * 9.5
        p.ell(cx, 4.5, 2.6, 2.6, "F"); p.px(round(cx), 2, ".", "main"); p.main.pop((round(cx), 2), None)
        p.px(round(cx), 3, "G")
        a = 11.5 + sx * 7.5
        p.line([(round(cx - sx * 1), 7), (round(a), 9)], "F", "main")
        p.px(round(cx), 6, "F"); p.px(round(cx), 7, "F")
    for ex in (9, 14):                                                  # eye stalks
        p.px(ex, 4, "B"); p.px(ex, 5, "B"); p.px(ex, 3, "W"); p.px(ex, 4, "B")
    for sx in (-1, 1):                                                  # three legs each side
        for i, (dy, dx) in enumerate([(0, 0), (1, 1), (2, 2)]):
            x = round(11.5 + sx * (8.5 + dx)); y = 11 + dy + i
            p.px(x, y, "F", "extra"); p.px(x + sx, y + 1, "F", "extra") if x + sx < 23 else None
    return p

def seahorse():
    p = Plan()
    p.ell(9, 4, 3.2, 2.8, "B")                                          # head
    p.rect(11, 4, 16, 5, "B"); p.rect(16, 4, 16, 5, "L")                # snout
    for x in (6, 7, 8): p.px(x, 1, "F")                                  # crest
    p.px(5, 2, "F"); p.px(5, 3, "F")
    p.px(8, 3, "W"); p.px(9, 3, "O")                                     # eye
    p.ell(9.5, 8.8, 3.7, 3.4, "B", ymin=6, ymax=11)                      # chest
    p.ell(10.4, 9, 2, 2.7, "L", ymin=6, ymax=11)                         # belly
    for (x, y) in [(8, 12), (9, 12), (10, 12), (8, 13), (9, 13), (8, 14), (9, 14), (10, 14), (11, 14), (12, 14), (12, 13), (13, 13), (12, 12), (13, 12)]:
        p.px(x, y, "B")                                                  # tail: waist, then curls forward round a hole
    p.px(13, 12, "L")
    for y in (7, 9, 11): p.px(9, y, "S"); p.px(10, y, "S"); p.px(11, y, "S")   # belly rings
    for y in range(6, 11): p.px(5, y, "F", "extra"); p.px(4, y + 1, "F", "extra")   # dorsal fin on the back
    return p

def shark():
    p = Plan()
    for x in range(4, 23):
        t = (x - 4) / 18
        half = 1 + 2.7 * (t / .45) if t <= .45 else 3.7 * math.sqrt(max(0, 1 - ((t - .45) / .55) ** 2))
        half = max(half, .5)
        for y in range(H):
            if abs(y - 8) <= half + .01:
                dy = y - 8
                p.px(x, y, "L" if dy >= half * .35 else ("D" if dy <= -half * .45 else "B"))
    for k in range(4):                                                  # forked tail
        p.px(3 - k // 2, 8 - 1 - k, "F"); p.px(4 - k // 2, 8 - k, "F") if k else None
    p.line([(4, 7), (1, 3)], "F", "main"); p.line([(5, 7), (2, 3)], "F", "main"); p.line([(1, 3), (4, 3)], "F", "main")
    p.line([(4, 9), (1, 13)], "F", "main"); p.line([(5, 9), (2, 13)], "F", "main"); p.line([(1, 13), (4, 13)], "F", "main")
    for (x, y) in [(8, 4), (9, 4), (9, 3), (9, 2), (10, 3), (10, 4), (10, 5), (11, 4), (11, 5), (12, 5), (8, 5), (9, 5), (9, 1)]: p.px(x, y, "F" if (x, y) != (9, 1) else "F")   # tall dorsal
    for (x, y) in [(11, 12), (12, 12), (12, 13), (13, 12), (11, 13), (10, 13)]: p.px(x, y, "G")                                                     # pectoral
    for x in (14, 15, 16): p.line([(x, 7), (x, 9)], "D", "main")        # gill slits
    p.px(18, 7, "W"); p.px(19, 7, "O"); p.rect(19, 9, 21, 9, "D") if False else None
    p.line([(19, 10), (21, 9)], "O", "main")                             # mouth
    p.px(12, 6, "W"); p.px(13, 6, "W")
    return p

def squid():
    p = Plan()
    for y in range(1, 9):                                               # cone mantle, point up
        half = 0.6 + (y - 1) * .6
        for x in range(W):
            if abs(x - 11.5) <= half: p.px(x, y, "D" if x < 11.5 - half * .3 else ("L" if x > 11.5 + half * .45 else "B"))
    for y in range(9, 11):                                              # head
        for x in range(7, 17): p.px(x, y, "B")
    p.rect(8, 11, 15, 11, "L")
    for k in range(5):                                                  # two triangular side fins at the top of the mantle
        for j in range(k + 1):
            p.px(8 - k + 0, 2 + k + (j - k // 2) * 0, "F") if False else None
    for (x, y) in [(9, 2), (8, 3), (9, 3), (7, 4), (8, 4), (9, 4), (8, 5), (9, 5), (9, 6)]: p.px(x, y, "F"); p.px(23 - x, y, "F")
    for (x, y) in [(7, 4), (8, 5), (8, 3)]: p.px(x, y, "G"); p.px(23 - x, y, "G")
    p.px(9, 9, "W"); p.px(10, 9, "O"); p.px(13, 9, "O"); p.px(14, 9, "W")                  # big eyes
    p.px(9, 10, "O"); p.px(14, 10, "O")
    for (x, y) in [(11, 4), (12, 5), (10, 6), (13, 7), (11, 8)]: p.px(x, y, "S")        # glowing chromatophore dots
    for x, off in [(8, 0), (10, 1), (13, 1), (15, 0)]:                  # four wavy tentacles with club tips
        for i in range(4): p.px(x + (off if i % 2 else 0) * (1 if x < 12 else -1) * 0 + (i % 2 if off else 0) * (1 if x < 12 else -1), 12 + i, "F" if i < 3 else "G", "extra")
    return p

def turtle():
    p = Plan()
    p.ell(11.5, 10, 8, 5.5, "B", ymax=10)                               # domed shell
    p.rect(3, 11, 20, 12, "L")                                          # plastron / shell rim
    for x in range(3, 21): p.px(x, 11, "D") if (x, 11) in p.main else None
    for y in range(5, 10): p.px(8, y, "S"); p.px(11, y, "S"); p.px(14, y, "S")         # scute lines
    for x in range(6, 18): p.px(x, 7, "S")
    p.px(9, 5, "W"); p.px(10, 5, "W"); p.px(8, 6, "W")
    p.ell(20.5, 9.5, 2.4, 2.2, "F")                                     # head
    p.rect(17, 10, 18, 12, "F")                                         # neck
    p.px(21, 8, "W"); p.px(22, 8, "O"); p.px(22, 11, "O")
    p.rect(5, 13, 7, 14, "F"); p.rect(9, 13, 10, 14, "F"); p.rect(13, 13, 14, 14, "F"); p.rect(16, 13, 18, 14, "F")   # four legs
    p.rect(1, 11, 3, 12, "F")                                           # tail
    return p

def frog():
    p = Plan()
    p.ell(11, 10.5, 8, 4.2, "B")                                        # squat body
    p.ell(16.5, 9, 5.2, 3.6, "B")                                       # head
    p.ell(16.5, 5.2, 2.4, 2.4, "B")                                     # big eye dome
    p.rect(15, 5, 17, 6, "W"); p.px(17, 6, "O"); p.px(17, 5, "O")
    p.rect(14, 11, 21, 11, "L"); p.line([(17, 10), (22, 10)], "O", "main")       # mouth line + pale chin
    p.ell(11, 13, 7, 1.8, "L", ymin=12)                                 # belly
    p.ell(6, 11.5, 4, 3.2, "D", ymin=8)                                 # bent hind leg (thigh)
    p.rect(1, 14, 8, 14, "B")                                           # hind foot
    p.rect(14, 13, 18, 14, "B")                                         # front legs
    for (x, y) in [(9, 8), (12, 8), (7, 10), (11, 10), (14, 7)]: p.px(x, y, "S")  # spots
    p.px(9, 7, "W"); p.px(10, 7, "W")
    for x in range(14, 19): p.px(x, 14, "F", "extra")
    return p

def axolotl():
    p = Plan()
    p.ell(17.5, 8, 5.5, 4.4, "B")                                       # wide head (seen from above)
    p.ell(11, 8, 4.2, 3, "B")                                           # body
    for x in range(1, 8):                                               # long tapering tail
        half = .5 + (x - 1) * .35
        for y in range(H):
            if abs(y - 8) <= half: p.px(x, y, "B" if abs(y - 8) < half else "D")
    p.rect(2, 7, 7, 9, "B")
    for (x, y) in [(5, 8), (7, 8)]: p.px(x, y, "L")
    p.ell(11, 9.4, 3.8, 1.6, "L", ymin=9)
    for dy in (-1, 1):                                                  # three feathery gills each side
        for i, gy in enumerate((0, 1, 2)):
            y0 = 8 + dy * 4
            for k in range(3): p.px(14 + i * 2 - (k if False else 0), y0 + dy * (k + gy * 0), "F", "extra")
            p.px(14 + i * 2 - 1, y0 + dy * 3, "G", "extra"); p.px(14 + i * 2 + 1, y0 + dy * 3, "G", "extra") if False else None
    for (x, y) in [(20, 6), (20, 10)]: p.px(x, y, "O"); p.px(x - 1, y, "W") if False else None   # eyes
    p.px(19, 6, "W"); p.px(19, 10, "W")
    p.line([(21, 9), (22, 8)], "O", "main") if False else None
    for x in (10, 13): p.px(x, 4, "B", "extra"); p.px(x, 5, "B", "extra"); p.px(x, 11, "B", "extra"); p.px(x, 12, "B", "extra")   # short legs
    for x in (10, 13): p.px(x, 3, "L", "extra"); p.px(x, 13, "L", "extra")
    p.px(9, 7, "S"); p.px(11, 6, "S"); p.px(8, 9, "S")
    return p

def crayfish():
    p = Plan()
    p.ell(15, 8, 4.6, 3.2, "B")                                         # carapace
    p.rect(19, 7, 20, 9, "B")                                           # head tip
    for i, x in enumerate(range(5, 11)):                                # segmented abdomen
        for y in (6, 7, 8, 9, 10): p.px(x, y, "D" if i % 2 else "B")
    for x in (5, 7, 9): p.line([(x, 6), (x, 10)], "S", "main")
    p.rect(1, 6, 4, 10, "F"); p.px(1, 8, "G"); p.px(1, 6, "G"); p.px(1, 10, "G")   # tail fan
    p.px(2, 8, "G")
    for sy in (-1, 1):                                                  # two big claws reaching forward
        cy = 8 + sy * 4.5
        p.line([(17, 8 + sy * 3), (19, round(cy))], "F", "main"); p.line([(18, 8 + sy * 3), (20, round(cy))], "F", "main")
        p.ell(21, cy, 2.4, 1.8, "F"); p.px(22, round(cy), "."); p.main.pop((22, round(cy)), None); p.px(21, round(cy), "G")
    p.px(18, 6, "W"); p.px(18, 10, "W"); p.px(19, 6, "O"); p.px(19, 10, "O")
    for x in (12, 14, 16):                                              # walking legs
        p.px(x, 4, "F", "extra"); p.px(x - 1, 3, "F", "extra"); p.px(x, 12, "F", "extra"); p.px(x - 1, 13, "F", "extra")
    p.px(20, 8, "F", "extra"); p.px(21, 7, "F", "extra") if False else None
    for x in (21, 22): p.px(x, 8, "F", "extra")
    p.px(13, 6, "W"); p.px(14, 6, "W")
    return p

PLANS = {"jellyfish": jellyfish, "crab": crab, "seahorse": seahorse, "shark": shark, "squid": squid,
         "turtle": turtle, "frog": frog, "axolotl": axolotl, "crayfish": crayfish}

def table():
    out = ["const FISH_PLANS = {   // generated by tools/make_fish_plans.py; letters: O outline, B body, D dark back, L belly, F fin, G fin edge, S accent, W shine"]
    for name, fn in PLANS.items():
        rows = fn().rows()
        out.append(f'  {name}: [')
        out += [f'    "{r}",' for r in rows]
        out.append("  ],")
    out.append("};")
    return "\n".join(out)

if __name__ == "__main__":
    t = table()
    if "--write" in sys.argv:
        p = Path(__file__).resolve().parent.parent / "js" / "state.js"
        s = p.read_text(encoding="utf-8")
        s2, n = re.subn(r"/\* PLANS BEGIN \*/.*?/\* PLANS END \*/", lambda m: "/* PLANS BEGIN */\n" + t + "\n/* PLANS END */", s, flags=re.S)
        assert n == 1; p.write_text(s2, encoding="utf-8"); print("written")
    else:
        for name, fn in PLANS.items():
            print(name); print("\n".join(fn().rows())); print()
