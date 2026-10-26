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
    pg.evaluate("S.coins = 120; save()"); pg.click("section.active >> text=HOME"); pg.click("section.active >> text=SHOP"); pg.wait_for_timeout(200)
    check("rod blocked with insufficient coins", pg.is_disabled("#buyRod"))
    pg.click("#buyBait"); check("buy bait works", pg.evaluate("S.bait") == 5 and pg.evaluate("S.coins") == 20)
    pg.screenshot(path=str(SHOTS / "09_shop.png"))

    # persistence
    pg.reload(); pg.wait_for_timeout(300)
    check("progress survives reload", pg.evaluate("S.bait") == 5 and pg.evaluate("S.coins") == 20)

    # broken save
    pg.evaluate("localStorage.setItem('littleLakeSave', '{\"coins\":\"abc\",\"bag\":[null,{\"fishId\":\"x\"}],\"rod\":-3}')"); pg.reload(); pg.wait_for_timeout(300)
    pg.click("#contBtn"); pg.wait_for_timeout(200)
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

    t.evaluate("S.coins = 777; S.bait = 3; save(); render()")
    t.reload(); t.wait_for_timeout(300)
    check("reload opens Title with CONTINUE enabled", t.is_visible("#titleScreen") and t.is_enabled("#contBtn"))
    t.click("#contBtn"); t.wait_for_timeout(200)
    check("CONTINUE after reload keeps progress",
          t.is_visible("#home") and t.inner_text("#hCoins") == "777" and t.inner_text("#homeName") == "Parinya" and t.evaluate("S.bait") == 3)

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
          t.inner_text("#homeName") == "Nova" and t.inner_text("#hCoins") == "300" and t.evaluate("S.bait") == 0)

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
    check("Home shows drifting clouds + water shimmer", t.is_visible(".bgfx")
          and t.evaluate("getComputedStyle(document.querySelector('.bgfx .clouds'), '::before').animationName") == "drift-x")
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
    check("page background continues as water down to a sea floor",
          t.evaluate("getComputedStyle(document.body).backgroundImage.split('url(').length - 1") >= 2
          and t.evaluate("getComputedStyle(document.body).backgroundImage.includes('svg')"))

    rm = b.new_page(viewport={"width": 360, "height": 780}, reduced_motion="reduce")
    rm.goto(URL); rm.wait_for_timeout(300)
    check("prefers-reduced-motion stops the background animations",
          rm.evaluate("['.hero .clouds', '.hero .water'].every(s => getComputedStyle(document.querySelector(s), '::before').animationName === 'none')")
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
    q.click("#bagList .row .btn"); q.wait_for_timeout(100); q.click("#bagBack"); q.wait_for_timeout(200)
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
    q.evaluate("() => { S.rod = 2; S.bait = 3; S.mastery.harbor = true; S.mastery.forest = true; save(); go('home'); }")
    q.click("#tackleBtn"); q.wait_for_timeout(300)
    gear = q.inner_text("#gearList")
    check("TACKLE BOX opens from Home and lists rod, misses, bait, bag", q.is_visible("#tackle")
          and "Rod Lv.2" in gear and "3 misses allowed" in gear and "Bait x3" in gear and "Bag 1 / 5" in gear, gear[:120])
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

    # BUG-6: bait toggle and the last-bait bug
    q.evaluate("() => { island = 'harbor'; go('fishing'); }"); q.wait_for_timeout(300)
    check("fishing HUD shows USE BAIT: ON with the bait count", "USE BAIT: ON (3)" in q.inner_text("#baitBtn") and q.get_attribute("#baitBtn", "aria-pressed") == "true")
    q.click("#baitBtn"); q.wait_for_timeout(100)
    check("USE BAIT can be turned off and is saved", "OFF" in q.inner_text("#baitBtn") and q.evaluate(SAVED + ".useBait") is False)
    q.click("#actBtn"); q.wait_for_timeout(100)
    check("casting with USE BAIT off keeps the bait", q.evaluate("S.bait") == 3 and q.evaluate("F.usedBait") is False and q.is_disabled("#baitBtn"))
    q.evaluate("() => stopFishing()"); q.evaluate("() => { go('fishing'); }"); q.wait_for_timeout(150)
    q.click("#baitBtn"); q.evaluate("() => { S.bait = 1; save(); render(); window._wb = []; const o = pickFish; pickFish = w => { _wb.push(w); return o(w); }; }")
    q.click("#actBtn"); q.wait_for_timeout(100)
    check("the last bait still gives bait odds", q.evaluate("_wb") == [True] and q.evaluate("S.bait") == 0 and "NO BAIT" in q.inner_text("#baitBtn"))
    q.evaluate("() => stopFishing()")
    q.evaluate("localStorage.setItem('littleLakeSave', JSON.stringify({name:'Old', coins:50, rod:1, bait:2, bagMax:5, bag:[]}))")
    q.reload(); q.wait_for_timeout(300)
    check("older save without the bait toggle loads with USE BAIT on", q.evaluate("S.useBait") is True and q.evaluate("S.pending") is None)
    q.click("#contBtn"); q.wait_for_timeout(200)

    # BUG-7: hearts for misses left, bonus icons with tooltips
    q.evaluate("() => { S.rod = 2; S.mastery.frost = true; save(); island = 'harbor'; go('fishing'); }"); q.wait_for_timeout(300)
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
    q.evaluate("() => { S.rod = 1; S.mastery = {}; S.bagMax = 5; S.coins = 1000; save(); go('shop'); }"); q.wait_for_timeout(200)
    check("Shop: rod shows 'Rod Lv.2: 2 misses allowed (now 1)'", q.inner_text("#sRodFx") == "Rod Lv.2: 2 misses allowed (now 1)", q.inner_text("#sRodFx"))
    check("Shop: bait says it works while USE BAIT is on", "better chance of Rare+ fish while USE BAIT is on" in q.inner_text("#sBaitFx"))
    check("Shop: bag shows new and current size", q.inner_text("#sBagFx") == "Bag: 10 slots (now 5)")
    q.click("#buyRod"); q.wait_for_timeout(100)
    check("Shop effect text updates after buying", q.inner_text("#sRodFx") == "Rod Lv.3: 3 misses allowed (now 2)")

    q.click("section.active >> text=HOME"); q.click("#menuBtn"); q.click("#howBtn"); q.wait_for_timeout(200)
    how = q.inner_text("#howBox")
    check("HOW TO PLAY explains bait toggle, hearts, Tackle Box and Master's Charm",
          all(w in how for w in ["USE BAIT", "heart", "Tackle Box", "Master's Charm", "separate saves"]))
    q.click("#howOk")

    # phones
    m.evaluate("() => { S.bait = 2; S.mastery.harbor = true; save(); go('tackle'); }"); m.wait_for_timeout(300)
    check("mobile Tackle Box no side scroll", m.is_visible("#tackle") and no_side_scroll(m))
    m.screenshot(path=str(SHOTS / "31_mobile_tackle.png"), full_page=True)
    m.evaluate("() => { S.bag = []; while (S.bag.length < S.bagMax) S.bag.push({fishId:'harbor_0',weight:.2,price:20,time:1}); F = { phase: 'idle', fish: fishById('harbor_5') }; caught(); }"); m.wait_for_timeout(300)
    check("mobile full-bag choice no side scroll", m.is_visible("#sellOneBtn") and no_side_scroll(m))
    m.screenshot(path=str(SHOTS / "32_mobile_full_bag.png"), full_page=True)
    m.click("#fullRelease"); m.wait_for_timeout(200)
    check("mobile fishing HUD (bait + bonuses) no side scroll", m.is_visible("#baitBtn") and m.is_visible("#bonuses .bonus") and no_side_scroll(m))

    # ---------- BUG-9: the main fishing button must not move between phases (see docs/bug_log.md) ----------
    ACT_POS = """(() => { const r = document.getElementById('actBtn').getBoundingClientRect();
        return { top: r.top + scrollY, bottom: r.bottom, vh: innerHeight, page: document.documentElement.scrollHeight }; })()"""
    for vw, vh in [(1366, 768), (1280, 720), (390, 844)]:
        s = b.new_page(viewport={"width": vw, "height": vh})
        s.on("pageerror", lambda e: errs.append(str(e)))
        s.goto(URL); s.evaluate("localStorage.clear()"); s.reload(); s.wait_for_timeout(200); start_new(s, "Steady")
        s.evaluate("() => { S.bait = 5; S.mastery = { harbor: true, frost: true }; save(); island = 'harbor'; go('fishing'); }"); s.wait_for_timeout(400)
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

    check("no JavaScript errors", not errs, "; ".join(errs[:3]))
    b.close()

print(f"\n{sum(r[1] for r in results)}/{len(results)} passed")
json.dump(results, open(Path(__file__).with_name("results.json"), "w"), indent=1)
