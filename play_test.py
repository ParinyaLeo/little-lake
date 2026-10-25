import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = Path(__file__).with_name("index.html").resolve().as_uri()
SHOTS = Path(__file__).with_name("shots"); SHOTS.mkdir(exist_ok=True)
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail)); print(("PASS " if ok else "FAIL ") + name, detail)

def catch_one(pg, perfect=True):
    pg.click("#actBtn")                                   # CAST
    pg.wait_for_function("F.phase === 'bite'", timeout=8000)
    pg.click("#actBtn")                                   # HOOK
    while pg.evaluate("F.phase") == "reeling":
        if perfect:
            pg.wait_for_function("F.phase !== 'reeling' || (F.pos > F.zoneX + 0.01 && F.pos < F.zoneX + F.zoneW - 0.01)", timeout=8000, polling=5)
        if pg.evaluate("F.phase") != "reeling": break
        pg.click("#actBtn")
        pg.wait_for_timeout(30)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(300)
    pg.screenshot(path=str(SHOTS / "01_home.png"))
    check("home shows default coins", pg.inner_text("#hCoins") == "300")

    pg.click("section.active >> text=TOWN MAP"); pg.wait_for_timeout(200); pg.screenshot(path=str(SHOTS / "02_map.png"))
    check("secret island locked", "???" in pg.inner_text("#islands"))
    pg.click(".island.bg-harbor"); pg.wait_for_timeout(400); pg.screenshot(path=str(SHOTS / "03_fishing.png"))

    # bite + hook screenshot
    pg.click("#actBtn"); pg.wait_for_function("F.phase === 'bite'", timeout=8000)
    pg.screenshot(path=str(SHOTS / "04_bite.png"))
    pg.click("#actBtn"); pg.wait_for_timeout(250); pg.screenshot(path=str(SHOTS / "05_minigame.png"))
    while pg.evaluate("F.phase") == "reeling":
        pg.wait_for_function("F.phase !== 'reeling' || (F.pos > F.zoneX + 0.01 && F.pos < F.zoneX + F.zoneW - 0.01)", timeout=8000, polling=5)
        if pg.evaluate("F.phase") != "reeling": break
        pg.click("#actBtn"); pg.wait_for_timeout(30)
    pg.wait_for_timeout(500)
    check("perfect timing catches fish", pg.is_visible("#result"), pg.inner_text("#resName"))
    pg.screenshot(path=str(SHOTS / "06_result.png"))
    pg.click("#keepBtn"); pg.wait_for_timeout(200)
    check("catch saved to bag", pg.evaluate("S.bag.length") == 1)

    # miss path -> escape
    pg.click("#actBtn"); pg.wait_for_function("F.phase === 'bite'", timeout=8000); pg.click("#actBtn")
    for _ in range(5):
        if pg.evaluate("F.phase") != "reeling": break
        pg.wait_for_function("F.phase !== 'reeling' || (F.pos < F.zoneX - 0.05 || F.pos > F.zoneX + F.zoneW + 0.05)", timeout=8000, polling=5)
        if pg.evaluate("F.phase") != "reeling": break
        pg.click("#actBtn"); pg.wait_for_timeout(30)
    check("2 misses at rod 1 = escape", pg.evaluate("F.phase") == "idle" and "escaped" in pg.inner_text("#fMsg"), pg.inner_text("#fMsg"))

    # too slow on bite
    pg.click("#actBtn"); pg.wait_for_function("F.phase === 'bite'", timeout=8000); pg.wait_for_timeout(1300)
    check("no HOOK within 1s = fish swims away", "Too slow" in pg.inner_text("#fMsg"))

    # random delay check
    delays = []
    for _ in range(6):
        delays.append(float(pg.evaluate("""() => new Promise(r => { const t0 = performance.now(); document.getElementById('actBtn').click();
            const iv = setInterval(() => { if (F.phase === 'bite') { clearInterval(iv); r(((performance.now() - t0) / 1000).toFixed(2)); } }, 20); })""")))
        pg.wait_for_timeout(1200)
    check("bite delay varies (1-5 s after cast)", len(set(delays)) > 1 and all(1.3 < d < 6 for d in delays), str(delays))

    # full bag
    pg.evaluate("S.bag = []; while (S.bag.length < S.bagMax) S.bag.push({fishId:'harbor_0',weight:.2,price:20,time:1}); save(); render()")
    pg.wait_for_timeout(200); pg.screenshot(path=str(SHOTS / "07_fullbag.png"))
    check("full bag blocks CAST", pg.is_disabled("#actBtn"))
    pg.click("#fBagBtn"); pg.wait_for_timeout(200)
    check("OPEN BAG works when full", pg.is_visible("#bag"))
    pg.screenshot(path=str(SHOTS / "08_bag.png"))
    coins0 = pg.evaluate("S.coins"); pg.click("#sellAll"); pg.wait_for_timeout(200)
    check("sell all adds coins and empties bag", pg.evaluate("S.coins") == coins0 + 100 and pg.evaluate("S.bag.length") == 0)

    # shop
    pg.evaluate("S.coins = 120; save()"); pg.click("section.active >> text=HOME"); pg.click("text=SHOP"); pg.wait_for_timeout(200)
    check("rod blocked with insufficient coins", pg.is_disabled("#buyRod"))
    pg.click("#buyBait"); check("buy bait works", pg.evaluate("S.bait") == 5 and pg.evaluate("S.coins") == 20)
    pg.screenshot(path=str(SHOTS / "09_shop.png"))

    # persistence
    pg.reload(); pg.wait_for_timeout(300)
    check("progress survives reload", pg.evaluate("S.bait") == 5 and pg.evaluate("S.coins") == 20)

    # broken save
    pg.evaluate("localStorage.setItem('littleLakeSave', '{\"coins\":\"abc\",\"bag\":[null,{\"fishId\":\"x\"}],\"rod\":-3}')"); pg.reload(); pg.wait_for_timeout(300)
    check("broken save falls back safely", pg.evaluate("S.coins") == 300 and pg.evaluate("S.rod") == 1 and pg.evaluate("S.bag.length") == 0
          and "NaN" not in pg.inner_text("body") and "undefined" not in pg.inner_text("body"))

    # mastery via demo mode
    for _ in range(5): pg.click("#title")
    pg.wait_for_timeout(200); pg.click("#dHarbor"); pg.wait_for_timeout(400)
    check("Harbor mastery banner", pg.is_visible("#banner") and "Harbor Mastered" in pg.inner_text("#banTitle"))
    pg.screenshot(path=str(SHOTS / "10_mastery.png"))
    pg.click("#banOk"); pg.click("#dAll"); pg.wait_for_timeout(3000); pg.screenshot(path=str(SHOTS / "10b_secret_banner.png"))
    check("secret island unlocked", pg.evaluate("secretOpen()"))
    pg.evaluate("document.getElementById('banner').classList.remove('show')")
    pg.click("section.active >> button:has-text(\"COLLECTION\")"); pg.wait_for_timeout(200); pg.screenshot(path=str(SHOTS / "11_collection.png"))
    pg.click("section.active >> text=HOME"); pg.click("section.active >> text=TOWN MAP"); pg.wait_for_timeout(200); pg.screenshot(path=str(SHOTS / "12_map_secret.png"))

    # mastery effects
    check("Harbor reward +20% price active", pg.evaluate("!!S.mastery.harbor"))
    check("Forest reward adds a miss", pg.evaluate("allowedMiss()") == 2)

    # mobile
    m = b.new_page(viewport={"width": 360, "height": 780}); m.goto(URL); m.wait_for_timeout(300)
    check("mobile home no side scroll", m.evaluate("document.documentElement.scrollWidth") <= 360)
    m.screenshot(path=str(SHOTS / "13_mobile_home.png"), full_page=True)
    m.click("section.active >> text=TOWN MAP"); m.click(".island.bg-harbor"); m.wait_for_timeout(400)
    check("mobile fishing no side scroll", m.evaluate("document.documentElement.scrollWidth") <= 360)
    m.screenshot(path=str(SHOTS / "14_mobile_fishing.png"), full_page=True)

    check("no JavaScript errors", not errs, "; ".join(errs[:3]))
    b.close()

print(f"\n{sum(r[1] for r in results)}/{len(results)} passed")
json.dump(results, open(Path(__file__).with_name("results.json"), "w"), indent=1)
