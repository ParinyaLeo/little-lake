// Save data, shared helpers (toast, sound, confetti, banner, fish drawing) and progress checks. Loaded after data.js.
/* ===================== SAVE / STATE ===================== */
const SAVE_KEY = "littleLakeSave";
const DEFAULT = () => ({ name: "Angler", coins: 300, rod: 1, bait: 0, bagMax: 5, bag: [], discovered: {}, records: {}, mastery: {}, totalCaught: 0, mythical: false, sound: true, useBait: true, pending: null });
const num = (v, d, min = 0) => (typeof v === "number" && Number.isFinite(v) && v >= min) ? Math.floor(v) : d;
function load() {
  let raw;
  try { raw = JSON.parse(localStorage.getItem(SAVE_KEY)); } catch (e) { raw = null; }
  const d = DEFAULT(); if (!raw || typeof raw !== "object") return d;
  const s = {
    name: typeof raw.name === "string" && raw.name.trim() ? raw.name.trim().slice(0, 20) : d.name,
    coins: num(raw.coins, d.coins), rod: num(raw.rod, 1, 1), bait: num(raw.bait, 0), bagMax: num(raw.bagMax, 5, 5),
    bag: Array.isArray(raw.bag) ? raw.bag.filter(b => b && fishById(b.fishId) && Number.isFinite(b.weight) && Number.isFinite(b.price)) : [],
    discovered: raw.discovered && typeof raw.discovered === "object" ? raw.discovered : {},
    records: raw.records && typeof raw.records === "object" ? raw.records : {},
    mastery: raw.mastery && typeof raw.mastery === "object" ? raw.mastery : {},
    totalCaught: num(raw.totalCaught, 0), mythical: raw.mythical === true,
    sound: raw.sound !== false,                       // older saves have no sound setting: default on
    useBait: raw.useBait !== false,                   // older saves have no bait toggle: default on
    pending: validCatch(raw.pending) ? raw.pending : null,   // a catch still waiting for KEEP / RELEASE
  };
  s.bag = s.bag.slice(0, s.bagMax);
  return s;
}
// The fish shown on the Result screen stays in the save until KEEP or RELEASE, so closing the page can't lose it.
function validCatch(p) { return !!p && typeof p === "object" && !!fishById(p.fishId) && Number.isFinite(p.weight) && Number.isFinite(p.price); }
let S = load();
function save() { try { localStorage.setItem(SAVE_KEY, JSON.stringify(S)); } catch (e) {} }
// A game exists if the save holds anything besides the sound setting (toggling sound on the
// Title screen before starting a game stores only { sound }).
function hasSave() {
  try { const raw = JSON.parse(localStorage.getItem(SAVE_KEY)); return !!raw && typeof raw === "object" && Object.keys(raw).some(k => k !== "sound"); }
  catch (e) { return false; }
}
function saveSound() {
  if (hasSave()) return save();
  try { localStorage.setItem(SAVE_KEY, JSON.stringify({ sound: S.sound })); } catch (e) {}
}

// Another tab of the game saved: reload, so this tab doesn't later overwrite that progress with its old copy.
window.addEventListener("storage", e => {
  if (e.key !== SAVE_KEY && e.key !== null) return;
  S = load(); if (typeof render === "function") render();
});

/* ===================== HELPERS ===================== */
const $ = id => document.getElementById(id);
const fmt = n => Math.round(n).toLocaleString("en-US");
let toastT;
function toast(m) { const t = $("toast"); t.textContent = m; t.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), 1600); }
// short bounce on a number that just changed (e.g. the bag counter after KEEP)
function bump(id) { const e = $(id); e.classList.remove("bump"); void e.offsetWidth; e.classList.add("bump"); }
function vibrate(p) { try { navigator.vibrate && navigator.vibrate(p); } catch (e) {} }
let AC;
function beep(freq, dur = .12, type = "square", vol = .06) {
  if (!S.sound) return;                               // every sfx goes through beep()
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)();
    const o = AC.createOscillator(), g = AC.createGain();
    o.type = type; o.frequency.value = freq; g.gain.value = vol;
    o.connect(g); g.connect(AC.destination); o.start();
    g.gain.exponentialRampToValueAtTime(.0001, AC.currentTime + dur); o.stop(AC.currentTime + dur);
  } catch (e) {}
}
const sfx = {
  cast: () => beep(300, .15, "triangle"), bite: () => { beep(880, .1); setTimeout(() => beep(880, .1), 130); },
  hit: () => beep(660, .08), miss: () => beep(140, .2, "sawtooth"),
  catch: () => [523, 659, 784, 1047].forEach((f, i) => setTimeout(() => beep(f, .15, "triangle"), i * 110)),
  coin: () => beep(1200, .06), fail: () => beep(110, .35, "sawtooth"),
};
function confetti() {
  const cols = ["#ffd54f", "#4caf50", "#64b5f6", "#ef5350", "#ce93d8"];
  for (let i = 0; i < 40; i++) {
    const c = document.createElement("div"); c.className = "confetti";
    c.style.left = Math.random() * 100 + "vw"; c.style.background = cols[i % cols.length]; c.style.animationDelay = Math.random() * .5 + "s";
    document.body.append(c); setTimeout(() => c.remove(), 2300);
  }
}
function banner(title, text) { $("banTitle").textContent = title; $("banText").textContent = text; $("banner").classList.add("show"); confetti(); sfx.catch(); vibrate([80, 60, 80]); }
$("banOk").onclick = () => $("banner").classList.remove("show");

/* ===================== PIXEL FISH (24x16 grid) =====================
   The body shape comes from each fish's size data (len, h), with a few named exceptions,
   so fish added later get a sensible shape automatically. */
const FISH_SHAPES = { "Sandstorm Eel": "eel", "Oarfish": "eel", "Manta Ray": "ray", "Pufferfish": "round", "Lumpsucker": "round", "Lake Guardian": "flat" };
function fishShape(f) {
  if (FISH_SHAPES[f.name]) return FISH_SHAPES[f.name];
  if (f.len >= 19) return "long";
  if (f.h >= 7) return "flat";       // tall, side-flattened body (bream, tang, koi)
  if (f.h <= 5) return "slim";
  return "regular";
}
// half-height of the body along its length: u = -1 at the tail end, +1 at the head
const FISH_PROFILE = {
  regular: u => Math.sqrt(1 - u * u),
  slim:    u => Math.sqrt(1 - u * u) * (u > 0 ? 1 - u * u * .4 : 1),
  round:   u => Math.pow(1 - u * u, .3),
  flat:    u => Math.max(0, 1 - Math.pow(Math.abs(u - .1) / 1.1, 1.5)),
  long:    u => Math.min(1, 1.4 * Math.sqrt(1 - u * u)),
  eel:     u => u < 0 ? Math.min(1, 1.6 * (1 + u)) : Math.min(1, 5 * (1 - u)),
  ray:     u => Math.pow(u < .25 ? (u + 1) / 1.25 : (1 - u) / .75, .75),
};
// lighten (k > 0) or darken (k < 0) a #rrggbb colour
function shade(hex, k) {
  const n = parseInt(hex.slice(1), 16);
  return "#" + [n >> 16, n >> 8 & 255, n & 255].map(v => Math.round(k >= 0 ? v + (255 - v) * k : v * (1 + k)).toString(16).padStart(2, "0")).join("");
}
function drawFish(cv, f) {
  const c = cv.getContext("2d"); cv.width = 24; cv.height = 16; c.clearRect(0, 0, 24, 16);
  const W = 24, H = 16, OUT = "#0b1d27", cy = 8, shape = fishShape(f), dark = f.dark;
  const grid = new Array(W * H).fill(null), isBody = new Array(W * H).fill(false);
  const set = (x, y, col) => { if (x >= 0 && x < W && y >= 0 && y < H) grid[y * W + x] = col; };
  const get = (x, y) => (x >= 0 && x < W && y >= 0 && y < H) ? grid[y * W + x] : null;
  const body = (x, y) => x >= 0 && x < W && y >= 0 && y < H && isBody[y * W + x];

  // ---- body with simple shading: darker back, main colour, lighter belly, shine line ----
  const tail = { eel: 0, ray: 6, round: 3, flat: 3 }[shape] ?? 4;
  const L = shape === "ray" ? 15 : Math.min(f.len, (shape === "eel" ? 22 : 23) - tail);
  const x0 = Math.floor((W - (tail + L + 1)) / 2) + tail;
  const hh = shape === "ray" ? 6 : Math.min(f.h, 9) / 2;
  const back = dark ? f.body : shade(f.body, -.22), shine = dark ? f.body : shade(f.body, .38);
  const halfAt = [];
  for (let x = 0; x < L; x++) {
    const u = (x + .5) / L * 2 - 1, half = Math.max(1, Math.round(hh * FISH_PROFILE[shape](u)));
    halfAt.push(half);
    for (let y = -half; y <= half; y++) {
      const rel = y / half;
      let col = shape === "ray" ? (Math.abs(rel) > .7 ? back : f.body) : rel < -.5 ? back : rel > .3 ? f.belly : f.body;
      if (f.stripe && shape !== "eel" && x % 4 === 1 && x > 2 && x < L - 3 && Math.abs(y) < half) col = f.stripe;
      if (f.stripe && shape === "eel" && y === 0 && x % 2 === 0 && x > 1 && x < L - 3) col = f.stripe;   // eels: dotted side line
      if (!dark && half >= 3 && y === -half + 1 && x > L * .3 && x < L * .8) col = shine;
      set(x0 + x, cy + y, col); isBody[(cy + y) * W + x0 + x] = true;
    }
  }
  // ---- outline around the body ----
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++)
    if (!body(x, y) && (body(x - 1, y) || body(x + 1, y) || body(x, y - 1) || body(x, y + 1))) set(x, y, OUT);
  const top = x => cy - halfAt[x] - 1, bottom = x => cy + halfAt[x] + 1;
  const finEdge = dark ? f.fin : shade(f.fin, -.3);

  if (shape === "ray") {
    for (let k = 1; k <= tail; k++) set(x0 - k, cy, f.fin);                               // whip tail
    set(x0 + L, cy - 2, f.fin); set(x0 + L + 1, cy - 2, finEdge); set(x0 + L, cy + 2, f.fin); set(x0 + L + 1, cy + 2, finEdge);   // head fins
  } else {
    // ---- tail: forked for fast fish, fan for round/flat fish, none for eels ----
    for (let k = 1; k <= tail; k++) {
      const col = k === tail ? finEdge : f.fin, spread = Math.min(k, Math.ceil(hh) + 1);
      if (shape === "round" || shape === "flat") for (let y = -spread; y <= spread; y++) set(x0 - k, cy + y, col);
      else if (k === 1) for (let y = -1; y <= 1; y++) set(x0 - k, cy + y, col);
      else { set(x0 - k, cy - spread, col); set(x0 - k, cy - spread + 1, col); set(x0 - k, cy + spread, col); set(x0 - k, cy + spread - 1, col); }
    }
    // ---- dorsal fin: rises at the front, slopes back ----
    const a = shape === "eel" ? 2 : Math.floor(L * .3), b = shape === "eel" ? L - 4 : Math.floor(L * .68);
    const tall = shape === "eel" ? 1 : (shape === "flat" || shape === "round") ? 3 : 2;
    for (let x = a; x <= b; x++) {
      const p = (x - a) / Math.max(1, b - a), fh = Math.max(1, Math.round(tall * (p < .3 ? .5 + p / .6 : 1 - (p - .3) / .7 * .6)));
      if (shape === "eel") { set(x0 + x, top(x), f.fin); continue; }                         // eels: fin fringe joins the body
      for (let k = 1; k <= fh; k++) set(x0 + x, top(x) - k, k === fh ? finEdge : f.fin);
    }
    if (shape === "eel") for (let x = 3; x < L * .6; x++) set(x0 + x, bottom(x), f.fin);       // long belly fringe
    else {
      const ax = Math.round(L * .3);                                                        // anal fin
      set(x0 + ax, bottom(ax) + 1, f.fin); set(x0 + ax + 1, bottom(ax + 1) + 1, f.fin); set(x0 + ax, bottom(ax) + 2, finEdge);
      const px = Math.round(L * .62);                                                       // pectoral fin
      if (halfAt[px] >= 2) { set(x0 + px, cy + 1, finEdge); set(x0 + px - 1, cy + 1, f.fin); set(x0 + px - 1, cy + 2, finEdge); }
    }
    // ---- gill line and mouth ----
    const ex = L - (L >= 15 ? 4 : 3);
    if (!dark && shape !== "eel" && halfAt[ex - 2] >= 3) for (let y = -halfAt[ex - 2] + 2; y <= halfAt[ex - 2] - 2; y++)
      if (y !== 0 || shape === "round") set(x0 + ex - 2, cy + y, shade(f.body, -.18));
    if (!dark && halfAt[L - 1] >= 1) set(x0 + L - 1, cy + (halfAt[L - 1] > 1 ? 1 : 0), shade(f.belly, -.35));
    if (f.name && f.name.includes("Catfish")) { set(x0 + L, cy + 2, OUT); set(x0 + L + 1, cy + 3, OUT); }   // whiskers
  }
  // ---- eye with a highlight ----
  const eyes = shape === "ray" ? [[L - 3, -2], [L - 3, 2]] : [[L - (L >= 15 ? 4 : 3), null]];
  for (const [exr, dy] of eyes) {
    const h = halfAt[exr], ex = x0 + exr, ey = dy !== null ? cy + dy : cy - Math.max(1, Math.round(h * .4));
    if (h >= 3 && dy === null) { set(ex, ey, "#ffffff"); set(ex + 1, ey, OUT); set(ex, ey + 1, OUT); set(ex + 1, ey + 1, OUT); }
    else { set(ex, ey, OUT); set(ex - 1, ey, "#ffffff"); }
  }
  // ---- shine for rarer fish: glints on the back, sparkles around Legendary and Mythical ----
  const tier = { Rare: 1, Epic: 2, Legendary: 3, Mythical: 3 }[f.rarity] || 0;
  if (!dark && tier && shape !== "ray") {
    const gx = Math.round(L * .55); set(x0 + gx, cy - halfAt[gx] + (halfAt[gx] >= 3 ? 2 : 0), "#ffffff");
    if (tier >= 2) { const g2 = Math.round(L * .4); set(x0 + g2, cy - halfAt[g2] + (halfAt[g2] >= 3 ? 2 : 0), "#ffffff"); }
  }
  if (!dark && tier >= 2) {
    const spark = (x, y, col) => { if (get(x, y) || get(x - 1, y) || get(x + 1, y) || get(x, y - 1) || get(x, y + 1)) return;
      set(x, y, "#ffffff"); set(x - 1, y, col); set(x + 1, y, col); set(x, y - 1, col); set(x, y + 1, col); };
    const gold = f.rarity === "Mythical" ? "#ff80ab" : "#fff59d";
    if (tier === 2) set(21, 2, "#fff59d");
    else { spark(21, 2, gold); spark(2, 13, gold); if (f.rarity === "Mythical") spark(2, 2, gold); }
  }
  // ---- paint ----
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const col = grid[y * W + x]; if (col) { c.fillStyle = col; c.fillRect(x, y, 1, 1); } }
}
// dark shape of an undiscovered fish (generic shape when no fish is given)
function silhouette(cv, f) { const d = "#0b2733"; drawFish(cv, { ...(f || { len: 16, h: 6 }), body: d, belly: d, fin: d, stripe: null, rarity: "Common", dark: true }); }

/* ===================== DERIVED ===================== */
const discCount = isl => FISH.filter(f => f.island === isl && S.discovered[f.id]).length;
const totalDisc = () => FISH.filter(f => f.island !== "secret" && S.discovered[f.id]).length;
const masteredCount = () => ISLAND_IDS.filter(i => S.mastery[i]).length;
const secretOpen = () => masteredCount() === 4;
const allowedMiss = () => S.rod + (S.mastery.forest ? 1 : 0);
const bagFull = () => S.bag.length >= S.bagMax;
// rarity weights (Common, Rare, Epic, Legendary) for one cast
function rarityWeights(withBait) {
  const w = withBait ? [40, 30, 24, 6] : [60, 30, 8, 2];
  return S.mastery.desert ? [w[0] - 8, w[1], w[2] + 5, w[3] + 3] : w;
}
// chance (%) of a Rare or better fish
const rarePlus = withBait => { const w = rarityWeights(withBait); return Math.round((w[1] + w[2] + w[3]) / w.reduce((a, b) => a + b) * 100); };
const misses = n => `${n} miss${n === 1 ? "" : "es"}`;

function checkMastery() {
  for (const isl of ISLAND_IDS) {
    if (!S.mastery[isl] && discCount(isl) === 10) {
      S.mastery[isl] = true; save();
      const I = ISLANDS[isl];
      banner(`${I.name} Mastered!`, `Reward unlocked: ${I.reward}. ${I.effect}. It works automatically – see your Tackle Box.`);
      if (secretOpen()) setTimeout(() => banner("Secret island found!", "All four islands are mastered. The Town Map now shows Little Lake, home of a mythical fish."), 2400);
      return;
    }
  }
}
