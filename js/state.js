// Save data, shared helpers (toast, sound, confetti, banner, fish drawing) and progress checks. Loaded after data.js.
/* ===================== SAVE / STATE ===================== */
const SAVE_KEY = "littleLakeSave";
const DEFAULT = () => ({ name: "Angler", coins: 300, rod: 1, bait: 0, bagMax: 5, bag: [], discovered: {}, records: {}, mastery: {}, totalCaught: 0, mythical: false, sound: true });
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
  };
  s.bag = s.bag.slice(0, s.bagMax);
  return s;
}
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

/* ===================== HELPERS ===================== */
const $ = id => document.getElementById(id);
const fmt = n => Math.round(n).toLocaleString("en-US");
let toastT;
function toast(m) { const t = $("toast"); t.textContent = m; t.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), 1600); }
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

/* pixel fish drawn on a 24x16 grid */
function drawFish(cv, f) {
  const c = cv.getContext("2d"); cv.width = 24; cv.height = 16; c.clearRect(0, 0, 24, 16);
  const px = (x, y, col) => { c.fillStyle = col; c.fillRect(x, y, 1, 1); };
  const cx = 2 + Math.floor((20 - f.len) / 2), cy = 8, hh = f.h / 2;
  for (let i = 0; i < 4; i++) for (let y = -i - 1; y <= i + 1; y++) px(cx - 1 - (3 - i), cy + y, f.fin);
  for (let x = 0; x < f.len; x++) {
    const t = (x - f.len / 2) / (f.len / 2), half = Math.max(1, Math.round(hh * Math.sqrt(Math.max(0, 1 - t * t))));
    for (let y = -half; y <= half; y++) {
      let col = y > half / 3 ? f.belly : f.body;
      if (f.stripe && x % 4 === 1 && x > 2 && x < f.len - 3 && Math.abs(y) < half) col = f.stripe;
      px(cx + x, cy + y, col);
    }
    px(cx + x, cy - half - 1, "#0b1d27"); px(cx + x, cy + half + 1, "#0b1d27");
  }
  for (let x = Math.floor(f.len * .35); x < Math.floor(f.len * .65); x++) px(cx + x, cy - Math.ceil(hh) - 2, f.fin);
  const ex = cx + f.len - 3; px(ex, cy - 1, "#fff"); px(ex + 1, cy - 1, "#0b1d27");
  if (f.rarity === "Legendary" || f.rarity === "Mythical") for (let x = 0; x < f.len; x += 2) px(cx + x, cy - Math.ceil(hh) - 3, f.fin);
}
function silhouette(cv) { drawFish(cv, { len: 16, h: 6, body: "#0b2733", belly: "#0b2733", fin: "#0b2733", stripe: null, rarity: "Common" }); }

/* ===================== DERIVED ===================== */
const discCount = isl => FISH.filter(f => f.island === isl && S.discovered[f.id]).length;
const totalDisc = () => FISH.filter(f => f.island !== "secret" && S.discovered[f.id]).length;
const masteredCount = () => ISLAND_IDS.filter(i => S.mastery[i]).length;
const secretOpen = () => masteredCount() === 4;
const allowedMiss = () => S.rod + (S.mastery.forest ? 1 : 0);
const bagFull = () => S.bag.length >= S.bagMax;

function checkMastery() {
  for (const isl of ISLAND_IDS) {
    if (!S.mastery[isl] && discCount(isl) === 10) {
      S.mastery[isl] = true; save();
      const I = ISLANDS[isl];
      banner(`${I.name} Mastered!`, `Reward unlocked: ${I.reward}. ${I.effect}.`);
      if (secretOpen()) setTimeout(() => banner("Secret island found!", "All four islands are mastered. The Town Map now shows Little Lake, home of a mythical fish."), 2400);
      return;
    }
  }
}
