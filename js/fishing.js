/* ===================== FISHING ===================== */
// Fishing scene, bite timing and the reeling minigame. Loaded after state.js, before screens.js.
let island = "harbor";   // island currently being fished (chosen on the Town Map)
const cv = $("sceneCanvas"), ctx = cv.getContext("2d");
let ROD_TIP = { x: .36, y: .25 }; const BOB = { x: .58, y: .66 };

/* ===================== ISLAND SCENES =====================
   Each island is either a picture file (image) or a painter that draws pixel art onto a small canvas
   (1 art pixel = PX screen pixels). The painted background is drawn once and cached; only the light
   effects (fx) are drawn every frame, so phones stay smooth.
   A picture scene: image (file), anchor ([x, y] 0-1: which part stays in view when the picture is cropped to the
   canvas; default [0, 0] = top-left), and rod (where the rod tip is in the picture, as 0-1 fractions) or fisher.
   Pictures load after the Title screen appears (preloadScenes). Until one is ready, or if it fails to load, an
   island with a painter shows its painted scene instead. To swap in an artist's picture, change image (and fisher).
   A picture can also have a fisher config (js/fisherman.js): the figure baked into the photo is patched out
   (patch / rodClear, in photo pixels) and an animated one is drawn at x, y (top-left of his 28x36 art grid)
   with scale photo pixels per art pixel. Then the line starts at his drawn rod tip instead of rod. */
const PX = 3;
const SCENES = {
  harbor: { image: "assets/harbor.jpg", rod: { x: .34, y: .31 },
    fisher: { x: 194, y: 182, scale: 3.6, outfit: "harbor",
      rodClear: [386, 132, 262, 268, 24, 26, 120],   // old rod + line: from (x0,y0) to (x1,y1), band left/right width, copied from dx
      patch: [[192, 174, 98, 84, 100, 0], [227, 258, 63, 26, 115, 0],                                  // water behind him
        [200, 254, 6, 24, -10, 0], [206, 254, 6, 24, -16, 0], [212, 254, 6, 24, -22, 0], [218, 254, 6, 24, -28, 0], [224, 254, 4, 24, -34, 0],   // chest lid
        [228, 284, 61, 30, -112, -15]] } },                                                            // dock under his legs
  // painted by tools/make_backgrounds.py (1920x800, 4 image pixels per art pixel); the fisherman sits on the crate on the dock
  frost:  { image: "assets/frost.png",  anchor: [0, .8], fisher: { x: 232, y: 400, scale: 6, outfit: "frost" }, picFx: fxSnow, paint: paintFrost,  fx: fxSnow },
  desert: { image: "assets/desert.png", anchor: [0, .8], fisher: { x: 232, y: 400, scale: 6, outfit: "desert" }, paint: paintDesert, fx: fxHeat },
  forest: { image: "assets/forest.png", anchor: [0, .8], fisher: { x: 232, y: 400, scale: 6, outfit: "forest" }, paint: paintForest, fx: fxWaterfall },
  secret: { image: "assets/secret.png", anchor: [0, .8], fisher: { x: 232, y: 400, scale: 6, outfit: "secret" }, paint: paintSecret, fx: fxStars },
};
const DEFAULT_ROD = { x: .36, y: .25 }, NO_ANCHOR = [0, 0];
// start loading every picture (once); sc.img is only set when the picture is ready, sc.failed if it can't load
function preloadScenes() {
  for (const k in SCENES) {
    const sc = SCENES[k]; if (!sc.image || sc.loading) continue;
    const im = new Image(); sc.loading = true;
    im.onload = () => { if (im.naturalWidth) sc.img = im; else sc.failed = true; };
    im.onerror = () => { sc.failed = true; };       // keep the painted scene
    im.src = sc.image;
  }
}
const REDUCED = window.matchMedia ? matchMedia("(prefers-reduced-motion: reduce)") : null;
/* Power cast (Playtest 1, part 4): hold CAST (button, Space or the scene) longer than POWER.quick ms to charge a power meter in the reel meter's
   space, release to throw. Only WHERE the bobber lands changes (a point on the near > far line, plus a small random offset); the wait,
   bite, HOOK, REEL, odds and rewards are untouched. A quick press (< POWER.quick) is the normal medium cast (POWER.mid). */
const POWER = { quick: 250, fill: 1200, mid: .5, near: { x: .48, y: .72 }, far: { x: .68, y: .60 }, jitterQuick: .05, jitterHold: .05 };   // jitter = uniform +- share of the throw range   // mid = BOB = (.58, .66)
const CH = { on: false, src: "", pid: -1, t0: 0, shown: false };
let sceneBg = null;   // cached painted background: { key, canvas, info }
const TIP = { x: 0, y: 0 }, FCFG = { x: 0, y: 0, p: 1, outfit: "harbor" };   // reused every frame (no allocations)
const CROP = { sx: 0, sy: 0, sw: 1, sh: 1 };              // part of the picture shown on the canvas (image pixels)

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

/* Floats (Playtest 1, part 12b): the bobber is cosmetic gear (S.floatEq, bought in the Shop), NOT linked to the bait. The float equipped when the cast starts is stored in
   F.floatId, so it never changes mid-cast. Each float is a 12 x 19 art-pixel map (FLOAT_MAPS, made by tools/make_float_sprites.py) drawn at 1 screen pixel per art pixel (Playtest 1, part 12c: back to the
   original 12 x 19 px size of the part 12 bobber), with a 1px dark outline and bold colours. Anchor: (bx, by) is the waterline = the top edge of row FLOAT_WL (rows below it sit in the
   water); the fishing line ties on at the top (row 0 = FLOAT_TOP px above the anchor). The bob, dip, splash and HOOK timing all work on (bx, by) and are unchanged. */
/* FLOAT MAPS BEGIN */
const FLOAT_MAPS = {   // generated by tools/make_float_sprites.py: 12 x 19 art pixels, 1 screen pixel each; row 14 = the waterline, row 0 = where the line ties on
  classic: ["....OOOO....", ".....OO.....", ".....OO.....", "....OOOO....", "...OBBBBO...", "..OLBBBBBO..", ".OBLBBBBBDO.", ".OBBBBBBBDO.", "OBBBBBBBBDDO", "OBBBBBBBBDDO", "ODDDDDDDDDDO", "OAAAAAAAAaaO", "OAAAAAAAAaaO", "OAAAAAAAAaaO", ".OAAAAAAAaO.", ".OAAAAAAAaO.", "..OAAAAAAO..", "...OAAAAO...", "....OOOO...."],
  candy: ["....OOOO....", ".....OO.....", ".....OO.....", "....OOOO....", "...OBAAAO...", "..OBAAABBO..", ".OBAAABBBaO.", ".OAAABBBAaO.", "OAAABBBAAaDO", "OAABBBAAADDO", "OABBBAAABDDO", "OBBBAAABBDaO", "OBBAAABBBaaO", "OBAAABBBAaaO", ".OAABBBAAaO.", ".OABBBAAADO.", "..OBBAAABO..", "...OAAABO...", "....OOOO...."],
  frog: ["....OOOO....", ".OOO.OO.OOO.", "OWWWOBBOWWWO", "OWKWOBBOWKWO", "OGGGBBBBGGGO", "OBBBBBBBBBBO", "OBDBBBBBBDBO", "OBBDDDDDDBBO", ".OBBBBBBBBO.", "..OOOOOOOO..", "..OMMMMMmO..", "..OMMMMMmO..", "..ONNNNNmO..", "..OMMMMMmO..", "..OMMMMMmO..", "..OMMMMMmO..", "...OMMMMO...", "....OMMO....", "....OOOO...."],
  duck: ["..OOOO......", "...OO.......", "...OO.......", "...OOO......", "..OBBBO.....", ".OBLLBBO....", "OBBBBBKDO...", "OBBBBBBDOOO.", "OBBBBBBDOAAO", "OBBBBBBDOOO.", "OBBBBBBDO...", "OBBBBBBDO...", "OBLLLDBDO...", "OBDDDDBDO...", "OBBBBBBDO...", "OBBBBBBDO...", ".OBBBBBO....", "..OBBBO.....", "...OOO......"],
  golden: ["....OOOO....", ".....OO.....", ".....OO.....", "....OOOO....", "...OBBBBO...", "..OLBBBBBO..", ".OBLBBBBBDO.", ".OBLBBBBBDO.", "OBBBBBBBBDDO", "OBBBBBBBBDDO", "OBBBBBBBBDDO", "OLLLLLLLLLLO", "OAAAAAAAADDO", "OAAAAAAAADDO", ".OAAAAAAADO.", ".OAAAAAAADO.", "..OAAAAAAO..", "...OAAAAO...", "....OOOO...."],
};
const FLOAT_BLINK = { frog: ["....OOOO....", ".OOO.OO.OOO.", "OGGGOBBOGGGO", "ODDDOBBODDDO", "OGGGBBBBGGGO", "OBBBBBBBBBBO", "OBDBBBBBBDBO", "OBBDDDDDDBBO", ".OBBBBBBBBO.", "..OOOOOOOO..", "..OMMMMMmO..", "..OMMMMMmO..", "..ONNNNNmO..", "..OMMMMMmO..", "..OMMMMMmO..", "..OMMMMMmO..", "...OMMMMO...", "....OMMO....", "....OOOO...."] };   // eyes shut (~120 ms every 3 s)
const FLOAT_ICON_MAPS = { frog: ["..OOOO....OOOO..", ".OBBBBO..OBBBBO.", "OBWWKWBOOBWWKWBO", "OBWKKWBOOBWKKWBO", "OBBBBBBOOBBBBBBO", "OBPPBBBBBBBBPPBO", "OBPPBDBBBBDBPPBO", "OBBBBBDDDDBBBBBO", ".OBBBBBBBBBBBBO.", "..OOOOOOOOOOOO..", "...OMMMMMMMmO...", "...ONNNNNNNmO...", "...OMMMMMMMmO...", "...OMMMMMMMmO...", "....OMMMMMMO....", "....OOOOOOOO...."] };   // 16 x 16 UI preview, shown at 2x
/* FLOAT MAPS END */
// palette per float: O outline, B body, L light, D shade, A second colour, a its shade, W white, K black
const FLOAT_LOOK = {
  classic: { O: "#3a0d0d", B: "#e53935", L: "#ff9e9e", D: "#a32121", A: "#ffffff", a: "#b8c4cc", W: "#ffffff", K: "#111111" },
  candy:   { O: "#6a0f45", B: "#ff4fa0", L: "#ffffff", D: "#c2185b", A: "#ffffff", a: "#f3b6d4", W: "#ffffff", K: "#111111" },
  frog:    { O: "#0b3a12", B: "#43c94f", L: "#d4f58a", D: "#2a8a30", G: "#7fe06a", P: "#ff9fb0", M: "#a8612a", m: "#6b3a17", N: "#e3aa6a", A: "#ffffff", a: "#c8e6c9", W: "#ffffff", K: "#0a0a0a" },
  duck:    { O: "#5e3b00", B: "#fff03a", L: "#ffffb0", D: "#e8c800", A: "#ff8a00", a: "#d46a00", W: "#ffffff", K: "#111111" },
  golden:  { O: "#5a3d00", B: "#f7b000", L: "#ffe27a", D: "#c26a00", A: "#e08a00", a: "#9a5200", W: "#ffffff", K: "#111111" },
};
const FLOAT_U = 1, FLOAT_W = 12, FLOAT_WL = 14, FLOAT_TOP = FLOAT_WL * FLOAT_U;      // art pixel size, grid width, waterline row, px from the line tie to the anchor
let BOBBER_LAST = "classic";                                                         // the float drawn last, for the tests (like fisherRodStyle())
const bobberStyleKey = () => BOBBER_LAST;
function drawFloat(c, bx, by, id, t, still) {
  const key = FLOAT_MAPS[id] ? id : "classic", map = (key === "frog" && !still && t % 3000 >= 2880) ? FLOAT_BLINK.frog : FLOAT_MAPS[key], pal = FLOAT_LOOK[key], u = FLOAT_U;
  BOBBER_LAST = key; const x0 = Math.round(bx) - FLOAT_W * u / 2, y0 = Math.round(by) - FLOAT_TOP;
  for (let y = 0; y < map.length; y++) {
    const row = map[y];
    for (let x = 0; x < FLOAT_W; x++) { const k = row[x]; if (k !== ".") { c.fillStyle = pal[k]; c.fillRect(x0 + x * u, y0 + y * u, u, u); } }
  }
  if (key === "golden" && !still) {                                                  // a small 2-frame sparkle every 500 ms (none with reduced motion), inside the 12 x 19 box
    const f = Math.floor(t / 500) % 2, cx = x0 + (f ? 8 : 4), cy = y0 + (f ? 12 : 6);
    c.fillStyle = "#fff7b0"; c.fillRect(cx - 1, cy, 3, 1); c.fillRect(cx, cy - 1, 1, 3);
    c.fillStyle = "#ffffff"; c.fillRect(cx, cy, 1, 1);
  }
}
// a small picture of a float for the Shop, Tackle Box, popup and the FLOAT chip: the same sprite as a data URL (made once per float)
const FLOAT_ICONS = {};
function floatIconUrl(id) {
  if (!FLOAT_ICONS[id]) {
    const m = FLOAT_ICON_MAPS[id] || FLOAT_MAPS[id], c = document.createElement("canvas"); c.width = m[0].length; c.height = m.length; const g = c.getContext("2d"), pal = FLOAT_LOOK[id];
    m.forEach((row, y) => { for (let x = 0; x < row.length; x++) if (row[x] !== ".") { g.fillStyle = pal[row[x]]; g.fillRect(x, y, 1, 1); } });
    FLOAT_ICONS[id] = c.toDataURL();
  }
  return FLOAT_ICONS[id];
}
const floatIcon = id => `<span class="ico fl${FLOAT_ICON_MAPS[id] ? " big" : ""}" style="background-image:url(${floatIconUrl(id)})"></span>`;

/* Fish shadow (Playtest 2, part 1): VISUAL ONLY. A dark, semi-transparent silhouette of the real F.fish swims to the bobber while you wait, nibbles, darts on the bite and thrashes
   during REEL. Nothing here changes the rules: the wait still ends at F.biteAt (the old 1-5 s random wait, only stored now), HOOK, REEL, hits, misses, odds and saves are untouched.
   The state lives in SH (not in F) so the shadow can still fade after F is reset (escape / catch). It only runs for a real cast (F.biteAt is set by cast()), so a hand-made F draws no shadow.
   Positions are canvas pixels (the canvas is always 900 px wide). The shadow starts on the deep side (right, a little up), so it never crosses the dock on the left; the end of the
   reel pulls it (and the float it drags) toward SH.dk, a point of open water in front of the dock. No allocations per frame: SH and SHO are reused, sprites are cached per fish id. */
const SH = { on: false, mode: "", cast: -1, pm: "", fish: null, size: 2, x: 0, y: 0, face: 1, alpha: 0, bx: 0, by: 0, ox: 0, oy: 0, dip: 0, nib: 0, dx: 0, prog: 0, lastT: 0, lx: 0, lastMiss: 0, kickAt: -1e9, t0: 0, fx: 0, fy: 0, fa: 1, k: 1, W: 900, H: 400, dk: { x: 0, y: 0 } };
const SHO = { x: 0, y: 0, m: "approach", nib: 0 }, SH_KY = .42, SH_CACHE = {};
const shadowClear = () => { SH.on = false; SH.mode = ""; SH.cast = -1; SH.pm = ""; SH.ox = SH.oy = SH.dip = 0; };
function shadowSprite(f) { let c = SH_CACHE[f.id]; if (!c) { c = document.createElement("canvas"); silhouette(c, f); SH_CACHE[f.id] = c; } return c; }   // one dark colour, 24 x 16
function shadowSize(f) { const m = (f.min + f.max) / 2, t = Math.min(1, Math.max(0, (Math.log10(m) + 1.5) / 3.5)); return 1.6 + 1.6 * t; }   // screen px per art pixel: heavier fish = bigger, only a little
const shPulse = (w, a) => { const v = Math.sin(Math.PI * Math.min(1, Math.max(0, (w - a) / .3))); return v * v; };
// where the shadow is while waiting, relative to the bobber, for u = 0..1 over the wait: approach (0-.5), one circle (.5-.8), two nibbles (.8-1); ends 8 px under the float
function shWaitOffset(u, k, still) {
  const S0x = 170 * k, S0y = -24 * k, by0 = 8 * k; SHO.nib = 0;
  if (still) { SHO.m = "approach"; SHO.x = S0x * (1 - u); SHO.y = S0y + (by0 - S0y) * u; return; }   // reduced motion: a straight line, no circling
  const R0 = 34 * k, R1 = 12 * k, a0 = -.3;
  if (u < .5) { const p = u / .5, e = 1 - (1 - p) * (1 - p), cx = R0 * Math.cos(a0), cy = R0 * SH_KY * Math.sin(a0) + by0;
    SHO.m = "approach"; SHO.x = S0x + (cx - S0x) * e; SHO.y = S0y + (cy - S0y) * e + Math.sin(p * 6) * 6 * k * (1 - p); }
  else if (u < .8) { const v = (u - .5) / .3, r = R0 + (R1 - R0) * v, a = a0 + 6.2832 * v; SHO.m = "circle"; SHO.x = r * Math.cos(a); SHO.y = r * SH_KY * Math.sin(a) + by0; }
  else { const w = (u - .8) / .2, ex = R1 * Math.cos(a0), ey = R1 * SH_KY * Math.sin(a0) + by0; SHO.m = "nibble"; SHO.x = ex * (1 - w); SHO.y = ey + (by0 - ey) * w; SHO.nib = Math.min(1, shPulse(w, .1) + shPulse(w, .55)); }
}
function shadowLeave() { if (!SH.on || !SH.fish) return; SH.mode = "leave"; SH.t0 = performance.now(); SH.fx = SH.x; SH.fy = SH.y; SH.fa = SH.alpha; SH.ox = SH.oy = SH.dip = 0; }   // missed HOOK / escaped
function shadowCatch(reeled) {                                                              // third hit: pulled to the surface in front of the dock, a splash, then the Result screen
  if (reeled && SH.on && SH.fish && F.biteAt) { SH.mode = "catch"; SH.t0 = performance.now(); SH.fx = SH.x; SH.fy = SH.y; SH.fa = SH.alpha; SH.ox = SH.oy = SH.dip = 0; } else shadowClear();
}
// advances the shadow for this frame (sets SH.x / y / alpha / mode, and SH.ox / oy / dip = how the bobber follows it); true when it should be drawn
function shadowStep(t, W, H, still) {
  const s = SH, k = W / 900; s.W = W; s.H = H; s.k = k; s.ox = s.oy = s.dip = s.nib = s.dx = 0;
  s.dk.x = W * .36; s.dk.y = H * .68;
  if (F.biteAt && F.fish && (F.phase === "waiting" || F.phase === "bite" || F.phase === "reeling")) {
    if (s.cast !== F.castAt) { s.cast = F.castAt; s.fish = F.fish; s.size = shadowSize(F.fish); s.pm = ""; s.on = true; s.face = 1; s.prog = 0; s.lastMiss = 0; s.kickAt = -1e9; }
    const L = F.land || BOB, dt = Math.min(.05, Math.max(0, (t - s.lastT) / 1000)); s.lastT = t;
    s.bx = W * L.x; s.by = H * L.y;
    if (s.pm !== F.phase) { s.pm = F.phase; s.t0 = t; if (F.phase === "reeling") { s.prog = 0; s.lastMiss = F.misses; s.kickAt = -1e9; } }
    let px = 0, py = 8 * k, a = 1, dx = 0;
    if (F.phase === "waiting") {
      const since = t - F.castAt - 500, span = Math.max(1, F.biteAt - F.castAt - 500), u = Math.min(1, Math.max(0, since / span));
      shWaitOffset(u, k, still); px = SHO.x; py = SHO.y; s.mode = SHO.m; s.nib = SHO.nib; s.dip = still ? 0 : 4 * k * SHO.nib;
      a = since < 0 ? 0 : still ? Math.min(1, u / .15) : Math.min(1, since / 400);
    } else if (F.phase === "bite") {
      s.mode = "bite"; const e = (t - s.t0) / 140;
      if (!still) { px = Math.sin(Math.min(1, Math.max(0, e)) * Math.PI) * 22 * k + Math.sin(t / 35) * 3 * k; py += Math.sin(t / 50) * 2 * k; }   // a quick dart, then a tremble
    } else {
      s.mode = "reel";
      if (F.misses > s.lastMiss) { s.lastMiss = F.misses; s.kickAt = t; }                  // a miss: it darts back
      const goal = Math.max(0, F.hits / 3 - .06 * F.misses);                                // each hit pulls it a third of the way to the dock, each miss gives a little back
      s.prog += (goal - s.prog) * (still ? 1 : Math.min(1, dt * 8));
      const kick = still ? 0 : 20 * k * Math.exp(-(t - s.kickAt) / 180);
      s.ox = (s.dk.x - s.bx) * s.prog + kick; s.oy = (s.dk.y - s.by) * s.prog;             // the float is dragged along
      if (!still) { const rr = 1 + .15 * ["Common", "Rare", "Epic", "Legendary", "Mythical"].indexOf(F.fish.rarity); dx = (Math.sin(t / 55) * 9 + Math.sin(t / 21) * 3) * k * rr; py += Math.sin(t / 80) * 3 * k; }
      px = 0;
    }
    s.dx = dx; s.x = s.bx + s.ox + px + dx; s.y = Math.min(H * .9, Math.max(H * .5, s.by + s.oy + py));
    if (F.phase === "reeling" && !still) s.face = Math.sin(t / 110) > 0 ? 1 : -1;            // thrashing: it keeps turning
    else if (Math.abs(s.x - s.lx) > .05) s.face = s.x < s.lx ? -1 : 1;                       // the sprite faces right: turn to where it swims
    s.lx = s.x;
    s.alpha = a;
    return a > .01;
  }
  if (s.on && (s.mode === "leave" || s.mode === "catch")) {
    const e = Math.max(0, t - s.t0) / (s.mode === "leave" ? 1000 : FISHER_HOLD.caught);
    if (e >= 1) { shadowClear(); return false; }
    if (s.mode === "leave") { const p = still ? e : 1 - (1 - e) * (1 - e); s.face = 1; s.x = s.fx + 230 * k * p; s.y = Math.min(H * .9, Math.max(H * .5, s.fy - 30 * k * p)); s.alpha = s.fa * (1 - e); }
    else { const p = Math.min(1, e / .35), q = 1 - (1 - p) * (1 - p); s.x = s.fx + (s.dk.x - s.fx) * q; s.y = s.fy + (s.dk.y - s.fy) * q; s.alpha = e < .6 ? s.fa : s.fa * (1 - (e - .6) / .4); s.face = -1;
      if (!still && e > .45) splash(s.x, s.y, Math.min(1, (e - .45) / .45), W); }
    return s.alpha > .01;
  }
  if (s.on) shadowClear();
  return false;
}
function shadowDraw(t, still) {
  const s = SH, sp = shadowSprite(s.fish), u = s.size * s.k, w = 24 * u, h = 16 * u, rows = 8, sh = h / rows, ss = 16 / rows;
  const ring = s.mode === "bite" || s.mode === "reel" || s.nib > .05;
  if (ring && !still) {                                                                      // ripples over the shadow (they stay under the float and the line)
    ctx.lineWidth = 2;
    for (let j = 0; j < 2; j++) { const p = (t / (s.mode === "reel" ? 380 : 600) + j * .5) % 1, r = (6 + p * 30) * s.k;
      ctx.strokeStyle = `rgba(255,255,255,${(.5 * (1 - p) * Math.min(1, s.alpha)).toFixed(2)})`; ctx.beginPath(); ctx.ellipse(s.x, s.y + 2, r, r / 3.2, 0, 0, 7); ctx.stroke(); }
  }
  ctx.save(); ctx.translate(Math.round(s.x), Math.round(s.y)); ctx.scale(s.face, 1);
  ctx.globalAlpha = .18 * s.alpha; ctx.drawImage(sp, 0, 0, 24, 16, -w * .56, -h * .56, w * 1.12, h * 1.12);   // soft edge: a slightly bigger, fainter copy under the shadow
  ctx.globalAlpha = .6 * s.alpha;
  for (let r = 0; r < rows; r++) { const off = still ? 0 : Math.round(Math.sin(t / 260 + r * .9) * 1.5 * s.k); ctx.drawImage(sp, 0, r * ss, 24, ss, -w / 2 + off, -h / 2 + r * sh, w, sh + .5); }   // wavy slices = seen through water
  ctx.restore();
}
// for the tests only (not used by the UI): where the shadow is, in canvas fractions, and its distances in canvas px
function fishShadowState() {
  if (!SH.on || !SH.fish) return null;
  const bobX = SH.bx + SH.ox, bobY = SH.by + SH.oy;
  return { fishId: SH.fish.id, x: SH.x / SH.W, y: SH.y / SH.H, phase: SH.mode, alpha: SH.alpha, face: SH.face, size: SH.size, dBob: Math.hypot(SH.x - bobX, SH.y - (bobY + 8 * SH.k)), dDock: Math.hypot(SH.x - SH.dk.x, SH.y - SH.dk.y), dDockC: Math.hypot(SH.x - SH.dx - SH.dk.x, SH.y - SH.dk.y),   // C = without the thrash wiggle
   
    bob: { x: bobX / SH.W, y: bobY / SH.H }, W: SH.W, H: SH.H, prog: SH.prog };
}

function drawScene(t) {
  const W = cv.width, H = cv.height, sc = SCENES[island], still = !!(REDUCED && REDUCED.matches), ft = still ? 0 : t;
  ctx.imageSmoothingEnabled = false;
  if (sc.img || !sc.paint) {
    ctx.fillStyle = "#7fd0f5"; ctx.fillRect(0, 0, W, H);
    const img = sc.img;
    if (img) {
      const nw = img.naturalWidth, nh = img.naturalHeight, ir = nw / nh, cr = W / H, an = sc.anchor || NO_ANCHOR;
      let sw = nw, sh = nh;
      if (ir > cr) sw = sh * cr; else sh = sw / cr;                                  // cover: crop the sides or the top/bottom
      const sx = (nw - sw) * an[0], sy = (nh - sh) * an[1], k = W / sw, fc = sc.fisher;
      CROP.sx = sx; CROP.sy = sy; CROP.sw = sw; CROP.sh = sh;
      if (fc && (fc.patch || fc.rodClear) && !sc.plate) sc.plate = cleanPlate(img, fc);   // photo without the baked-in fisherman
      ctx.drawImage(sc.plate || img, sx, sy, sw, sh, 0, 0, W, H);
      ROD_TIP = TIP;
      if (fc) {
        FCFG.x = (fc.x - sx) * k; FCFG.y = (fc.y - sy) * k; FCFG.p = fc.scale * k; FCFG.outfit = fc.outfit;
        drawFisherman(ctx, FCFG, fisherPoseFor(F.phase, t), t, still);
        TIP.x = FISHER.tipX / W; TIP.y = FISHER.tipY / H;                           // the line starts at the drawn rod tip
      } else { TIP.x = (sc.rod.x * nw - sx) / sw; TIP.y = (sc.rod.y * nh - sy) / sh; }
    }
    if (sc.picFx) sc.picFx(ctx, W, H, ft);
  } else {                                                                          // painted scene (picture not ready or failed)
    ROD_TIP = sc.rod || DEFAULT_ROD;
    const bg = sceneBackground(W, H);
    ctx.drawImage(bg.canvas, 0, 0, bg.canvas.width * PX, bg.canvas.height * PX);
    fxWater(ctx, W, H, ft, bg.info);
    if (sc.fx) sc.fx(ctx, W, H, ft, bg.info, bg.canvas);
  }
  if (shadowStep(t, W, H, still)) shadowDraw(t, still);                                       // the fish under the water: below the line and the float
  // line + bobber
  if (F.phase !== "idle") {
    const L = F.land || BOB;                                                                   // where this cast lands (BOB for a medium cast)
    let bx = W * L.x, by = H * L.y;
    if (F.phase === "casting") {
      let k = Math.min(1, (t - F.castAt) / 500);
      if (sc.fisher) k = Math.max(0, (k - .4) / .6);                                      // the bobber flies after his wind-up
      bx = W * (ROD_TIP.x + (L.x - ROD_TIP.x) * k); by = H * (ROD_TIP.y + (L.y - ROD_TIP.y) * k) - Math.sin(k * Math.PI) * H * .25; }
    else if (F.phase === "waiting") by += Math.sin(t / 300) * 3 + SH.dip;                    // SH.dip = a nibble (0 without a shadow)
    else if (F.phase === "bite") by += 8 + Math.sin(t / 40) * 5;
    else if (F.phase === "reeling") { bx += SH.ox; by += Math.sin(t / 60) * 6 + SH.oy; }      // SH.ox / oy: the fish drags the float toward the dock
    const since = t - F.castAt - 500;                                                         // ms since the bobber landed
    ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2;
    const tx = W * ROD_TIP.x, ty = H * ROD_TIP.y;                                          // a drawn rod moves, so the line sags between tip and bobber
    const ey = by - FLOAT_TOP;                                                                // the line ties on at the top of the float
    const qx = sc.fisher ? (tx + bx) / 2 : W * .45, qy = sc.fisher ? (ty + ey) / 2 + (F.phase === "reeling" ? (SH.on && !still ? Math.sin(t / 45) * 3 : 0) : H * .06) : H * .45;   // taut line that wobbles while a fish fights
    ctx.beginPath(); ctx.moveTo(tx, ty); ctx.quadraticCurveTo(qx, qy, bx, ey); ctx.stroke();
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
    drawFloat(ctx, bx, by, F.floatId || S.floatEq, t, still);                                   // the float equipped when THIS cast started (F.floatId)
    if (F.phase !== "casting" && !still && since >= 0 && since < 450) splash(bx, by, since / 450, W);
    F.bobPos = { x: bx / W, y: by / H };
  }
}
function loop(t) {
  if (CH.on) chargeTick(t);
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
function stopFishing() { shadowClear(); musicDuck(false); chargeReset(true); clearTimers(); F = { phase: "idle" }; showMeter(false); $("bang").style.display = "none"; if (raf) cancelAnimationFrame(raf); raf = null; }
// the reel meter and the island progress share one fixed-size space: the meter while reeling, the progress otherwise
// (both use visibility, never display, so nothing below them moves)
function showMeter(on) { $("meter").style.visibility = on ? "visible" : "hidden"; $("isleProg").style.visibility = on ? "hidden" : "visible"; }
// "<Island>: X / 10 found" with a bar, and the island's Mastery reward (or "Mastered!"); Little Lake has its own text
function renderIsleProgress() {
  const I = ISLANDS[island], secret = island === "secret", total = secret ? 1 : 10, n = discCount(island), done = secret ? n >= 1 : !!S.mastery[island];
  const line2 = secret ? (n ? `<span class="ico i-star"></span><b>Lake Legend!</b> You caught the Lake Guardian.` : `Mythical fish: the <b>Lake Guardian</b> lives here. Good luck!`)
    : done ? `<span class="ico i-${I.icon}"></span><b class="done">★ Mastered!</b> ${I.reward} is active: ${I.effect.toLowerCase()}.`
    : `<span class="ico i-lock"></span>Mastery reward: <b>${I.reward}</b> – ${I.effect.toLowerCase()}.`;
  $("isleProg").classList.toggle("mastered", done);
  $("isleProg").innerHTML = `<div class="ip-top"><span class="ip-n">${I.name}: ${n} / ${total} found</span>` +
    `<span class="ip-bar" role="progressbar" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${n}" aria-label="${I.name} fish found"><span style="width:${n / total * 100}%"></span></span></div>` +
    `<div class="ip-reward">${line2}</div>`;
}

function renderFishingHud() {
  $("fBag").textContent = `${S.bag.length} / ${S.bagMax}`;
  // equipped rod and selected bait (tap to switch to the next one you own)
  const busy = F.phase !== "idle", b = BAITS[S.baitSel];
  $("rodChip").innerHTML = `<span class="ico i-rod-${S.rodEq}"></span><span class="k">ROD</span>${rod().short}`;
  $("rodChip").title = `${rod().name}: ${rodFx(S.rodEq)} Tap to choose a rod.`;
  $("baitChip").innerHTML = `<span class="ico i-bait-${b ? S.baitSel : "none"}"></span><span class="k">BAIT</span>` + (b ? `${b.short || b.name} x${S.baits[S.baitSel]}` : "None");
  $("baitChip").title = `${baitName(S.baitSel)}: ${oddsText(rarityWeights(S.baitSel))}. Tap to choose bait.`;
  const fl = FLOATS[S.floatEq] || FLOATS.classic;
  $("floatChip").innerHTML = `${floatIcon(S.floatEq)}<span class="k">FLOAT</span>${fl.short}`;
  $("floatChip").title = `${fl.name}: ${fl.blurb} (only a look). Tap to choose a float.`;
  $("rodChip").disabled = $("baitChip").disabled = $("floatChip").disabled = busy;
  $("homeTop").disabled = busy;                                  // HOME (part 13): only when idle, so a cast or catch is never lost
  // small icons for the island rewards that are active (tap for details; hover shows the same text)
  $("bonuses").innerHTML = ISLAND_IDS.filter(i => S.mastery[i]).map(i => { const I = ISLANDS[i], tip = `${I.reward}: ${I.effect}`;
    return `<button class="bonus" data-tip="${tip}" title="${tip}" aria-label="${tip}"><span class="ico i-${I.icon}"></span></button>`; }).join("")
    || `<span class="hint">Tap ROD, BAIT or FLOAT to change</span>`;
  $("sellTop").classList.toggle("glow", bagFull());   // SELL beside the coins glows when the bag is full
  const a = $("actBtn");
  if (F.phase === "idle") {
    a.disabled = bagFull(); a.textContent = bagFull() ? "BAG FULL" : "CAST"; a.className = "btn green";
    $("fMsg").textContent = bagFull() ? "Bag full! Sell fish or buy a bigger bag."
      : (S.holdCasts || 0) < 3 ? "Tip: hold CAST to throw farther" : `${ISLANDS[island].name}: Ready? Cast your line!`;   // the tip: until 3 hold casts
    $("dots").textContent = ""; $("hearts").innerHTML = "";
  }
  renderIsleProgress(); if (F.phase !== "reeling") showMeter(CH.on && CH.shown);
  preloadScenes(); fitCanvas(); startLoop();
}

// HUD chips open the "Choose Rod" / "Choose Bait" popup: every item with its effect and odds, pick one = 2 taps.
// Items you can't use (rod not owned, bait with 0 left) are disabled buttons, so they can't be clicked or tabbed to.
let pickKind = null;
function openPicker(kind) {
  if (F.phase !== "idle" || current !== "fishing") return;          // never mid-catch
  pickKind = kind; renderPicker();
  openModal("pickBox", `pick-${kind === "rod" ? S.rodEq : kind === "float" ? S.floatEq : S.baitSel}`);
}
// label for an item you can't use yet: full text, or just the price on narrow screens (CSS picks one)
const lockedLabel = price => `<span class="long">${price} COINS · Buy in Shop</span><span class="short">🪙${price}</span>`;
function renderPicker() {
  const isRod = pickKind === "rod", isFloat = pickKind === "float", charm = S.mastery.forest ? " +1 miss from Master's Charm." : "";
  $("pickTitle").textContent = isRod ? "Choose Rod" : isFloat ? "Choose Float" : "Choose Bait";
  $("pickSub").textContent = isRod ? `Odds are shown with your current bait (${baitName(S.baitSel)}).`
    : isFloat ? "Floats only change how your bobber looks. Buy more in the Shop."
    : `Odds are shown with your ${rod().name}. One bait is used per cast.`;
  const card = (id, icon, name, fx, odds, state, label) =>
    `<button type="button" class="pick-card ${state}" id="pick-${id}" data-nosound data-id="${id}"${state === "locked" ? " disabled" : ""}>` +
    (icon.startsWith("fl:") ? floatIcon(icon.slice(3)) : `<span class="ico i-${icon}"></span>`) + `<span class="grow"><span class="top"><b>${name}</b><span class="chip">${label}</span></span>` +
    `<span class="fx">${fx}</span><span class="odds">${odds}</span></span></button>`;
  $("pickList").innerHTML = isFloat
    ? FLOAT_IDS.map(id => {
        const f = FLOATS[id], own = S.floatsOwned.includes(id), eq = S.floatEq === id;
        return card(id, `fl:${id}`, f.name, f.blurb, "Only a look: no effect on fishing.", eq ? "equipped" : own ? "" : "locked", eq ? "EQUIPPED" : own ? "EQUIP" : lockedLabel(f.price));
      }).join("")
    : isRod
    ? ROD_IDS.map(id => {
        const r = RODS[id], own = S.rods.includes(id), eq = S.rodEq === id;
        return card(id, `rodlg-${id}`, r.name, rodFx(id) + (own ? charm : ""), oddsText(rarityWeights(S.baitSel, id)),
          eq ? "equipped" : own ? "" : "locked", eq ? "EQUIPPED" : own ? "EQUIP" : lockedLabel(r.price));
      }).join("")
    : ["none", ...BAIT_IDS].map(id => {
        const b = BAITS[id], n = b ? S.baits[id] : 0, sel = S.baitSel === id, have = !b || n > 0;
        return card(id, `bait-${id}`, b ? `${b.name} x${n}` : "No bait", b ? b.blurb : "Saves your bait for later.", oddsText(rarityWeights(id)),
          sel ? "equipped" : have ? "" : "locked", sel ? "EQUIPPED" : have ? "USE" : lockedLabel(b.price));
      }).join("");
}
$("rodChip").onclick = () => openPicker("rod");
$("baitChip").onclick = () => openPicker("bait");
$("floatChip").onclick = () => openPicker("float");
$("pickList").onclick = e => {
  const c = e.target.closest(".pick-card"); if (!c || c.disabled) return;
  const id = c.dataset.id, kind = pickKind;
  closeModal("pickBox");                                               // focus goes back to the chip
  if (kind === "rod" && id !== S.rodEq) equipRod(id);                  // equip / select toast and re-render the HUD
  if (kind === "bait" && id !== S.baitSel) selectBait(id);
  if (kind === "float" && id !== S.floatEq) equipFloat(id);
};
$("pickClose").onclick = () => closeModal("pickBox");
$("pickShop").onclick = () => { closeModal("pickBox"); go("shop"); };
$("pickBox").addEventListener("click", e => { if (e.target === e.currentTarget) closeModal("pickBox"); });   // tap outside
$("bonuses").onclick = e => { const b = e.target.closest(".bonus"); if (b) toast(b.dataset.tip); };

function pickFish(baitId) {
  if (island === "secret") return FISH.find(f => f.island === "secret");
  const w = rarityWeights(baitId || "none");
  const tiers = ["Common", "Rare", "Epic", "Legendary"];
  let r = Math.random() * w.reduce((a, b) => a + b), tier = tiers[0];
  for (let i = 0; i < 4; i++) { if (r < w[i]) { tier = tiers[i]; break; } r -= w[i]; }
  const pool = FISH.filter(f => f.island === island && f.rarity === tier);
  return pool[Math.floor(Math.random() * pool.length)];
}

// main action (CAST / HOOK / REEL): the button, the Space key, or a tap anywhere on the scene
function act() {
  if ($("actBtn").disabled || current !== "fishing") return;
  if (F.phase === "idle") cast();
  else if (F.phase === "bite") hook();
  else if (F.phase === "reeling") reel();
}
// CAST: a press on the button / scene / Space starts a charge when idle (HOOK and REEL act at once, as before); the release throws.
// A real pointer click while idle is already handled by pointerdown/up; detail 0 (Enter on the focused button, el.click()) still casts at once.
$("actBtn").addEventListener("pointerdown", e => { if (!e.button && F.phase === "idle") chargeStart("ptr", e.pointerId); });
$("actBtn").addEventListener("click", e => { if (F.phase === "idle" && e.detail) return; act(); });
$("scene").addEventListener("pointerdown", e => { if (e.button) return; e.preventDefault(); if (F.phase === "idle") chargeStart("ptr", e.pointerId); else act(); });
document.addEventListener("pointerup", e => { if (CH.on && CH.src === "ptr" && e.pointerId === CH.pid) chargeEnd(); });      // anywhere on the page
document.addEventListener("pointercancel", e => { if (CH.on && CH.src === "ptr" && e.pointerId === CH.pid) chargeReset(); });
// iOS: a long press fires contextmenu (callout / loupe) and may take the pointer away (lostpointercapture): both are a clean cancel, not a stuck charge.
// lostpointercapture also follows every normal pointerup, but by then the release has already thrown and CH.on is false.
["actBtn", "scene"].forEach(id => {
  $(id).addEventListener("contextmenu", e => e.preventDefault());
  $(id).addEventListener("lostpointercapture", e => { if (CH.on && CH.src === "ptr" && e.pointerId === CH.pid) chargeReset(); });
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") chargeReset();                                                    // Esc cancels the charge, nothing is thrown
  if (e.code !== "Space" || current !== "fishing" || document.querySelector(".banner.show") || e.target === $("homeTop")) return;   // Space on the focused HOME button presses HOME (part 13), it does not cast
  e.preventDefault();                                                                       // no page scroll, no second click on a focused button
  if (e.repeat) return;
  if (F.phase === "idle") chargeStart("key"); else act();
});
document.addEventListener("keyup", e => {
  if (e.code !== "Space" || e.target === $("homeTop")) return;
  if (CH.on && CH.src === "key") chargeEnd();
  if (current === "fishing" && !document.querySelector(".banner.show")) e.preventDefault();
});
window.addEventListener("blur", () => chargeReset());
document.addEventListener("visibilitychange", () => { if (document.hidden) chargeReset(); });
function chargeStart(src, pid = -1) {
  if (CH.on || F.phase !== "idle" || current !== "fishing" || $("actBtn").disabled || document.querySelector(".banner.show")) return;
  Object.assign(CH, { on: true, src, pid, t0: performance.now(), shown: false });
}
// power 0..1: the meter fills in POWER.fill ms after the quick-press time, then ping-pongs; with reduced motion it fills once and holds at max
function chargePower(now) {
  const d = Math.max(0, (now - CH.t0 - POWER.quick) / POWER.fill);
  if (REDUCED && REDUCED.matches) return Math.min(1, d);
  const m = d % 2; return m < 1 ? m : 2 - m;
}
function chargeTick(now) {
  if (current !== "fishing" || F.phase !== "idle" || document.querySelector(".banner.show")) { chargeReset(); return; }
  if (!CH.shown && now - CH.t0 >= POWER.quick) {                                            // held longer than a tap: show the meter (same space as the reel meter)
    CH.shown = true; $("meter").classList.add("charging"); showMeter(true); $("fMsg").textContent = "Release to throw!";
  }
  if (CH.shown) $("powerFill").style.transform = `scaleX(${(1 - chargePower(now)).toFixed(3)})`;   // the cover shrinks from the right, the bar grows
}
// stop charging without throwing (Esc, focus lost, screen change, bag full...); quiet = leaving the screen, so don't redraw the HUD
function chargeReset(quiet) {
  const was = CH.on && CH.shown; CH.on = false; CH.shown = false;
  $("meter").classList.remove("charging");
  if (was && F.phase === "idle") { showMeter(false); if (!quiet && current === "fishing") renderFishingHud(); }
}
function chargeEnd() {
  const now = performance.now(), quick = now - CH.t0 < POWER.quick, p = quick ? POWER.mid : chargePower(now);
  chargeReset(true);
  if (F.phase === "idle" && current === "fishing" && !$("actBtn").disabled) {
    if (!quick) { S.holdCasts = (S.holdCasts || 0) + 1; save(); }          // the hint "hold CAST" goes away after 3 hold-to-charge casts
    cast(p, quick ? POWER.jitterQuick : POWER.jitterHold);
  }
}
// where a cast with this power lands: a point on the near > far line, with a uniform random offset of +-`jitter` of the throw range (5%) and +-1% of the height
function landing(power, jitter = POWER.jitterQuick) {
  const p = Math.min(1, Math.max(0, power + (Math.random() * 2 - 1) * jitter));
  return { x: POWER.near.x + (POWER.far.x - POWER.near.x) * p, y: POWER.near.y + (POWER.far.y - POWER.near.y) * p + (Math.random() - .5) * .02, p };
}
function cast(power = POWER.mid, jitter = POWER.jitterQuick) {
  if (bagFull()) { toast("Your bag is full."); return; }
  // one bait of the selected kind; when it runs out the selection goes back to "no bait"
  const usedBait = BAITS[S.baitSel] && S.baits[S.baitSel] > 0 ? S.baitSel : null;
  if (usedBait) { S.baits[usedBait]--; if (!S.baits[usedBait]) S.baitSel = "none"; save(); }
  F = { phase: "casting", castAt: performance.now(), fish: pickFish(usedBait), usedBait, floatId: S.floatEq, land: landing(power, jitter) };
  sfx.cast(); $("actBtn").disabled = true; $("actBtn").textContent = "...";
  const left = usedBait && S.baits[usedBait];
  $("fMsg").textContent = !usedBait ? "Waiting for a bite..." : left ? `Cast with ${BAITS[usedBait].name} (${left} left)... waiting` : `Cast with your last ${BAITS[usedBait].name}... waiting`;
  renderFishingHud();
  $("actBtn").disabled = true;
  later(() => { F.phase = "waiting"; sfx.splash(); }, 500);   // the bobber lands: splash
  const wait = 1000 + Math.random() * 4000;           // 1-5 s random wait (unchanged); F.biteAt only tells the fish shadow when to arrive
  F.biteAt = F.castAt + 500 + wait; later(bite, 500 + wait);
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
    speed: d.speed * (S.mastery.frost ? .8 : 1) * rod().speed, zoneW: d.zone * rod().zone });   // rod + Steady Hands
  newZone(); showMeter(true);
  const a = $("actBtn"); a.textContent = "REEL"; a.className = "btn green";
  $("fMsg").textContent = "Press REEL inside the green zone!"; updateDots(); sfx.hit(); musicDuck(true);   // the music dips while reeling so the effects stay clear
}
function newZone() { F.zoneX = .1 + Math.random() * (.8 - F.zoneW); $("zone").style.left = F.zoneX * 100 + "%"; $("zone").style.width = F.zoneW * 100 + "%"; }
// HIT dots, and one heart per miss you can still afford (a miss with no hearts left = the fish escapes)
function updateDots() {
  $("dots").textContent = "HIT " + "●".repeat(F.hits) + "○".repeat(3 - F.hits);
  const max = allowedMiss(), left = Math.max(0, max - F.misses), H = $("hearts");
  H.innerHTML = `<span class="l">${left ? "MISSES LEFT" : "NO MISSES LEFT!"}</span>` + (max > 6
    ? `<span class="ico ${left ? "i-heart" : "i-heart0"}"></span>x${left}`
    : Array.from({ length: max }, (_, i) => `<span class="ico ${i < left ? "i-heart" : "i-heart0"}"></span>`).join(""));
  H.classList.toggle("last", !left); H.setAttribute("aria-label", `${misses(left)} left`);
}
function reel() {
  const inside = F.pos >= F.zoneX && F.pos <= F.zoneX + F.zoneW;
  if (inside) { F.hits++; sfx.hit(); vibrate(40); } else { F.misses++; sfx.miss(); vibrate([30, 30, 30]); }
  fisherTug(inside);                                  // fisherman: strong tug on a hit, slack wobble on a miss
  updateDots();
  if (F.hits >= 3) return caught(true);
  if (F.misses > allowedMiss()) return escape("Too many misses. The fish escaped!");
  F.pos = 0; F.dir = 1; newZone();                    // marker resets and keeps moving after every hit or miss
}
function escape(text) {
  shadowLeave(); musicDuck(false); sfx.fail(); vibrate(300); showMeter(false); $("bang").style.display = "none";
  clearTimers(); F = { phase: "idle" }; fisherEvent("escaped"); renderFishingHud(); $("fMsg").textContent = text; toast(text);
}
// reeled = caught on the fishing screen: the fisherman lifts the rod for a moment before the Result screen
function caught(reeled) {
  musicDuck(false);
  const f = F.fish; shadowCatch(reeled && current === "fishing"); clearTimers(); F = { phase: "idle" }; showMeter(false);
  const skew = Math.pow(Math.random(), 1.6);
  const weight = +(f.min + (f.max - f.min) * skew).toFixed(2);
  const mid = (f.min + f.max) / 2;
  const price = Math.round(f.price * (0.7 + 0.6 * (weight / mid) / 2) * (S.mastery.harbor ? 1.2 : 1));
  const rec = !S.records[f.id] || weight > S.records[f.id];
  const isNew = !S.discovered[f.id];
  S.pending = { fishId: f.id, weight, price, isNew, rec };   // saved, so the catch survives a reload
  S.discovered[f.id] = true; S.totalCaught++; if (rec) S.records[f.id] = weight;
  if (f.rarity === "Mythical") S.mythical = true;
  save(); renderIsleProgress();                              // a new fish shows in the progress line straight away
  sfx.catch(); vibrate([60, 40, 120]); confetti();
  const wait = reeled && current === "fishing" ? FISHER_HOLD.caught : 0;
  if (wait) {
    fisherEvent("caught"); $("actBtn").disabled = true; $("fMsg").textContent = "Got it!";   // no new cast during the celebration
    setTimeout(() => { if (current === "fishing") go("result"); }, wait);
  } else go("result");
  if (f.rarity === "Mythical") setTimeout(() => banner("You caught the Lake Guardian!", "You completed Little Lake. A trophy has been added to your Home screen."), 600 + wait);
  else setTimeout(checkMastery, 400 + wait);
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
    const c = cheapest(), cf = c < 0 ? null : fishById(S.bag[c].fishId);
    $("sellOneBtn").disabled = c < 0;
    $("fullText").textContent = `Your bag is full (${S.bag.length} / ${S.bagMax}). Make room for the ${f.name} or let it go.`;
    $("sellOneBtn").innerHTML = `<span class="ico i-coin"></span>SELL A FISH`;
    $("sellOneInfo").textContent = cf ? `SELL A FISH sells your cheapest unlocked fish (${cf.name}, ${fmt(S.bag[c].price)} coins) and keeps the ${f.name}.`
      : `All your fish are locked. Unlock one in the Bag to sell it, or release the ${f.name}.`;
  }
}
const cheapest = () => S.bag.reduce((m, b, i) => b.locked ? m : m < 0 || b.price < S.bag[m].price ? i : m, -1);   // -1 = every fish is locked
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
  const i = cheapest(); if (i < 0) { toast("All your fish are locked"); return; }
  const b = S.bag[i]; S.bag.splice(i, 1); S.coins += b.price; sfx.coin();
  keepCatch(`Sold ${fishById(b.fishId).name} for ${fmt(b.price)} coins. `);
};
$("resBagBtn").onclick = () => go("bag");
function releaseCatch() { S.pending = null; save(); toast("Released. It stays in your Collection Book."); go("fishing"); }
$("releaseBtn").onclick = releaseCatch;
$("fullRelease").onclick = releaseCatch;
