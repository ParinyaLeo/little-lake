/* ===================== FISHING FROM A BOAT (Playtest 3) =====================
   THE SWITCH: BOAT_MODE below. true = on every island (Harbor, Frost, Desert, Forest, Little Lake) the fisherman sits in a small boat on the water and the player slides the boat left and
   right between casts (A / Left arrow, D / Right arrow, or the two on-screen buttons). false = the old pier / shore look, no buttons and the old landing spot, exactly as before this feature.
   It is `let` (not const) only so the tests can flip it; to turn the boat off for good change `true` to `false` on the next line.                                                         */
let BOAT_MODE = true;
/* How it works (js/boat.js is loaded after fishing.js and uses its helpers: CROP, TIP, FCFG, F, CH, POWER, SCENES, drawFisherman ...):
   - Each scene has `boat: { w, h, y, x, x0, x1, water }` in js/fishing.js, all in PICTURE pixels: w x h = the picture size, y = the waterline of the boat, x = start centre, x0..x1 = the allowed
     range of the boat centre (so it never touches the pier, the shore, rocks or ice), water = the open-water rectangle used for the landing (the equivalent of tools/water_masks; the Harbor has no
     mask file, its rectangle was read from the photo). The boat is drawn at the same pixel scale as the old fisherman (`fisher.scale`), over the picture that is already on the canvas;
     the old fisherman is not drawn at all (drawScene calls boatDraw() instead of drawFisherman(); the painted fallback scenes skip their painted angler).
   - BOAT.u = the boat centre in picture pixels (so it stays on the same spot of the picture when the window is resized); it is reset to the scene's start when the island changes.
     Visible range = the scene range, cut to what the cropped canvas shows (the whole hull and the rod tip stay inside the scene with a small margin).
   - Movement: BOAT_SPEED (.20 = 20% of the visible width per second), only while F.phase is "idle" and no power charge runs (boatCan()); ignored (the boat holds still) while charging, casting,
     waiting, bite, reeling and on the Result screen, so the line never changes mid-fish. Key release, blur and the page being hidden stop it.
   - boatLanding(): the same landing line as landing() (POWER.near > POWER.far, same jitter); the x offsets are measured from the boat (BOAT_REF = where the old fisherman stood), then clamped to the
     scene's water rectangle (and to BOAT_LAND_MAX of the canvas), so the bobber never lands on land, ice, rocks or off the scene. Everything after the landing is unchanged. */
const BOAT_SPEED = .20, BOAT_REF = .18, BOAT_MARGIN = .03, BOAT_LAND_MAX = .965, BOAT_LAND_PAD = 24;   // pad = picture pixels kept clear of the water rectangle's edge
const BOAT = { u: 0, scene: "", kL: false, kR: false, tL: false, tR: false, v: 0, wake: 0, wdir: 1, lastT: 0, hinted: false, cx: 0, wy: 0, p: 1 };
const BOAT_LEN = 60, BOAT_ROWS = 13, BOAT_WROW = 9;                                        // hull size in art pixels, and the row where the waterline is
const boatScene = () => SCENES[island] && SCENES[island].boat ? SCENES[island] : null;
// the allowed range of the boat centre (picture pixels): the scene's range cut to what the canvas shows
function boatRange() {
  const sc = boatScene(); if (!sc) return null;
  const b = sc.boat, V = CROP, hh = BOAT_LEN / 2 * sc.fisher.scale, m = BOAT_MARGIN * V.sw;
  const lo = Math.max(b.x0, V.sx + hh + m), hi = Math.max(lo, Math.min(b.x1, V.sx + V.sw - hh - m - .02 * V.sw));
  return { lo, hi, hh };
}
const boatClamp = u => { const r = boatRange(); return r ? Math.min(r.hi, Math.max(r.lo, u)) : u; };
// the bobber's landing spot: the old near > far line with the old jitter; x counted from the boat, then kept inside the scene's open water
function boatLanding(power, jitter) {
  const sc = boatScene(), V = CROP, w = sc.boat.water, pad = BOAT_LAND_PAD;
  const p = Math.min(1, Math.max(0, power + (Math.random() * 2 - 1) * jitter));
  const bf = (BOAT.u - V.sx) / V.sw;                                                         // the boat centre as a share of the canvas width
  let x = bf + (POWER.near.x - BOAT_REF) + (POWER.far.x - POWER.near.x) * p, y = POWER.near.y + (POWER.far.y - POWER.near.y) * p + (Math.random() - .5) * .02;
  const xmax = Math.min(BOAT_LAND_MAX, (w.x1 - pad - V.sx) / V.sw), ymin = (w.y0 + pad - V.sy) / V.sh, ymax = (w.y1 - pad - V.sy) / V.sh;
  x = Math.min(xmax, Math.max(Math.min(bf + .06, xmax), x)); y = Math.min(ymax, Math.max(ymin, y));
  return { x, y, p };
}
// where the reel pulls the fish to (shadow code in fishing.js): just ahead of the bow, a little below the waterline
function boatDock(dk, W, H) { dk.x = Math.min(W * .95, BOAT.cx + W * .03); dk.y = Math.min(H * .9, BOAT.wy + H * .05); }

/* ---------- input ---------- */
const boatCan = () => BOAT_MODE && current === "fishing" && F.phase === "idle" && !CH.on && !document.querySelector(".banner.show");
function boatDir() { return (BOAT.kL || BOAT.tL ? -1 : 0) + (BOAT.kR || BOAT.tR ? 1 : 0); }
function boatInputReset() { BOAT.kL = BOAT.kR = BOAT.tL = BOAT.tR = false; $("boatL").classList.remove("down"); $("boatR").classList.remove("down"); }
const boatKey = e => { const c = e.code, k = (e.key || "").toLowerCase(); return c === "KeyA" || c === "ArrowLeft" || k === "a" || k === "arrowleft" ? -1 : c === "KeyD" || c === "ArrowRight" || k === "d" || k === "arrowright" ? 1 : 0; };
document.addEventListener("keydown", e => {
  const d = boatKey(e); if (!d || e.ctrlKey || e.metaKey || e.altKey) return;
  if (!BOAT_MODE || typeof current === "undefined" || current !== "fishing" || document.querySelector(".banner.show")) return;   // A and D do nothing on other screens
  if (d < 0) BOAT.kL = true; else BOAT.kR = true;
  if ((e.key || "").startsWith("Arrow")) e.preventDefault();                                          // no page scroll from the arrows while fishing
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
// shows / hides the buttons and gives the once-per-session hint (called by renderFishingHud)
function boatSync() {
  $("boatPad").style.display = BOAT_MODE ? "" : "none";
  if (!BOAT_MODE) { boatInputReset(); return; }
  if (!BOAT.hinted) { BOAT.hinted = true; setTimeout(() => toast("A / D or the arrow buttons: move the boat"), 250); }
}
// one frame of movement (called from loop() before the scene is drawn)
function boatStep(t) {
  const dt = Math.min(.05, Math.max(0, (t - BOAT.lastT) / 1000)); BOAT.lastT = t;
  if (!BOAT_MODE) return;
  const can = boatCan(), dir = can ? boatDir() : 0, sc = boatScene();
  for (const id of ["boatL", "boatR"]) { const b = $(id); if (b.disabled === can) b.disabled = !can; }   // greyed out while the line is out
  if (sc && CROP.sw > 1) BOAT.u = boatClamp(BOAT.u + dir * BOAT_SPEED * CROP.sw * dt);
  BOAT.v = dir; if (dir) BOAT.wdir = dir;
  BOAT.wake += ((dir ? 1 : 0) - BOAT.wake) * Math.min(1, dt * (dir ? 8 : 3));                // the wake grows quickly and fades slowly
}
// for the tests only: the boat in picture pixels, as a share of the canvas, its allowed range, and the canvas pixels
function boatState() {
  const sc = boatScene(), r = boatRange(), V = CROP;
  return { u: BOAT.u, x: (BOAT.u - V.sx) / V.sw, lo: r && r.lo, hi: r && r.hi, loX: r && (r.lo - V.sx) / V.sw, hiX: r && (r.hi - V.sx) / V.sw, v: BOAT.v, wake: BOAT.wake, cx: BOAT.cx, wy: BOAT.wy, p: BOAT.p,
    scene: BOAT.scene, can: boatCan(), hinted: BOAT.hinted, hullHalf: r && r.hh, water: sc && sc.boat.water, mode: BOAT_MODE };
}

/* ---------- drawing ---------- */
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
// the boat and the fisherman on the scene's water (called by drawScene instead of drawFisherman). CROP must describe the picture that was just drawn (image px -> canvas px: x * W / CROP.sw).
function boatDraw(sc, W, H, t, still) {
  const b = sc.boat, V = CROP, k = W / V.sw, p = sc.fisher.scale * k, ft = still ? 0 : t;
  if (BOAT.scene !== island) { BOAT.scene = island; BOAT.u = b.x; BOAT.wake = 0; }              // a new island: the boat starts at that scene's start spot
  BOAT.u = boatClamp(BOAT.u);                                                                 // also after a resize / a different crop
  const cx = (BOAT.u - V.sx) * k, wl = (b.y - V.sy) * k;
  BOAT.cx = cx; BOAT.wy = wl; BOAT.p = p;
  const bob = still ? 0 : (Math.sin(ft / 800) * .55 + Math.sin(ft / 330) * .15) * p, tilt = still ? 0 : (Math.sin(ft / 1150 + 1) * 1.1 + Math.sin(ft / 410) * .25) * Math.PI / 180;
  const u = Math.max(1, Math.round(p / 1.5)) ;                                                // wake dash height in canvas px (about one art pixel)
  if (BOAT.wake > .02) {                                                                      // wake: dashes behind the stern, bigger the faster, fading out after the boat stops
    const back = -BOAT.wdir, sx = cx + back * BOAT_LEN * .45 * p;
    for (let i = 0; i < 7; i++) {
      const a = BOAT.wake * (1 - i / 7) * .8, d = (i * 7 + ((ft / 60) % 7)) * p * .35, w = (10 + i * 3) * p * .25;
      ctx.fillStyle = `rgba(255,255,255,${a.toFixed(2)})`;
      ctx.fillRect(Math.round(sx + back * d - (back < 0 ? w : 0)), Math.round(wl + p * 1.2 + i * u * .4), Math.round(w), u);
      ctx.fillRect(Math.round(sx + back * d * .8 - (back < 0 ? w * .6 : 0)), Math.round(wl - p * .8 - i * u * .4), Math.round(w * .6), u);
    }
  }
  ctx.save(); ctx.translate(cx, wl + bob); ctx.rotate(tilt); ctx.translate(-cx, -wl);        // the boat and the fisherman bob and tilt together around the waterline
  const top0 = wl - BOAT_WROW * p;                                                            // top of the gunwale
  FCFG.x = cx - 21 * p; FCFG.y = top0 + 6 * p - 36 * p; FCFG.p = p; FCFG.outfit = sc.fisher.outfit;   // he sits in the stern, his lower legs behind the hull
  drawFisherman(ctx, FCFG, fisherPoseFor(F.phase, t), t, still);
  boatHull(ctx, cx, top0, p);
  ctx.restore();
  const dx = FISHER.tipX - cx, dy = FISHER.tipY - wl, c = Math.cos(tilt), s = Math.sin(tilt);   // the rod tip after the same turn, where the line starts
  ROD_TIP = TIP; TIP.x = (cx + dx * c - dy * s) / W; TIP.y = (wl + bob + dx * s + dy * c) / H;
  ctx.strokeStyle = "rgba(255,255,255,.55)"; ctx.lineWidth = 2;                                // a little ripple ring round the hull
  ctx.beginPath(); ctx.ellipse(cx, wl + bob + 3, BOAT_LEN * .56 * p + (still ? 0 : Math.sin(ft / 500) * 2), p * 1.1 + 1, 0, 0, 7); ctx.stroke();
}
