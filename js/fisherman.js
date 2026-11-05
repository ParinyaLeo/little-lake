/* ===================== FISHERMAN ===================== */
// Animated pixel-art fisherman for picture scenes (Harbor). Loaded after state.js, before fishing.js.
// cleanPlate() hides the fisherman baked into the photo; drawFisherman() draws the new one with his rod.
// Coordinates in a scene's fisher config are photo pixels: x, y = top-left of the 28x36 art grid,
// scale = photo pixels per art pixel. fishing.js turns them into canvas pixels.

// Copy dock planks and water from beside the baked-in figure over it. Each patch [x, y, w, h, dx, dy] fills
// (x, y, w, h) with the pixels at (x + dx, y + dy). The rod is cleared in thin bands that follow it.
// Runs once per picture; the result is cached in an offscreen canvas.
function cleanPlate(img, fisher) {
  const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext("2d"); g.imageSmoothingEnabled = false; g.drawImage(img, 0, 0);
  const r = fisher.rodClear;
  if (r) for (let y = r[1]; y < r[3]; y += 3) {
    const x = r[0] + (r[2] - r[0]) * (y - r[1]) / (r[3] - r[1]);
    g.drawImage(c, x - r[4] + r[6], y, r[4] + r[5], 3, x - r[4], y, r[4] + r[5], 3);
  }
  for (const [x, y, w, h, dx, dy] of fisher.patch || []) g.drawImage(c, x + dx, y + dy, w, h, x, y, w, h);
  return c;
}

/* ---------- the sprite ----------
   Parts are pixel maps (one character = one art pixel, "." = see-through), drawn at offsets per frame,
   so leaning, breathing and head tilts reuse the same art. Colours match the photo. */
const FPAL = {
  o: "#2b1a10", H: "#e9b95c", h: "#b9802f", L: "#f7da8e", B: "#2f3c8f", r: "#3b2414", s: "#f0bf94", k: "#c98a62",
  S: "#3352c4", d: "#22337f", l: "#5b7ae6", P: "#6f6d3b", p: "#4b4a26", b: "#7a4520", n: "#43260f",
};
const F_HEAD = [          // straw hat seen a little from above, blue band, hair at the back, cheek and ear on the right (col 0..21, row 0..14)
  "........oooooo........",
  "......ooLLLLLHoo......",
  ".....oLLLLHHHHHho.....",
  ".....oLHHHHHHHHho.....",
  ".....oBBBBBBBBBBo.....",
  "...ooBBBBBBBBBBBhoo...",
  ".ooLLhBBBBBBBBBhHHHoo.",
  "oLLLHHhhhhhhhhhHHHHHHo",
  "oLHHHHHHHHHHHHHHHHHHHo",
  ".ohHHHHHHHHHHHHHHHHHho",
  "..oohhhhhhhhhhhhhhhoo.",
  "....oooorrrrrsssoo....",
  "......orrrrrrsskso....",
  "......orrrrrssssso....",
  ".......oorrrrsoo......",
];
const F_BODY = [          // blue shirt seen from behind, darker at the back (col 2.., row 12..27)
  "......oooooooo....",
  ".....oddSSSSSSlo..",
  "....oddSSSSSSSllo.",
  "...oddSSSSSSSSSllo",
  "...odSSSSSSSSSSSlo",
  "..oddSSSSSSSSSSSSo",
  "..oddSSSSSSSSSSSSo",
  "..oddSSSSSSSSSSSSo",
  "..oddSSSSSSSSSSSSo",
  "..oddSSSSSSSSSSSo.",
  "..oddSSSSSSSSSSSo.",
  "..oddSSSSSSSSSSSo.",
  "..oddSSSSSSSSSSo..",
  "...oddSSSSSSSSSo..",
  "...odddddSSSSSo...",
  "....ooooooooo.....",
];
const F_LEGS = [          // olive trousers and brown boots, seated on the chest (col 0..27, row 25..35)
  ".........ooooooooooooo......",
  "........oPPPPPPPPPPPPPo.....",
  "........oPPPPPPPPPPPPPPo....",
  "........opPPPPPPPPPPPPPo....",
  "........oppppPPPPPPPPPPo....",
  ".........oPPPPoo.oPPPPPo....",
  ".........oPPPPo..oPPPPo.....",
  "........oopPPpo..opPPPo.....",
  ".......obbbbbbo..obbbbbbo...",
  ".......obbbbbbbo.obbbbbbbo..",
  ".......onnnnnnno.onnnnnnnno.",
];
/* ---------- outfits ----------
   Each island dresses him for its weather (SCENES[island].fisher.outfit). An outfit swaps the palette and the head,
   body or legs maps; every map keeps the harbor grid (head 22x15, body 18x16, legs 28x11), so the size, the poses,
   the hands and the rod tip stay exactly where they are. arm = [sleeve, sleeve highlight, forearm, hand, hand shade]
   as palette letters; front = [map, col, row], a small map drawn over the arm that moves with the upper body.
   Frames are cached per outfit. */
const F_LANTERN = ["ZZoZZ", "ZoooZ", "oYYYo", "oYyYo", "ZoooZ"];
const OUTFITS = {
  harbor: { pal: FPAL, head: F_HEAD, body: F_BODY, legs: F_LEGS, arm: "Slssk" },   // straw hat, blue shirt, olive trousers
  frost: {                                                          // red parka, fur-trimmed hood, yellow scarf, white boots
    pal: { o: "#2b1a10", S: "#cf3a2f", d: "#8a1f1c", l: "#f06a50", W: "#f4f1ea", w: "#c4bdb1", s: "#f0bf94", k: "#c98a62",
      Y: "#f2b630", y: "#b77f16", P: "#2e3447", p: "#1c2030", b: "#f1f5f8", n: "#8e9cad" },
    head: [
      "......................",
      "........oooooo........",
      "......ooSSSSSloo......",
      ".....oSSSSSSSSllo.....",
      "....odSSSSSSSSSSlo....",
      "...odSSSSSSSSSSSSWo...",
      "...odSSSSSSSSSSSWWWo..",
      "..odSSSSSSSSSSSWWwsWo.",
      "..odSSSSSSSSSSSWwsssWo",
      "..oddSSSSSSSSSSWwsksWo",
      "..oddSSSSSSSSSSWWsssWo",
      "...oddSSSSSSSSSSWWWWo.",
      "....oddSSSSSSSSSSSo...",
      ".....ooddSSSSSSSoo....",
      ".......oooooooo.......",
    ],
    body: [
      "......oooooooo....",
      ".....oYYYYYYYYYo..",
      "....oyYYYYYYYYYyo.",
      "...oyYYYYYYYYYYYyo",
      "...oyyyyyyyyyyyyyo",
      "..oddYYSSSSSSSSSSo",
      "..oddYYSSSSSSSSSSo",
      "..oddYySSSSSSSSSSo",
      "..oddyYSSSSSSSSSSo",
      "..oddYySSSSSSSSSo.",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSo..",
      "...oddSSSSSSSSSo..",
      "...owWWWWWWWWWWo..",
      "....ooooooooo.....",
    ],
    legs: F_LEGS, arm: "SlSYy" },
  desert: {                                                         // wide sun hat, sleeveless shirt, tan shorts, sandals
    pal: { o: "#2b1a10", H: "#ead7a8", h: "#bf9f68", L: "#fbf0d4", B: "#8c5a34", r: "#3b2414", s: "#dc9c6c", k: "#a86a42",
      q: "#f0bb8c", S: "#f4f1e4", d: "#c9c1a6", l: "#ffffff", P: "#e6cc94", p: "#b8975e", b: "#8a5426", n: "#5b3517" },
    head: [
      "......................",
      "......................",
      "........oooooo........",
      "......ooLLLLLHoo......",
      ".....oLLHHHHHHHho.....",
      ".....oBBBBBBBBBBo.....",
      "..oooohhhhhhhhhhoooo..",
      "ooLLLLHHHHHHHHHHHHHHoo",
      "oLHHHHHHHHHHHHHHHHHHHo",
      "ohHHHHHHHHHHHHHHHHHHho",
      ".oohhhhhhhhhhhhhhhhoo.",
      "....oooorrrrrsssoo....",
      "......orrrrrrsskso....",
      "......orrrrrssssso....",
      ".......oorrrrsoo......",
    ],
    body: [
      "......oooooooo....",
      ".....oddSSSSSSlo..",
      "....okdSSSSSSSllo.",
      "...oskdSSSSSSSSllo",
      "...oskdSSSSSSSSSlo",
      "..oddddSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSo..",
      "...oddSSSSSSSSSo..",
      "...odddddSSSSSo...",
      "....ooooooooo.....",
    ],
    // shorts (hem on row 4), bare shins, sandals: skin toes over a brown strap and sole
    legs: F_LEGS.map((r, i) => i < 4 ? r : i === 4 ? r.replace(/P/g, "p") : i < 9 ? r.replace(/[Pb]/g, "s").replace(/p/g, "k") : r),
    arm: "sqssk" },
  forest: {                                                         // green explorer cap with a feather, olive vest, cream shirt
    pal: { o: "#2b1a10", H: "#5f8a3c", h: "#3e6228", L: "#8ab65c", B: "#4a3018", F: "#e04a32", f: "#ffe0a8", r: "#7a3e1a",
      s: "#f0bf94", k: "#c98a62", S: "#6e7d34", d: "#4a5622", l: "#93a54c", c: "#efe4c4", C: "#c4b48a", e: "#fff8e2",
      P: "#6b4428", p: "#4a2e1a", b: "#3b2a1c", n: "#22170e" },
    head: [
      "........oooooo........",
      "......ooLLLLLHoo......",
      ".....oLLLHHHHHHho.....",
      ".oo..oLHHHHHHHHho.....",
      "oFFo.oHHHHHHHHHho.....",
      ".oFFooBBBBBBBBBBo.....",
      "..ofFoBBBBBBBBBBhooo..",
      "...ooohhhhhhhhhhHHHHo.",
      "....orrrrrrrrrrohhhhho",
      "....orrrrrrrrrrsoooo..",
      "....orrrrrrrrrssso....",
      "....oorrrrrrrsssso....",
      "......orrrrrrsskso....",
      "......orrrrrssssso....",
      ".......oorrrrsoo......",
    ],
    body: [
      "......oooooooo....",
      ".....oCccccccco...",
      "....oddSSSSSSScco.",
      "...oddSSSSSSSSScco",
      "...odSSSSSSSSSSSco",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSo..",
      "...oCccccccccco...",
      "...oCCCCCccccco...",
      "....ooooooooo.....",
    ],
    legs: F_LEGS, arm: "cessk" },
  secret: {                                                         // dark purple hooded cloak, glowing cyan trim, lantern
    pal: { o: "#140c1e", S: "#5c369a", d: "#36205f", l: "#8a64cf", C: "#5ff3ff", c: "#29b6cc", s: "#e0b08c", k: "#a8765a",
      G: "#1d1233", P: "#2a2440", p: "#1a1530", b: "#3c2c56", n: "#1a1228", Y: "#ffe37a", y: "#f3a330",
      Z: "rgba(255, 220, 120, .35)" },
    head: [
      "......................",
      "........oooooo........",
      "......ooSSSSSloo......",
      ".....oSSSSSSSSllo.....",
      "....odSSSSSSSSSSlo....",
      "...odSSSSSSSSSSSSCo...",
      "...odSSSSSSSSSSSCddo..",
      "..odSSSSSSSSSSSCddsCo.",
      "..odSSSSSSSSSSSCdsssCo",
      "..oddSSSSSSSSSSCdsksCo",
      "..oddSSSSSSSSSSCddssCo",
      "...oddSSSSSSSSSSCCCCo.",
      "....oddSSSSSSSSSSSo...",
      ".....ooddSSSSSSSoo....",
      ".......oooooooo.......",
    ],
    body: [
      "......oooooooo....",
      ".....oddSSSSSSlo..",
      "....oddSSSSSSSllo.",
      "...oddSSSSSSSSSllo",
      "...odSSSSSSSSSSSlo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSSo",
      "..oddSSSSSSSSSSSo.",
      "..oddSSSSSSSSSSSo.",
      "..oGGGGGGGGGGGGGo.",
      "..oddSSSSSSSSSSo..",
      "...oddSSSSSSSSSo..",
      "...oCCCCCCCCCCCo..",
      "....ooooooooo.....",
    ],
    legs: F_LEGS, arm: "SlSsk", front: [F_LANTERN, 13, 22] },
};
// Body frames: ux/uy = upper body offset, hx/hy = extra head offset, hand = [col, row] of the hands on the rod.
const F_FRAMES = [
  { ux: 0, uy: 0, hx: 0, hy: 0, hand: [20, 20] },    // 0 idle
  { ux: 0, uy: 1, hx: 0, hy: 0, hand: [20, 21] },    // 1 idle, breathing out
  { ux: -1, uy: 0, hx: -1, hy: 0, hand: [17, 15] },  // 2 cast: wind-up
  { ux: 1, uy: 1, hx: 1, hy: 0, hand: [22, 19] },    // 3 cast: swing forward
  { ux: 0, uy: 0, hx: 0, hy: 0, hand: [20, 20] },    // 4 waiting
  { ux: 0, uy: 0, hx: 1, hy: 1, hand: [20, 20] },    // 5 waiting, head tilted
  { ux: 2, uy: 1, hx: 1, hy: -1, hand: [23, 21] },   // 6 bite: startled, leaning forward
  { ux: -2, uy: 0, hx: 0, hy: 0, hand: [17, 19] },   // 7 reeling: leaning back
  { ux: -2, uy: 0, hx: 0, hy: 0, hand: [17, 20] },   // 8 reeling: crank
  { ux: -3, uy: 0, hx: -1, hy: 0, hand: [16, 18] },  // 9 reeling: strong tug
  { ux: 0, uy: 1, hx: 0, hy: 0, hand: [20, 21] },    // 10 reeling: slack after a miss
  { ux: -1, uy: -1, hx: 0, hy: 0, hand: [17, 12] },  // 11 caught: rod up
  { ux: -1, uy: -2, hx: 0, hy: -1, hand: [17, 11] }, // 12 caught: little hop
  { ux: 1, uy: 2, hx: 1, hy: 2, hand: [21, 23] },    // 13 escaped: shoulders and head drop
];
const FM = 4;   // empty margin around each frame canvas, so leaning never clips
const fFrames = {};   // outfit name -> frame canvases
function fMap(g, rows, x0, y0, pal) {
  for (let y = 0; y < rows.length; y++) for (let x = 0; x < rows[y].length; x++) {
    const ch = rows[y][x]; if (ch === ".") continue;
    g.fillStyle = pal[ch]; g.fillRect(x0 + x, y0 + y, 1, 1);
  }
}
function fLine(g, x0, y0, x1, y1, w, col) {   // thick blocky line for the arm
  const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) || 1; g.fillStyle = col;
  for (let i = 0; i <= n; i++) g.fillRect(Math.round(x0 + (x1 - x0) * i / n), Math.round(y0 + (y1 - y0) * i / n), w, w);
}
function fFrame(i, name) {
  const cache = fFrames[name] || (fFrames[name] = []);
  if (cache[i]) return cache[i];
  const o = OUTFITS[name], pal = o.pal, A = o.arm, f = F_FRAMES[i], c = document.createElement("canvas"); c.width = 28 + FM * 2; c.height = 36 + FM * 2;
  const g = c.getContext("2d"), ux = FM + f.ux, uy = FM + f.uy;
  fMap(g, o.legs, FM, FM + 25, pal);
  fMap(g, o.body, ux + 2, uy + 12, pal);
  fMap(g, o.head, ux + f.hx, uy + f.hy, pal);
  // near arm: sleeve from the shoulder to the elbow, forearm to the hands (drawn outline first)
  const sx = ux + 15, sy = uy + 15, hx = FM + f.hand[0], hy = FM + f.hand[1];
  const ex = Math.round((sx + hx) / 2), ey = Math.round((sy + hy) / 2) + (hy < sy ? 0 : 3);
  fLine(g, sx - 1, sy - 1, ex - 1, ey - 1, 5, pal.o); fLine(g, ex - 1, ey - 1, hx - 1, hy - 1, 4, pal.o);
  fLine(g, sx, sy, ex, ey, 3, pal[A[0]]); fLine(g, sx + 1, sy, ex + 1, ey, 1, pal[A[1]]); fLine(g, ex, ey, hx, hy, 2, pal[A[2]]);
  if (o.front) fMap(g, o.front[0], ux + o.front[1], uy + o.front[2], pal);
  return (cache[i] = c);
}

/* ---------- poses ----------
   fishing.js reports events (a REEL press, a catch, an escape); the pose comes from the phase plus those events.
   P is reused every frame (no allocations): f = body frame, a = rod angle (degrees, 0 = right, 90 = up),
   bend = how far the tip curves down (degrees; negative = whips back). */
const FISH_EVT = { name: "", at: -1e9, tugAt: -1e9, tugHit: false };
function fisherEvent(name) { FISH_EVT.name = name; FISH_EVT.at = performance.now(); }
function fisherTug(hit) { FISH_EVT.tugAt = performance.now(); FISH_EVT.tugHit = hit; }
const FISHER_HOLD = { caught: 700, escaped: 1400 };   // how long the after-catch poses last (ms)
// Playtest 2, part 7: the cast animation follows the charge power. CHARGE_POSE is set by fishing.js while the power meter is shown (the rod leans back as the power grows);
// CAST describes the cast being played: wind-up ms, swing ms, power 0..1, and the rod angle at the start of the wind-up / the back angle where the swing starts. The defaults are the old fixed cast (200 ms wind-up, 300 ms swing).
// Playtest 2, part 7b: the charging pose is smoothed. `a` / `b` (deg) are the SHOWN rod angle and bend: they move toward the target with exponential smoothing (tau 90 ms, frame-rate independent),
// start at the idle rod angle (ease-in), keep the pose alive after a cancel until they are back at idle (ease-out, `live`), and the swing starts from the shown angle.
const IDLE_A = 38, IDLE_B = 3, CHARGE_TAU = 90, CHARGE_MAX_DEG_MS = .3;
const CHARGE_POSE = { on: false, p: 0, live: false, a: IDLE_A, b: IDLE_B, t: 0 }, CAST = { w: 200, swing: 300, p: .5, a1: 38, a0: 125, b0: 0 };
const chargeBackAngle = p => 38 + 87 * (.15 + .85 * p);                              // rod angle (deg) at charge power p: a little back at 0, fully back (125) at 1
function fisherCastSet(w, swing, p, charged) {
  CAST.w = w; CAST.swing = swing; CAST.p = p;
  CAST.a0 = charged ? CHARGE_POSE.a : 125; CAST.a1 = charged ? CAST.a0 : 38; CAST.b0 = charged ? CHARGE_POSE.b : 0;     // a charged throw swings from the angle the rod is SHOWN at, so nothing jumps
  CHARGE_POSE.live = false; CHARGE_POSE.on = false;
}
const chargeShown = () => ({ on: CHARGE_POSE.on, live: CHARGE_POSE.live, p: CHARGE_POSE.p, a: CHARGE_POSE.a, b: CHARGE_POSE.b });   // tests only
function fisherPoseFor(phase, t) {
  if (phase !== "idle") return phase;
  if (!CHARGE_POSE.on && CHARGE_POSE.live && t - CHARGE_POSE.t > 250) CHARGE_POSE.live = false;   // stale (the screen was left mid-charge)
  if (CHARGE_POSE.on || CHARGE_POSE.live) return "charging";
  return FISH_EVT.name && t - FISH_EVT.at < FISHER_HOLD[FISH_EVT.name] ? FISH_EVT.name : "idle";
}
const P = { f: 0, a: 38, bend: 3 }, FISHER = { pose: "idle", since: 0, tipX: 0, tipY: 0, outfit: "harbor", rod: "bamboo" };
const fEase = k => 1 - (1 - k) * (1 - k) * (1 - k);
function poseParams(name, lt, t, still) {
  const sin = Math.sin;
  if (name === "casting") {
    if (still) { P.f = 3; P.a = 22; P.bend = 2; }
    else if (lt < CAST.w) { const e = lt / CAST.w; P.f = 2; P.a = CAST.a1 + (CAST.a0 - CAST.a1) * e * e * (3 - 2 * e); P.bend = CAST.b0 + (-3 - CAST.b0) * e; }        // wind-up, back over the head (none for a charged cast: the rod is already back)
    else { const e = Math.min(1, (lt - CAST.w) / CAST.swing); P.f = 3; P.a = CAST.a0 - (CAST.a0 - 22) * fEase(e); P.bend = -(6 + 10 * CAST.p) * sin(e * Math.PI) + 2 * e; }   // swing forward: shorter, wider and faster with more power
  } else if (name === "charging") {
    const C = CHARGE_POSE;                                                            // holding CAST: the rod eases back, then follows the power with a little inertia
    if (!C.live) { C.live = true; C.a = IDLE_A; C.b = IDLE_B; C.t = t; }               // ease-in: start from the idle rod angle
    const dt = Math.min(50, Math.max(0, t - C.t)); C.t = t; const k = 1 - Math.exp(-dt / CHARGE_TAU);
    const mx = CHARGE_MAX_DEG_MS * dt, da = ((C.on ? chargeBackAngle(C.p) : IDLE_A) - C.a) * k;   // exponential smoothing, with a speed limit (300 deg/s, 5 deg per frame at 60 fps) so even a cancel from far back never jumps
    C.a += da > mx ? mx : da < -mx ? -mx : da; C.b += ((C.on ? -3 * C.p : IDLE_B) - C.b) * k;
    if (!C.on && Math.abs(C.a - IDLE_A) < .4 && Math.abs(C.b - IDLE_B) < .3) { C.live = false; C.a = IDLE_A; C.b = IDLE_B; }   // ease-out finished: back to idle
    const tr = C.on && C.p > .5 ? sin(t * .0565) * .6 * (C.p - .5) * 2 : 0;           // a very slight tremble at high power (+-0.6 deg, 9 Hz, none below power .5)
    P.f = 2; P.a = C.a + tr; P.bend = C.b;
  } else if (name === "waiting") {
    P.f = still || Math.floor(lt / 1600) % 2 === 0 ? 4 : 5;
    const s = still ? 0 : sin(t / 300);                // same wave as the bobber, so the tip dips with it
    P.a = 30 - s * 1.5; P.bend = 4 + s;
  } else if (name === "bite") {
    const j = still ? .5 : Math.abs(sin(t / 40));
    P.f = 6; P.a = 16 - j * 10; P.bend = 10 + j * 6;
  } else if (name === "reeling") {
    const d = t - FISH_EVT.tugAt;
    if (!still && d >= 0 && d < 280 && FISH_EVT.tugHit) { const s = sin(d / 280 * Math.PI); P.f = 9; P.a = 55 + 18 * s; P.bend = 14 + 8 * s; }
    else if (!still && d >= 0 && d < 350) { const w = 1 - d / 350; P.f = 10; P.a = 40 + sin(d / 25) * 5 * w; P.bend = 1 + sin(d / 30) * 3 * w; }
    else { P.f = still || Math.floor(t / 140) % 2 === 0 ? 7 : 8; P.a = 55 + (still ? 0 : sin(t / 90) * 2); P.bend = 16 + (still ? 0 : sin(t / 60) * 2); }
    if (FIGHT.on) P.bend *= .8 + .5 * FIGHT.tension;   // the rod bends more as the line tension rises (visual only; FIGHT is set by fishing.js)
  } else if (name === "caught") {
    P.f = still || Math.floor(lt / 175) % 2 === 0 ? 11 : 12; P.a = 82; P.bend = still ? 0 : -1 + sin(lt / 60) * 2;
  } else if (name === "escaped") {
    P.f = 13; P.a = -12; P.bend = 6;
  } else {
    P.f = still || Math.floor(lt / 1200) % 2 === 0 ? 0 : 1; P.a = 38; P.bend = 3;   // idle: slow breathing
  }
  return P;
}

/* ---------- rod styles (Playtest 1, part 3: all rods looked the same) ----------
   One entry per rod in RODS, picked by S.rodEq (or cfg.rod). The shape, length and angle never change, only the look:
   grip / cane / tip = colours of the first 20% / middle / last 30% of the rod, shade = the dark pixel row(s) under the butt (butt = how many
   art pixels thick that butt is, 0 = a thin rod), ring = a metal ring where the grip ends, node = bamboo joints, reel = a reel dot just past
   the hands (+ reelHi, its highlight), charm = a sparkling star at the tip. The icons in css/style.css (.i-rod-*, .i-rodlg-*, made by
   tools/make_rod_icons.py) use the same colours. */
const ROD_STYLES = {
  bamboo:    { grip: "#c9a26a", cane: "#a9bd3c", tip: "#7d9a2a", shade: "#3b4a14", butt: 1, node: "#6b8120" },
  sturdy:    { grip: "#3a2210", cane: "#5b3517", tip: "#4a2b12", shade: "#1a0d04", butt: 2, ring: "#aeb8be" },
  precision: { grip: "#7f96aa", cane: "#b8dcef", tip: "#e6f6ff", shade: "", butt: 0, reel: "#1c3f78", reelHi: "#6fa8ff" },
  lucky:     { grip: "#c0392b", cane: "#ffcf3f", tip: "#fff3a8", shade: "#9a6a00", butt: 1, charm: true }
};
const CHARM = ["#ffcf3f", "#fff6c0"];                       // star arms, star centre / sparkle
function rodStyleKey(cfg) { return ROD_STYLES[cfg.rod] ? cfg.rod : ROD_STYLES[S.rodEq] ? S.rodEq : "bamboo"; }

// Draw the fisherman and his rod. cfg = { x, y, p, outfit, rod? } in canvas pixels (p = canvas pixels per art pixel;
// outfit = a key of OUTFITS, anything else draws the harbor look; rod = a key of ROD_STYLES, default the equipped rod S.rodEq).
// pose = idle | casting | waiting | bite | reeling | caught | escaped; t = animation time (ms).
// Sets FISHER.tipX / tipY (canvas pixels) to the centre of the drawn rod tip, where the line starts.
const ROD_LEN = 44;
function drawFisherman(c, cfg, pose, t, still) {
  if (pose !== FISHER.pose) { FISHER.pose = pose; FISHER.since = t; }
  const q = poseParams(pose, t - FISHER.since, t, still), fr = F_FRAMES[q.f], p = cfg.p;
  const name = OUTFITS[cfg.outfit] ? cfg.outfit : "harbor", o = OUTFITS[name], pal = o.pal; FISHER.outfit = name;
  const rk = rodStyleKey(cfg), rs = ROD_STYLES[rk]; FISHER.rod = rk;
  c.imageSmoothingEnabled = false;
  c.drawImage(fFrame(q.f, name),cfg.x - FM * p, cfg.y - FM * p, (28 + FM * 2) * p, (36 + FM * 2) * p);
  // rod: a quadratic curve from the hands, straight at the butt and bending down toward the tip,
  // drawn as art-pixel blocks snapped to the same grid as the body
  const hx = fr.hand[0] + .5, hy = fr.hand[1] + .5, a = q.a * Math.PI / 180, b = (q.a - q.bend) * Math.PI / 180;
  const bx = hx - Math.cos(a) * 4, by = hy + Math.sin(a) * 4;                                  // butt, behind the hands
  const cx = hx + Math.cos(a) * ROD_LEN * .55, cy = hy - Math.sin(a) * ROD_LEN * .55;
  const tx = hx + Math.cos(b) * ROD_LEN, ty = hy - Math.sin(b) * ROD_LEN;
  let lc = 1e9, lr = 1e9, n = 0, mark = false;
  const pr = Math.round(p);
  for (let i = 0; i <= 64; i++) {
    const k = i / 64, m = 1 - k;
    const col = Math.floor(m * m * bx + 2 * m * k * cx + k * k * tx), row = Math.floor(m * m * by + 2 * m * k * cy + k * k * ty);
    if (col === lc && row === lr) continue; lc = col; lr = row; n++;
    const x0 = Math.round(cfg.x + col * p), y0 = Math.round(cfg.y + row * p), w = Math.round(cfg.x + (col + 1) * p) - x0, h = Math.round(cfg.y + (row + 1) * p) - y0;
    c.fillStyle = k < .2 ? rs.grip : k < .7 ? rs.cane : rs.tip; c.fillRect(x0, y0, w, h);               // grip, cane, thin tip
    if (rs.node && k >= .2 && k < .7 && n % 4 === 0) { c.fillStyle = rs.node; c.fillRect(x0, y0, w, h); }   // bamboo joints
    if (k < .5 && rs.butt) { c.fillStyle = rs.shade; c.fillRect(x0, y0 + h, w, pr * rs.butt); }          // thicker butt
    if (!mark && k >= .2) {                                                                              // where the grip ends
      mark = true;
      if (rs.ring) { c.fillStyle = rs.ring; c.fillRect(x0, y0, w, h); c.fillRect(x0, y0 + h, w, pr); }      // metal ring across the rod
      if (rs.reel) { c.fillStyle = rs.reel; c.fillRect(x0, y0 + h, w, pr * 2); c.fillStyle = rs.reelHi; c.fillRect(x0, y0 + h, pr, pr); }   // reel dot
    }
    FISHER.tipX = x0 + w / 2; FISHER.tipY = y0 + h / 2;
  }
  if (rs.charm) {                                                                                       // lucky charm: a star sitting on the tip
    const sx = Math.round(FISHER.tipX), sy = Math.round(FISHER.tipY - 2 * p), alt = !still && Math.floor(t / 500) % 2 === 1, u = pr, h2 = Math.round(u / 2);
    c.fillStyle = CHARM[0];
    c.fillRect(sx - h2, sy - u - h2, u, u); c.fillRect(sx - h2, sy + h2, u, u); c.fillRect(sx - u - h2, sy - h2, u, u); c.fillRect(sx + h2, sy - h2, u, u);
    c.fillStyle = CHARM[1]; c.fillRect(sx - h2, sy - h2, u, u);                                          // bright centre
    if (alt) { const d = Math.max(1, Math.round(u / 2)); c.fillStyle = CHARM[1];                           // sparkle frame: four tiny glints
      c.fillRect(sx - u - h2 - d, sy - u - h2 - d, d, d); c.fillRect(sx + u + h2, sy - u - h2 - d, d, d);
      c.fillRect(sx - u - h2 - d, sy + u + h2, d, d); c.fillRect(sx + u + h2, sy + u + h2, d, d); }
  }
  // hands on top of the rod
  const gx = Math.round(cfg.x + (fr.hand[0] - 1) * p), gy = Math.round(cfg.y + (fr.hand[1] - 1) * p), gs = Math.round(3 * p);
  c.fillStyle = pal.o; c.fillRect(gx - Math.round(p / 2), gy - Math.round(p / 2), gs + Math.round(p), gs + Math.round(p));
  c.fillStyle = pal[o.arm[3]]; c.fillRect(gx, gy, gs, gs); c.fillStyle = pal[o.arm[4]]; c.fillRect(gx, gy + gs - Math.round(p), gs, Math.round(p));
}
function fisherPose() { return FISHER.pose; }
function fisherTip() { return { x: FISHER.tipX, y: FISHER.tipY }; }   // for tests
function fisherOutfit() { return FISHER.outfit; }                      // for tests: the outfit drawn last
function fisherRodStyle() { return FISHER.rod; }                         // for tests: the rod style drawn last (a key of ROD_STYLES)
