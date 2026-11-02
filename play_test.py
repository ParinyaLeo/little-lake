import base64, json, re, sys
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

def start_new(pg, name="Tester"):
    """Title screen -> NEW GAME -> enter name -> Home."""
    pg.click("#newBtn"); pg.fill("#nameInput", name); pg.click("#nameStart"); pg.wait_for_timeout(200)

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
          t.evaluate("document.querySelectorAll('#home .stat > .ico').length") == 6 and t.evaluate("document.querySelectorAll('#home .btns .ico').length") == 5)
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
    t.click("#actBtn"); t.wait_for_timeout(700)
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
    check("prefers-reduced-motion stops the background animations",
          rm.evaluate("getComputedStyle(document.querySelector('.title-shimmer')).animationName === 'none'")
          and rm.evaluate("getComputedStyle(document.querySelector('#backdrop .bd')).transitionDuration") == "0s"
          and rm.evaluate("getComputedStyle(document.querySelector('.screen.active')).animationName") == "none")

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
    check("reload + CONTINUE returns to the waiting catch", q.is_visible("#result") and "Sea Bream" in q.inner_text("#resName"))
    q.evaluate("go('home')"); q.wait_for_timeout(150)
    check("can't leave the Result screen without KEEP or RELEASE", q.is_visible("#result") and not q.is_visible("#home"))
    q.click("#keepBtn"); q.wait_for_timeout(150)
    check("KEEP shows '+1 Sea Bream added to bag' and bounces the bag count",
          "+1 Sea Bream added to bag" in toast_text(q) and "bump" in q.get_attribute("#fBag", "class")
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
          and q.evaluate("S.pending") is None and "Striped Mullet added to bag" in toast_text(q), toast_text(q))
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
          and "5 misses allowed, better rarity odds (like Shrimp bait), marker 10% faster." in luc["text"]
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
          and "2 misses allowed" in rl[1][3] and "green zone 35% wider" in rl[2][3] and "marker 10% faster" in rl[3][3]
          and all("Common" in x[3] for x in rl) and "Legendary 6%" in rl[3][3], str([x[0:3] for x in rl]))
    g.screenshot(path=str(SHOTS / "39_choose_rod.png"))
    g.click("#pick-lucky"); g.wait_for_timeout(100)
    check("equipping a non-first rod takes one tap in the popup (Lucky Rod)",
          g.evaluate("S.rodEq") == "lucky" and "Lucky" in g.inner_text("#rodChip") and not g.is_visible("#pickBox")
          and "Equipped Lucky Rod" in g.inner_text("#toast") and g.evaluate(SAVED + ".rodEq") == "lucky")
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
    check("prefers-reduced-motion: one still fisherman pose per phase",
          len({tuple(x) for x in still}) == 1 and still[0][0] == "idle" and len({tuple(x) for x in wait_still}) == 1 and wait_still[0][0] == "waiting",
          f"{still[0]} {wait_still[0]}")
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
        const btns = ['newBtn', 'contBtn', 'howBtn', 'soundBtn'].map(id => { const b = document.getElementById(id).getBoundingClientRect(),
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
        check(f"{vw}x{vh}: all 4 Title buttons visible and clickable, sign near the top",
              all(x[0] and x[1] for x in r["btns"]) and r["logoTop"] < .25, str(r["btns"]) + f" logo {r['logoTop']:.2f}")
        check(f"{vw}x{vh}: Title has no side or page scroll", r["sw"] <= r["vw"] and r["sh"] <= r["vh"], f"{r['sw']}x{r['sh']}")
        if vw == 360:
            check("360x640: Title buttons stacked 2x2 at the bottom",
                  len({x[2] for x in r["btns"]}) == 2 and len({x[3] for x in r["btns"]}) == 2 and min(x[2] for x in r["btns"]) > vh * .6, str(r["btns"]))
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
        const btns = ['newBtn', 'contBtn', 'howBtn', 'soundBtn'].map(id => { const b = document.getElementById(id).getBoundingClientRect(); return b.top >= 0 && b.bottom <= innerHeight; });
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
                  ok2a and nv.is_visible("#fishing") and nv.evaluate("island") == "frost" and "Frost" in nv.inner_text("#fMsg") and nv.is_enabled("#actBtn"), nv.inner_text("#fMsg"))
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
    check("prefers-reduced-motion: no backdrop crossfade", rm2.evaluate("getComputedStyle(document.querySelector('.bd')).transitionDuration") == "0s")
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

    # ---------- BUG-30 / BUG-34: Town Map HOME (BUG-30: out of the bottom bar; BUG-34: a bigger tab on the panel's top border, top right) ----------
    MH = """() => { const homes = [...document.querySelectorAll('[data-go="home"]')].filter(b => b.offsetParent), m = document.getElementById('mapHome'),
        panel = document.querySelector('#map .panel'), p = panel.getBoundingClientRect(), r = m.getBoundingClientRect(), h2 = panel.querySelector('h2').getBoundingClientRect(),
        bw = parseFloat(getComputedStyle(panel).borderTopWidth), ico = m.querySelector('.ico.i-home').getBoundingClientRect(),
        hit = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom,
        others = [...document.querySelectorAll('.app > .top > *, #map .island, #map h2')].filter(e => e.offsetParent || getComputedStyle(e).position === 'fixed');
        return { n: homes.length, inPanel: m.parentElement === panel, inBar: !!document.querySelector('#navbar [data-go="home"]'),
                 below: document.querySelectorAll('#map > .btns').length, right: Math.round(p.right - r.right),
                 above: Math.round(p.top - r.top), inside: Math.round(r.bottom - (p.top + bw)), straddles: r.top < p.top && r.bottom > p.top + bw,
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
        if (vw, vh) in ((1536, 730), (360, 640)): hp.screenshot(path=str(SHOTS / f"98_map_home_tab_{vw}x{vh}.png"))
        check(f"{vw}x{vh}: Town Map has exactly one HOME, a real button (pixel house icon, 'HOME', aria-label 'Home') on the panel frame; none in the top bar or below the panel",
              r["n"] == 1 and r["inPanel"] and not r["inBar"] and r["below"] == 0 and r["icon"] and r["label"] == "HOME" and r["aria"] == "Home" and r["tag"] == "BUTTON",
              str({k: r[k] for k in ("n", "inPanel", "inBar", "below", "icon", "label", "aria")}))
        check(f"{vw}x{vh}: Town Map HOME is >= 44px tall with a bigger icon (>= 20px) and label (>= 18px)", r["h"] >= 44 and r["iconPx"] >= 20 and r["font"] >= 18,
              f"h {r['h']} icon {r['iconPx']} font {r['font']}")
        check(f"{vw}x{vh}: Town Map HOME sits on the panel's top border at the right edge (about half above, half inside; <= 20px from the right)",
              r["straddles"] and abs(r["above"] - r["h"] / 2) <= 8 and 0 <= r["right"] <= 20, f"above {r['above']} inside {r['inside']} h {r['h']} right {r['right']}")
        check(f"{vw}x{vh}: Town Map HOME doesn't overlap the title, the island cards or the top bar, is fully in view and on top (tappable)",
              not r["overlaps"] and r["inView"] and r["topAt"], f"{r['overlaps']} inView {r['inView']} topAt {r['topAt']}")
        check(f"{vw}x{vh}: Town Map header row is no taller than before (<= 44px) and the page has no page scroll or side scroll",
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
          "Bamboo (free, 1 miss), Sturdy (2 misses), Precision (3 misses and a 35% wider green zone) or Lucky (5 misses and better odds, but a 10% faster marker)" in rp.inner_text("#howBox"))
    rc.close()
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
            back = [sp.evaluate("current"), sp.evaluate("island"), sp.is_enabled("#actBtn"), "Desert" in sp.inner_text("#fMsg")]
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

    check("no JavaScript errors", not errs, "; ".join(errs[:3]))
    b.close()

print(f"\n{sum(r[1] for r in results)}/{len(results)} passed")
json.dump(results, open(Path(__file__).with_name("results.json"), "w"), indent=1)
