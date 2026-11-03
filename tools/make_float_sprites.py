"""Tool only (never loaded by the game): draws the 5 float sprites (12 x 19 art pixels, drawn at 2 screen pixels per art pixel) used by drawFloat() in js/fishing.js.

Letters: . empty   O outline   B body   L light / highlight   D shade   A second colour (white, orange beak)   a its shade   W white   K black (pupils)
Row 14 is the waterline (the anchor `(bx, by)` of the bobber is the top edge of row 14); rows 0-2 are the antenna whose top (row 0) is where the fishing line attaches.
`python tools/make_float_sprites.py`          prints the JavaScript FLOAT_MAPS block
`python tools/make_float_sprites.py --write`  rewrites it in js/fishing.js between the FLOAT MAPS markers
`python tools/make_float_sprites.py --sheet`  writes shots/floats_contact.png (Pillow) with the palettes from FLOAT_LOOK below
"""
import re, sys
from pathlib import Path

W, H = 12, 19

class G:
    def __init__(self):
        self.m = {}                                   # (x, y) -> letter, the part that gets an outline
    def ell(self, cx, cy, rx, ry, k="B", y0=-99, y1=99):
        for y in range(H):
            for x in range(W):
                if y0 <= y <= y1 and ((x + .5 - cx) / rx) ** 2 + ((y + .5 - cy) / ry) ** 2 <= 1: self.m[(x, y)] = k
    def px(self, x, y, k, only=True):
        if (x, y) in self.m or not only: self.m[(x, y)] = k
    def rect(self, x0, y0, x1, y1, k, only=True):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1): self.px(x, y, k, only)
    def rows(self, ant=(5, 6)):
        g = [["."] * W for _ in range(H)]
        for (x, y), k in self.m.items(): g[y][x] = k
        for y in range(H):
            for x in range(W):
                if g[y][x] == "." and any(0 <= x + dx < W and 0 <= y + dy < H and (x + dx, y + dy) in self.m for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))): g[y][x] = "O"
        a0, a1 = ant
        for y in (1, 2):
            for x in (a0, a1): g[y][x] = "O"
        for x in range(a0 - 1, a1 + 2): g[0][x] = "O"                  # the line eye: where the fishing line ties on
        return ["".join(r) for r in g]

def round_body(g, cx=6, rx=5):
    g.ell(cx, 11, rx, 7, "B", 4, 17)

def classic():
    g = G(); round_body(g)
    for (x, y) in list(g.m):
        top = y <= 10
        g.m[(x, y)] = "B" if top else "A"
        if x >= 9: g.m[(x, y)] = "D" if top else "a"                    # shaded right side
    g.rect(0, 10, 11, 10, "D")                                           # dark band between red and white
    g.rect(3, 5, 4, 6, "L")                                              # highlight
    return g.rows()

def candy():
    g = G(); round_body(g)
    for (x, y) in list(g.m):
        s = (x + y) % 6
        g.m[(x, y)] = "B" if s < 3 else "A"                              # diagonal pink-and-white swirl
        if x >= 9: g.m[(x, y)] = "D" if s < 3 else "a"
    g.rect(3, 5, 4, 6, "W")
    return g.rows()

def frog():
    g = G(); round_body(g)
    for (x, y) in list(g.m):
        g.m[(x, y)] = "L" if y >= 13 and 2 <= x <= 9 else "B"           # pale belly
        if x >= 9: g.m[(x, y)] = "D"
    g.rect(2, 3, 4, 5, "W", only=False); g.rect(7, 3, 9, 5, "W", only=False)   # two big eyes on top
    g.rect(3, 4, 4, 5, "K"); g.rect(8, 4, 9, 5, "K")                      # 2x2 pupils
    g.rect(3, 10, 8, 10, "D")                                            # mouth
    for (x, y) in [(2, 12), (8, 13), (5, 12), (9, 11)]: g.px(x, y, "D")  # spots
    return g.rows((5, 6))

def duck():
    g = G(); g.ell(4, 11, 3.7, 7, "B", 4, 17)
    for (x, y) in list(g.m):
        if x >= 6: g.m[(x, y)] = "D"
    g.rect(1, 12, 4, 14, "D"); g.rect(2, 12, 3, 12, "B")                 # wing
    g.rect(7, 8, 9, 9, "A", only=False); g.rect(7, 10, 8, 10, "a", only=False)      # a big orange beak
    g.rect(5, 6, 6, 7, "K"); g.px(5, 6, "W")                             # eye with a glint
    g.rect(2, 5, 3, 5, "L")                                              # highlight
    g.rect(2, 3, 3, 3, "A", only=False)                                  # a little tuft
    return g.rows((3, 4))

def golden():
    g = G(); round_body(g)
    for (x, y) in list(g.m):
        g.m[(x, y)] = "B" if y <= 10 else "A"
        if x >= 8: g.m[(x, y)] = "D"
    g.rect(0, 11, 11, 11, "L")
    g.rect(3, 5, 5, 8, "L"); g.rect(3, 5, 4, 6, "W")                     # big shine
    g.px(8, 6, "W"); g.px(7, 13, "L")
    return g.rows()

FLOATS = {"classic": classic, "candy": candy, "frog": frog, "duck": duck, "golden": golden}
LOOK = {   # O outline, B body, L light, D shade, A second colour, a its shade, W white, K black
    "classic": dict(O="#3a0d0d", B="#e53935", L="#ff9e9e", D="#a32121", A="#ffffff", a="#b8c4cc", W="#ffffff", K="#111111"),
    "candy":   dict(O="#6a0f45", B="#ff4fa0", L="#ffffff", D="#c2185b", A="#ffffff", a="#f3b6d4", W="#ffffff", K="#111111"),
    "frog":    dict(O="#0b3a12", B="#43b649", L="#b6f0a8", D="#2a8a30", A="#ffffff", a="#c8e6c9", W="#ffffff", K="#0a0a0a"),
    "duck":    dict(O="#5e3b00", B="#ffd91a", L="#fff08a", D="#e0a800", A="#ff8a00", a="#d46a00", W="#ffffff", K="#111111"),
    "golden":  dict(O="#5a3d00", B="#ffc400", L="#fff4a8", D="#d98e00", A="#ffb300", a="#b87400", W="#ffffff", K="#111111"),
}

def block():
    out = ["const FLOAT_MAPS = {   // generated by tools/make_float_sprites.py: 12 x 19 art pixels, 2 screen pixels each; row 14 = the waterline, row 0 = where the line ties on"]
    for k, fn in FLOATS.items():
        out.append(f"  {k}: [" + ", ".join(f'"{r}"' for r in fn()) + "],")
    out.append("};")
    return "\n".join(out)

if __name__ == "__main__":
    if "--write" in sys.argv:
        p = Path(__file__).resolve().parent.parent / "js" / "fishing.js"
        s = p.read_text(encoding="utf-8")
        s2, n = re.subn(r"/\* FLOAT MAPS BEGIN \*/.*?/\* FLOAT MAPS END \*/", lambda m: "/* FLOAT MAPS BEGIN */\n" + block() + "\n/* FLOAT MAPS END */", s, flags=re.S)
        assert n == 1; p.write_text(s2, encoding="utf-8"); print("written")
    elif "--sheet" in sys.argv:
        from PIL import Image
        S = 12; img = Image.new("RGB", (len(FLOATS) * (W * S + 20) + 20, H * S + 40), (30, 120, 170))
        for i, (k, fn) in enumerate(FLOATS.items()):
            pal = {a: tuple(int(v[j:j + 2], 16) for j in (1, 3, 5)) for a, v in LOOK[k].items()}
            for y, row in enumerate(fn()):
                for x, ch in enumerate(row):
                    if ch in pal:
                        for dy in range(S):
                            for dx in range(S): img.putpixel((20 + i * (W * S + 20) + x * S + dx, 20 + y * S + dy), pal[ch])
        out = Path(__file__).resolve().parent.parent / "shots" / "floats_contact.png"; out.parent.mkdir(exist_ok=True); img.save(out); print(out)
    else:
        print(block())
