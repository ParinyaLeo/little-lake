/* ===================== BOAT TRIP (Playtest 3) =====================
   A fishing spot (island id "boat", see SPOTS in js/data.js): the fisherman sits in a small boat on open sea and the player moves the boat left and right between casts
   (A / Left arrow, D / Right arrow, or the two on-screen buttons). It fishes the Harbor table (fishIsland), so fish, odds, prices, rods, bait and rewards are the same as on the
   Harbor; the only new rules are WHERE the boat is and that the bobber lands relative to it. The whole scene is canvas code (no picture files).
   Loaded after fishing.js (uses its helpers: rect, cv, ctx, TIP, FCFG, snap, PX, F, CH ...), before screens.js. Everything here runs only while island === "boat".
   - BOAT.x = the boat's centre as a share of the canvas width (the canvas is always 900 px wide). Movement: BOAT_SPEED (.20 = 20% of the width per second), only while F.phase is "idle"
     and no charge is running; it is ignored (the boat holds still) while charging, casting, waiting, bite, reeling and on the Result screen, so the line never changes mid-fish.
   - boatLanding(): the same landing line as landing() (POWER.near > POWER.far), the x offsets measured from the boat (BOAT_REF = where the fisherman stands in the other scenes),
     clamped inside the scene. BOAT_HORIZON = the horizon: everything below it is open water (boatWater(x, y) is this scene's water mask, used by the tests). */
const BOAT_SPEED = .20, BOAT_HORIZON = .40, BOAT_WL = .60, BOAT_REF = .22, BOAT_MARGIN = .03, BOAT_LAND_MAX = .965;
const BOAT = { x: .3, kL: false, kR: false, tL: false, tR: false, v: 0, wake: 0, wdir: 1, lastT: 0, hinted: false };
const BOAT_LEN = 60, BOAT_ROWS = 13, BOAT_WROW = 9;                                                     // hull size in art pixels
const BOAT_SCENE = { boat: true, fisher: { outfit: "harbor" }, rod: { x: .4, y: .3 }, paint: paintBoatSea };
const boatWater = (x, y) => y > BOAT_HORIZON + .02 && y < .99 && x > .01 && x < .99;      // this scene's water mask: everything under the horizon (tests)
// art pixel size on the canvas and the hull half-width as a share of the canvas width
function boatGeom(W, H) { const p = Math.min(4, H / 100); return { p, half: BOAT_LEN * p / 2 / W }; }
function boatLimits() { const g = boatGeom(cv.width, cv.height); return { min: BOAT_MARGIN + g.half, max: 1 - BOAT_MARGIN - g.half - .02 }; }
const boatClamp = x => { const l = boatLimits(); return Math.min(l.max, Math.max(l.min, x)); };
// the bobber's landing spot: the old near > far line, x counted from the boat (BOAT_REF = the fisherman's x in the other scenes), clamped to the water inside the scene
function boatLanding(power, jitter) {
  const p = Math.min(1, Math.max(0, power + (Math.random() * 2 - 1) * jitter));
  const x = BOAT.x + (POWER.near.x - BOAT_REF) + (POWER.far.x - POWER.near.x) * p;
  return { x: Math.min(BOAT_LAND_MAX, Math.max(BOAT.x + .06, x)), y: POWER.near.y + (POWER.far.y - POWER.near.y) * p + (Math.random() - .5) * .02, p };
}

/* ---------- input ---------- */
const boatCan = () => current === "fishing" && island === "boat" && F.phase === "idle" && !CH.on && !document.querySelector(".banner.show");
function boatDir() { return (BOAT.kL || BOAT.tL ? -1 : 0) + (BOAT.kR || BOAT.tR ? 1 : 0); }
function boatInputReset() { BOAT.kL = BOAT.kR = BOAT.tL = BOAT.tR = false; $("boatL").classList.remove("down"); $("boatR").classList.remove("down"); }
const boatKey = e => { const c = e.code, k = (e.key || "").toLowerCase(); return c === "KeyA" || c === "ArrowLeft" || k === "a" || k === "arrowleft" ? -1 : c === "KeyD" || c === "ArrowRight" || k === "d" || k === "arrowright" ? 1 : 0; };
document.addEventListener("keydown", e => {
  const d = boatKey(e); if (!d || e.ctrlKey || e.metaKey || e.altKey) return;
  if (current !== "fishing" || island !== "boat" || document.querySelector(".banner.show")) return;   // A and D do nothing on other screens and scenes
  if (d < 0) BOAT.kL = true; else BOAT.kR = true;
  if (e.key.startsWith("Arrow")) e.preventDefault();                                                // no page scroll from the arrows in this scene
});
document.addEventListener("keyup", e => { const d = boatKey(e); if (d < 0) BOAT.kL = false; else if (d > 0) BOAT.kR = false; });
window.addEventListener("blur", boatInputReset);
document.addEventListener("visibilitychange", () => { if (document.hidden) boatInputReset(); });
// the two on-screen buttons: held to move. Same iOS prevention as REEL (no selection, callout, loupe, context menu); pointerdown does not reach the scene, so a press never starts a cast charge
[["boatL", "tL"], ["boatR", "tR"]].forEach(([id, flag]) => {
  const b = $(id); let pid = -1;
  const up = e => { if (pid !== -1 && e.pointerId === pid) { pid = -1; BOAT[flag] = false; b.classList.remove("down"); } };
  b.addEventListener("pointerdown", e => { if (e.button) return; e.preventDefault(); e.stopPropagation(); clearSelection(); pid = e.pointerId; BOAT[flag] = true; b.classList.add("down"); try { b.setPointerCapture(e.pointerId); } catch (err) {} });
  ["pointerup", "pointercancel", "lostpointercapture"].forEach(t => b.addEventListener(t, up));
  document.addEventListener("pointerup", up); document.addEventListener("pointercancel", up);
  ["touchstart", "touchmove"].forEach(t => b.addEventListener(t, e => { if (e.cancelable) e.preventDefault(); }, { passive: false }));
  ["contextmenu", "selectstart", "dragstart"].forEach(t => b.addEventListener(t, e => e.preventDefault()));
});
// shows / hides the pad and gives the once-per-session hint (called by renderFishingHud)
function boatSync() {
  const on = island === "boat"; $("boatPad").style.display = on ? "" : "none";
  if (!on) { boatInputReset(); return; }
  if (!BOAT.hinted) { BOAT.hinted = true; setTimeout(() => toast("A / D or the arrow buttons: move the boat"), 250); }
}
// one frame of movement (called from loop() before the scene is drawn)
function boatStep(t) {
  const dt = Math.min(.05, Math.max(0, (t - BOAT.lastT) / 1000)); BOAT.lastT = t;
  if (island !== "boat") return;
  const can = boatCan(), dir = can ? boatDir() : 0;
  for (const id of ["boatL", "boatR"]) { const b = $(id); if (b.disabled === can) b.disabled = !can; }   // greyed out while the line is out
  BOAT.x = boatClamp(BOAT.x + dir * BOAT_SPEED * dt); BOAT.v = dir;
  if (dir) BOAT.wdir = dir;
  BOAT.wake += ((dir ? 1 : 0) - BOAT.wake) * Math.min(1, dt * (dir ? 8 : 3));                // the wake grows quickly and fades slowly
}
// for the tests only
const boatState = () => ({ x: BOAT.x, v: BOAT.v, wake: BOAT.wake, limits: boatLimits(), hinted: BOAT.hinted, can: boatCan() });

/* ---------- the scene ---------- */
function paintBoatSea(g, w, h) {                                                          // the still part (cached): sky, horizon, sea; art pixels
  bands(g, w, 0, h * BOAT_HORIZON, ["#7cc6ea", "#8fd2f1", "#a4dcf4", "#bbe6f7", "#d2f0fa", "#e6f7fd"]);
  rect(g, 0, h * BOAT_HORIZON - 1, w, 1, "#f2fbff");                                      // the horizon line
  water(g, w, h, h * BOAT_HORIZON, ["#3fb6e0", "#35a8d6", "#2c9ac9", "#238bba", "#1b7caa", "#146d9a", "#0f5f89"], "#9fe0f7");
  return { water: BOAT_HORIZON };
}
// a pixel cloud in screen pixels (rects, snapped to the art grid)
function boatCloud(c, x, y, s) { const u = PX * s; c.fillStyle = "#ffffff"; c.fillRect(snap(x), snap(y), u * 5, u); c.fillRect(snap(x + u), snap(y - u), u * 3, u); c.fillRect(snap(x + u * 2), snap(y - u * 2), u, u); c.fillStyle = "#cfe9f6"; c.fillRect(snap(x), snap(y + u), u * 5, PX); }
const BOAT_CLOUDS = [[.08, .12, 3, 5], [.42, .06, 2, 3.5], [.7, .18, 3, 4.4], [.9, .09, 2, 2.6]];   // x, y (shares), size, drift speed (px/s)
// the hull, drawn from rects in art pixels: (cx, top) = centre of the gunwale; p = canvas px per art pixel. Row BOAT_WROW is the waterline.
function boatHull(c, cx, top, p) {
  const px = (x, y, w, h, col) => { c.fillStyle = col; const x0 = Math.round(cx + x * p), y0 = Math.round(top + y * p); c.fillRect(x0, y0, Math.round(cx + (x + w) * p) - x0, Math.round(top + (y + h) * p) - y0); };
  const L = BOAT_LEN / 2;
  for (let r = 0; r < BOAT_ROWS; r++) {
    const l = -L + r * .9 + (r === 0 ? 0 : 1), rt = L - r * 1.25 + (r < 3 ? 2 : 0), w = rt - l;                    // stern (left) is blunt, the bow (right) sweeps up and in
    const col = r === 0 ? "#d9a05a" : r === 1 ? "#b7773a" : r === 2 || r === 3 ? "#c0392b" : r % 2 ? "#8a5428" : "#9a6030";
    px(l, r, w, 1, col);
    px(l, r, 1, 1, "#3a210d"); px(rt - 1, r, 1, 1, "#3a210d");                                                 // outline
    if (r >= 4 && r < BOAT_ROWS - 1) for (let x = Math.ceil(l + 5); x < rt - 2; x += 11) px(x + (r % 2) * 4, r, 1, 1, "#4a2d14");   // plank seams
  }
  px(-L + 6.5, BOAT_ROWS - 1, BOAT_LEN - 11, 1, "#3a210d");                                                    // keel
  px(L - 1.5, -2, 3, 2, "#d9a05a"); px(L - .5, -3, 2, 1, "#3a210d"); px(L - 1.5, -2, 1, 2, "#3a210d");         // the prow curls up
  px(-L + 1, 0, 1, 1, "#fff3d0"); px(-L + 3, 0, BOAT_LEN - 9, 1, "#e8b872");                                     // light on the gunwale
  px(-L + 1, 4, 3, 2, "#fff3d0"); px(-L + 2, 4.5, 1, 1, "#c0392b");                                              // a little name plate on the stern
  c.fillStyle = "rgba(10,60,95,.5)"; const y0 = Math.round(top + BOAT_WROW * p); c.fillRect(Math.round(cx - L * p - 2), y0, Math.round(BOAT_LEN * p + 4), Math.round(4 * p));   // under the waterline
}
function drawBoatScene(W, H, t, ft, still) {
  const bg = sceneBackground(W, H), g = boatGeom(W, H), p = g.p, k = W / 900;
  ctx.drawImage(bg.canvas, 0, 0, bg.canvas.width * PX, bg.canvas.height * PX);
  for (const [cx, cy, s, sp] of BOAT_CLOUDS) { const span = W + PX * 30, x = (((cx * W + ft * sp / 1000) % span) + span) % span - PX * 15; boatCloud(ctx, x, cy * H, s); }
  // gentle waves: short light dashes that slide and bob, more of them (and bigger) toward the viewer
  const top = H * BOAT_HORIZON;
  for (let i = 0; i < 34; i++) {
    const rowF = ((i * 37) % 97) / 97, y = top + PX * 3 + rowF * (H - top - PX * 6), sz = PX * (2 + Math.floor(rowF * 4) + i % 3), dir = i % 2 ? 1 : -1;
    const x = (((i * 211 + dir * ft * .012 * (1 + i % 3) + Math.sin(ft / 900 + i) * PX * 2) % (W + sz)) + W + sz) % (W + sz) - sz / 2;
    ctx.fillStyle = i % 3 ? "rgba(255,255,255,.3)" : "rgba(190,235,250,.4)"; ctx.fillRect(snap(x), snap(y + Math.sin(ft / 700 + i * 1.7) * PX), sz, PX);
  }
  const cx = BOAT.x * W, wl = H * BOAT_WL, bob = still ? 0 : Math.sin(ft / 800) * 2.2 * k + Math.sin(ft / 330) * .6 * k, tilt = still ? 0 : (Math.sin(ft / 1150 + 1) * 1.1 + Math.sin(ft / 410) * .25) * Math.PI / 180;
  // wake: dashes behind the stern, bigger the faster, fading out after the boat stops
  if (BOAT.wake > .02) {
    const back = -BOAT.wdir, sx = cx + back * BOAT_LEN * .45 * p;
    for (let i = 0; i < 7; i++) {
      const a = BOAT.wake * (1 - i / 7) * .7, d = (i * 7 + ((ft / 60) % 7)) * k * 1.4, w = (10 + i * 3) * k;
      ctx.fillStyle = `rgba(255,255,255,${a.toFixed(2)})`;
      ctx.fillRect(snap(sx + back * d - (back < 0 ? w : 0)), snap(wl + 5 * k + i * 1.5), Math.round(w / PX) * PX, PX);
      ctx.fillRect(snap(sx + back * d * .8 - (back < 0 ? w * .6 : 0)), snap(wl - 3 * k - i * 1.5), Math.round(w * .6 / PX) * PX, PX);
    }
  }
  // the boat and the fisherman, bobbing and tilting around the waterline
  ctx.save(); ctx.translate(cx, wl + bob); ctx.rotate(tilt); ctx.translate(-cx, -wl);
  const top0 = wl - BOAT_WROW * p;                                                          // top of the gunwale (row BOAT_WROW is the waterline)
  FCFG.x = cx - 21 * p; FCFG.y = top0 + 6 * p - 36 * p; FCFG.p = p; FCFG.outfit = "harbor";   // he sits in the stern, his lower legs behind the hull
  drawFisherman(ctx, FCFG, fisherPoseFor(F.phase, t), t, still);
  boatHull(ctx, cx, top0, p);
  ctx.restore();
  const dx = FISHER.tipX - cx, dy = FISHER.tipY - wl, c = Math.cos(tilt), s = Math.sin(tilt);   // the rod tip after the same turn, where the line starts
  ROD_TIP = TIP; TIP.x = (cx + dx * c - dy * s) / W; TIP.y = (wl + bob + dx * s + dy * c) / H;
  ctx.strokeStyle = "rgba(255,255,255,.55)"; ctx.lineWidth = 2; const ry = wl + bob + 1, rr = (BOAT_LEN * .56) * p;      // a little ripple ring round the hull
  ctx.beginPath(); ctx.ellipse(cx, ry + 2, rr + (still ? 0 : Math.sin(ft / 500) * 2 * k), 4 * k + 1, 0, 0, 7); ctx.stroke();
}
