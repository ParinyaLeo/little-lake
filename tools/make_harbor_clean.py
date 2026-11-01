"""Write assets/harbor_clean.jpg: the Harbor photo with the baked-in fisherman patched out (Town Map card art).

Tool only, never loaded by the game. It opens index.html in headless Chromium, runs the game's own
cleanPlate(img, SCENES.harbor.fisher) from js/fisherman.js on assets/harbor.jpg and saves the canvas as JPEG,
so the card always matches the clean plate the fishing scene draws under the animated fisherman.

    pip install playwright && python -m playwright install chromium
    python tools/make_harbor_clean.py

Run it again whenever the patch / rodClear numbers in js/fishing.js change.
"""
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "assets" / "harbor.jpg", ROOT / "assets" / "harbor_clean.jpg"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto((ROOT / "index.html").as_uri())
    # the photo goes in as a data URL so the canvas isn't tainted (file:// images count as cross-origin)
    data = pg.evaluate("""async src => { const im = new Image(); im.src = src; await im.decode();
        return cleanPlate(im, SCENES.harbor.fisher).toDataURL('image/jpeg', 0.92); }""",
        "data:image/jpeg;base64," + base64.b64encode(SRC.read_bytes()).decode())
    b.close()
OUT.write_bytes(base64.b64decode(data.split(",", 1)[1]))
print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
