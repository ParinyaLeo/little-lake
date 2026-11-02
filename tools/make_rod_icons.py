"""Tool only (never loaded by the game): paints the rod icons as pixel-art SVG data URIs.

    python tools/make_rod_icons.py            # prints the CSS rules (.i-rod-<id> 12x12, .i-rodlg-<id> 16x16)
    python tools/make_rod_icons.py --write    # replaces those rules inside css/style.css
    python tools/make_rod_icons.py --sheet    # writes shots/rod_icons_contact.png (needs Pillow) to check the art

The colours are the ROD_STYLES table in js/fisherman.js (the fisherman's rod), so icon and rod match.
The 12x12 icon is the small one (HUD chip); the 16x16 one is shown at 2x / 3x in the Shop, Tackle Box and Choose Rod popup.
"""
import re, sys, pathlib

STYLES = {   # same values as ROD_STYLES in js/fisherman.js
    "bamboo":    dict(grip="#c9a26a", cane="#a9bd3c", tip="#7d9a2a", shade="#3b4a14", butt=1, node="#6b8120"),
    "sturdy":    dict(grip="#3a2210", cane="#5b3517", tip="#4a2b12", shade="#1a0d04", butt=2, ring="#aeb8be"),
    "precision": dict(grip="#7f96aa", cane="#b8dcef", tip="#e6f6ff", shade="",        butt=0, reel="#1c3f78", reelHi="#6fa8ff"),
    "lucky":     dict(grip="#c0392b", cane="#ffcf3f", tip="#fff3a8", shade="#9a6a00", butt=1, charm=True),
}
LINE, HOOK, CHARM, CHARM_HI = "#e8f4ff", "#8d99a1", "#ffcf3f", "#fff6c0"


def icon(n, s):
    """Return {(x, y): colour} for an n x n rod icon: a 45-degree rod from bottom-left to the top, a line and a hook on the right."""
    px = {}
    L = n - 4                                    # rod pixel i is (i, n-1-i); the tip is (L, 3)
    ring_i = None
    for i in range(L + 1):
        k = i / L
        x, y = i, n - 1 - i
        col = s["grip"] if k < .2 else s["cane"] if k < .7 else s["tip"]
        if s.get("node") and .2 <= k < .7 and i % 3 == 0: col = s["node"]
        px[(x, y)] = col
        if k < .5 and s["butt"]:
            px[(x, y + 1)] = s["shade"]                         # shaded row under the butt
            if s["butt"] >= 2: px[(x + 1, y)] = s["cane"]; px[(x + 1, y + 1)] = s["shade"]   # one art pixel thicker butt
        if ring_i is None and k >= .2:
            ring_i = i
            if s.get("ring"):
                px[(x, y)] = s["ring"]; px[(x + 1, y)] = s["ring"]; px[(x, y + 1)] = s["ring"]
                if n > 12: px[(x + 1, y + 1)] = s["ring"]
            if s.get("reel"):
                px[(x + 1, y)] = s["reel"]; px[(x + 1, y + 1)] = s["reel"]
                if n > 12: px[(x, y + 1)] = s["reel"]; px[(x + 2, y + 1)] = s["reel"]; px[(x + 1, y + 2)] = s["reel"]
                px[(x + 1, y)] = s["reelHi"]
    lx = n - 3
    for y in range(3, n - 4): px[(lx, y)] = LINE                # fishing line hanging from the tip
    px[(lx, n - 4)] = HOOK; px[(lx - 1, n - 4)] = HOOK   # hook
    if s.get("charm"):                                           # star sitting on the tip: a plus with a bright centre
        cx = L
        for (dx, dy) in ((0, -1), (-1, 0), (1, 0), (0, 1)): px[(cx + dx, 1 + dy)] = CHARM
        px[(cx, 1)] = CHARM_HI
        if n > 12:
            for (dx, dy) in ((-2, 1), (2, 1)): px[(cx + dx, 1 + dy)] = CHARM_HI   # tiny glints (the sparkle frame)
    return px


def svg(n, px):
    by = {}
    for (x, y), c in sorted(px.items()):
        if 0 <= x < n and 0 <= y < n and c: by.setdefault(c, []).append(f"M{x} {y}h1v1h-1z")
    paths = "".join(f"%3Cpath fill='%23{c[1:]}' d='{''.join(d)}'/%3E" for c, d in by.items())
    return f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {n} {n}' shape-rendering='crispEdges'%3E{paths}%3C/svg%3E"


def css():
    out = []
    for cls, n in (("i-rod", 12), ("i-rodlg", 16)):
        for rid, s in STYLES.items():
            out.append(f'.{cls}-{rid} {{ background-image: url("{svg(n, icon(n, s))}"); }}')
    return "\n".join(out)


if __name__ == "__main__":
    if "--write" in sys.argv:
        p = pathlib.Path(__file__).resolve().parent.parent / "css" / "style.css"
        t = p.read_text(encoding="utf-8")
        t = re.sub(r"^\.i-rod(lg)?-(bamboo|sturdy|precision|lucky) \{.*\}\n", "", t, flags=re.M)
        marker = ".i-bait-shrimp {"
        i = t.index(marker)
        t = t[:i] + css() + "\n" + t[i:]
        p.write_text(t, encoding="utf-8"); print("css/style.css updated")
    elif "--sheet" in sys.argv:
        from PIL import Image
        sc, W = 12, 0
        sheet = Image.new("RGB", (4 * 20 * sc + 10, 2 * 20 * sc), (90, 140, 170)); x0 = 5
        for j, (rid, s) in enumerate(STYLES.items()):
            for r, n in enumerate((12, 16)):
                for (x, y), c in icon(n, s).items():
                    if 0 <= x < n and 0 <= y < n and c:
                        rgb = tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
                        for dx in range(sc):
                            for dy in range(sc): sheet.putpixel((x0 + j * 20 * sc + x * sc + dx, r * 20 * sc + 4 + y * sc + dy), rgb)
        pathlib.Path("shots").mkdir(exist_ok=True); sheet.save("shots/rod_icons_contact.png"); print("shots/rod_icons_contact.png")
    else:
        print(css())
