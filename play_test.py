import base64, json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(errors="replace")   # Windows consoles can't print every character in the details

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

ROD_IDS_PY = ["bamboo", "sturdy", "precision", "lucky"]


def start_new(pg, name="Tester"):
    """Title screen -> NEW GAME -> enter name -> Home."""
    pg.click("#newBtn"); pg.fill("#nameInput", name); pg.click("#nameStart"); pg.wait_for_timeout(200)
    pg.evaluate("() => { S.fightStyle = 'tap'; save(); }")          # Playtest 2, part 3: the default fight is Hold Fight; all the older tests are about the classic tap minigame

def no_side_scroll(pg, width=360):
    return pg.evaluate("document.documentElement.scrollWidth") <= width

SAVED = "JSON.parse(localStorage.getItem('littleLakeSave'))"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(300)
    start_new(pg)
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
    pg.wait_for_timeout(1000)                             # the fisherman celebrates for 700 ms first
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
    pg.click("#sellTop"); pg.wait_for_timeout(200)
    check("SELL (fishing screen top bar) opens the Bag when the bag is full", pg.is_visible("#bag"))
    pg.screenshot(path=str(SHOTS / "08_bag.png"))
    coins0 = pg.evaluate("S.coins"); pg.click("#sellAll"); pg.wait_for_timeout(200)
    check("sell all adds coins and empties bag", pg.evaluate("S.coins") == coins0 + 100 and pg.evaluate("S.bag.length") == 0)

    # shop
    pg.evaluate("S.coins = 120; save(); go('home')"); pg.click("section.active >> text=SHOP"); pg.wait_for_timeout(200)
    check("rod blocked with insufficient coins", pg.is_disabled('[data-buy="rod:sturdy"]'))
    pg.click('[data-buy="bait:shrimp"]'); check("buy bait works", pg.evaluate("S.baits.shrimp") == 5 and pg.evaluate("S.coins") == 20)
    pg.screenshot(path=str(SHOTS / "09_shop.png"))

    # persistence
    pg.reload(); pg.wait_for_timeout(300)
    check("progress survives reload", pg.evaluate("S.baits.shrimp") == 5 and pg.evaluate("S.coins") == 20)

    # broken save
    pg.evaluate("localStorage.setItem('littleLakeSave', '{\"coins\":\"abc\",\"bag\":[null,{\"fishId\":\"x\"}],\"rod\":-3}')"); pg.reload(); pg.wait_for_timeout(300)
    pg.click("#contBtn"); pg.wait_for_timeout(200)
    check("broken save falls back safely", pg.evaluate("S.coins") == 300 and pg.evaluate("S.rodEq") == "bamboo" and pg.evaluate("S.rods") == ["bamboo"] and pg.evaluate("S.bag.length") == 0
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
    pg.click("#navBack"); pg.click("section.active >> text=TOWN MAP"); pg.wait_for_timeout(200); pg.screenshot(path=str(SHOTS / "12_map_secret.png"))

    # mastery effects
    check("Harbor reward +20% price active", pg.evaluate("!!S.mastery.harbor"))
    check("Forest reward adds a miss", pg.evaluate("allowedMiss()") == 2)

    # mobile
    m = b.new_page(viewport={"width": 360, "height": 780}); m.goto(URL); m.wait_for_timeout(300)
    m.on("pageerror", lambda e: errs.append(str(e)))
    check("mobile title no side scroll", m.is_visible("#titleScreen") and no_side_scroll(m))
    m.screenshot(path=str(SHOTS / "15_mobile_title.png"), full_page=True)
    m.click("#howBtn"); m.wait_for_timeout(300)
    check("mobile How to Play no side scroll", m.is_visible("#howBox") and no_side_scroll(m))
    m.screenshot(path=str(SHOTS / "16_mobile_howto.png"))
    m.click("#howOk"); m.click("#newBtn"); m.wait_for_timeout(300)
    check("mobile name dialog no side scroll", m.is_visible("#nameInput") and no_side_scroll(m))
    m.screenshot(path=str(SHOTS / "17_mobile_name.png"))
    m.click("#nameCancel"); start_new(m, "Mobi")
    check("mobile home no side scroll", m.evaluate("document.documentElement.scrollWidth") <= 360)
    m.screenshot(path=str(SHOTS / "13_mobile_home.png"), full_page=True)
    m.click("section.active >> text=TOWN MAP"); m.click(".island.bg-harbor"); m.wait_for_timeout(400)
    check("mobile fishing no side scroll", m.evaluate("document.documentElement.scrollWidth") <= 360)
    m.screenshot(path=str(SHOTS / "14_mobile_fishing.png"), full_page=True)

    # mobile bite alert + toast position
    for w in (360, 430):
        m.set_viewport_size({"width": w, "height": 780}); m.wait_for_timeout(200)
        m.click("#actBtn"); m.wait_for_function("F.phase === 'bite'", timeout=8000); m.wait_for_timeout(150)
        bang = m.evaluate("(() => { const s = getComputedStyle(document.getElementById('bang')); return [parseFloat(s.fontSize), s.animationName]; })()")
        hook = m.evaluate("getComputedStyle(document.getElementById('actBtn')).animationName")
        if w == 360: m.screenshot(path=str(SHOTS / "22_mobile_bite.png"))
        check(f"mobile {w}px: big shaking '!' and flashing HOOK", bang[0] >= 80 and "shake" in bang[1] and hook == "hookflash", f"{bang} {hook}")
        m.wait_for_function("document.getElementById('toast').classList.contains('show')", timeout=3000)   # "Too slow" toast
        pos = m.evaluate("[document.getElementById('toast').getBoundingClientRect().top, document.querySelector('.top').getBoundingClientRect().bottom]")
        if w == 360: m.wait_for_timeout(250); m.screenshot(path=str(SHOTS / "23_mobile_toast.png"))
        check(f"mobile {w}px: toast below the top bar", pos[0] >= pos[1], str(pos))
        m.wait_for_timeout(1800)
    m.set_viewport_size({"width": 360, "height": 780})

    # ---------- title screen (fresh browser, no save) ----------
    t = b.new_page(viewport={"width": 1280, "height": 800})
    t.on("pageerror", lambda e: errs.append(str(e)))
    t.on("console", lambda m: m.type == "error" and errs.append(m.text))
    t.goto(URL); t.wait_for_timeout(300)
    t.screenshot(path=str(SHOTS / "18_title.png"))
    check("first visit shows Title with CONTINUE disabled",
          t.is_visible("#titleScreen") and not t.is_visible("#home") and t.is_disabled("#contBtn"))
    check("top bar hidden on Title", not t.is_visible("#title"))

    t.click("#howBtn"); t.wait_for_timeout(200)
    how = t.inner_text("#howBox")
    check("HOW TO PLAY explains cast, !, reel, bag, shop, mastery",
          t.is_visible("#howBox") and all(w in how for w in ["CAST", '"!"', "REEL", "Bag", "Shop", "Island Mastery"]))
    t.screenshot(path=str(SHOTS / "19_howto.png"))
    t.keyboard.press("Escape"); t.wait_for_timeout(100)
    check("Escape closes HOW TO PLAY", not t.is_visible("#howBox"))

    t.click("#newBtn"); t.wait_for_timeout(200)
    check("NEW GAME without a save skips the confirm", t.is_visible("#nameBox") and not t.is_visible("#confirmBox"))
    rejected = []
    for bad in ["", "     ", "\t  \t"]:
        t.fill("#nameInput", bad); t.click("#nameStart"); t.wait_for_timeout(100)
        rejected.append(t.is_visible("#nameBox") and t.inner_text("#nameErr") != "" and t.evaluate(SAVED) is None)
    t.screenshot(path=str(SHOTS / "20_name_error.png"))
    check("empty or whitespace-only name is rejected", all(rejected), str(rejected))
    t.evaluate("document.getElementById('nameInput').value = 'ABCDEFGHIJKLM'"); t.click("#nameStart"); t.wait_for_timeout(100)
    check("name longer than 12 characters is rejected", t.is_visible("#nameBox") and t.evaluate(SAVED) is None)
    t.fill("#nameInput", "  Parinya  "); t.press("#nameInput", "Enter"); t.wait_for_timeout(300)
    check("NEW GAME with a name reaches Home showing that name",
          t.is_visible("#home") and t.inner_text("#homeName") == "Parinya" and t.inner_text("#hCoins") == "300"
          and t.evaluate(SAVED + ".name") == "Parinya", t.inner_text("#homeName"))

    t.evaluate("S.coins = 777; S.baits.shrimp = 3; save(); render()")
    t.reload(); t.wait_for_timeout(300)
    check("reload opens Title with CONTINUE enabled", t.is_visible("#titleScreen") and t.is_enabled("#contBtn"))
    t.click("#contBtn"); t.wait_for_timeout(200)
    check("CONTINUE after reload keeps progress",
          t.is_visible("#home") and t.inner_text("#hCoins") == "777" and t.inner_text("#homeName") == "Parinya" and t.evaluate("S.baits.shrimp") == 3)

    t.click("#menuBtn"); t.wait_for_timeout(200)
    check("MENU button returns to Title", t.is_visible("#titleScreen") and not t.is_visible("#home"))
    t.click("#newBtn"); t.wait_for_timeout(200)
    check("NEW GAME over an existing save asks for confirmation",
          t.is_visible("#confirmBox") and "This will delete your current progress" in t.inner_text("#confirmBox") and not t.is_visible("#nameBox"))
    t.screenshot(path=str(SHOTS / "21_confirm.png"))
    t.click("#confirmNo"); t.wait_for_timeout(100)
    check("cancelling the confirm keeps the save", not t.is_visible("#confirmBox") and t.evaluate(SAVED + ".coins") == 777)
    t.click("#newBtn"); t.click("#confirmYes"); t.wait_for_timeout(100)
    t.click("#nameCancel"); t.wait_for_timeout(100)
    check("confirming then cancelling the name still keeps the save", t.evaluate(SAVED + ".coins") == 777)
    t.click("#newBtn"); t.click("#confirmYes"); t.fill("#nameInput", "Nova"); t.click("#nameStart"); t.wait_for_timeout(300)
    check("confirmed NEW GAME resets progress",
          t.inner_text("#homeName") == "Nova" and t.inner_text("#hCoins") == "300" and t.evaluate("S.baits.shrimp") == 0 and t.evaluate("S.rodEq") == "bamboo")

    # sound
    t.click("#menuBtn"); t.wait_for_timeout(100)
    t.click("#soundBtn"); t.wait_for_timeout(100)
    check("sound toggle switches off", "OFF" in t.inner_text("#soundBtn") and t.evaluate("S.sound") is False)
    t.reload(); t.wait_for_timeout(300)
    check("sound toggle is remembered after reload",
          "OFF" in t.inner_text("#soundBtn") and t.evaluate("S.sound") is False and t.evaluate(SAVED + ".sound") is False
          and t.evaluate(SAVED + ".name") == "Nova")
    t.evaluate("Object.values(sfx).forEach(f => f())"); t.wait_for_timeout(600)
    check("no sound effect plays while sound is off", t.evaluate("typeof AC") == "undefined")
    t.click("#soundBtn"); t.wait_for_timeout(100)
    check("sound toggle switches back on", "ON" in t.inner_text("#soundBtn") and t.evaluate(SAVED + ".sound") is True)

    t.evaluate("localStorage.clear()"); t.reload(); t.wait_for_timeout(300)
    t.click("#soundBtn"); t.reload(); t.wait_for_timeout(300)
    check("sound setting saved before any game keeps CONTINUE disabled",
          t.evaluate("S.sound") is False and t.is_disabled("#contBtn"))
    t.evaluate("localStorage.setItem('littleLakeSave', JSON.stringify({name:'Old', coins:50, rod:1, bait:0, bagMax:5, bag:[]}))")
    t.reload(); t.wait_for_timeout(300)
    check("older save without sound setting defaults to sound on", t.evaluate("S.sound") is True and t.is_enabled("#contBtn"))
    t.click("#contBtn"); t.wait_for_timeout(200)
    for _ in range(5): t.click("#title")
    t.wait_for_timeout(200)
    check("demo mode still opens from Home", t.is_visible("#demo"))

    # ---------- visual polish (display only) ----------
    check("pixel font loads from assets/fonts", t.evaluate("document.fonts.check('700 20px \"Pixelify Sans\"')")
          and "Pixelify Sans" in t.evaluate("getComputedStyle(document.querySelector('.btn')).fontFamily"))
    check("Home stat cards and buttons have pixel icons",
          t.evaluate("document.querySelectorAll('#home .stat > .ico').length") == 6 and t.evaluate("document.querySelectorAll('#home .btns .ico').length") == 6)   # 6 with the AQUARIUM button (Playtest 2, part 8)
    check("Home shows the full-screen harbor backdrop (no pixel clouds or dashes)", t.evaluate("document.querySelector('#backdrop .bd.on').dataset.isle") == "harbor"
          and t.evaluate("!document.querySelector('.bgfx, .clouds, .water')"))
    t.evaluate("() => { F = { phase: 'idle', fish: fishById('harbor_9') }; caught(); }"); t.wait_for_timeout(400)
    check("Legendary result: gold frame + sparkles", t.evaluate("document.getElementById('result').dataset.rarity") == "Legendary"
          and t.is_visible("#result .sparkles") and t.evaluate("getComputedStyle(document.querySelector('.portrait')).borderTopColor") == "rgb(255, 213, 79)")
    t.screenshot(path=str(SHOTS / "24_result_legendary.png"))
    t.click("#releaseBtn"); t.evaluate("() => { F = { phase: 'idle', fish: fishById('harbor_0') }; caught(); }"); t.wait_for_timeout(400)
    check("Common result: grey frame, no sparkles", t.evaluate("document.getElementById('result').dataset.rarity") == "Common"
          and not t.is_visible("#result .sparkles"))
    t.click("#releaseBtn"); t.evaluate("() => { collTab = 'harbor'; go('collection'); }"); t.wait_for_timeout(400)
    check("Collection cards coloured by rarity, unknown fish show '?'",
          t.evaluate("document.querySelectorAll('#collGrid .cell.r-Rare').length") == 3
          and t.evaluate("[...document.querySelectorAll('#collGrid .cell.unknown')].every(c => getComputedStyle(c, '::after').content === '\"?\"')"))
    t.screenshot(path=str(SHOTS / "25_collection.png"))

    # ---------- scene art + fish drawings (display only) ----------
    t.evaluate("() => { ['harbor','frost','desert','forest'].forEach(i => S.mastery[i] = true); }")
    # the painted scenes are the fallback when a picture can't load: hide the pictures to check the painters
    t.wait_for_function("Object.values(SCENES).every(s => s.img || s.failed)", timeout=8000)
    t.evaluate("() => { for (const k in SCENES) if (SCENES[k].paint) { SCENES[k].saved = SCENES[k].img; SCENES[k].img = null; } }")
    looks = {}
    for isl in ["frost", "desert", "forest", "secret"]:
        t.evaluate(f"() => {{ island = '{isl}'; go('fishing'); }}"); t.wait_for_timeout(400)
        looks[isl] = t.evaluate("""() => { const c = document.getElementById('sceneCanvas'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            const cols = new Set(); let r = 0, g = 0, b = 0, n = 0;
            for (let i = 0; i < d.length; i += 4 * 97) { cols.add(d[i] >> 3 << 10 | d[i+1] >> 3 << 5 | d[i+2] >> 3); r += d[i]; g += d[i+1]; b += d[i+2]; n++; }
            return [cols.size, Math.round(r / n), Math.round(g / n), Math.round(b / n)]; }""")
        t.screenshot(path=str(SHOTS / f"26_scene_{isl}.png"))
    avg = [tuple(v[1:]) for v in looks.values()]
    check("each painted island is detailed and looks different",
          all(v[0] >= 25 for v in looks.values()) and all(sum(abs(a - b) for a, b in zip(avg[i], avg[j])) > 40 for i in range(4) for j in range(i + 1, 4)), str(looks))
    t.click("#actBtn"); t.wait_for_timeout(1000)
    check("casting on a painted island still works", t.evaluate("F.phase") == "waiting")
    t.evaluate("() => { stopFishing(); for (const k in SCENES) if (SCENES[k].paint) SCENES[k].img = SCENES[k].saved; }")
    shapes = t.evaluate("[...new Set(FISH.map(fishShape))].sort()")
    check("fish come in several body shapes", all(s in shapes for s in ["eel", "flat", "long", "round", "slim"]), str(shapes))
    t.evaluate("() => { F = { phase: 'idle', fish: fishById('forest_9') }; caught(); }"); t.wait_for_timeout(100)
    check("catch plays the fish-jump animation", t.evaluate("getComputedStyle(document.getElementById('resCanvas')).animationName") == "fish-jump")
    t.click("#releaseBtn"); t.wait_for_timeout(200)
    t.click("#actBtn"); t.wait_for_function("F.phase === 'bite'", timeout=8000); t.click("#actBtn"); t.wait_for_timeout(200)
    check("reel gauge has a pulsing zone and glowing marker",
          t.evaluate("getComputedStyle(document.getElementById('zone'), '::after').animationName") == "zone-pulse"
          and "255, 235, 59" in t.evaluate("getComputedStyle(document.getElementById('marker')).boxShadow"))
    t.screenshot(path=str(SHOTS / "27_reel_gauge.png"))
    t.evaluate("() => stopFishing()"); t.evaluate("() => go('home')")
    check("page background is the fixed backdrop layer (body keeps only a fallback colour)",
          t.evaluate("getComputedStyle(document.body).backgroundImage") == "none" and t.evaluate("getComputedStyle(document.getElementById('backdrop')).position") == "fixed")

    rm = b.new_page(viewport={"width": 360, "height": 780}, reduced_motion="reduce")
    rm.goto(URL); rm.wait_for_timeout(300)
    check("Playtest 2, part 6: prefers-reduced-motion does NOT stop the background animations (shimmer, backdrop crossfade, screen fade still run)",
          rm.evaluate("getComputedStyle(document.querySelector('.title-shimmer')).animationName !== 'none'")
          and rm.evaluate("getComputedStyle(document.querySelector('#backdrop .bd')).transitionDuration") != "0s"
          and rm.evaluate("getComputedStyle(document.querySelector('.screen.active')).animationName") != "none"
          and rm.evaluate("motionReduced()") is False and rm.evaluate("typeof REDUCED") == "undefined")

    # ---------- playtest fixes: missing fish, Tackle Box, bait toggle, hearts, shop effects (see docs/bug_log.md) ----------
    qc = b.new_context(viewport={"width": 1280, "height": 800}); q = qc.new_page()   # own context so a 2nd tab can share its storage
    q.on("pageerror", lambda e: errs.append(str(e)))
    q.on("console", lambda m: m.type == "error" and errs.append(m.text))
    q.goto(URL); q.evaluate("localStorage.clear()"); q.reload(); q.wait_for_timeout(300)
    start_new(q, "Fixer")
    def toast_text(pg): return pg.inner_text("#toast")
    def fake_catch(pg, fish_id): pg.evaluate(f"() => {{ F = {{ phase: 'idle', fish: fishById('{fish_id}') }}; caught(); }}"); pg.wait_for_timeout(150)

    # BUG-1: the catch on the Result screen is saved, so a reload can't lose it
    fake_catch(q, "harbor_2")
    check("catch waiting on Result is stored in the save", q.evaluate(SAVED + ".pending.fishId") == "harbor_2")
    q.reload(); q.wait_for_timeout(300); q.click("#contBtn"); q.wait_for_timeout(300)
    check("reload + CONTINUE returns to the waiting catch", q.is_visible("#result") and "Hermit Crab" in q.inner_text("#resName"))
    q.evaluate("go('home')"); q.wait_for_timeout(150)
    check("can't leave the Result screen without KEEP or RELEASE", q.is_visible("#result") and not q.is_visible("#home"))
    q.click("#keepBtn"); q.wait_for_timeout(150)
    check("KEEP shows '+1 Hermit Crab added to bag' and bounces the bag count",
          "+1 Hermit Crab added to bag" in toast_text(q) and "bump" in q.get_attribute("#fBag", "class")
          and q.evaluate("S.bag.length") == 1 and q.evaluate(SAVED + ".pending") is None, toast_text(q))
    q.evaluate("() => { for (let i = 0; i < 4; i++) { F = { phase: 'idle', fish: fishById('harbor_0') }; caught(); keepCatch(); } }")
    check("several catches in a row all stay in the bag (and after reload)",
          q.evaluate("S.bag.length") == 5 and (q.reload() or True) and q.evaluate(SAVED + ".bag.length") == 5)
    q.click("#contBtn"); q.wait_for_timeout(200)

    # BUG-2: full bag on the Result screen -> clear choice instead of a silent release
    q.evaluate("() => { S.bag[0].price = 7; save(); }")
    fake_catch(q, "harbor_1"); q.wait_for_timeout(200)
    check("full bag on Result shows SELL A FISH / OPEN BAG / RELEASE instead of KEEP",
          q.is_visible("#fullBag") and not q.is_visible("#keepBtn") and q.is_visible("#sellOneBtn") and q.is_visible("#resBagBtn") and q.is_visible("#fullRelease"))
    q.screenshot(path=str(SHOTS / "28_full_bag_choice.png"))
    coins0 = q.evaluate("S.coins"); q.click("#sellOneBtn"); q.wait_for_timeout(150)
    check("SELL A FISH sells the cheapest fish and keeps the new one",
          q.evaluate("S.coins") == coins0 + 7 and q.evaluate("S.bag.length") == 5 and q.evaluate("S.bag.some(b => b.fishId === 'harbor_1')")
          and q.evaluate("S.pending") is None and "Moon Jellyfish added to bag" in toast_text(q), toast_text(q))
    fake_catch(q, "harbor_3"); q.click("#resBagBtn"); q.wait_for_timeout(200)
    check("OPEN BAG from a full Result opens the bag", q.is_visible("#bag"))
    q.click("#bagList .row .btn"); q.wait_for_timeout(100); q.click("#navBack"); q.wait_for_timeout(200)
    check("after selling in the bag, BACK returns to the catch with KEEP available", q.is_visible("#result") and q.is_visible("#keepBtn") and not q.is_visible("#fullBag"))
    q.click("#keepBtn"); q.wait_for_timeout(100)
    fake_catch(q, "harbor_0"); bag0 = q.evaluate("JSON.stringify(S.bag)"); q.click("#fullRelease"); q.wait_for_timeout(150)
    check("RELEASE on a full bag leaves the bag unchanged", q.evaluate("JSON.stringify(S.bag)") == bag0 and q.evaluate("S.pending") is None and q.is_visible("#fishing"))
    q.evaluate("() => { S.bag = []; save(); go('home'); }")

    # BUG-3: two tabs of the game no longer overwrite each other's progress
    q2 = qc.new_page(); q2.goto(URL); q2.wait_for_timeout(300); q2.click("#contBtn"); q2.wait_for_timeout(200)
    q2.evaluate("() => { S.bag.push({ fishId: 'frost_0', weight: .1, price: 20, time: 1 }); save(); }"); q2.wait_for_timeout(300)
    q.evaluate("() => { S.coins += 1; save(); }")
    check("a fish kept in another tab is not wiped by this tab's next save", q.evaluate(SAVED + ".bag.length") == 1 and q.evaluate("S.bag.length") == 1)
    q2.close()

    # BUG-4: Tackle Box lists all gear with effects
    q.evaluate("() => { S.rods = ['bamboo', 'sturdy']; S.rodEq = 'sturdy'; S.baits.shrimp = 3; S.baitSel = 'shrimp'; S.mastery.harbor = true; S.mastery.forest = true; save(); go('home'); }")
    q.click("#tackleBtn"); q.wait_for_timeout(300)
    gear = q.inner_text("#gearList")
    check("TACKLE BOX opens from Home and lists rod, misses, bait, bag", q.is_visible("#tackle")
          and "Sturdy Rod" in gear and "3 misses allowed in total" in gear and "Shrimp x3" in gear and "Bag 1 / 5" in gear, gear[:120])
    check("Tackle Box shows each island reward as unlocked or locked with progress",
          q.evaluate("[...document.querySelectorAll('#gearList .gear-row')].filter(r => r.textContent.includes('UNLOCKED')).length") == 2
          and q.evaluate("document.querySelectorAll('#gearList .gear-row.locked').length") == 2
          and "Golden Hook" in gear and "Steady Hands" in gear and "Lucky Lure" in gear and "Master's Charm" in gear and "/ 10 Frost fish" in gear)
    check("every Tackle Box row has an icon and a one-line effect",
          q.evaluate("[...document.querySelectorAll('#gearList .gear-row')].every(r => r.querySelector('.ico') && r.querySelector('.fx').textContent.trim().length > 10)"))
    q.screenshot(path=str(SHOTS / "29_tackle_box.png"), full_page=True)

    # BUG-5: "Master Rod" renamed so it isn't confused with the shop rod
    check("'Master Rod' is renamed to 'Master's Charm' everywhere",
          q.evaluate("ISLANDS.forest.reward") == "Master's Charm" and "Master Rod" not in q.content()
          and q.evaluate("(() => { go('collection'); collTab = 'forest'; renderCollection(); return document.getElementById('collHead').textContent; })()").count("Master's Charm") == 1)

    # BUG-6: the last bait must still give bait odds (bait selection is tested in the gear section below)
    q.evaluate("() => { island = 'harbor'; go('fishing'); }"); q.wait_for_timeout(300)
    q.evaluate("() => { S.baits.shrimp = 1; S.baitSel = 'shrimp'; save(); render(); window._wb = []; const o = pickFish; pickFish = w => { _wb.push(w); return o(w); }; }")
    q.click("#actBtn"); q.wait_for_timeout(100)
    check("the last bait still gives bait odds", q.evaluate("_wb") == ["shrimp"] and q.evaluate("S.baits.shrimp") == 0
          and q.evaluate("S.baitSel") == "none" and "None" in q.inner_text("#baitChip"))
    q.evaluate("() => stopFishing()")

    # BUG-7: hearts for misses left, bonus icons with tooltips
    q.evaluate("() => { S.rods = ['bamboo', 'sturdy']; S.rodEq = 'sturdy'; S.mastery = { frost: true }; save(); island = 'harbor'; go('fishing'); }"); q.wait_for_timeout(300)
    bon = q.evaluate("[...document.querySelectorAll('#bonuses .bonus')].map(b => b.title)")
    check("active rewards show as small icons with tooltips", len(bon) == 1 and "Steady Hands" in bon[0] and "20% slower" in bon[0], str(bon))
    q.click("#bonuses .bonus"); q.wait_for_timeout(100)
    check("tapping a reward icon explains it", "Steady Hands" in toast_text(q))
    q.click("#actBtn"); q.wait_for_function("F.phase === 'bite'", timeout=8000); q.click("#actBtn"); q.wait_for_timeout(100)
    hearts = lambda: q.evaluate("[document.querySelectorAll('#hearts .i-heart').length, document.querySelectorAll('#hearts .i-heart0').length]")
    h0 = hearts()
    q.wait_for_function("F.phase !== 'reeling' || (F.pos < F.zoneX - 0.05 || F.pos > F.zoneX + F.zoneW + 0.05)", timeout=8000, polling=5); q.click("#actBtn"); q.wait_for_timeout(60)
    h1 = hearts()
    check("reeling shows one heart per allowed miss and a miss empties one", h0 == [2, 0] and h1 == [1, 1] and "MISSES LEFT" in q.inner_text("#hearts"), f"{h0} {h1}")
    q.screenshot(path=str(SHOTS / "30_hearts.png"))
    q.evaluate("() => stopFishing()")
    check("hearts are hidden when not reeling", q.evaluate("(() => { go('fishing'); return document.getElementById('hearts').children.length; })()") == 0)

    # BUG-8: the Shop shows each item's effect before buying
    q.evaluate("() => { S.mastery = {}; S.bagMax = 5; S.coins = 1000; save(); go('shop'); }"); q.wait_for_timeout(200)
    check("Shop: bag shows new and current size", q.inner_text("#sBagFx") == "Bag: 10 slots (now 5)")

    q.click("section.active >> text=HOME"); q.click("#menuBtn"); q.click("#howBtn"); q.wait_for_timeout(200)
    how = q.inner_text("#howBox")
    check("HOW TO PLAY explains rods, bait choice, hearts, Tackle Box and Master's Charm",
          all(w in how for w in ["Rods", "Sturdy", "Precision", "Lucky", "Worm", "Golden Lure", "heart", "Tackle Box", "Master's Charm", "separate save"]))
    q.click("#howOk")

    # phones
    m.evaluate("() => { S.baits.worm = 2; S.mastery.harbor = true; save(); go('tackle'); }"); m.wait_for_timeout(300)
    check("mobile Tackle Box no side scroll", m.is_visible("#tackle") and no_side_scroll(m))
    m.screenshot(path=str(SHOTS / "31_mobile_tackle.png"), full_page=True)
    m.evaluate("() => { S.bag = []; while (S.bag.length < S.bagMax) S.bag.push({fishId:'harbor_0',weight:.2,price:20,time:1}); F = { phase: 'idle', fish: fishById('harbor_5') }; caught(); }"); m.wait_for_timeout(300)
    check("mobile full-bag choice no side scroll", m.is_visible("#sellOneBtn") and no_side_scroll(m))
    m.screenshot(path=str(SHOTS / "32_mobile_full_bag.png"), full_page=True)
    m.click("#fullRelease"); m.wait_for_timeout(200)
    check("mobile fishing HUD (rod + bait + bonuses) no side scroll", m.is_visible("#rodChip") and m.is_visible("#baitChip") and m.is_visible("#bonuses .bonus") and no_side_scroll(m))

    # ---------- BUG-9: the main fishing button must not move between phases (see docs/bug_log.md) ----------
    ACT_POS = """(() => { const r = document.getElementById('actBtn').getBoundingClientRect();
        return { top: r.top + scrollY, bottom: r.bottom, vh: innerHeight, page: document.documentElement.scrollHeight }; })()"""
    for vw, vh in [(1366, 768), (1280, 720), (1366, 625), (1280, 600), (390, 844)]:
        s = b.new_page(viewport={"width": vw, "height": vh})
        s.on("pageerror", lambda e: errs.append(str(e)))
        s.goto(URL); s.evaluate("localStorage.clear()"); s.reload(); s.wait_for_timeout(200); start_new(s, "Steady")
        s.evaluate("() => { S.baits.shrimp = 5; S.baitSel = 'shrimp'; S.mastery = { harbor: true, frost: true }; save(); island = 'harbor'; go('fishing'); }"); s.wait_for_timeout(400)
        pos = {}
        def at(phase):
            s.mouse.move(1, 1); pos[phase] = s.evaluate(ACT_POS)
        at("idle")
        s.click("#actBtn"); s.wait_for_function("F.phase === 'waiting'"); at("waiting")
        s.wait_for_function("F.phase === 'bite'", timeout=8000); at("bite")
        s.click("#actBtn"); s.wait_for_timeout(100); at("reeling")
        s.click("#actBtn"); s.wait_for_timeout(60); at("reeling after a press")
        s.screenshot(path=str(SHOTS / f"33_steady_{vw}x{vh}.png"))
        tops = [p["top"] for p in pos.values()]
        check(f"{vw}x{vh}: CAST/HOOK/REEL button stays put in every phase (<= 1px)", max(tops) - min(tops) <= 1,
              ", ".join(f"{k} {v['top']:.1f}" for k, v in pos.items()))
        check(f"{vw}x{vh}: button is inside the viewport and the page doesn't scroll while fishing",
              all(p["bottom"] <= p["vh"] and p["page"] <= p["vh"] for p in pos.values()),
              ", ".join(f"{k} bottom {v['bottom']:.0f}/{v['vh']} page {v['page']}" for k, v in pos.items()))
        s.evaluate("() => stopFishing()"); s.close()

    # Space key and tapping the scene do the same as the main button
    k = b.new_page(viewport={"width": 1280, "height": 720})
    k.on("pageerror", lambda e: errs.append(str(e)))
    k.goto(URL); k.evaluate("localStorage.clear()"); k.reload(); k.wait_for_timeout(200); start_new(k, "Keys")
    k.evaluate("() => { island = 'harbor'; go('fishing'); }"); k.wait_for_timeout(400)
    k.keyboard.press("Space"); k.wait_for_timeout(50)
    check("Space casts on the fishing screen", k.evaluate("F.phase") in ("casting", "waiting") and k.evaluate("scrollY") == 0)
    k.wait_for_function("F.phase === 'bite'", timeout=8000); k.click("#scene"); k.wait_for_timeout(50)
    check("tapping the scene hooks the fish", k.evaluate("F.phase") == "reeling")
    k.focus("#actBtn"); k.keyboard.press("Space"); k.wait_for_timeout(100)
    check("Space reels exactly once, even with the button focused", k.evaluate("F.phase") == "reeling" and k.evaluate("F.hits + F.misses") == 1)
    k.evaluate("() => stopFishing()"); k.evaluate("() => go('fishing')"); k.wait_for_timeout(200)
    k.focus("#actBtn"); k.keyboard.press("Space"); k.wait_for_timeout(50)
    check("Space on a focused button acts only once", k.evaluate("F.phase") in ("casting", "waiting") and k.evaluate("S.totalCaught") == 0)
    k.wait_for_function("F.phase === 'bite'", timeout=8000); k.wait_for_timeout(1200)
    k.evaluate("() => { S.bag = []; while (S.bag.length < S.bagMax) S.bag.push({fishId:'harbor_0',weight:.2,price:20,time:1}); save(); render(); }")
    k.click("#scene"); k.keyboard.press("Space"); k.wait_for_timeout(50)
    check("Space / tap do nothing while the main button is disabled (full bag)", k.evaluate("F.phase") == "idle")
    k.evaluate("() => go('home')"); k.wait_for_timeout(300); k.keyboard.press("Space"); k.wait_for_timeout(50)
    check("Space does nothing outside the fishing screen", k.evaluate("F.phase") == "idle" and k.is_visible("#home"))
    k.close()

    # ---------- rods (buy once, equip one) and baits (select one, or none) ----------
    g = b.new_page(viewport={"width": 1280, "height": 800})
    g.on("pageerror", lambda e: errs.append(str(e)))
    g.on("console", lambda m: m.type == "error" and errs.append(m.text))
    g.goto(URL); g.evaluate("localStorage.clear()"); g.reload(); g.wait_for_timeout(200); start_new(g, "Gear")
    check("new game starts with only the Bamboo Rod equipped and no bait",
          g.evaluate("[S.rods, S.rodEq, S.baitSel, allowedMiss()]") == [["bamboo"], "bamboo", "none", 1] and g.inner_text("#hRod") == "Bamboo")

    # shop: affordable / not affordable / owned
    g.evaluate("() => go('shop')"); g.wait_for_timeout(200)
    shop_item = lambda key: g.evaluate(f"""(() => {{ const btn = document.querySelector('[data-buy="{key}"]'), it = btn.closest('.item');
        return {{ disabled: btn.disabled, label: btn.textContent, text: it.textContent }}; }})()""")
    bam, stu, pre, luc = (shop_item(f"rod:{r}") for r in ["bamboo", "sturdy", "precision", "lucky"])
    check("Shop lists 4 rods with exact effects",
          "1 miss allowed, normal zone and speed." in bam["text"] and "2 misses allowed, normal zone and speed." in stu["text"]
          and "3 misses allowed, green zone 35% wider." in pre["text"]
          and "5 misses allowed, better rarity odds (like Shrimp bait), minigame 10% faster." in luc["text"]
          and "Legendary 6%" in luc["text"], luc["text"][:160])
    check("Shop: equipped starter rod is marked and can't be bought", bam["disabled"] and bam["label"] == "EQUIPPED" and "EQUIPPED" in bam["text"])
    check("Shop: items you can't afford are disabled and say how much is missing (300 coins)",
          not stu["disabled"] and pre["disabled"] and luc["disabled"] and "Need 150 more coins" in pre["text"] and "Need 400 more coins" in luc["text"])
    wor, shr, gol = (shop_item(f"bait:{x}") for x in ["worm", "shrimp", "golden"])
    check("Shop lists 3 baits with pack size, price and exact odds",
          "Worm x5" in wor["text"] and wor["label"] == "60 COINS" and "Rare 40%" in wor["text"]
          and "Shrimp x5" in shr["text"] and shr["label"] == "100 COINS" and "Common 40% · Rare 30% · Epic 24% · Legendary 6%" in shr["text"]
          and "Golden Lure x3" in gol["text"] and gol["label"] == "250 COINS" and "Legendary 20%" in gol["text"], gol["text"][:160])
    g.click('[data-buy="rod:sturdy"]'); g.wait_for_timeout(100)
    stu = shop_item("rod:sturdy")
    check("buying a rod takes the coins, adds it, and marks it OWNED (not equipped yet)",
          g.evaluate("S.coins") == 100 and g.evaluate("S.rods") == ["bamboo", "sturdy"] and g.evaluate("S.rodEq") == "bamboo"
          and stu["disabled"] and stu["label"] == "OWNED" and g.evaluate(SAVED + ".rods") == ["bamboo", "sturdy"])
    g.evaluate("() => { buyRod('sturdy'); buyRod('precision'); }"); g.wait_for_timeout(50)
    check("can't buy a rod twice or without enough coins", g.evaluate("S.coins") == 100 and g.evaluate("S.rods.length") == 2)
    g.evaluate("() => { buyBait('golden'); }")
    check("can't buy bait without enough coins", g.evaluate("S.coins") == 100 and g.evaluate("S.baits.golden") == 0)
    g.click('[data-buy="bait:worm"]'); g.wait_for_timeout(100)
    check("buying bait with no bait selected selects it", g.evaluate("[S.baits.worm, S.baitSel, S.coins]") == [5, "worm", 40]
          and "Worm is now your bait" in g.inner_text("#toast"))
    g.evaluate("() => { S.coins = 2000; save(); render(); }"); g.click('[data-buy="bait:shrimp"]'); g.wait_for_timeout(50)
    check("buying another bait keeps the current selection", g.evaluate("[S.baits.shrimp, S.baitSel]") == [5, "worm"])
    g.screenshot(path=str(SHOTS / "34_shop_rods_baits.png"), full_page=True)

    # Tackle Box: equip a rod, select a bait
    g.evaluate("() => go('tackle')"); g.wait_for_timeout(200)
    g.click('[data-equip="sturdy"]'); g.wait_for_timeout(100)
    row_of = lambda name: g.evaluate(f"[...document.querySelectorAll('#gearList .gear-row')].find(r => r.querySelector('b').textContent.startsWith('{name}')).textContent")
    check("Tackle Box: EQUIP the Sturdy Rod (2 misses), labelled EQUIPPED",
          g.evaluate("[S.rodEq, allowedMiss()]") == ["sturdy", 2] and "EQUIPPED" in row_of("Sturdy Rod") and "EQUIP" in row_of("Bamboo Rod")
          and "EQUIPPED" not in row_of("Bamboo Rod") and g.evaluate(SAVED + ".rodEq") == "sturdy")
    check("Tackle Box: rods you don't own point to the Shop and can't be equipped",
          "SHOP · 700 COINS" in row_of("Lucky Rod") and not g.evaluate("!!document.querySelector('[data-equip=\"lucky\"]')")
          and (g.evaluate("equipRod('lucky'), S.rodEq") == "sturdy"))
    g.click('[data-bait="shrimp"]'); g.wait_for_timeout(100)
    check("Tackle Box: select Shrimp, labelled EQUIPPED", g.evaluate("S.baitSel") == "shrimp" and "EQUIPPED" in row_of("Shrimp")
          and "EQUIPPED" not in row_of("Worm") and g.evaluate(SAVED + ".baitSel") == "shrimp")
    check("Tackle Box: bait you have none of says BUY IN SHOP and can't be selected",
          "BUY IN SHOP" in row_of("Golden Lure") and g.evaluate("selectBait('golden'), S.baitSel") == "shrimp")
    g.screenshot(path=str(SHOTS / "35_tackle_equip.png"), full_page=True)

    # fishing: bait use, HUD chips
    g.evaluate("() => { island = 'harbor'; go('fishing'); }"); g.wait_for_timeout(300)
    check("fishing HUD shows the equipped rod and selected bait", "Sturdy" in g.inner_text("#rodChip") and "Shrimp x5" in g.inner_text("#baitChip"))
    g.click("#actBtn"); g.wait_for_timeout(100)
    check("a cast uses one of the selected bait only", g.evaluate("[S.baits.shrimp, S.baits.worm, F.usedBait]") == [4, 5, "shrimp"]
          and g.is_disabled("#rodChip") and g.is_disabled("#baitChip"))
    # ROD / BAIT picker popups (BUG-12: the chips used to cycle one item per tap)
    g.evaluate("() => { stopFishing(); go('fishing'); }"); g.wait_for_timeout(100)
    cards = lambda: g.evaluate("[...document.querySelectorAll('#pickList .pick-card')].map(c => [c.dataset.id, c.disabled, c.classList.contains('equipped'), c.textContent])")
    focused = lambda: g.evaluate("document.activeElement && document.activeElement.id")
    g.click("#baitChip"); g.wait_for_timeout(150)
    bl = cards()
    check("BAIT opens 'Choose Bait': No bait first, then each bait with count, odds and EQUIPPED",
          g.is_visible("#pickBox") and g.inner_text("#pickTitle") == "Choose Bait" and [x[0] for x in bl] == ["none", "worm", "shrimp", "golden"]
          and bl[2][2] and "EQUIPPED" in bl[2][3] and "Shrimp x4" in bl[2][3] and "Legendary 6%" in bl[2][3]
          and "Worm x5" in bl[1][3] and "Rare 40%" in bl[1][3] and focused() == "pick-shrimp", str([x[0:3] for x in bl]))
    g.screenshot(path=str(SHOTS / "38_choose_bait.png"))
    g.click("#pick-golden", force=True); g.wait_for_timeout(100)
    check("bait with 0 left is greyed out with 'Buy in Shop' and can't be selected",
          bl[3][1] and "Buy in Shop" in bl[3][3] and g.evaluate("S.baitSel") == "shrimp" and g.is_visible("#pickBox"))
    g.click("#pick-none"); g.wait_for_timeout(100)
    check("picking 'No bait' selects it in one tap, closes the popup, updates the chip, focus back on BAIT",
          g.evaluate("S.baitSel") == "none" and not g.is_visible("#pickBox") and "None" in g.inner_text("#baitChip") and focused() == "baitChip")
    g.click("#actBtn"); g.wait_for_timeout(100)
    check("casting with no bait uses none", g.evaluate("[S.baits.shrimp, S.baits.worm, F.usedBait]") == [4, 5, None])
    for ph in ["waiting", "bite"]:
        g.wait_for_function(f"F.phase === '{ph}'", timeout=8000)
        g.evaluate("() => { openPicker('rod'); openPicker('bait'); }")
        check(f"ROD / BAIT disabled and no popup while {ph}", g.is_disabled("#rodChip") and g.is_disabled("#baitChip") and not g.is_visible("#pickBox"))
    g.click("#actBtn"); g.wait_for_timeout(100); g.evaluate("() => { openPicker('rod'); }")
    check("ROD / BAIT disabled and no popup while reeling", g.evaluate("F.phase") == "reeling" and g.is_disabled("#rodChip") and not g.is_visible("#pickBox"))
    g.evaluate("() => { stopFishing(); go('fishing'); }"); g.wait_for_timeout(100)

    g.evaluate("() => { S.rods = ['bamboo', 'sturdy', 'precision', 'lucky']; S.mastery = {}; save(); render(); }")
    g.click("#rodChip"); g.wait_for_timeout(150)
    rl = cards()
    check("ROD opens 'Choose Rod': all 4 rods with misses, zone, odds, marker speed and EQUIPPED",
          g.inner_text("#pickTitle") == "Choose Rod" and [x[0] for x in rl] == ["bamboo", "sturdy", "precision", "lucky"] and rl[1][2]
          and "2 misses allowed" in rl[1][3] and "green zone 35% wider" in rl[2][3] and "minigame 10% faster" in rl[3][3]
          and all("Common" in x[3] for x in rl) and "Legendary 6%" in rl[3][3], str([x[0:3] for x in rl]))
    g.screenshot(path=str(SHOTS / "39_choose_rod.png"))
    g.click("#pick-lucky"); g.wait_for_timeout(100)
    check("equipping a non-first rod takes one tap in the popup (Lucky Rod)",
          g.evaluate("S.rodEq") == "lucky" and "Lucky" in g.inner_text("#rodChip") and not g.is_visible("#pickBox")
          and "Equipped: Lucky Rod" in g.inner_text("#toast") and g.evaluate(SAVED + ".rodEq") == "lucky")
    g.evaluate("() => { S.rods = ['bamboo', 'lucky']; save(); render(); }")
    g.click("#rodChip"); g.wait_for_timeout(150)
    rl = cards()
    g.click("#pick-precision", force=True); g.wait_for_timeout(100)
    check("rods you don't own are greyed out with price and 'Buy in Shop' and can't be equipped",
          rl[2][1] and "450 COINS" in rl[2][3] and "Buy in Shop" in rl[2][3] and rl[1][1] and g.evaluate("S.rodEq") == "lucky" and g.is_visible("#pickBox"))
    g.keyboard.press("Escape"); g.wait_for_timeout(100)
    check("Esc closes the popup and focus returns to ROD", not g.is_visible("#pickBox") and focused() == "rodChip" and g.evaluate("S.rodEq") == "lucky")
    g.click("#rodChip"); g.wait_for_timeout(150)
    g.keyboard.press("Shift+Tab"); f1 = focused(); g.keyboard.press("Enter"); g.wait_for_timeout(100)
    check("keyboard: Tab moves between items (skipping locked ones), Enter selects",
          f1 == "pick-bamboo" and g.evaluate("S.rodEq") == "bamboo" and not g.is_visible("#pickBox") and focused() == "rodChip", f1)
    g.click("#rodChip"); g.wait_for_timeout(150)
    for _ in range(6): g.keyboard.press("Tab")
    check("Tab stays inside the popup", g.evaluate("!!document.activeElement.closest('#pickBox')"))
    g.evaluate("() => document.activeElement.blur()"); g.keyboard.press("Space"); g.wait_for_timeout(100)
    check("Space doesn't cast while the popup is open", g.evaluate("F.phase") == "idle" and g.is_visible("#pickBox"))
    g.mouse.click(5, 5); g.wait_for_timeout(100)
    check("tapping outside closes the popup", not g.is_visible("#pickBox") and g.evaluate("S.rodEq") == "bamboo")
    g.click("#baitChip"); g.wait_for_timeout(150); g.click("#pickClose"); g.wait_for_timeout(100)
    check("CLOSE closes the popup without changing anything", not g.is_visible("#pickBox") and g.evaluate("S.baitSel") == "none")
    g.click("#rodChip"); g.wait_for_timeout(150); g.click("#pickShop"); g.wait_for_timeout(200)
    check("GO TO SHOP closes the popup and opens the Shop", not g.is_visible("#pickBox") and g.is_visible("#shop"))
    g.evaluate("() => { go('tackle'); }"); g.wait_for_timeout(200); g.click('[data-equip="lucky"]'); g.wait_for_timeout(100)
    check("the Tackle Box still equips rods", g.evaluate("S.rodEq") == "lucky")
    g.evaluate("() => { go('fishing'); }"); g.wait_for_timeout(200)
    g.evaluate("() => { S.baitSel = 'golden'; S.baits.golden = 0; save(); }")
    g.reload(); g.wait_for_timeout(200)
    check("a selected bait with none left loads as no bait", g.evaluate("S.baitSel") == "none")
    g.click("#contBtn"); g.wait_for_timeout(200)

    # effects of each rod on misses, zone and marker speed (Common fish: zone .26, speed .55), with island rewards on top
    eff = """(rodId, mastery) => { S.rods = ['bamboo','sturdy','precision','lucky']; S.rodEq = rodId; S.mastery = mastery;
        island = 'harbor'; go('fishing'); F = { phase: 'bite', fish: fishById('harbor_0') }; hook();
        const r = [allowedMiss(), Math.round(F.zoneW * 1000) / 1000, Math.round(F.speed * 1000) / 1000]; stopFishing(); return r; }"""
    effects = {r: g.evaluate(f"({eff})('{r}', {{}})") for r in ["bamboo", "sturdy", "precision", "lucky"]}
    check("rod effects: Bamboo 1 miss, Sturdy 2, Precision 3 + zone x1.35, Lucky 5 + marker x1.1",
          effects == {"bamboo": [1, .26, .55], "sturdy": [2, .26, .55], "precision": [3, .351, .55], "lucky": [5, .26, .605]}, str(effects))
    with_rewards = g.evaluate(f"({eff})('lucky', {{ forest: true, frost: true }})"), g.evaluate(f"({eff})('sturdy', {{ forest: true }})")
    check("island rewards stack on the rod (Master's Charm +1 miss, Steady Hands 20% slower)",
          with_rewards[0] == [6, .26, .484] and with_rewards[1] == [3, .26, .55], str(with_rewards))

    # odds: each bait / Lucky Rod / Lucky Lure, stacking, Legendary cap
    odds = lambda bait, rod_id, desert=False: g.evaluate(f"(() => {{ S.mastery = {{ desert: {str(desert).lower()} }}; return rarityWeights('{bait}', '{rod_id}').map(v => Math.round(v * 100) / 100); }})()")
    check("odds unchanged for no bait and Shrimp (60/30/8/2, 40/30/24/6) and the Desert reward",
          odds("none", "bamboo") == [60, 30, 8, 2] and odds("shrimp", "bamboo") == [40, 30, 24, 6] and odds("none", "bamboo", True) == [52, 30, 13, 5])
    check("Worm boosts Rare, Golden Lure boosts Epic and Legendary, Lucky Rod = Shrimp odds",
          odds("worm", "bamboo") == [50, 40, 8, 2] and odds("golden", "bamboo") == [25, 25, 30, 20] and odds("none", "lucky") == [40, 30, 24, 6])
    stack = odds("golden", "lucky"), odds("golden", "lucky", True), odds("shrimp", "lucky")
    check("bait and Lucky Rod stack, with Legendary capped at 20%",
          stack[0] == [5, 25, 50, 20] and stack[1][3] == 20 and min(stack[1]) >= 0 and abs(sum(stack[1]) - 100) < .01
          and stack[2] == [20, 30, 40, 10], str(stack))
    picked = g.evaluate("""(() => { const r = Math.random; Math.random = () => .5; island = 'harbor'; S.mastery = {}; S.rodEq = 'bamboo';
        const out = [pickFish(null).rarity, pickFish('golden').rarity]; Math.random = r; return out; })()""")
    check("the cast's fish is rolled with those odds", picked == ["Common", "Epic"], str(picked))
    g.close()

    # save migration from before the gear update
    mig = b.new_page(viewport={"width": 1280, "height": 800})
    def migrate(old):
        mig.goto(URL); mig.evaluate(f"localStorage.setItem('littleLakeSave', JSON.stringify({old}))"); mig.reload(); mig.wait_for_timeout(150)
        return mig.evaluate("({ rods: S.rods, rodEq: S.rodEq, baits: S.baits, baitSel: S.baitSel, coins: S.coins, miss: allowedMiss() })")
    m1 = migrate("{ name: 'Old', coins: 50, rod: 1, bait: 0, bagMax: 5, bag: [] }")
    check("old save rod level 1 -> Bamboo Rod", m1["rods"] == ["bamboo"] and m1["rodEq"] == "bamboo" and m1["baitSel"] == "none" and m1["coins"] == 50, str(m1))
    m2 = migrate("{ name: 'Old', coins: 50, rod: 2, bait: 4, bagMax: 5, bag: [] }")
    check("old save rod level 2 -> owns and equips Sturdy; bait becomes Shrimp (selected)",
          m2["rods"] == ["bamboo", "sturdy"] and m2["rodEq"] == "sturdy" and m2["miss"] == 2 and m2["baits"] == {"worm": 0, "shrimp": 4, "golden": 0}
          and m2["baitSel"] == "shrimp", str(m2))
    m3 = migrate("{ name: 'Old', coins: 50, rod: 4, bait: 2, useBait: false, bagMax: 5, bag: [] }")
    check("old save rod level 4 -> Sturdy + 400 coins refunded; USE BAIT off -> no bait selected",
          m3["rodEq"] == "sturdy" and m3["coins"] == 450 and m3["baits"]["shrimp"] == 2 and m3["baitSel"] == "none", str(m3))
    mig.evaluate("() => save()"); mig.reload(); mig.wait_for_timeout(150)
    check("migration happens once (no second refund after saving)", mig.evaluate("S.coins") == 450 and mig.evaluate(SAVED + ".rod") is None)
    mig.close()

    # 360px layout
    n = b.new_page(viewport={"width": 360, "height": 780})
    n.on("pageerror", lambda e: errs.append(str(e)))
    n.goto(URL); n.evaluate("localStorage.clear()"); n.reload(); n.wait_for_timeout(200); start_new(n, "Tiny")
    n.evaluate("() => { S.coins = 400; S.rods.push('precision'); S.rodEq = 'precision'; S.baits = { worm: 3, shrimp: 12, golden: 2 }; S.baitSel = 'golden'; S.mastery = { harbor: true, frost: true, desert: true, forest: true }; save(); go('shop'); }")
    n.wait_for_timeout(300)
    check("360px: Shop with rods and baits has no side scroll", no_side_scroll(n))
    n.screenshot(path=str(SHOTS / "36_mobile_shop.png"), full_page=True)
    n.evaluate("() => go('tackle')"); n.wait_for_timeout(300)
    check("360px: Tackle Box with rods and baits has no side scroll", no_side_scroll(n))
    n.evaluate("() => { island = 'harbor'; go('fishing'); }"); n.wait_for_timeout(400)
    r = n.evaluate("(() => { const a = document.getElementById('actBtn').getBoundingClientRect(), c = document.getElementById('baitChip'); return [a.bottom, innerHeight, document.documentElement.scrollHeight, c.scrollWidth <= c.clientWidth + 1]; })()")
    check("360px: fishing HUD with rod + bait chips fits (no side scroll, no page scroll, chips not cut off)",
          no_side_scroll(n) and r[0] <= r[1] and r[2] <= r[1] and r[3], str(r))
    n.screenshot(path=str(SHOTS / "37_mobile_fishing_gear.png"))
    n.set_viewport_size({"width": 360, "height": 640}); n.wait_for_timeout(200)
    n.evaluate("() => { S.rods = ['bamboo', 'sturdy', 'precision']; S.baits.shrimp = 0; save(); render(); }")
    locked_label = """(() => { const c = document.querySelector('#pickList .pick-card.locked'), b = c.querySelector('b');
        return [c.querySelector('.chip').innerText.trim(), Math.round(b.getBoundingClientRect().height) <= Math.round(parseFloat(getComputedStyle(b).fontSize) * 1.5)]; })()"""
    for chip, name in [("#rodChip", "rod"), ("#baitChip", "bait")]:
        n.click(chip); n.wait_for_timeout(300)
        fit = n.evaluate("""(() => { const p = document.getElementById('pickPanel').getBoundingClientRect(), vh = innerHeight,
            inView = id => { const r = document.getElementById(id).getBoundingClientRect(); return r.top >= 0 && r.bottom <= vh && r.right <= innerWidth; };
            return [p.top >= 0 && p.bottom <= vh && p.right <= innerWidth, inView('pickClose'), inView('pickShop'), inView('pickTitle')]; })()""")
        check(f"360x640: Choose {name.title()} popup fits with CLOSE and GO TO SHOP visible, no side scroll", all(fit) and no_side_scroll(n), str(fit))
        lab = n.evaluate(locked_label)
        check(f"360px: locked {name} shows the short price label and its name stays on one line",
              lab == (["🪙700", True] if name == "rod" else ["🪙100", True]), str(lab))
        n.screenshot(path=str(SHOTS / f"40_mobile_choose_{name}.png"))
        n.keyboard.press("Escape"); n.wait_for_timeout(100)
    n.set_viewport_size({"width": 1280, "height": 800}); n.wait_for_timeout(200)
    n.click("#rodChip"); n.wait_for_timeout(300)
    check("wide screens keep the full '700 COINS · Buy in Shop' label", n.evaluate(locked_label)[0] == "700 COINS · Buy in Shop", str(n.evaluate(locked_label)))
    n.keyboard.press("Escape"); n.wait_for_timeout(100)
    n.set_viewport_size({"width": 360, "height": 780})
    n.close()

    # ---------- animated Harbor fisherman (js/fisherman.js) ----------
    STATE = """() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => {
        const t = fisherTip(), m = window.__mt, a = document.getElementById('actBtn').getBoundingClientRect(); window.__mt = null;
        r({ pose: fisherPose(), phase: F.phase, gap: m ? Math.hypot(m[0] - t.x, m[1] - t.y) : null, tip: [t.x, t.y], top: a.top + scrollY }); })))"""
    SPY = "() => { const o = ctx.moveTo; ctx.moveTo = function (x, y) { window.__mt = [x, y]; return o.call(this, x, y); }; }"   # records where the line starts
    fz = b.new_page(viewport={"width": 360, "height": 640})
    fz.on("pageerror", lambda e: errs.append(str(e))); fz.on("console", lambda m: m.type == "error" and errs.append(m.text))
    fz.goto(URL); fz.evaluate("localStorage.clear()"); fz.reload(); fz.wait_for_timeout(200); start_new(fz, "Angler")
    fz.add_style_tag(content="#toast { display: none !important; }")             # keep the screenshots clear
    fz.evaluate("() => { island = 'harbor'; go('fishing'); }"); fz.wait_for_timeout(400); fz.evaluate(SPY)
    seen = {}
    def snap(label):
        st = fz.evaluate(STATE); seen[label] = st
        fz.locator("#scene").screenshot(path=str(SHOTS / f"42_fisher_{label}.png")); return st
    snap("idle")
    fz.click("#actBtn"); snap("casting")
    fz.wait_for_function("F.phase === 'waiting'"); fz.wait_for_timeout(100); snap("waiting")
    fz.wait_for_function("F.phase === 'bite'", timeout=8000); snap("bite")
    fz.click("#actBtn"); fz.wait_for_timeout(100); snap("reeling")
    fz.wait_for_function("F.phase !== 'reeling' || (F.pos > F.zoneX + 0.01 && F.pos < F.zoneX + F.zoneW - 0.01)", timeout=8000, polling=5)
    fz.click("#actBtn"); fz.wait_for_timeout(40); snap("reeling_tug")
    fz.wait_for_function("F.phase !== 'reeling' || (F.pos < F.zoneX - 0.05 || F.pos > F.zoneX + F.zoneW + 0.05)", timeout=8000, polling=5)
    fz.click("#actBtn"); fz.wait_for_timeout(40); snap("reeling_slack")
    while fz.evaluate("F.phase") == "reeling":                                       # Bamboo Rod: the 2nd miss loses the fish
        fz.wait_for_function("F.phase !== 'reeling' || (F.pos < F.zoneX - 0.05 || F.pos > F.zoneX + F.zoneW + 0.05)", timeout=8000, polling=5)
        if fz.evaluate("F.phase") == "reeling": fz.click("#actBtn"); fz.wait_for_timeout(30)
    snap("escaped")
    fz.wait_for_timeout(1500); fz.click("#actBtn")
    fz.wait_for_function("F.phase === 'bite'", timeout=8000); fz.click("#actBtn")
    while fz.evaluate("F.phase") == "reeling":
        fz.wait_for_function("F.phase !== 'reeling' || (F.pos > F.zoneX + 0.01 && F.pos < F.zoneX + F.zoneW - 0.01)", timeout=8000, polling=5)
        if fz.evaluate("F.phase") == "reeling": fz.click("#actBtn"); fz.wait_for_timeout(30)
    snap("caught")
    celebrating = fz.evaluate("[current, document.getElementById('actBtn').disabled]")
    fz.wait_for_timeout(900)
    poses = {k: v["pose"] for k, v in seen.items()}
    check("fisherman pose follows the phase (idle, casting, waiting, bite, reeling, escaped, caught)",
          all(poses[k] == k.split("_")[0] for k in poses), str(poses))
    check("caught: he celebrates on the fishing screen (button disabled), then the Result screen opens",
          celebrating == ["fishing", True] and fz.is_visible("#result"), f"{celebrating} result {fz.is_visible('#result')}")
    gaps = {k: v["gap"] for k, v in seen.items() if v["phase"] != "idle"}
    check("the line starts at the drawn rod tip in every phase (<= 2px)",
          len(gaps) == 6 and all(g is not None and g <= 2 for g in gaps.values()), str({k: None if g is None else round(g, 2) for k, g in gaps.items()}))
    tips = {k: tuple(round(x) for x in v["tip"]) for k, v in seen.items()}
    check("the rod moves between poses", len(set(tips.values())) >= 6, str(tips))
    tops = [v["top"] for v in seen.values()]
    check("360x640: CAST button stays put in every fisherman pose, no side scroll", max(tops) - min(tops) <= 1 and no_side_scroll(fz),
          ", ".join(f"{k} {v['top']:.1f}" for k, v in seen.items()))
    # the fisherman baked into the photo is patched out: count shirt-blue and straw-hat pixels where he sat
    fz.evaluate("""() => { const sc = SCENES.harbor, c = document.createElement('canvas'), g = c.getContext('2d'); c.id = 'plateTest'; c.width = 100; c.height = 162;
        c.style.cssText = 'position:fixed;left:0;top:0;z-index:999;width:100px;height:162px';
        g.drawImage(sc.img, 190, 174, 100, 81, 0, 0, 100, 81); g.drawImage(sc.plate, 190, 174, 100, 81, 0, 81, 100, 81); document.body.appendChild(c); }""")
    png = fz.locator("#plateTest").screenshot(); fz.evaluate("document.getElementById('plateTest').remove()")
    counts = fz.evaluate("""async src => { const im = new Image(); im.src = src; await im.decode();
        const c = document.createElement('canvas'), g = c.getContext('2d'); c.width = im.width; c.height = im.height; g.drawImage(im, 0, 0);
        const d = g.getImageData(0, 0, c.width, c.height).data, out = [0, 0];
        for (let i = 0; i < d.length; i += 4) { const r = d[i], gg = d[i + 1], bl = d[i + 2];
            if ((bl > 140 && r < 100 && gg < 100) || (r > 200 && gg > 150 && bl < 120)) out[(i / 4 / c.width) < c.height / 2 ? 0 : 1]++; }
        return out; }""", "data:image/png;base64," + base64.b64encode(png).decode())
    check("the fisherman baked into the photo is gone (shirt and hat colours in his spot: photo vs patched)",
          counts[0] > 800 and counts[1] < counts[0] * .02, str(counts))
    fz.close()

    rmf = b.new_page(viewport={"width": 360, "height": 640}, reduced_motion="reduce")
    rmf.on("pageerror", lambda e: errs.append(str(e)))
    rmf.goto(URL); rmf.evaluate("localStorage.clear()"); rmf.reload(); rmf.wait_for_timeout(200); start_new(rmf, "Calm")
    rmf.evaluate("() => { island = 'harbor'; go('fishing'); }"); rmf.wait_for_timeout(400)
    still = []
    for _ in range(6): still.append(rmf.evaluate("[fisherPose(), Math.round(fisherTip().x), Math.round(fisherTip().y)]")); rmf.wait_for_timeout(300)
    rmf.evaluate("() => { F = { phase: 'waiting', castAt: performance.now() - 2000 }; }"); rmf.wait_for_timeout(100)
    wait_still = []
    for _ in range(4): wait_still.append(rmf.evaluate("[fisherPose(), Math.round(fisherTip().x), Math.round(fisherTip().y)]")); rmf.wait_for_timeout(250)
    rmf.evaluate("() => stopFishing()")
    check("prefers-reduced-motion emulated: the fisherman still animates (idle breathing and the waiting dip move the rod tip, as without the setting)",
          still[0][0] == "idle" and len({tuple(x) for x in still}) > 1 and wait_still[0][0] == "waiting" and len({tuple(x) for x in wait_still}) > 1,
          f"{still[:3]} {wait_still[:3]}")
    rmf.close()

    # ---------- island pictures (tools/make_backgrounds.py) on the fishing screen and the Town Map ----------
    PICS = ["frost", "desert", "forest", "secret"]
    MASKS = {i: "data:image/png;base64," + base64.b64encode((Path(__file__).parent / "tools" / "water_masks" / f"{i}.png").read_bytes()).decode() for i in PICS}
    ON_WATER = """async ([src, x, y]) => { const im = new Image(); im.src = src; await im.decode();     // water mask: 1 art pixel = 4 image pixels
        const c = document.createElement('canvas'), g = c.getContext('2d'); c.width = im.width; c.height = im.height; g.drawImage(im, 0, 0);
        const ax = Math.floor(x / 4), ay = Math.floor(y / 4), d = g.getImageData(ax - 3, ay - 2, 7, 5).data;
        for (let i = 0; i < d.length; i += 4) if (d[i] < 128) return false; return true; }"""
    UNLOCK = "() => { ['harbor','frost','desert','forest'].forEach(i => S.mastery[i] = true); save(); }"
    ip = b.new_page(viewport={"width": 1366, "height": 768})
    ip.on("pageerror", lambda e: errs.append(str(e))); ip.on("console", lambda m: m.type == "error" and errs.append(m.text))
    ip.goto(URL); ip.evaluate("localStorage.clear()"); ip.reload(); ip.wait_for_timeout(200); start_new(ip, "Islands")
    ip.add_style_tag(content="#toast { display: none !important; }")
    ip.wait_for_function("Object.values(SCENES).every(s => s.img || s.failed)", timeout=8000)
    sizes = ip.evaluate("Object.fromEntries(Object.entries(SCENES).map(([k, s]) => [k, s.img ? [s.img.naturalWidth, s.img.naturalHeight] : null]))")
    check("every island picture loads after the Title screen (naturalWidth > 0)",
          all(sizes[k] and sizes[k][0] > 0 for k in sizes) and all(sizes[k] == [1920, 800] for k in PICS), str(sizes))
    pngs = {i: (Path(__file__).parent / "assets" / f"{i}.png").stat().st_size for i in PICS}
    check("island PNGs are under 400 KB", all(v < 400 * 1024 for v in pngs.values()), str(pngs))
    ip.evaluate(UNLOCK); ip.evaluate(SPY)
    for isl in ["harbor"] + PICS:
        ip.evaluate(f"() => {{ island = '{isl}'; go('fishing'); }}"); ip.wait_for_timeout(300)
        seen = {}
        def at(label):
            seen[label] = ip.evaluate(STATE)
        at("idle"); ip.click("#actBtn"); at("casting")
        ip.wait_for_function("F.phase === 'waiting'"); ip.wait_for_timeout(150); at("waiting")
        bob = ip.evaluate("[CROP.sx + F.bobPos.x * CROP.sw, CROP.sy + F.bobPos.y * CROP.sh, SCENES[island].img === null || !!SCENES[island].img]")
        ip.screenshot(path=str(SHOTS / f"43_island_{isl}.png"))
        ip.wait_for_function("F.phase === 'bite'", timeout=8000); at("bite")
        ip.click("#actBtn"); ip.wait_for_timeout(100); at("reeling")
        while ip.evaluate("F.phase") == "reeling":
            ip.wait_for_function("F.phase !== 'reeling' || (F.pos < F.zoneX - 0.05 || F.pos > F.zoneX + F.zoneW + 0.05)", timeout=8000, polling=5)
            if ip.evaluate("F.phase") == "reeling": ip.click("#actBtn"); ip.wait_for_timeout(30)
        at("escaped")
        ip.evaluate("fisherEvent('caught')"); at("caught")                         # the celebration pose, as after a catch
        poses = {k: v["pose"] for k, v in seen.items()}
        check(f"{isl}: fisherman pose follows the phase (all 7 poses)", all(poses[k] == k for k in poses) and len(poses) == 7, str(poses))
        check(f"{isl}: the fisherman wears the {isl} outfit (BUG-18)", ip.evaluate("[SCENES[island].fisher.outfit, fisherOutfit()]") == [isl, isl])
        gaps = {k: v["gap"] for k, v in seen.items() if v["phase"] != "idle"}
        check(f"{isl}: the line starts at the rod tip in every phase (<= 2px)", len(gaps) == 4 and all(g is not None and g <= 2 for g in gaps.values()),
              str({k: None if g is None else round(g, 2) for k, g in gaps.items()}))
        tops = [v["top"] for v in seen.values()]
        check(f"{isl}: CAST button stays put in every phase", max(tops) - min(tops) <= 1, str([round(t, 1) for t in tops]))
        if isl in PICS:
            check(f"{isl}: the bobber lands on water", ip.evaluate(ON_WATER, [MASKS[isl], bob[0], bob[1]]), f"image px {bob[0]:.0f},{bob[1]:.0f}")
        ip.wait_for_timeout(1500)
    for vw, vh in [(1366, 768), (360, 640)]:
        ip.set_viewport_size({"width": vw, "height": vh}); ip.evaluate("() => go('map')"); ip.wait_for_timeout(300)
        cards = ip.evaluate("""() => Object.fromEntries(['harbor','frost','desert','forest','secret'].map(i => { const c = document.querySelector('.island.bg-' + i), r = c.getBoundingClientRect();
            return [i, [getComputedStyle(c).backgroundImage.includes(i === 'harbor' ? 'assets/harbor_clean.jpg' : `assets/${i}.png`), r.width > 0 && r.right <= innerWidth]]; }))""")
        check(f"{vw}x{vh}: Town Map cards show the island pictures, no side scroll", all(all(v) for v in cards.values()) and no_side_scroll(ip, vw), str(cards))
        ip.screenshot(path=str(SHOTS / f"44_map_{vw}x{vh}.png"), full_page=True)
    ip.evaluate("() => { S.mastery = {}; save(); render(); }"); ip.wait_for_timeout(100)
    locked = ip.evaluate("(() => { const c = document.querySelector('.island.bg-secret'); return [c.classList.contains('locked'), getComputedStyle(c).backgroundImage.includes('secret.png'), c.textContent]; })()")
    check("locked secret card stays '???' without the picture", locked[0] and not locked[1] and "???" in locked[2], str(locked))
    ip.close()

    # ---------- Harbor card without the baked-in fisherman, island outfits (see docs/bug_log.md BUG-18) ----------
    ASSET = lambda n: "data:image/jpeg;base64," + base64.b64encode((Path(__file__).parent / "assets" / n).read_bytes()).decode()
    oc = b.new_page(viewport={"width": 1366, "height": 768})
    oc.on("pageerror", lambda e: errs.append(str(e))); oc.on("console", lambda m: m.type == "error" and errs.append(m.text))
    oc.goto(URL); oc.evaluate("localStorage.clear()"); oc.reload(); oc.wait_for_timeout(200); start_new(oc, "Outfits")
    oc.add_style_tag(content="#toast { display: none !important; }")
    # the file vs the game's own clean plate, in the spot where the photo's fisherman sits (photo pixels 190..290 x 174..314)
    cmp = oc.evaluate("""async ([photo, clean]) => {
        const load = async s => { const im = new Image(); im.src = s; await im.decode(); return im; }, P = await load(photo), C = await load(clean);
        const px = src => { const c = document.createElement('canvas'), g = c.getContext('2d'); c.width = 100; c.height = 140;
            g.drawImage(src, 190, 174, 100, 140, 0, 0, 100, 140); return g.getImageData(0, 0, 100, 140).data; };
        const a = px(P), b = px(cleanPlate(P, SCENES.harbor.fisher)), c = px(C), diff = (x, y) => { let s = 0; for (let i = 0; i < x.length; i += 4)
            s += Math.abs(x[i] - y[i]) + Math.abs(x[i + 1] - y[i + 1]) + Math.abs(x[i + 2] - y[i + 2]); return s / (x.length / 4) / 3; };
        const figure = d => { let n = 0; for (let i = 0; i < 100 * 81 * 4; i += 4) {   /* his shirt and hat, over the water */ const r = d[i], gg = d[i + 1], bl = d[i + 2];
            if ((bl > 140 && r < 100 && gg < 100) || (r > 200 && gg > 150 && bl < 120)) n++; } return n; };
        return { size: [C.naturalWidth, C.naturalHeight], vsPlate: diff(c, b), vsPhoto: diff(c, a), photoFig: figure(a), cleanFig: figure(c) }; }""",
        [ASSET("harbor.jpg"), ASSET("harbor_clean.jpg")])
    check("harbor_clean.jpg = the clean plate (same size, matches cleanPlate, differs from the photo where the fisherman sat)",
          cmp["size"] == [1373, 455] and cmp["vsPlate"] < 4 and cmp["vsPhoto"] > 15 and cmp["cleanFig"] < cmp["photoFig"] * .02 and cmp["photoFig"] > 800,
          json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in cmp.items()}))
    # the card on screen: shirt-blue / straw-hat pixels in his spot (photo 190..290 x 174..255 mapped onto the card, like
    # background 20% 40% / cover inside the 4px border) with the clean picture vs the same card showing the old photo
    SPOT = """() => { const c = document.querySelector('.island.bg-harbor'), w = c.clientWidth, h = c.clientHeight, k = Math.max(w / 1373, h / 455);
        const ox = 4 + (w - 1373 * k) * .2, oy = 4 + (h - 455 * k) * .4;
        // clipped to inside the card's 4px border + 3px gold frame, so the frame's gold never counts as straw-hat pixels
        const x0 = Math.max(8, ox + 190 * k), y0 = Math.max(8, oy + 174 * k), x1 = Math.min(w, ox + 290 * k), y1 = Math.min(h, oy + 255 * k);
        return [Math.round(x0), Math.round(y0), Math.round(x1 - x0), Math.round(y1 - y0)]; }"""
    FIG = """async ([src, r]) => { const im = new Image(); im.src = src; await im.decode();
        const c = document.createElement('canvas'), g = c.getContext('2d'); c.width = im.width; c.height = im.height; g.drawImage(im, 0, 0);
        const d = g.getImageData(r[0], r[1], r[2], r[3]).data; let n = 0;
        for (let i = 0; i < d.length; i += 4) { const r = d[i], gg = d[i + 1], bl = d[i + 2]; if ((bl > 140 && r < 100 && gg < 100) || (r > 200 && gg > 150 && bl < 120)) n++; }
        return n; }"""
    for vw, vh in [(1366, 768), (360, 640)]:
        oc.set_viewport_size({"width": vw, "height": vh}); oc.evaluate("() => go('map')"); oc.wait_for_timeout(300)
        oc.wait_for_function("(() => { const im = new Image(); im.src = 'assets/harbor_clean.jpg'; return im.complete && im.naturalWidth > 0; })()")
        card = oc.locator(".island.bg-harbor"); oc.add_style_tag(content=".island.bg-harbor > * { visibility: hidden; }")
        clean = card.screenshot(path=str(SHOTS / f"51_harbor_card_{vw}.png"))
        oc.evaluate("document.querySelector('.island.bg-harbor').style.background = 'url(assets/harbor.jpg) 20% 40% / cover'"); oc.wait_for_timeout(100)
        old = card.screenshot(); oc.evaluate("document.querySelector('.island.bg-harbor').style.background = ''")
        spot = oc.evaluate(SPOT)
        n_clean, n_old = (oc.evaluate(FIG, ["data:image/png;base64," + base64.b64encode(x).decode(), spot]) for x in (clean, old))
        bg = oc.evaluate("getComputedStyle(document.querySelector('.island.bg-harbor')).backgroundImage")
        check(f"{vw}x{vh}: Harbor map card shows no fisherman (clean picture first, old photo behind it as fallback), no side scroll",
              n_old > 40 and n_clean < n_old * .05 and bg.index("harbor_clean.jpg") < bg.index("harbor.jpg") and no_side_scroll(oc, vw), f"figure px in his spot {spot}: clean {n_clean} vs photo {n_old}")
        oc.add_style_tag(content=".island.bg-harbor > * { visibility: visible; }")
    oc.set_viewport_size({"width": 1366, "height": 768}); oc.evaluate("() => go('titleScreen')"); oc.wait_for_timeout(200)
    check("Title screen keeps the original harbor.jpg cover art (with the fisherman)",
          oc.evaluate("document.querySelector('#titleScreen .title-bg').getAttribute('src')") == "assets/harbor.jpg")
    # every outfit: its own pixels, the same frame size, the same rod tip and hands in every pose
    out = oc.evaluate("""() => { const names = Object.keys(OUTFITS), poses = ['idle', 'casting', 'waiting', 'bite', 'reeling', 'caught', 'escaped'], res = {};
        const c = document.createElement('canvas'), g = c.getContext('2d'); c.width = 300; c.height = 300;
        const hash = d => { let h = 2166136261; for (let i = 0; i < d.length; i++) h = Math.imul(h ^ d[i], 16777619); return (h >>> 0).toString(16); };
        for (const n of names) {
            const f = fFrame(0, n); res[n] = { hash: hash(f.getContext('2d').getImageData(0, 0, f.width, f.height).data), size: [f.width, f.height], tips: [], ok: true };
            for (const p of poses) for (const t of [0, 1000, 2600]) { g.clearRect(0, 0, 300, 300); FISHER.pose = '';
                try { drawFisherman(g, { x: 60, y: 140, p: 3, outfit: n }, p, t, false); res[n].tips.push(Math.round(FISHER.tipX) + ',' + Math.round(FISHER.tipY)); }
                catch (e) { res[n].ok = false; } }
        } return res; }""")
    check("each island draws a different outfit (5 different pixel hashes)", len({v["hash"] for v in out.values()}) == 5 and set(out) == {"harbor", "frost", "desert", "forest", "secret"},
          str({k: v["hash"] for k, v in out.items()}))
    check("every outfit keeps the sprite size and the exact rod tip in all 7 poses",
          all(v["ok"] and v["size"] == out["harbor"]["size"] and v["tips"] == out["harbor"]["tips"] for v in out.values()), str({k: v["tips"][:3] for k, v in out.items()}))
    # ---------- Playtest 1, part 3: all rods looked the same -> each rod has its own style, the tip and the angle stay the same ----------
    rd = oc.evaluate("""() => { const outs = Object.keys(OUTFITS), poses = ['idle', 'casting', 'waiting', 'bite', 'reeling', 'caught', 'escaped'], rods = Object.keys(ROD_STYLES);
        const c = document.createElement('canvas'), g = c.getContext('2d'); c.width = 300; c.height = 300;
        const hash = d => { let h = 2166136261; for (let i = 0; i < d.length; i++) h = Math.imul(h ^ d[i], 16777619); return (h >>> 0).toString(16); };
        const r = { rods, keys: {}, hashes: {}, tipsSame: true, inside: true, ok: true, tipsBad: [], sparkle: {}, still: {} };
        for (const o of outs) for (const ps of poses) for (const t of [0, 1000, 2600]) {
            const tips = [];
            for (const rod of rods) { g.clearRect(0, 0, 300, 300); FISHER.pose = '';
                try { drawFisherman(g, { x: 60, y: 140, p: 3, outfit: o, rod }, ps, t, false); } catch (e) { r.ok = false; }
                const tp = fisherTip(); tips.push(Math.round(tp.x) + ',' + Math.round(tp.y)); r.keys[rod] = fisherRodStyle();
                if (!(tp.x >= 0 && tp.x <= 300 && tp.y >= 0 && tp.y <= 300)) { r.inside = false; r.tipsBad.push([o, ps, rod, tp.x, tp.y]); }
                if (o === 'harbor' && t === 1000) (r.hashes[rod] = r.hashes[rod] || []).push(hash(g.getImageData(0, 0, 300, 300).data)); }
            if (new Set(tips).size !== 1) { r.tipsSame = false; r.tipsBad.push([o, ps, tips.join(' | ')]); } }
        const shot = (t, still) => { g.clearRect(0, 0, 300, 300); FISHER.pose = ''; drawFisherman(g, { x: 60, y: 140, p: 3, outfit: 'harbor', rod: 'lucky' }, 'idle', t, still); return hash(g.getImageData(0, 0, 300, 300).data); };
        r.sparkle = [shot(0, false), shot(500, false), shot(1000, false)]; r.still = [shot(0, true), shot(500, true), shot(1000, true)];
        return r; }""")
    check("rod styles: bamboo, sturdy, precision and lucky each draw under their own key (fisherRodStyle) for every outfit and pose, with no errors",
          rd["ok"] and rd["rods"] == ["bamboo", "sturdy", "precision", "lucky"] and rd["keys"] == {k: k for k in rd["rods"]}, str(rd["keys"]))
    check("the four rods draw four different pictures in every pose (pixel hashes all different)",
          all(len({rd["hashes"][k][i] for k in rd["rods"]}) == 4 for i in range(7)), str({k: v[:2] for k, v in rd["hashes"].items()}))
    check("the line start (fisherTip) is the same for all 4 rods in all 5 outfits x 7 poses and always inside the canvas (rod angle unchanged)",
          rd["tipsSame"] and rd["inside"], str(rd["tipsBad"][:3]))
    check("Lucky Rod charm sparkles with a 2-frame loop (500 ms), but not with reduced motion (still frame)",
          rd["sparkle"][0] != rd["sparkle"][1] and rd["sparkle"][0] == rd["sparkle"][2] and len(set(rd["still"])) == 1, f"{rd['sparkle']} {rd['still']}")
    # contact sheet: every outfit (rows) in every pose (columns) over its own island picture
    oc.set_viewport_size({"width": 1600, "height": 900})
    oc.wait_for_function("Object.values(SCENES).every(s => s.img || s.failed)", timeout=8000)
    oc.evaluate("""() => { const sc = SCENES.harbor; if (!sc.plate) sc.plate = cleanPlate(sc.img, sc.fisher);
        const isl = ['harbor', 'frost', 'desert', 'forest', 'secret'], poses = ['idle', 'casting', 'waiting', 'bite', 'reeling', 'caught', 'escaped'];
        const p = 3, AW = 72, AH = 58, cw = AW * p, ch = AH * p, c = document.createElement('canvas'), g = c.getContext('2d');
        c.id = 'outfitSheet'; c.width = cw * poses.length; c.height = ch * isl.length; c.style.cssText = 'position:fixed;left:0;top:0;z-index:9999'; g.imageSmoothingEnabled = false;
        isl.forEach((k, r) => poses.forEach((ps, col) => { const s = SCENES[k], fc = s.fisher, k2 = fc.scale;
            g.save(); g.beginPath(); g.rect(col * cw, r * ch, cw, ch); g.clip();
            g.drawImage(s.plate || s.img, fc.x - 8 * k2, fc.y - 18 * k2, AW * k2, AH * k2, col * cw, r * ch, cw, ch);
            FISHER.pose = ''; drawFisherman(g, { x: col * cw + 8 * p, y: r * ch + 18 * p, p, outfit: k }, ps, 1000, true); g.restore(); }));
        document.body.appendChild(c); }""")
    oc.locator("#outfitSheet").screenshot(path=str(SHOTS / "outfits_contact.png"))
    oc.evaluate("document.getElementById('outfitSheet').remove()")
    # contact sheet: every rod x every outfit (rows) in every pose (columns), in the rod's own colours
    oc.evaluate("""() => { const isl = ['harbor', 'frost', 'desert', 'forest', 'secret'], rods = Object.keys(ROD_STYLES), poses = ['idle', 'casting', 'waiting', 'bite', 'reeling', 'caught', 'escaped'];
        const p = 2, AW = 72, AH = 58, cw = AW * p, ch = AH * p, c = document.createElement('canvas'), g = c.getContext('2d'); c.id = 'rodSheet';
        c.width = cw * poses.length; c.height = ch * isl.length * rods.length; c.style.cssText = 'position:fixed;left:0;top:0;z-index:9999'; g.imageSmoothingEnabled = false;
        rods.forEach((rod, ri) => isl.forEach((k, r) => poses.forEach((ps, col) => { const s = SCENES[k], fc = s.fisher, k2 = fc.scale, row = ri * isl.length + r;
            g.save(); g.beginPath(); g.rect(col * cw, row * ch, cw, ch); g.clip();
            g.drawImage(s.plate || s.img, fc.x - 8 * k2, fc.y - 18 * k2, AW * k2, AH * k2, col * cw, row * ch, cw, ch);
            FISHER.pose = ''; drawFisherman(g, { x: col * cw + 8 * p, y: row * ch + 18 * p, p, outfit: k, rod }, ps, 1000, true); g.restore(); })));
        document.body.appendChild(c); }""")
    oc.locator("#rodSheet").screenshot(path=str(SHOTS / "99_rods_contact.png"))
    oc.close()

    # a picture that can't load: the island keeps its painted scene and gradient card, with no JavaScript errors
    bc = b.new_context(viewport={"width": 1366, "height": 768}); bp = bc.new_page(); page_errs = []
    bp.on("pageerror", lambda e: page_errs.append(str(e)))
    bp.route("**/assets/frost.png", lambda r: r.abort())
    bp.goto(URL); bp.evaluate("localStorage.clear()"); bp.reload(); bp.wait_for_timeout(200); start_new(bp, "Offline")
    bp.wait_for_function("SCENES.frost.failed", timeout=5000)
    bp.evaluate("() => { island = 'frost'; go('fishing'); }"); bp.wait_for_timeout(400)
    fb = bp.evaluate("[!SCENES.frost.img, !!sceneBg && sceneBg.key.startsWith('frost'), getComputedStyle(document.getElementById('actBtn')).display]")
    bp.click("#actBtn"); bp.wait_for_function("F.phase === 'waiting'"); bp.wait_for_timeout(200)
    bp.screenshot(path=str(SHOTS / "45_frost_fallback.png")); bp.evaluate("() => stopFishing(); go('map')"); bp.wait_for_timeout(200)
    grad = bp.evaluate("getComputedStyle(document.querySelector('.island.bg-frost')).backgroundImage.includes('linear-gradient(rgb(207, 233, 255)')")
    check("a blocked picture falls back to the painted scene and the gradient card, no JavaScript errors",
          fb[0] and fb[1] and grad and not page_errs, f"{fb} gradient {grad} errors {page_errs[:2]}")
    bc.close()

    # ---------- full-screen Title art ----------
    TITLE = """(() => { const img = document.querySelector('#titleScreen .title-bg'), r = img.getBoundingClientRect(), cs = getComputedStyle(img);
        const btns = ['newBtn', 'contBtn', 'howBtn', 'soundBtn', 'musicBtn'].map(id => { const b = document.getElementById(id).getBoundingClientRect(),
            hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2), hb = hit && hit.closest('button');
            return [b.top >= 0 && b.bottom <= innerHeight && b.left >= 0 && b.right <= innerWidth, !!hb && hb.id === id, Math.round(b.top), Math.round(b.left)]; });
        const logo = document.querySelector('#titleScreen .logo').getBoundingClientRect();
        return { cover: r.left <= 0 && r.top <= 0 && r.right >= innerWidth && r.bottom >= innerHeight, fit: cs.objectFit, pix: cs.imageRendering,
                 btns, logoTop: logo.top / innerHeight, old: !!document.querySelector('#titleScreen .hero, #titleScreen .clouds, #titleScreen .water'),
                 shimmer: getComputedStyle(document.querySelector('.title-shimmer')).animationName,
                 sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, vw: innerWidth, vh: innerHeight }; })()"""
    for vw, vh in [(1920, 1080), (1366, 768), (360, 640)]:
        tp = b.new_page(viewport={"width": vw, "height": vh})
        tp.on("pageerror", lambda e: errs.append(str(e)))
        tp.goto(URL); tp.evaluate("localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Art', coins: 300 }))"); tp.reload(); tp.wait_for_timeout(700)
        r = tp.evaluate(TITLE)
        check(f"{vw}x{vh}: Title picture covers the whole screen (cover, pixelated), no frame, no pixel clouds or dashes",
              r["cover"] and r["fit"] == "cover" and r["pix"] == "pixelated" and not r["old"] and r["shimmer"] == "title-shimmer", str({k: r[k] for k in ("cover", "fit", "pix", "old", "shimmer")}))
        check(f"{vw}x{vh}: all 5 Title buttons visible and clickable, sign near the top",
              all(x[0] and x[1] for x in r["btns"]) and r["logoTop"] < .25, str(r["btns"]) + f" logo {r['logoTop']:.2f}")
        check(f"{vw}x{vh}: Title has no side or page scroll", r["sw"] <= r["vw"] and r["sh"] <= r["vh"], f"{r['sw']}x{r['sh']}")
        if vw == 360:
            check("360x640: the 5 Title buttons are stacked at the bottom: NEW | CONTINUE, HOW TO PLAY across, SOUND | MUSIC (3 rows, 2 columns)",
                  len({x[2] for x in r["btns"]}) == 3 and len({x[3] for x in r["btns"]}) == 2 and min(x[2] for x in r["btns"]) > vh * .5, str(r["btns"]))
        tp.screenshot(path=str(SHOTS / f"41_title_{vw}x{vh}.png"))
        tp.click("#howBtn"); tp.wait_for_timeout(200); ok_how = tp.is_visible("#howBox"); tp.click("#howOk"); tp.wait_for_timeout(100)
        tp.click("#soundBtn"); ok_sound = "OFF" in tp.inner_text("#soundBtn"); tp.click("#soundBtn")
        tp.click("#contBtn"); tp.wait_for_timeout(300)
        check(f"{vw}x{vh}: Title buttons still work (HOW TO PLAY, SOUND, CONTINUE)", ok_how and ok_sound and tp.is_visible("#home"))
        check(f"{vw}x{vh}: Home keeps its framed layout (top bar, no full-screen picture, no BACK bar)",
              tp.is_visible("#title") and not tp.is_visible(".title-bg") and not tp.is_visible("#navBack"))
        tp.close()

    # ---------- polish: Forest picture, island progress line, Town Map text (see docs/bug_log.md BUG-14..16) ----------
    fp = b.new_page(viewport={"width": 1280, "height": 720})
    fp.on("pageerror", lambda e: errs.append(str(e))); fp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    fp.goto(URL)
    FOREST = "data:image/png;base64," + base64.b64encode((Path(__file__).parent / "assets" / "forest.png").read_bytes()).decode()
    fr = fp.evaluate("""async src => { const im = new Image(); im.src = src; await im.decode();     // art pixels: image / 4, horizon at art row 88
        const c = document.createElement('canvas'), g = c.getContext('2d'); c.width = 480; c.height = 200; g.imageSmoothingEnabled = false;
        g.drawImage(im, 0, 0, 480, 200); const d = g.getImageData(0, 0, 480, 200).data, white = (x, y) => d[(y * 480 + x) * 4] > 245 && d[(y * 480 + x) * 4 + 1] > 245 && d[(y * 480 + x) * 4 + 2] > 245;
        let sky = 0, foam = 0;
        for (let y = 0; y < 70; y++) for (let x = 0; x < 260; x++) sky += white(x, y);                 // top-left sky (old sunbeam dots)
        for (let y = 88; y < 92; y++) for (let x = 384; x < 416; x++) foam += white(x, y);              // foam on the water line under the fall
        // the old block: a solid white bar 26 px wide just above the water with trees (not the fall) right under it
        let bar = 0; for (let x = 386; x < 416; x++) bar += white(x, 85) && white(x, 86) && white(x, 87);
        return { sky, foam, bar }; }""", FOREST)
    check("Forest picture: no white dots in the top-left sky, foam sits on the water line (no floating white bar)",
          fr["sky"] == 0 and fr["foam"] >= 40 and fr["bar"] < 20, str(fr))

    fp.evaluate("localStorage.clear()"); fp.reload(); fp.wait_for_timeout(200); start_new(fp, "Prog")
    fp.add_style_tag(content="#toast { display: none !important; }")
    PROG = """(() => { const p = document.getElementById('isleProg'), a = document.getElementById('actBtn').getBoundingClientRect(), r = p.getBoundingClientRect(),
        g = document.querySelector('#fishing .gearbar').getBoundingClientRect();
        return { text: p.innerText.replace(/\\s+/g, ' '), vis: getComputedStyle(p).visibility, meter: getComputedStyle(document.getElementById('meter')).visibility,
                 bar: parseFloat(p.querySelector('.ip-bar > span').style.width), top: a.top + scrollY, fits: r.top >= g.bottom - 1 && r.bottom <= a.top + 1,
                 clip: [...p.children].every(c => c.scrollWidth <= c.clientWidth + 1) }; })()"""
    fp.evaluate("() => { S.discovered = { harbor_0: true, harbor_1: true, harbor_2: true, frost_0: true }; S.mastery = { desert: true };"
                " FISH.filter(f => f.island === 'desert').forEach(f => S.discovered[f.id] = true); save(); }")
    expect = {"harbor": ("Harbor: 3 / 10 found", "Mastery reward: Golden Hook", 30), "frost": ("Frost: 1 / 10 found", "Steady Hands", 10),
              "desert": ("Desert: 10 / 10 found", "Mastered! Lucky Lure is active", 100), "forest": ("Forest: 0 / 10 found", "Master's Charm", 0),
              "secret": ("Little Lake: 0 / 1 found", "Lake Guardian", 0)}
    for vw, vh in [(1280, 720), (360, 640)]:
        fp.set_viewport_size({"width": vw, "height": vh})
        for isl, (t1, t2, pc) in expect.items():
            fp.evaluate(f"() => {{ island = '{isl}'; go('fishing'); }}"); fp.wait_for_timeout(150)
            pr = fp.evaluate(PROG)
            check(f"{vw}x{vh} {isl}: progress line '{t1}' with bar and reward text, fits between the chips and CAST",
                  t1 in pr["text"] and t2 in pr["text"] and pr["vis"] == "visible" and pr["meter"] == "hidden" and pr["bar"] == pc and pr["fits"] and pr["clip"], str(pr))
        if vw == 360: fp.screenshot(path=str(SHOTS / "46_mobile_progress.png"))
    fp.set_viewport_size({"width": 1280, "height": 720})
    fp.evaluate("() => { island = 'harbor'; go('fishing'); }"); fp.wait_for_timeout(200)
    fp.screenshot(path=str(SHOTS / "47_progress.png"))
    before = fp.evaluate(PROG)
    fp.evaluate("() => { const r = Math.random; Math.random = () => .01; F = { phase: 'idle', fish: fishById('harbor_9') }; caught(true); Math.random = r; }")
    during = fp.evaluate(PROG)
    fp.wait_for_timeout(900); fp.click("#keepBtn"); fp.wait_for_timeout(500)          # after the 280 ms screen fade-in
    after = fp.evaluate(PROG)
    check("progress line updates right after a catch (and after KEEP)",
          "Harbor: 3 / 10" in before["text"] and "Harbor: 4 / 10" in during["text"] and "Harbor: 4 / 10" in after["text"] and after["bar"] == 40,
          f"{before['text'][:22]} | {during['text'][:22]} | {after['text'][:22]}")
    fp.click("#actBtn"); fp.wait_for_function("F.phase === 'bite'", timeout=8000); fp.click("#actBtn"); fp.wait_for_timeout(100)
    reel = fp.evaluate(PROG)
    check("while reeling the meter replaces the progress line, CAST/REEL doesn't move",
          reel["vis"] == "hidden" and reel["meter"] == "visible" and abs(reel["top"] - after["top"]) <= 1, f"{reel['vis']} {reel['meter']} {reel['top']} {after['top']}")
    fp.evaluate("() => stopFishing()")
    for vw, vh in [(1280, 720), (360, 640)]:
        fp.set_viewport_size({"width": vw, "height": vh}); fp.evaluate("() => go('map')"); fp.wait_for_timeout(200)
        mp = fp.evaluate("""(() => { const c = document.querySelector('.island.bg-harbor'), r = c.getBoundingClientRect(), t = c.querySelector('.isl-plate').getBoundingClientRect();
            return [Math.round((t.top - r.top) / r.height * 100), t.left >= r.left && t.right <= r.right + .5 && t.bottom <= r.bottom + .5]; })()""")
        check(f"{vw}x{vh}: Harbor card: the progress plate sits in the lower part, the picture shows above it", mp[0] >= 35 and mp[1], str(mp))
        fp.screenshot(path=str(SHOTS / f"48_map_text_{vw}.png"))
    fp.close()

    # ---------- cleanup round (see docs/bug_log.md BUG-19..22) ----------
    # BUG-19: Export / Import Save was removed on purpose (owner decision: saving in this browser is enough)
    xc = b.new_context(viewport={"width": 1280, "height": 800}); x = xc.new_page()
    x.on("pageerror", lambda e: errs.append(str(e))); x.on("console", lambda m: m.type == "error" and errs.append(m.text))
    x.goto(URL); x.evaluate("localStorage.clear()"); x.reload(); x.wait_for_timeout(200)
    WORDS = re.compile(r"\bexport\b|\bimport\b|save code|savecode", re.I)
    seen = {}
    for sc in ["titleScreen", "home", "map", "bag", "shop", "tackle", "collection"]:
        if sc == "home": start_new(x, "Clean")
        else: x.evaluate(f"() => go('{sc}')")
        x.wait_for_timeout(120)
        txt = x.evaluate("document.documentElement.textContent")        # includes hidden popups and HOW TO PLAY
        seen[sc] = WORDS.findall(txt)
    ids = x.evaluate("['exportBtn', 'importBtn', 'titleImport', 'exportBox', 'importBox', 'exportCode', 'importCode'].filter(id => document.getElementById(id))")
    fns = x.evaluate("['exportCode', 'readCode', 'openExport', 'openImport'].filter(n => typeof window[n] !== 'undefined')")
    src = {f: WORDS.findall((Path(__file__).parent / f).read_text(encoding="utf-8")) for f in ["index.html", "css/style.css", "js/data.js", "js/state.js", "js/fisherman.js", "js/fishing.js", "js/screens.js"]}
    check("no Export / Import / save code anywhere (every screen, popups, HOW TO PLAY, the game files)",
          not any(seen.values()) and not ids and not fns and not any(src.values()), f"{ {k: v for k, v in seen.items() if v} } {ids} {fns} { {k: v for k, v in src.items() if v} }")
    x.evaluate("() => go('titleScreen')"); x.click("#howBtn"); x.wait_for_timeout(150)
    check("HOW TO PLAY (Saving): saved automatically in this browser, other browsers / devices / home-screen app have their own save",
          "Your progress is saved automatically in this browser on this device. A different browser, device or home-screen app has its own separate save."
          in x.inner_text("#howBox"))
    x.keyboard.press("Escape")
    check("normal saving still works (key littleLakeSave, CONTINUE)", x.evaluate(SAVED + ".name") == "Clean" and x.is_enabled("#contBtn"))
    xc.close()

    # BUG-20: Title sign fully visible on phones (100dvh, safe areas, no page scroll), at least 12px from the top edge
    SIGN = """(() => { const l = document.querySelector('#titleScreen .logo'), r = l.getBoundingClientRect(), m = new DOMMatrix(getComputedStyle(l).transform);
        const btns = ['newBtn', 'contBtn', 'howBtn', 'soundBtn', 'musicBtn'].map(id => { const b = document.getElementById(id).getBoundingClientRect(); return b.top >= 0 && b.bottom <= innerHeight; });
        return { top: r.top - m.m42 - 6, now: r.top, left: r.left, right: r.right, btns, vw: innerWidth, vh: innerHeight,
                 sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, viewport: document.querySelector('meta[name=viewport]').content }; })()"""
    def sign_ok(r): return r["top"] >= 12 and r["left"] >= 0 and r["right"] <= r["vw"] and all(r["btns"]) and r["sw"] <= r["vw"] and r["sh"] <= r["vh"]
    for vw, vh in [(390, 844), (375, 667), (360, 640), (390, 700)]:
        tp = b.new_page(viewport={"width": vw, "height": vh}); tp.on("pageerror", lambda e: errs.append(str(e)))
        tp.goto(URL); tp.wait_for_timeout(500); r = tp.evaluate(SIGN)
        tp.screenshot(path=str(SHOTS / f"52_title_sign_{vw}x{vh}.png"))
        check(f"{vw}x{vh}: Title sign >= 12px from the top (even at the top of its bob), 4 buttons on screen, no page scroll",
              sign_ok(r), f"top {r['top']:.1f} page {r['sw']}x{r['sh']}")
        tp.close()
    check("viewport-fit=cover is set (safe-area padding on iPhone)", "viewport-fit=cover" in r["viewport"])
    css = (Path(__file__).parent / "css" / "style.css").read_text(encoding="utf-8")
    check("Title uses 100dvh (100vh fallback) and env(safe-area-inset-top / bottom)",
          "height: 100vh; height: 100dvh" in css and "env(safe-area-inset-top)" in css and "env(safe-area-inset-bottom)" in css)
    # Playwright's WebKit with iPhone profiles (WebKit engine on this PC, not a real iPhone: no notch / toolbar)
    webkit = None
    try: webkit = p.webkit.launch()
    except Exception as e: print("NOTE WebKit not available:", str(e)[:120])
    if webkit:
        for dev in ["iPhone 13", "iPhone SE"]:
            wc = webkit.new_context(**p.devices[dev]); wp = wc.new_page(); werr = []
            wp.on("pageerror", lambda e: werr.append(str(e)))
            wp.goto(URL); wp.wait_for_timeout(700); r = wp.evaluate(SIGN)
            wp.screenshot(path=str(SHOTS / f"53_webkit_{dev.replace(' ', '_')}_title.png"))
            check(f"WebKit {dev} ({r['vw']}x{r['vh']}): Title sign >= 12px from the top, buttons on screen, no page scroll, no errors",
                  sign_ok(r) and not werr, f"top {r['top']:.1f} page {r['sw']}x{r['sh']} {werr[:1]}")
            wc.close()
        webkit.close()

    # BUG-21: sticky BACK bar on Home, Map, Bag, Shop, Collection, Tackle Box
    NAV = {"map": "TOWN MAP", "bag": "BAG", "shop": "SHOP", "collection": "COLLECTION", "tackle": "TACKLE BOX"}
    BAR = """(() => { const b = document.getElementById('navBack').getBoundingClientRect(), bar = document.getElementById('navbar').getBoundingClientRect(),
        hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2), first = document.querySelector('.screen.active').firstElementChild;
        const nb = document.getElementById('navbar'), f = first && first.getBoundingClientRect();
        return { vis: b.width > 0 && b.top >= 0 && b.bottom <= innerHeight && b.left >= 0 && b.right <= innerWidth, hit: !!hit && hit.closest('button') === document.getElementById('navBack'),
                 name: document.getElementById('navName').textContent, y: scrollY, sticky: getComputedStyle(nb.parentElement).position, barBottom: bar.bottom, firstTop: f ? f.top : 9999,
                 sw: document.documentElement.scrollWidth, vw: innerWidth, max: document.documentElement.scrollHeight - innerHeight }; })()"""
    for vw, vh in [(360, 640), (390, 844), (1366, 768)]:
        phone = vw < 900
        nc = b.new_context(viewport={"width": vw, "height": vh}); nv = nc.new_page()
        nv.on("pageerror", lambda e: errs.append(str(e))); nv.on("console", lambda m: m.type == "error" and errs.append(m.text))
        nv.goto(URL); nv.evaluate("localStorage.clear()"); nv.reload(); nv.wait_for_timeout(200); start_new(nv, "Nav")
        nv.evaluate("() => { S.coins = 5000; S.bagMax = 15; while (S.bag.length < 15) S.bag.push({ fishId: 'harbor_' + (S.bag.length % 10), weight: .5, price: 20, time: 1 }); save(); }")
        nv.add_style_tag(content="#toast { display: none !important; }")
        res = {}
        for sc, name in NAV.items():
            nv.evaluate(f"() => go('{sc}')"); nv.wait_for_timeout(350)
            top = nv.evaluate(BAR)
            nv.evaluate("window.scrollTo(0, 1500)"); nv.wait_for_timeout(150)
            down = nv.evaluate(BAR); res[sc] = (top, down)
            check(f"{vw}x{vh} {sc}: BACK + '{name}' visible at the top, still visible and clickable after scrolling 1500px down (scrolled {down['y']:.0f}px)",
                  top["vis"] and down["vis"] and down["hit"] and top["name"] == name and (down["sticky"] == "sticky" or not phone), f"{top['vis']} {down['vis']} {down['hit']} {top['name']}")
            check(f"{vw}x{vh} {sc}: the bar doesn't cover the screen's content, no side scroll",
                  top["barBottom"] <= top["firstTop"] and top["sw"] <= vw and down["sw"] <= vw, f"bar {top['barBottom']:.0f} content {top['firstTop']:.0f} sw {down['sw']}")
            if vw == 360 and sc in ("shop", "tackle"): nv.screenshot(path=str(SHOTS / f"54_back_scrolled_{sc}_{vw}.png"))
        if phone:
            check(f"{vw}x{vh}: phone Shop and Tackle Box pages really scrolled (to the bottom, or 1500px) while BACK stayed in view",
                  all(res[k][1]["y"] > 300 and res[k][1]["y"] >= min(1500, res[k][1]["max"]) - 1 for k in ("shop", "tackle")),
                  f"shop {res['shop'][1]['y']} tackle {res['tackle'][1]['y']}")
        nv.evaluate("() => go('home')"); nv.wait_for_timeout(150)
        check(f"{vw}x{vh}: no BACK bar on Home (root screen; MENU button instead)", not nv.is_visible("#navbar") and nv.is_visible("#menuBtn"))
        if vw == 360:
            # BACK returns to the screen the player came from
            nv.evaluate("() => { S.bag = []; S.bagMax = 5; save(); go('home'); }"); nv.click("section.active >> text=OPEN BAG"); nv.wait_for_timeout(200)
            nv.click("#navBack"); nv.wait_for_timeout(200)
            ok1 = nv.is_visible("#home")
            nv.click("section.active >> text=TOWN MAP"); nv.click(".island.bg-frost"); nv.wait_for_timeout(300)
            nav_on_fishing = nv.is_visible("#navBack")
            acts = nv.evaluate("[...document.querySelectorAll('#fishing .actions .btn')].map(b => b.id || b.dataset.go)")
            nv.click("#rodChip"); nv.wait_for_timeout(150); nv.click("#pickShop"); nv.wait_for_timeout(250)
            ok2a = nv.is_visible("#shop") and nv.inner_text("#navName") == "SHOP"
            nv.click("#navBack"); nv.wait_for_timeout(300)
            check("Fishing (Frost) > GO TO SHOP > BACK returns to the Fishing screen on the same island",
                  ok2a and nv.is_visible("#fishing") and nv.evaluate("island") == "frost" and "Frost" in nv.inner_text("#isleProg") and nv.is_enabled("#actBtn"), nv.inner_text("#isleProg"))
            check("Home > Bag > BACK returns to Home", ok1)
            check("no BACK bar on the Fishing screen; SHOP and TOWN MAP stay next to CAST", not nav_on_fishing and acts == ["actBtn", "fShopBtn", "map"], str(acts))
            nv.click("#fishing [data-go=map]"); nv.wait_for_timeout(200); nv.click("#navBack"); nv.wait_for_timeout(200)
            check("Map > Fishing > TOWN MAP > BACK goes back to where the map was opened from (Fishing)", nv.is_visible("#fishing"), nv.evaluate("current"))
            nv.evaluate("() => go('home')"); nv.click("#home [data-go=shop]"); nv.click("#shop [data-go=tackle]"); nv.wait_for_timeout(150)
            nv.click("#navBack"); nv.wait_for_timeout(150); a = nv.evaluate("current")
            nv.click("#shop [data-go=tackle]"); nv.click("#tackle [data-go=shop]"); nv.wait_for_timeout(150)
            trail = []
            for _ in range(3): nv.click("#navBack"); nv.wait_for_timeout(150); trail.append(nv.evaluate("current"))
            check("Shop > Tackle Box > BACK = Shop; Shop > Tackle > Shop then BACK x3 = Tackle, Shop, Home", a == "shop" and trail == ["tackle", "shop", "home"], f"{a} {trail}")
            nv.evaluate("() => { F = { phase: 'idle', fish: fishById('harbor_0') }; caught(); }"); nv.wait_for_timeout(200)
            on_result = [nv.is_visible("#result"), nv.is_visible("#navbar")]; nv.click("#releaseBtn"); nv.wait_for_timeout(200)
            check("no BACK bar on the Result screen", on_result == [True, False], str(on_result))
            # Esc closes a popup first and never leaves the screen while one is open; then Esc = BACK
            nv.evaluate("() => { stopFishing(); go('home'); go('shop'); openModal('howBox', 'howPanel'); }"); nv.wait_for_timeout(150)
            nv.keyboard.press("Escape"); nv.wait_for_timeout(150)
            e1 = [nv.is_visible("#howBox"), nv.evaluate("current")]
            nv.keyboard.press("Escape"); nv.wait_for_timeout(150)
            e2 = nv.evaluate("current"); nv.keyboard.press("Escape"); nv.wait_for_timeout(150)
            check("Esc with a popup open only closes the popup; then Esc works as BACK (but never leaves Home)",
                  e1 == [False, "shop"] and e2 == "home" and nv.evaluate("current") == "home", f"{e1} {e2} {nv.evaluate('current')}")
            nv.evaluate("() => go('collection')"); nv.evaluate("document.activeElement.blur()"); nv.keyboard.press("Tab")
            check("Tab order: BACK is the first control on a screen", nv.evaluate("document.activeElement.id") == "navBack", nv.evaluate("document.activeElement.id"))
        nc.close()

    # BUG-22: one fixed full-viewport backdrop behind every screen
    BD = """(() => { const bd = document.getElementById('backdrop'), r = bd.getBoundingClientRect(), on = document.querySelector('#backdrop .bd.on'), cs = getComputedStyle(on);
        const app = document.querySelector('.app');
        return { cover: r.left <= 0 && r.top <= 0 && r.right >= innerWidth && r.bottom >= innerHeight, pos: getComputedStyle(bd).position, top: r.top,
                 behind: +getComputedStyle(bd).zIndex < +getComputedStyle(app).zIndex, isle: on.dataset.isle, img: cs.backgroundImage, size: cs.backgroundSize,
                 pix: cs.imageRendering, ons: document.querySelectorAll('#backdrop .bd.on').length, shade: +getComputedStyle(document.querySelector('.bd-shade'), '::after').opacity,
                 att: getComputedStyle(document.body).backgroundAttachment, body: getComputedStyle(document.body).backgroundImage, y: scrollY }; })()"""
    # every visible text must sit on an opaque panel / button / card, never straight on the picture
    READ = """(() => { const bad = [];
        const solid = el => { const s = getComputedStyle(el); if (s.backgroundImage !== 'none') return true; const m = s.backgroundColor.match(/[\\d.]+/g); return m && (m.length < 4 || +m[3] >= .6); };
        for (const el of document.querySelectorAll('.app *, .toast')) {
            if (!el.offsetParent || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
            let a = el; while (a && a !== document.body && !solid(a)) a = a.parentElement;
            if (!a || a === document.body) bad.push(el.className || el.tagName);
        } return bad; })()"""
    for vw, vh in [(1600, 900), (1366, 768), (360, 640), (390, 844)]:
        dc = b.new_context(viewport={"width": vw, "height": vh}); d = dc.new_page()
        d.on("pageerror", lambda e: errs.append(str(e))); d.on("console", lambda m: m.type == "error" and errs.append(m.text))
        d.goto(URL); d.evaluate("localStorage.clear()"); d.reload(); d.wait_for_timeout(200)
        if vw in (1600, 390): d.screenshot(path=str(SHOTS / f"60_title_{vw}x{vh}.png"))
        start_new(d, "Backdrop")
        d.evaluate("() => { S.coins = 2000; ['harbor','frost','desert','forest'].forEach(i => { S.mastery[i] = true; FISH.filter(f => f.island === i).forEach(f => S.discovered[f.id] = true); });"
                   " S.bag = [{ fishId: 'frost_3', weight: 1.2, price: 80, time: 1 }]; save(); }")
        d.add_style_tag(content="#toast { display: none !important; }")
        d.wait_for_function("[...document.querySelectorAll('#backdrop .bd')].every(e => e.classList.contains('loaded') || e.classList.contains('failed'))", timeout=8000)
        loaded = d.evaluate("[...document.querySelectorAll('#backdrop .bd.loaded')].map(e => e.dataset.isle)")
        menu = {}
        for sc in ["home", *NAV]:
            d.evaluate(f"() => go('{sc}')"); d.wait_for_timeout(400)
            menu[sc] = d.evaluate(BD); unread = d.evaluate(READ)
            d.evaluate("window.scrollTo(0, 1500)"); d.wait_for_timeout(100); menu[sc + "_down"] = d.evaluate(BD); d.evaluate("window.scrollTo(0, 0)")
            check(f"{vw}x{vh} {sc}: all text sits on solid panels (readable over the backdrop)", not unread, str(unread[:4]))
            if vw in (1600, 390): d.screenshot(path=str(SHOTS / f"60_{sc}_{vw}x{vh}.png"))
        mv = list(menu.values())
        check(f"{vw}x{vh}: menu screens show harbor_clean.jpg (no fisherman) full-viewport, fixed while scrolling, cover + pixelated, ~35% shade",
              all(v["cover"] and v["pos"] == "fixed" and v["top"] == 0 and v["behind"] and v["isle"] == "harbor" and "harbor_clean.jpg" in v["img"] and "/harbor.jpg" not in v["img"]
                  and v["size"] == "cover" and v["pix"] == "pixelated" and v["ons"] == 1 and v["shade"] == 0 for v in mv)
              and (any(v["y"] > 0 for v in mv) or vw >= 900) and all(v["att"] != "fixed" and "url(" not in v["body"] for v in mv), str({k: (v["isle"], v["cover"], v["top"], v["y"]) for k, v in menu.items() if not v["cover"] or v["top"]}))
        isl_bd = {}
        for isl in ["harbor", "frost", "desert", "forest", "secret"]:
            d.evaluate(f"() => {{ island = '{isl}'; go('fishing'); }}"); d.wait_for_timeout(450)
            isl_bd[isl] = d.evaluate(BD)
            if vw in (1600, 390): d.screenshot(path=str(SHOTS / f"60_fishing_{isl}_{vw}x{vh}.png"))
        files = {"harbor": "harbor_clean.jpg", "frost": "frost.png", "desert": "desert.png", "forest": "forest.png", "secret": "secret.png"}
        check(f"{vw}x{vh}: Fishing backdrop changes with the island (5 pictures), full viewport, ~55% shade",
              all(v["isle"] == k and files[k] in v["img"] and v["cover"] and v["shade"] == 1 and v["ons"] == 1 for k, v in isl_bd.items()) and len(loaded) == 5,
              str({k: (v["isle"], v["img"][-30:]) for k, v in isl_bd.items()}) + f" loaded {loaded}")
        if vw in (1600, 390):
            d.evaluate("() => { F = { phase: 'idle', fish: fishById('desert_9') }; caught(); }"); d.wait_for_timeout(900)
            d.screenshot(path=str(SHOTS / f"60_result_{vw}x{vh}.png")); d.click("#releaseBtn")
        if vw == 1366:
            d.evaluate("() => { stopFishing(); island = 'harbor'; go('fishing'); }"); d.wait_for_timeout(400)
            fade = d.evaluate("""() => new Promise(r => { island = 'desert'; go('map'); go('fishing');  // harbor -> desert: both layers mid-fade after ~120 ms
                const t = getComputedStyle(document.querySelector('.bd')).transitionDuration;
                setTimeout(() => r([t, +getComputedStyle(document.querySelector('.bd-desert')).opacity, +getComputedStyle(document.querySelector('.bd-harbor')).opacity]), 120); })""")
            check("changing island crossfades the backdrop in about 300 ms", fade[0] == "0.3s" and 0 < fade[1] < 1 and 0 < fade[2] < 1, str(fade))
            check("old pixel clouds and water dashes are gone", d.evaluate("!document.querySelector('.bgfx, .clouds, .water')"))
        dc.close()
    rm2 = b.new_page(viewport={"width": 360, "height": 640}, reduced_motion="reduce"); rm2.goto(URL); rm2.wait_for_timeout(200)
    check("prefers-reduced-motion emulated: the backdrop still crossfades", rm2.evaluate("getComputedStyle(document.querySelector('.bd')).transitionDuration") != "0s")
    rm2.close()
    # a backdrop picture that can't load: its gradient stays, no JavaScript errors
    fc = b.new_context(viewport={"width": 1366, "height": 768}); fpg = fc.new_page(); f_errs = []
    fpg.on("pageerror", lambda e: f_errs.append(str(e))); fpg.route("**/assets/desert.png", lambda r: r.abort())
    fpg.goto(URL); fpg.evaluate("localStorage.clear()"); fpg.reload(); fpg.wait_for_timeout(200); start_new(fpg, "NoPic")
    fpg.wait_for_function("document.querySelector('.bd-desert').classList.contains('failed')", timeout=5000)
    fpg.evaluate("() => { island = 'desert'; go('fishing'); }"); fpg.wait_for_timeout(400)
    bgd = fpg.evaluate("getComputedStyle(document.querySelector('.bd-desert')).backgroundImage")
    check("a backdrop that fails to load keeps its gradient colour, no JavaScript errors", "linear-gradient" in bgd and "url(" not in bgd and not f_errs, f"{bgd[:60]} {f_errs[:1]}")
    fc.close()

    # ---------- BUG-23: every screen fits a laptop window without page scrolling ----------
    FIT = """sc => { const vh = innerHeight, vw = innerWidth, inView = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.top >= -0.5 && r.bottom <= vh + 0.5 && r.left >= 0 && r.right <= vw + 0.5; };
        const main = [...document.querySelectorAll('.screen.active .btn, .app > .top .btn, .app > .top .title, .app > .top .sign')]
            .filter(b => b.offsetParent && !b.closest('.scroll-list, .islands, .coll, .tabs'));
        return { page: document.documentElement.scrollHeight, vh, sw: document.documentElement.scrollWidth, vw,
                 out: main.filter(b => !inView(b)).map(b => (b.id || b.textContent.trim()).slice(0, 14)), n: main.length,
                 nav: !!document.getElementById('navbar').offsetParent }; }"""
    LIST = """sc => { const l = document.querySelector('#' + sc + ' .scroll-list'), cs = getComputedStyle(l), fade = getComputedStyle(l, '::after');
        const before = l.scrollTop; l.scrollTop = 1e6; const moved = l.scrollTop > before;
        const btns = [...document.querySelectorAll('#' + sc + ' > .btns .btn')].every(b => { const r = b.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; });
        const r = [cs.overflowY, l.scrollHeight > l.clientHeight + 4, moved, scrollY === 0 && document.documentElement.scrollHeight <= innerHeight + 1, btns,
                   fade.content !== 'none' && fade.position === 'sticky', cs.scrollbarWidth];
        l.scrollTop = 0; return r; }"""
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600)]:
        lc = b.new_context(viewport={"width": vw, "height": vh}); lp = lc.new_page()
        lp.on("pageerror", lambda e: errs.append(str(e))); lp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        lp.goto(URL); lp.evaluate("localStorage.clear()"); lp.reload(); lp.wait_for_timeout(200)
        if vw in (1536, 1366): lp.screenshot(path=str(SHOTS / f"70_title_{vw}x{vh}.png"))
        start_new(lp, "Laptop")
        lp.evaluate("() => { S.coins = 3000; S.bagMax = 15; ['harbor','frost','desert','forest'].forEach(i => { S.mastery[i] = true; FISH.filter(f => f.island === i).forEach(f => S.discovered[f.id] = true); });"
                    " S.records = {}; while (S.bag.length < 15) S.bag.push({ fishId: 'harbor_' + (S.bag.length % 10), weight: .5, price: 20, time: 1 }); save(); }")
        lp.add_style_tag(content="#toast { display: none !important; } .confetti { display: none !important; }")
        fits = {}
        for sc in ["home", "map", "bag", "collection", "shop", "tackle", "fishing", "result_full", "result"]:
            if sc == "fishing": lp.evaluate("() => { island = 'desert'; go('fishing'); }")
            elif sc == "result_full": lp.evaluate("() => { stopFishing(); F = { phase: 'idle', fish: fishById('desert_9') }; caught(); }")
            elif sc == "result":
                lp.click("#fullRelease"); lp.wait_for_timeout(200)
                lp.evaluate("() => { stopFishing(); S.bag = S.bag.slice(0, 3); save(); F = { phase: 'idle', fish: fishById('frost_8') }; caught(); }")
            else: lp.evaluate(f"() => go('{sc}')")
            lp.wait_for_timeout(450)
            fits[sc] = lp.evaluate(FIT, sc)
            if vw in (1536, 1366): lp.screenshot(path=str(SHOTS / f"70_{sc}_{vw}x{vh}.png"))
        lp.click("#releaseBtn"); lp.wait_for_timeout(200)
        for sc, r in fits.items():
            check(f"{vw}x{vh} {sc}: no page scroll ({r['page']} <= {r['vh']}), every main button fully on screen, no side scroll",
                  r["page"] <= r["vh"] + 1 and not r["out"] and r["n"] >= 1 and r["sw"] <= r["vw"], f"page {r['page']} out {r['out']}")
        check(f"{vw}x{vh}: no BACK bar on Home; BACK bar in the header row on the other menu screens",
              not fits["home"]["nav"] and all(fits[k]["nav"] for k in ("map", "bag", "collection", "shop", "tackle")))
        hdr = lp.evaluate("""() => { go('shop'); const t = document.getElementById('title').getBoundingClientRect(), n = document.getElementById('navbar').getBoundingClientRect(),
            c = document.querySelector('.app > .top .sign').getBoundingClientRect(); return [Math.abs(t.top - n.top) < 1 && Math.abs(n.top - c.top) < 1, t.right <= n.left, n.right <= c.left]; }""")
        check(f"{vw}x{vh}: header is one row: LITTLE LAKE | < BACK + SHOP | coins", all(hdr), str(hdr))
        lp.evaluate("() => { while (S.bag.length < 15) S.bag.push({ fishId: 'harbor_' + (S.bag.length % 10), weight: .5, price: 20, time: 1 }); save(); }")
        for sc in ("shop", "tackle", "bag"):
            lp.evaluate(f"() => go('{sc}')"); lp.wait_for_timeout(350)
            r = lp.evaluate(LIST, sc)
            check(f"{vw}x{vh} {sc}: the list scrolls inside the panel (thin scrollbar, fade at the bottom), the page doesn't, bottom buttons stay visible",
                  r[0] == "auto" and r[1] and r[2] and r[3] and r[4] and r[5] and r[6] == "thin", str(r))
        lp.evaluate("() => { collTab = 'harbor'; go('collection'); }"); lp.wait_for_timeout(350)
        coll = lp.evaluate("""() => { const vh = innerHeight, ok = el => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= vh; };
            const cells = [...document.querySelectorAll('#collGrid .cell')], sizes = [...document.querySelectorAll('#collection .cell, #collection .tab, #collHead div')].map(e => parseFloat(getComputedStyle(e).fontSize));
            return [cells.length, cells.every(ok), ok(document.querySelector('#collHead .bar')), ok(document.querySelector('#collHead .reward')), Math.min(...sizes)]; }""")
        check(f"{vw}x{vh}: Collection shows all 10 cards, the island progress bar and the reward line, text >= 12px",
              coll[0] == 10 and coll[1] and coll[2] and coll[3] and coll[4] >= 12, str(coll))
        small = lp.evaluate("""() => { const out = []; for (const sc of ['home', 'map', 'bag', 'shop', 'tackle', 'collection']) { go(sc);
            for (const el of document.querySelectorAll('.screen.active *, .app > .top *')) if (el.offsetParent && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())
                && parseFloat(getComputedStyle(el).fontSize) < 12) out.push(sc + ':' + (el.className || el.tagName)); } return [...new Set(out)]; }""")
        check(f"{vw}x{vh}: no text smaller than 12px on the menu screens", not small, str(small[:5]))
        if vw == 1280:
            # popups fit at 1280x600
            POPFIT = """id => { const m = document.getElementById(id), p = m.querySelector('.panel'), r = p.getBoundingClientRect(), vh = innerHeight;
                const btns = [...p.querySelectorAll('.btns .btn, #howOk, #banOk')].filter(b => b.offsetParent);
                return [r.top >= 0 && r.bottom <= vh && r.left >= 0 && r.right <= innerWidth, btns.length >= 1 && btns.every(b => { const q = b.getBoundingClientRect(); return q.top >= 0 && q.bottom <= vh; })]; }"""
            pops = {}
            lp.evaluate("() => { island = 'harbor'; go('fishing'); }"); lp.wait_for_timeout(300)
            lp.evaluate("() => { S.bag = []; save(); render(); }")
            for chip in ("rodChip", "baitChip"):
                lp.click(f"#{chip}"); lp.wait_for_timeout(450); pops[chip] = lp.evaluate(POPFIT, "pickBox")
                lp.screenshot(path=str(SHOTS / f"71_picker_{chip}_1280x600.png")); lp.click("#pickClose")
            lp.evaluate("() => go('titleScreen')"); lp.wait_for_timeout(200)
            for btn, box in (("howBtn", "howBox"), ("newBtn", "confirmBox")):
                lp.click(f"#{btn}"); lp.wait_for_timeout(450); pops[box] = lp.evaluate(POPFIT, box); lp.keyboard.press("Escape")
            lp.evaluate("() => openNameBox()"); lp.wait_for_timeout(450); pops["nameBox"] = lp.evaluate(POPFIT, "nameBox"); lp.keyboard.press("Escape")
            lp.evaluate("() => { go('home'); banner('Harbor Mastered!', 'Golden Hook unlocked: fish sell for 20% more coins.'); }"); lp.wait_for_timeout(450)
            pops["banner"] = lp.evaluate(POPFIT, "banner")
            check("1280x600: rod / bait picker, HOW TO PLAY, confirm, name and mastery popups fit with their buttons on screen",
                  all(all(v) for v in pops.values()), str({k: v for k, v in pops.items() if not all(v)}))
        lc.close()

    # ---------- BUG-24: Home, Map, Bag and Collection use the whole window on wide / tall screens ----------
    BLOCK = """sc => { const s = document.getElementById(sc), kids = [...s.children].filter(e => e.offsetParent && !e.classList.contains('demo'));
        const top = Math.min(...kids.map(e => e.getBoundingClientRect().top)), bottom = Math.max(...kids.map(e => e.getBoundingClientRect().bottom));
        const btns = [...document.querySelectorAll('.screen.active .btn, .app > .top .btn')].filter(b => b.offsetParent && !b.closest('.scroll-list'));
        return { top, bottom, vh: innerHeight, page: document.documentElement.scrollHeight, center: document.body.classList.contains('center'),
                 out: btns.filter(b => { const r = b.getBoundingClientRect(); return r.top < 0 || r.bottom > innerHeight + .5 || r.right > innerWidth + .5; }).map(b => b.textContent.trim().slice(0, 12)),
                 appW: document.querySelector('.app').getBoundingClientRect().width }; }"""
    BIG = """() => { const r = id => document.querySelector('#home > .btns > [data-go="' + id + '"]').getBoundingClientRect();
        const m = r('map'); return [m.width, m.height, ['bag', 'shop', 'collection', 'tackle'].map(k => [r(k).width, r(k).height])]; }"""
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600)]:
        cc = b.new_context(viewport={"width": vw, "height": vh}); cp = cc.new_page()
        cp.on("pageerror", lambda e: errs.append(str(e))); cp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        cp.goto(URL); cp.evaluate("localStorage.clear()"); cp.reload(); cp.wait_for_timeout(200); start_new(cp, "Center")
        cp.evaluate("() => { S.coins = 1500; S.discovered = { harbor_0: true, harbor_4: true, frost_2: true }; S.bag = [{ fishId: 'harbor_0', weight: .4, price: 18, time: 1 }, { fishId: 'frost_2', weight: 1.1, price: 40, time: 2 }]; save(); }")
        cp.add_style_tag(content="#toast { display: none !important; }")
        blocks = {}
        for sc in ["home", "map", "collection"]:
            cp.evaluate(f"() => {{ collTab = 'harbor'; go('{sc}'); }}"); cp.wait_for_timeout(450)
            blocks[sc] = r = cp.evaluate(BLOCK, sc)
            check(f"{vw}x{vh} {sc}: centred layout, no page scroll, every main button fully on screen",
                  r["center"] and r["page"] <= r["vh"] + 1 and not r["out"], f"page {r['page']} out {r['out']}")
            if vw in (1920, 1366): cp.screenshot(path=str(SHOTS / f"80_{sc}_{vw}x{vh}.png"))
        h = blocks["home"]; mid = (h["top"] + h["bottom"]) / 2
        if vw == 1920:
            check("1920x915: Home panel + buttons are vertically centred (within 10% of the window) and use at least 55% of its height",
                  abs(mid - vh / 2) <= vh * .10 and (h["bottom"] - h["top"]) >= vh * .55, f"centre {mid:.0f} vs {vh / 2:.0f}, block {h['bottom'] - h['top']:.0f}px = {(h['bottom'] - h['top']) / vh:.0%}")
            check("1920x915: Map and Collection are centred below the header too (within 10%)",
                  all(abs((blocks[k]["top"] + blocks[k]["bottom"]) / 2 - vh / 2) <= vh * .10 for k in ("map", "collection")),
                  str({k: round((v["top"] + v["bottom"]) / 2) for k, v in blocks.items()}))
            check("1920x915: the content is at most about 1100px wide", blocks["home"]["appW"] <= 1100)
        cp.evaluate("() => go('home')"); cp.wait_for_timeout(300); big = cp.evaluate(BIG)
        check(f"{vw}x{vh}: TOWN MAP is the main Home action (wider and taller than OPEN BAG, SHOP, COLLECTION, TACKLE BOX)",
              all(big[0] > w and big[1] > hh for w, hh in big[2]), str(big))
        if vw == 1280:
            cp.evaluate("() => { island = 'harbor'; go('fishing'); }"); cp.wait_for_timeout(300)
            check("Fishing screen is not affected by the centred layout (no body.center, same 980px width)",
                  not cp.evaluate("document.body.classList.contains('center')") and cp.evaluate("getComputedStyle(document.querySelector('.app')).maxWidth") == "980px")
            cp.evaluate("() => { stopFishing(); go('shop'); }"); cp.wait_for_timeout(200)
            check("Shop and Tackle Box keep their fixed layout (not centred)", not cp.evaluate("document.body.classList.contains('center')"))
        cc.close()
    for vw, vh in [(360, 640), (390, 844)]:
        ph = b.new_page(viewport={"width": vw, "height": vh}); ph.on("pageerror", lambda e: errs.append(str(e)))
        ph.goto(URL); ph.evaluate("localStorage.clear()"); ph.reload(); ph.wait_for_timeout(200); start_new(ph, "Phone")
        r = ph.evaluate("""() => [getComputedStyle(document.querySelector('#home'), '::before').content, getComputedStyle(document.querySelector('#home > .btns > [data-go="map"]')).gridRowStart,
                               document.documentElement.scrollWidth <= innerWidth]""")
        check(f"{vw}x{vh}: phones keep the current Home layout (no centring spacers, TOWN MAP a normal button), no side scroll",
              r[0] in ("none", "normal") and r[1] == "auto" and r[2], str(r))
        ph.close()

    # ---------- BUG-25 / BUG-27: Bag anchored at the top, compact fixed-height rows added downward, buttons never move; BUG-26: Town Map ----------
    # fish in catch order: a different fish each time (harbor_0, frost_1, desert_2, ...), so the order on screen can be checked
    FILL = """n => { S.bagMax = 15; S.bag = []; const isl = ['harbor', 'frost', 'desert', 'forest'];
        while (S.bag.length < n) { const i = S.bag.length; S.bag.push({ fishId: isl[i % 4] + '_' + (i % 10), weight: .5, price: 20 + i, time: 1000 + i }); }
        save(); go('home'); go('bag'); }"""
    BAGPOS = """() => { const p = document.querySelector('#bag .panel').getBoundingClientRect(), l = document.getElementById('bagList'),
        q = id => { const r = document.getElementById(id).getBoundingClientRect(); return [Math.round(r.top), Math.round(r.left), r.bottom <= innerHeight]; };
        const rows = [...l.querySelectorAll('.row')], rr = rows.map(r => r.getBoundingClientRect());
        return { panel: Math.round(p.top), sell: q('sellAll'), home: q('navBack'), scrolls: l.scrollHeight > l.clientHeight + 4, ov: getComputedStyle(l).overflowY,
                 thin: getComputedStyle(l).scrollbarWidth, page: document.documentElement.scrollHeight, vh: innerHeight, rows: rows.length,
                 heights: rr.map(r => +r.height.toFixed(1)), first: rr.length ? +rr[0].top.toFixed(1) : null,
                 names: rows.map(r => (r.querySelector('b') || {}).textContent || ''), want: S.bag.map(x => fishById(x.fishId).name),
                 text: l.innerText, back: !!document.getElementById('bagBack'), bottomHome: !!document.querySelector('#bag > .btns [data-go="home"]'),
                 center: document.body.classList.contains('center') }; }"""
    row_h = {}
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600), (390, 844), (360, 640)]:
        phone = vw < 900
        gc = b.new_context(viewport={"width": vw, "height": vh}); gp = gc.new_page()
        gp.on("pageerror", lambda e: errs.append(str(e))); gp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        gp.goto(URL); gp.evaluate("localStorage.clear()"); gp.reload(); gp.wait_for_timeout(200); start_new(gp, "BagTop")
        gp.add_style_tag(content="#toast { display: none !important; }")
        bp_ = {}
        for n in (0, 1, 5, 10, 15):
            gp.evaluate(FILL, n); gp.wait_for_timeout(400); bp_[n] = gp.evaluate(BAGPOS)
            if (vw, vh) in ((1536, 730), (390, 844)) and n in (0, 1, 5, 15): gp.screenshot(path=str(SHOTS / f"92_bag_{n}_fish_{vw}x{vh}.png"))
        hs = [h for v in bp_.values() for h in v["heights"]]; row_h[(vw, vh)] = hs[0]
        check(f"{vw}x{vh}: every Bag row has the same compact height with 0, 1, 5, 10 and 15 fish (empty message included), never stretched",
              max(hs) - min(hs) <= 1 and (52 <= hs[0] <= 66), f"{min(hs)}..{max(hs)}")
        check(f"{vw}x{vh}: the first row starts at the same y with 0, 1, 5, 10, 15 fish; rows are in catch order",
              len({v["first"] for v in bp_.values()}) == 1 and all(v["names"] == v["want"] for k, v in bp_.items() if k), str({k: v["first"] for k, v in bp_.items()}))
        if not phone:
            same = all(v["panel"] == bp_[0]["panel"] and v["sell"] == bp_[0]["sell"] and v["home"] == bp_[0]["home"] for v in bp_.values())
            check(f"{vw}x{vh}: Bag with 0, 1, 5, 10, 15 fish: panel top, SELL ALL and the top BACK stay in the same place, on screen, no page scroll",
                  same and all(v["sell"][2] and v["home"][2] and v["page"] <= v["vh"] + 1 for v in bp_.values()),
                  str({n: (v["panel"], v["sell"][:2], v["home"][:2], v["page"]) for n, v in bp_.items()}))
            check(f"{vw}x{vh}: Bag is anchored at the top (not centred): panel right under the header", not bp_[5]["center"] and bp_[5]["panel"] < 120, str(bp_[5]["panel"]))
            check(f"{vw}x{vh}: a full Bag scrolls inside its list (overflow-y auto, thin scrollbar); 5 fish fit without scrolling",
                  bp_[15]["scrolls"] and bp_[15]["ov"] == "auto" and bp_[15]["thin"] == "thin" and bp_[15]["rows"] == 15 and not bp_[5]["scrolls"],
                  f"15: {bp_[15]['scrolls']} 5: {bp_[5]['scrolls']}")
        else:
            check(f"{vw}x{vh}: phone Bag has no side scroll", gp.evaluate("document.documentElement.scrollWidth") <= vw)
        if vw == 1920:
            check("empty Bag still says 'Your bag is empty. Go fishing!'; no bottom BACK or HOME button in the Bag",
                  "Your bag is empty. Go fishing!" in bp_[0]["text"] and not bp_[0]["back"] and not bp_[0]["bottomHome"], bp_[0]["text"][:40])
            # BUG-29: one navigation rule: every inner screen has BACK + a centred name in the top bar, and no HOME up there
            bars = {}
            for sc, name in [("map", "TOWN MAP"), ("bag", "BAG"), ("shop", "SHOP"), ("collection", "COLLECTION"), ("tackle", "TACKLE BOX")]:
                gp.evaluate(f"() => {{ go('home'); go('{sc}'); }}"); gp.wait_for_timeout(250)
                bars[sc] = gp.evaluate("""() => { const bar = document.getElementById('navbar'), r = bar.getBoundingClientRect(), t = document.getElementById('navName').getBoundingClientRect();
                    return [[...bar.querySelectorAll('button')].map(b => b.textContent.trim()), document.getElementById('navName').textContent,
                            Math.round(Math.abs((t.left + t.right) / 2 - (r.left + r.right) / 2)), document.querySelectorAll('.screen.active [data-go="home"]').length]; }""")
                gp.click("#navBack"); gp.wait_for_timeout(250); bars[sc].append(gp.evaluate("current"))
            check("top bar of Map, Bag, Shop, Collection and Tackle Box: only '< BACK' (no HOME), the name centred, BACK returns Home",
                  all(v[0] == ["< BACK"] and v[1] == n and v[2] <= 2 and v[4] == "home" for (s_, n), v in zip([("map", "TOWN MAP"), ("bag", "BAG"), ("shop", "SHOP"), ("collection", "COLLECTION"), ("tackle", "TACKLE BOX")], bars.values()))
                  and not gp.evaluate("!!document.getElementById('navHome')"), str(bars))
            check("HOME buttons: Town Map (panel header), Shop and Tackle Box (bottom) have exactly one; Collection and Bag have none",
                  {k: v[3] for k, v in bars.items()} == {"map": 1, "bag": 0, "shop": 1, "collection": 0, "tackle": 1}, str({k: v[3] for k, v in bars.items()}))
            gp.evaluate("() => { go('home'); island = 'forest'; go('fishing'); }"); gp.wait_for_timeout(300)
            gp.click("#fishing [data-go=map]"); gp.wait_for_timeout(250); gp.click("#map [data-go=home]"); gp.wait_for_timeout(250)
            check("from Fishing, Town Map > HOME reaches Home", gp.evaluate("current") == "home")
            gp.click("#home [data-go=collection]"); gp.wait_for_timeout(250); gp.click("#navBack"); gp.wait_for_timeout(250)
            check("Home > Collection > BACK returns to Home", gp.evaluate("current") == "home")
            gp.evaluate("() => { go('home'); island = 'desert'; go('fishing'); }"); gp.wait_for_timeout(300)
            gp.click("#sellTop"); gp.wait_for_timeout(250); on_bag = gp.evaluate("current")
            gp.click("#navBack"); gp.wait_for_timeout(300)
            check("Fishing (Desert) > SELL > BACK returns to the Fishing screen on the same island",
                  on_bag == "bag" and gp.evaluate("current") == "fishing" and gp.evaluate("island") == "desert" and "Desert:" in gp.inner_text("#isleProg"), gp.inner_text("#isleProg")[:30])
            gp.evaluate("() => stopFishing()")
            keep = gp.evaluate("['shop', 'tackle'].every(s => !!document.querySelector('#' + s + ' > .btns [data-go=\"home\"]'))")
            check("Shop and Tackle Box keep their bottom HOME button", keep)

        gc.close()
    check("Bag rows: about 64px on tall desktop windows and phones, about 56px on windows under 760px high",
          row_h[(1920, 915)] == 64 and row_h[(390, 844)] == 64 and row_h[(360, 640)] == 64 and row_h[(1536, 730)] == 56 and row_h[(1280, 600)] == 56, str(row_h))
    # Town Map
    MAPS = """() => { const cards = [...document.querySelectorAll('#islands .island:not(.secret-strip)')], strip = document.querySelector('#islands .secret-strip');
        const r = cards.map(c => c.getBoundingClientRect()), sr = strip.getBoundingClientRect();
        return { n: cards.length, ids: cards.map(c => [...c.classList].find(k => k.startsWith('bg-'))), w: r.map(x => Math.round(x.width)), h: r.map(x => Math.round(x.height)),
                 row: r.every(x => Math.abs(x.top - r[0].top) < 1), stripBelow: sr.top >= Math.max(...r.map(x => x.bottom)), stripWide: sr.width > r[0].width * 3,
                 bars: cards.map(c => parseFloat(c.querySelector('.isl-bar > span').style.width)), counts: cards.map(c => c.querySelector('.isl-count').textContent),
                 stars: cards.map(c => !!c.querySelector('.isl-name .i-star')), rewards: cards.map(c => c.querySelector('.isl-reward').textContent),
                 strip: strip.innerText.replace(/\\s+/g, ' '), locked: strip.classList.contains('locked'), stripPic: getComputedStyle(strip).backgroundImage.includes('secret.png'),
                 homes: document.querySelectorAll('#map [data-go="home"]').length, bars2: document.querySelectorAll('#map .btns').length,
                 page: document.documentElement.scrollHeight, vh: innerHeight, sw: document.documentElement.scrollWidth, vw: innerWidth }; }"""
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600), (360, 640), (390, 844)]:
        mc = b.new_context(viewport={"width": vw, "height": vh}); mpg = mc.new_page()
        mpg.on("pageerror", lambda e: errs.append(str(e))); mpg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        mpg.goto(URL); mpg.evaluate("localStorage.clear()"); mpg.reload(); mpg.wait_for_timeout(200); start_new(mpg, "Mapper")
        mpg.add_style_tag(content="#toast { display: none !important; }")
        states = {"fresh": "() => {}",
                  "harbor8": "() => { for (let i = 0; i < 8; i++) S.discovered['harbor_' + i] = true; S.discovered.frost_0 = true; S.discovered.frost_1 = true; S.discovered.desert_3 = true; save(); }",
                  "all": "() => { ['harbor','frost','desert','forest'].forEach(i => { S.mastery[i] = true; FISH.filter(f => f.island === i).forEach(f => S.discovered[f.id] = true); }); save(); }"}
        got = {}
        for tag, js in states.items():
            mpg.evaluate(js); mpg.evaluate("() => { go('home'); go('map'); }"); mpg.wait_for_timeout(400); got[tag] = mpg.evaluate(MAPS)
            if vw == 1536: mpg.screenshot(path=str(SHOTS / f"91_map_{tag}_{vw}x{vh}.png"))
            if vw == 360 and tag == "fresh": mpg.screenshot(path=str(SHOTS / f"91_map_{tag}_{vw}x{vh}.png"), full_page=True)
        f, h8, al = got["fresh"], got["harbor8"], got["all"]
        phone = vw < 900
        if phone:
            check(f"{vw}x{vh}: Town Map island cards 2x2 + secret strip, no side scroll", f["n"] == 4 and f["sw"] <= vw and f["stripBelow"], str(f["w"]))
        else:
            check(f"{vw}x{vh}: Town Map = 4 equal island cards in one row (220-260px) + a separate wide secret strip below, one HOME button (panel header), no page scroll",
                  f["n"] == 4 and f["ids"] == ["bg-harbor", "bg-frost", "bg-desert", "bg-forest"] and f["row"] and len(set(f["w"])) == 1
                  and (220 <= f["w"][0] <= 260 or vw < 1366) and f["stripBelow"] and f["stripWide"] and f["homes"] == 1 and f["bars2"] == 0 and f["page"] <= f["vh"] + 1,
                  f"w {f['w']} h {f['h']} page {f['page']}")
        check(f"{vw}x{vh}: progress bars and counts match the save (Harbor 8/10, Frost 2/10, Desert 1/10, Forest 0/10)",
              h8["bars"] == [80, 20, 10, 0] and h8["counts"] == ["8 / 10", "2 / 10", "1 / 10", "0 / 10"] and h8["rewards"] == ["Golden Hook", "Steady Hands", "Lucky Lure", "Master's Charm"],
              f"{h8['bars']} {h8['counts']}")
        check(f"{vw}x{vh}: gold star only on mastered islands",
              f["stars"] == [False] * 4 and h8["stars"] == [False] * 4 and al["stars"] == [True] * 4 and al["bars"] == [100] * 4)
        check(f"{vw}x{vh}: secret strip: locked '??? Master all 4 islands to unlock' with a padlock; unlocked 'Little Lake' with its night picture",
              f["locked"] and "???" in f["strip"] and "Master all 4 islands to unlock" in f["strip"] and not f["stripPic"]
              and not al["locked"] and "Little Lake" in al["strip"] and al["stripPic"], f"{f['strip']} | {al['strip']}")
        if vw == 1536:
            mpg.evaluate("() => { S.mastery = {}; save(); go('home'); go('map'); }"); mpg.wait_for_timeout(300)
            mpg.locator("#islands .secret-strip").screenshot(path=str(SHOTS / "92_map_locked_strip_1536x730.png"))
            moon = mpg.evaluate("""() => { const s = document.querySelector('#islands .secret-strip'), bg = getComputedStyle(s).backgroundImage, r = s.getBoundingClientRect();
                const kids = [...s.children].every(c => { const q = c.getBoundingClientRect(); return q.top >= r.top && q.bottom <= r.bottom; });
                return [bg.includes('radial-gradient'), bg.includes('url('), getComputedStyle(s).overflow, kids]; }""")
            check("locked secret strip: no moon circle (no picture, no radial moon), everything clipped inside the strip",
                  moon == [False, False, "hidden", True], str(moon))
            mpg.evaluate("() => { ['harbor','frost','desert','forest'].forEach(i => S.mastery[i] = true); save(); go('home'); go('map'); }"); mpg.wait_for_timeout(300)
            opened = {}
            for isl in ["harbor", "frost", "desert", "forest", "secret"]:
                mpg.evaluate("() => go('map')"); mpg.wait_for_timeout(250); mpg.click(f"#islands .bg-{isl}"); mpg.wait_for_timeout(300)
                opened[isl] = [mpg.evaluate("current"), mpg.evaluate("island")]
            mpg.evaluate("() => stopFishing()")
            check("clicking each island card (and the unlocked strip) opens the fishing screen of that island",
                  all(v == ["fishing", k] for k, v in opened.items()), str(opened))
            mpg.evaluate("() => { S.mastery = {}; save(); go('home'); go('map'); }"); mpg.wait_for_timeout(250); mpg.click("#islands .secret-strip"); mpg.wait_for_timeout(200)
            check("the locked strip doesn't open fishing (explains how to unlock it)", mpg.evaluate("current") == "map" and "Master all four islands" in mpg.inner_text("#toast"))
        mc.close()

    # screenshots of the inner screens with the single-BACK top bar (BUG-29)
    sc_ = b.new_page(viewport={"width": 1536, "height": 730}); sc_.on("pageerror", lambda e: errs.append(str(e)))
    sc_.goto(URL); sc_.evaluate("localStorage.clear()"); sc_.reload(); sc_.wait_for_timeout(200); start_new(sc_, "Shots")
    sc_.evaluate("() => { S.coins = 900; S.discovered = { harbor_0: true, harbor_4: true, frost_2: true }; S.bag = [{ fishId: 'harbor_0', weight: .4, price: 18, time: 1 }, { fishId: 'frost_2', weight: 1.1, price: 40, time: 2 }]; save(); }")
    sc_.add_style_tag(content="#toast { display: none !important; }")
    for sc in ["collection", "bag", "map", "shop", "tackle"]:
        sc_.evaluate(f"() => {{ collTab = 'harbor'; go('home'); go('{sc}'); }}"); sc_.wait_for_timeout(450)
        sc_.screenshot(path=str(SHOTS / f"93_{sc}_1536x730.png"))
    sc_.close()

    # ---------- BUG-30 / BUG-34 / BUG-35: Town Map HOME (BUG-30: out of the bottom bar; BUG-34: bigger; BUG-35: fully above the panel frame, right-aligned) ----------
    MH = """() => { const homes = [...document.querySelectorAll('[data-go="home"]')].filter(b => b.offsetParent), m = document.getElementById('mapHome'),
        panel = document.querySelector('#map .panel'), p = panel.getBoundingClientRect(), r = m.getBoundingClientRect(), h2 = panel.querySelector('h2').getBoundingClientRect(),
        bw = parseFloat(getComputedStyle(panel).borderTopWidth), ico = m.querySelector('.ico.i-home').getBoundingClientRect(),
        hit = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom,
        others = [...document.querySelectorAll('.app > .top > *, #map .island, #map h2, #map .panel')].filter(e => e.offsetParent || getComputedStyle(e).position === 'fixed');
        return { n: homes.length, inPanel: m.parentElement === panel, inBar: !!document.querySelector('#navbar [data-go="home"]'),
                 below: document.querySelectorAll('#map > .btns').length, right: Math.round(p.right - r.right),
                 gap: Math.round(p.top - r.bottom), panelHit: hit(r, p), bar: Math.round(r.top - document.querySelector('.app > .top').getBoundingClientRect().bottom),
                 overlaps: others.filter(e => hit(r, e.getBoundingClientRect())).map(e => e.id || e.className),
                 inView: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight,
                 topAt: document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2)?.closest('#mapHome') === m,
                 icon: getComputedStyle(m.querySelector('.ico.i-home')).backgroundImage.includes('svg'), iconPx: Math.round(ico.width), font: parseFloat(getComputedStyle(m).fontSize),
                 label: m.textContent.trim(), aria: m.getAttribute('aria-label'), tag: m.tagName, headH: Math.round(panel.querySelector('.head').getBoundingClientRect().height),
                 h: Math.round(r.height), w: Math.round(r.width), page: document.documentElement.scrollHeight, vh: innerHeight, sw: document.documentElement.scrollWidth, vw: innerWidth }; }"""
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600), (390, 844), (360, 640)]:
        hp = b.new_page(viewport={"width": vw, "height": vh})
        hp.on("pageerror", lambda e: errs.append(str(e))); hp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        hp.goto(URL); hp.evaluate("localStorage.clear()"); hp.reload(); hp.wait_for_timeout(200); start_new(hp, "MapHome")
        hp.add_style_tag(content="#toast { display: none !important; }")
        hp.evaluate("() => { island = 'frost'; go('fishing'); }"); hp.wait_for_timeout(300)
        hp.click("#fishing [data-go=map]"); hp.wait_for_timeout(400)
        r = hp.evaluate(MH)
        if (vw, vh) in ((1536, 730), (360, 640)): hp.screenshot(path=str(SHOTS / f"98_map_home_above_{vw}x{vh}.png"))
        check(f"{vw}x{vh}: Town Map has exactly one HOME, a real button (pixel house icon, 'HOME', aria-label 'Home') placed from the panel; none in the top bar or below the panel",
              r["n"] == 1 and r["inPanel"] and not r["inBar"] and r["below"] == 0 and r["icon"] and r["label"] == "HOME" and r["aria"] == "Home" and r["tag"] == "BUTTON",
              str({k: r[k] for k in ("n", "inPanel", "inBar", "below", "icon", "label", "aria")}))
        check(f"{vw}x{vh}: Town Map HOME is >= 44px tall with a bigger icon (>= 20px) and label (>= 18px)", r["h"] >= 44 and r["iconPx"] >= 20 and r["font"] >= 18,
              f"h {r['h']} icon {r['iconPx']} font {r['font']}")
        check(f"{vw}x{vh}: Town Map HOME is fully above the panel's top border (gap 4-14px) and right-aligned with the panel's right edge (within 2px)",
              4 <= r["gap"] <= 14 and abs(r["right"]) <= 2 and not r["panelHit"], f"gap {r['gap']} right {r['right']} panelHit {r['panelHit']}")
        check(f"{vw}x{vh}: Town Map HOME doesn't overlap the top bar, the panel, the title or the island cards, is fully in view and on top (tappable)",
              not r["overlaps"] and r["bar"] >= 0 and r["inView"] and r["topAt"], f"{r['overlaps']} bar gap {r['bar']} inView {r['inView']} topAt {r['topAt']}")
        check(f"{vw}x{vh}: Town Map title row is a clean row (<= 44px) and the page has no page scroll or side scroll",
              r["headH"] <= 44 and r["page"] <= r["vh"] + 1 and r["sw"] <= r["vw"], f"head {r['headH']} page {r['page']}/{r['vh']} sw {r['sw']}")
        if vw in (1536, 360):
            hp.click("#navBack"); hp.wait_for_timeout(300)
            back = [hp.evaluate("current"), hp.evaluate("island"), hp.inner_text("#isleProg")[:6]]
            check(f"{vw}x{vh}: Fishing (Frost) > Town Map > BACK returns to the Fishing screen on the same island", back == ["fishing", "frost", "Frost:"], str(back))
            hp.click("#fishing [data-go=map]"); hp.wait_for_timeout(300)
            hp.focus("#mapHome"); hp.keyboard.press("Enter"); hp.wait_for_timeout(300)
            check(f"{vw}x{vh}: Fishing > Town Map > HOME (keyboard Enter) opens Home", hp.evaluate("current") == "home")
            hp.click("#home [data-go=map]"); hp.wait_for_timeout(300); hp.click("#mapHome"); hp.wait_for_timeout(300)
            check(f"{vw}x{vh}: Home > Town Map > HOME (tap) opens Home", hp.evaluate("current") == "home")
        hp.close()

    # ---------- BUG-31: rods are a clear step up in forgiveness (1, 2, 3, 5 misses; +1 with Master's Charm) ----------
    rc = b.new_context(viewport={"width": 1366, "height": 768}); rp = rc.new_page()
    rp.on("pageerror", lambda e: errs.append(str(e))); rp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    rp.goto(URL); rp.evaluate("localStorage.clear()"); rp.reload(); rp.wait_for_timeout(200); start_new(rp, "Rods")
    rp.add_style_tag(content="#toast { display: none !important; }")
    AM = "m => Object.fromEntries(ROD_IDS.map(id => { S.rods = [...ROD_IDS]; S.rodEq = id; S.mastery = m; return [id, allowedMiss()]; }))"
    am0, am1 = rp.evaluate(AM, {}), rp.evaluate(AM, {"forest": True})
    check("allowedMiss(): Bamboo 1, Sturdy 2, Precision 3, Lucky 5; with Master's Charm 2, 3, 4, 6",
          am0 == {"bamboo": 1, "sturdy": 2, "precision": 3, "lucky": 5} and am1 == {"bamboo": 2, "sturdy": 3, "precision": 4, "lucky": 6}, f"{am0} {am1}")
    # a fish is lost only after the (allowedMiss + 1)th miss: miss on purpose and watch the phase after every press
    def miss_run(pg, rod, mastery="{}"):
        pg.evaluate(f"() => {{ stopFishing(); S.rods = [...ROD_IDS]; S.rodEq = '{rod}'; S.mastery = {mastery}; S.bag = []; save(); island = 'harbor'; go('fishing'); }}"); pg.wait_for_timeout(300)
        pg.click("#actBtn"); pg.wait_for_function("F.phase === 'bite'", timeout=8000); pg.click("#actBtn"); pg.wait_for_timeout(80)
        hearts = [pg.evaluate("document.querySelectorAll('#hearts .ico').length")]; phases = []
        for _ in range(12):
            if pg.evaluate("F.phase") != "reeling": break
            pg.wait_for_function("F.phase !== 'reeling' || F.pos < F.zoneX - 0.06 || F.pos > F.zoneX + F.zoneW + 0.06", timeout=8000, polling=5)
            if pg.evaluate("F.phase") != "reeling": break
            pg.click("#actBtn"); pg.wait_for_timeout(40)
            phases.append(pg.evaluate("F.phase")); hearts.append(pg.evaluate("document.querySelectorAll('#hearts .i-heart').length"))
        return phases, hearts, pg.inner_text("#fMsg")
    for rod, n in [("precision", 3), ("lucky", 5)]:
        ph, he, msg = miss_run(rp, rod)
        check(f"{rod.title()} Rod: {n + 1} hearts' worth of play: still reeling after {n} misses, the fish escapes on miss {n + 1}; {n} hearts shown",
              ph == ["reeling"] * n + ["idle"] and he[0] == n and he[1:] == list(range(n - 1, -1, -1)) + [0] and "escaped" in msg, f"{ph} {he} {msg[:40]}")
    rp.evaluate("() => { stopFishing(); S.rods = [...ROD_IDS]; S.rodEq = 'lucky'; S.mastery = { forest: true }; save(); go('tackle'); }"); rp.wait_for_timeout(250)
    gear = rp.inner_text("#gearList")
    check("Tackle Box: '3 misses allowed' (Precision), '5 misses allowed' (Lucky), '6 misses allowed in total with your Lucky Rod' (with Master's Charm)",
          "3 misses allowed, green zone 35% wider" in gear and "5 misses allowed, better rarity odds" in gear and "6 misses allowed in total with your Lucky Rod" in gear, gear[:120])
    rp.evaluate("() => { S.mastery = {}; save(); island = 'harbor'; go('fishing'); }"); rp.wait_for_timeout(250); rp.click("#rodChip"); rp.wait_for_timeout(250)
    pick = {r: rp.inner_text(f"#pick-{r}") for r in ["bamboo", "sturdy", "precision", "lucky"]}
    check("Choose Rod popup: 1, 2, 3 and 5 misses allowed", "1 miss allowed" in pick["bamboo"] and "2 misses allowed" in pick["sturdy"]
          and "3 misses allowed" in pick["precision"] and "5 misses allowed" in pick["lucky"], str({k: v[:40] for k, v in pick.items()}))
    rp.keyboard.press("Escape"); rp.evaluate("() => go('titleScreen')"); rp.click("#howBtn"); rp.wait_for_timeout(150)
    check("HOW TO PLAY (Rods) lists the new misses",
          "Bamboo (free, 1 miss), Sturdy (2 misses), Precision (3 misses and a 35% wider green zone) or Lucky (5 misses and better odds, but a 10% faster minigame)" in rp.inner_text("#howBox"))
    rc.close()
    # ---------- Playtest 1, part 3: the rod you equip is visible (fisherman, icons, toast) ----------
    ICON_BG = """ids => ids.map(id => { const e = document.createElement('span'); e.className = 'ico ' + id; document.body.appendChild(e);
        const bg = getComputedStyle(e).backgroundImage; e.remove(); return bg; })"""
    for vw, vh in [(1536, 730), (360, 640)]:
        rp3 = b.new_page(viewport={"width": vw, "height": vh})
        rp3.on("pageerror", lambda e: errs.append(str(e))); rp3.on("console", lambda m: m.type == "error" and errs.append(m.text))
        rp3.goto(URL); rp3.evaluate("localStorage.clear()"); rp3.reload(); rp3.wait_for_timeout(200); start_new(rp3, "Rodlook")
        rp3.evaluate("() => { S.rods = [...ROD_IDS]; S.coins = 5000; save(); island = 'harbor'; go('fishing'); }")
        rp3.wait_for_function("SCENES.harbor.img || SCENES.harbor.failed", timeout=8000); rp3.wait_for_timeout(500)
        if vw == 1536:
            small = rp3.evaluate(ICON_BG, [f"i-rod-{r}" for r in ROD_IDS_PY]); big = rp3.evaluate(ICON_BG, [f"i-rodlg-{r}" for r in ROD_IDS_PY])
            check("the four small rod icons (.i-rod-*) have four different background images", len(set(small)) == 4 and all("svg" in x for x in small))
            check("the four large rod icons (.i-rodlg-*) have four different background images, also different from the small ones", len(set(big)) == 4 and not set(big) & set(small))
        seen = []
        for rid, name in [("sturdy", "Sturdy Rod"), ("precision", "Precision Rod"), ("lucky", "Lucky Rod"), ("bamboo", "Bamboo Rod")]:
            rp3.evaluate("() => { document.getElementById('toast').style.visibility = ''; }")
            rp3.click("#rodChip"); rp3.wait_for_timeout(300)
            if rid == "sturdy":
                big_sz = rp3.evaluate("[...document.querySelectorAll('#pickList .pick-card > .ico')].map(i => [i.className.includes('i-rodlg-'), i.offsetWidth])")
                bgs = rp3.evaluate("[...document.querySelectorAll('#pickList .pick-card > .ico')].map(i => getComputedStyle(i).backgroundImage)")
                check(f"{vw}x{vh}: the Choose Rod popup shows the four large rod icons (32px, all different)", len(big_sz) == 4 and all(x[0] and x[1] == 32 for x in big_sz) and len(set(bgs)) == 4, str(big_sz))
            rp3.click(f"#pick-{rid}"); rp3.wait_for_timeout(350)
            toast_txt = rp3.inner_text("#toast")
            rp3.evaluate("() => { const t = document.getElementById('toast'); t.style.visibility = 'hidden'; }")
            rp3.wait_for_timeout(150)
            seen.append((rid, toast_txt.strip(), rp3.evaluate("[S.rodEq, fisherRodStyle()]")))
            rp3.screenshot(path=str(SHOTS / f"99_rod_{rid}_{vw}x{vh}.png"))
        check(f"{vw}x{vh}: switching rods in the Choose Rod popup shows 'Equipped: <rod name>' and the fisherman draws the new rod at once",
              all(t == f"Equipped: {n}" and eq == [r, r] for (r, t, eq), n in zip(seen, ["Sturdy Rod", "Precision Rod", "Lucky Rod", "Bamboo Rod"])), str(seen))
        rp3.evaluate("() => { go('shop'); }"); rp3.wait_for_timeout(250)
        sh = rp3.evaluate("[...document.querySelectorAll('#shopRods .item b .ico')].map(i => [i.className.includes('i-rodlg-'), Math.round(i.getBoundingClientRect().width), getComputedStyle(i).backgroundImage])")
        check(f"{vw}x{vh}: the Shop shows the four large rod icons (32px, all different)", len(sh) == 4 and all(x[0] and x[1] == 32 for x in sh) and len({x[2] for x in sh}) == 4, str([x[:2] for x in sh]))
        rp3.evaluate("() => { go('tackle'); }"); rp3.wait_for_timeout(250)
        tk = rp3.evaluate("[...document.querySelectorAll('#gearList .gear-row > .ico')].filter(i => i.className.includes('i-rodlg-')).map(i => [Math.round(i.getBoundingClientRect().width), getComputedStyle(i).backgroundImage])")
        check(f"{vw}x{vh}: the Tackle Box shows the four large rod icons (48px, all different)", len(tk) == 4 and all(x[0] == 48 for x in tk) and len({x[1] for x in tk}) == 4, str([x[0] for x in tk]))
        rp3.click('[data-equip="sturdy"]'); rp3.wait_for_timeout(250)
        check(f"{vw}x{vh}: equipping a rod in the Tackle Box shows 'Equipped: Sturdy Rod'", rp3.evaluate("S.rodEq") == "sturdy" and rp3.evaluate("document.getElementById('toast').textContent.trim()") == "Equipped: Sturdy Rod")
        rp3.evaluate("() => { go('fishing'); }"); rp3.wait_for_timeout(300)
        check(f"{vw}x{vh}: back on the fishing screen the Sturdy Rod is drawn", rp3.evaluate("fisherRodStyle()") == "sturdy")
        rp3.close()
    # ---------- Playtest 1, part 4: hold-to-charge power cast (bobber landing spot only) ----------
    CAST_POS = """(() => { const e = document.getElementById('actBtn'), r = e.getBoundingClientRect(), ty = new DOMMatrix(getComputedStyle(e).transform).m42;   // minus the :active press offset
        return { top: r.top - ty, left: r.left, w: r.width, h: r.height }; })()"""
    def same_pos(a, b): return all(abs(a[k] - b[k]) <= 1 for k in a)
    CHARGING = "(() => { const m = document.getElementById('meter'); return m.classList.contains('charging') && getComputedStyle(m).visibility === 'visible' && getComputedStyle(m.querySelector('.power')).display === 'block'; })()"
    NO_SCROLL = "(() => document.documentElement.scrollHeight <= innerHeight + 1 && document.documentElement.scrollWidth <= innerWidth)()"

    def cast_reset(pg):
        pg.evaluate("() => { stopFishing(); S.bag = []; S.baitSel = 'none'; save(); island = 'harbor'; go('home'); go('fishing'); }"); pg.wait_for_timeout(250)

    def center(pg, sel):
        r = pg.locator(sel).bounding_box(); return r["x"] + r["width"] / 2, r["y"] + r["height"] / 2

    def hold_btn(pg, ms, sel="#actBtn"):
        x, y = center(pg, sel); pg.mouse.move(x, y); pg.mouse.down(); pg.wait_for_timeout(ms)

    def exp_power(held):                                           # the meter's power after `held` ms: fills in 1.2 s after 250 ms, then ping-pongs
        d = max(0, (held - 250) / 1200); m = d % 2; return m if m < 1 else 2 - m
    def timed_hold(pg, ms):
        x, y = center(pg, "#actBtn"); pg.mouse.move(x, y); pg.mouse.down(); t0 = time.perf_counter(); pg.wait_for_timeout(ms)
        held = (time.perf_counter() - t0) * 1000; pg.mouse.up(); pg.wait_for_timeout(50); return pg.evaluate("F.land"), held

    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600), (390, 844), (360, 640)]:
        cp = b.new_page(viewport={"width": vw, "height": vh})
        cp.on("pageerror", lambda e: errs.append(str(e))); cp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        cp.goto(URL); cp.evaluate("localStorage.clear()"); cp.reload(); cp.wait_for_timeout(200); start_new(cp, "Power")
        cp.add_style_tag(content="#toast { display: none !important; }")
        cast_reset(cp)
        tag = f"{vw}x{vh}"
        cp.wait_for_timeout(600)                                   # let the layout settle after the first draw
        pos0 = cp.evaluate(CAST_POS)
        # a quick press-and-release is the normal medium cast: same phase flow, lands near the old fixed spot
        cp.click("#actBtn"); cp.wait_for_timeout(60)
        quick = cp.evaluate("[F.phase, F.land, document.getElementById('meter').classList.contains('charging')]")
        check(f"{tag}: a quick press on CAST casts as before (casting, no power meter) and lands near the old spot (.58, .66)",
              quick[0] == "casting" and not quick[2] and abs(quick[1]["x"] - .58) <= .02 and abs(quick[1]["y"] - .66) <= .02, str(quick))
        if vw == 1536:
            cp.wait_for_function("F.phase === 'waiting'", timeout=3000); cp.wait_for_function("F.phase === 'bite'", timeout=8000)
            check(f"{tag}: quick cast keeps the phase flow casting > waiting > bite", True)
        cast_reset(cp)
        # hold: the meter shows in the reel meter's space, nothing moves, no scroll
        hold_btn(cp, 600)
        ch = cp.evaluate(CHARGING); pos1 = cp.evaluate(CAST_POS); ns1 = cp.evaluate(NO_SCROLL)
        prog = cp.evaluate("getComputedStyle(document.getElementById('isleProg')).visibility")
        if vw in (1536, 360): cp.screenshot(path=str(SHOTS / f"100_cast_power_{tag}.png"))
        cp.mouse.up(); cp.wait_for_timeout(50)
        check(f"{tag}: holding CAST for 600 ms shows the power meter (in the reel meter space, the island progress hides) and the page doesn't scroll", ch and prog == "hidden" and ns1, f"{ch} {prog} {ns1}")
        check(f"{tag}: the CAST button doesn't move while charging", same_pos(pos0, pos1), f"{pos0} {pos1}")
        cast_reset(cp)
        l600, h600 = timed_hold(cp, 600); cast_reset(cp)
        l1200, h1200 = timed_hold(cp, 1200)
        e600, e1200 = exp_power(h600), exp_power(h1200)
        check(f"{tag}: low power (600 ms) lands closer than high power (1200 ms); each lands where its real hold time says (+-.12 power)",
              abs(l600["p"] - e600) <= .12 and abs(l1200["p"] - e1200) <= .12 and (l600["x"] < l1200["x"] - .03 if e1200 - e600 > .3 else True) and e1200 - e600 > .1,
              f"{h600:.0f} ms p {l600['p']:.2f} (exp {e600:.2f}) x {l600['x']:.3f} | {h1200:.0f} ms p {l1200['p']:.2f} (exp {e1200:.2f}) x {l1200['x']:.3f}")
        phases = []
        for ph in ("casting", "waiting"):
            cp.wait_for_function(f"F.phase === '{ph}'", timeout=3000); phases.append(same_pos(cp.evaluate(CAST_POS), pos0))
        cp.wait_for_function("F.phase === 'bite'", timeout=8000); phases.append(same_pos(cp.evaluate(CAST_POS), pos0))
        check(f"{tag}: the CAST/HOOK button stays in the same place in every phase after a power cast (casting, waiting, bite)", all(phases), str(phases))
        ncharge = cp.evaluate("document.getElementById('meter').classList.contains('charging')")
        check(f"{tag}: the power meter isn't shown on the HOOK phase", not ncharge)
        cast_reset(cp)
        if vw != 1536 and vw != 360:
            cp.close(); continue
        # two quick casts never land on exactly the same spot (+-5% offset)
        lands = []
        for _ in range(4):
            cp.click("#actBtn"); cp.wait_for_timeout(40); lands.append(cp.evaluate("F.land")); cast_reset(cp)
        xs = [l["x"] for l in lands]
        check(f"{tag}: quick casts never land on exactly the same spot", len({(l["x"], l["y"]) for l in lands}) == 4 and max(xs) - min(xs) > .001, str([(round(l["x"], 4), round(l["y"], 4)) for l in lands]))
        # no power meter during waiting / bite / reeling, and holding in those phases does nothing but the normal action
        cp.click("#actBtn"); cp.wait_for_function("F.phase === 'waiting'", timeout=3000)
        sx, sy = center(cp, "#scene"); cp.mouse.move(sx, sy); cp.mouse.down(); cp.wait_for_timeout(450)
        w_ch = cp.evaluate("[document.getElementById('meter').classList.contains('charging'), F.phase]"); cp.mouse.up()
        cp.wait_for_function("F.phase === 'bite'", timeout=8000)
        cp.click("#actBtn"); cp.wait_for_timeout(100)
        r_ch = cp.evaluate("[document.getElementById('meter').classList.contains('charging'), F.phase, getComputedStyle(document.getElementById('meter')).visibility, getComputedStyle(document.querySelector('#meter .power')).display]")
        check(f"{tag}: the power meter never appears while waiting, on HOOK or while reeling", w_ch == [False, "waiting"] and r_ch == [False, "reeling", "visible", "none"], f"{w_ch} {r_ch}")
        cast_reset(cp)
        # not on other screens either: hold Space on the Home screen
        cp.evaluate("() => go('home')"); cp.keyboard.down("Space"); cp.wait_for_timeout(450)
        h_ch = cp.evaluate("[CH.on, document.getElementById('meter').classList.contains('charging'), F.phase]"); cp.keyboard.up("Space")
        check(f"{tag}: holding Space on another screen starts no charge", h_ch[0] is False and h_ch[1] is False and h_ch[2] == "idle", str(h_ch))
        cast_reset(cp)
        # release outside the scene / the button still casts, with that power
        hold_btn(cp, 1300, "#scene"); cp.mouse.move(3, 3); cp.mouse.up(); cp.wait_for_timeout(60)
        o1 = cp.evaluate("[F.phase, F.land && F.land.x]"); cast_reset(cp)
        hold_btn(cp, 1300); cp.mouse.move(3, 3); cp.mouse.up(); cp.wait_for_timeout(60)
        o2 = cp.evaluate("[F.phase, F.land && F.land.x]"); cast_reset(cp)
        check(f"{tag}: releasing outside the scene / the button still casts with the charged power", o1[0] == "casting" and o1[1] > .62 and o2[0] == "casting" and o2[1] > .62, f"{o1} {o2}")
        # a scene tap (quick) is a normal cast
        cp.mouse.click(sx, sy); cp.wait_for_timeout(60)
        st = cp.evaluate("[F.phase, F.land && Math.abs(F.land.x - .58) < .02]"); cast_reset(cp)
        check(f"{tag}: a quick tap on the scene casts a normal medium cast", st == ["casting", True], str(st))
        # Space: hold = stronger throw, quick press = normal
        cp.keyboard.down("Space"); cp.wait_for_timeout(1200); k_ch = cp.evaluate(CHARGING); cp.keyboard.up("Space"); cp.wait_for_timeout(60)
        k1 = cp.evaluate("[F.phase, F.land && F.land.x]"); cast_reset(cp)
        cp.keyboard.press("Space"); cp.wait_for_timeout(60); k2 = cp.evaluate("[F.phase, F.land && F.land.x]"); cast_reset(cp)
        check(f"{tag}: Space works: hold = meter and a far cast, quick press = medium cast", k_ch and k1[0] == "casting" and k1[1] > .62 and k2[0] == "casting" and abs(k2[1] - .58) < .02, f"{k_ch} {k1} {k2}")
        # Escape, window blur and a screen change cancel the charge cleanly
        hold_btn(cp, 500); e0 = cp.evaluate(CHARGING); cp.keyboard.press("Escape"); cp.wait_for_timeout(80)
        e1 = cp.evaluate("[CH.on, document.getElementById('meter').classList.contains('charging'), getComputedStyle(document.getElementById('meter')).visibility, getComputedStyle(document.getElementById('isleProg')).visibility, document.getElementById('fMsg').textContent]")
        cp.mouse.up(); cp.wait_for_timeout(80); e2 = cp.evaluate("[F.phase, document.getElementById('actBtn').disabled]")
        check(f"{tag}: Escape cancels the charge (meter gone, message back, nothing thrown on release)", e0 and e1[:4] == [False, False, "hidden", "visible"] and ("Ready" in e1[4] or "hold CAST" in e1[4]) and e2 == ["idle", False], f"{e0} {e1} {e2}")
        cp.keyboard.down("Space"); cp.wait_for_timeout(450); cp.keyboard.press("Escape"); cp.keyboard.up("Space"); cp.wait_for_timeout(80)
        check(f"{tag}: Escape also cancels a held Space (no cast)", cp.evaluate("[F.phase, CH.on]") == ["idle", False])
        hold_btn(cp, 450); cp.evaluate("() => window.dispatchEvent(new Event('blur'))"); cp.wait_for_timeout(80)
        b1 = cp.evaluate("[CH.on, document.getElementById('meter').classList.contains('charging')]"); cp.mouse.up(); cp.wait_for_timeout(60)
        check(f"{tag}: losing window focus cancels the charge", b1 == [False, False] and cp.evaluate("F.phase") == "idle", str(b1))
        hold_btn(cp, 450); cp.evaluate("() => go('map')"); cp.wait_for_timeout(100); cp.mouse.up()
        s1 = cp.evaluate("[CH.on, document.getElementById('meter').classList.contains('charging'), F.phase, current]")
        cp.evaluate("() => { island = 'harbor'; go('fishing'); }"); cp.wait_for_timeout(250)
        s2 = cp.evaluate("[document.getElementById('meter').classList.contains('charging'), getComputedStyle(document.getElementById('meter')).visibility, F.phase]")
        check(f"{tag}: changing screen cancels the charge, and the meter is gone when you come back", s1 == [False, False, "idle", "map"] and s2 == [False, "hidden", "idle"], f"{s1} {s2}")
        # touch pointers charge too
        cp.evaluate("""() => { const sc = document.getElementById('scene'), r = sc.getBoundingClientRect(); window.__tp = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
            sc.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 7, pointerType: 'touch', button: 0, bubbles: true, cancelable: true, clientX: __tp.x, clientY: __tp.y })); }""")
        cp.wait_for_timeout(1300); t_ch = cp.evaluate(CHARGING)
        cp.evaluate("() => document.dispatchEvent(new PointerEvent('pointerup', { pointerId: 7, pointerType: 'touch', bubbles: true }))"); cp.wait_for_timeout(60)
        t1 = cp.evaluate("[F.phase, F.land && F.land.x]")
        check(f"{tag}: a held touch pointer charges and throws too", t_ch and t1[0] == "casting" and t1[1] > .62, f"{t_ch} {t1}")
        cp.close()
    # landing spots are random in a small range, and the same code is used by every cast
    lp = b.new_page(viewport={"width": 1366, "height": 768}); lp.on("pageerror", lambda e: errs.append(str(e)))
    lp.goto(URL); lp.evaluate("localStorage.clear()"); lp.reload(); lp.wait_for_timeout(200)
    ls = lp.evaluate("Array.from({ length: 200 }, () => landing(.5))")
    lo = lp.evaluate("[landing(0), landing(1)]")
    check("landing(power): 200 medium casts are all different, within +-.06 of the old spot; power 0 is near (left, low) and 1 is far (right, high)",
          len({(l["x"], l["y"]) for l in ls}) == 200 and all(abs(l["x"] - .58) <= .06 and abs(l["y"] - .66) <= .04 for l in ls) and lo[0]["x"] < .52 and lo[1]["x"] > .64 and lo[0]["y"] > lo[1]["y"],
          f"{lo}")
    lp.close()
    # reduced motion: the meter fills once and holds at max (no ping-pong); normally it ping-pongs
    for reduced in (False, True):
        rc2 = b.new_context(viewport={"width": 1366, "height": 768}, reduced_motion="reduce" if reduced else "no-preference"); rq = rc2.new_page()
        rq.on("pageerror", lambda e: errs.append(str(e))); rq.on("console", lambda m: m.type == "error" and errs.append(m.text))
        rq.goto(URL); rq.evaluate("localStorage.clear()"); rq.reload(); rq.wait_for_timeout(200); start_new(rq, "Calm")
        rq.add_style_tag(content="#toast { display: none !important; }")
        res = []
        for ms in (1450, 2400):
            cast_reset(rq); hold_btn(rq, ms); rq.mouse.up(); rq.wait_for_timeout(40); res.append(rq.evaluate("F.land.x"))
        check(("reduced-motion emulated" if reduced else "normal motion") + ": the power meter ping-pongs (2.4 s lands nearer than 1.45 s), the setting is ignored", res[1] < res[0] - .04, str(res))
        rc2.close()
    # ---------- Playtest 1, parts 6-8: iOS long-press selection, quick casts vary, hold-to-charge hint ----------
    for vw, vh in [(1536, 730), (360, 640)]:
        tag = f"{vw}x{vh}"
        xp = b.new_page(viewport={"width": vw, "height": vh})
        xp.on("pageerror", lambda e: errs.append(str(e))); xp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        xp.goto(URL); xp.evaluate("localStorage.clear()"); xp.reload(); xp.wait_for_timeout(200)
        # the name input stays selectable and editable (Title > NEW GAME)
        xp.click("#newBtn"); xp.wait_for_timeout(150)
        ni = xp.evaluate("(() => { const i = document.getElementById('nameInput'), c = getComputedStyle(i); return [c.userSelect, c.webkitUserSelect]; })()")
        xp.fill("#nameInput", "Anglerx"); xp.focus("#nameInput"); xp.keyboard.press("Control+A")
        sel = xp.evaluate("(() => { const i = document.getElementById('nameInput'); return [i.selectionStart, i.selectionEnd, i.value]; })()")
        xp.keyboard.press("End"); xp.keyboard.type("y")
        check(f"{tag}: the player-name input stays selectable and editable (user-select text, Ctrl+A selects it, typing works)",
              ni[0] == "text" and sel == [0, 7, "Anglerx"] and xp.input_value("#nameInput") == "Anglerxy", f"{ni} {sel} {xp.input_value('#nameInput')}")
        xp.fill("#nameInput", "Power"); xp.click("#nameStart"); xp.wait_for_timeout(200)
        xp.add_style_tag(content="#toast { display: none !important; }")
        xp.evaluate("() => { island = 'harbor'; go('fishing'); }"); xp.wait_for_timeout(500)
        us = xp.evaluate("""() => ['actBtn', 'scene', 'sceneCanvas', 'rodChip', 'fMsg', 'sellTop'].map(id => { const c = getComputedStyle(document.getElementById(id));
            return [id, c.userSelect, c.webkitUserSelect, c.webkitTouchCallout || 'none', c.touchAction]; })""")
        check(f"{tag}: user-select is none on the CAST button, the scene, the canvas, the chips and the labels (no iOS selection handles / loupe)",
              all(r[1] == "none" for r in us), str(us))
        ta = {r[0]: r[4] for r in us}
        check(f"{tag}: touch-action is manipulation on the CAST button and the scene", ta["actBtn"] == "manipulation" and ta["scene"] == "manipulation", str(ta))
        cm = xp.evaluate("""() => ['actBtn', 'scene'].map(id => { const e = new MouseEvent('contextmenu', { bubbles: true, cancelable: true }); document.getElementById(id).dispatchEvent(e); return e.defaultPrevented; })""")
        check(f"{tag}: a contextmenu event (long press) on the CAST button and on the scene is default-prevented", cm == [True, True], str(cm))
        # pointercancel / lostpointercapture during a charge: meter hidden, nothing thrown, nothing stuck
        outs = []
        for kind in ("pointercancel", "lostpointercapture", "scene-touch-cancel"):
            xp.evaluate("() => { stopFishing(); renderFishingHud(); }"); xp.wait_for_timeout(100)
            if kind == "scene-touch-cancel":
                xp.evaluate("""() => { const sc = document.getElementById('scene'); sc.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 9, pointerType: 'touch', button: 0, bubbles: true, cancelable: true })); }""")
                xp.wait_for_timeout(450); shown = xp.evaluate(CHARGING)
                xp.evaluate("() => document.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 9, pointerType: 'touch', bubbles: true }))")
            else:
                x, y = center(xp, "#actBtn"); xp.mouse.move(x, y); xp.mouse.down(); xp.wait_for_timeout(450); shown = xp.evaluate(CHARGING)
                if kind == "pointercancel": xp.evaluate("() => document.dispatchEvent(new PointerEvent('pointercancel', { pointerId: CH.pid, bubbles: true }))")
                else: xp.evaluate("() => document.getElementById('actBtn').dispatchEvent(new PointerEvent('lostpointercapture', { pointerId: CH.pid, bubbles: true }))")
            xp.wait_for_timeout(80)
            st = xp.evaluate("[CH.on, document.getElementById('meter').classList.contains('charging'), getComputedStyle(document.getElementById('meter')).visibility, F.phase, document.getElementById('actBtn').disabled, document.getElementById('actBtn').textContent]")
            if kind != "scene-touch-cancel": xp.mouse.up()
            xp.evaluate("() => document.dispatchEvent(new PointerEvent('pointerup', { pointerId: 9, pointerType: 'touch', bubbles: true }))"); xp.wait_for_timeout(80)
            outs.append((kind, shown, st, xp.evaluate("F.phase")))
        check(f"{tag}: pointercancel / lostpointercapture during a charge hides the meter, throws nothing and leaves CAST usable (also after the late release)",
              all(o[1] and o[2] == [False, False, "hidden", "idle", False, "CAST"] and o[3] == "idle" for o in outs), str(outs))
        xp.evaluate("() => { stopFishing(); renderFishingHud(); }"); xp.click("#actBtn"); xp.wait_for_timeout(60)
        check(f"{tag}: after a cancelled charge a normal tap still casts", xp.evaluate("F.phase") == "casting")
        xp.close()
    # --- quick casts vary: 20 quick presses land at different distances inside a +-5% band around the medium cast ---
    qp = b.new_page(viewport={"width": 1366, "height": 768}); qp.on("pageerror", lambda e: errs.append(str(e))); qp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    qp.goto(URL); qp.evaluate("localStorage.clear()"); qp.reload(); qp.wait_for_timeout(200); start_new(qp, "Quick")
    qp.add_style_tag(content="#toast { display: none !important; }")
    qp.evaluate("() => { island = 'harbor'; go('fishing'); }"); qp.wait_for_timeout(500)
    ps = []
    for i in range(20):
        qp.evaluate("() => { stopFishing(); renderFishingHud(); }"); qp.wait_for_timeout(40)
        if i % 3 == 0: qp.click("#actBtn")
        elif i % 3 == 1: qp.mouse.click(*center(qp, "#scene"))
        else: qp.keyboard.press("Space")
        qp.wait_for_timeout(30); ps.append(qp.evaluate("F.land.p"))
    span = max(ps) - min(ps)
    check("20 quick casts (button, scene tap, Space) land at different distances: they span at least 4% of the throw range",
          span >= .04 and len(set(ps)) == 20, f"span {span:.3f}")
    check("20 quick casts stay inside the 10% band (+-5% of the throw range) around the medium cast", all(abs(p - .5) <= .0501 for p in ps), f"{min(ps):.3f}..{max(ps):.3f}")
    holds = []
    for ms in (450, 1300):
        qp.evaluate("() => { stopFishing(); renderFishingHud(); }"); qp.wait_for_timeout(60); l, h = timed_hold(qp, ms); holds.append((l["p"], exp_power(h)))
    check("hold casts still differ by power (the long hold lands farther) and follow their real hold time (+-.12)",
          holds[1][0] > holds[0][0] + .2 and all(abs(a - e) <= .12 for a, e in holds), str(holds))
    # --- the hint: new save shows it, 3 hold casts hide it, quick casts do not count, phases never show it ---
    TIP = "hold CAST to throw farther"
    qp.evaluate("() => { S.holdCasts = 0; save(); stopFishing(); renderFishingHud(); }"); qp.wait_for_timeout(100)
    m0 = qp.inner_text("#fMsg"); pos_tip = qp.evaluate(CAST_POS)
    qp.evaluate("() => { S.holdCasts = 3; save(); renderFishingHud(); }"); qp.wait_for_timeout(100)
    m3 = qp.inner_text("#fMsg"); pos_none = qp.evaluate(CAST_POS)
    check("hint: a new save shows 'Tip: hold CAST to throw farther' in the message line, a save with 3 hold casts doesn't, and CAST doesn't move",
          TIP in m0 and TIP not in m3 and "Ready" in m3 and same_pos(pos_tip, pos_none), f"{m0!r} {m3!r} {pos_tip} {pos_none}")
    qp.evaluate("() => { S.holdCasts = 0; save(); stopFishing(); renderFishingHud(); }"); qp.wait_for_timeout(60)
    qp.click("#actBtn"); qp.wait_for_timeout(60); q_cnt = qp.evaluate("S.holdCasts")        # a quick cast does not count
    seen = []
    for i in range(3):
        qp.evaluate("() => { stopFishing(); renderFishingHud(); }"); qp.wait_for_timeout(80)
        seen.append(TIP in qp.inner_text("#fMsg")); timed_hold(qp, 450)
    qp.evaluate("() => { stopFishing(); renderFishingHud(); }"); qp.wait_for_timeout(80)
    check("hint: quick casts don't count; it shows before each of the first 3 hold casts and is gone after the 3rd (counter saved)",
          q_cnt == 0 and seen == [True, True, True] and TIP not in qp.inner_text("#fMsg") and qp.evaluate("S.holdCasts") == 3 and qp.evaluate(SAVED + ".holdCasts") == 3,
          f"{q_cnt} {seen} {qp.inner_text('#fMsg')!r} {qp.evaluate(SAVED + '.holdCasts')}")
    qp.evaluate("() => { S.holdCasts = 0; save(); stopFishing(); renderFishingHud(); }"); qp.wait_for_timeout(60)
    qp.click("#actBtn"); qp.wait_for_function("F.phase === 'bite'", timeout=9000); b_msg = qp.inner_text("#fMsg")
    qp.click("#actBtn"); qp.wait_for_timeout(120); r_msg = qp.inner_text("#fMsg"); r_ph = qp.evaluate("F.phase")
    check("hint: never shown during bite, hook (reel) or reeling (the new-save counter is 0)", TIP not in b_msg and TIP not in r_msg and r_ph == "reeling", f"{b_msg!r} {r_msg!r} {r_ph}")
    qp.evaluate("() => stopFishing()")
    qp.close()
    # --- old saves without the counter load as 0 and keep working ---
    cs = b.new_page(viewport={"width": 1366, "height": 768}); cs.on("pageerror", lambda e: errs.append(str(e))); cs.on("console", lambda m: m.type == "error" and errs.append(m.text))
    cs.goto(URL)
    vals = cs.evaluate("[cleanSave({}).holdCasts, cleanSave({ holdCasts: 2 }).holdCasts, cleanSave({ holdCasts: -4 }).holdCasts, cleanSave({ holdCasts: 'x' }).holdCasts, cleanSave(null).holdCasts, cleanSave({ rod: 2, bait: 3 }).holdCasts]")
    cs.evaluate("""() => localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Oldie', coins: 120, rods: ['bamboo'], rodEq: 'bamboo', baits: { worm: 0, shrimp: 0, golden: 0 }, baitSel: 'none', bagMax: 5, bag: [], discovered: {}, records: {}, mastery: {}, totalCaught: 4 }))""")
    cs.reload(); cs.wait_for_timeout(300); cs.click("#contBtn"); cs.wait_for_timeout(200)
    cs.evaluate("() => { island = 'harbor'; go('fishing'); }"); cs.wait_for_timeout(300)
    old = cs.evaluate("[S.holdCasts, S.name, S.coins]"); old_msg = cs.inner_text("#fMsg")
    cs.click("#actBtn"); cs.wait_for_timeout(80)
    check("an old save without the hold counter loads as 0 (garbage too), CONTINUE works, the hint shows and CAST casts",
          vals == [0, 2, 0, 0, 0, 0] and old == [0, "Oldie", 120] and "hold CAST" in old_msg and cs.evaluate("F.phase") == "casting", f"{vals} {old} {old_msg!r}")
    cs.close()
    # --- scrolling still works in the Bag list and the Collection on a phone (user-select / touch-action don't block panning) ---
    sp2 = b.new_page(viewport={"width": 360, "height": 640}); sp2.on("pageerror", lambda e: errs.append(str(e))); sp2.on("console", lambda m: m.type == "error" and errs.append(m.text))
    sp2.goto(URL); sp2.evaluate("localStorage.clear()"); sp2.reload(); sp2.wait_for_timeout(200); start_new(sp2, "Scroller")
    sp2.evaluate("""() => { S.bagMax = 30; S.bag = FISH.slice(0, 14).map(f => ({ fishId: f.id, weight: f.min || 1, price: 10 })); FISH.forEach(f => S.discovered[f.id] = true); save(); go('bag'); }""")
    sp2.wait_for_timeout(300); x0, y0 = center(sp2, "#bagList")
    sp2.mouse.move(x0, y0); sp2.mouse.wheel(0, 400); sp2.wait_for_timeout(250)
    bag_sc = sp2.evaluate("[document.querySelector('#bag .scroll-list').scrollTop, window.scrollY, getComputedStyle(document.querySelector('#bag .scroll-list')).touchAction, getComputedStyle(document.body).touchAction]")
    sp2.evaluate("() => { go('collection'); }"); sp2.wait_for_timeout(300)
    sp2.mouse.move(180, 400); sp2.mouse.wheel(0, 500); sp2.wait_for_timeout(250)
    col_sc = sp2.evaluate("[window.scrollY, document.documentElement.scrollHeight > innerHeight]")
    check("the Bag list and the Collection still scroll (touch-action is not none there)",
          (bag_sc[0] > 0 or bag_sc[1] > 0) and bag_sc[2] != "none" and bag_sc[3] != "none" and col_sc[0] > 0, f"{bag_sc} {col_sc}")
    sp2.close()
    # ---------- Playtest 1, part 9: lock a fish in the Bag so SELL ALL keeps it ----------
    LK_FILL = """n => { S.bagMax = 8; S.bag = []; const isl = ['harbor', 'frost', 'desert', 'forest'];
        while (S.bag.length < n) { const i = S.bag.length; S.bag.push({ fishId: isl[i % 4] + '_' + (i % 10), weight: .5, price: 20 + i * 10, time: 1000 + i }); }
        save(); go('home'); go('bag'); }"""
    LK_GEO = """() => { const l = document.getElementById('bagList'), rows = [...l.querySelectorAll('.row')], btns = [...l.querySelectorAll('.lockbtn')],
        rb = id => document.getElementById(id).getBoundingClientRect(), L = l.getBoundingClientRect();
        return { rows: rows.length, h: rows.map(r => +r.getBoundingClientRect().height.toFixed(1)), lw: btns.map(x => Math.round(x.getBoundingClientRect().width)), lh: btns.map(x => Math.round(x.getBoundingClientRect().height)),
                 lab: btns.map(x => x.getAttribute('aria-label')), inside: rows.every(r => { const q = r.getBoundingClientRect(), s = r.querySelector('.btn').getBoundingClientRect(), k = r.querySelector('.lockbtn').getBoundingClientRect();
                     return q.right <= L.right + 1 && s.right <= q.right + 1 && k.right <= s.left + 1 && k.left >= q.left; }),
                 lockedCls: rows.filter(r => r.classList.contains('locked')).length, side: document.documentElement.scrollWidth, page: document.documentElement.scrollHeight, vw: innerWidth, vh: innerHeight,
                 all: document.getElementById('sellAll').innerText.trim(), sellAllTop: Math.round(rb('sellAll').top), noWrap: rows.every(r => r.querySelector('.grow').scrollHeight <= r.querySelector('.grow').clientHeight + 2) }; }"""
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600), (390, 844), (360, 640)]:
        tag = f"{vw}x{vh}"
        lp = b.new_page(viewport={"width": vw, "height": vh})
        lp.on("pageerror", lambda e: errs.append(str(e))); lp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        lp.goto(URL); lp.evaluate("localStorage.clear()"); lp.reload(); lp.wait_for_timeout(200); start_new(lp, "Locker")
        lp.evaluate(LK_FILL, 5); lp.wait_for_timeout(500)
        g0 = lp.evaluate(LK_GEO)
        lp.click("#bagList .row:nth-child(2) .lockbtn"); lp.wait_for_timeout(100)
        lp.click("#bagList .row:nth-child(4) .lockbtn"); lp.wait_for_timeout(100)
        g1 = lp.evaluate(LK_GEO)
        check(f"{tag}: every Bag row has a lock button of at least 40x40 with aria-label 'Lock fish'; tapping locks it ('Unlock fish'), locked rows are marked",
              g0["rows"] == 5 and min(g0["lw"]) >= 40 and min(g0["lh"]) >= 40 and set(g0["lab"]) == {"Lock fish"} and g0["lockedCls"] == 0
              and g1["lab"] == ["Lock fish", "Unlock fish", "Lock fish", "Unlock fish", "Lock fish"] and g1["lockedCls"] == 2 and lp.evaluate("S.bag.map(x => !!x.locked)") == [False, True, False, True, False], f"{g0} {g1}")
        check(f"{tag}: rows keep one constant height whether locked or not, the lock + SELL fit inside each row, names don't wrap, SELL ALL doesn't move, no page or side scroll",
              len(set(g0["h"] + g1["h"])) == 1 and g1["inside"] and g1["noWrap"] and g0["sellAllTop"] == g1["sellAllTop"] and g1["side"] <= g1["vw"] and (g1["page"] <= g1["vh"] or (vw < 900 and g1["page"] == g0["page"])), f"{g0['h']} {g1['h']} {g1}")
        lp.close()

    for vw, vh in [(1536, 730), (360, 640)]:
        tag = f"{vw}x{vh}"
        lp = b.new_page(viewport={"width": vw, "height": vh})
        lp.on("pageerror", lambda e: errs.append(str(e))); lp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        lp.goto(URL); lp.evaluate("localStorage.clear()"); lp.reload(); lp.wait_for_timeout(200); start_new(lp, "Locker")
        lp.evaluate(LK_FILL, 5); lp.wait_for_timeout(400)
        prices = lp.evaluate("S.bag.map(x => x.price)")      # 20 30 40 50 60
        lp.click("#bagList .row:nth-child(1) .lockbtn"); lp.click("#bagList .row:nth-child(5) .lockbtn"); lp.wait_for_timeout(100)
        want_total = prices[1] + prices[2] + prices[3]
        lbl = lp.inner_text("#sellAll")
        check(f"{tag}: the SELL ALL button shows the value of the unlocked fish only ({want_total})", str(want_total) in lbl.replace(",", "") and "SELL ALL" in lbl, lbl)
        # single sell of a locked fish is blocked
        c0 = lp.evaluate("S.coins"); lp.click("#bagList .row:nth-child(1) .btn"); lp.wait_for_timeout(120)
        check(f"{tag}: selling a locked fish one by one is blocked: toast 'Unlock it first', fish and coins unchanged",
              "Unlock it first" in lp.inner_text("#toast") and lp.evaluate("S.bag.length") == 5 and lp.evaluate("S.coins") == c0)
        lp.screenshot(path=str(SHOTS / f"101_bag_locks_{tag}.png"))
        # the lock survives a reload (CONTINUE)
        lp.reload(); lp.wait_for_timeout(300); lp.click("#contBtn"); lp.wait_for_timeout(300); lp.evaluate("go('bag')"); lp.wait_for_timeout(300)
        check(f"{tag}: the lock is saved: after a reload the same two fish are locked", lp.evaluate("S.bag.map(x => !!x.locked)") == [True, False, False, False, True]
              and lp.evaluate("document.querySelectorAll('#bagList .row.locked').length") == 2)
        # SELL ALL skips the locked fish
        c0 = lp.evaluate("S.coins"); lp.click("#sellAll"); lp.wait_for_timeout(200)
        left = lp.evaluate("S.bag.map(x => x.price)")
        check(f"{tag}: SELL ALL sells only the unlocked fish: the 2 locked ones stay, coins rise by exactly their total",
              left == [prices[0], prices[4]] and lp.evaluate("S.coins") - c0 == want_total and lp.evaluate("S.bag.every(x => x.locked)"), f"{left} {lp.evaluate('S.coins') - c0} want {want_total}")
        # all locked: toast, nothing sold, the bag still counts toward capacity
        c0 = lp.evaluate("S.coins"); lp.click("#sellAll"); lp.wait_for_timeout(120)
        check(f"{tag}: with every fish locked SELL ALL shows 'All your fish are locked' and sells nothing",
              "All your fish are locked" in lp.inner_text("#toast") and lp.evaluate("S.bag.length") == 2 and lp.evaluate("S.coins") == c0 and lp.inner_text("#sellAll").strip() == "SELL ALL")
        # unlock again and it can be sold one by one
        lp.click("#bagList .row:nth-child(1) .lockbtn"); lp.wait_for_timeout(80)
        check(f"{tag}: unlocking makes a fish sellable again", lp.get_attribute("#bagList .row:nth-child(1) .lockbtn", "aria-label") == "Lock fish" and lp.evaluate("!S.bag[0].locked"))
        lp.click("#bagList .row:nth-child(1) .btn"); lp.wait_for_timeout(120)
        check(f"{tag}: ...and a single sell then works", lp.evaluate("S.bag.length") == 1 and lp.evaluate("S.coins") == c0 + prices[0])
        lp.close()

    # Golden Hook (+20%): the stored price already holds the bonus, so SELL ALL pays exactly the unlocked prices
    lp = b.new_page(viewport={"width": 1536, "height": 730})
    lp.on("pageerror", lambda e: errs.append(str(e))); lp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    lp.goto(URL); lp.evaluate("localStorage.clear()"); lp.reload(); lp.wait_for_timeout(200); start_new(lp, "Hooker")
    lp.evaluate("() => { S.mastery.harbor = true; S.bagMax = 8; save(); }")
    for fid in ["harbor_2", "harbor_5", "harbor_7"]:
        lp.evaluate(f"() => {{ F = {{ phase: 'idle', fish: fishById('{fid}') }}; caught(); }}"); lp.wait_for_timeout(150); lp.click("#keepBtn"); lp.wait_for_timeout(200)
    pr = lp.evaluate("S.bag.map(x => x.price)")
    lp.evaluate("go('bag')"); lp.wait_for_timeout(300); lp.click("#bagList .row:nth-child(2) .lockbtn"); lp.wait_for_timeout(100)
    c0 = lp.evaluate("S.coins"); lp.click("#sellAll"); lp.wait_for_timeout(200)
    check("Golden Hook active: SELL ALL pays exactly the unlocked fish (bonus included) and keeps the locked one",
          len(pr) == 3 and lp.evaluate("S.coins") - c0 == pr[0] + pr[2] and lp.evaluate("S.bag.length") == 1 and lp.evaluate("S.bag[0].price") == pr[1], f"{pr} {lp.evaluate('S.coins') - c0}")
    # a full bag: locked fish still count toward capacity; the Result screen's SELL A FISH never sells a locked fish
    lp.evaluate("() => { S.bagMax = 3; S.bag = [{ fishId: 'harbor_0', weight: 1, price: 50, time: 1, locked: true }, { fishId: 'harbor_1', weight: 1, price: 90, time: 2 }, { fishId: 'harbor_3', weight: 1, price: 70, time: 3, locked: true }]; save(); }")
    lp.evaluate("() => { F = { phase: 'idle', fish: fishById('harbor_4') }; caught(); }"); lp.wait_for_timeout(1200)
    full_ok = lp.evaluate("bagFull()") and lp.is_visible("#fullBag") and lp.is_visible("#sellOneBtn")
    info = lp.inner_text("#sellOneInfo"); c0 = lp.evaluate("S.coins")
    lp.click("#sellOneBtn"); lp.wait_for_timeout(300)
    check("full bag with locked fish: they still count toward capacity, SELL A FISH sells the cheapest UNLOCKED fish and keeps the new catch",
          full_ok and lp.evaluate("fishById('harbor_1').name") in info and lp.evaluate("S.coins") - c0 == 90 and lp.evaluate("S.bag.length") == 3
          and lp.evaluate("S.bag.filter(x => x.locked).length") == 2 and lp.evaluate("S.bag.some(x => x.fishId === 'harbor_4')"), f"{info} {lp.evaluate('S.bag')}")
    lp.evaluate("() => { S.bag.forEach(x => x.locked = true); S.pending = null; save(); }")
    lp.evaluate("() => { F = { phase: 'idle', fish: fishById('harbor_6') }; caught(); }"); lp.wait_for_timeout(1200)
    check("full bag, every fish locked: SELL A FISH is disabled with an explanation; RELEASE and OPEN BAG still work",
          lp.is_visible("#sellOneBtn") and lp.is_disabled("#sellOneBtn") and "locked" in lp.inner_text("#sellOneInfo") and lp.is_visible("#fullRelease") and lp.is_visible("#resBagBtn"))
    lp.click("#fullRelease"); lp.wait_for_timeout(300)
    check("the top-bar SELL glows while the bag is full of locked fish, and the bag stays full", lp.evaluate("bagFull() && document.getElementById('sellTop').classList.contains('glow')") and lp.evaluate("S.bag.length") == 3)
    lp.close()

    # old saves without the flag load as unlocked; garbage flags too
    lp = b.new_page(viewport={"width": 1536, "height": 730})
    lp.on("pageerror", lambda e: errs.append(str(e))); lp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    lp.goto(URL)
    lp.evaluate("""() => localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Oldie', coins: 120, rods: ['bamboo'], rodEq: 'bamboo', bagMax: 5,
        bag: [{ fishId: 'harbor_0', weight: 1, price: 30, time: 1 }, { fishId: 'harbor_1', weight: 1, price: 40, time: 2, locked: 'yes' }, { fishId: 'harbor_2', weight: 1, price: 50, time: 3, locked: true }] }))""")
    lp.reload(); lp.wait_for_timeout(300); lp.click("#contBtn"); lp.wait_for_timeout(300); lp.evaluate("go('bag')"); lp.wait_for_timeout(300)
    check("an old save without the locked flag loads as unlocked (garbage flags too), the Bag renders and SELL ALL totals the unlocked fish",
          lp.evaluate("S.bag.map(x => x.locked)") == [False, False, True] and "70" in lp.inner_text("#sellAll") and lp.evaluate("document.querySelectorAll('#bagList .lockbtn').length") == 3)
    lp.evaluate("() => { localStorage.setItem('littleLakeSave', '{\"bag\": [null, 5, {\"fishId\": \"harbor_0\", \"weight\": 1, \"price\": 3}]}'); }")
    lp.reload(); lp.wait_for_timeout(300)
    check("a broken save with odd bag entries still loads (entries without the flag are unlocked)", lp.evaluate("S.bag.length") == 1 and lp.evaluate("S.bag[0].locked") is False)
    howtxt = lp.evaluate("document.getElementById('howBox').textContent")
    check("HOW TO PLAY says: Lock a fish in the Bag to keep it from SELL ALL.", "Lock a fish in the Bag to keep it from SELL ALL." in howtxt)
    lp.close()
    # ---------- Playtest 1, part 10: 13 new creature species with 9 new body plans (jellyfish, crab, seahorse, shark, squid, turtle, frog, axolotl, crayfish) ----------
    NEW_SPECIES = {  # id: (name, rarity, plan)
        "harbor_1": ("Moon Jellyfish", "Common", "jellyfish"), "harbor_2": ("Hermit Crab", "Common", "crab"), "harbor_5": ("Seahorse", "Rare", "seahorse"), "harbor_7": ("Reef Shark", "Epic", "shark"),
        "frost_2": ("Snow Crab", "Common", "crab"), "frost_6": ("Comb Jelly", "Rare", "jellyfish"), "frost_8": ("Greenland Shark", "Epic", "shark"), "frost_9": ("Aurora Squid", "Legendary", "squid"),
        "desert_2": ("Oasis Turtle", "Common", "turtle"), "desert_5": ("Oasis Crayfish", "Rare", "crayfish"),
        "forest_2": ("Green Frog", "Common", "frog"), "forest_6": ("Axolotl", "Rare", "axolotl"), "forest_8": ("Snapping Turtle", "Epic", "turtle")}
    OLD_PRICES = {"harbor_1": 25, "harbor_2": 30, "harbor_5": 70, "harbor_7": 150, "frost_2": 25, "frost_6": 60, "frost_8": 200, "frost_9": 480, "desert_2": 15, "desert_5": 60, "forest_2": 20, "forest_6": 65, "forest_8": 210}
    OLD_RARITY = {"harbor_1": "Common", "harbor_2": "Common", "harbor_5": "Rare", "harbor_7": "Epic", "frost_2": "Common", "frost_6": "Rare", "frost_8": "Epic", "frost_9": "Legendary",
                  "desert_2": "Common", "desert_5": "Rare", "forest_2": "Common", "forest_6": "Rare", "forest_8": "Epic"}
    fp = b.new_page(viewport={"width": 1536, "height": 730})
    fp.on("pageerror", lambda e: errs.append(str(e))); fp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    fp.goto(URL); fp.evaluate("localStorage.clear()"); fp.reload(); fp.wait_for_timeout(300)
    data = fp.evaluate("""() => ({ fish: FISH.map(f => ({ id: f.id, name: f.name, rarity: f.rarity, price: f.price, plan: f.plan, island: f.island })), ids: FISH.map(f => f.id) })""")
    by = {f["id"]: f for f in data["fish"]}
    check("the 13 new species sit in the listed slots with the listed names, the same rarity and the same price as the species they replaced",
          all(by[i]["name"] == n and by[i]["rarity"] == r and OLD_RARITY[i] == r and by[i]["price"] == OLD_PRICES[i] for i, (n, r, pl) in NEW_SPECIES.items()), str({i: by[i]["name"] for i in NEW_SPECIES}))
    check("each new species has its own plan field (jellyfish, crab, seahorse, shark, squid, turtle, frog, axolotl, crayfish) and no other fish has one",
          all(by[i]["plan"] == pl for i, (n, r, pl) in NEW_SPECIES.items()) and all(f["plan"] is None for f in data["fish"] if f["id"] not in NEW_SPECIES)
          and set(f["plan"] for f in data["fish"] if f["plan"]) == {"jellyfish", "crab", "seahorse", "shark", "squid", "turtle", "frog", "axolotl", "crayfish"})
    rc = {}
    for f in data["fish"]:
        if f["island"] != "secret": rc.setdefault(f["island"], {}).setdefault(f["rarity"], 0); rc[f["island"]][f["rarity"]] += 1
    check("every island still has 4 Common, 3 Rare, 2 Epic, 1 Legendary; the secret island has the one Mythical Lake Guardian; 41 fish in all",
          all(v == {"Common": 4, "Rare": 3, "Epic": 2, "Legendary": 1} for v in rc.values()) and len(rc) == 4 and by["secret_0"]["rarity"] == "Mythical" and by["secret_0"]["name"] == "Lake Guardian" and len(data["fish"]) == 41, str(rc))
    exp_ids = [f"{i}_{n}" for i in ["harbor", "frost", "desert", "forest"] for n in range(10)] + ["secret_0"]
    check("all fish ids are unchanged (harbor_0..9, frost_0..9, desert_0..9, forest_0..9, secret_0) and unique", data["ids"] == exp_ids)
    others = [f["name"] for f in data["fish"] if f["id"] not in NEW_SPECIES]
    check("the other 28 species keep their names (e.g. Sardine, Clownfish, Manta Ray, Spirit Koi)", len(others) == 28 and all(n in others for n in ["Sardine", "Mackerel", "Clownfish", "Pufferfish", "Manta Ray", "Oarfish", "Ice Pike", "Spirit Koi", "Lake Guardian"]))
    px = fp.evaluate("""ids => { const out = {};
        for (const id of ids) { const f = fishById(id), cv = document.createElement('canvas'); drawFish(cv, f);
          const d = cv.getContext('2d').getImageData(0, 0, 24, 16).data; let n = 0, bits = '';
          for (let i = 3; i < d.length; i += 4) { n += d[i] ? 1 : 0; bits += d[i] ? '1' : '0'; }
          const sc = document.createElement('canvas'); silhouette(sc, f); const sd = sc.getContext('2d').getImageData(0, 0, 24, 16).data; let sn = 0; for (let i = 3; i < sd.length; i += 4) sn += sd[i] ? 1 : 0;
          const maps = FISH_PLANS[f.plan]; const mapOk = maps.length === 16 && maps.every(r => r.length === 24);
          out[id] = { n, w: cv.width, h: cv.height, bits, sn, mapOk }; }
        return out; }""", list(NEW_SPECIES))
    check("every new species draws on a 24x16 canvas with at least 12 non-transparent pixels, its plan map is exactly 16 rows x 24 columns, and its undiscovered silhouette is drawn too",
          all(v["w"] == 24 and v["h"] == 16 and v["n"] >= 12 and v["mapOk"] and v["sn"] >= 12 for v in px.values()), str({k: v["n"] for k, v in px.items()}))
    bitsets = {}
    for i, (n, r, pl) in NEW_SPECIES.items(): bitsets.setdefault(pl, set()).add(px[i]["bits"])
    check("the 9 plans have 9 different silhouettes, and the plans shared by two species (crab, jellyfish, shark, turtle) draw the same outline", len({next(iter(s)) for s in bitsets.values()}) == 9 and all(len(s) <= 2 for s in bitsets.values()))
    cmp = fp.evaluate("""() => { const mask = f => { const cv = document.createElement('canvas'); drawFish(cv, f); const d = cv.getContext('2d').getImageData(0, 0, 24, 16).data; let s = ''; for (let i = 3; i < d.length; i += 4) s += d[i] ? '1' : '0'; return s; };
        const fish = FISH.filter(f => !f.plan).map(mask); const plans = ['harbor_1','harbor_2','harbor_5','harbor_7','frost_9','desert_2','forest_2','forest_6','desert_5'].map(id => mask(fishById(id)));
        return plans.map(m => Math.min(...fish.map(o => { let diff = 0; for (let i = 0; i < m.length; i++) if (m[i] !== o[i]) diff++; return diff; }))); }""")
    check("every new silhouette differs clearly from every ordinary fish at 24x16 (at least 40 pixels apart)", all(d >= 40 for d in cmp), str(cmp))
    # Collection with everything found: all 4 islands, screenshots; Bag shows the new names; Result cards
    start_new(fp, "Artist")
    fp.evaluate("() => { FISH.forEach(f => { S.discovered[f.id] = true; S.records[f.id] = f.max; }); S.bagMax = 15; save(); go('collection'); }"); fp.wait_for_timeout(400)
    for isl, nm in [("harbor", "Harbor"), ("frost", "Frost"), ("desert", "Desert"), ("forest", "Forest")]:
        fp.click(f"#tabs .tab:has-text('{nm}')"); fp.wait_for_timeout(300)
        txt = fp.inner_text("#collGrid"); want = [v[0] for i, v in NEW_SPECIES.items() if i.startswith(isl)]
        sizes = fp.evaluate("[...document.querySelectorAll('#collGrid canvas')].map(c => [c.width, c.height])")
        check(f"Collection {nm}: the new species show their names ({', '.join(want)}), 10 cards, every drawing 24x16", all(w in txt for w in want) and len(sizes) == 10 and all(s == [24, 16] for s in sizes))
        fp.screenshot(path=str(SHOTS / f"102_collection_{isl}_1536x730.png"))
    fp.evaluate("() => { S.discovered = {}; S.records = {}; save(); go('home'); go('collection'); }"); fp.wait_for_timeout(300)
    unk = fp.evaluate("() => { const c = [...document.querySelectorAll('#collGrid .cell')]; return [c.length, c.every(x => x.classList.contains('unknown')), c.every(x => x.textContent.includes('Not found yet')), document.getElementById('collGrid').textContent.includes('Moon')]; }")
    check("undiscovered fish still show the silhouette cards ('Not found yet', no name leaked)", unk[0] == 10 and unk[1] and unk[2] and not unk[3])
    fp.evaluate("() => { S.discovered = { harbor_1: true, harbor_7: true }; S.records = { harbor_1: 1.2 }; save(); go('home'); go('collection'); }"); fp.wait_for_timeout(300); fp.click("#tabs .tab:has-text('Harbor')"); fp.wait_for_timeout(200)
    fnd = fp.inner_text("#collGrid")
    check("an old save that had discovered harbor_1 now shows Moon Jellyfish as found (ids unchanged, no migration)", "Moon Jellyfish" in fnd and "Reef Shark" in fnd and "Seahorse" not in fnd and "Best: 1.2 kg" in fnd)
    fp.evaluate("() => { S.bag = ['harbor_1', 'frost_9', 'forest_8', 'desert_5', 'forest_6'].map((id, i) => ({ fishId: id, weight: 1, price: 50 + i, time: i })); save(); go('home'); go('bag'); }"); fp.wait_for_timeout(400)
    bag = fp.inner_text("#bagList")
    check("the Bag lists the new names (Moon Jellyfish, Aurora Squid, Snapping Turtle, Oasis Crayfish, Axolotl)", all(n in bag for n in ["Moon Jellyfish", "Aurora Squid", "Snapping Turtle", "Oasis Crayfish", "Axolotl"]))
    fp.screenshot(path=str(SHOTS / "102_bag_new_fish_1536x730.png"))
    fp.evaluate("() => { S.bag = []; S.bagMax = 5; save(); }")
    for fid, tag in [("harbor_1", "moon_jellyfish"), ("harbor_7", "reef_shark"), ("frost_9", "aurora_squid"), ("forest_8", "snapping_turtle")]:
        fp.evaluate(f"() => {{ S.pending = null; F = {{ phase: 'idle', fish: fishById('{fid}') }}; caught(); }}"); fp.wait_for_timeout(1300)
        shown = fp.inner_text("#resName")
        check(f"Result card shows {NEW_SPECIES[fid][0]}", NEW_SPECIES[fid][0] in shown and fp.is_visible("#resCanvas"), shown)
        fp.screenshot(path=str(SHOTS / f"102_result_{tag}_1536x730.png"))
        fp.evaluate("() => { S.pending = null; save(); go('home'); }"); fp.wait_for_timeout(200)
    # an old save (with fish ids from before) still loads
    fp.evaluate("""() => localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Oldie', coins: 90, rods: ['bamboo'], rodEq: 'bamboo', bagMax: 5,
        bag: [{ fishId: 'harbor_1', weight: 1, price: 25, time: 1 }, { fishId: 'forest_8', weight: 9, price: 200, time: 2 }], discovered: { harbor_1: true, forest_8: true, frost_9: true }, records: { frost_9: 4 } }))""")
    fp.reload(); fp.wait_for_timeout(300); fp.click("#contBtn"); fp.wait_for_timeout(300); fp.evaluate("go('bag')"); fp.wait_for_timeout(300)
    check("an old save with fish ids harbor_1, forest_8, frost_9 loads: the bag and Collection show the new species", "Moon Jellyfish" in fp.inner_text("#bagList") and "Snapping Turtle" in fp.inner_text("#bagList")
          and fp.evaluate("totalDisc()") == 3)
    fp.close()
    # ---------- Playtest 1, part 11: audible effects, procedural music, separate Sound / Music switches ----------
    ap = b.new_page(viewport={"width": 1280, "height": 720})
    ap.on("pageerror", lambda e: errs.append(str(e))); ap.on("console", lambda m: m.type == "error" and errs.append(m.text))
    ap.goto(URL); ap.evaluate("localStorage.clear()"); ap.reload(); ap.wait_for_timeout(400)
    check("before the first gesture there is no AudioContext and no music (nothing extra on first load)", ap.evaluate("typeof AC") == "undefined" and ap.evaluate("audioState().theme") is None)
    ap.click("#howBtn"); ap.wait_for_timeout(700); ap.click("#howOk"); ap.wait_for_timeout(300)
    st = ap.evaluate("audioState()")
    check("the first gesture creates the shared AudioContext and it is running (resumed)", ap.evaluate("typeof AC") == "object" and st["ctx"] == "running", str(st))
    check("Sound ON: sfx bus and master gain are above 0; Music ON: music bus is 0.25, well below the effects", st["master"] > 0 and st["sfx"] > 0 and abs(st["music"] - .25) < .001 and st["music"] < st["sfx"], str(st))
    check("the music scheduler started after the gesture with the home theme and keeps scheduling notes", st["theme"] == "home" and st["ticking"] is True, str(st))
    n0 = ap.evaluate("audioState().notes"); ap.wait_for_timeout(2500); n1 = ap.evaluate("audioState().notes")
    check("the scheduler keeps adding notes ahead of time (audio clock), not in one burst", n1 > n0 and n1 - n0 < 40, f"{n0} -> {n1}")
    sfx_names = ["whoosh", "splash", "cast", "bite", "hit", "miss", "fail", "catch", "coin", "click", "tick"]
    res = ap.evaluate("""names => names.map(n => { try { if (typeof sfx[n] !== 'function') return n + ': missing'; sfx[n](); return 'ok'; } catch (e) { return n + ': ' + e.message; } })""", sfx_names)
    check("every sound effect function exists (whoosh, splash, cast, bite, hit, miss, fail, catch, coin, click) and runs without throwing", all(r == "ok" for r in res), str(res))
    ap.wait_for_timeout(500)
    ev = ap.evaluate("""() => { const q = []; const wrap = (o, k) => { const f = o[k]; o[k] = (...a) => { q.push(k); return f(...a); }; };
        const bad = []; for (const v of [[220, .1, 'sine', .22], [440, .2, 'square', .3, .05, { to: 880 }]]) { try { tone(...v); } catch (e) { bad.push(e.message); } }
        try { beep(500); noise(.2, .2, 'lowpass', 2000, 300); } catch (e) { bad.push(e.message); } return bad; }""")
    check("tone(), noise() and the old beep() run without throwing", ev == [])
    pk = ap.evaluate("""async () => { const an = AC.createAnalyser(); an.fftSize = 2048; AUD.master.connect(an); const buf = new Float32Array(2048);
        const peak = async ms => { let m = 0; const t0 = performance.now(); while (performance.now() - t0 < ms) { an.getFloatTimeDomainData(buf); for (const v of buf) m = Math.max(m, Math.abs(v)); await new Promise(r => setTimeout(r, 15)); } return m; };
        const out = {}; musicStop(.01); await new Promise(r => setTimeout(r, 300));
        for (const k of ['whoosh', 'splash', 'bite', 'hit', 'miss', 'fail', 'catch', 'coin', 'tick']) { sfx[k](); out[k] = await peak(450); }
        musicStart('home'); out.music = await peak(2500); return out; }""")
    sfx_min = min(v for k, v in pk.items() if k != "music")
    check("the effects are audible (every one peaks above 0.1 on the master output) and the music is clearly quieter than the effects", sfx_min > .1 and .03 < pk["music"] < .6 * sfx_min + .1 and pk["music"] < max(v for k, v in pk.items() if k != "music"), str({k: round(v, 2) for k, v in pk.items()}))
    # switches
    ap.evaluate("() => go('titleScreen')"); ap.wait_for_timeout(200)
    ap.click("#soundBtn"); ap.wait_for_timeout(200)
    s2 = ap.evaluate("audioState()")
    check("Sound OFF: the effects bus is 0 (master stays open for the music); the button says OFF and aria-pressed is false; S.sound saved",
          s2["sfx"] == 0 and s2["master"] > 0 and "OFF" in ap.inner_text("#soundBtn") and ap.get_attribute("#soundBtn", "aria-pressed") == "false" and ap.evaluate("S.sound") is False)
    ap.click("#musicBtn"); ap.wait_for_timeout(500)
    s3 = ap.evaluate("audioState()")
    check("Music OFF as well: the master gain is 0, the scheduler stopped and no theme is playing; button says OFF, aria-pressed false",
          s3["master"] == 0 and s3["music"] == 0 and s3["theme"] is None and s3["ticking"] is False and "OFF" in ap.inner_text("#musicBtn") and ap.get_attribute("#musicBtn", "aria-pressed") == "false" and ap.evaluate("S.music") is False, str(s3))
    sv = ap.evaluate("JSON.parse(localStorage.getItem('littleLakeSave'))")
    check("both toggles are saved before any game exists, and that still doesn't count as a save (CONTINUE disabled)", sv == {"sound": False, "music": False} and ap.is_disabled("#contBtn"), str(sv))
    ap.reload(); ap.wait_for_timeout(400)
    check("after a reload both buttons still say OFF and nothing plays", "SOUND: OFF" in ap.inner_text("#soundBtn") and "MUSIC: OFF" in ap.inner_text("#musicBtn") and ap.evaluate("S.music") is False)
    ap.click("#musicBtn"); ap.wait_for_timeout(500)
    s4 = ap.evaluate("audioState()")
    check("Music ON again (Sound still off): the theme plays, master > 0, effects bus 0", s4["theme"] == "home" and s4["ticking"] is True and s4["master"] > 0 and s4["sfx"] == 0 and "MUSIC: ON" in ap.inner_text("#musicBtn"), str(s4))
    ap.click("#soundBtn"); ap.wait_for_timeout(200)
    check("Sound ON again: effects bus open", ap.evaluate("audioState().sfx") == 1 and "SOUND: ON" in ap.inner_text("#soundBtn"))
    # themes follow the island
    start_new(ap, "Tuner"); ap.wait_for_timeout(300)
    themes = {}
    for isl in ["harbor", "frost", "desert", "forest", "secret"]:
        ap.evaluate(f"() => {{ island = '{isl}'; go('fishing'); }}"); ap.wait_for_timeout(250); themes[isl] = ap.evaluate("audioState().theme")
    ap.evaluate("() => go('map')"); ap.wait_for_timeout(250); themes["map"] = ap.evaluate("audioState().theme")
    check("the music theme changes with the island (harbor, frost, desert, forest, secret) and goes back to home on the other screens", themes == {"harbor": "harbor", "frost": "frost", "desert": "desert", "forest": "forest", "secret": "secret", "map": "home"}, str(themes))
    check("the six themes exist with 8 bars of melody each and keep scheduling after a change", ap.evaluate("Object.keys(THEMES).sort().join()") == "desert,forest,frost,harbor,home,secret"
          and ap.evaluate("Object.values(THEMES).every(T => T.m.length === 64 && T.chords.length === 8)") and ap.evaluate("audioState().ticking") is True)
    # ducking during the REEL minigame
    ap.evaluate("() => { island = 'harbor'; go('fishing'); }"); ap.wait_for_timeout(400)
    d0 = ap.evaluate("audioState().duck")
    ap.evaluate("() => { F = { phase: 'bite', fish: fishById('harbor_0') }; hook(); }"); ap.wait_for_timeout(500)
    d1 = ap.evaluate("audioState().duck")
    ap.evaluate("() => escape('test')"); ap.wait_for_timeout(500)
    d2 = ap.evaluate("audioState().duck")
    check("the music ducks to about 40% while reeling and comes back afterwards", d0 > .95 and .35 <= d1 <= .5 and d2 > .95, f"{d0} {d1} {d2}")
    # cast: whoosh at the start, splash when the bobber lands
    ap.evaluate("() => { window.__c = []; ['whoosh', 'splash'].forEach(k => { const f = sfx[k]; sfx[k] = () => { window.__c.push(k); f(); }; }); sfx.cast = sfx.whoosh; }")
    ap.evaluate("() => { stopFishing(); go('home'); island = 'harbor'; go('fishing'); }"); ap.wait_for_timeout(300)
    ap.click("#actBtn"); ap.wait_for_timeout(900)
    check("a cast plays the whoosh when it starts and the splash when the bobber lands", ap.evaluate("window.__c") == ["whoosh", "splash"], str(ap.evaluate("window.__c")))
    # a hidden tab is silent
    ap.evaluate("() => { Object.defineProperty(document, 'hidden', { value: true, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }"); ap.wait_for_timeout(300)
    h = ap.evaluate("audioState()")
    ap.evaluate("() => { Object.defineProperty(document, 'hidden', { value: false, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); }"); ap.wait_for_timeout(700)
    v = ap.evaluate("audioState()")
    check("the music pauses when the tab is hidden and resumes when it is visible again", h["ticking"] is False and h["ctx"] == "suspended" and v["ticking"] is True and v["ctx"] == "running", f"{h} {v}")
    check("the HOW TO PLAY dialog has the silent-switch line", "No sound on iPhone? Turn off the silent switch on the side of the phone." in ap.evaluate("document.getElementById('howBox').textContent"))
    ap.close()
    # a failing audio engine never breaks the game
    bp2 = b.new_page(viewport={"width": 1280, "height": 720}); perr = []
    bp2.on("pageerror", lambda e: perr.append(str(e)))
    bp2.add_init_script("window.AudioContext = function () { throw new Error('no audio here'); }; window.webkitAudioContext = undefined;")
    bp2.goto(URL); bp2.evaluate("localStorage.clear()"); bp2.reload(); bp2.wait_for_timeout(300)
    bp2.click("#howBtn"); bp2.click("#howOk"); bp2.click("#musicBtn"); bp2.click("#soundBtn")
    start_new(bp2, "Mute"); bp2.evaluate("() => { island = 'harbor'; go('fishing'); }"); bp2.wait_for_timeout(300)
    bp2.click("#actBtn"); bp2.wait_for_timeout(700); bp2.evaluate("Object.values(sfx).forEach(f => f())")
    check("if the AudioContext can't be created (or throws) the game still works: no errors, CAST still casts", not perr and bp2.evaluate("F.phase") in ("waiting", "casting", "bite"), str(perr[:2]))
    bp2.close()
    # saves: an old save without S.music loads with music ON; a save with music false stays off
    op = b.new_page(viewport={"width": 1280, "height": 720})
    op.on("pageerror", lambda e: errs.append(str(e)))
    op.goto(URL); op.evaluate("localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Old', coins: 70, rods: ['bamboo'], rodEq: 'bamboo', bagMax: 5, bag: [], sound: false }))")
    op.reload(); op.wait_for_timeout(300)
    check("an old save without S.music loads with music ON (and keeps sound OFF); the Title shows MUSIC: ON", op.evaluate("S.music") is True and op.evaluate("S.sound") is False and "MUSIC: ON" in op.inner_text("#musicBtn") and op.is_enabled("#contBtn"))
    op.evaluate("localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Old', coins: 70, music: false }))"); op.reload(); op.wait_for_timeout(300)
    op.click("#contBtn"); op.wait_for_timeout(500)
    check("a save with music false stays silent after CONTINUE, then NEW GAME keeps both choices", op.evaluate("audioState().theme") is None and op.evaluate("S.music") is False)
    op.evaluate("() => go('titleScreen')"); op.click("#newBtn"); op.click("#confirmYes"); op.fill("#nameInput", "Fresh"); op.click("#nameStart"); op.wait_for_timeout(300)
    check("NEW GAME keeps the player's Music choice", op.evaluate("S.music") is False and op.evaluate("S.name") == "Fresh")
    op.close()
    # ---------- Playtest 1, part 14: ordinary buttons make a soft click; buttons with their own sound stay quiet ----------
    kp = b.new_page(viewport={"width": 1280, "height": 720})
    kp.on("pageerror", lambda e: errs.append(str(e))); kp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    kp.goto(URL); kp.evaluate("localStorage.clear()"); kp.reload(); kp.wait_for_timeout(300)
    kp.click("#howBtn"); kp.wait_for_timeout(500); kp.click("#howOk"); kp.wait_for_timeout(200)
    start_new(kp, "Clicker"); kp.wait_for_timeout(400)
    kp.evaluate("""() => { window.__k = { click: 0, tick: 0, coin: 0, voices: 0 };
        for (const n of ['click', 'tick', 'coin']) { const f = sfx[n]; sfx[n] = (...a) => { window.__k[n]++; return f(...a); }; }
        const tn = tone, nz = noise; tone = (...a) => { window.__k.voices++; return tn(...a); }; noise = (...a) => { window.__k.voices++; return nz(...a); };   // sfx voices only (the music has its own)
        S.coins = 5000; S.bagMax = 10; S.bag = ['harbor_0', 'harbor_3', 'frost_0'].map((id, i) => ({ fishId: id, weight: 1, price: 30 + i, time: i })); save(); render(); }""")
    def press(sel, wait=250):
        kp.evaluate("() => { window.__k.click = window.__k.tick = window.__k.coin = window.__k.voices = 0; }")
        kp.click(sel); kp.wait_for_timeout(wait)
        return kp.evaluate("window.__k")
    k = press("[data-go='map'].green"); check("pressing TOWN MAP calls sfx.click once and plays one sound", k["click"] == 1 and k["voices"] == 1, str(k))
    k = press("#mapHome"); check("pressing HOME (Town Map) calls sfx.click once", k["click"] == 1 and k["voices"] == 1, str(k))
    k = press("#home [data-go='shop']"); check("pressing SHOP calls sfx.click once", k["click"] == 1 and k["voices"] == 1, str(k))
    k = press("#navBack"); check("pressing BACK calls sfx.click once", k["click"] == 1 and k["voices"] == 1, str(k))
    k = press("#home [data-go='tackle']"); k2 = press("#navBack")
    check("pressing TACKLE BOX and BACK each call sfx.click once", k["click"] == 1 and k2["click"] == 1)
    kp.evaluate("() => { island = 'harbor'; go('fishing'); }"); kp.wait_for_timeout(300)
    k = press("#rodChip"); check("pressing the ROD chip calls sfx.click once", k["click"] == 1 and kp.is_visible("#pickBox"), str(k))
    k = press("#pickClose"); check("pressing a popup button (CLOSE) calls sfx.click once", k["click"] == 1, str(k))
    k = press("#actBtn", 100); check("pressing CAST does not call sfx.click (the whoosh is its sound)", k["click"] == 0 and k["tick"] == 0, str(k))
    kp.evaluate("() => { stopFishing(); go('home'); go('bag'); }"); kp.wait_for_timeout(300)
    k = press("#bagList .row:nth-child(1) .lockbtn"); check("pressing a lock does not call sfx.click; it plays its own tick (one sound)", k["click"] == 0 and k["tick"] == 1 and k["voices"] == 1, str(k))
    k = press("#bagList .row:nth-child(2) .btn"); check("a single SELL button does not call sfx.click (coin sound only)", k["click"] == 0 and k["coin"] == 1, str(k))
    k = press("#sellAll"); check("SELL ALL does not call sfx.click (coin sound only)", k["click"] == 0 and k["coin"] == 1, str(k))
    kp.evaluate("() => { go('home'); go('shop'); }"); kp.wait_for_timeout(300)
    k = press("#buyBag"); check("buying (Bigger bag) does not call sfx.click (coin sound only)", k["click"] == 0 and k["coin"] == 1, str(k))
    kp.evaluate("() => { S.coins = 5000; save(); go('home'); go('tackle'); }"); kp.wait_for_timeout(300)
    kp.evaluate("() => { S.rods = ['bamboo', 'sturdy']; save(); render(); }"); kp.wait_for_timeout(200)
    k = press("[data-equip='sturdy']"); check("EQUIP does not call sfx.click (its own tick only)", k["click"] == 0 and k["tick"] == 1 and k["voices"] == 1, str(k))
    dis = kp.evaluate("() => { go('shop'); render(); S.coins = 0; render(); return [...document.querySelectorAll('#shop [data-buy]')].filter(x => x.disabled).length; }"); kp.wait_for_timeout(300)
    kp.evaluate("() => { window.__k.click = window.__k.voices = 0; document.querySelector('#shop [data-buy][disabled]').dispatchEvent(new MouseEvent('click', { bubbles: true })); }")
    kd = kp.evaluate("window.__k")
    check("a disabled button makes no sound", dis > 0 and kd["click"] == 0 and kd["voices"] == 0, f"{dis} {kd}")
    kp.evaluate("() => go('titleScreen')"); kp.wait_for_timeout(300)
    k = press("#soundBtn"); check("the Title SOUND toggle does not call sfx.click (it has its own confirmation)", k["click"] == 0 and k["tick"] == 1, str(k))
    k = press("#soundBtn")
    k = press("#musicBtn"); check("the Title MUSIC toggle plays only its own tick (no click)", k["click"] == 0 and k["tick"] == 1 and k["voices"] == 1, str(k))
    kp.evaluate("() => { S.sound = false; saveSound(); audioApply(); renderTitle(); }")
    k = press("#howBtn"); kp.click("#howOk")
    osc_off = kp.evaluate("() => { let n = 0; const f = AC.createOscillator; AC.createOscillator = function (...a) { n++; return f.apply(this, a); }; sfx.click(); AC.createOscillator = f; return n; }")
    check("with SOUND off a menu press runs sfx.click but makes no sound (no oscillator is created, the effects bus is 0)", k["click"] == 1 and osc_off == 0 and kp.evaluate("audioState().sfx") == 0, f"{k} {osc_off}")
    kp.evaluate("() => { S.sound = true; saveSound(); audioApply(); renderTitle(); musicStop(.01); }"); kp.wait_for_timeout(400)
    osc_on = kp.evaluate("() => { let n = 0; const f = AC.createOscillator; AC.createOscillator = function (...a) { n++; return f.apply(this, a); }; sfx.click(); AC.createOscillator = f; return n; }")
    check("with SOUND on one press makes exactly one short sound (one oscillator)", osc_on == 1, str(osc_on))
    q2 = kp.evaluate("""() => { const o = {}; const t0 = AC.currentTime; let peak = 0; const an = AC.createAnalyser(); AUD.master.connect(an); return new Promise(res => { sfx.click(); const buf = new Float32Array(2048);
        const iv = setInterval(() => { an.getFloatTimeDomainData(buf); for (const v of buf) peak = Math.max(peak, Math.abs(v)); }, 5); setTimeout(() => { clearInterval(iv); res(peak); }, 300); }); }""")
    check("the click is soft: its peak is far below the other effects (below 0.12) yet audible (above 0.005)", .005 < q2 < .12, str(q2))
    kp.close()
    # ---------- Playtest 1, part 12b: floats are cosmetic gear you buy in the Shop and choose (Tackle Box, FLOAT chip); NOT linked to the bait ----------
    FL = {"classic": 0, "candy": 150, "frog": 250, "duck": 350, "golden": 600}
    bp = b.new_page(viewport={"width": 1536, "height": 730})
    bp.on("pageerror", lambda e: errs.append(str(e))); bp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    bp.goto(URL); bp.evaluate("localStorage.clear()"); bp.reload(); bp.wait_for_timeout(300); start_new(bp, "Floater")
    d = bp.evaluate("() => ({ f: Object.fromEntries(FLOAT_IDS.map(id => [id, FLOATS[id].price])), own: S.floatsOwned, eq: S.floatEq, names: FLOAT_IDS.map(id => FLOATS[id].name) })")
    check("the five floats exist with the listed prices (classic free, candy 150, frog 250, duck 350, golden 600); classic is owned and equipped from the start",
          d["f"] == FL and d["own"] == ["classic"] and d["eq"] == "classic", str(d))
    # saves: old saves without the fields, garbage
    bp.evaluate("""() => localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Old', coins: 80, rods: ['bamboo'], rodEq: 'bamboo', bagMax: 5, bag: [] }))"""); bp.reload(); bp.wait_for_timeout(300)
    bp.click("#contBtn"); bp.wait_for_timeout(300)
    check("an old save without floatsOwned / floatEq loads with the classic float owned and equipped (CONTINUE works)", bp.evaluate("[S.floatsOwned, S.floatEq, S.coins]") == [["classic"], "classic", 80])
    bp.evaluate("""() => localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Odd', coins: 80, floatsOwned: ['nonsense', 'duck', 7], floatEq: 'frog' }))"""); bp.reload(); bp.wait_for_timeout(300)
    check("odd float data is cleaned: unknown ids dropped, classic always owned, an unowned equipped float falls back to classic",
          bp.evaluate("[S.floatsOwned.slice().sort(), S.floatEq]") == [["classic", "duck"], "classic"])
    bp.evaluate("""() => localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Odd', coins: 80, floatsOwned: ['golden'], floatEq: 'golden' }))"""); bp.reload(); bp.wait_for_timeout(300)
    check("a saved float choice survives a reload", bp.evaluate("[S.floatsOwned.slice().sort(), S.floatEq]") == [["classic", "golden"], "golden"])
    bp.evaluate("localStorage.clear()"); bp.reload(); bp.wait_for_timeout(300); start_new(bp, "Floater")
    # Shop: Floats section after Bait, with previews, descriptions, prices and states
    bp.evaluate("() => { S.coins = 200; S.bagMax = 20; save(); go('shop'); }"); bp.wait_for_timeout(400)
    sh = bp.evaluate("""() => { const h = [...document.querySelectorAll('#shop .shop-h')].map(x => x.firstChild.textContent.trim()), items = [...document.querySelectorAll('#shopFloats .item')];
        return { heads: h, n: items.length, icons: items.every(i => i.querySelector('.ico.fl') && i.querySelector('.ico.fl').getBoundingClientRect().height >= 24 && i.querySelector('.ico.fl').getBoundingClientRect().height <= 32),
                 names: items.map(i => i.querySelector('b').textContent.trim()), btns: items.map(i => i.querySelector('button').textContent.trim()), dis: items.map(i => i.querySelector('button').disabled),
                 need: items.map(i => (i.querySelector('.need') || {}).textContent || ''), desc: items.every(i => i.querySelector('.fx').textContent.length > 12) }; }""")
    check("Shop: a Floats section after Bait lists the five floats with a 24-32px preview, name and description; classic is EQUIPPED, the others show their price",
          sh["heads"][:6] == ["Rods", "Bait", "Floats", "Tank Themes", "Tank Decorations", "Bag"] and sh["n"] == 5 and sh["icons"] and sh["desc"] and sh["btns"] == ["EQUIPPED", "150 COINS", "250 COINS", "350 COINS", "600 COINS"], str(sh))
    check("Shop: floats you can't afford are disabled and say 'Need N more coins'; the affordable one is enabled", sh["dis"] == [True, False, True, True, True] and sh["need"][2] == "Need 50 more coins" and sh["need"][4] == "Need 400 more coins", str(sh["need"]))
    bp.click("#shopFloats [data-buy='float:candy']"); bp.wait_for_timeout(200)
    check("buying with enough coins deducts the price, owns the float, equips it and toasts 'Bought: Candy Float'",
          bp.evaluate("[S.coins, S.floatsOwned, S.floatEq]") == [50, ["classic", "candy"], "candy"] and "Bought: Candy Float" in bp.inner_text("#toast"), str(bp.evaluate("[S.coins, S.floatsOwned, S.floatEq]")))
    bp.evaluate("() => { buyFloat('frog'); }"); bp.wait_for_timeout(150)
    check("buying without enough coins fails: 'Not enough coins.', nothing owned, coins unchanged", bp.evaluate("[S.coins, S.floatsOwned.includes('frog'), S.floatEq]") == [50, False, "candy"] and "Not enough coins" in bp.inner_text("#toast"))
    st = bp.evaluate("[...document.querySelectorAll('#shopFloats .item button')].map(b => b.textContent.trim())")
    check("Shop states after buying: Classic OWNED, Candy EQUIPPED, the rest priced", st == ["OWNED", "EQUIPPED", "250 COINS", "350 COINS", "600 COINS"], str(st))
    # Tackle Box: a Float row per float, equip with one tap
    bp.evaluate("() => { S.coins = 5000; S.floatsOwned = ['classic', 'candy', 'duck']; S.floatEq = 'candy'; save(); go('tackle'); }"); bp.wait_for_timeout(400)
    tk = bp.evaluate("""() => { const rows = [...document.querySelectorAll('#gearList .gear-row')].filter(r => r.querySelector('.ico.fl'));
        return { n: rows.length, icons: rows.every(r => r.querySelector('.ico.fl').getBoundingClientRect().height > 20), text: rows.map(r => r.innerText.replace(/\\s+/g, ' ')), head: [...document.querySelectorAll('#gearList h3')].map(h => h.firstChild.textContent.trim()) }; }""")
    check("Tackle Box: a Float row for each float with a preview, after Bait; the equipped one says EQUIPPED, owned ones have EQUIP, unowned ones show the price and a shop shortcut",
          tk["n"] == 5 and tk["icons"] and tk["head"][:3] == ["Rod", "Bait", "Float"] and "EQUIPPED" in tk["text"][1] and "EQUIP" in tk["text"][0] and "SHOP · 250 COINS" in tk["text"][2] and "SHOP · 600 COINS" in tk["text"][4], str(tk["text"]))
    bp.click("#gearList [data-float='duck']"); bp.wait_for_timeout(200)
    check("equipping from the Tackle Box with one tap works and shows 'Equipped: Duck Float'", bp.evaluate("S.floatEq") == "duck" and "Equipped: Duck Float" in bp.inner_text("#toast"))
    bp.click("#gearList .gear-row:has(.ico.fl) >> nth=2 >> text=SHOP"); bp.wait_for_timeout(300)
    check("an unowned float's shop shortcut opens the Shop", bp.evaluate("current") == "shop")
    # fishing screen: FLOAT chip + popup
    bp.evaluate("() => { island = 'harbor'; go('fishing'); }"); bp.wait_for_timeout(500)
    chip = bp.inner_text("#floatChip")
    check("the fishing screen has a FLOAT chip with a preview and the short name next to ROD and BAIT", bp.is_visible("#floatChip") and "Duck" in chip and bp.evaluate("!!document.querySelector('#floatChip .ico.fl')"), chip)
    bp.click("#floatChip"); bp.wait_for_timeout(300)
    pk = bp.evaluate("""() => ({ title: document.getElementById('pickTitle').textContent, n: document.querySelectorAll('#pickList .pick-card').length, dis: [...document.querySelectorAll('#pickList .pick-card')].map(c => c.disabled),
        icons: [...document.querySelectorAll('#pickList .pick-card .ico.fl')].length, shop: !!document.getElementById('pickShop') && getComputedStyle(document.getElementById('pickShop')).display !== 'none' })""")
    check("the FLOAT chip opens Choose Float: five cards with previews, unowned ones disabled with a price, a GO TO SHOP shortcut", pk["title"] == "Choose Float" and pk["n"] == 5 and pk["dis"] == [False, False, True, False, True] and pk["icons"] == 5 and pk["shop"], str(pk))
    bp.click("#pick-classic"); bp.wait_for_timeout(250)
    check("choosing an owned float equips it with one tap, closes the popup and toasts 'Equipped: Classic Float'", bp.evaluate("S.floatEq") == "classic" and not bp.is_visible("#pickBox") and "Equipped: Classic Float" in bp.inner_text("#toast") and "Classic" in bp.inner_text("#floatChip"))
    bp.click("#floatChip"); bp.wait_for_timeout(200); bp.keyboard.press("Escape"); bp.wait_for_timeout(150)
    check("the Choose Float popup closes with Esc and the focus returns to the FLOAT chip", not bp.is_visible("#pickBox") and bp.evaluate("document.activeElement.id") == "floatChip")
    # the style key follows the float, never the bait
    bp.evaluate("() => { S.floatsOwned = ['classic', 'candy', 'frog', 'duck', 'golden']; S.baits = { worm: 20, shrimp: 20, golden: 20 }; save(); }")
    keys = {}
    for fid in FL:
        row = []
        for bait in ["none", "worm", "shrimp", "golden"]:
            bp.evaluate(f"() => {{ stopFishing(); S.floatEq = '{fid}'; S.baitSel = '{bait}'; save(); go('home'); go('fishing'); }}"); bp.wait_for_timeout(250)
            bp.click("#actBtn"); bp.wait_for_function("F.phase === 'waiting'", timeout=4000); bp.wait_for_timeout(150)
            row.append(bp.evaluate("[bobberStyleKey(), F.floatId, F.usedBait]"))
        keys[fid] = row
    check("the style key (bobberStyleKey) is the equipped float, and it does NOT change with the bait (none, worm, shrimp, golden)",
          all([r[0] for r in rows] == [fid] * 4 and [r[1] for r in rows] == [fid] * 4 for fid, rows in keys.items()) and [r[2] for r in keys["candy"]] == [None, "worm", "shrimp", "golden"], str(keys["candy"]))
    px = bp.evaluate("""() => { const ids = ['classic', 'candy', 'frog', 'duck', 'golden'], snap = (id, t, still) => { const c = document.createElement('canvas'); c.width = 60; c.height = 70; const g = c.getContext('2d');
          drawFloat(g, 30, 44, id, t, still); return Array.from(g.getImageData(0, 0, 60, 70).data).join(','); };
        const diff = (a, b) => { a = a.split(','); b = b.split(','); let n = 0; for (let i = 0; i < a.length; i += 4) if (a[i] !== b[i] || a[i + 1] !== b[i + 1] || a[i + 2] !== b[i + 2] || a[i + 3] !== b[i + 3]) n++; return n; };
        const s = Object.fromEntries(ids.map(id => [id, snap(id, 0, true)])), d = {}; for (let i = 0; i < 5; i++) for (let j = i + 1; j < 5; j++) d[ids[i] + '/' + ids[j]] = diff(s[ids[i]], s[ids[j]]);
        const ext = (id, t = 0, st = true) => { const c = document.createElement('canvas'); c.width = 60; c.height = 70; const g = c.getContext('2d'); drawFloat(g, 30, 44, id, t, st); const a = g.getImageData(0, 0, 60, 70).data; let x0 = 99, x1 = -1, y0 = 99, y1 = -1;
          for (let y = 0; y < 70; y++) for (let x = 0; x < 60; x++) if (a[(y * 60 + x) * 4 + 3]) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); } return [x1 - x0 + 1, y1 - y0 + 1, y0]; };
        return { d, g0: diff(snap('golden', 0, false), snap('golden', 500, false)), gStill: diff(snap('golden', 0, true), snap('golden', 500, true)), g0still: diff(snap('golden', 0, false), snap('golden', 0, true)),
                 others: ['classic', 'candy', 'frog', 'duck'].map(id => diff(snap(id, 0, false), snap(id, 500, false))), ext: ids.map(id => ext(id)), extSp: [ext('golden', 0, false), ext('golden', 500, false)] }; }""")
    check("the five float styles draw clearly different pixels (every pair differs in at least 10 pixels)", len(px["d"]) == 10 and min(px["d"].values()) >= 10, str(px["d"]))
    check("golden: the 2-frame sparkle alternates every 500 ms; with prefers-reduced-motion there is no sparkle and no change; the other floats never animate",
          px["g0"] > 0 and px["gStill"] == 0 and px["g0still"] > 0 and px["others"] == [0, 0, 0, 0], str(px))
    check("every float is no bigger than the original classic float (12 x 19 px), also with the golden sparkle, and the line ties on 14px above the anchor",
          all(e[0] <= 12 and e[1] <= 19 for e in px["ext"] + px["extSp"]) and all(e[0] >= 9 and e[1] >= 17 for e in px["ext"]), str(px["ext"]) + str(px["extSp"]))
    # ---------- Playtest 1, part 12d: the frog float is cuter (eyes, blink, bigger preview) ----------
    fr = bp.evaluate("""() => { const W = 60, H = 70, cvs = (id, t, st) => { const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d'); drawFloat(g, 30, 44, id, t, st); return g.getImageData(0, 0, W, H).data; };
        const diff = (a, b) => { let n = 0; for (let i = 0; i < a.length; i += 4) if (a[i] !== b[i] || a[i + 1] !== b[i + 1] || a[i + 2] !== b[i + 2] || a[i + 3] !== b[i + 3]) n++; return n; };
        const box = a => { let x0 = 99, x1 = -1, y0 = 99, y1 = -1; for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (a[(y * W + x) * 4 + 3]) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); } return [x1 - x0 + 1, y1 - y0 + 1, x0, y0]; };
        const open = cvs('frog', 0, false), shut = cvs('frog', 2900, false), still = cvs('frog', 2900, true), openStill = cvs('frog', 0, true), later = cvs('frog', 3000 + 100, false), cl = cvs('classic', 0, true);
        const others = ['classic', 'candy', 'duck', 'golden'].map(id => diff(openStill, cvs(id, 0, true)));
        return { box: [box(open), box(shut), box(cl)], blink: diff(open, shut), still: diff(openStill, still), openAgain: diff(open, later), openEq: diff(open, openStill), shutMs: [2879, 2880, 2999, 3000].map(t => diff(cvs('frog', t, false), open)), others }; }""")
    check("frog: the open and the blinking frog fit the classic float's box (12 x 19) at the same position (same top, same anchor)",
          all(b[0] <= 12 and b[1] <= 19 for b in fr["box"]) and fr["box"][0] == fr["box"][1] == fr["box"][2], str(fr["box"]))
    check("frog: differs from classic, candy, duck and golden in at least 10 pixels each", len(fr["others"]) == 4 and min(fr["others"]) >= 10, str(fr["others"]))
    check("frog: blinks every 3 s for about 120 ms (open until 2879 ms, closed 2880-2999, open again at 3000); the closed frame differs from the open one; static open eyes with reduced motion",
          fr["blink"] > 0 and fr["openAgain"] == 0 and fr["still"] == 0 and fr["openEq"] == 0 and fr["shutMs"] == [0, fr["blink"], fr["blink"], 0], str(fr))
    cl = bp.evaluate("""() => { const W = 60, H = 70, c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d'); drawFloat(g, 30, 44, 'frog', 0, true); const a = g.getImageData(0, 0, W, H).data;
        const y0 = 44 - FLOAT_TOP, cnt = (ya, yb) => { let gr = 0, br = 0, n = 0; for (let y = y0 + ya; y <= y0 + yb; y++) for (let x = 0; x < W; x++) { const i = (y * W + x) * 4; if (!a[i + 3]) continue; const r = a[i], gg = a[i + 1], b = a[i + 2]; if (gg > 110 && gg > r + 30 && gg > b + 30) gr++; if (r > gg + 20 && gg > b + 10) br++; n++; } return { gr, br, n }; };
        const rowW = y => { let x0 = 99, x1 = -1; for (let x = 0; x < W; x++) if (a[((y0 + y) * W + x) * 4 + 3]) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); } return x1 - x0 + 1; };
        return { head: cnt(1, 8), body: cnt(10, 17), headW: rowW(5), bodyW: rowW(12) }; }""")
    check("frog (part 12f): the head is mostly green, the float body below it is mostly brown, and the head is at least 2px wider than the body on each side",
          cl["head"]["gr"] > cl["head"]["n"] * .5 and cl["head"]["br"] == 0 and cl["body"]["br"] > cl["body"]["n"] * .5 and cl["body"]["gr"] == 0 and cl["headW"] - cl["bodyW"] >= 4, str(cl))
    pp = b.new_page(viewport={"width": 1536, "height": 730})
    pp.on("pageerror", lambda e: errs.append(str(e))); pp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pp.goto(URL); pp.evaluate("localStorage.clear()"); pp.reload(); pp.wait_for_timeout(300); start_new(pp, "Froggy")
    pp.add_style_tag(content="#toast { display: none !important; }")
    pp.evaluate("() => { S.coins = 5000; S.floatsOwned = ['classic', 'candy', 'frog', 'duck', 'golden']; save(); }")
    SZ = "(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })"
    pp.evaluate("go('shop')"); pp.wait_for_timeout(300)
    pv = {"shop": pp.evaluate(f"{SZ}(document.querySelector('#shopFloats .item:nth-child(3) .ico.fl'))"), "shopOther": pp.evaluate(f"{SZ}(document.querySelector('#shopFloats .item:nth-child(2) .ico.fl'))")}
    pp.locator("#shopFloats").scroll_into_view_if_needed(); pp.wait_for_timeout(200)
    pp.locator("#shopFloats").screenshot(path=str(SHOTS / "105_frog_shop_cards_1536x730.png"))
    pp.evaluate("go('tackle')"); pp.wait_for_timeout(300)
    pv["tackle"] = pp.evaluate(f"{SZ}([...document.querySelectorAll('#gearList .gear-row')].filter(r => r.querySelector('.ico.fl'))[2].querySelector('.ico.fl'))")
    pp.evaluate("() => { S.floatEq = 'frog'; save(); island = 'harbor'; go('fishing'); }"); pp.wait_for_timeout(300); pp.click("#floatChip"); pp.wait_for_timeout(300)
    pv["pick"] = pp.evaluate(f"{SZ}(document.querySelector('#pickList .pick-card:nth-child(3) .ico.fl'))")
    DESC = "A little frog riding a floating log."
    d12g = {"popup": DESC in pp.inner_text("#pickList"), "chip": DESC in (pp.get_attribute("#floatChip", "title") or ""), "data": pp.evaluate("FLOATS.frog.blurb") == DESC}
    pp.evaluate("closeModal('pickBox'); go('shop')"); pp.wait_for_timeout(250); d12g["shop"] = DESC in pp.inner_text("#shopFloats")
    pp.evaluate("go('tackle')"); pp.wait_for_timeout(250); d12g["tackle"] = DESC in pp.inner_text("#gearList")
    d12g["old"] = "two tiny eyes" not in pp.evaluate("document.body.innerHTML")
    check("frog description (part 12g) is 'A little frog riding a floating log.' in the data, the Shop card, the Tackle Box row, the Choose Float popup and the chip tooltip", all(d12g.values()), str(d12g))
    ic = pp.evaluate("""async () => { const px = url => new Promise(res => { const im = new Image(); im.onload = () => { const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; const g = c.getContext('2d'); g.drawImage(im, 0, 0); res([im.width, im.height, g.getImageData(0, 0, im.width, im.height).data]); }; im.src = url; });
        const f = await px(floatIconUrl('frog')); let gr = 0, br = 0, pk = 0; for (let i = 0; i < f[2].length; i += 4) { if (!f[2][i + 3]) continue; const r = f[2][i], g = f[2][i + 1], b = f[2][i + 2]; if (g > 110 && g > r + 30 && g > b + 30) gr++; if (r > g + 20 && g > b + 10 && r < 240) br++; if (r > 240 && g > 140 && g < 180) pk++; }
        const same = {}; for (const id of ['classic', 'candy', 'duck', 'golden']) { const c = document.createElement('canvas'); c.width = 12; c.height = 19; const g = c.getContext('2d'); FLOAT_MAPS[id].forEach((row, y) => { for (let x = 0; x < 12; x++) if (row[x] !== '.') { g.fillStyle = FLOAT_LOOK[id][row[x]]; g.fillRect(x, y, 1, 1); } }); same[id] = c.toDataURL() === floatIconUrl(id); }
        return { size: [f[0], f[1]], gr, br, pk, same }; }""")
    check("frog preview icon (part 12g) is 16 x 16 art pixels with both green and brown (and pink cheek) pixels; the other four previews are still their on-water sprites",
          ic["size"] == [16, 16] and ic["gr"] >= 30 and ic["br"] >= 20 and ic["pk"] >= 2 and all(ic["same"].values()) and len(ic["same"]) == 4, str(ic))
    pp.close()
    check("frog preview icon is bigger than before (at least 28 x 28 px) in the Shop, the Tackle Box and the Choose Float popup; the other floats' previews keep their size",
          all(pv[k][0] >= 28 and pv[k][1] >= 28 for k in ["shop", "tackle", "pick"]) and pv["shopOther"] == [24, 32], str(pv))
    # close-up screenshot: the frog open and blinking (enlarged 8x, on water colour)
    bp.evaluate("""() => { const c = document.createElement('canvas'); c.id = 'frogShot'; c.width = 48; c.height = 24; const g = c.getContext('2d'); g.fillStyle = '#2f8fc8'; g.fillRect(0, 0, 48, 24);
        drawFloat(g, 12, 16, 'frog', 0, false); drawFloat(g, 36, 16, 'frog', 2900, false); c.style.cssText = 'position:fixed;left:20px;top:20px;width:384px;height:192px;image-rendering:pixelated;z-index:9999'; document.body.appendChild(c); }""")
    bp.screenshot(path=str(SHOTS / "105_frog_open_blink_1536x730.png"), clip={"x": 20, "y": 20, "width": 384, "height": 192}); bp.evaluate("document.getElementById('frogShot').remove()")
    # a float can't change mid-cast: chip disabled, popup refuses, equipFloat refuses; the cast keeps its float
    bp.evaluate("() => { stopFishing(); S.floatEq = 'candy'; S.baitSel = 'none'; save(); go('home'); go('fishing'); }"); bp.wait_for_timeout(300)
    seen = {}
    def probe(ph):
        seen[ph] = bp.evaluate("""() => { const before = S.floatEq; openPicker('float'); const open = document.getElementById('pickBox').classList.contains('show'); equipFloat('duck');
            const r = [document.getElementById('floatChip').disabled, open, S.floatEq === before, bobberStyleKey(), F.floatId]; return r; }""")
    bp.click("#actBtn"); bp.wait_for_timeout(60); probe("casting")
    bp.wait_for_function("F.phase === 'waiting'", timeout=4000); bp.wait_for_timeout(200); probe("waiting")
    bp.evaluate("() => { S.floatEq = 'frog'; }"); bp.wait_for_timeout(200)       # even a forced change mid-cast does not change the float being drawn
    bp.wait_for_function("F.phase === 'bite'", timeout=9000); bp.wait_for_timeout(100); probe("bite")
    bp.click("#actBtn"); bp.wait_for_timeout(250); probe("reeling")
    check("while casting, waiting, on the bite and while reeling: the FLOAT chip is disabled, the popup won't open, equipFloat changes nothing",
          all(v[0] is True and v[1] is False and v[2] is True for ph, v in seen.items() if ph != "bite") and seen["bite"][0] is True and seen["bite"][1] is False, str(seen))
    check("a cast keeps the float that was equipped when it started (candy) in every phase, even if the saved choice changes mid-cast",
          all(v[3] == "candy" and v[4] == "candy" for v in seen.values()), str(seen))
    bp.evaluate("() => { stopFishing(); S.floatEq = 'duck'; go('home'); go('fishing'); }"); bp.wait_for_timeout(300)
    bp.click("#actBtn"); bp.wait_for_function("F.phase === 'waiting'", timeout=4000); bp.wait_for_timeout(200)
    check("the next cast uses the newly equipped float (duck)", bp.evaluate("bobberStyleKey()") == "duck")
    # line start, tie-on point and dip are unchanged (identical for every float; the formulas are the old ones)
    pos = bp.evaluate("""() => { stopFishing(); island = 'harbor'; go('fishing'); const out = {}, T = 4321.5, H = cv.height, W = cv.width, L = { x: .6, y: .65 };
        const rec = []; const names = ['moveTo', 'quadraticCurveTo', 'ellipse', 'stroke']; const orig = names.map(k => ctx[k]);
        names.forEach(k => { const f = ctx[k]; ctx[k] = function (...a) { rec.push(k + ':' + a.map(v => typeof v === 'number' ? +v.toFixed(3) : v).join(',')); return f.apply(this, a); }; });
        for (const id of ['classic', 'candy', 'frog', 'duck', 'golden']) for (const phase of ['waiting', 'bite', 'reeling']) {
          rec.length = 0; F = { phase, castAt: T - 3000, land: L, fish: fishById('harbor_0'), usedBait: null, floatId: id }; drawScene(T);
          out[id + '/' + phase] = { bp: [F.bobPos.x, F.bobPos.y], calls: rec.join('|'), n: rec.length, key: bobberStyleKey(), move: rec.find(c => c.startsWith('moveTo')), quad: rec.find(c => c.startsWith('quadraticCurveTo')) }; }
        names.forEach((k, i) => { ctx[k] = orig[i]; });
        const dy = { waiting: Math.sin(T / 300) * 3, bite: 8 + Math.sin(T / 40) * 5, reeling: Math.sin(T / 60) * 6 };
        return { out, exp: Object.fromEntries(Object.entries(dy).map(([ph, v]) => [ph, [L.x, (H * L.y + v) / H]])), tip: [TIP.x * W, TIP.y * H], W, H, top: FLOAT_TOP }; }""")
    ids5 = list(FL)
    exact = all(abs(pos["out"][f"{i}/{ph}"]["bp"][0] - pos["exp"][ph][0]) < 1e-9 and abs(pos["out"][f"{i}/{ph}"]["bp"][1] - pos["exp"][ph][1]) < 1e-9 for i in ids5 for ph in ["waiting", "bite", "reeling"])
    same = all(pos["out"][f"{i}/{ph}"]["calls"] == pos["out"][f"classic/{ph}"]["calls"] and pos["out"][f"{i}/{ph}"]["n"] >= 3 and pos["out"][f"{i}/{ph}"]["key"] == i for i in ids5 for ph in ["waiting", "bite", "reeling"])
    mv = pos["out"]["golden/reeling"]["move"].split(":")[1].split(",")      # the last scene drawn: its rod tip is TIP now
    qd = pos["out"]["classic/waiting"]["quad"].split(":")[1].split(",")
    bx = pos["exp"]["waiting"][0] * pos["W"]; by = pos["exp"]["waiting"][1] * pos["H"]
    check("the bobber's anchor and the dip on a bite / reel are exactly as before for all five floats (same formulas, same position)", exact)
    check("the line starts at the rod tip and is drawn identically for every float; it ties on at the top of the float (14px above the anchor)",
          same and abs(float(mv[0]) - pos["tip"][0]) < .01 and abs(float(mv[1]) - pos["tip"][1]) < .01 and abs(float(qd[2]) - bx) < .01 and abs(float(qd[3]) - (by - pos["top"])) < .01 and pos["top"] == 14, f"{mv} {qd} {bx} {by}")
    # ---------- Playtest 1, part 13: HOME button on the fishing screen ----------
    HOME_GEO = """() => { const r = id => { const e = document.getElementById(id), b = e.getBoundingClientRect(); return { l: b.left, r: b.right, t: b.top, w: b.width, h: b.height, vis: b.width > 0 && getComputedStyle(e).visibility !== 'hidden', dis: e.disabled }; };
          const top = document.querySelector('.app > .top'), t = document.getElementById('title'), lbl = document.querySelector('#homeTop .lbl'), ic = document.querySelector('#homeTop .ico').getBoundingClientRect();
          return { home: r('homeTop'), sell: r('sellTop'), title: r('title'), tops: [...top.children].filter(c => c.getBoundingClientRect().width > 0).map(c => Math.round(c.getBoundingClientRect().top)),
                   overflow: top.scrollWidth > top.clientWidth + 1, titleClip: t.scrollWidth > t.clientWidth + 1, pageScroll: document.documentElement.scrollWidth > innerWidth, lbl: !!lbl && getComputedStyle(lbl).display !== 'none', icon: ic.width, label: document.getElementById('homeTop').getAttribute('aria-label') }; }"""
    SAVE_SNAP = "JSON.stringify({ c: S.coins, b: S.bag.length, r: S.rods, f: S.floatsOwned, e: S.floatEq, rod: S.rodEq })"
    for hw, hh in [(1536, 730), (390, 844), (360, 640)]:
        hp = b.new_page(viewport={"width": hw, "height": hh})
        hp.on("pageerror", lambda e: errs.append(str(e))); hp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        hp.goto(URL); hp.evaluate("localStorage.clear()"); hp.reload(); hp.wait_for_timeout(300); start_new(hp, "Homer")
        hp.add_style_tag(content="#toast { display: none !important; }")
        hp.evaluate("() => { S.coins = 999999; S.bagMax = 20; S.floatsOwned = ['classic', 'frog']; S.floatEq = 'frog'; S.rods = ['bamboo', 'sturdy']; save(); }")
        for isl in ["harbor", "frost", "desert", "forest"]:
            hp.evaluate(f"() => {{ stopFishing(); island = '{isl}'; go('home'); go('fishing'); }}"); hp.wait_for_timeout(350)
            g = hp.evaluate(HOME_GEO)
            ok = (g["home"]["vis"] and not g["home"]["dis"] and g["home"]["r"] <= g["sell"]["l"] + .5 and g["home"]["l"] >= g["title"]["r"] - .5 and abs(g["home"]["h"] - g["sell"]["h"]) < 1.5
                  and abs(g["home"]["t"] - g["sell"]["t"]) < 1.5 and g["home"]["w"] >= 40 and g["home"]["h"] >= 40 and len(set(g["tops"])) == 1 and not g["overflow"] and not g["titleClip"] and not g["pageScroll"]
                  and g["label"] == "Home" and (g["lbl"] if hw > 700 else not g["lbl"]))
            check(f"{hw}x{hh} {isl}: HOME is visible and enabled when idle, between the title and SELL, as tall as SELL (at least 40x40), top bar on one line without overflow or a clipped title; {'icon + HOME' if hw > 700 else 'icon only'}", ok, str(g))
        if hw in (1536, 360):
            hp.evaluate("() => { stopFishing(); island = 'harbor'; go('home'); go('fishing'); }"); hp.wait_for_timeout(300)
            hp.screenshot(path=str(SHOTS / f"106_home_fishing_{hw}x{hh}.png"))
            hp.screenshot(path=str(SHOTS / f"106_home_topbar_{hw}x{hh}.png"), clip={"x": 0, "y": 0, "width": hw, "height": 110})
        if hw == 1536:
            snap = hp.evaluate(SAVE_SNAP)
            dis = {}
            for ph in ["casting", "waiting", "bite", "reeling", "caught"]:
                dis[ph] = hp.evaluate(f"() => {{ stopFishing(); go('fishing'); F.phase = '{ph}'; renderFishingHud(); const b = document.getElementById('homeTop'); b.click(); return [b.disabled, current]; }}")
            check("HOME is disabled during cast, wait, bite, reel and catch, and clicking it does nothing (stays on the fishing screen)", all(v == [True, "fishing"] for v in dis.values()), str(dis))
            hp.evaluate("() => { stopFishing(); go('home'); go('fishing'); }"); hp.wait_for_timeout(300)
            hp.click("#actBtn"); hp.wait_for_function("F.phase === 'waiting'", timeout=4000)
            real = [hp.evaluate("document.getElementById('homeTop').disabled")]
            hp.evaluate("document.getElementById('homeTop').click()"); real.append(hp.evaluate("[current, F.phase]"))
            hp.wait_for_function("F.phase === 'bite'", timeout=9000); real.append(hp.evaluate("document.getElementById('homeTop').disabled"))
            hp.click("#actBtn"); hp.wait_for_timeout(250); real.append(hp.evaluate("[document.getElementById('homeTop').disabled, F.phase]"))
            check("in a real cast HOME is disabled while waiting, on the bite and while reeling, and a click while waiting keeps the cast", real[0] is True and real[1] == ["fishing", "waiting"] and real[2] is True and real[3] == [True, "reeling"], str(real))
            hp.evaluate("() => { stopFishing(); go('fishing'); }"); hp.wait_for_timeout(300)
            check("HOME is enabled again once the fishing state is idle", hp.evaluate("document.getElementById('homeTop').disabled") is False)
            hp.evaluate("() => { go('shop'); go('fishing'); }"); hp.wait_for_timeout(250)
            navbefore = hp.evaluate("() => { window.__clicks = 0; const f = sfx.click; sfx.click = function (...a) { window.__clicks++; return f.apply(this, a); }; return navStack.length; }")
            hp.click("#homeTop"); hp.wait_for_timeout(350)
            after = hp.evaluate(SAVE_SNAP)
            hp.screenshot(path=str(SHOTS / "106_home_hub_1536x730.png"))
            st = hp.evaluate("() => ({ cur: current, title: document.getElementById('titleScreen').classList.contains('active'), hub: document.getElementById('home').classList.contains('active'), nav: navStack.length, clicks: window.__clicks, saved: JSON.parse(localStorage.getItem('littleLakeSave')).coins, cont: 1 })")
            check("HOME goes to the Home hub screen (like the Town Map HOME tab, not the Title screen), clears the history, keeps the save (coins, bag, rods, floats), and plays one soft click",
                  st["cur"] == "home" and st["hub"] and not st["title"] and st["nav"] == 0 and navbefore >= 1 and snap == after and st["saved"] == 999999 and st["clicks"] == 1, f"{st} {navbefore} {snap} {after}")
            # BACK on the hub behaves as after the Town Map HOME tab: back to the Title screen, never into the fishing screen; same history state
            hp.evaluate("() => { go('map'); }"); hp.wait_for_timeout(200); hp.click("#mapHome"); hp.wait_for_timeout(250)
            viamap = hp.evaluate("[current, navStack.length]")
            hp.evaluate("() => { go('fishing'); }"); hp.wait_for_timeout(250); hp.click("#homeTop"); hp.wait_for_timeout(250)
            viafish = hp.evaluate("[current, navStack.length]")
            hp.click("#navBack") if hp.is_visible("#navBack") else hp.keyboard.press("Escape"); hp.wait_for_timeout(250)
            check("after HOME the history is the same as after the Town Map HOME tab (home, empty), and BACK / Esc on the hub does not return to the fishing screen",
                  viamap == viafish == ["home", 0] and hp.evaluate("current") != "fishing", f"{viamap} {viafish} {hp.evaluate('current')}")
            for key in ["Enter", "Space"]:
                hp.evaluate("() => { go('home'); go('fishing'); }"); hp.wait_for_timeout(300)
                hp.focus("#homeTop"); hp.keyboard.press(key); hp.wait_for_timeout(250)
                check(f"HOME is focusable and {key} works (goes to the Home hub)", hp.evaluate("current") == "home")
            hp.evaluate("() => { go('home'); go('fishing'); }"); hp.wait_for_timeout(300)
            bt = hp.evaluate("[...document.querySelectorAll('#fishing .actions > *')].map(e => (e.id || e.textContent).trim())")
            check("the bottom three buttons are unchanged (CAST, SHOP, TOWN MAP)", len(bt) == 3, str(bt))
        hp.close()
    # ---------- Playtest 1, part 14: rivets never overlap icons or text ----------
    RIVET_JS = r"""() => {
  const out = [], seen = new Set();
  const all = document.querySelectorAll('body *');
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const bg = cs.backgroundImage;
    if (!bg || !bg.includes('rgb(244, 244, 244)')) continue;      // the rivet gradient
    const r = el.getBoundingClientRect(); if (r.width < 4 || r.height < 4) continue;
    const bl = parseFloat(cs.borderLeftWidth) || 0, bt = parseFloat(cs.borderTopWidth) || 0, br = parseFloat(cs.borderRightWidth) || 0, bb = parseFloat(cs.borderBottomWidth) || 0;
    const px0 = r.left + bl, py0 = r.top + bt, px1 = r.right - br, py1 = r.bottom - bb;   // padding box
    const riv = [];    // the visible circle: 14x14 box at 7px from the padding edges, radius 6
    for (const [cx, cy] of [[px0 + 14, py0 + 14], [px1 - 14, py0 + 14], [px0 + 14, py1 - 14], [px1 - 14, py1 - 14]]) riv.push([cx, cy]);
    const content = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_ALL);
    let n;
    while ((n = walker.nextNode())) {
      if (n.nodeType === 3) {
        if (!n.textContent.trim()) continue;
        const p = n.parentElement, pcs = getComputedStyle(p); if (pcs.display === 'none' || pcs.visibility === 'hidden') continue;
        const rg = document.createRange(); rg.selectNodeContents(n);
        for (const q of rg.getClientRects()) if (q.width > 0 && q.height > 0) content.push([q.left, q.top, q.right, q.bottom, 'text:' + n.textContent.trim().slice(0, 14)]);
      } else if (n.nodeType === 1) {
        const c = getComputedStyle(n); if (c.display === 'none' || c.visibility === 'hidden') continue;
        const isIcon = n.classList.contains('ico') || ['IMG', 'CANVAS', 'SVG'].includes(n.tagName.toUpperCase());
        if (isIcon) { const q = n.getBoundingClientRect(); if (q.width > 0 && q.height > 0) content.push([q.left, q.top, q.right, q.bottom, 'icon:' + (n.className.baseVal || n.className)]); }
      }
    }
    for (const [cx, cy] of riv) for (const c of content) {
      const nx = Math.max(c[0], Math.min(cx, c[2])), ny = Math.max(c[1], Math.min(cy, c[3]));
      if (Math.hypot(nx - cx, ny - cy) < 5) { const id = el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + String(el.className).split(/\s+/).filter(Boolean).join('.'); const key = id + '|' + c[4]; if (!seen.has(key)) { seen.add(key); out.push({ el: id, hit: c[4], box: [Math.round(r.width), Math.round(r.height)] }); } }
    }
  }
  return out;
}"""
    for rw, rh in [(1536, 730), (360, 640)]:
        rp = b.new_page(viewport={"width": rw, "height": rh})
        rp.on("pageerror", lambda e: errs.append(str(e))); rp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        rp.goto(URL); rp.evaluate("localStorage.clear()"); rp.reload(); rp.wait_for_timeout(300); start_new(rp, "Rivets")
        rp.add_style_tag(content="#toast { display: none !important; }")
        rp.evaluate("() => { S.coins = 999999; S.bagMax = 20; S.rods = ['bamboo','sturdy','precision','lucky']; S.floatsOwned = ['classic','candy','frog','duck','golden']; S.baits = {worm: 5, shrimp: 5, golden: 3}; S.baitSel = 'worm';"
                    " S.bag = [0,1,2].map(i => ({ fishId: 'harbor_' + i, w: 1.2, price: 20 + i, locked: i === 1 })); save(); }")
        hits = []
        def rv(name, js):
            rp.evaluate(js); rp.wait_for_timeout(350)
            for h in rp.evaluate(RIVET_JS): hits.append(f"{name}: {h['el']} {h['hit']}")
        rv("title", "go('titleScreen')"); rv("how", "document.getElementById('howBtn').click()"); rp.evaluate("document.getElementById('howOk').click()"); rp.wait_for_timeout(200); rv("hub", "go('home')"); rv("map", "go('map')")
        for isl in ["harbor", "frost", "desert", "forest"]: rv("fishing-" + isl, f"() => {{ stopFishing(); island = '{isl}'; go('fishing'); }}")
        for kind in ["float", "rod", "bait"]: rv("popup-" + kind, f"() => {{ closeModal('pickBox'); openPicker('{kind}'); }}")
        rp.evaluate("closeModal('pickBox')")
        rv("shop", "go('shop')"); rv("tackle", "go('tackle')"); rv("collection", "go('collection')"); rv("bag", "go('bag')")
        check(f"{rw}x{rh}: no rivet overlaps an icon or text inside its own element (title, how to play, hub, map, 4 islands, 3 popups, shop, tackle box, collection, bag)", not hits, "; ".join(hits[:8]))
        rp.evaluate("() => { stopFishing(); island = 'harbor'; go('fishing'); }"); rp.wait_for_timeout(400)
        rp.screenshot(path=str(SHOTS / f"107_rivets_fishing_topbar_{rw}x{rh}.png"), clip={"x": 0, "y": 0, "width": rw, "height": 120})
        rp.evaluate("go('home')"); rp.wait_for_timeout(400)
        rp.screenshot(path=str(SHOTS / f"107_rivets_hub_{rw}x{rh}.png"))
        if rw == 1536:
            big = rp.evaluate("""() => { go('home'); const n = el => getComputedStyle(el).backgroundImage.includes('rgb(244, 244, 244)'); return { panel: n(document.querySelector('#home .panel')), map: (go('map'), n(document.querySelector('.map-panel'))), tm: (go('home'), n(document.querySelector('#home .btn[data-go=\"map\"]'))), chip: n(document.getElementById('menuBtn')) }; }""")
            check("large panels and buttons keep their rivets on wide windows (hub panel, Town Map panel, big hub button) while the MENU button has none", big["panel"] and big["map"] and big["tm"] and not big["chip"], str(big))
        rp.close()
    # screenshots (the five floats on the water, full scene + close-up) at 1536x730 and 360x640
    bp.close()
    for vw, vh in [(1536, 730), (360, 640)]:
        sp = b.new_page(viewport={"width": vw, "height": vh})
        sp.on("pageerror", lambda e: errs.append(str(e))); sp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        sp.goto(URL); sp.evaluate("localStorage.clear()"); sp.reload(); sp.wait_for_timeout(300); start_new(sp, "Shots")
        sp.add_style_tag(content="#toast { display: none !important; }")
        sp.evaluate("() => { S.coins = 5000; S.floatsOwned = ['classic', 'candy', 'frog', 'duck', 'golden']; S.bagMax = 30; save(); }")
        for fid in FL:
            sp.evaluate(f"() => {{ stopFishing(); S.floatEq = '{fid}'; save(); island = 'harbor'; go('home'); go('fishing'); }}"); sp.wait_for_timeout(300)
            sp.click("#actBtn"); sp.wait_for_function("F.phase === 'waiting'", timeout=4000); sp.wait_for_timeout(900); sp.evaluate("clearTimers()")
            sp.screenshot(path=str(SHOTS / f"104_float_{fid}_{vw}x{vh}.png"))
            r = sp.evaluate("""() => { const c = document.getElementById('sceneCanvas').getBoundingClientRect(); return [c.left + F.bobPos.x * c.width, c.top + F.bobPos.y * c.height]; }""")
            sp.screenshot(path=str(SHOTS / f"104_float_{fid}_{vw}x{vh}_crop.png"), clip={"x": max(0, r[0] - 70), "y": max(0, r[1] - 60), "width": 140, "height": 100})
        sp.evaluate("() => { stopFishing(); S.floatEq = 'duck'; save(); island = 'harbor'; go('fishing'); }"); sp.wait_for_timeout(400)
        sp.locator("#fishing .gearbar").screenshot(path=str(SHOTS / f"104_float_chips_{vw}x{vh}.png"))
        sp.screenshot(path=str(SHOTS / f"104_float_fishing_{vw}x{vh}.png"))
        sp.evaluate("() => { go('home'); go('shop'); }"); sp.wait_for_timeout(300)
        sp.evaluate("() => document.getElementById('shopFloats').scrollIntoView({ block: 'center' })"); sp.wait_for_timeout(300)
        sp.screenshot(path=str(SHOTS / f"104_float_shop_{vw}x{vh}.png"))
        sp.evaluate("() => { go('home'); go('tackle'); }"); sp.wait_for_timeout(300)
        sp.evaluate("() => { const r = [...document.querySelectorAll('#gearList h3')].find(h => h.textContent.startsWith('Float')); r.scrollIntoView({ block: 'start' }); }"); sp.wait_for_timeout(300)
        sp.screenshot(path=str(SHOTS / f"104_float_tackle_{vw}x{vh}.png"))
        sp.close()
    # layout: the three chips fit on one row on phones; no overflow; CAST doesn't move; no page scroll on the Fishing screen at every size, nor on Shop / Tackle Box on wide windows
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600), (390, 844), (360, 640)]:
        tag = f"{vw}x{vh}"
        lp = b.new_page(viewport={"width": vw, "height": vh})
        lp.on("pageerror", lambda e: errs.append(str(e))); lp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        lp.goto(URL); lp.evaluate("localStorage.clear()"); lp.reload(); lp.wait_for_timeout(300); start_new(lp, "Fitter")
        lp.evaluate("() => { S.floatsOwned = ['classic', 'candy', 'frog', 'duck', 'golden']; S.floatEq = 'golden'; S.rods = ['bamboo', 'sturdy', 'precision', 'lucky']; S.rodEq = 'precision'; S.baits = { worm: 12, shrimp: 12, golden: 12 }; S.baitSel = 'golden'; S.mastery = { harbor: true, frost: true, desert: true, forest: true }; save(); island = 'harbor'; go('fishing'); }")
        lp.wait_for_timeout(500)
        GEO = """() => { const bar = document.querySelector('#fishing .gearbar').getBoundingClientRect(), ids = ['rodChip', 'baitChip', 'floatChip'], cs = ids.map(id => { const e = document.getElementById(id), r = e.getBoundingClientRect(); return { top: Math.round(r.top), h: Math.round(r.height), l: r.left, r: r.right, over: e.scrollWidth > e.clientWidth + 1, vis: r.width > 0 }; });
            const a = document.getElementById('actBtn').getBoundingClientRect(), bon = document.getElementById('bonuses').getBoundingClientRect();
            return { cs, barL: bar.left, barR: bar.right, barB: bar.bottom, act: Math.round(a.top * 10) / 10, sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, vw: innerWidth, vh: innerHeight, bonB: bon.bottom, bonR: bon.right }; }"""
        g0 = lp.evaluate(GEO)
        chips_ok = all(c["vis"] and c["h"] >= (40 if vw < 900 else 36) and c["l"] >= g0["barL"] - 1 and c["r"] <= g0["barR"] + 1 and not c["over"] for c in g0["cs"])      # not cut off even with Precision + Golden x12
        one_row = len({c["top"] for c in g0["cs"]}) == 1 and g0["cs"][0]["r"] <= g0["cs"][1]["l"] + 1 and g0["cs"][1]["r"] <= g0["cs"][2]["l"] + 1
        check(f"{tag}: the ROD, BAIT and FLOAT chips fit on one row inside the panel (no overflow, tap height at least {'40' if vw < 900 else '36'}px), 4 island rewards beside / below them, no side scroll",
              chips_ok and one_row and g0["sw"] <= g0["vw"] and g0["bonR"] <= g0["barR"] + 1, str(g0))
        check(f"{tag}: Fishing screen with the FLOAT chip: no page scroll", g0["sh"] <= g0["vh"], f"{g0['sh']} > {g0['vh']}")
        tops = [g0["act"]]
        lp.click("#actBtn"); lp.wait_for_timeout(80); tops.append(lp.evaluate(GEO)["act"])
        lp.wait_for_function("F.phase === 'waiting'", timeout=4000); tops.append(lp.evaluate(GEO)["act"])
        lp.wait_for_function("F.phase === 'bite'", timeout=9000); tops.append(lp.evaluate(GEO)["act"])
        lp.click("#actBtn"); lp.wait_for_timeout(100); g4 = lp.evaluate(GEO); tops.append(g4["act"])
        check(f"{tag}: CAST / HOOK / REEL doesn't move between phases and the chips stay in place while busy (floats disabled)", max(tops) - min(tops) <= 1 and [c["top"] for c in g4["cs"]] == [c["top"] for c in g0["cs"]], str(tops))
        for scr in ["shop", "tackle"]:
            lp.evaluate(f"() => {{ stopFishing(); go('home'); go('{scr}'); }}"); lp.wait_for_timeout(350)
            m = lp.evaluate("() => ({ sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, vw: innerWidth, vh: innerHeight })")
            if vw >= 900: check(f"{tag}: {scr.title()} with the floats: no page scroll", m["sh"] <= m["vh"] and m["sw"] <= m["vw"], str(m))
            else: check(f"{tag}: {scr.title()} with the floats: no side scroll (phones scroll the page, as before)", m["sw"] <= m["vw"], str(m))
        lp.close()
    # 6 hearts (Lucky + Master's Charm) fit on a 360x640 phone; CAST/HOOK/REEL doesn't move between phases
    hp6 = b.new_page(viewport={"width": 360, "height": 640}); hp6.on("pageerror", lambda e: errs.append(str(e)))
    hp6.goto(URL); hp6.evaluate("localStorage.clear()"); hp6.reload(); hp6.wait_for_timeout(200); start_new(hp6, "Six")
    hp6.add_style_tag(content="#toast { display: none !important; }")
    hp6.evaluate("() => { S.rods = [...ROD_IDS]; S.rodEq = 'lucky'; S.mastery = { forest: true }; save(); island = 'harbor'; go('fishing'); }"); hp6.wait_for_timeout(500)
    tops = [hp6.evaluate(ACT_POS)["top"]]
    hp6.click("#actBtn"); hp6.wait_for_function("F.phase === 'waiting'"); tops.append(hp6.evaluate(ACT_POS)["top"])
    hp6.wait_for_function("F.phase === 'bite'", timeout=8000); tops.append(hp6.evaluate(ACT_POS)["top"])
    hp6.click("#actBtn"); hp6.wait_for_timeout(120); tops.append(hp6.evaluate(ACT_POS)["top"])
    six = hp6.evaluate("""() => { const h = document.getElementById('hearts'), ri = document.querySelector('.reelinfo').getBoundingClientRect(), icons = [...h.querySelectorAll('.ico')];
        return [icons.length, icons.every(i => { const r = i.getBoundingClientRect(); return r.left >= ri.left - .5 && r.right <= ri.right + .5 && r.top >= ri.top - .5 && r.bottom <= ri.bottom + .5; }),
                new Set(icons.map(i => Math.round(i.getBoundingClientRect().top))).size, h.scrollWidth <= h.clientWidth + 1, document.documentElement.scrollWidth <= 360,
                document.documentElement.scrollHeight <= innerHeight, document.getElementById('dots').getBoundingClientRect().height <= 24]; }""")
    hp6.screenshot(path=str(SHOTS / "95_six_hearts_360x640.png"))
    hp6.click("#actBtn"); hp6.wait_for_timeout(80); tops.append(hp6.evaluate(ACT_POS)["top"])
    check("360x640: 6 hearts (Lucky Rod + Master's Charm) fit on one line inside the reel row beside a one-line HIT counter, no overflow, no side or page scroll",
          six == [6, True, 1, True, True, True, True], str(six))
    check("360x640 with 6 hearts: CAST/HOOK/REEL stays put in every phase (<= 1px)", max(tops) - min(tops) <= 1, str([round(t, 1) for t in tops]))
    hp6.evaluate("() => stopFishing()"); hp6.close()
    # save compatibility: a save that equips Precision or Lucky just gets the new miss counts
    cp6 = b.new_page(viewport={"width": 1280, "height": 720}); cp6.goto(URL)
    cp6.evaluate("localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Old', coins: 10, rods: ['bamboo', 'precision', 'lucky'], rodEq: 'precision', bag: [] }))"); cp6.reload(); cp6.wait_for_timeout(200)
    a1 = cp6.evaluate("allowedMiss()"); cp6.evaluate("() => { S.rodEq = 'lucky'; }"); a2 = cp6.evaluate("allowedMiss()")
    check("an existing save with Precision / Lucky equipped loads unchanged and gets 3 / 5 misses", a1 == 3 and a2 == 5 and cp6.evaluate(SAVED + ".rodEq") == "precision", f"{a1} {a2}")
    cp6.close()

    # ---------- BUG-32 / BUG-33 (Playtest 1): SHOP on the fishing screen; SELL moved next to the coins in the top bar ----------
    SELLTOP = """() => { const s = document.getElementById('sellTop'), g = document.querySelector('.app > .top > .sign'), t = document.getElementById('title'),
            rs = s.getBoundingClientRect(), rg = g.getBoundingClientRect(), rt = t.getBoundingClientRect(), i = s.querySelector('.ico'), lbl = [...s.childNodes].find(n => n.nodeType === 3);
        const rg2 = document.createRange(); rg2.selectNodeContents(lbl); const lr = rg2.getBoundingClientRect();
        return { vis: !!s.offsetParent && getComputedStyle(s).display !== 'none', label: s.textContent.trim(), icon: !!i && i.classList.contains('i-bag') && getComputedStyle(i).display !== 'none',
                 title: s.title, aria: s.getAttribute('aria-label'), go: s.dataset.go, tag: s.tagName,
                 gapToCoins: Math.round(rg.left - rs.right), sameTop: Math.abs(rs.top - rg.top) < 1 && Math.abs(rt.top - rg.top) < 1, sameH: Math.abs(rs.height - rg.height) < 1,
                 w: Math.round(rs.width), h: Math.round(rs.height), titleFits: t.scrollWidth <= t.clientWidth + 1, signFits: g.scrollWidth <= g.clientWidth + 1,
                 labelIn: lr.left >= rs.left + 4 && lr.right <= rs.right - 4, order: rt.right <= rs.left && rs.right <= rg.left,
                 inWin: rg.right <= innerWidth - 10, sw: document.documentElement.scrollWidth, vw: innerWidth,
                 bottomSell: [...document.querySelectorAll('#fishing .btn')].filter(b => /SELL/.test(b.textContent)).length }; }"""
    ACTS = """() => { const bs = [...document.querySelectorAll('#fishing .actions .btn')], de = document.documentElement;
        return { labels: bs.map(b => b.textContent.trim()), ids: bs.map(b => b.id || b.dataset.go),
                 icons: bs.map(b => { const i = b.querySelector('.ico'); return i ? [...i.classList].find(c => c.startsWith('i-')) + (getComputedStyle(i).display !== 'none' ? '' : ':hidden') : null; }),
                 rects: bs.map(b => { const r = b.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }),
                 clipped: bs.filter(b => b.scrollWidth > b.clientWidth + 1 || [...b.childNodes].some(n => n.nodeType === 3 && n.textContent.trim() && (() => { const rg = document.createRange(); rg.selectNodeContents(n); const t = rg.getBoundingClientRect(), r = b.getBoundingClientRect(); return t.left < r.left + 4 || t.right > r.right - 4; })())).map(b => b.id || b.dataset.go),
                 page: de.scrollHeight, vh: innerHeight, sw: de.scrollWidth, vw: innerWidth }; }"""
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600), (390, 844), (360, 640)]:
        sp = b.new_page(viewport={"width": vw, "height": vh})
        sp.on("pageerror", lambda e: errs.append(str(e))); sp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        sp.goto(URL); sp.evaluate("localStorage.clear()"); sp.reload(); sp.wait_for_timeout(200); start_new(sp, "Shop")
        sp.add_style_tag(content="#toast { display: none !important; }")
        sp.evaluate("() => { island = 'desert'; go('fishing'); }"); sp.wait_for_timeout(400)
        a = sp.evaluate(ACTS)
        if (vw, vh) in ((1366, 625), (360, 640)): sp.screenshot(path=str(SHOTS / f"96_fishing_actions_{vw}x{vh}.png"))
        check(f"{vw}x{vh}: the fishing bottom row is exactly CAST | SHOP | TOWN MAP (shop and map icons), no SELL FISH",
              a["labels"] == ["CAST", "SHOP", "TOWN MAP"] and a["ids"] == ["actBtn", "fShopBtn", "map"]
              and a["icons"] == [None, "i-shop", "i-map"], f"{a['labels']} {a['icons']}")
        for coins in (300, 999999):
            sp.evaluate(f"() => {{ S.coins = {coins}; save(); render(); }}"); sp.wait_for_timeout(150)
            t = sp.evaluate(SELLTOP)
            if coins == 300 and (vw, vh) in ((1366, 625), (360, 640)): sp.screenshot(path=str(SHOTS / f"97_sell_top_{vw}x{vh}.png"))
            check(f"{vw}x{vh} ({coins} coins): SELL (bag icon, 'Sell your fish') sits directly left of the coin counter, same height, on one line with LITTLE LAKE; nothing cut off or overflowing",
                  t["vis"] and t["label"] == "SELL" and t["icon"] and t["title"] == "Sell your fish" and t["aria"] == "Sell your fish" and t["go"] == "bag" and t["tag"] == "BUTTON"
                  and 0 <= t["gapToCoins"] <= 12 and t["sameTop"] and t["sameH"] and t["order"] and t["titleFits"] and t["signFits"] and t["labelIn"]
                  and t["inWin"] and t["sw"] <= t["vw"] and t["bottomSell"] == 0, str(t))
            check(f"{vw}x{vh} ({coins} coins): SELL tap size >= 40x40px", t["w"] >= 40 and t["h"] >= 40, f"{t['w']}x{t['h']}")
        sp.evaluate("() => { S.coins = 300; save(); render(); }")
        R = a["rects"]
        if vw >= 900:
            layout = len({round(r[1]) for r in R}) == 1 and len({round(r[3] - r[1]) for r in R}) == 1
            layout = layout and len({round(r[2] - r[0]) for r in R}) == 1
            check(f"{vw}x{vh}: CAST, SHOP and TOWN MAP are three equal buttons on one row", layout, str([[round(v) for v in r] for r in R]))
        else:
            cast, rest = R[0], R[1:]
            layout = (len({round(r[1]) for r in rest}) == 1 and len({round(r[3] - r[1]) for r in rest}) == 1 and all(r[1] >= cast[3] for r in rest)
                      and len({round(r[2] - r[0]) for r in rest}) == 1 and cast[2] - cast[0] > 1.8 * (rest[0][2] - rest[0][0]) and min(r[3] - r[1] for r in rest) >= 40)
            check(f"{vw}x{vh}: CAST full width on top, SHOP / TOWN MAP as two equal smaller buttons in one row below (tap size >= 40px)",
                  layout, str([[round(v) for v in r] for r in R]))
        check(f"{vw}x{vh}: fishing buttons' labels fit (not cut off), no page or side scroll",
              not a["clipped"] and a["page"] <= a["vh"] + 1 and a["sw"] <= a["vw"], f"clipped {a['clipped']} page {a['page']}/{a['vh']} sw {a['sw']}")
        # CAST/HOOK/REEL doesn't move between phases
        tops = [sp.evaluate(ACT_POS)["top"]]
        sp.click("#actBtn"); sp.wait_for_function("F.phase === 'waiting'"); tops.append(sp.evaluate(ACT_POS)["top"])
        sp.wait_for_function("F.phase === 'bite'", timeout=8000); tops.append(sp.evaluate(ACT_POS)["top"])
        sp.click("#actBtn"); sp.wait_for_timeout(120); tops.append(sp.evaluate(ACT_POS)["top"])
        sp.evaluate("() => stopFishing()"); sp.wait_for_timeout(100); tops.append(sp.evaluate(ACT_POS)["top"])
        check(f"{vw}x{vh}: CAST/HOOK/REEL stays put in every phase with SELL in the top bar (<= 1px)", max(tops) - min(tops) <= 1, str([round(t, 1) for t in tops]))
        if vw in (1366, 360):
            sp.click("#fShopBtn"); sp.wait_for_timeout(300)
            on_shop = [sp.evaluate("current"), sp.inner_text("#navName")]
            shop_fit = sp.evaluate("document.documentElement.scrollHeight <= innerHeight + 1") if vw >= 900 else True
            sp.click("#navBack"); sp.wait_for_timeout(300)
            back = [sp.evaluate("current"), sp.evaluate("island"), sp.is_enabled("#actBtn"), "Desert" in sp.inner_text("#isleProg")]
            check(f"{vw}x{vh}: Fishing (Desert) > SHOP opens the Shop; BACK returns to the Fishing screen on the same island",
                  on_shop == ["shop", "SHOP"] and shop_fit and back == ["fishing", "desert", True, True], f"{on_shop} {back}")
            sp.click("#sellTop"); sp.wait_for_timeout(300)
            on_bag = [sp.evaluate("current"), sp.inner_text("#navName")]
            sp.click("#navBack"); sp.wait_for_timeout(300)
            check(f"{vw}x{vh}: SELL (top bar) opens the Bag; BACK returns to the Fishing screen on the same island",
                  on_bag == ["bag", "BAG"] and sp.evaluate("current") == "fishing" and sp.evaluate("island") == "desert", str(on_bag))
            hidden = {}
            for scr in ["home", "map", "bag", "shop", "collection", "tackle"]:
                sp.evaluate(f"() => go('{scr}')"); sp.wait_for_timeout(120); hidden[scr] = sp.is_visible("#sellTop")
            sp.evaluate("() => { S.pending = { fishId: 'harbor_0', weight: .3, price: 20, time: 1 }; save(); go('result'); }"); sp.wait_for_timeout(150)
            hidden["result"] = [sp.evaluate("current"), sp.is_visible("#sellTop")]
            sp.evaluate("() => { S.pending = null; save(); island = 'desert'; go('fishing'); }"); sp.wait_for_timeout(200)
            check(f"{vw}x{vh}: SELL is only in the Fishing screen's top bar (not on Home, Map, Bag, Shop, Collection, Tackle Box or Result)",
                  not any(v for k, v in hidden.items() if k != "result") and hidden["result"] == ["result", False], str(hidden))
            sp.click("#rodChip"); sp.wait_for_timeout(200)
            check(f"{vw}x{vh}: the Choose Rod popup keeps its GO TO SHOP link", sp.is_visible("#pickShop") and "SHOP" in sp.inner_text("#pickShop"))
            sp.keyboard.press("Escape"); sp.wait_for_timeout(100)
        sp.close()
    hw = b.new_page(viewport={"width": 1280, "height": 720}); hw.goto(URL); hw.wait_for_timeout(200); hw.click("#howBtn"); hw.wait_for_timeout(150)
    how = hw.inner_text("#howBox")
    check("HOW TO PLAY: no 'OPEN BAG' / 'SELL FISH'; says SELL is next to your coins and mentions SHOP on the fishing screen",
          "While fishing, SELL (next to your coins at the top) opens the bag." in how and "SELL FISH" not in how and "with SHOP on the fishing screen" in how and "OPEN BAG" not in how, how[:80])
    hw.close()

    # ---------- Playtest 2, part 1: the fish shadow approaches the bait and fights during REEL (visual only) ----------
    import math
    SAMPLER = """() => { window.__sh = []; window.__shRun = true; const f = () => { const s = fishShadowState(); window.__sh.push({ t: performance.now(), ph: F.phase, s, fid: F.fish && F.fish.id, ca: F.castAt, cd: F.cd, ba: F.biteAt, bp: F.bobPos && [F.bobPos.x, F.bobPos.y] });
        if (window.__shRun) requestAnimationFrame(f); }; requestAnimationFrame(f); }"""
    def sh_collect(pg):
        pg.evaluate("() => { window.__shRun = false; }"); pg.wait_for_timeout(60); return pg.evaluate("window.__sh")
    def sh_cast(pg):
        pg.evaluate(SAMPLER); pg.click("#actBtn")
        pg.wait_for_function("F.phase === 'bite'", timeout=9000); pg.wait_for_timeout(120)
    def sh_hit(pg):
        pg.wait_for_function("F.phase !== 'reeling' || (F.pos > F.zoneX + 0.02 && F.pos < F.zoneX + F.zoneW - 0.02)", timeout=9000, polling=5); pg.click("#actBtn")
    def sh_miss(pg):
        pg.wait_for_function("F.phase !== 'reeling' || F.pos < F.zoneX - 0.06 || F.pos > F.zoneX + F.zoneW + 0.06", timeout=9000, polling=5); pg.click("#actBtn")
    def sh_now(pg): return pg.evaluate("fishShadowState()")
    def sh_avg(pg, key, n=6, gap=40):
        v = []
        for _ in range(n):
            st = sh_now(pg)
            if st: v.append(st[key])
            pg.wait_for_timeout(gap)
        return sum(v) / max(1, len(v))
    def winding(samples):                                           # total angle swept around the bobber's resting spot by the "circle" samples (radians)
        tot, prev = 0.0, None
        for a in samples:
            s = a["s"]
            if not s or s["phase"] != "circle": prev = None; continue
            ang = math.atan2((s["y"] * s["H"] - (s["bob"]["y"] * s["H"] + 8 * s["W"] / 900)) / .42, s["x"] * s["W"] - s["bob"]["x"] * s["W"])
            if prev is not None:
                d = ang - prev
                while d > math.pi: d -= 2 * math.pi
                while d < -math.pi: d += 2 * math.pi
                tot += d
            prev = ang
        return abs(tot)
    fsp = b.new_page(viewport={"width": 1536, "height": 730})
    fsp.on("pageerror", lambda e: errs.append(str(e))); fsp.on("console", lambda m: m.type == "error" and errs.append(m.text))
    fsp.goto(URL); fsp.evaluate("localStorage.clear()"); fsp.reload(); fsp.wait_for_timeout(300); start_new(fsp, "Shadow")
    fsp.add_style_tag(content="#toast { display: none !important; }")
    fsp.wait_for_function("Object.values(SCENES).every(s => s.img || s.failed)", timeout=8000)
    fsp.evaluate(UNLOCK)
    waits = []; ok = {k: True for k in ["exists", "id", "shrinks", "near0", "circle", "nib", "bounds", "water", "timing", "face"]}
    notes = {}
    for isl in ["harbor", "frost", "desert", "forest", "secret"]:
        fsp.evaluate(f"() => {{ island = '{isl}'; go('fishing'); }}"); fsp.wait_for_timeout(350)
        sh_cast(fsp); smp = sh_collect(fsp)
        wt = [a for a in smp if a["ph"] == "waiting"]; sd = [a for a in wt if a["s"]]
        bite_t = next(a["t"] for a in smp if a["ph"] == "bite"); c0 = next(a for a in smp if a["ca"]); span = c0["ba"] - (c0["ca"] + (c0["cd"] or 500))
        waits.append(span)
        ok["exists"] &= len(sd) >= 0.8 * len(wt) and len(sd) > 30
        ok["id"] &= all(a["s"]["fishId"] == a["fid"] for a in smp if a["s"] and a["ph"] in ("waiting", "bite"))
        n3 = max(1, len(sd) // 3); d_first = sum(a["s"]["dBob"] for a in sd[:n3]) / n3; d_last = sum(a["s"]["dBob"] for a in sd[-n3:]) / n3
        ok["shrinks"] &= d_first > 2 * d_last and sd[-1]["s"]["dBob"] < 25 and d_first > 60
        near = [a for a in smp if a["ph"] == "bite" and a["s"]]
        ok["near0"] &= len(near) > 0 and all(a["s"]["dBob"] < 45 for a in near)
        ok["circle"] &= winding(sd) > 5.5 and any(a["s"]["phase"] == "nibble" for a in sd)
        nib = [a["bp"][1] for a in sd if a["s"]["phase"] == "nibble" and a["bp"]]
        Hh = sd[0]["s"]["H"]
        ok["nib"] &= (max(nib) - min(nib)) * Hh > 3 if nib else False                  # the float dips a few pixels
        # the real wait is still 1-5 s: the bite fires at biteAt (1000 + random * 4000 ms after the bobber lands)
        ok["timing"] &= 1000 <= span <= 5000 and abs(bite_t - c0["ba"]) < 150
        ok["bounds"] &= all(.30 <= a["s"]["x"] <= .92 and .5 <= a["s"]["y"] <= .9 for a in smp if a["s"])
        ok["face"] &= all(a["s"]["face"] == -1 for a in sd[len(sd) // 10: len(sd) // 3])      # swimming in from the right: head toward the bobber
        if isl in PICS:
            crop = fsp.evaluate("[CROP.sx, CROP.sy, CROP.sw, CROP.sh]")
            pts = [(crop[0] + a["s"]["x"] * crop[2], crop[1] + a["s"]["y"] * crop[3]) for a in smp[::4] if a["s"]]
            bad = sum(1 for (x, y) in pts if not fsp.evaluate(ON_WATER, [MASKS[isl], x, y]))
            ok["water"] &= bad == 0; notes[isl] = f"{len(pts)} pts, {bad} off water"
        fsp.evaluate("() => { clearTimers(); escape('x'); }"); fsp.wait_for_timeout(1200)
    check("fish shadow: it exists the whole wait on all five islands and its fishId is F.fish.id", ok["exists"] and ok["id"], str(ok))
    check("fish shadow: it swims in from the right (head to the bobber), its distance to the bobber shrinks over the wait and is near 0 at the bite", ok["shrinks"] and ok["near0"] and ok["face"], str(ok))
    check("fish shadow: it circles the bobber once and nibbles (the float dips a few pixels) before the bite", ok["circle"] and ok["nib"], str(ok))
    check("fish shadow: the wait is unchanged (1-5 s after the bobber lands; the bite fires at F.biteAt)", ok["timing"] and all(1000 <= w <= 5000 for w in waits), str([round(w) for w in waits]))
    check("fish shadow: it never leaves the water (every sampled point is on the water mask; Harbor stays inside the open-water box)", ok["water"] and ok["bounds"], str(notes))
    # --- REEL: each hit pulls it a third closer to the dock, each miss makes it dart back, the third hit pulls it up with a splash ---
    fsp.evaluate("() => { island = 'harbor'; go('fishing'); }"); fsp.wait_for_timeout(350)
    sh_cast(fsp); sh_collect(fsp); fsp.click("#actBtn"); fsp.wait_for_timeout(600)
    d0 = sh_avg(fsp, "dDockC"); st0 = sh_now(fsp)
    xs = []
    for _ in range(30): xs.append(sh_now(fsp)["x"] * 900); fsp.wait_for_timeout(80)
    check("REEL: the shadow stays near the bobber and thrashes sideways (quick motion), phase 'reel'", st0["phase"] == "reel" and st0["dBob"] < 60 and max(xs) - min(xs) > 2, f"{st0['phase']} dBob={st0['dBob']:.0f} spread={max(xs) - min(xs):.1f}px")
    bob_a = fsp.evaluate("F.bobPos.x")
    sh_hit(fsp); fsp.wait_for_timeout(700); d1 = sh_avg(fsp, "dDockC")
    sh_miss(fsp); fsp.wait_for_timeout(70); dk = sh_now(fsp)["dDockC"]; fsp.wait_for_timeout(800); dm = sh_avg(fsp, "dDockC")
    bob_b = fsp.evaluate("F.bobPos.x")
    sh_hit(fsp); fsp.wait_for_timeout(700); d2 = sh_avg(fsp, "dDockC")
    check("REEL: each HIT moves the shadow closer to the dock (about a third of the way); a MISS darts it back",
          d0 > d1 + 5 and d1 > d2 + 5 and dk > d1 + 5 and dm > d1 + 2 and dm > d2 + 5 and abs((d0 - d1) - (d1 - d2)) < .6 * (d0 - d1), f"d0={d0:.0f} d1={d1:.0f} kick={dk:.0f} afterMiss={dm:.0f} d2={d2:.0f}")
    check("REEL: the float is dragged along with the fish (the bobber moves toward the dock too)", bob_b < bob_a - .01, f"{bob_a:.3f} -> {bob_b:.3f}")
    fsp.screenshot(path=str(SHOTS / "103_shadow_midreel_1536x730.png"))
    sh_hit(fsp); fsp.wait_for_timeout(120); stc = sh_now(fsp)
    check("REEL: the third hit pulls the shadow to the surface (phase 'catch', splash) just before the Result screen", stc is not None and stc["phase"] == "catch" and fsp.evaluate("current") == "fishing", str(stc and stc["phase"]))
    fsp.wait_for_function("current === 'result'", timeout=3000); fsp.wait_for_timeout(100)
    check("the shadow is gone on the Result screen and the catch is the fish it showed", sh_now(fsp) is None and fsp.evaluate("S.pending && S.pending.fishId") == stc["fishId"], str(stc["fishId"]))
    fsp.evaluate("() => { releaseCatch(); }"); fsp.wait_for_timeout(300)
    # --- escape: a missed HOOK window and too many misses: it swims away and fades ---
    sh_cast(fsp); sh_collect(fsp)
    fsp.wait_for_function("F.phase === 'idle'", timeout=3000); a1 = sh_now(fsp); fsp.wait_for_timeout(500); a2 = sh_now(fsp); fsp.wait_for_timeout(900); a3 = sh_now(fsp)
    check("missed HOOK window: the shadow swims away from the bobber toward the deep side and fades out",
          bool(a1 and a2) and a1["phase"] == "leave" and a2["x"] > a1["x"] + .03 and a2["alpha"] < a1["alpha"] and a3 is None, f"{a1 and round(a1['x'], 3)} -> {a2 and round(a2['x'], 3)} gone={a3 is None}")
    fsp.wait_for_timeout(200)
    sh_cast(fsp); sh_collect(fsp); fsp.click("#actBtn"); fsp.wait_for_timeout(300)
    for _ in range(8):                                                 # Master's Charm (UNLOCK) allows one more miss: keep missing until the fish escapes
        if fsp.evaluate("F.phase") != "reeling": break
        sh_miss(fsp); fsp.wait_for_timeout(120)
    fsp.wait_for_timeout(0)
    e1 = sh_now(fsp); fsp.wait_for_timeout(500); e2 = sh_now(fsp); fsp.wait_for_timeout(900); e3 = sh_now(fsp)
    check("too many misses: the shadow swims away and fades, then it is gone", bool(e1 and e2) and e1["phase"] == "leave" and e2["x"] > e1["x"] + .03 and e3 is None, f"{e1 and e1['phase']} gone={e3 is None}")
    fsp.evaluate("() => { go('home'); go('fishing'); }"); fsp.wait_for_timeout(300)
    check("leaving the fishing screen clears the shadow", sh_now(fsp) is None)
    fsp.close()
    # --- prefers-reduced-motion: no circling, no thrashing: it fades in, moves in a straight line and fades out ---
    rms = b.new_page(viewport={"width": 360, "height": 640}, reduced_motion="reduce")
    rms.on("pageerror", lambda e: errs.append(str(e))); rms.on("console", lambda m: m.type == "error" and errs.append(m.text))
    rms.goto(URL); rms.evaluate("localStorage.clear()"); rms.reload(); rms.wait_for_timeout(300); start_new(rms, "Calm")
    rms.add_style_tag(content="#toast { display: none !important; }")
    rms.evaluate("() => { island = 'harbor'; go('fishing'); }"); rms.wait_for_timeout(400)
    sh_cast(rms); smp = sh_collect(rms); sd = [a["s"] for a in smp if a["s"] and a["ph"] == "waiting"]
    X0, Y0, X1, Y1 = sd[0]["x"] * 900, sd[0]["y"] * sd[0]["H"], sd[-1]["x"] * 900, sd[-1]["y"] * sd[-1]["H"]
    ln = math.hypot(X1 - X0, Y1 - Y0) or 1
    dev = max(abs((X1 - X0) * (s["y"] * s["H"] - Y0) - (Y1 - Y0) * (s["x"] * 900 - X0)) / ln for s in sd)
    check("reduced-motion emulated: while waiting the shadow still circles and nibbles (more than the straight approach, off the straight line)",
          len({s["phase"] for s in sd}) > 1 and dev > 2, f"phases={ {s['phase'] for s in sd} } deviation={dev:.2f}px")
    rms.click("#actBtn"); rms.wait_for_timeout(500)
    xs = []
    for _ in range(30): xs.append(sh_now(rms)["x"] * 900); rms.wait_for_timeout(80)      # the same sampling as the normal-motion thrash test (10 quick samples were borderline)
    check("reduced-motion emulated: the shadow still thrashes while reeling", max(xs) - min(xs) > 2, f"spread {max(xs) - min(xs):.2f}px")
    sh_miss(rms); rms.wait_for_timeout(100); sh_miss(rms); rms.wait_for_timeout(100); r1 = sh_now(rms); rms.wait_for_timeout(400); r2 = sh_now(rms)
    check("reduced-motion emulated: on escape it still swims away and fades out", bool(r1 and r2) and r1["phase"] == "leave" and r2["x"] > r1["x"] and r2["alpha"] < r1["alpha"], f"{r1 and r1['phase']}")
    rms.close()
    # --- screenshots (shadow approaching, bite, mid-reel) on Harbor and Frost at 1536x730 and 360x640 ---
    for vw, vh in [(1536, 730), (360, 640)]:
        ssp = b.new_page(viewport={"width": vw, "height": vh})
        ssp.on("pageerror", lambda e: errs.append(str(e))); ssp.on("console", lambda m: m.type == "error" and errs.append(m.text))
        ssp.goto(URL); ssp.evaluate("localStorage.clear()"); ssp.reload(); ssp.wait_for_timeout(300); start_new(ssp, "Shots")
        ssp.add_style_tag(content="#toast { display: none !important; }")
        ssp.wait_for_function("Object.values(SCENES).every(s => s.img || s.failed)", timeout=8000)
        for isl in ["harbor", "frost"]:
            ssp.evaluate(f"() => {{ island = '{isl}'; go('fishing'); }}"); ssp.wait_for_timeout(350)
            ssp.click("#actBtn")
            try: ssp.wait_for_function("(() => { const s = fishShadowState(); return s && s.phase === 'approach' && s.dBob < 85 && s.alpha > .9; })()", timeout=9000, polling=20)
            except Exception: pass
            ssp.screenshot(path=str(SHOTS / f"101_shadow_approach_{isl}_{vw}x{vh}.png"))
            ssp.wait_for_function("F.phase === 'bite'", timeout=9000); ssp.wait_for_timeout(110)
            ssp.screenshot(path=str(SHOTS / f"102_shadow_bite_{isl}_{vw}x{vh}.png"))
            ssp.click("#actBtn"); ssp.wait_for_timeout(300); sh_hit(ssp); ssp.wait_for_timeout(750)
            ssp.screenshot(path=str(SHOTS / f"103_shadow_reel_{isl}_{vw}x{vh}.png"))
            ssp.evaluate("() => { clearTimers(); escape('x'); }"); ssp.wait_for_timeout(1200)
        ssp.close()

    # ---------- Playtest 2, part 2: fight feel (line tension and fish personalities); visual, sound and vibration only ----------
    FIGHT_IDS = {"Common": "harbor_0", "Rare": "harbor_4", "Epic": "harbor_7", "Legendary": "harbor_9"}
    def fh_page(vw, vh, reduced=False, vib=False, name="Fight"):
        kw = {"viewport": {"width": vw, "height": vh}}
        if reduced: kw["reduced_motion"] = "reduce"
        pg_ = b.new_page(**kw)
        if vib: pg_.add_init_script("window.__vib = []; navigator.vibrate = p => { window.__vib.push(p); return true; };")
        pg_.on("pageerror", lambda e: errs.append(str(e))); pg_.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg_.goto(URL); pg_.evaluate("localStorage.clear()"); pg_.reload(); pg_.wait_for_timeout(300); start_new(pg_, name)
        pg_.add_style_tag(content="#toast { display: none !important; }")
        pg_.wait_for_function("Object.values(SCENES).every(s => s.img || s.failed)", timeout=8000)
        return pg_
    def fh_hook(pg_, fish_id, isl="harbor"):
        """cast, then (skipping the random wait, which part 1 tests) force the bite for the chosen fish and press HOOK."""
        pg_.evaluate(f"() => {{ island = '{isl}'; S.pending = null; go('fishing'); }}"); pg_.wait_for_timeout(300)
        pg_.click("#actBtn"); pg_.wait_for_function("F.phase === 'waiting'", timeout=4000); pg_.wait_for_timeout(150)
        pg_.evaluate(f"() => {{ clearTimers(); F.fish = fishById('{fish_id}'); bite(); }}"); pg_.wait_for_timeout(120)
        pg_.click("#actBtn"); pg_.wait_for_timeout(150)
    def fh_hit(pg_):                                                    # a sure hit: put the marker in the middle of the zone and run the real reel() (a mouse click is too slow for the fast Legendary marker)
        pg_.wait_for_function("F.phase === 'reeling'", timeout=9000); pg_.evaluate("() => { F.pos = F.zoneX + F.zoneW / 2; reel(); }")
    def fh_miss(pg_):                                                   # a sure miss: marker at the far left, outside the zone (the zone starts at .1 or later)
        pg_.wait_for_function("F.phase === 'reeling'", timeout=9000); pg_.evaluate("() => { F.pos = 0; reel(); }")
    def fh_state(pg_): return pg_.evaluate("fightState()")
    def fh_end(pg_): pg_.evaluate("() => { clearTimers(); escape('x'); }"); pg_.wait_for_timeout(1100)
    SEC_ID = None
    fp = fh_page(1536, 730)
    SEC_ID = fp.evaluate("FISH.find(f => f.island === 'secret').id")
    fp.evaluate("() => { S.rods = ['bamboo', 'sturdy']; S.rodEq = 'sturdy'; save(); }")        # Sturdy: 2 misses allowed, so danger is false at the start
    # --- fightState exists only while reeling; personality follows the rarity ---
    fp.evaluate("() => { island = 'harbor'; go('fishing'); }"); fp.wait_for_timeout(300)
    none_idle = fh_state(fp) is None
    fp.click("#actBtn"); fp.wait_for_function("F.phase === 'waiting'", timeout=4000); fp.wait_for_timeout(100)
    none_wait = fh_state(fp) is None
    fp.evaluate("() => { clearTimers(); bite(); }"); fp.wait_for_timeout(100); none_bite = fh_state(fp) is None
    fp.click("#actBtn"); fp.wait_for_timeout(150); in_reel = fh_state(fp)
    fh_end(fp)
    check("fightState() is null while idle, waiting and on the bite, and exists while reeling", none_idle and none_wait and none_bite and in_reel is not None and set(in_reel) >= {"tension", "personality", "danger", "tickMs"}, str(in_reel and {k: in_reel[k] for k in ("tension", "personality", "danger", "tickMs")}))
    pers = {}
    EXPECT = {"Common": "steady", "Rare": "dash", "Epic": "zigzag", "Legendary": "leap", "Mythical": "leap"}
    for rar, fid in list(FIGHT_IDS.items()) + [("Mythical", SEC_ID)]:
        fh_hook(fp, fid, "secret" if rar == "Mythical" else "harbor"); st = fh_state(fp); pers[rar] = (st["personality"], round(st["tension"], 2)); fh_end(fp)
    check("personality matches the rarity: Common steady, Rare dash, Epic zigzag, Legendary and the secret Mythical fish leap", all(pers[r][0] == EXPECT[r] for r in EXPECT), str(pers))
    check("base tension by rarity: Common .35, Rare .5, Epic .65, Legendary and Mythical .8 (no hit or miss yet)",
          all(abs(pers[r][1] - v) < .03 for r, v in {"Common": .35, "Rare": .5, "Epic": .65, "Legendary": .8, "Mythical": .8}.items()), str(pers))
    # --- tension spike after a miss decays; danger and the red line ---
    fh_hook(fp, FIGHT_IDS["Common"])
    s0 = fh_state(fp); line0 = s0["line"]
    fh_hit(fp); fp.wait_for_timeout(60); s_hit = fh_state(fp); fp.wait_for_timeout(1100)
    fh_miss(fp); fp.wait_for_timeout(60); s1 = fh_state(fp); fp.wait_for_timeout(1300); s2 = fh_state(fp)
    check("tension rises after a hit and after a miss and decays back to the rarity's base", s_hit["tension"] > s0["tension"] + .1 and s1["tension"] > s0["tension"] + .2 and abs(s2["tension"] - s0["tension"]) < .06,
          f"base {s0['tension']:.2f} hit {s_hit['tension']:.2f} miss {s1['tension']:.2f} later {s2['tension']:.2f}")
    check("danger is false with 2 misses left (Sturdy Rod) and true with one miss left; the line is white, then warm red", s0["danger"] is False and s1["danger"] is True and s2["danger"] is True and s0["red"] == 0 and s2["red"] > .9,
          f"{s0['danger']} {s1['danger']} {s2['danger']} red {s0['red']:.2f} -> {s2['red']:.2f}")
    rgb = lambda c: [float(v) for v in c[c.index("(") + 1:c.rindex(")")].split(",")[:3]]
    c0, c2 = rgb(s0["line"]), rgb(s2["line"])
    check("the line colour blends from white to a reddish colour (red channel far above green and blue)", abs(c0[0] - c0[1]) < 1 and abs(c0[0] - c0[2]) < 1 and c2[0] - c2[1] > 100 and c2[0] - c2[2] > 150, f"{s0['line']} -> {s2['line']}")
    # the line is really stroked in that colour (canvas pixels can't be read over file://, so record ctx.strokeStyle at the line's stroke call)
    drawn = fp.evaluate("""() => { const q = ctx.quadraticCurveTo, st = ctx.stroke; let flag = false, col = null;
        ctx.quadraticCurveTo = function (...a) { flag = true; return q.apply(this, a); }; ctx.stroke = function () { if (flag) { col = this.strokeStyle; flag = false; } return st.apply(this); };
        drawScene(performance.now()); ctx.quadraticCurveTo = q; ctx.stroke = st; return col; }""")
    check("the line is drawn with the warm red stroke while in danger", drawn is not None and rgb(drawn)[0] - rgb(drawn)[2] > 100 if drawn and "rgb" in drawn else False, str(drawn))
    fh_end(fp)
    # --- rod bends more with tension ---
    bends = {}
    for rar in ("Common", "Legendary"):
        fh_hook(fp, FIGHT_IDS[rar]); v = []
        for _ in range(14): v.append(fp.evaluate("P.bend")); fp.wait_for_timeout(45)
        bends[rar] = sum(v) / len(v); fh_end(fp)
    check("the rod bends more at higher tension (Legendary vs Common, same pose code, scaled)", bends["Legendary"] > bends["Common"] + 2, str({k: round(v, 1) for k, v in bends.items()}))
    # --- the reel tick speeds up with tension ---
    ticks = {}; tms = {}
    for rar in ("Common", "Legendary"):
        fh_hook(fp, FIGHT_IDS[rar]); tms[rar] = fh_state(fp)["tickMs"]
        fp.evaluate("() => { window.__tk = []; const o = sfx.reelTick; window.__tko = o; sfx.reelTick = x => { window.__tk.push(performance.now()); return o(x); }; }")
        fp.wait_for_timeout(2300); log = fp.evaluate("() => { sfx.reelTick = window.__tko; return window.__tk; }")
        ticks[rar] = (log[-1] - log[0]) / (len(log) - 1) if len(log) > 2 else 9999; fh_end(fp)
    check("the reel tick interval shortens with tension (tickMs and the real tick calls, Common vs Legendary)", tms["Legendary"] < tms["Common"] - 80 and ticks["Legendary"] < ticks["Common"] * .8, f"tickMs {tms} measured {({k: round(v) for k, v in ticks.items()})}")
    # --- a miss makes the ticks faster for a moment ---
    fh_hook(fp, FIGHT_IDS["Common"]); t_before = fh_state(fp)["tickMs"]; fh_miss(fp); fp.wait_for_timeout(50); t_after = fh_state(fp)["tickMs"]; fh_end(fp)
    check("tickMs is shorter right after a miss", t_after < t_before - 60, f"{t_before} -> {t_after}")
    # --- personalities: Common steady, Rare dashes (ripple), Epic zigzag, Legendary leaps only on a hit ---
    mv = {}
    for rar in ("Common", "Rare", "Epic"):
        fh_hook(fp, FIGHT_IDS[rar]); xs = []; ys = []
        for _ in range(36):
            st = fp.evaluate("[SH.x, SH.dx, SH.dy, FIGHT.personality]"); xs.append(st[1]); ys.append(st[2]); fp.wait_for_timeout(70)
        mv[rar] = (max(xs) - min(xs), max(ys) - min(ys)); fh_end(fp)
    check("personality movement: steady sways slowly, a dash covers 25+ px quickly, zigzag moves both ways with a vertical zig", mv["Common"][0] > 12 and mv["Rare"][0] > 25 and mv["Epic"][0] > 20 and mv["Epic"][1] > 4, str({k: (round(a), round(b)) for k, (a, b) in mv.items()}))
    leap = {}
    for rar, fid in list(FIGHT_IDS.items()) + [("Mythical", SEC_ID)]:
        isl = "secret" if rar == "Mythical" else "harbor"
        fh_hook(fp, fid, isl); fp.evaluate("() => { window.__lp = []; window.__lpr = true; const f = () => { const s = fightState(); window.__lp.push(s ? [s.leaping, s.lx, s.ly, s.W, s.H] : null); if (window.__lpr) requestAnimationFrame(f); }; f(); }")
        fp.wait_for_timeout(700); before = fp.evaluate("window.__lp.filter(x => x && x[0]).length")
        fh_hit(fp); fp.wait_for_timeout(700)
        fp.evaluate("() => { window.__lpr = false; }"); fp.wait_for_timeout(60); lp = [x for x in fp.evaluate("window.__lp") if x and x[0]]
        leap[rar] = (before, len(lp), lp); fh_end(fp)
    check("the leap happens only for Legendary and Mythical, and only after a hit",
          all(leap[r][0] == 0 for r in leap) and leap["Legendary"][1] > 5 and leap["Mythical"][1] > 5 and leap["Common"][1] == 0 and leap["Rare"][1] == 0 and leap["Epic"][1] == 0, str({k: (v[0], v[1]) for k, v in leap.items()}))
    ap = min(leap["Legendary"][2], key=lambda x: x[2]); apM = min(leap["Mythical"][2], key=lambda x: x[2])
    check("the leap stays in the water area on Harbor (inside the open-water box, never over the dock or the horizon)", all(.30 <= x[1] <= .92 and .45 <= x[2] <= .9 for r in ("Legendary", "Mythical") for x in leap[r][2]), f"apex {ap[1]:.2f},{ap[2]:.2f}")
    # frost: shadow and leap against the real water mask
    fp.evaluate("() => { S.mastery = {}; save(); }")
    fr_id = fp.evaluate("FISH.find(f => f.island === 'frost' && f.rarity === 'Legendary').id")
    fh_hook(fp, fr_id, "frost"); fp.evaluate("() => { window.__lp = []; window.__lpr = true; const f = () => { const s = fightState(); window.__lp.push(s ? [s.leaping, SH.x / SH.W, SH.y / SH.H, s.lx, s.ly] : null); if (window.__lpr) requestAnimationFrame(f); }; f(); }")
    fp.wait_for_timeout(500); fh_hit(fp); fp.wait_for_timeout(700); fh_miss(fp); fp.wait_for_timeout(500); fp.evaluate("() => { window.__lpr = false; }"); fp.wait_for_timeout(60)
    lp = [x for x in fp.evaluate("window.__lp") if x]; crop = fp.evaluate("[CROP.sx, CROP.sy, CROP.sw, CROP.sh]")
    pts = [(crop[0] + x[1] * crop[2], crop[1] + x[2] * crop[3]) for x in lp[::6]] + [(crop[0] + x[3] * crop[2], crop[1] + x[4] * crop[3]) for x in lp if x[0]][::4]
    bad = sum(1 for (x, y) in pts if not fp.evaluate(ON_WATER, [MASKS["frost"], x, y]))
    check("Frost: the shadow and the leaping fish stay on the water mask during the whole fight", bad == 0 and len(pts) > 8 and any(x[0] for x in lp), f"{len(pts)} points, {bad} off water")
    fh_end(fp)
    # --- particles are capped ---
    cap = fp.evaluate("() => { for (let i = 0; i < 40; i++) partSpawn(300, 250, 8, 1); return [partCount(), PART_N]; }")
    check("splash particles use a fixed pool (never more than 24 alive)", cap[0] <= cap[1] == 24, str(cap))
    fp.evaluate("() => { PART.life.fill(0); }")
    # --- the rules are exactly as before: the same seeded run gives the rule's own numbers, and the fight code draws no random numbers ---
    rules = fp.evaluate("""() => { island = 'harbor'; go('fishing'); const calls = []; let seed = 12345; const orig = Math.random;
        Math.random = () => { seed = seed * 16807 % 2147483647; const v = seed / 2147483647; calls.push(v); return v; };
        const out = { zones: [], phases: [] };
        try {
          F = { phase: 'bite', fish: fishById('harbor_4'), castAt: performance.now(), biteAt: performance.now() + 1000, land: { x: .6, y: .65 }, usedBait: null, floatId: 'classic' };
          hook(); out.speed = F.speed; out.zoneW = F.zoneW; out.expSpeed = DIFF.Rare.speed * rod().speed * (S.mastery.frost ? .8 : 1); out.expZone = DIFF.Rare.zone * rod().zone; out.zones.push(F.zoneX);
          out.allowed = allowedMiss();
          for (const press of ['in', 'out', 'in', 'out', 'out', 'out']) {
            if (F.phase !== 'reeling') break;
            F.pos = press === 'in' ? F.zoneX + F.zoneW / 2 : (F.zoneX > .2 ? 0 : 1); reel(); out.phases.push([press, F.phase, F.hits, F.misses]); if (F.phase === 'reeling') out.zones.push(F.zoneX);
          }
        } finally { Math.random = orig; }
        out.calls = calls.length; out.seq = calls.slice(0, 8); return out; }""")
    exp_z = [.1 + rules["seq"][i] * (.8 - rules["zoneW"]) for i in range(len(rules["zones"]))]
    check("rules unchanged: speed and zone width are the rarity x rod formulas; every new zone consumes exactly one random number (the seeded zone sequence is reproduced)",
          abs(rules["speed"] - rules["expSpeed"]) < 1e-9 and abs(rules["zoneW"] - rules["expZone"]) < 1e-9 and all(abs(a - b) < 1e-9 for a, b in zip(rules["zones"], exp_z)) and rules["calls"] == len(rules["zones"]), str({k: rules[k] for k in ("speed", "zoneW", "calls")}) + f" zones={len(rules['zones'])}")
    ph = rules["phases"]
    check("rules unchanged: a hit inside the zone, a miss outside; with Sturdy (2 misses) the third miss escapes", ph[0][1:] == ["reeling", 1, 0] and ph[1][1:] == ["reeling", 1, 1] and ph[2][1:] == ["reeling", 2, 1] and ph[3][1:] == ["reeling", 2, 2] and ph[4][1] == "idle" and rules["allowed"] == 2, str(ph))
    fp.evaluate("() => { stopFishing(); }")
    fh_hook(fp, FIGHT_IDS["Rare"]); fp.evaluate("() => { window.__rc = 0; window.__ro = Math.random; Math.random = () => { window.__rc++; return window.__ro(); }; }")
    fp.wait_for_timeout(1500); rc = fp.evaluate("() => { Math.random = window.__ro; return window.__rc; }")
    sp1 = fp.evaluate("[F.pos, F.dir, F.speed, performance.now()]"); fp.wait_for_timeout(120); sp2 = fp.evaluate("[F.pos, F.dir, F.speed, performance.now()]")
    meas = abs(sp2[0] - sp1[0]) / ((sp2[3] - sp1[3]) / 1000) if sp1[1] == sp2[1] else sp2[2]
    check("rules unchanged: no random numbers are drawn by the frames while reeling (tension, dashes, particles) and the marker still moves at F.speed", rc == 0 and abs(meas - sp1[2]) < .25 * sp1[2], f"random calls={rc}, marker {meas:.2f}/s vs speed {sp1[2]:.2f}")
    fh_end(fp)
    fp.close()
    # --- vibration: a short pulse on a hit, a double pulse on a miss; none with reduced motion ---
    vp = fh_page(1536, 730, vib=True, name="Vibe")
    fh_hook(vp, FIGHT_IDS["Common"]); vp.evaluate("() => { window.__vib.length = 0; }")
    fh_hit(vp); vp.wait_for_timeout(100); v_hit = vp.evaluate("window.__vib.slice()"); vp.evaluate("() => { window.__vib.length = 0; }")
    fh_miss(vp); vp.wait_for_timeout(100); v_miss = vp.evaluate("window.__vib.slice()")
    check("vibration (mocked navigator.vibrate): a short pulse on a hit, a double pulse on a miss", v_hit == [40] and v_miss == [[30, 30, 30]], f"hit {v_hit} miss {v_miss}")
    vp.close()
    rp = fh_page(1536, 730, reduced=True, vib=True, name="Calm2")
    fh_hook(rp, FIGHT_IDS["Legendary"]); rp.evaluate("() => { window.__vib.length = 0; window.__tk = []; const o = sfx.reelTick; sfx.reelTick = x => { window.__tk.push(1); return o(x); }; }")
    fh_hit(rp); rp.wait_for_timeout(80); fh_miss(rp); rp.wait_for_timeout(60)
    r_st = fh_state(rp); r_vib = rp.evaluate("window.__vib.slice()")
    xs = []
    for _ in range(12): xs.append(rp.evaluate("SH.dx") ); rp.wait_for_timeout(40)
    r_leap = []; r_part = []
    fh_hit(rp)                                                          # a fresh hit: the leap and the splash particles start right now
    for _ in range(8): r_leap.append(fh_state(rp)["leaping"]); r_part.append(fh_state(rp)["particles"]); rp.wait_for_timeout(40)
    rp.wait_for_timeout(1200); r_tk = rp.evaluate("window.__tk.length"); r_line = fh_state(rp)
    check("reduced-motion emulated: vibration, shake / dash / leap and particles all still happen", len(r_vib) >= 1 and any(x != 0 for x in xs) and (any(r_leap) or max(r_part) > 0), f"vib={r_vib} dx={set(xs)} leap={any(r_leap)} particles={max(r_part)}")
    check("reduced-motion emulated: the line colour change (danger) and the reel tick sounds stay", r_line is not None and r_line["danger"] and r_line["red"] > .9 and r_tk >= 4, f"red={r_line and r_line['red']} ticks={r_tk}")
    rp.close()
    # --- screenshots: Common mid-reel, a Legendary leap, the red danger line (1536x730 and 360x640) ---
    for vw, vh in [(1536, 730), (360, 640)]:
        sp = fh_page(vw, vh, name="Shots")
        fh_hook(sp, FIGHT_IDS["Common"]); sp.wait_for_timeout(500); sp.screenshot(path=str(SHOTS / f"104_fight_common_{vw}x{vh}.png"))
        fh_miss(sp); sp.wait_for_timeout(900); sp.screenshot(path=str(SHOTS / f"106_fight_danger_{vw}x{vh}.png")); fh_end(sp)
        fh_hook(sp, FIGHT_IDS["Legendary"]); fh_hit(sp)
        try: sp.wait_for_function("(() => { const s = fightState(); return s && s.leaping && s.leapP > .05 && s.leapP < .3; })()", timeout=3000, polling=10)
        except Exception: pass
        sp.screenshot(path=str(SHOTS / f"105_fight_leap_{vw}x{vh}.png")); fh_end(sp)
        sp.close()

    # ---------- Playtest 2, part 3: Hold Fight (a player-controlled fight); the classic tap minigame stays as an option ----------
    def hf_page(vw, vh, reduced=False, name="Hold"):
        pg_ = fh_page(vw, vh, reduced=reduced, name=name)                 # fh_page starts a new game (the helper forces "tap")
        pg_.evaluate("() => { S.fightStyle = 'hold'; save(); }")
        return pg_
    hp = hf_page(1536, 730)
    # --- the pure simulation: deterministic for a seed; hold moves the zone right, release moves it left; progress fills inside and drains outside ---
    SIM = """([seed, script]) => { const rng = seededRng(seed), st = fightInit({ personality: 'dash', speed: .5, zoneW: .2, hearts: 2 }, rng), out = [];
        for (let i = 0; i < 600; i++) { stepFight(st, 1 / 60, script(i), rng); if (i % 60 === 0) out.push([st.fx.toFixed(4), st.zx.toFixed(4), st.progress.toFixed(4)]); } return JSON.stringify([out, st.result, st.misses]); }"""
    sim = lambda seed: hp.evaluate("([seed]) => (" + SIM + ")([seed, i => Math.floor(i / 25) % 2 === 0])", [seed])
    a1, a2, b1 = sim(42), sim(42), sim(43)
    check("Hold Fight simulation is deterministic for a given seed (and differs for another seed)", a1 == a2 and a1 != b1, a1[:80])
    mv = hp.evaluate("""() => { const rng = seededRng(1), st = fightInit({ personality: 'steady', speed: 0, zoneW: .2, hearts: 1 }, rng), z0 = st.zx; for (let i = 0; i < 30; i++) stepFight(st, 1 / 60, true, rng);
        const up = st.zx, vup = st.zv; for (let i = 0; i < 120; i++) stepFight(st, 1 / 60, false, rng); const down = st.zx, vdown = st.zv; return { z0, up, vup, down, vdown }; }""")
    check("holding moves the zone right (positive velocity) and releasing moves it back left, with a soft wall at the left end", mv["up"] > mv["z0"] + .1 and mv["vup"] > 0 and mv["down"] < mv["up"] - .1 and mv["down"] >= 0, str(mv))
    pr = hp.evaluate("""() => { const rng = seededRng(1), mk = () => fightInit({ personality: 'steady', speed: 0, zoneW: .2, hearts: 1 }, rng);
        const a = mk(); a.fx = .5; a.zx = .4; a.zv = 0; const p0 = a.progress; for (let i = 0; i < 6; i++) stepFight(a, 1 / 60, true, rng);
        const b = mk(); b.fx = .8; b.zx = 0; b.started = true; const q0 = b.progress; for (let i = 0; i < 6; i++) stepFight(b, 1 / 60, false, rng);
        const c = mk(); c.fx = .8; c.zx = 0; const r0 = c.progress; for (let i = 0; i < 6; i++) stepFight(c, 1 / 60, false, rng);   // not started yet: nothing drains
        return { fill: (a.progress - p0) / (6 / 60), drain: (q0 - b.progress) / (6 / 60), idle: c.progress - r0, HF, dr: DRAIN }; }""")
    check("the catch bar fills while the fish is inside the zone and drains, more slowly, while it is outside (nothing drains before the first contact)",
          abs(pr["fill"] - pr["HF"]["fill"]) < .01 and abs(pr["drain"] - pr["dr"]["Common"]) < .01 and pr["drain"] < pr["fill"] and pr["idle"] == 0, f"fill {pr['fill']:.3f}/s drain {pr['drain']:.3f}/s")
    lim = hp.evaluate("""() => { const rng = seededRng(5), st = fightInit({ personality: 'steady', speed: 0, zoneW: .2, hearts: 1 }, rng); st.fx = .6; let n = 0; while (!st.result && n < 5000) { stepFight(st, 1 / 60, false, rng); n++; } return { result: st.result, reason: st.reason, t: st.t }; }""")
    dr = hp.evaluate("""() => { const out = {}; for (const r of ['Common', 'Rare', 'Epic', 'Legendary', 'Mythical']) { const rng = seededRng(1), b = fightInit({ rarity: r, personality: 'steady', speed: 0, zoneW: .2, hearts: 1 }, rng);
        b.fx = .8; b.zx = 0; b.started = true; const q0 = b.progress; for (let i = 0; i < 6; i++) stepFight(b, 1 / 60, false, rng); out[r] = (q0 - b.progress) / (6 / 60); } return out; }""")
    want = {"Common": .10, "Rare": .15, "Epic": .185, "Legendary": .30, "Mythical": .40}
    check("the catch bar drains at the DRAIN table value of each rarity (Common .10 ... Mythical .40, fill stays .27 for all)", all(abs(dr[k] - v) < .01 for k, v in want.items()) and pr["HF"]["fill"] == .27, str(dr))
    rs = hp.evaluate("""() => { const rng = seededRng(5), st = fightInit({ rarity: 'Rare', personality: 'steady', speed: 0, zoneW: .2, hearts: 9 }, rng); st.fx = .8; st.zx = 0; st.started = true; const seq = [];
        for (let k = 0; k < 7; k++) { st.progress = .001; stepFight(st, 1 / 60, false, rng); seq.push(+st.progress.toFixed(2)); } return { seq, table: RESTORE }; }""")
    check("the restore after each lost heart shrinks (the RESTORE table; the 5th and later all use the last value)", rs["seq"] == [.3, .24, .18, .12, .1, .1, .1] and rs["seq"] == sorted(rs["seq"], reverse=True), str(rs))
    check("the 35 second time limit ends the fight as an escape", lim["result"] == "escaped" and lim["reason"] == "time" and 34.9 < lim["t"] < 35.1, str(lim))
    sl = hp.evaluate("""() => { const rng = seededRng(5), st = fightInit({ personality: 'steady', speed: 0, zoneW: .2, hearts: 1 }, rng); st.fx = .8; st.zx = 0; st.started = true; st.progress = .001; const log = [];
        stepFight(st, 1 / 60, false, rng); log.push([st.misses, +st.progress.toFixed(2), st.result]); st.progress = .001; stepFight(st, 1 / 60, false, rng); log.push([st.misses, st.result, st.reason]); return log; }""")
    check("the bar reaching 0 costs a heart and restores 30% progress; a slip with no hearts left = escape (hearts = misses allowed)", sl[0] == [1, .3, None] and sl[1] == [2, "escaped", "slips"], str(sl))
    # --- gear: hearts = allowedMiss(); Precision zone x1.35; Steady Hands fish x0.8; Lucky Rod fish x1.1; rarer = faster and narrower ---
    gear = {}
    for rid in ("bamboo", "sturdy", "precision", "lucky"):
        gear[rid] = hp.evaluate(f"""() => {{ S.rods = ['bamboo','sturdy','precision','lucky']; S.rodEq = '{rid}'; S.mastery = {{}}; const hold = r => {{ const q = holdParams(r), rod = RODS['{rid}']; return {{ speed: q.speed * rod.speed, zone: q.zone * rod.zone }}; }};
            island = 'harbor'; go('fishing'); F = {{ phase: 'bite', fish: fishById('harbor_0'), castAt: performance.now(), biteAt: performance.now() + 500, land: {{ x: .6, y: .65 }}, usedBait: null, floatId: 'classic' }}; hook();
            const c = F.fight.cfg, base = {{ speed: c.speed, zone: c.zoneW, hearts: c.hearts, allowed: allowedMiss(), mode: F.mode }}; stopFishing(); S.mastery = {{ forest: true, frost: true }}; F = {{ phase: 'bite', fish: fishById('harbor_0'), castAt: performance.now(), biteAt: performance.now() + 500, land: {{ x: .6, y: .65 }}, usedBait: null, floatId: 'classic' }}; hook();
            const c2 = F.fight.cfg, gear = {{ speed: c2.speed, zone: c2.zoneW, hearts: c2.hearts, allowed: allowedMiss() }}; stopFishing(); S.mastery = {{}}; return {{ base, gear }}; }}""")
    hearts_ok = all(g["base"]["hearts"] == g["base"]["allowed"] == n and g["base"]["mode"] == "hold" and g["gear"]["hearts"] == g["gear"]["allowed"] == n + 1 for g, n in zip(gear.values(), (1, 2, 3, 5)))
    check("hearts = allowedMiss(): Bamboo 1, Sturdy 2, Precision 3, Lucky 5, +1 with Master's Charm (read from the real hook)", hearts_ok, str({k: (v["base"]["hearts"], v["gear"]["hearts"]) for k, v in gear.items()}))
    zb, zp = gear["bamboo"]["base"]["zone"], gear["precision"]["base"]["zone"]
    check("Precision Rod zone is 35% wider; Steady Hands makes the fish 20% slower; the Lucky Rod makes it 10% faster",
          abs(zp / zb - 1.35) < 1e-9 and abs(gear["bamboo"]["gear"]["speed"] / gear["bamboo"]["base"]["speed"] - .8) < 1e-9 and abs(gear["lucky"]["base"]["speed"] / gear["bamboo"]["base"]["speed"] - 1.1) < 1e-9, f"zone x{zp / zb:.3f}, frost x{gear['bamboo']['gear']['speed'] / gear['bamboo']['base']['speed']:.2f}, lucky x{gear['lucky']['base']['speed'] / gear['bamboo']['base']['speed']:.2f}")
    prm = hp.evaluate("['Common', 'Rare', 'Epic', 'Legendary', 'Mythical'].map(r => [r, holdParams(r).speed, holdParams(r).zone])")
    check("rarer fish are faster and the zone is narrower: Common .35 / .22 ... Legendary .90 / .14", all(prm[i][1] < prm[i + 1][1] and prm[i][2] > prm[i + 1][2] for i in range(4)) and abs(prm[0][1] - .35) < .01 and abs(prm[0][2] - .22) < .01 and abs(prm[3][1] - .9) < .01 and abs(prm[3][2] - .14) < .01, str([(r, round(s, 2), round(z, 3)) for r, s, z in prm]))
    # --- balance bots (seeded, no real time): good = reacts every 120 ms, bad = every 400 ms, idle = never holds ---
    BOT = """([rarity, bot, n, rodId, frost, forest]) => { const rod = RODS[rodId], hp = holdParams(rarity); let w = 0, tw = 0, tl = 0, sl = 0;
        for (let i = 0; i < n; i++) { const rng = seededRng(9000 + i), st = fightInit({ personality: FIGHT_PERS[rarity], speed: hp.speed * (frost ? .8 : 1) * rod.speed, zoneW: hp.zone * rod.zone, hearts: rod.miss + (forest ? 1 : 0), rarity }, rng);
          let holding = false, next = 0; while (!st.result) { if (bot !== 'idle' && st.t >= next) { next = st.t + (bot === 'good' ? .12 : .4); holding = st.fx > st.zx + st.cfg.zoneW / 2; } stepFight(st, 1 / 60, bot === 'idle' ? false : holding, rng); }
          if (st.result === 'caught') { w++; tw += st.t; } else tl += st.t; sl += st.slips; }
        return { win: w / n * 100, tWin: w ? tw / w : 0, tLoss: n - w ? tl / (n - w) : 0, slips: sl / n }; }"""
    N = 500; bots = {}
    for rar in ("Common", "Rare", "Epic", "Legendary", "Mythical"):
        for bot in ("good", "bad", "idle"): bots[(rar, bot)] = hp.evaluate(BOT, [rar, bot, N, "bamboo", False, False])
    luck = {r: hp.evaluate(BOT, ["Legendary", "good", N, r, False, False]) for r in ("bamboo", "lucky", "sturdy", "precision")}
    luckE = {r: hp.evaluate(BOT, ["Epic", "good", N, r, False, False]) for r in ("bamboo", "lucky", "precision")}
    W = lambda r, b: bots[(r, b)]["win"]
    summary = "good " + "/".join(f"{W(r, 'good'):.0f}" for r in ("Common", "Rare", "Epic", "Legendary", "Mythical")) + "% (C/R/E/L/M), bad " + "/".join(f"{W(r, 'bad'):.0f}" for r in ("Common", "Rare", "Epic", "Legendary", "Mythical")) + "%, idle " + "/".join(f"{W(r, 'idle'):.0f}" for r in ("Common", "Rare", "Epic", "Legendary", "Mythical")) + "%"
    print("BOTS", summary, "| win time s:", {r: round(bots[(r, 'good')]['tWin'], 1) for r in ("Common", "Rare", "Epic", "Legendary")}, "| Legendary good bot by rod:", {k: round(v["win"], 1) for k, v in luck.items()}, "| Epic by rod:", {k: round(v["win"], 1) for k, v in luckE.items()})
    check("balance, good bot (120 ms) on Bamboo: Common >= 95%, Rare >= 80%, Epic >= 55%, Legendary 22-45%, Mythical 10-30% and below Legendary", W("Common", "good") >= 95 and W("Rare", "good") >= 80 and W("Epic", "good") >= 55 and 22 <= W("Legendary", "good") <= 45 and 10 <= W("Mythical", "good") <= 30 and W("Mythical", "good") < W("Legendary", "good"), summary)
    check("balance, bad bot (400 ms) on Bamboo: Rare, Epic, Legendary and Mythical stay low (below 30%); Common stays forgiving", all(W(r, "bad") < 30 for r in ("Rare", "Epic", "Legendary", "Mythical")) and W("Common", "bad") > W("Rare", "bad"), f"{W('Common', 'bad'):.1f}% / {W('Legendary', 'bad'):.1f}%")
    check("balance, idle bot never wins (any rarity)", all(W(r, "idle") == 0 for r in ("Common", "Rare", "Epic", "Legendary", "Mythical")), summary)
    check("balance: Lucky Rod (5 hearts) beats Bamboo by 10+ points on Epic and is not worse on Legendary; Precision is clearly easier on Epic and Legendary", luckE["lucky"]["win"] >= luckE["bamboo"]["win"] + 10 and luck["lucky"]["win"] >= luck["bamboo"]["win"] - 1 and luckE["precision"]["win"] > luckE["bamboo"]["win"] + 20 and luck["precision"]["win"] > luck["bamboo"]["win"] + 15, str({"E": {k: round(v["win"], 1) for k, v in luckE.items()}, "L": {k: round(v["win"], 1) for k, v in luck.items()}}))
    check("balance: a typical fight (good bot, wins) lasts 5 to 25 seconds on every rarity", all(5 <= bots[(r, "good")]["tWin"] <= 25 for r in ("Common", "Rare", "Epic", "Legendary")), str({r: round(bots[(r, 'good')]['tWin'], 1) for r in ("Common", "Rare", "Epic", "Legendary")}))
    # --- the fight on screen: Hold Fight layout, inputs (button, Space, scene), releases ---
    fh_hook(hp, FIGHT_IDS["Common"])
    lay = hp.evaluate("""() => ({ mode: F.mode, hold: document.getElementById('meter').classList.contains('hold'), icon: getComputedStyle(document.getElementById('fishIcon')).display, marker: getComputedStyle(document.getElementById('marker')).display,
        bar: !!document.getElementById('pbar'), dotsText: document.getElementById('dots').textContent, hearts: document.querySelectorAll('#hearts .ico').length, hr: allowedMiss(), cfg: F.fight.cfg.hearts, pers: F.fight.cfg.personality })""")
    check("Hold Fight layout: fish icon and catch bar shown, marker and HIT dots hidden, one heart per allowed miss, personality steady for a Common fish",
          lay["mode"] == "hold" and lay["hold"] and lay["icon"] == "block" and lay["marker"] == "none" and lay["bar"] and "HIT" not in lay["dotsText"] and lay["hearts"] == lay["hr"] == lay["cfg"] and lay["pers"] == "steady", str(lay))
    # --- the fish icon belongs to the fight only: never on the power bar (after a finished fight, after a cancelled fight) ---
    ICON = "() => { const m = document.getElementById('meter'); return { hold: m.classList.contains('hold'), charging: m.classList.contains('charging'), icon: getComputedStyle(document.getElementById('fishIcon')).display, phase: F.phase }; }"
    def charge_state(pg_):
        r = pg_.evaluate("(() => { const r = document.getElementById('actBtn').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
        pg_.mouse.move(r[0], r[1]); pg_.mouse.down(); pg_.wait_for_timeout(600); s = pg_.evaluate(ICON); pg_.evaluate("() => chargeReset(true)"); pg_.mouse.up(); pg_.wait_for_timeout(100); return s
    ic_reel = hp.evaluate(ICON)
    check("the fish icon is visible while reeling a Hold Fight", ic_reel["phase"] == "reeling" and ic_reel["hold"] and ic_reel["icon"] == "block", str(ic_reel))
    fh_end(hp); hp.wait_for_timeout(800)
    ic_end = hp.evaluate(ICON)
    check("after the fight ends the meter loses its hold class and the icon is hidden", not ic_end["hold"] and ic_end["icon"] == "none", str(ic_end))
    hp.wait_for_function("F.phase === 'idle' && !document.getElementById('actBtn').disabled", timeout=5000)
    ic_ch = charge_state(hp)
    check("the power bar after a finished fight shows no fish icon (charging, computed display none)", ic_ch["charging"] and not ic_ch["hold"] and ic_ch["icon"] == "none", str(ic_ch))
    hp.wait_for_timeout(1500)
    fh_hook(hp, FIGHT_IDS["Common"]); hp.evaluate("() => { stopFishing(); renderFishingHud(); }"); hp.wait_for_timeout(300)
    ic_stop = hp.evaluate(ICON)
    ic_ch2 = charge_state(hp)
    check("a cancelled fight (stopFishing) also leaves no icon, and the power bar after it is clean", not ic_stop["hold"] and ic_stop["icon"] == "none" and ic_ch2["charging"] and ic_ch2["icon"] == "none", str([ic_stop, ic_ch2]))
    hp.evaluate("() => { chargeReset(true); }"); hp.wait_for_timeout(1500)
    hp.evaluate("() => { document.getElementById('meter').classList.add('hold'); }")
    ic_cs = charge_state(hp)
    check("starting a charge removes a stale hold class, and CSS hides the icon while charging", ic_cs["charging"] and not ic_cs["hold"] and ic_cs["icon"] == "none", str(ic_cs))
    hp.wait_for_timeout(1500)
    fh_hook(hp, FIGHT_IDS["Common"])
    HS = "() => [HOLD.on, HOLD.src, F.fight.zx, F.fight.zv]"
    def zone_dir(pg_, label, press, release):
        pg_.evaluate("() => { const s = F.fight; s.zx = .3; s.zv = 0; s.started = false; s.progress = .5; s.misses = 0; }"); pg_.wait_for_timeout(30); z0 = pg_.evaluate("F.fight.zx"); press(); pg_.wait_for_timeout(350); on = pg_.evaluate(HS); z1 = pg_.evaluate("F.fight.zx")
        release(); pg_.wait_for_timeout(120); off = pg_.evaluate(HS); pg_.wait_for_timeout(500); z2 = pg_.evaluate("F.fight.zx")
        return on[0] is True and off[0] is False and z1 > z0 + .1 and z2 < z1 - .05, f"{label}: on={on[:2]} zone {z0:.2f}->{z1:.2f}->{z2:.2f} released={not off[0]}"
    bb = hp.evaluate("(() => { const r = document.getElementById('actBtn').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    sc = hp.evaluate("(() => { const r = document.getElementById('scene').getBoundingClientRect(); return [r.left + r.width * .8, r.top + r.height * .3]; })()")
    hp.evaluate("() => { F.fight.progress = .5; }")
    def keep(): hp.evaluate("() => { F.fight.progress = .5; F.fight.misses = 0; }")
    ok1, d1 = zone_dir(hp, "REEL button (mouse)", lambda: (hp.mouse.move(bb[0], bb[1]), hp.mouse.down()), lambda: hp.mouse.up()); keep()
    ok2, d2 = zone_dir(hp, "Space", lambda: hp.keyboard.down("Space"), lambda: hp.keyboard.up("Space")); keep()
    ok3, d3 = zone_dir(hp, "press on the scene", lambda: (hp.mouse.move(sc[0], sc[1]), hp.mouse.down()), lambda: hp.mouse.up()); keep()
    check("the REEL button, the Space key and a press on the scene all hold (the zone rises while held and falls when let go)", ok1 and ok2 and ok3, d1 + " | " + d2 + " | " + d3)
    rel = {}
    hp.mouse.move(bb[0], bb[1]); hp.mouse.down(); hp.wait_for_timeout(80); hp.mouse.move(sc[0], sc[1]); hp.mouse.up(); hp.wait_for_timeout(60); rel["pointerup anywhere"] = hp.evaluate("HOLD.on")
    hp.mouse.move(bb[0], bb[1]); hp.mouse.down(); hp.wait_for_timeout(80); on_before = hp.evaluate("HOLD.on"); hp.evaluate("() => document.dispatchEvent(new PointerEvent('pointercancel', { pointerId: HOLD.pid }))"); hp.wait_for_timeout(60); rel["pointercancel"] = hp.evaluate("HOLD.on"); hp.mouse.up()
    hp.keyboard.down("Space"); hp.wait_for_timeout(80); hp.evaluate("() => window.dispatchEvent(new Event('blur'))"); hp.wait_for_timeout(60); rel["blur"] = hp.evaluate("HOLD.on"); hp.keyboard.up("Space")
    hp.keyboard.down("Space"); hp.wait_for_timeout(80); hp.evaluate("() => { Object.defineProperty(document, 'hidden', { value: true, configurable: true }); document.dispatchEvent(new Event('visibilitychange')); delete document.hidden; }"); hp.wait_for_timeout(60); rel["visibilitychange"] = hp.evaluate("HOLD.on"); hp.keyboard.up("Space")
    hp.keyboard.down("Space"); hp.wait_for_timeout(80); hp.keyboard.press("Escape"); hp.wait_for_timeout(60); rel["Escape"] = hp.evaluate("HOLD.on"); hp.keyboard.up("Space")
    check("the hold is released by pointerup anywhere, pointercancel, blur, visibilitychange and Esc (never stuck)", on_before is True and all(v is False for v in rel.values()), str(rel))
    fh_end(hp)
    check("the hold is gone when the fight ends (escape / leaving the screen)", hp.evaluate("HOLD.on") is False and hp.evaluate("F.phase") == "idle")
    # --- visuals follow the fight: tension, danger, line colour, tick, shadow ---
    hp.evaluate("() => { S.rods = ['bamboo', 'sturdy']; S.rodEq = 'sturdy'; save(); }")
    fh_hook(hp, FIGHT_IDS["Common"])
    PIN = "(v) => { clearInterval(window.__pin); F.fight.cfg.speed = 0; window.__pin = setInterval(() => { if (F.fight) Object.assign(F.fight, v, { zv: 0, started: true }); }, 16); }"        # hold the zone, the fish and the bar still so the state can be read
    hp.evaluate(PIN, {"zx": .5, "fx": .6, "progress": .9}); hp.wait_for_timeout(700); calm = fh_state(hp)
    hp.evaluate(PIN, {"zx": .26, "fx": .9, "progress": .5}); hp.wait_for_timeout(500); far = fh_state(hp)
    check("tension: low while the fish is inside the zone, high when it is far from it (and the reel tick is faster)", calm["tension"] < .45 and far["tension"] > calm["tension"] + .2 and far["tickMs"] < calm["tickMs"] - 50 and not calm["danger"], f"inside {calm['tension']:.2f} ({calm['tickMs']} ms) far {far['tension']:.2f} ({far['tickMs']} ms)")
    hp.evaluate(PIN, {"zx": .5, "fx": .6, "progress": .15}); hp.wait_for_timeout(700); dgr = fh_state(hp)
    check("danger = one heart left or catch progress below 20%; then the line turns warm red", dgr["danger"] and dgr["red"] > .9 and rgb(dgr["line"])[0] - rgb(dgr["line"])[2] > 100, f"danger={dgr['danger']} red={dgr['red']:.2f} {dgr['line']}")
    sdx = []
    for fx in (.3, .9):
        hp.evaluate(PIN, {"zx": .5, "fx": fx, "progress": .5}); hp.wait_for_timeout(250); sdx.append(hp.evaluate("SH.x"))
    check("the fish shadow in the water follows the same fish position (moves right when the fish icon moves right)", sdx[1] > sdx[0] + 40, f"{sdx[0]:.0f} -> {sdx[1]:.0f}")
    hp.evaluate("() => { clearInterval(window.__pin); }"); fh_end(hp)
    # --- personality leaps only for Legendary / Mythical in Hold Fight; the leap and the shadow stay in the water ---
    hp.evaluate("() => { S.rods = ['bamboo', 'sturdy', 'precision', 'lucky']; S.rodEq = 'lucky'; S.mastery = {}; save(); }")
    leaps = {}
    for rar in ("Common", "Legendary"):
        hp.evaluate("() => { S.pending = null; S.bag = []; save(); }")        # a Common fight can be won by the bot: no catch may wait on the Result screen
        fh_hook(hp, FIGHT_IDS[rar]); hp.evaluate("() => { window.__bot = setInterval(() => { const s = F.fight; if (s) holdSet(s.fx > s.zx + s.cfg.zoneW / 2, 'bot'); }, 120); window.__lv = []; window.__ln = 0; window.__lr = true; const f = () => { const q = fightState(); if (q) window.__lv.push([q.leaping, q.lx, q.ly]); if (F.fight) window.__ln = Math.max(window.__ln, F.fight.leapN); if (window.__lr) requestAnimationFrame(f); }; f(); }")
        hp.wait_for_timeout(4500); leaps[rar] = hp.evaluate("() => { window.__lr = false; clearInterval(window.__bot); return [window.__ln, window.__lv.filter(x => x[0]).length, window.__lv.filter(x => x[0])]; }"); fh_end(hp)
    check("Hold Fight personalities: the leap (fish out of the water) happens only for Legendary / Mythical, never for Common", leaps["Common"][0] == 0 and leaps["Common"][1] == 0 and leaps["Legendary"][0] >= 1 and leaps["Legendary"][1] > 3, f"Common {leaps['Common'][:2]} Legendary {leaps['Legendary'][:2]}")
    check("the leap stays in the water area on Harbor", all(.3 <= x[1] <= .92 and .45 <= x[2] <= .9 for x in leaps["Legendary"][2]), str([(round(x[1], 2), round(x[2], 2)) for x in leaps["Legendary"][2][:3]]))
    fr_id = hp.evaluate("FISH.find(f => f.island === 'frost' && f.rarity === 'Legendary').id")
    fh_hook(hp, fr_id, "frost"); hp.evaluate("() => { window.__bot = setInterval(() => { const s = F.fight; if (s) holdSet(s.fx > s.zx + s.cfg.zoneW / 2, 'bot'); }, 120); window.__lp = []; window.__lpr = true; const f = () => { const s = fightState(); window.__lp.push(s ? [s.leaping, SH.x / SH.W, SH.y / SH.H, s.lx, s.ly] : null); if (window.__lpr) requestAnimationFrame(f); }; f(); }")
    hp.wait_for_timeout(5500); hp.evaluate("() => { window.__lpr = false; clearInterval(window.__bot); }"); hp.wait_for_timeout(50)
    lp = [x for x in hp.evaluate("window.__lp") if x]; crop = hp.evaluate("[CROP.sx, CROP.sy, CROP.sw, CROP.sh]")
    pts = [(crop[0] + x[1] * crop[2], crop[1] + x[2] * crop[3]) for x in lp[::6]] + [(crop[0] + x[3] * crop[2], crop[1] + x[4] * crop[3]) for x in lp if x[0]][::4]
    bad = sum(1 for (x, y) in pts if not hp.evaluate(ON_WATER, [MASKS["frost"], x, y]))
    check("Frost: the shadow and the leaping fish stay on the water mask during a Hold Fight", bad == 0 and len(pts) > 12, f"{len(pts)} points, {bad} off water")
    fh_end(hp)
    # --- the same results as tap mode on success and escape (bag, records, island progress, mastery), and the classic tap minigame is unchanged ---
    def finish(pg_, mode, fid, how, isl="harbor"):
        pg_.evaluate(f"() => {{ S.fightStyle = '{mode}'; save(); }}"); fh_hook(pg_, fid, isl)
        info = pg_.evaluate("({ mode: F.mode, hold: document.getElementById('meter').classList.contains('hold'), dots: document.getElementById('dots').textContent, marker: getComputedStyle(document.getElementById('marker')).display })")
        before = pg_.evaluate("() => JSON.stringify({ coins: S.coins, bag: S.bag.length, tc: S.totalCaught, disc: Object.keys(S.discovered).length, rec: Object.keys(S.records).length })")
        if how == "catch":
            if mode == "hold": pg_.evaluate("() => { const s = F.fight; s.cfg.speed = 0; s.fx = .6; s.zx = .5; s.zv = 0; s.progress = .995; s.started = true; }")
            else: pg_.evaluate("() => { F.hits = 2; F.pos = F.zoneX + F.zoneW / 2; reel(); }")
            pg_.wait_for_function("current === 'result'", timeout=6000); pg_.wait_for_timeout(100)
        else:
            if mode == "hold": pg_.evaluate("() => { const s = F.fight; s.cfg.speed = 0; s.fx = .9; s.zx = 0; s.started = true; s.misses = s.cfg.hearts; s.progress = .002; }")
            else: pg_.evaluate("() => { F.misses = allowedMiss(); F.pos = 0; reel(); }")
            pg_.wait_for_function("F.phase === 'idle'", timeout=6000); pg_.wait_for_timeout(100)
        after = pg_.evaluate("() => JSON.stringify({ coins: S.coins, bag: S.bag.length, tc: S.totalCaught, disc: Object.keys(S.discovered).length, rec: Object.keys(S.records).length })")
        pend = pg_.evaluate("() => S.pending && Object.keys(S.pending).sort().join(',')")
        return info, json.loads(before), json.loads(after), pend, pg_.evaluate("current")
    res = {}
    for mode in ("tap", "hold"):
        fpg = hf_page(1536, 730, name="Cmp")
        res[(mode, "catch")] = finish(fpg, mode, "harbor_1", "catch")
        fpg.click("#keepBtn"); fpg.wait_for_timeout(200); res[(mode, "kept")] = fpg.evaluate("() => JSON.stringify({ bag: S.bag.map(b => b.fishId), pend: S.pending })"); fpg.evaluate("() => go('fishing')"); fpg.wait_for_timeout(300)
        res[(mode, "escape")] = finish(fpg, mode, "harbor_3", "escape")
        res[(mode, "prog")] = fpg.evaluate("() => [discCount('harbor'), document.getElementById('isleProg').textContent.includes('1 / 10 found')]")
        fpg.close()
    def delta(r): return (r[2]["tc"] - r[1]["tc"], r[2]["disc"] - r[1]["disc"], r[2]["rec"] - r[1]["rec"], r[2]["bag"] - r[1]["bag"], r[2]["coins"] - r[1]["coins"])
    check("catch result is the same in tap and hold: Result screen, same pending fields, +1 caught, +1 discovered, +1 record, nothing in the bag until KEEP",
          all(res[(m, "catch")][4] == "result" for m in ("tap", "hold")) and res[("tap", "catch")][3] == res[("hold", "catch")][3] and delta(res[("tap", "catch")]) == delta(res[("hold", "catch")]) == (1, 1, 1, 0, 0), f"{delta(res[('tap', 'catch')])} {delta(res[('hold', 'catch')])} {res[('hold', 'catch')][3]}")
    check("KEEP after a Hold Fight catch puts the same fish in the bag as after a tap catch; island progress shows 1 / 10", res[("tap", "kept")] == res[("hold", "kept")] and res[("hold", "prog")] == [1, True] and res[("tap", "prog")] == [1, True], f"{res[('hold', 'kept')][:80]} {res[('hold', 'prog')]}")
    check("escape result is the same in tap and hold: back to idle on the fishing screen, nothing caught, no bag, coin or record change, no pending catch",
          all(res[(m, "escape")][4] == "fishing" for m in ("tap", "hold")) and delta(res[("tap", "escape")]) == delta(res[("hold", "escape")]) == (0, 0, 0, 0, 0) and res[("tap", "escape")][3] is None and res[("hold", "escape")][3] is None, f"{delta(res[('tap', 'escape')])} {delta(res[('hold', 'escape')])}")
    ti, hi = res[("tap", "catch")][0], res[("hold", "catch")][0]
    check("the tap style still runs the classic minigame (marker, HIT dots, no fish icon) and the hold style the new one", ti["mode"] == "tap" and not ti["hold"] and "HIT" in ti["dots"] and ti["marker"] != "none" and hi["mode"] == "hold" and hi["hold"] and "HIT" not in hi["dots"] and hi["marker"] == "none", f"{ti} {hi}")
    # mastery through a Hold Fight catch
    mpg = hf_page(1536, 730, name="Mast")
    mpg.evaluate("() => { for (let i = 0; i < 9; i++) S.discovered['harbor_' + i] = true; save(); }")
    mi = finish(mpg, "hold", "harbor_9", "catch"); mpg.wait_for_timeout(900)
    check("mastery works through a Hold Fight catch (the 10th Harbor fish unlocks Golden Hook)", mpg.evaluate("S.mastery.harbor") is True, str(mpg.evaluate("S.mastery")))
    mpg.close()
    hp.close()
    # --- the setting: default hold, persists, validated, switch in How to Play, tap kept ---
    sp_ = b.new_page(viewport={"width": 1280, "height": 800}); sp_.on("pageerror", lambda e: errs.append(str(e))); sp_.on("console", lambda m: m.type == "error" and errs.append(m.text))
    sp_.goto(URL); sp_.evaluate("localStorage.clear()"); sp_.reload(); sp_.wait_for_timeout(300)
    d0 = sp_.evaluate("[S.fightStyle, DEFAULT_FIGHT, hasSave()]")
    sp_.click("#howBtn"); sp_.wait_for_timeout(150); lbl0 = sp_.inner_text("#fightBtn"); sp_.click("#fightBtn"); sp_.wait_for_timeout(100); lbl1 = sp_.inner_text("#fightBtn")
    stored = sp_.evaluate("localStorage.getItem('littleLakeSave')"); how_text = sp_.inner_text("#howBox")
    check("the fight style defaults to hold, the switch is in How to Play (FIGHT: HOLD / TAP) and it explains both modes", d0 == ["hold", "hold", False] and lbl0 == "FIGHT: HOLD" and lbl1 == "FIGHT: TAP" and "HOLD fight (default)" in how_text and "TAP fight (classic)" in how_text, f"{d0} {lbl0} -> {lbl1}")
    check("changing the style before any game does not count as a game (CONTINUE stays disabled) and is stored", sp_.evaluate("hasSave()") is False and json.loads(stored) == {"sound": True, "music": True, "fightStyle": "tap"}, stored)
    sp_.click("#howOk"); sp_.reload(); sp_.wait_for_timeout(300)
    check("the chosen style persists after a reload", sp_.evaluate("S.fightStyle") == "tap")
    sp_.click("#newBtn"); sp_.fill("#nameInput", "Setting"); sp_.click("#nameStart"); sp_.wait_for_timeout(200)
    saved = sp_.evaluate(SAVED)
    check("NEW GAME keeps the chosen fight style and saves it", saved["fightStyle"] == "tap" and sp_.evaluate("S.fightStyle") == "tap", str(saved.get("fightStyle")))
    vals = sp_.evaluate("""() => { const base = JSON.parse(localStorage.getItem('littleLakeSave')), out = {}; for (const [k, v] of [['missing', undefined], ['junk', 'banana'], ['number', 7], ['null', null], ['hold', 'hold'], ['tap', 'tap']]) {
        const raw = { ...base }; if (v === undefined) delete raw.fightStyle; else raw.fightStyle = v; localStorage.setItem('littleLakeSave', JSON.stringify(raw)); out[k] = load().fightStyle; } return out; }""")
    check("the saved value is validated on load: missing, junk, a number or null load as the default (hold); hold and tap are kept", vals == {"missing": "hold", "junk": "hold", "number": "hold", "null": "hold", "hold": "hold", "tap": "tap"}, str(vals))
    sp_.close()
    # --- reduced motion: no shaking, but the fight is still playable ---
    rmh = hf_page(1536, 730, reduced=True, name="CalmHold")
    fh_hook(rmh, FIGHT_IDS["Legendary"]); rmh.evaluate("() => { const s = F.fight; s.cfg.speed = 0; s.fx = .7; s.zx = .2; s.zv = 0; s.progress = .5; s.started = true; }")
    rmh.keyboard.down("Space"); rmh.wait_for_timeout(450); z_up = rmh.evaluate("F.fight.zx"); st_r = fh_state(rmh); rmh.keyboard.up("Space"); rmh.wait_for_timeout(1100); z_dn = rmh.evaluate("F.fight.zx")
    jit = [rmh.evaluate("[FIGHT.jx, FIGHT.dy, FIGHT.leapP, partCount()]") for _ in range(8) if not rmh.wait_for_timeout(40)]
    check("reduced-motion emulated: the Hold Fight plays the same and the effects are on (the fish leaps, things shake or splash)",
          z_up > .3 and z_dn < z_up - .05 and any(j[0] != 0 or j[1] != 0 or j[2] != -1 or j[3] != 0 for j in jit), f"zone {z_up:.2f} -> {z_dn:.2f}, effects {jit[0]}")
    fh_end(rmh); rmh.close()
    # --- screenshots: Hold Fight mid-fight with a Common fish and with a Legendary fish (1536x730 and 360x640) ---
    for vw, vh in [(1536, 730), (360, 640)]:
        shp = hf_page(vw, vh, name="HoldShots")
        for rar in ("Common", "Legendary"):
            fh_hook(shp, FIGHT_IDS[rar]); shp.evaluate("() => { window.__bot = setInterval(() => { const s = F.fight; if (s) holdSet(s.fx > s.zx + s.cfg.zoneW / 2, 'bot'); }, 120); }")
            if rar == "Legendary":
                try: shp.wait_for_function("(() => { const q = fightState(); return q && q.leaping && q.leapP > .05 && q.leapP < .3; })()", timeout=9000, polling=10)
                except Exception: pass
            else: shp.wait_for_timeout(2200)
            shp.screenshot(path=str(SHOTS / f"107_holdfight_{rar.lower()}_{vw}x{vh}.png"))
            shp.evaluate("() => { clearInterval(window.__bot); }"); fh_end(shp)
        fh_hook(shp, FIGHT_IDS["Common"]); shp.wait_for_timeout(400)
        shp.screenshot(path=str(SHOTS / f"108_reeling_{vw}x{vh}.png")); fh_end(shp)
        shp.wait_for_function("F.phase === 'idle' && !document.getElementById('actBtn').disabled", timeout=5000)
        r_ = shp.evaluate("(() => { const r = document.getElementById('actBtn').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
        shp.mouse.move(r_[0], r_[1]); shp.mouse.down(); shp.wait_for_timeout(600)
        shp.screenshot(path=str(SHOTS / f"109_powerbar_after_fight_{vw}x{vh}.png")); shp.evaluate("() => chargeReset(true)"); shp.mouse.up()
        shp.close()

    # ---------- Playtest 2, part 7: the cast animation follows the charge power (wind-up pose, swing, arc, splash); the wait, bite, hook and reel are unchanged ----------
    cs = fh_page(1536, 730, name="CastAnim")
    ANG = "() => ({ pose: fisherPose(), a: P.a, f: P.f, cs: castState(), phase: F.phase })"
    cast_reset(cs)
    hold_btn(cs, 600); c_lo = cs.evaluate(ANG)
    cs.wait_for_timeout(860); c_hi = cs.evaluate(ANG)                                   # ~1460 ms held: the meter is at (or near) full power
    check("charging pose: while the meter is shown the fisherman is in the 'charging' pose and the rod leans back further as the power grows",
          c_lo["pose"] == c_hi["pose"] == "charging" and c_hi["a"] > c_lo["a"] + 25 and c_hi["a"] > 100 and c_lo["a"] > 38, f"{c_lo['pose']} {c_lo['a']:.0f} deg -> {c_hi['a']:.0f} deg")
    cs.keyboard.press("Escape"); cs.mouse.up(); cs.wait_for_timeout(700)      # the rod eases back to idle (part 7b), about 250-500 ms
    c_end = cs.evaluate(ANG)
    check("a cancelled charge (Esc) throws nothing and the fisherman returns to idle", c_end["phase"] == "idle" and c_end["pose"] == "idle" and c_end["cs"] is None, str(c_end))
    def throw(pg_, power, charged=True):
        cast_reset(pg_); pg_.evaluate(f"() => cast({power}, 0, {'true' if charged else 'false'})")
        s0 = pg_.evaluate("castState()"); pg_.wait_for_function("(castState().u || 0) > .45", timeout=3000); pg_.wait_for_timeout(20)
        s1 = pg_.evaluate("castState()"); pg_.evaluate("() => { stopFishing(); }"); return s0, s1
    wk0, wk1 = throw(cs, 0.0); st0, st1 = throw(cs, 1.0)
    check("swing and flight follow the power: weak = a long gentle swing (350 ms), strong = a short fast one (220 ms), flight 350 > 600 ms, arc higher for the longer throw",
          wk0["swingMs"] == 350 and st0["swingMs"] == 220 and wk0["flightMs"] == 350 and st0["flightMs"] == 600 and st1["arc"] > wk1["arc"] + .03 and 0.08 <= wk1["arc"] <= .4 and st1["arc"] <= .4,
          f"swing {wk0['swingMs']}/{st0['swingMs']} flight {wk0['flightMs']}/{st0['flightMs']} arc {wk1['arc']:.3f}/{st1['arc']:.3f}")
    check("landing time = wind-up + swing + flight stays between 560 and 850 ms for every power (cd)", all(560 <= s["cd"] <= 850 for s in (wk0, st0)), f"{wk0['cd']} / {st0['cd']}")
    cast_reset(cs); cs.click("#actBtn"); cs.wait_for_timeout(60); q0 = cs.evaluate("castState()")
    check("a quick tap is still the medium cast (power .5, 200 ms wind-up, 285 ms swing, not charged)", q0 and q0["pw"] == .5 and q0["windMs"] == 200 and q0["swingMs"] == 285 and not q0["charged"], str(q0))
    cs.evaluate("() => { F.castAt = performance.now() - F.launchMs - F.flightMs; }"); cs.wait_for_timeout(50); q1 = cs.evaluate("castState()")
    check("the bobber ends exactly at F.land (the last frame of the flight)", q1["phase"] in ("casting", "waiting") and abs(q1["bob"]["x"] - q1["land"]["x"]) < 1e-6 and (q1["phase"] == "waiting" or abs(q1["bob"]["y"] - q1["land"]["y"]) < 1e-6), str((q1["bob"], q1["land"], q1["phase"])))
    cs.evaluate("() => { stopFishing(); }")
    # timing after landing is unchanged: waiting starts at castAt + cd, the bite at biteAt (1-5 s after the landing)
    cast_reset(cs); cs.evaluate("() => cast(1, 0, true)")
    cs.wait_for_function("F.phase === 'waiting'", timeout=4000); t_land = cs.evaluate("performance.now() - F.castAt"); cdv = cs.evaluate("F.cd")
    cs.wait_for_function("F.phase === 'bite'", timeout=7000); t_bite = cs.evaluate("performance.now() - F.castAt"); bs = cs.evaluate("F.biteAt - F.castAt")
    check("wait / bite timing relative to the landing is unchanged: waiting starts at the landing (cd), the bite 1-5 s later, at F.biteAt", abs(t_land - cdv) < 120 and 1000 <= bs - cdv <= 5000 and abs(t_bite - bs) < 120, f"landed {t_land:.0f} vs cd {cdv}, bite {t_bite:.0f} vs {bs:.0f}")
    cs.evaluate("() => { stopFishing(); }")
    # Space: hold = charge and throw on release; touch pointer: a long press charges and throws
    cast_reset(cs); cs.keyboard.down("Space"); cs.wait_for_timeout(700); sp1 = cs.evaluate(ANG); cs.keyboard.up("Space"); cs.wait_for_timeout(80); sp2 = cs.evaluate("castState()")
    check("Space: holding charges (charging pose) and releasing throws a charged cast", sp1["pose"] == "charging" and sp2 and sp2["charged"] and sp2["pw"] > 0, f"{sp1['pose']} {sp2 and sp2['pw']}")
    cs.evaluate("() => { stopFishing(); }")
    cast_reset(cs)
    cs.evaluate("() => { const b = document.getElementById('actBtn'), r = b.getBoundingClientRect(), o = { pointerType: 'touch', pointerId: 7, isPrimary: true, bubbles: true, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, button: 0 }; b.dispatchEvent(new PointerEvent('pointerdown', o)); window.__to = o; }")
    cs.wait_for_timeout(700); tp1 = cs.evaluate(ANG)
    cs.evaluate("() => { document.dispatchEvent(new PointerEvent('pointerup', window.__to)); }"); cs.wait_for_timeout(80); tp2 = cs.evaluate("castState()")
    check("touch pointer: a long press charges (charging pose) and the release throws a charged cast", tp1["pose"] == "charging" and tp2 and tp2["charged"], f"{tp1['pose']} {tp2 and tp2['charged']}")
    cs.evaluate("() => { stopFishing(); }")
    # splash size follows the power (the canvas draw is recorded: the biggest ripple radius drawn right after the landing)
    SPL = """(pw) => { const g = cv.getContext('2d'), os = window.splash; let r = [];
        window.splash = function (bx, by, k, W, p) { const o = g.ellipse; g.ellipse = function (...a) { r.push(a[2]); return o.apply(this, a); }; os(bx, by, k, W, p); g.ellipse = o; };
        stopFishing(); island = 'harbor'; go('fishing'); F = { phase: 'waiting', castAt: performance.now() - 700, cd: 600, pw, land: { x: .6, y: .65 }, floatId: 'classic' }; drawScene(performance.now()); window.splash = os; return r[0]; }"""
    rs_weak = cs.evaluate(SPL, 0.0); rs_strong = cs.evaluate(SPL, 1.0)
    cs.evaluate("() => { stopFishing(); }")
    check("the splash ripple is bigger for a strong throw than for a weak one", rs_strong > rs_weak * 1.4, f"{rs_weak:.1f}px vs {rs_strong:.1f}px")
    cs.close()
    # --- screenshots: the full charge pose and the bobber mid-flight (1536x730 and 360x640) ---
    for vw, vh in [(1536, 730), (360, 640)]:
        sp_ = fh_page(vw, vh, name="CastShots"); cast_reset(sp_)
        hold_btn(sp_, 1460); sp_.screenshot(path=str(SHOTS / f"110_charge_pose_{vw}x{vh}.png")); sp_.keyboard.press("Escape"); sp_.mouse.up(); sp_.wait_for_timeout(150)
        sp_.evaluate("() => cast(1, 0, true)"); sp_.wait_for_function("(castState().u || 0) > .4", timeout=3000); sp_.screenshot(path=str(SHOTS / f"111_bobber_flight_{vw}x{vh}.png")); sp_.evaluate("() => stopFishing()")
        sp_.close()

    # ---------- Playtest 2, part 8: the Aquarium (a tank for up to 12 caught fish; cosmetic only) ----------
    def aq_page(vw, vh, name="Tank"):
        pg_ = b.new_page(viewport={"width": vw, "height": vh})
        pg_.on("pageerror", lambda e: errs.append(str(e))); pg_.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg_.goto(URL); pg_.evaluate("localStorage.clear()"); pg_.reload(); pg_.wait_for_timeout(300); start_new(pg_, name)
        pg_.add_style_tag(content="#toast { display: none !important; }")
        return pg_
    FILL = """([n, locked]) => { S.bagMax = 100; S.bag = []; S.tank = []; for (let i = 0; i < n; i++) { const f = FISH[(i * 3) % 40]; S.bag.push({ fishId: f.id, weight: +(f.min + (f.max - f.min) * (i % 5) / 4).toFixed(2), price: f.price, time: 0, locked: locked === i }); } save(); render(); }"""
    ap = aq_page(1536, 730)
    old = ap.evaluate("() => { const o = cleanSave({ coins: 5, bag: [], bagMax: 5 }); return { tank: o.tank, theme: o.tankTheme, d: DEFAULT().tank, dt: DEFAULT().tankTheme }; }")
    check("an old save without tank / tankTheme loads with an empty tank and the theme 'pond'", old["tank"] == [] and old["theme"] == "pond" and old["d"] == [] and old["dt"] == "pond", str(old))
    ap.evaluate("() => { localStorage.setItem('littleLakeSave', JSON.stringify({ name: 'Old', coins: 77, rods: ['bamboo'], rodEq: 'bamboo', bag: [], bagMax: 5 })); }"); ap.reload(); ap.wait_for_timeout(300)
    ol2 = ap.evaluate("() => ({ tank: S.tank, theme: S.tankTheme, coins: S.coins })")
    check("a real old save in localStorage loads without errors (empty tank, pond)", ol2 == {"tank": [], "theme": "pond", "coins": 77}, str(ol2))
    cl = ap.evaluate("""() => { const ok = { fishId: FISH[0].id, weight: 1, price: 5 }, bad = [ok, { ...ok, fishId: 'nope' }, null, 'x', { fishId: FISH[1].id, weight: 'a', price: 1 }, { ...ok, locked: 'yes' }];
        const many = []; for (let i = 0; i < 20; i++) many.push({ ...ok });
        const a = cleanSave({ tank: bad, tankTheme: 'zzz' }), b2 = cleanSave({ tank: many, tankTheme: 'pond' }), c2 = cleanSave({ tank: 'junk', tankTheme: 5 }), d2 = cleanSave({ tank: { a: 1 }, tankTheme: null }), e2 = cleanSave({ tank: [{ ...ok, locked: true }] });
        return { a: a2len(a), at: a.tankTheme, b: b2.tank.length, bt: b2.tankTheme, c: c2.tank, ct: c2.tankTheme, d: d2.tank, dt: d2.tankTheme, lock: e2.tank[0].locked, al: a.tank.map(x => x.locked) };
        function a2len(x) { return x.tank.length; } }""")
    check("invalid tank / theme data is cleaned: unknown fish and junk dropped, cut to 12, bad theme falls back to pond, locked is a real boolean",
          cl["a"] == 2 and cl["at"] == "pond" and cl["b"] == 12 and cl["bt"] == "pond" and cl["c"] == [] and cl["ct"] == "pond" and cl["d"] == [] and cl["dt"] == "pond" and cl["lock"] is True and cl["al"] == [False, False], str(cl))
    check("one TANK_SIZE constant (12) and the TANK_THEMES table (Classic Pond first; the other four came in part 9)",
          ap.evaluate("TANK_SIZE") == 12 and ap.evaluate("Object.keys(TANK_THEMES).join()") == "pond,reef,deep,garden,ship" and ap.evaluate("TANK_THEMES.pond.name") == "Classic Pond")
    # hub button, screen, HOME
    ap.evaluate("() => go('home')"); ap.wait_for_timeout(200)
    check("the hub has an AQUARIUM button", ap.is_visible("#aquariumBtn") and "AQUARIUM" in ap.inner_text("#aquariumBtn"))
    ap.click("#aquariumBtn"); ap.wait_for_timeout(300)
    check("the AQUARIUM button opens the Aquarium screen (with the tank canvas and the counter)", ap.evaluate("current") == "aquarium" and ap.is_visible("#tankCv") and "Tank: 0 / 12" in ap.inner_text("#tankCount"), ap.inner_text("#tankCount"))
    ap.click("#aquarium .btns [data-go=home]"); ap.wait_for_timeout(200)
    check("HOME on the Aquarium goes back to the hub", ap.evaluate("current") == "home")
    # put in / take out, locked fish
    ap.evaluate(FILL, [5, 1]); ap.click("#aquariumBtn"); ap.wait_for_timeout(250)
    ap.locator("#aqLists .btn", has_text="PUT IN TANK").nth(1).click(); ap.wait_for_timeout(100)
    pi = ap.evaluate("() => ({ bag: S.bag.length, tank: S.tank.length, locked: S.tank[0].locked, id: S.tank[0].fishId, saved: JSON.parse(localStorage.getItem('littleLakeSave')).tank.length })")
    check("PUT IN TANK moves a fish from the bag to the tank (not a copy); a locked fish may go in and keeps its lock; saved at once", pi["bag"] == 4 and pi["tank"] == 1 and pi["locked"] is True and pi["saved"] == 1, str(pi))
    check("the counters follow: 'Tank: 1 / 12' and the bag shows 4 / 100", "Tank: 1 / 12" in ap.inner_text("#tankCount") and "4 / 100" in ap.inner_text("#aqLists"))
    ap.locator("#aqLists .btn", has_text="TAKE OUT").first.click(); ap.wait_for_timeout(100)
    to = ap.evaluate("() => ({ bag: S.bag.length, tank: S.tank.length, locked: S.bag.filter(b => b.locked).length })")
    check("TAKE OUT moves the fish back to the bag and it keeps its lock", to == {"bag": 5, "tank": 0, "locked": 1}, str(to))
    # full tank (12) and full bag
    ap.evaluate(FILL, [14, -1]); ap.evaluate("() => { for (let i = 0; i < 12; i++) S.tank.push(S.bag.shift()); save(); render(); }")
    full = ap.evaluate("() => ({ tank: S.tank.length, put: [...document.querySelectorAll('#aqLists .btn')].filter(b => b.textContent === 'PUT IN TANK').map(b => b.disabled), msg: document.getElementById('aqMsg').textContent })")
    check("a full tank (12 / 12): every PUT IN TANK is disabled and the message says 'Tank is full (12/12)'", full["tank"] == 12 and len(full["put"]) == 2 and all(full["put"]) and "Tank is full (12/12)" in full["msg"], str(full))
    ap.evaluate("() => { tankPut(S.bag[0]); }")
    check("tankPut refuses a 13th fish", ap.evaluate("S.tank.length") == 12 and ap.evaluate("S.bag.length") == 2)
    ap.evaluate("() => { S.bagMax = 4; S.tank = S.tank.slice(0, 3); S.bag = []; for (let i = 0; i < 4; i++) S.bag.push({ ...S.tank[0] }); save(); render(); }")
    fb = ap.evaluate("() => ({ take: [...document.querySelectorAll('#aqLists .btn')].filter(b => b.textContent === 'TAKE OUT').map(b => b.disabled), msg: document.getElementById('aqMsg').textContent, t: S.tank.length })")
    check("a full bag: every TAKE OUT is disabled and the message says 'Bag is full'", fb["t"] == 3 and len(fb["take"]) == 3 and all(fb["take"]) and "Bag is full" in fb["msg"], str(fb))
    ap.evaluate("() => { tankTake(S.tank[0]); }")
    check("tankTake refuses while the bag is full", ap.evaluate("S.tank.length") == 3 and ap.evaluate("S.bag.length") == 4)
    # SELL ALL leaves the tank untouched, the economy is unchanged
    ap.evaluate(FILL, [4, -1]); ap.evaluate("() => { for (let i = 0; i < 3; i++) S.tank.push(S.bag.shift()); S.coins = 0; save(); render(); }")
    pre = ap.evaluate("() => ({ tank: JSON.stringify(S.tank), worth: S.bag.reduce((a, b) => a + b.price, 0), found: Object.keys(S.discovered).length, coins: S.coins })")
    ap.evaluate("() => go('bag')"); ap.click("#sellAll"); ap.wait_for_timeout(200)
    post = ap.evaluate("() => ({ tank: JSON.stringify(S.tank), bag: S.bag.length, coins: S.coins, found: Object.keys(S.discovered).length })")
    check("SELL ALL never touches the fish in the tank, and the money is only from the bag (no tank bonus)", post["tank"] == pre["tank"] and post["bag"] == 0 and post["coins"] == pre["worth"] and post["found"] == pre["found"], f"{pre['worth']} vs {post['coins']}")
    # reload keeps the tank, NEW GAME clears it
    ap.evaluate("() => { go('home'); }"); ap.reload(); ap.wait_for_timeout(300)
    rl = ap.evaluate("() => ({ tank: S.tank.length, theme: S.tankTheme })")
    check("the tank survives a reload", rl["tank"] == 3 and rl["theme"] == "pond", str(rl))
    ap.evaluate("() => { S.tankTheme = 'pond'; save(); }")
    ap.click("#newBtn"); ap.click("#confirmYes"); ap.fill("#nameInput", "Fresh"); ap.click("#nameStart"); ap.wait_for_timeout(300)
    nw = ap.evaluate("() => ({ tank: S.tank, theme: S.tankTheme, saved: JSON.parse(localStorage.getItem('littleLakeSave')).tank })")
    check("NEW GAME clears the tank and resets the theme", nw == {"tank": [], "theme": "pond", "saved": []}, str(nw))
    # swimming, turning at the edges, tap a fish, the loop only runs on this screen
    ap.evaluate(FILL, [8, -1]); ap.evaluate("() => { while (S.tank.length < 8) S.tank.push(S.bag.shift()); save(); go('aquarium'); }"); ap.wait_for_timeout(500)
    s0 = ap.evaluate("tankState()"); ap.wait_for_timeout(900); s1 = ap.evaluate("tankState()")
    check("the loop runs on the Aquarium screen and 8 fish swim (positions change, different depths)", s0["on"] and s0["raf"] and len(s0["fish"]) == 8 and sum(abs(a["x"] - c["x"]) > .5 for a, c in zip(s0["fish"], s1["fish"])) >= 6 and len({round(f["y"] / 6) for f in s1["fish"]}) >= 4, f"{s0['on']} {len(s0['fish'])}")
    ap.evaluate("() => { TK.sim[0].u = .9995; TK.sim[0].dir = 1; }"); ap.wait_for_timeout(200); ed = ap.evaluate("tankState().fish[0].dir")
    check("a fish turns (mirrors) at the edge of the tank", ed == -1, str(ed))
    pos = ap.evaluate("() => { const s = TK.sim[2], r = document.getElementById('tankCv').getBoundingClientRect(); return [r.left + s.x * TANK_SCALE, r.top + s.y * TANK_SCALE, s.f.name]; }")
    ap.mouse.click(pos[0], pos[1]); ap.wait_for_timeout(120); tp = ap.evaluate("tankState().tip")
    check("tapping a swimming fish shows its name and rarity for a moment", tp is not None and pos[2] in tp, f"{tp} / {pos[2]}")
    ap.wait_for_timeout(2600); check("the name label goes away again", ap.evaluate("tankState().tip") is None)
    ap.evaluate("() => go('home')"); ap.wait_for_timeout(100); sa = ap.evaluate("tankState()"); ap.wait_for_timeout(400); sb = ap.evaluate("tankState()")
    check("leaving the screen stops the animation loop (no requestAnimationFrame, positions frozen)", not sa["on"] and not sa["raf"] and all(abs(x["x"] - y["x"]) < .001 for x, y in zip(sa["fish"], sb["fish"])), str(sa["on"]))
    ap.evaluate("() => go('aquarium')"); ap.wait_for_timeout(200); check("and it starts again when the screen is opened", ap.evaluate("tankState().on"))
    ap.close()
    # fit: no page scroll on wide windows, no sideways scroll on phones; screenshots
    for vw, vh in [(1920, 915), (1536, 730), (1366, 625), (1280, 600), (360, 640)]:
        ap = aq_page(vw, vh, "Fit"); ap.evaluate(FILL, [14, -1]); ap.evaluate("() => { for (let i = 0; i < 8; i++) S.tank.push(S.bag.shift()); save(); go('aquarium'); }"); ap.wait_for_timeout(700)
        m = ap.evaluate("() => ({ sh: document.documentElement.scrollHeight, ih: innerHeight, sw: document.documentElement.scrollWidth, tank: document.getElementById('tankCv').getBoundingClientRect().height, tw: document.getElementById('tankCv').getBoundingClientRect().width })")
        check(f"{vw}x{vh}: the Aquarium has no sideways scroll" + (" and fits the window without page scroll" if vw >= 900 else "") + " (tank is big)", m["sw"] <= vw and (vw < 900 or m["sh"] <= m["ih"]) and m["tank"] >= (150 if vw < 900 else 250) and m["tw"] >= (260 if vw < 900 else 500), str(m))
        if (vw, vh) in [(1536, 730), (360, 640)]:
            ap.screenshot(path=str(SHOTS / f"112_aquarium_{vw}x{vh}.png"))
            ap.evaluate("() => go('home')"); ap.wait_for_timeout(300)
            hm = ap.evaluate("() => ({ sh: document.documentElement.scrollHeight, ih: innerHeight, sw: document.documentElement.scrollWidth })")
            check(f"{vw}x{vh}: the hub with the AQUARIUM button has no sideways scroll" + (" and no page scroll" if vw >= 900 else ""), hm["sw"] <= vw and (vw < 900 or hm["sh"] <= hm["ih"]), str(hm))
            ap.screenshot(path=str(SHOTS / f"113_hub_aquarium_{vw}x{vh}.png"))
        elif vw >= 900:
            ap.evaluate("() => go('home')"); ap.wait_for_timeout(300)
            hm = ap.evaluate("() => ({ sh: document.documentElement.scrollHeight, ih: innerHeight })"); check(f"{vw}x{vh}: the hub with the AQUARIUM button fits without page scroll", hm["sh"] <= hm["ih"], str(hm))
        ap.close()

    # ---------- Playtest 2, part 7b: smooth charging pose (ease-in, inertia, ease-out) ----------
    sm = fh_page(1536, 730, name="SmoothCharge")
    SAMPLE = """() => { window.__ca = []; window.__cr = true; const f = t => { window.__ca.push({ t, pose: fisherPose(), a: P.a, sa: CHARGE_POSE.a, phase: F.phase }); if (window.__cr) requestAnimationFrame(f); }; requestAnimationFrame(f); }"""
    def sample_start(pg_): pg_.evaluate(SAMPLE)
    def sample_stop(pg_): pg_.evaluate("() => { window.__cr = false; }"); pg_.wait_for_timeout(50); return pg_.evaluate("window.__ca")
    def max_jump(fr, ok_pair):
        """largest change of the drawn rod angle between two consecutive frames, counting only the pairs ok_pair(prev, cur) accepts"""
        return max([abs(b["a"] - a["a"]) for a, b in zip(fr, fr[1:]) if ok_pair(a, b)] or [0])
    SMOOTH = lambda a, b: a["pose"] in ("idle", "charging") and b["pose"] in ("idle", "charging") or (a["pose"] == "charging" and b["pose"] == "casting")
    def hold_run(pg_, ms, how):
        """how = 'release' (let go: a charged cast) or 'cancel' (Esc); returns the frames"""
        cast_reset(pg_); sample_start(pg_); pg_.wait_for_timeout(300)
        x, y = center(pg_, "#actBtn"); pg_.mouse.move(x, y); pg_.mouse.down(); pg_.wait_for_timeout(ms)
        if how == "release": pg_.mouse.up(); pg_.wait_for_timeout(500)
        else: pg_.keyboard.press("Escape"); pg_.mouse.up(); pg_.wait_for_timeout(700)
        fr = sample_stop(pg_); pg_.evaluate("() => { stopFishing(); }"); return fr
    # a hold to full power (the meter fills at 1.45 s, then ping-pongs back: the turnaround is inside the hold), released into a cast
    fr_full = hold_run(sm, 1900, "release")
    jf = max_jump(fr_full, SMOOTH); ch = [f for f in fr_full if f["pose"] == "charging"]
    check("smooth charge: no jump bigger than 3 degrees between two frames - idle to charging, the whole hold to full power incl. the ping-pong turnaround, and charging to the swing",
          len(ch) > 60 and jf <= 3.0 and max(f["a"] for f in ch) > 100 and any(f["pose"] == "casting" for f in fr_full), f"max jump {jf:.2f} deg over {len(ch)} charging frames, peak {max(f['a'] for f in ch):.0f}")
    t0 = next(f["t"] for f in fr_full if f["pose"] == "charging"); early = [f for f in fr_full if f["pose"] == "charging" and f["t"] - t0 < 400]
    check("ease-in: the rod starts at the idle angle (38 deg) and travels back gradually (not at the target at the first frame)", abs(early[0]["a"] - 38) < 1.5 and early[-1]["a"] > early[0]["a"] + 5, f"{early[0]['a']:.1f} -> {early[-1]['a']:.1f}")
    # a hold-release at mid power
    fr_mid = hold_run(sm, 850, "release"); jm = max_jump(fr_mid, SMOOTH)
    check("smooth charge: a hold released at mid power has no jump either (charge to swing)", jm <= 3.0 and any(f["pose"] == "casting" for f in fr_mid), f"max jump {jm:.2f} deg")
    # a cancel: eases back to idle, then the idle pose
    fr_can = hold_run(sm, 900, "cancel"); jc = max_jump(fr_can, SMOOTH)
    last_ch = max(i for i, f in enumerate(fr_can) if f["pose"] == "charging")
    check("ease-out: a cancelled charge (Esc) stays in the charging pose while the rod eases back (no jump above 5.5 degrees per frame), then ends in the idle pose with the idle angle",
          jc <= 5.5 and fr_can[-1]["pose"] == "idle" and abs(fr_can[-1]["a"] - 38) < 1 and fr_can[-1]["phase"] == "idle" and sum(1 for f in fr_can if f["pose"] == "charging") > 40,
          f"max jump {jc:.2f}, final {fr_can[-1]['pose']} {fr_can[-1]['a']:.1f}")
    # convergence at a constant power, tremble only at high power
    cast_reset(sm); sm.evaluate("() => { window.chargePower = () => .8; }")
    x, y = center(sm, "#actBtn"); sm.mouse.move(x, y); sm.mouse.down(); sm.wait_for_timeout(1500)
    conv = sm.evaluate("() => { const a = []; for (let i = 0; i < 1; i++) a.push(CHARGE_POSE.a); return { shown: CHARGE_POSE.a, target: chargeBackAngle(.8) }; }")
    trem = sm.evaluate("""() => new Promise(res => { const v = []; let n = 0; const f = () => { v.push(P.a - CHARGE_POSE.a); if (++n < 40) requestAnimationFrame(f); else res(v); }; requestAnimationFrame(f); })""")
    sm.evaluate("() => { window.chargePower = () => .3; }"); sm.wait_for_timeout(900)
    trem_lo = sm.evaluate("""() => new Promise(res => { const v = []; let n = 0; const f = () => { v.push(P.a - CHARGE_POSE.a); if (++n < 30) requestAnimationFrame(f); else res(v); }; requestAnimationFrame(f); })""")
    sm.keyboard.press("Escape"); sm.mouse.up(); sm.wait_for_timeout(600); sm.evaluate("() => { delete window.chargePower; }")
    check("the shown angle converges to the target when the power is constant (.8 -> chargeBackAngle(.8))", abs(conv["shown"] - conv["target"]) < 1.0, str(conv))
    check("a slight rod tremble at high power (within +-0.6 deg) and none below power .5", .1 < max(abs(v) for v in trem) <= .62 and max(abs(v) for v in trem_lo) < .01, f"high {max(abs(v) for v in trem):.2f}, low {max(abs(v) for v in trem_lo):.3f}")
    # the swing starts from the shown angle
    cast_reset(sm); x, y = center(sm, "#actBtn"); sm.mouse.move(x, y); sm.mouse.down(); sm.wait_for_timeout(900)
    sw = sm.evaluate("() => { const a = CHARGE_POSE.a, b = CHARGE_POSE.b; chargeEnd(); return { shown: a, a0: CAST.a0, a1: CAST.a1, b: b, b0: CAST.b0, live: CHARGE_POSE.live, pose: fisherPoseFor(F.phase, performance.now()) }; }"); sm.mouse.up()
    check("the swing starts from the SHOWN angle (CAST.a0 = the shown angle at release), the charge pose ends and the cast pose takes over", abs(sw["shown"] - sw["a0"]) < .01 and abs(sw["a0"] - sw["a1"]) < .01 and abs(sw["b"] - sw["b0"]) < .01 and not sw["live"] and sw["pose"] == "casting", str(sw))
    sm.evaluate("() => stopFishing()")
    # quick tap, Space and touch are unchanged
    cast_reset(sm); sm.click("#actBtn"); sm.wait_for_timeout(60); q = sm.evaluate("castState()")
    check("a quick tap is still the medium cast (no charging pose, 200 ms wind-up)", q and q["pw"] == .5 and not q["charged"] and q["windMs"] == 200 and not sm.evaluate("CHARGE_POSE.live"), str(q))
    sm.evaluate("() => stopFishing()"); cast_reset(sm); sm.keyboard.down("Space"); sm.wait_for_timeout(700); sp1 = sm.evaluate("fisherPose()"); sm.keyboard.up("Space"); sm.wait_for_timeout(80); sp2 = sm.evaluate("castState()")
    check("Space still charges (charging pose) and throws a charged cast", sp1 == "charging" and sp2 and sp2["charged"], f"{sp1} {sp2 and sp2['charged']}")
    sm.evaluate("() => stopFishing()"); cast_reset(sm)
    sm.evaluate("() => { const b = document.getElementById('actBtn'), r = b.getBoundingClientRect(), o = { pointerType: 'touch', pointerId: 7, isPrimary: true, bubbles: true, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, button: 0 }; b.dispatchEvent(new PointerEvent('pointerdown', o)); window.__to = o; }")
    sm.wait_for_timeout(700); tp1 = sm.evaluate("fisherPose()"); sm.evaluate("() => { document.dispatchEvent(new PointerEvent('pointerup', window.__to)); }"); sm.wait_for_timeout(80); tp2 = sm.evaluate("castState()")
    check("a touch long press still charges and throws a charged cast", tp1 == "charging" and tp2 and tp2["charged"], f"{tp1} {tp2 and tp2['charged']}")
    sm.evaluate("() => stopFishing()"); cast_reset(sm)
    x, y = center(sm, "#actBtn"); sm.mouse.move(x, y); sm.mouse.down(); sm.wait_for_timeout(1500); sm.screenshot(path=str(SHOTS / "114_charge_smooth_1536x730.png")); sm.keyboard.press("Escape"); sm.mouse.up()
    sm.close()

    # ---------- Playtest 2, part 9: tank themes and decorations sold in the shop and applied in the Aquarium (cosmetic only) ----------
    tp = aq_page(1536, 730, "Themer")
    tbl = tp.evaluate("() => ({ th: TANK_THEME_IDS.map(i => [i, TANK_THEMES[i].price]), de: TANK_DECO_IDS.map(i => [i, TANK_DECOS[i].price]), max: TANK_DECO_MAX, d: DEFAULT(), key: Object.keys(TANK_THEMES).join() })")
    check("data tables: Classic Pond free, Coral Reef 400, Deep Sea 600, Japanese Garden 800, Sunken Ship 1000; Treasure Chest 150, Anchor 120, Castle 250, Big Coral 200, Bubble Maker 180; max 4 shown",
          tbl["th"] == [["pond", 0], ["reef", 400], ["deep", 600], ["garden", 800], ["ship", 1000]] and tbl["de"] == [["chest", 150], ["anchor", 120], ["castle", 250], ["bigcoral", 200], ["bubbler", 180]] and tbl["max"] == 4, str(tbl["th"]) + str(tbl["de"]))
    d0 = tbl["d"]
    check("a new game starts with only the Classic Pond owned and in use, and no decorations", d0["tankThemes"] == ["pond"] and d0["tankTheme"] == "pond" and d0["tankDecos"] == [] and d0["tankDecoOn"] == [], str((d0["tankThemes"], d0["tankTheme"])))
    ol = tp.evaluate("() => { const o = cleanSave({ coins: 5, tank: [], bagMax: 5 }); return [o.tankThemes, o.tankTheme, o.tankDecos, o.tankDecoOn]; }")
    check("an old save (no theme or decoration fields) loads with the defaults", ol == [["pond"], "pond", [], []], str(ol))
    cl = tp.evaluate("""() => { const a = cleanSave({ tankThemes: ['reef', 'nope', 'reef', 5, null], tankTheme: 'reef', tankDecos: ['chest', 'zzz', 'chest', 'castle'], tankDecoOn: ['castle', 'anchor', 'chest', 'chest'] }),
        b = cleanSave({ tankThemes: ['pond'], tankTheme: 'ship', tankDecos: TANK_DECO_IDS, tankDecoOn: TANK_DECO_IDS }), c = cleanSave({ tankThemes: 'junk', tankTheme: 7, tankDecos: { a: 1 }, tankDecoOn: 'x' }), d = cleanSave({ tankThemes: ['deep'], tankTheme: 'deep' });
        return { a: [a.tankThemes, a.tankTheme, a.tankDecos, a.tankDecoOn], b: [b.tankTheme, b.tankDecoOn], c: [c.tankThemes, c.tankTheme, c.tankDecos, c.tankDecoOn], d: d.tankThemes }; }""")
    check("saves are cleaned: unknown ids and duplicates dropped, the Classic Pond always owned, the theme in use must be owned, only owned decorations can be shown, at most 4 shown",
          cl["a"] == [["pond", "reef"], "reef", ["chest", "castle"], ["castle", "chest"]] and cl["b"] == ["pond", ["chest", "anchor", "castle", "bigcoral"]] and cl["c"] == [["pond"], "pond", [], []] and cl["d"] == ["pond", "deep"], str(cl))
    # the shop section
    tp.evaluate("() => { S.coins = 0; save(); go('shop'); }"); tp.wait_for_timeout(300)
    sh0 = tp.evaluate("""() => { const q = s => [...document.querySelectorAll(s)], heads = q('#shop .shop-h').map(h => h.firstChild.textContent.trim());
        const px = (id) => new Promise(r => { const im = new Image(); im.onload = () => { const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; const x = c.getContext('2d'); x.drawImage(im, 0, 0); const p = [[0, 0], [10, 0], [20, 2], [55, 1], [71, 2]].map(a => [...x.getImageData(a[0], a[1], 1, 1).data].slice(0, 3).join()); r(p); }; im.src = tankThumb('deco', id); });
        return Promise.all(TANK_DECO_IDS.map(px)).then(dp => ({ heads, themes: q('#shopThemes .item').length, decos: q('#shopDecos .item').length, tn: q('#shopThemes .item b').map(b => b.textContent.trim()), dn: q('#shopDecos .item b').map(b => b.textContent.trim()),
          tagsD: q('#shopDecos .item .kind').map(k => k.textContent), tagsT: q('#shopThemes .item .kind').length, imgs: q('#shopThemes .tkthumb, #shopDecos .tkthumb').map(i => i.naturalWidth), btns: q('#shopThemes .btn, #shopDecos .btn').map(b => [b.textContent, b.disabled]), dp, panel: TK_PANEL })); }""")
    check("the Shop has two sections 'Tank Themes' and 'Tank Decorations' and no single 'Aquarium' heading; 5 themes + 5 decorations, each with a drawn thumbnail; no coins = every BUY disabled (the Classic Pond is IN USE)",
          "Tank Themes" in sh0["heads"] and "Tank Decorations" in sh0["heads"] and "Aquarium" not in sh0["heads"] and sh0["themes"] == 5 and sh0["decos"] == 5 and all(w > 0 for w in sh0["imgs"]) and len(sh0["imgs"]) == 10 and sh0["btns"][0] == ["IN USE", True] and all(b[1] for b in sh0["btns"]), str(sh0["heads"]) + str(sh0["btns"][:3]))
    check("theme card names contain 'Theme' (Coral Reef Theme, Classic Pond Theme); decoration cards have the DECOR tag and theme cards do not", all("Theme" in n for n in sh0["tn"]) and "Coral Reef Theme" in sh0["tn"] and "Classic Pond Theme" in sh0["tn"] and sh0["tagsD"] == ["DECOR"] * 5 and sh0["tagsT"] == 0 and not any("Theme" in n for n in sh0["dn"]), str(sh0["tn"]) + str(sh0["dn"]))
    pc = {"#245a8c": "36,90,140"}
    check("decoration thumbnails do not draw the tank background: pixels along the top are exactly the plain panel colour", all(set(p) == {pc[sh0["panel"]]} for p in sh0["dp"]), str(sh0["dp"]))
    tp.evaluate("() => { S.coins = 5000; save(); render(); }")
    c0 = tp.evaluate("S.coins"); tp.locator("#shopThemes [data-buy='theme:reef']").click(); tp.wait_for_timeout(150)
    b1 = tp.evaluate("() => ({ coins: S.coins, own: S.tankThemes, use: S.tankTheme, saved: JSON.parse(localStorage.getItem('littleLakeSave')).tankThemes })")
    check("buying Coral Reef deducts 400 coins, adds it to the owned themes, uses it at once (like a float) and saves", b1["coins"] == c0 - 400 and b1["own"] == ["pond", "reef"] and b1["use"] == "reef" and b1["saved"] == ["pond", "reef"], str(b1))
    again = tp.evaluate("() => { const c = S.coins; buyTheme('reef'); return [c, S.coins, S.tankThemes.length]; }")
    dis = tp.evaluate("document.querySelector(\"#shopThemes [data-buy='theme:reef']\").disabled")
    check("a theme cannot be bought twice (button disabled, the function refuses, no coins lost)", again[0] == again[1] and again[2] == 2 and dis is True, str(again))
    tp.evaluate("() => { S.coins = 799; save(); render(); }")
    poor = tp.evaluate("() => { buyTheme('garden'); return [S.coins, S.tankThemes.length, document.querySelector(\"#shopThemes [data-buy='theme:garden']\").disabled, document.querySelector('#shopThemes .need') && true]; }")
    check("not enough coins (799 of 800): the BUY button is disabled with 'Need N more coins', and buying anyway changes nothing", poor[0] == 799 and poor[1] == 2 and poor[2] is True and poor[3], str(poor))
    tp.evaluate("() => { S.coins = 5000; save(); render(); }")
    for did in ["chest", "anchor", "castle", "bigcoral", "bubbler"]: tp.locator(f"#shopDecos [data-buy='deco:{did}']").click(); tp.wait_for_timeout(80)
    dc = tp.evaluate("() => ({ coins: S.coins, own: S.tankDecos, on: S.tankDecoOn })")
    check("buying the 5 decorations costs 150+120+250+200+180 coins; the first 4 are shown at once, the 5th is owned but not shown (max 4)", dc["coins"] == 5000 - 900 and dc["own"] == ["chest", "anchor", "castle", "bigcoral", "bubbler"] and dc["on"] == ["chest", "anchor", "castle", "bigcoral"], str(dc))
    tp.evaluate("() => { S.coins = 0; save(); }"); tp.reload(); tp.wait_for_timeout(300)
    rl = tp.evaluate("() => ({ th: S.tankThemes, use: S.tankTheme, de: S.tankDecos, on: S.tankDecoOn })")
    check("owned themes and decorations, the theme in use and the shown decorations survive a reload", rl == {"th": ["pond", "reef"], "use": "reef", "de": ["chest", "anchor", "castle", "bigcoral", "bubbler"], "on": ["chest", "anchor", "castle", "bigcoral"]}, str(rl))
    # the Aquarium: tabs, using a theme, switching decorations, max 4
    tp.evaluate("() => go('aquarium')"); tp.wait_for_timeout(300)
    tp.click("#aqTabs [data-tab=theme]"); tp.wait_for_timeout(100)
    th = tp.evaluate("() => ({ names: [...document.querySelectorAll('#aqLists .row b')].map(b => b.textContent), btns: [...document.querySelectorAll('#aqLists .row .btn')].map(b => b.textContent), tab: document.querySelector('#aqTabs .tab.on').dataset.tab })")
    check("THEME tab: only owned themes are listed (Classic Pond, Coral Reef), the one in use is marked", th["names"] == ["Classic Pond Theme", "Coral Reef Theme"] and th["btns"] == ["USE", "IN USE"] and th["tab"] == "theme", str(th))
    tp.locator("#aqLists .row .btn").first.click(); tp.wait_for_timeout(100)
    check("tapping a theme uses it at once (S.tankTheme and the saved value change)", tp.evaluate("S.tankTheme") == "pond" and tp.evaluate("JSON.parse(localStorage.getItem('littleLakeSave')).tankTheme") == "pond")
    nu = tp.evaluate("() => { tankUse('ship'); return S.tankTheme; }")
    check("a theme that is not owned cannot be used", nu == "pond")
    tp.click("#aqTabs [data-tab=decor]"); tp.wait_for_timeout(100)
    dl = tp.evaluate("() => ({ names: [...document.querySelectorAll('#aqLists .row b')].map(b => b.textContent), btns: [...document.querySelectorAll('#aqLists .row .btn')].map(b => b.textContent), msg: document.getElementById('aqMsg').textContent })")
    check("DECOR tab: all 5 owned decorations are listed (with the DECOR tag), 4 ON and 1 OFF, and the message says 'Max 4 decorations'", len(dl["names"]) == 5 and tp.evaluate("document.querySelectorAll('#aqLists .row .kind').length") == 5 and dl["btns"] == ["ON", "ON", "ON", "ON", "OFF"] and "Max 4 decorations" in dl["msg"], str(dl))
    tp.locator("#aqLists .row .btn").nth(4).click(); tp.wait_for_timeout(100)
    mx = tp.evaluate("() => ({ on: S.tankDecoOn.length, msg: document.getElementById('aqMsg').textContent })")
    check("switching a 5th decoration on is refused with 'Max 4 decorations'", mx["on"] == 4 and "Max 4 decorations" in mx["msg"], str(mx))
    tp.locator("#aqLists .row .btn").nth(0).click(); tp.wait_for_timeout(100); tp.locator("#aqLists .row .btn").nth(4).click(); tp.wait_for_timeout(100)
    sw = tp.evaluate("S.tankDecoOn")
    check("switching one off makes room: the Bubble Maker can then be switched on (changes apply at once and are saved)", sw == ["anchor", "castle", "bigcoral", "bubbler"] and tp.evaluate("JSON.parse(localStorage.getItem('littleLakeSave')).tankDecoOn") == sw, str(sw))
    tp.click("#aqTabs [data-tab=fish]"); tp.wait_for_timeout(100)
    check("the FISH tab still lists the tank and the bag (PUT IN TANK / TAKE OUT work as before)", "In the tank" in tp.inner_text("#aqLists") and tp.evaluate("tankState().on"))
    # drawing: every theme and every decoration on a canvas, not blank, no errors
    DRAW = """() => { const out = {}, mk = () => { const cv = document.createElement('canvas'); cv.width = 240; cv.height = 140; return cv; };
        const sig = cv => { const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data, set = new Set(); let r = 0, g = 0, b = 0, n = 0; for (let i = 0; i < d.length; i += 4) { set.add((d[i] >> 4) * 256 + (d[i + 1] >> 4) * 16 + (d[i + 2] >> 4)); r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; } return { colors: set.size, avg: [r / n, g / n, b / n].map(Math.round) }; };
        const fish = [0, 3, 7].map((k, i) => { const f = FISH[k * 5]; return { x: 60 + i * 50, y: 40 + i * 12, dir: i % 2 ? -1 : 1, w: 36, h: 24, spr: fishSprite(f), bobS: .002, ph: i }; });
        for (const th of TANK_THEME_IDS) { const cv = mk(); drawTank(cv.getContext('2d'), 240, 140, 2300, th, TANK_DECO_IDS, fish); out[th] = sig(cv); }
        const base = mk(); drawTank(base.getContext('2d'), 240, 140, 2300, 'pond', [], []); const bd = base.getContext('2d').getImageData(0, 0, 240, 140).data; out.decos = {};
        for (const de of TANK_DECO_IDS) { const cv = mk(); drawTank(cv.getContext('2d'), 240, 140, 2300, 'pond', [de], []); const d = cv.getContext('2d').getImageData(0, 0, 240, 140).data; let diff = 0; for (let i = 0; i < d.length; i += 4) if (d[i] !== bd[i] || d[i + 1] !== bd[i + 1] || d[i + 2] !== bd[i + 2]) diff++; out.decos[de] = diff; }
        const t1 = mk(), t2 = mk(); drawTank(t1.getContext('2d'), 240, 140, 0, 'deep', [], []); drawTank(t2.getContext('2d'), 240, 140, 3000, 'deep', [], []); const a = t1.getContext('2d').getImageData(0, 0, 240, 140).data, b = t2.getContext('2d').getImageData(0, 0, 240, 140).data; let mv = 0; for (let i = 0; i < a.length; i += 4) if (a[i] !== b[i]) mv++; out.moves = mv;
        out.thumbs = [...TANK_THEME_IDS.map(i => tankThumb('theme', i)), ...TANK_DECO_IDS.map(i => tankThumb('deco', i))].map(u => u.length); return out; }"""
    dr = tp.evaluate(DRAW)
    check("drawTank paints every theme with every decoration and fish: not blank (many colours) and each theme has its own average colour",
          all(dr[t]["colors"] > 25 for t in ("pond", "reef", "deep", "garden", "ship")) and len({tuple(dr[t]["avg"]) for t in ("pond", "reef", "deep", "garden", "ship")}) == 5, str({t: (dr[t]["colors"], dr[t]["avg"]) for t in ("pond", "reef", "deep", "garden", "ship")}))
    check("every decoration is drawn (it changes the pixels of an empty pond) and the animated themes move over time", all(v > 40 for v in dr["decos"].values()) and dr["moves"] > 100 and all(n > 100 for n in dr["thumbs"]), str(dr["decos"]) + f" moves={dr['moves']}")
    # the decorations stand at their own slots and never overlap each other
    sl = tp.evaluate("() => { const e = Object.entries(TANK_DECO_SLOT).sort((a, b) => a[1] - b[1]); return e.map(x => x[0]).join() + ':' + e.map((x, i) => i ? +(x[1] - e[i - 1][1]).toFixed(2) : 0).join(); }")
    check("the decorations have fixed floor slots in a set order, at least .17 of the width apart", sl.startswith("chest,anchor,castle,bigcoral,bubbler") and all(float(v) >= .17 for v in sl.split(":")[1].split(",")[1:]), sl)
    # no gameplay effect: the economy, odds and selling do not read any of it
    eco = tp.evaluate("() => { const a = JSON.stringify(rarityWeights('none')), c = S.coins; S.tankTheme = 'pond'; S.tankDecoOn = []; const b = JSON.stringify(rarityWeights('none')); return [a === b, c === S.coins]; }")
    check("themes and decorations are cosmetic: the odds and the coins do not depend on them", eco == [True, True])
    tp.close()
    # NEW GAME resets the looks
    tn = aq_page(1536, 730, "Reset")
    tn.evaluate("() => { S.tankThemes = ['pond', 'deep']; S.tankTheme = 'deep'; S.tankDecos = ['chest']; S.tankDecoOn = ['chest']; save(); }")
    tn.reload(); tn.wait_for_timeout(300); tn.click("#newBtn"); tn.click("#confirmYes"); tn.fill("#nameInput", "Fresh"); tn.click("#nameStart"); tn.wait_for_timeout(300)
    nw = tn.evaluate("() => ({ th: S.tankThemes, use: S.tankTheme, de: S.tankDecos, on: S.tankDecoOn, saved: JSON.parse(localStorage.getItem('littleLakeSave')).tankThemes })")
    check("NEW GAME resets the owned themes, the theme in use and the decorations", nw == {"th": ["pond"], "use": "pond", "de": [], "on": [], "saved": ["pond"]}, str(nw))
    tn.close()
    # layout and screenshots: the Shop section and the Aquarium (Deep Sea + two decorations) at 1536x730 and 360x640
    for vw, vh in [(1536, 730), (360, 640), (1280, 600)]:
        tl = aq_page(vw, vh, "Look")
        tl.evaluate("() => { S.coins = 100; S.bagMax = 20; for (let i = 0; i < 9; i++) { const f = FISH[(i * 4) % 40]; S.tank.push({ fishId: f.id, weight: f.min, price: f.price, time: 0, locked: false }); } S.tankThemes = ['pond', 'deep']; S.tankTheme = 'deep'; S.tankDecos = ['castle', 'bubbler']; S.tankDecoOn = ['castle', 'bubbler']; save(); go('shop'); }")
        tl.wait_for_timeout(300)
        m = tl.evaluate("() => ({ sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, ih: innerHeight, over: [...document.querySelectorAll('#shopThemes .item, #shopDecos .item')].filter(i => i.scrollWidth > i.clientWidth + 1).length })")
        check(f"{vw}x{vh}: the Shop with the Tank Themes and Tank Decorations sections has no sideways scroll, no clipped card" + (" and fits the window" if vw >= 900 else ""), m["sw"] <= vw and m["over"] == 0 and (vw < 900 or m["sh"] <= m["ih"]), str(m))
        tl.evaluate("() => { const l = document.getElementById('shopScroll'); l.scrollTop = document.getElementById('shopThemes').previousElementSibling.offsetTop - l.offsetTop - 8; window.scrollTo(0, 0); }")
        if vw < 900: tl.evaluate("() => document.getElementById('shopThemes').previousElementSibling.scrollIntoView()")
        tl.wait_for_timeout(250)
        if vw != 1280: tl.screenshot(path=str(SHOTS / f"115_shop_tank_themes_{vw}x{vh}.png"))
        tl.evaluate("() => { const l = document.getElementById('shopScroll'); l.scrollTop = document.getElementById('shopDecos').previousElementSibling.offsetTop - l.offsetTop - 8; }")
        if vw < 900: tl.evaluate("() => document.getElementById('shopDecos').previousElementSibling.scrollIntoView()")
        tl.wait_for_timeout(250)
        if vw != 1280: tl.screenshot(path=str(SHOTS / f"115b_shop_tank_decorations_{vw}x{vh}.png"))
        tl.evaluate("() => go('aquarium')"); tl.wait_for_timeout(700)
        m2 = tl.evaluate("() => ({ sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, ih: innerHeight, tabs: document.querySelectorAll('#aqTabs .tab').length, tank: document.getElementById('tankCv').getBoundingClientRect().height })")
        check(f"{vw}x{vh}: the Aquarium with the THEME | DECOR tabs has no sideways scroll" + (" and fits the window" if vw >= 900 else "") + ", tank still big", m2["sw"] <= vw and m2["tabs"] == 3 and (vw < 900 or m2["sh"] <= m2["ih"]) and m2["tank"] >= (150 if vw < 900 else 250), str(m2))
        for tab in ("theme", "decor"):
            tl.click(f"#aqTabs [data-tab={tab}]"); tl.wait_for_timeout(150)
            mm = tl.evaluate("() => ({ sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, ih: innerHeight })")
            check(f"{vw}x{vh}: the {tab.upper()} tab fits (no sideways scroll" + (", no page scroll)" if vw >= 900 else ")"), mm["sw"] <= vw and (vw < 900 or mm["sh"] <= mm["ih"]), str(mm))
        tl.click("#aqTabs [data-tab=fish]"); tl.wait_for_timeout(200)
        if vw != 1280: tl.screenshot(path=str(SHOTS / f"116_aquarium_deepsea_{vw}x{vh}.png"))
        tl.close()


    # ---------- Playtest 2, part 10: the Shop category filter bar (ALL | RODS | BAIT | FLOATS | THEMES | DECOR) ----------
    SECS = ["rods", "bait", "floats", "themes", "decor", "bag"]
    VIS = """() => Object.fromEntries([...document.querySelectorAll('#shop .shop-sec')].map(e => [e.dataset.sec, getComputedStyle(e).display !== 'none']))"""
    fp = aq_page(1536, 730, "Filter")
    fp.evaluate("() => { S.coins = 5000; S.bagMax = 20; save(); go('shop'); }"); fp.wait_for_timeout(300)
    labels = fp.evaluate("[...document.querySelectorAll('#shopFilter .tab')].map(b => b.textContent)")
    v0 = fp.evaluate(VIS)
    check("the Shop has the filter bar ALL | RODS | BAIT | FLOATS | THEMES | DECOR; ALL is the default and shows every section", labels == ["ALL", "RODS", "BAIT", "FLOATS", "THEMES", "DECOR"] and all(v0.values()) and len(v0) == 6 and fp.evaluate("document.querySelector('#shopFilter .tab.on').textContent") == "ALL", str(v0))
    ok = True; det = []
    for k, f in enumerate(["rods", "bait", "floats", "themes", "decor"]):
        fp.evaluate("() => { document.getElementById('shopScroll').scrollTop = 400; }")
        fp.click(f"#shopFilter [data-filter={f}]"); fp.wait_for_timeout(80)
        v = fp.evaluate(VIS); st = fp.evaluate("() => [document.getElementById('shopScroll').scrollTop, document.querySelector('#shopFilter .tab.on').dataset.filter, document.querySelector('#shopFilter .tab.on').getAttribute('aria-pressed')]")
        good = [x for x in SECS if v[x]] == [f] and st[0] == 0 and st[1] == f and st[2] == "true"
        ok &= good; det.append((f, good))
    check("each filter shows only its own section, hides the others, scrolls the list back to the top and marks the active button", ok, str(det))
    fp.click("#shopFilter [data-filter=all]"); fp.wait_for_timeout(80)
    check("ALL restores every section", all(fp.evaluate(VIS).values()))
    nit = fp.evaluate("() => { const e = document.querySelector('#shopRods .item'); e.dataset.mark = 'x'; applyShopFilter(true); return 1; }")
    fp.click("#shopFilter [data-filter=rods]"); fp.click("#shopFilter [data-filter=all]")
    check("filtering does not rebuild the items (a marker on a card survives)", fp.evaluate("document.querySelector('#shopRods .item').dataset.mark") == "x")
    # buying under a filter
    for f, sel, cond in [("rods", "#shopRods [data-buy='rod:sturdy']", "S.rods.includes('sturdy')"), ("floats", "#shopFloats [data-buy='float:candy']", "S.floatsOwned.includes('candy') && S.floatEq === 'candy'"),
                         ("themes", "#shopThemes [data-buy='theme:reef']", "S.tankThemes.includes('reef') && S.tankTheme === 'reef'"), ("decor", "#shopDecos [data-buy='deco:chest']", "S.tankDecos.includes('chest') && S.tankDecoOn.includes('chest')")]:
        fp.click(f"#shopFilter [data-filter={f}]"); c0 = fp.evaluate("S.coins"); fp.locator(sel).click(); fp.wait_for_timeout(120)
        lab = fp.evaluate(f"document.querySelector(\"{sel}\").textContent")
        check(f"buying under the {f.upper()} filter still works (coins drop, state saved, button updates to '{lab}') and the filter stays", fp.evaluate(cond) and fp.evaluate("S.coins") < c0 and lab in ("OWNED", "EQUIPPED", "IN USE", "SHOWN") and fp.evaluate("shopFilter") == f and [x for x in SECS if fp.evaluate(VIS)[x]] == [{"themes": "themes", "decor": "decor"}.get(f, f)], f"{lab} {fp.evaluate('shopFilter')}")
    # survives re-render and reopening, reload resets
    fp.click("#shopFilter [data-filter=floats]"); fp.evaluate("() => { render(); }"); fp.wait_for_timeout(100)
    k1 = [x for x in SECS if fp.evaluate(VIS)[x]]
    fp.evaluate("() => { go('home'); go('shop'); }"); fp.wait_for_timeout(200)
    k2 = [x for x in SECS if fp.evaluate(VIS)[x]]
    check("the filter survives a re-render and leaving and reopening the Shop", k1 == ["floats"] and k2 == ["floats"] and fp.evaluate("document.querySelector('#shopFilter .tab.on').dataset.filter") == "floats", str((k1, k2)))
    check("the filter is not stored in the save", "shopFilter" not in fp.evaluate("localStorage.getItem('littleLakeSave')"))
    fp.reload(); fp.wait_for_timeout(300); fp.click("#contBtn"); fp.wait_for_timeout(200); fp.evaluate("() => go('shop')"); fp.wait_for_timeout(200)
    check("after a reload the Shop is back on ALL", all(fp.evaluate(VIS).values()) and fp.evaluate("shopFilter") == "all")
    fp.evaluate("() => { shopFilter = 'bait'; }"); fp.evaluate("() => go('titleScreen')"); fp.click("#newBtn"); fp.click("#confirmYes"); fp.fill("#nameInput", "Again"); fp.click("#nameStart"); fp.wait_for_timeout(200)
    check("NEW GAME resets the filter to ALL", fp.evaluate("shopFilter") == "all")
    # keyboard
    fp.evaluate("() => go('shop')"); fp.wait_for_timeout(200)
    fp.focus("#shopFilter [data-filter=bait]"); fp.keyboard.press("Enter"); fp.wait_for_timeout(80)
    kb1 = fp.evaluate("shopFilter"); fp.focus("#shopFilter [data-filter=themes]"); fp.keyboard.press("Space"); fp.wait_for_timeout(80)
    check("the filter buttons are focusable and Enter / Space activate them", kb1 == "bait" and fp.evaluate("shopFilter") == "themes")
    fp.close()
    for vw, vh in [(1536, 730), (360, 640), (390, 844)]:
        fl = aq_page(vw, vh, "FilterLook")
        fl.evaluate("() => { S.coins = 100; save(); go('shop'); }"); fl.wait_for_timeout(300)
        def fm(): return fl.evaluate("""() => { const bar = document.getElementById('shopFilter'), bs = [...bar.querySelectorAll('.tab')], r = bar.getBoundingClientRect(), bb = bs.map(b => b.getBoundingClientRect()), ys = new Set(bb.map(x => Math.round(x.top)));
            const card = [...document.querySelectorAll('#shop .item')].find(i => i.offsetParent), cr = card && card.getBoundingClientRect();
            return { sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, ih: innerHeight, top: r.top, bottom: r.bottom, rows: ys.size, n: bs.length, minH: Math.min(...bb.map(x => x.height)),
              barScroll: bar.scrollWidth > bar.clientWidth + 1, inside: bb.every(x => x.left >= 0 && x.right <= innerWidth), clipped: bs.filter(b => b.scrollWidth > b.clientWidth + 1).length, vis: r.top >= 0 && r.bottom <= innerHeight,
              cardFull: !!cr && cr.top >= r.bottom && cr.bottom <= innerHeight }; }""")
        m = fm(); narrow = vw < 700
        check(f"{vw}x{vh}: the filter bar is visible without scrolling, six buttons " + ("in a 3 x 2 grid fully inside the screen" if narrow else "in ONE row") + ", 40px+ high, text not clipped, no horizontal scroll of the bar or the page",
              m["vis"] and m["n"] == 6 and m["rows"] == (2 if narrow else 1) and m["minH"] >= 39.9 and m["sw"] <= vw and not m["barScroll"] and m["inside"] and m["clipped"] == 0 and (narrow or m["sh"] <= m["ih"]), str(m))
        if narrow: check(f"{vw}x{vh}: a full shop card is visible under the bar without scrolling", m["cardFull"], str(m))
        fl.screenshot(path=str(SHOTS / f"117_shop_filter_all_{vw}x{vh}.png")) if vw != 390 else None
        fl.click("#shopFilter [data-filter=decor]"); fl.wait_for_timeout(200)
        m = fm(); v = fl.evaluate(VIS)
        check(f"{vw}x{vh}: the last button (DECOR) can be tapped at once; only that section shows and the bar stays in place", [x for x in SECS if v[x]] == ["decor"] and m["vis"] and m["inside"] and m["sw"] <= vw and not m["barScroll"] and (narrow or m["sh"] <= m["ih"]), str(m))
        fl.close()

    check("no JavaScript errors", not errs, "; ".join(errs[:3]))
    b.close()

print(f"\n{sum(r[1] for r in results)}/{len(results)} passed")
json.dump(results, open(Path(__file__).with_name("results.json"), "w"), indent=1)
