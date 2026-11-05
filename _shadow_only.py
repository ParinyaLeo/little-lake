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

def no_side_scroll(pg, width=360):
    return pg.evaluate("document.documentElement.scrollWidth") <= width

SAVED = "JSON.parse(localStorage.getItem('littleLakeSave'))"


with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    PICS = ["frost", "desert", "forest", "secret"]
    MASKS = {i: "data:image/png;base64," + base64.b64encode((Path(__file__).parent / "tools" / "water_masks" / f"{i}.png").read_bytes()).decode() for i in PICS}
    ON_WATER = """async ([src, x, y]) => { const im = new Image(); im.src = src; await im.decode();
        const c = document.createElement('canvas'), g = c.getContext('2d'); c.width = im.width; c.height = im.height; g.drawImage(im, 0, 0);
        const ax = Math.floor(x / 4), ay = Math.floor(y / 4), d = g.getImageData(ax - 3, ay - 2, 7, 5).data;
        for (let i = 0; i < d.length; i += 4) if (d[i] < 128) return false; return true; }"""
    UNLOCK = "() => { ['harbor','frost','desert','forest'].forEach(i => S.mastery[i] = true); save(); }"
    # ---------- Playtest 2, part 1: the fish shadow approaches the bait and fights during REEL (visual only) ----------
    import math
    SAMPLER = """() => { window.__sh = []; window.__shRun = true; const f = () => { const s = fishShadowState(); window.__sh.push({ t: performance.now(), ph: F.phase, s, fid: F.fish && F.fish.id, ca: F.castAt, ba: F.biteAt, bp: F.bobPos && [F.bobPos.x, F.bobPos.y] });
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
        bite_t = next(a["t"] for a in smp if a["ph"] == "bite"); c0 = next(a for a in smp if a["ca"]); span = c0["ba"] - (c0["ca"] + 500)
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
    for _ in range(14): xs.append(sh_now(fsp)["x"] * 900); fsp.wait_for_timeout(25)
    check("REEL: the shadow stays near the bobber and thrashes sideways (quick motion), phase 'reel'", st0["phase"] == "reel" and st0["dBob"] < 60 and max(xs) - min(xs) > 6, f"{st0['phase']} dBob={st0['dBob']:.0f} spread={max(xs) - min(xs):.1f}px")
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
    check("reduced motion: while waiting there is no circling or nibbling (one straight approach with a fade-in)",
          {s["phase"] for s in sd} == {"approach"} and dev < 2 and sd[0]["alpha"] < .5 and sd[-1]["alpha"] == 1, f"phases={ {s['phase'] for s in sd} } deviation={dev:.2f}px alpha {sd[0]['alpha']:.2f}->{sd[-1]['alpha']:.2f}")
    rms.click("#actBtn"); rms.wait_for_timeout(500)
    xs = []
    for _ in range(10): xs.append(sh_now(rms)["x"] * 900); rms.wait_for_timeout(30)
    check("reduced motion: the shadow does not thrash while reeling (it holds still)", max(xs) - min(xs) < 1.0, f"spread {max(xs) - min(xs):.2f}px")
    sh_miss(rms); rms.wait_for_timeout(100); sh_miss(rms); rms.wait_for_timeout(100); r1 = sh_now(rms); rms.wait_for_timeout(400); r2 = sh_now(rms)
    check("reduced motion: on escape it moves in a straight line away and fades out", bool(r1 and r2) and r1["phase"] == "leave" and r2["x"] > r1["x"] and r2["alpha"] < r1["alpha"], f"{r1 and r1['phase']}")
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

    check("no JavaScript errors", not errs, "; ".join(errs[:3]))
    b.close()
print(f"{sum(r[1] for r in results)}/{len(results)} passed")
