import json, sys
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
          rm.evaluate("getComputedStyle(document.querySelector('.title-shimmer')).animationName === 'none'")
          and rm.evaluate("['.bgfx .clouds', '.bgfx .water'].every(s => getComputedStyle(document.querySelector(s), '::before').animationName === 'none')")
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
          all(w in how for w in ["Rods", "Sturdy", "Precision", "Lucky", "Worm", "Golden Lure", "heart", "Tackle Box", "Master's Charm", "separate saves"]))
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
    for vw, vh in [(1366, 768), (1280, 720), (390, 844)]:
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
          and "1 miss allowed, green zone 35% wider." in pre["text"]
          and "1 miss allowed, better rarity odds (like Shrimp bait), marker 10% faster." in luc["text"]
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
    check("rod effects: Bamboo 1 miss, Sturdy 2, Precision zone x1.35, Lucky marker x1.1",
          effects == {"bamboo": [1, .26, .55], "sturdy": [2, .26, .55], "precision": [1, .351, .55], "lucky": [1, .26, .605]}, str(effects))
    with_rewards = g.evaluate(f"({eff})('lucky', {{ forest: true, frost: true }})"), g.evaluate(f"({eff})('sturdy', {{ forest: true }})")
    check("island rewards stack on the rod (Master's Charm +1 miss, Steady Hands 20% slower)",
          with_rewards[0] == [2, .26, .484] and with_rewards[1] == [3, .26, .55], str(with_rewards))

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
        check(f"{vw}x{vh}: Home keeps its framed layout (top bar, no full-screen picture)",
              tp.is_visible("#title") and not tp.is_visible(".title-bg") and tp.is_visible(".bgfx"))
        tp.close()

    check("no JavaScript errors", not errs, "; ".join(errs[:3]))
    b.close()

print(f"\n{sum(r[1] for r in results)}/{len(results)} passed")
json.dump(results, open(Path(__file__).with_name("results.json"), "w"), indent=1)
