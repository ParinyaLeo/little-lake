/* ===================== FISHING ===================== */
// Fishing scene, bite timing and the reeling minigame. Loaded after state.js, before screens.js.
let island = "harbor";   // island currently being fished (chosen on the Town Map)
const cv = $("sceneCanvas"), ctx = cv.getContext("2d");
let ROD_TIP = { x: .36, y: .25 }; const BOB = { x: .58, y: .66 };

/* ===================== ISLAND SCENES =====================
   Each island is either a picture file (image) or a painter that draws pixel art onto a small canvas
   (1 art pixel = PX screen pixels). The painted background is drawn once and cached; only the light
   effects (fx) are drawn every frame, so phones stay smooth.
   To use a picture instead of a painter later:  frost: { image: "assets/frost.jpg", rod: { x: .3, y: .3 } }
   (rod = where the rod tip is in the picture, as 0-1 fractions of width and height). */
const PX = 3;
const SCENES = {
  harbor: { image: "assets/harbor.jpg", rod: { x: .34, y: .31 } },
  frost:  { paint: paintFrost,  fx: fxSnow },
  desert: { paint: paintDesert, fx: fxHeat },
  forest: { paint: paintForest, fx: fxWaterfall },
  secret: { paint: paintSecret, fx: fxStars },
};
const DEFAULT_ROD = { x: .36, y: .25 };
for (const k in SCENES) if (SCENES[k].image) { SCENES[k].img = new Image(); SCENES[k].img.src = SCENES[k].image; }
const REDUCED = window.matchMedia ? matchMedia("(prefers-reduced-motion: reduce)") : null;
let sceneBg = null;   // cached painted background: { key, canvas, info }

function fitCanvas() { const r = cv.getBoundingClientRect(); if (r.width) { cv.width = 900; cv.height = Math.round(900 * r.height / r.width); } ROD_TIP = SCENES[island].rod || DEFAULT_ROD; }
window.addEventListener("resize", () => current === "fishing" && fitCanvas());
let F = { phase: "idle" }, raf = null, timers = [];
function later(fn, ms) { const t = setTimeout(fn, ms); timers.push(t); return t; }
function clearTimers() { timers.forEach(clearTimeout); timers = []; }

/* ---------- pixel painting helpers (art-pixel coordinates) ---------- */
function rect(g, x, y, w, h, col) { g.fillStyle = col; g.fillRect(Math.round(x), Math.round(y), Math.max(1, Math.round(w)), Math.max(1, Math.round(h))); }
function line(g, x0, y0, x1, y1, col) { const n = Math.ceil(Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0))); for (let i = 0; i <= n; i++) rect(g, x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n, 1, 1, col); }
function disc(g, cx, cy, r, col) { for (let dy = -r; dy <= r; dy++) { const half = Math.sqrt(r * r - dy * dy); rect(g, cx - half, cy + dy, half * 2, 1, col); } }
function rng(seed) { return () => (seed = seed * 16807 % 2147483647) / 2147483647; }
// banded vertical gradient with a dithered row where two bands meet
function bands(g, w, y0, y1, cols) {
  for (let i = 0; i < cols.length; i++) {
    const a = Math.round(y0 + (y1 - y0) * i / cols.length), b = Math.round(y0 + (y1 - y0) * (i + 1) / cols.length);
    rect(g, 0, a, w, b - a, cols[i]);
    if (i) { g.fillStyle = cols[i - 1]; for (let x = a % 2; x < w; x += 2) g.fillRect(x, a, 1, 1); }
  }
}
// hills / mountains filled column by column; slopes facing right are shaded
function ridge(g, w, bottom, topAt, lit, shaded, crest) {
  for (let x = 0; x < w; x++) {
    const t = Math.round(topAt(x)), right = topAt(x + 1) > topAt(x);
    rect(g, x, t, 1, bottom - t, right ? shaded : lit);
    if (crest) rect(g, x, t, 1, 1, crest);
  }
}
function water(g, w, h, top, cols, glint) {
  bands(g, w, top, h, cols);
  const r = rng(9); for (let i = 0; i < 36; i++) rect(g, r() * w, top + 3 + r() * (h - top - 4), 3 + r() * 8, 1, glint);
}
function pine(g, x, base, ht, dark, lit, snow) {
  rect(g, x - 1, base - ht * .18, 2, ht * .18, "#4a2d14");
  for (let i = 0; i < 3; i++) {
    const t0 = base - ht + i * ht * .25, th = ht * .4, wd = ht * (.2 + i * .07);
    for (let r = 0; r < th; r++) {
      const half = Math.round(wd * r / th), y = t0 + r;
      rect(g, x - half, y, half + 1, 1, lit); rect(g, x + 1, y, half, 1, dark);
      if (snow && r < th * .35) rect(g, x - half, y, half + 1, 1, "#f4f9ff");
    }
  }
}
function palm(g, x, base, ht, lean) {
  let tx = x, ty = base - ht;
  for (let i = 0; i <= ht; i++) {
    const p = i / ht, xx = x + lean * p * p, y = base - i;
    rect(g, xx - 1, y, 3, 1, (i >> 1) % 2 ? "#8a5a2b" : "#6b4420");
    if (i === Math.round(ht)) { tx = xx; ty = y; }
  }
  for (const [a, len] of [[-3.3, .8], [-2.8, 1], [-2.2, 1.1], [-1.6, .7], [-.9, 1.1], [-.3, 1], [.2, .8]]) {
    const L = ht * .5 * len;
    for (let s = 0; s < L; s++) {
      const fx = tx + Math.cos(a) * s, fy = ty + Math.sin(a) * s + s * s / (L * 2.2);
      rect(g, fx, fy, 2, 1, "#3f8f35"); rect(g, fx, fy - 1, 1, 1, "#62b24c");
    }
  }
  rect(g, tx - 2, ty + 1, 2, 2, "#5a3a1a"); rect(g, tx + 1, ty + 2, 2, 2, "#6b4420");
}
function cloud(g, x, y, s) { rect(g, x, y, s * 3, s * .6, "#ffffff"); rect(g, x + s * .5, y - s * .5, s * 1.4, s * .6, "#ffffff"); rect(g, x + s * .3, y + s * .5, s * 2.6, s * .25, "#dbeef8"); }
// wooden dock with an angler sitting on a tackle box (same pose on every painted island)
function dockAndAngler(g, w, h, rod, o) {
  const deck = Math.round(h * .56), dx = Math.round(w * .3);
  for (let x = 6; x < dx; x += 22) { rect(g, x, deck + 3, 4, h * .3, "#4a2d14"); rect(g, x + 3, deck + 3, 1, h * .3, "#3a210d"); }
  rect(g, 0, deck, dx, 4, "#8a5a2b"); rect(g, 0, deck + 3, dx, 1, "#5a3a1a");
  for (let x = 7; x < dx; x += 8) rect(g, x, deck, 1, 3, "#6b4420");
  rect(g, 0, deck - 1, dx, 1, o.deckTop || "#a8743f");
  const s = h / 125, ox = Math.round(w * .15), R = (x, y, ww, hh, col) => rect(g, ox + x * s, deck + y * s, ww * s, hh * s, col);
  R(0, -5, 9, 5, "#8a5428"); R(0, -5, 9, 1, "#a8743f");                                   // tackle box
  R(4, -9, 9, 3, o.pants); R(11, -7, 3, 7, o.pants); R(11, -1, 4, 1, "#3a2a1a");          // legs + boots
  R(2, -19, 8, 11, o.shirt); R(8, -19, 2, 11, shade(o.shirt, -.25));                       // body
  R(7, -16, 7, 3, o.shirt); R(13, -17, 3, 3, "#f1c27d");                                    // arm + hand
  R(3, -25, 6, 6, "#f1c27d"); R(8, -23, 1, 1, "#3a2a1a");                                   // head + eye
  if (o.scarf) { R(2, -19, 8, 2, o.scarf); R(1, -18, 2, 5, o.scarf); }
  R(0, -27, 12, 2, o.hat); R(3, -31, 7, 4, shade(o.hat, .15)); R(3, -28, 7, 1, o.band);    // straw hat
  line(g, ox + 15 * s, deck - 16 * s, rod.x * w, rod.y * h, "#3b2a1a");                      // rod
}

/* ---------- painters: (art canvas, width, height, rod tip) -> info for the effects ---------- */
function paintFrost(g, w, h, rod) {
  bands(g, w, 0, h * .46, ["#8fc6ec", "#a6d3f1", "#bfe0f6", "#d6ecfa", "#e9f5fd"]);
  const far = x => h * (.31 - .1 * Math.abs(Math.sin(x * .023 + .5)) - .05 * Math.abs(Math.sin(x * .061)));
  for (let x = 0; x < w; x++) {                                                             // snowy mountains
    const t = Math.round(far(x)), right = far(x + 1) > far(x);
    rect(g, x, t, 1, h * .46 - t, right ? "#8ea9c3" : "#a9c1d8");
    rect(g, x, t, 1, Math.max(1, (h * .31 - t) * .7), right ? "#d2e2f0" : "#f4f9ff");
  }
  ridge(g, w, h * .53, x => h * (.41 - .035 * Math.sin(x * .045 + 1) - .02 * Math.sin(x * .13)), "#eef6fd", "#dceaf5", "#ffffff");
  const r = rng(3);
  for (let x = w * .34; x < w; x += 9 + r() * 12) pine(g, x, h * (.5 + r() * .02), h * (.12 + r() * .08), "#24493f", "#33604f", true);
  rect(g, 0, h * .52, w, 1, "#c9dcec");
  water(g, w, h, h * .53, ["#86bfe4", "#74b0da", "#629fcd", "#548fbf", "#4680b0"], "#d8ecfa");
  for (const [fx, fy, fw] of [[.74, .6, 16], [.9, .79, 22], [.38, .9, 14], [.06, .97, 18]]) {   // ice floes
    rect(g, w * fx, h * fy, fw, 2, "#f4f9ff"); rect(g, w * fx + 2, h * fy + 2, fw - 4, 1, "#bcd8ee");
  }
  dockAndAngler(g, w, h, rod, { shirt: "#c0392b", pants: "#4a4a5a", hat: "#e0b04a", band: "#2b4e9b", scarf: "#2e7dd1", deckTop: "#f4f9ff" });
  return { water: .53 };
}
function paintDesert(g, w, h, rod) {
  bands(g, w, 0, h * .46, ["#ff9a52", "#ffad62", "#ffc078", "#ffd394", "#ffe4b4"]);
  disc(g, w * .8, h * .17, h * .1, "#ffe08a"); disc(g, w * .8, h * .17, h * .08, "#fff3b0");
  ridge(g, w, h * .5, x => h * (.35 - .04 * Math.sin(x * .018) - .025 * Math.sin(x * .047 + 2)), "#eab26a", "#dda055", "#f7cf90");
  palm(g, w * .47, h * .37, h * .1, 2);
  ridge(g, w, h * .53, x => h * (.43 - .03 * Math.sin(x * .03 + 1)), "#d9964c", "#c98840", "#eeb470");
  rect(g, 0, h * .5, w, h * .05, "#f0cf8a"); rect(g, 0, h * .545, w, 1, "#d9b06a");
  water(g, w, h, h * .55, ["#56d6c8", "#45c6b9", "#36b3a8", "#2a9f97", "#208a85"], "#b8fff4");
  for (let y = h * .5; y < h * .72; y++) { const xs = w * (.8 + (y / h - .5) * .7); rect(g, xs, y, w - xs, 1, "#f0cf8a"); rect(g, xs, y, 2, 1, "#d9b06a"); }
  for (const [rx, ry] of [[.7, .93], [.86, .75]]) { rect(g, w * rx, h * ry, 9, 4, "#9a7a5a"); rect(g, w * rx + 1, h * ry - 1, 6, 1, "#b8987a"); }
  palm(g, w * .88, h * .64, h * .44, -8); palm(g, w * .96, h * .68, h * .34, 6);
  for (const x of [w * .31, w * .335, w * .36, w * .78, w * .8]) for (let k = 0; k < 3; k++) {     // reeds
    const ht = 6 + k * 3 + (x % 3); rect(g, x + k * 2, h * .56 - ht, 1, ht, "#5d8a3a"); rect(g, x + k * 2, h * .56 - ht, 1, 3, "#7a4a2a");
  }
  dockAndAngler(g, w, h, rod, { shirt: "#e8e0c8", pants: "#8a6a3a", hat: "#e0b04a", band: "#c0392b" });
  return { water: .55, heat: [.27, .5] };
}
function paintForest(g, w, h, rod) {
  bands(g, w, 0, h * .42, ["#6cc0e6", "#84cbea", "#9cd6ef", "#b6e1f4", "#cdebf7"]);
  cloud(g, w * .1, h * .09, 12); cloud(g, w * .48, h * .15, 8);
  ridge(g, w, h * .5, x => h * (.25 - .05 * Math.abs(Math.sin(x * .012 + .4)) - .02 * Math.sin(x * .05)), "#6aa883", "#5d9d78");
  let r = rng(5);
  for (let x = 0; x < w * .8; x += 5 + r() * 5) pine(g, x, h * (.44 + r() * .02), h * (.08 + r() * .05), "#2f6b4c", "#3f7f5a");
  const f0 = w * .82, f1 = w * .9, fy0 = h * .1, fy1 = h * .55;
  for (let x = Math.round(w * .74); x < w; x++) {                                            // cliff
    const t = h * (.06 + .04 * Math.abs(Math.sin(x * .21)) + Math.max(0, (w * .78 - x) / w) * 3);
    rect(g, x, t, 1, h * .56 - t, x % 5 ? "#6f7a80" : "#5a646a"); rect(g, x, t, 1, 2, "#4f8f3a");
  }
  r = rng(8); for (let i = 0; i < 30; i++) rect(g, w * (.75 + r() * .25), h * (.15 + r() * .38), 3, 1, "#59636a");
  rect(g, f0, fy0, f1 - f0, fy1 - fy0, "#a8def3"); rect(g, f0, fy0, 1, fy1 - fy0, "#e8f8ff"); rect(g, f1 - 1, fy0, 1, fy1 - fy0, "#7fc4e4");
  r = rng(11);
  for (let x = w * .33; x < w * .79; x += 8 + r() * 9) pine(g, x, h * .53, h * (.16 + r() * .08), "#1b4630", "#2a6343");
  rect(g, 0, h * .52, w, h * .03, "#3f7f3a"); rect(g, 0, h * .545, w, 1, "#2f5f2a");
  water(g, w, h, h * .55, ["#3fa3c2", "#3596b5", "#2d88a7", "#257a99", "#1e6c8a"], "#d0f0ff");
  r = rng(11); for (let x = w * .33; x < w * .79; x += 8 + r() * 9) { r(); for (let y = 0; y < h * .05; y += 2) rect(g, x - 1 + (y % 4 ? 1 : 0), h * .556 + y, 2, 1, "#2b7790"); }   // wavy tree reflections
  rect(g, f0 - 4, fy1 - 1, f1 - f0 + 8, 3, "#ffffff");
  for (const [px, py, fl] of [[.42, .88, true], [.8, .8, false], [.93, .93, true], [.68, .97, false]]) {   // lily pads
    rect(g, w * px - 4, h * py, 9, 2, "#4f9a3a"); rect(g, w * px - 3, h * py - 1, 7, 1, "#62b24c"); rect(g, w * px + 1, h * py, 2, 1, "#2d88a7");
    if (fl) rect(g, w * px - 2, h * py - 2, 2, 2, "#f7a8c8");
  }
  dockAndAngler(g, w, h, rod, { shirt: "#2f7d3a", pants: "#5a4a3a", hat: "#e0b04a", band: "#8a3a2a" });
  return { water: .55, fall: [f0 / w, fy0 / h, f1 / w, fy1 / h] };
}
function paintSecret(g, w, h, rod) {
  bands(g, w, 0, h * .53, ["#120d2e", "#181238", "#1f1645", "#271b55", "#302066", "#3a2876"]);
  const r = rng(21); for (let i = 0; i < 40; i++) rect(g, r() * w, r() * h * .45, 1, 1, "#9f96d8");
  disc(g, w * .8, h * .17, h * .08, "#fff6c2"); rect(g, w * .79, h * .14, 3, 2, "#eee0a0"); rect(g, w * .82, h * .19, 2, 2, "#eee0a0");
  ridge(g, w, h * .53, x => h * (.38 - .07 * Math.abs(Math.sin(x * .02 + 1))), "#251b55", "#211849");
  ridge(g, w, h * .53, x => h * (.46 - .03 * Math.sin(x * .05)), "#1a133b", "#17113a");
  water(g, w, h, h * .53, ["#1d4277", "#183b6d", "#143463", "#102c57", "#0c244a"], "#5f7fc0");
  for (let y = h * .55; y < h * .96; y += 3) { const wd = 16 * (1 - (y / h - .55) * 1.5); rect(g, w * .8 - wd / 2 + Math.sin(y) * 2, y, Math.max(2, wd), 1, "#e8dfa8"); }
  rect(g, w * .27, h * .47, 3, 4, "#ffd54f"); rect(g, w * .27 - 1, h * .46, 5, 1, "#5a3a1a"); rect(g, w * .275, h * .51, 1, h * .05, "#5a3a1a");   // lantern
  dockAndAngler(g, w, h, rod, { shirt: "#5e35b1", pants: "#3a3a5a", hat: "#e0b04a", band: "#ff80ab" });
  return { water: .53, lantern: [.27, .47] };
}

/* ---------- animated effects (screen pixels, snapped to the art-pixel grid) ---------- */
const snap = v => Math.floor(v / PX) * PX;
function fxWater(c, W, H, t, info) {
  const top = H * info.water; c.fillStyle = "rgba(255,255,255,.33)";
  for (let i = 0; i < 16; i++) {
    const y = top + PX * 2 + ((i * 37) % 97) / 97 * (H - top - PX * 4), dir = i % 2 ? 1 : -1;
    c.fillRect(snap((((i * 131 + dir * t * .015 * (1 + i % 3)) % W) + W) % W), snap(y), PX * (3 + i % 4), PX);
  }
}
function fxSnow(c, W, H, t) {
  c.fillStyle = "rgba(255,255,255,.92)";
  for (let i = 0; i < 70; i++) {
    const sp = 18 + (i % 5) * 9, size = PX * (i % 4 === 0 ? 2 : 1);
    const y = ((i * 53.7) % H + t * sp / 1000) % H, x = (((i * 97.3 + Math.sin(t / 900 + i) * 14 + t * .004 * (i % 3)) % W) + W) % W;
    c.fillRect(snap(x), snap(y), size, size);
  }
}
// heat shimmer: rows of the horizon slide sideways a little
function fxHeat(c, W, H, t, info, bg) {
  const r0 = Math.floor(H * info.heat[0] / PX), r1 = Math.ceil(H * info.heat[1] / PX);
  for (let r = r0; r < r1; r++) { const off = Math.round(Math.sin(t / 240 + r * .8) * 1.4) * 2; if (off) c.drawImage(bg, 0, r, bg.width, 1, off, r * PX, bg.width * PX, PX); }
}
function fxWaterfall(c, W, H, t, info) {
  const [x0, y0, x1, y1] = info.fall.map((v, i) => i % 2 ? v * H : v * W), len = y1 - y0;
  c.fillStyle = "rgba(255,255,255,.75)";
  for (let x = snap(x0) + PX; x < x1 - PX; x += PX * 2) for (let k = 0; k < 3; k++) c.fillRect(x, snap(y0 + (t * .16 + x * 7.3 + k * len / 3) % len), PX, PX * 4);
  c.fillStyle = "rgba(255,255,255,.9)";
  for (let i = 0; i < 7; i++) { const s = PX * Math.round(2.5 + 1.5 * Math.sin(t / 180 + i * 1.7)); c.fillRect(snap(x0 - PX * 3 + i * (x1 - x0 + PX * 6) / 7), snap(y1 - s / 2), s, s); }
}
function fxStars(c, W, H, t, info) {
  const r = rng(77);
  for (let i = 0; i < 26; i++) {
    const x = snap(r() * W), y = snap(r() * H * .42), a = .3 + .7 * Math.abs(Math.sin(t / 700 + i * 1.3));
    c.fillStyle = `rgba(255,250,220,${a.toFixed(2)})`; c.fillRect(x, y, PX, PX);
    if (i % 6 === 0) { c.fillRect(x - PX, y, PX * 3, PX); c.fillRect(x, y - PX, PX, PX * 3); }
  }
  const gx = info.lantern[0] * W + PX * 2, gy = info.lantern[1] * H + PX * 2, rad = 46 * W / 900;   // soft lantern glow
  const glow = c.createRadialGradient(gx, gy, 0, gx, gy, rad);
  glow.addColorStop(0, `rgba(255,213,79,${(.4 + .12 * Math.sin(t / 300)).toFixed(2)})`); glow.addColorStop(1, "rgba(255,213,79,0)");
  c.fillStyle = glow; c.fillRect(gx - rad, gy - rad, rad * 2, rad * 2);
}
function sceneBackground(W, H) {
  const key = `${island}|${W}|${H}`;
  if (!sceneBg || sceneBg.key !== key) {
    const c = document.createElement("canvas"); c.width = Math.ceil(W / PX); c.height = Math.ceil(H / PX);
    const info = SCENES[island].paint(c.getContext("2d"), c.width, c.height, ROD_TIP);
    sceneBg = { key, canvas: c, info };
  }
  return sceneBg;
}
// splash when the bobber lands (k: 0 -> 1 over the splash)
function splash(bx, by, k, W) {
  const s = W / 900, a = (1 - k).toFixed(2), r = (10 + k * 34) * s;
  ctx.strokeStyle = `rgba(255,255,255,${a})`; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(bx, by + 6, r, r / 3, 0, 0, 7); ctx.stroke();
  for (let i = 0; i < 9; i++) {
    const ang = (i - 4) * .32, v = (50 + (i % 3) * 18) * s, size = i % 2 ? 4 : 6;
    const x = bx + Math.sin(ang) * v * k * 1.3, y = by - (Math.cos(ang) * v * 2.6 * k - 120 * s * k * k);
    ctx.fillStyle = i % 2 ? `rgba(255,255,255,${a})` : `rgba(190,235,255,${a})`; ctx.fillRect(Math.round(x - size / 2), Math.round(y - size / 2), size, size);
  }
}

function drawScene(t) {
  const W = cv.width, H = cv.height, sc = SCENES[island], still = !!(REDUCED && REDUCED.matches), ft = still ? 0 : t;
  ctx.imageSmoothingEnabled = false;
  if (sc.img) {
    ctx.fillStyle = "#7fd0f5"; ctx.fillRect(0, 0, W, H);
    if (sc.img.complete && sc.img.naturalWidth) {
      const ir = sc.img.naturalWidth / sc.img.naturalHeight, cr = W / H;
      let sw = sc.img.naturalWidth, sh = sc.img.naturalHeight;
      if (ir > cr) sw = sh * cr; else sh = sw / cr;
      ctx.drawImage(sc.img, 0, 0, sw, sh, 0, 0, W, H);
    }
    if (sc.fx) sc.fx(ctx, W, H, ft, sc.info || {}, null);
  } else {
    const bg = sceneBackground(W, H);
    ctx.drawImage(bg.canvas, 0, 0, bg.canvas.width * PX, bg.canvas.height * PX);
    fxWater(ctx, W, H, ft, bg.info);
    if (sc.fx) sc.fx(ctx, W, H, ft, bg.info, bg.canvas);
  }
  // line + bobber
  if (F.phase !== "idle") {
    let bx = W * BOB.x, by = H * BOB.y;
    if (F.phase === "casting") { const k = Math.min(1, (t - F.castAt) / 500); bx = W * (ROD_TIP.x + (BOB.x - ROD_TIP.x) * k); by = H * (ROD_TIP.y + (BOB.y - ROD_TIP.y) * k) - Math.sin(k * Math.PI) * H * .25; }
    else if (F.phase === "waiting") by += Math.sin(t / 300) * 3;
    else if (F.phase === "bite") by += 8 + Math.sin(t / 40) * 5;
    else if (F.phase === "reeling") by += Math.sin(t / 60) * 6;
    const since = t - F.castAt - 500;                                                         // ms since the bobber landed
    ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(W * ROD_TIP.x, H * ROD_TIP.y); ctx.quadraticCurveTo(W * .45, H * .45, bx, by); ctx.stroke();
    if (F.phase === "waiting" && since > 0) {                                                // soft rings while waiting
      ctx.lineWidth = 2;
      for (let j = 0; j < 2; j++) {
        const p = still ? .35 + j * .3 : (since / 1700 + j * .5) % 1, r = (8 + p * 44) * W / 900;
        ctx.strokeStyle = `rgba(255,255,255,${(.55 * (1 - p)).toFixed(2)})`; ctx.beginPath(); ctx.ellipse(bx, by + 6, r, r / 3.2, 0, 0, 7); ctx.stroke();
      }
    }
    if (F.phase === "bite" || F.phase === "reeling") {
      ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 2;
      const r = 10 + ((t / 8) % 30); ctx.beginPath(); ctx.ellipse(bx, by + 6, r, r / 3, 0, 0, 7); ctx.stroke();
    }
    ctx.fillStyle = "#3b2a1a"; ctx.fillRect(bx - 1, by - 14, 2, 4);                          // bobber
    ctx.fillStyle = "#e53935"; ctx.fillRect(bx - 6, by - 10, 12, 8); ctx.fillStyle = "#ff8a80"; ctx.fillRect(bx - 4, by - 9, 3, 2);
    ctx.fillStyle = "#fff"; ctx.fillRect(bx - 6, by - 2, 12, 7); ctx.fillStyle = "#c8d0d6"; ctx.fillRect(bx + 3, by - 2, 3, 7);
    if (F.phase !== "casting" && !still && since >= 0 && since < 450) splash(bx, by, since / 450, W);
    F.bobPos = { x: bx / W, y: by / H };
  }
}
function loop(t) {
  drawScene(t);
  if (F.phase === "reeling") {
    const dt = Math.min(.05, (t - (F.lastT || t)) / 1000); F.lastT = t;
    F.pos += F.dir * F.speed * dt;
    if (F.pos > 1) { F.pos = 1; F.dir = -1; } if (F.pos < 0) { F.pos = 0; F.dir = 1; }
    $("marker").style.left = `calc(${F.pos * 100}% - 3px)`;
  }
  raf = requestAnimationFrame(loop);
}
function startLoop() { if (!raf) raf = requestAnimationFrame(loop); }
function stopFishing() { clearTimers(); F = { phase: "idle" }; $("meter").style.display = "none"; $("bang").style.display = "none"; if (raf) cancelAnimationFrame(raf); raf = null; }

function renderFishingHud() {
  $("fBag").textContent = `${S.bag.length} / ${S.bagMax}`;
  renderBaitBtn($("baitBtn"), F.phase !== "idle");
  // small icons for the island rewards that are active (tap for details; hover shows the same text)
  $("bonuses").innerHTML = ISLAND_IDS.filter(i => S.mastery[i]).map(i => { const I = ISLANDS[i], tip = `${I.reward}: ${I.effect}`;
    return `<button class="bonus" data-tip="${tip}" title="${tip}" aria-label="${tip}"><span class="ico i-${I.icon}"></span></button>`; }).join("");
  $("fBagBtn").classList.toggle("glow", bagFull());
  const a = $("actBtn");
  if (F.phase === "idle") {
    a.disabled = bagFull(); a.textContent = bagFull() ? "BAG FULL" : "CAST"; a.className = "btn green";
    $("fMsg").textContent = bagFull() ? "Bag full! Sell fish or buy a bigger bag." : `${ISLANDS[island].name}: Ready? Cast your line!`;
    $("dots").textContent = ""; $("hearts").innerHTML = "";
  }
  fitCanvas(); startLoop();
}

// USE BAIT button (fishing HUD and Tackle Box): shows on/off and how much bait is left
function renderBaitBtn(b, busy) {
  const on = S.useBait && S.bait > 0;
  b.innerHTML = `<span class="ico i-bait"></span>` + (S.bait ? `USE BAIT: ${S.useBait ? "ON" : "OFF"} (${S.bait})` : "NO BAIT (SHOP)");
  b.classList.toggle("on", on); b.setAttribute("aria-pressed", on); b.disabled = !S.bait || !!busy;
  b.title = `Bait: ${rarePlus(true)}% chance of Rare or better (${rarePlus(false)}% without). One bait per cast while ON.`;
}
function toggleBait() { if (F.phase !== "idle" || !S.bait) return; S.useBait = !S.useBait; save(); toast(S.useBait ? "Bait ON: better chance of Rare+ fish." : "Bait OFF: saving your bait."); render(); }
$("baitBtn").onclick = toggleBait;
$("bonuses").onclick = e => { const b = e.target.closest(".bonus"); if (b) toast(b.dataset.tip); };

function pickFish(withBait) {
  if (island === "secret") return FISH.find(f => f.island === "secret");
  const w = rarityWeights(withBait);
  const tiers = ["Common", "Rare", "Epic", "Legendary"];
  let r = Math.random() * w.reduce((a, b) => a + b), tier = tiers[0];
  for (let i = 0; i < 4; i++) { if (r < w[i]) { tier = tiers[i]; break; } r -= w[i]; }
  const pool = FISH.filter(f => f.island === island && f.rarity === tier);
  return pool[Math.floor(Math.random() * pool.length)];
}

$("actBtn").onclick = () => {
  if (F.phase === "idle") cast();
  else if (F.phase === "bite") hook();
  else if (F.phase === "reeling") reel();
};
function cast() {
  if (bagFull()) { toast("Your bag is full."); return; }
  const usedBait = S.useBait && S.bait > 0; if (usedBait) { S.bait--; save(); }
  F = { phase: "casting", castAt: performance.now(), fish: pickFish(usedBait), usedBait };
  sfx.cast(); $("actBtn").disabled = true; $("actBtn").textContent = "...";
  $("fMsg").textContent = usedBait ? `Cast with bait (${S.bait} left)... waiting` : "Waiting for a bite..."; renderFishingHud();
  $("actBtn").disabled = true;
  later(() => { F.phase = "waiting"; }, 500);
  later(bite, 500 + 1000 + Math.random() * 4000);   // 1-5 s random wait
}
function bite() {
  F.phase = "bite"; sfx.bite(); vibrate(200);
  const b = $("bang"); b.style.display = "block"; b.style.left = (F.bobPos ? F.bobPos.x * 100 : 58) + "%"; b.style.top = (F.bobPos ? F.bobPos.y * 100 : 66) + "%";
  const a = $("actBtn"); a.disabled = false; a.textContent = "HOOK!"; a.className = "btn red glow";
  $("fMsg").textContent = "A fish is biting! Tap HOOK!";
  F.biteTimer = later(() => { if (F.phase === "bite") escape("Too slow! The fish swam away."); }, 1000);
}
function hook() {
  clearTimeout(F.biteTimer); $("bang").style.display = "none";
  const d = DIFF[F.fish.rarity];
  Object.assign(F, { phase: "reeling", pos: 0, dir: 1, hits: 0, misses: 0, lastT: 0,
    speed: d.speed * (S.mastery.frost ? .8 : 1), zoneW: d.zone });
  newZone(); $("meter").style.display = "block";
  const a = $("actBtn"); a.textContent = "REEL"; a.className = "btn green";
  $("fMsg").textContent = "Press REEL inside the green zone!"; updateDots(); sfx.hit();
}
function newZone() { F.zoneX = .1 + Math.random() * (.8 - F.zoneW); $("zone").style.left = F.zoneX * 100 + "%"; $("zone").style.width = F.zoneW * 100 + "%"; }
// HIT dots, and one heart per miss you can still afford (a miss with no hearts left = the fish escapes)
function updateDots() {
  $("dots").textContent = "HIT " + "●".repeat(F.hits) + "○".repeat(3 - F.hits);
  const max = allowedMiss(), left = Math.max(0, max - F.misses), H = $("hearts");
  H.innerHTML = `<span class="l">${left ? "MISSES LEFT" : "NO MISSES LEFT!"}</span>` +
    Array.from({ length: max }, (_, i) => `<span class="ico ${i < left ? "i-heart" : "i-heart0"}"></span>`).join("");
  H.classList.toggle("last", !left); H.setAttribute("aria-label", `${misses(left)} left`);
}
function reel() {
  const inside = F.pos >= F.zoneX && F.pos <= F.zoneX + F.zoneW;
  if (inside) { F.hits++; sfx.hit(); vibrate(40); } else { F.misses++; sfx.miss(); vibrate([30, 30, 30]); }
  updateDots();
  if (F.hits >= 3) return caught();
  if (F.misses > allowedMiss()) return escape("Too many misses. The fish escaped!");
  F.pos = 0; F.dir = 1; newZone();                    // marker resets and keeps moving after every hit or miss
}
function escape(text) {
  sfx.fail(); vibrate(300); $("meter").style.display = "none"; $("bang").style.display = "none";
  clearTimers(); F = { phase: "idle" }; renderFishingHud(); $("fMsg").textContent = text; toast(text);
}
function caught() {
  const f = F.fish; clearTimers(); F = { phase: "idle" }; $("meter").style.display = "none";
  const skew = Math.pow(Math.random(), 1.6);
  const weight = +(f.min + (f.max - f.min) * skew).toFixed(2);
  const mid = (f.min + f.max) / 2;
  const price = Math.round(f.price * (0.7 + 0.6 * (weight / mid) / 2) * (S.mastery.harbor ? 1.2 : 1));
  const rec = !S.records[f.id] || weight > S.records[f.id];
  const isNew = !S.discovered[f.id];
  S.pending = { fishId: f.id, weight, price, isNew, rec };   // saved, so the catch survives a reload
  S.discovered[f.id] = true; S.totalCaught++; if (rec) S.records[f.id] = weight;
  if (f.rarity === "Mythical") S.mythical = true;
  save();
  sfx.catch(); vibrate([60, 40, 120]); confetti();
  go("result");
  if (f.rarity === "Mythical") setTimeout(() => banner("You caught the Lake Guardian!", "You completed Little Lake. A trophy has been added to your Home screen."), 600);
  else setTimeout(checkMastery, 400);
}
function renderResult() {
  const p = S.pending; if (!p) return;
  const f = fishById(p.fishId), full = bagFull();
  drawFish($("resCanvas"), f); $("result").dataset.rarity = f.rarity;   // frame + glow colour
  $("resName").textContent = f.name + (p.isNew ? "  (NEW!)" : "");
  $("resRarity").innerHTML = `<span class="rar-${f.rarity}">${f.rarity}</span> · ${ISLANDS[f.island].name}`;
  $("resWeight").textContent = `Weight: ${p.weight} kg`;
  $("resPrice").textContent = `Value: ${fmt(p.price)} coins` + (S.mastery.harbor ? " (Golden Hook +20%)" : "");
  $("resRecord").textContent = p.rec ? "NEW RECORD!" : "";
  // full bag: never drop the fish silently; offer a clear choice instead of KEEP
  $("result").classList.toggle("full", full);
  if (full) {
    const c = cheapest(), cf = fishById(S.bag[c].fishId);
    $("fullText").textContent = `Your bag is full (${S.bag.length} / ${S.bagMax}). Make room for the ${f.name} or let it go.`;
    $("sellOneBtn").innerHTML = `<span class="ico i-coin"></span>SELL A FISH`;
    $("sellOneInfo").textContent = `SELL A FISH sells your cheapest fish (${cf.name}, ${fmt(S.bag[c].price)} coins) and keeps the ${f.name}.`;
  }
}
const cheapest = () => S.bag.reduce((m, b, i) => b.price < S.bag[m].price ? i : m, 0);
// put the waiting catch in the bag, with a toast and a bouncing bag counter
function keepCatch(prefix = "") {
  const p = S.pending; if (!p) return go("fishing");
  if (bagFull()) return renderResult();
  S.bag.push({ fishId: p.fishId, weight: p.weight, price: p.price, time: Date.now() }); S.pending = null; save();
  toast(`${prefix}+1 ${fishById(p.fishId).name} added to bag`); go("fishing"); bump("fBag");
}
$("keepBtn").onclick = () => keepCatch();
$("sellOneBtn").onclick = () => {
  if (!S.pending || !bagFull()) return keepCatch();
  const i = cheapest(), b = S.bag[i]; S.bag.splice(i, 1); S.coins += b.price; sfx.coin();
  keepCatch(`Sold ${fishById(b.fishId).name} for ${fmt(b.price)} coins. `);
};
$("resBagBtn").onclick = () => go("bag");
function releaseCatch() { S.pending = null; save(); toast("Released. It stays in your Collection Book."); go("fishing"); }
$("releaseBtn").onclick = releaseCatch;
$("fullRelease").onclick = releaseCatch;
