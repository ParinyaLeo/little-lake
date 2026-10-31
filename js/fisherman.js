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
const fFrames = [];
function fMap(g, rows, x0, y0) {
  for (let y = 0; y < rows.length; y++) for (let x = 0; x < rows[y].length; x++) {
    const ch = rows[y][x]; if (ch === ".") continue;
    g.fillStyle = FPAL[ch]; g.fillRect(x0 + x, y0 + y, 1, 1);
  }
}
function fLine(g, x0, y0, x1, y1, w, col) {   // thick blocky line for the arm
  const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) || 1; g.fillStyle = col;
  for (let i = 0; i <= n; i++) g.fillRect(Math.round(x0 + (x1 - x0) * i / n), Math.round(y0 + (y1 - y0) * i / n), w, w);
}
function fFrame(i) {
  if (fFrames[i]) return fFrames[i];
  const f = F_FRAMES[i], c = document.createElement("canvas"); c.width = 28 + FM * 2; c.height = 36 + FM * 2;
  const g = c.getContext("2d"), ux = FM + f.ux, uy = FM + f.uy;
  fMap(g, F_LEGS, FM, FM + 25);
  fMap(g, F_BODY, ux + 2, uy + 12);
  fMap(g, F_HEAD, ux + f.hx, uy + f.hy);
  // near arm: blue sleeve from the shoulder to the elbow, bare forearm to the hands (drawn outline first)
  const sx = ux + 15, sy = uy + 15, hx = FM + f.hand[0], hy = FM + f.hand[1];
  const ex = Math.round((sx + hx) / 2), ey = Math.round((sy + hy) / 2) + (hy < sy ? 0 : 3);
  fLine(g, sx - 1, sy - 1, ex - 1, ey - 1, 5, FPAL.o); fLine(g, ex - 1, ey - 1, hx - 1, hy - 1, 4, FPAL.o);
  fLine(g, sx, sy, ex, ey, 3, FPAL.S); fLine(g, sx + 1, sy, ex + 1, ey, 1, FPAL.l); fLine(g, ex, ey, hx, hy, 2, FPAL.s);
  return (fFrames[i] = c);
}

/* ---------- poses ----------
   fishing.js reports events (a REEL press, a catch, an escape); the pose comes from the phase plus those events.
   P is reused every frame (no allocations): f = body frame, a = rod angle (degrees, 0 = right, 90 = up),
   bend = how far the tip curves down (degrees; negative = whips back). */
const FISH_EVT = { name: "", at: -1e9, tugAt: -1e9, tugHit: false };
function fisherEvent(name) { FISH_EVT.name = name; FISH_EVT.at = performance.now(); }
function fisherTug(hit) { FISH_EVT.tugAt = performance.now(); FISH_EVT.tugHit = hit; }
const FISHER_HOLD = { caught: 700, escaped: 1400 };   // how long the after-catch poses last (ms)
function fisherPoseFor(phase, t) {
  if (phase !== "idle") return phase;
  return FISH_EVT.name && t - FISH_EVT.at < FISHER_HOLD[FISH_EVT.name] ? FISH_EVT.name : "idle";
}
const P = { f: 0, a: 38, bend: 3 }, FISHER = { pose: "idle", since: 0, tipX: 0, tipY: 0 };
const fEase = k => 1 - (1 - k) * (1 - k) * (1 - k);
function poseParams(name, lt, t, still) {
  const sin = Math.sin;
  if (name === "casting") {
    const k = still ? 1 : Math.min(1, lt / 500);
    if (k < .4) { const e = k / .4; P.f = 2; P.a = 38 + 87 * e * e * (3 - 2 * e); P.bend = -3 * e; }        // wind-up, back over the head
    else { const e = (k - .4) / .6; P.f = 3; P.a = 125 - 103 * fEase(e); P.bend = still ? 2 : -12 * sin(e * Math.PI) + 2 * e; }   // fast swing forward
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
  } else if (name === "caught") {
    P.f = still || Math.floor(lt / 175) % 2 === 0 ? 11 : 12; P.a = 82; P.bend = still ? 0 : -1 + sin(lt / 60) * 2;
  } else if (name === "escaped") {
    P.f = 13; P.a = -12; P.bend = 6;
  } else {
    P.f = still || Math.floor(lt / 1200) % 2 === 0 ? 0 : 1; P.a = 38; P.bend = 3;   // idle: slow breathing
  }
  return P;
}

// Draw the fisherman and his rod. cfg = { x, y, p } in canvas pixels (p = canvas pixels per art pixel).
// pose = idle | casting | waiting | bite | reeling | caught | escaped; t = animation time (ms).
// Sets FISHER.tipX / tipY (canvas pixels) to the centre of the drawn rod tip, where the line starts.
const ROD_LEN = 44;
function drawFisherman(c, cfg, pose, t, still) {
  if (pose !== FISHER.pose) { FISHER.pose = pose; FISHER.since = t; }
  const q = poseParams(pose, t - FISHER.since, t, still), fr = F_FRAMES[q.f], p = cfg.p;
  c.imageSmoothingEnabled = false;
  c.drawImage(fFrame(q.f), cfg.x - FM * p, cfg.y - FM * p, (28 + FM * 2) * p, (36 + FM * 2) * p);
  // rod: a quadratic curve from the hands, straight at the butt and bending down toward the tip,
  // drawn as art-pixel blocks snapped to the same grid as the body
  const hx = fr.hand[0] + .5, hy = fr.hand[1] + .5, a = q.a * Math.PI / 180, b = (q.a - q.bend) * Math.PI / 180;
  const bx = hx - Math.cos(a) * 4, by = hy + Math.sin(a) * 4;                                  // butt, behind the hands
  const cx = hx + Math.cos(a) * ROD_LEN * .55, cy = hy - Math.sin(a) * ROD_LEN * .55;
  const tx = hx + Math.cos(b) * ROD_LEN, ty = hy - Math.sin(b) * ROD_LEN;
  let lc = 1e9, lr = 1e9;
  for (let i = 0; i <= 64; i++) {
    const k = i / 64, m = 1 - k;
    const col = Math.floor(m * m * bx + 2 * m * k * cx + k * k * tx), row = Math.floor(m * m * by + 2 * m * k * cy + k * k * ty);
    if (col === lc && row === lr) continue; lc = col; lr = row;
    const x0 = Math.round(cfg.x + col * p), y0 = Math.round(cfg.y + row * p), w = Math.round(cfg.x + (col + 1) * p) - x0, h = Math.round(cfg.y + (row + 1) * p) - y0;
    c.fillStyle = k < .2 ? "#c9a26a" : k < .7 ? "#5a3518" : "#3a2210"; c.fillRect(x0, y0, w, h);       // cork grip, cane, thin tip
    if (k < .5) { c.fillStyle = "#2b1a10"; c.fillRect(x0, y0 + h, w, Math.round(p)); }                     // thicker butt
    FISHER.tipX = x0 + w / 2; FISHER.tipY = y0 + h / 2;
  }
  // hands on top of the rod
  const gx = Math.round(cfg.x + (fr.hand[0] - 1) * p), gy = Math.round(cfg.y + (fr.hand[1] - 1) * p), gs = Math.round(3 * p);
  c.fillStyle = FPAL.o; c.fillRect(gx - Math.round(p / 2), gy - Math.round(p / 2), gs + Math.round(p), gs + Math.round(p));
  c.fillStyle = FPAL.s; c.fillRect(gx, gy, gs, gs); c.fillStyle = FPAL.k; c.fillRect(gx, gy + gs - Math.round(p), gs, Math.round(p));
}
function fisherPose() { return FISHER.pose; }
function fisherTip() { return { x: FISHER.tipX, y: FISHER.tipY }; }   // for tests
