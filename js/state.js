// Save data, shared helpers (toast, sound, confetti, banner, fish drawing) and progress checks. Loaded after data.js.
/* ===================== SAVE / STATE ===================== */
const SAVE_KEY = "littleLakeSave";
const DEFAULT = () => ({ name: "Angler", coins: 300, rods: ["bamboo"], rodEq: "bamboo", baits: { worm: 0, shrimp: 0, golden: 0 }, baitSel: "none", floatsOwned: ["classic"], floatEq: "classic",
  bagMax: 5, bag: [], discovered: {}, records: {}, mastery: {}, totalCaught: 0, mythical: false, sound: true, music: true, pending: null, holdCasts: 0, fightStyle: DEFAULT_FIGHT, tank: [], tankTheme: DEFAULT_THEME });
const num = (v, d, min = 0) => (typeof v === "number" && Number.isFinite(v) && v >= min) ? Math.floor(v) : d;
function load() {
  let raw;
  try { raw = JSON.parse(localStorage.getItem(SAVE_KEY)); } catch (e) { raw = null; }
  return cleanSave(raw);
}
// Turns any stored object (old or broken) into a safe save; used by load().
function cleanSave(raw) {
  const d = DEFAULT(); if (!raw || typeof raw !== "object" || Array.isArray(raw)) return d;
  // Saves from before the gear update have rod (level 1+), bait (count) and useBait instead of rods/baits:
  // level 1 = Bamboo; level 2+ also owns and equips the Sturdy Rod (levels above 2 are refunded, 200 coins each);
  // the old bait count becomes Shrimp.
  const legacy = !Array.isArray(raw.rods), oldRod = num(raw.rod, 1, 1);
  const rods = ["bamboo", ...(legacy ? (oldRod >= 2 ? ["sturdy"] : []) : raw.rods.filter(r => RODS[r] && r !== "bamboo"))];
  const baits = {}; BAIT_IDS.forEach(b => baits[b] = legacy ? (b === "shrimp" ? num(raw.bait, 0) : 0) : num(raw.baits && raw.baits[b], 0));
  let baitSel = legacy ? (raw.useBait !== false ? "shrimp" : "none") : raw.baitSel;
  if (!BAITS[baitSel] || !baits[baitSel]) baitSel = "none";
  const floatsOwned = [...new Set(["classic", ...(Array.isArray(raw.floatsOwned) ? raw.floatsOwned.filter(id => FLOATS[id]) : [])])];
  const floatEq = FLOATS[raw.floatEq] && floatsOwned.includes(raw.floatEq) ? raw.floatEq : "classic";
  const s = {
    name: typeof raw.name === "string" && raw.name.trim() ? raw.name.trim().slice(0, 20) : d.name,
    coins: num(raw.coins, d.coins) + (legacy && oldRod > 2 ? (oldRod - 2) * 200 : 0),
    rods: [...new Set(rods)], rodEq: legacy ? (oldRod >= 2 ? "sturdy" : "bamboo") : rods.includes(raw.rodEq) ? raw.rodEq : "bamboo",
    baits, baitSel, bagMax: num(raw.bagMax, 5, 5),
    floatsOwned: floatsOwned, floatEq,          // cosmetic floats: older saves have none, so they own and use the classic float
    bag: Array.isArray(raw.bag) ? raw.bag.filter(b => b && fishById(b.fishId) && Number.isFinite(b.weight) && Number.isFinite(b.price)).map(b => ({ ...b, locked: b.locked === true })) : [],   // locked: kept out of SELL ALL (old saves: unlocked)
    tank: Array.isArray(raw.tank) ? raw.tank.filter(b => b && fishById(b.fishId) && Number.isFinite(b.weight) && Number.isFinite(b.price)).slice(0, TANK_SIZE).map(b => ({ ...b, locked: b.locked === true })) : [],   // the Aquarium (same entries as the bag, kept out of SELL / SELL ALL); old saves: empty
    tankTheme: typeof raw.tankTheme === "string" && Object.prototype.hasOwnProperty.call(TANK_THEMES, raw.tankTheme) ? raw.tankTheme : DEFAULT_THEME,
    discovered: raw.discovered && typeof raw.discovered === "object" ? raw.discovered : {},
    records: raw.records && typeof raw.records === "object" ? raw.records : {},
    mastery: raw.mastery && typeof raw.mastery === "object" ? raw.mastery : {},
    totalCaught: num(raw.totalCaught, 0), mythical: raw.mythical === true,
    holdCasts: num(raw.holdCasts, 0),               // hold-to-charge casts so far (the "hold CAST" hint stops after 3); old saves: 0
    sound: raw.sound !== false,                       // older saves have no sound setting: default on
    music: raw.music !== false,                       // ... and no music setting: default on
    fightStyle: FIGHT_STYLES.includes(raw.fightStyle) ? raw.fightStyle : DEFAULT_FIGHT,   // "hold" (Hold Fight) or "tap" (classic marker); anything else = the default
    pending: validCatch(raw.pending) ? raw.pending : null,   // a catch still waiting for KEEP / RELEASE
  };
  s.bag = s.bag.slice(0, s.bagMax);
  return s;
}
// The fish shown on the Result screen stays in the save until KEEP or RELEASE, so closing the page can't lose it.
function validCatch(p) { return !!p && typeof p === "object" && !!fishById(p.fishId) && Number.isFinite(p.weight) && Number.isFinite(p.price); }
let S = load();
function save() { try { localStorage.setItem(SAVE_KEY, JSON.stringify(S)); } catch (e) {} }
// A game exists if the save holds anything besides the sound / music settings (toggling them on the
// Title screen before starting a game stores only { sound, music } (plus fightStyle when it was changed in How to Play)).
function hasSave() {
  try { const raw = JSON.parse(localStorage.getItem(SAVE_KEY)); return !!raw && typeof raw === "object" && Object.keys(raw).some(k => k !== "sound" && k !== "music" && k !== "fightStyle"); }
  catch (e) { return false; }
}
function saveSound() {                               // Sound and Music settings (also used for both toggles)
  if (hasSave()) return save();
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(S.fightStyle === DEFAULT_FIGHT ? { sound: S.sound, music: S.music } : { sound: S.sound, music: S.music, fightStyle: S.fightStyle })); } catch (e) {}
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
/* ===================== AUDIO (Playtest 1, part 11) =====================
   One shared AudioContext, created and resumed on the first user gesture (browsers keep it suspended before that, and iOS needs the resume inside a
   touch). Graph: sfx bus ----------------------\
                  theme gain > duck > music bus --+> master > compressor > speakers.
   Sound (S.sound) opens the sfx bus, Music (S.music) the music bus (quieter: MUSIC_VOL). Everything is made in code; no audio files.
   Music is a small step sequencer: a 120 ms timer schedules the next notes ~0.35 s ahead on the audio clock, so CPU use stays tiny. */
let AC;                                              // the AudioContext; stays undefined until the first gesture
const MUSIC_VOL = .25, DUCK_VOL = .4, MUSIC_TRIM = .5;   // music bus .25; each theme's own level .5 keeps the song well below the effects
const AUD = { master: null, sfx: null, music: null, duck: null, noise: null, cur: null, ducked: false, notes: 0 };
function audioInit() {
  if (AC) return true;
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext; if (!Ctx) return false;
    try { if (navigator.audioSession) navigator.audioSession.type = "playback"; } catch (e) {}   // iOS: play even with the silent switch on
    const ctx = new Ctx(), comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -16; comp.knee.value = 24; comp.ratio.value = 3; comp.attack.value = .004; comp.release.value = .2;
    AUD.master = ctx.createGain(); AUD.sfx = ctx.createGain(); AUD.music = ctx.createGain(); AUD.duck = ctx.createGain();
    AUD.sfx.connect(AUD.master); AUD.duck.connect(AUD.music); AUD.music.connect(AUD.master); AUD.master.connect(comp); comp.connect(ctx.destination);
    const nb = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate), d = nb.getChannelData(0);   // 1 s of white noise, looped by every noise voice
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    AUD.noise = nb; AC = ctx; audioApply();
    AC.addEventListener && AC.addEventListener("statechange", () => { if (AC.state === "running") { audioGestureDone(); musicSync(); } });
    return true;
  } catch (e) { return false; }
}
// the switches: master is open while either Sound or Music is on; each bus has its own level
function audioApply() {
  if (!AC) return;
  try {
    AUD.master.gain.value = S.sound || S.music ? 1 : 0;
    AUD.sfx.gain.value = S.sound ? 1 : 0;
    AUD.music.gain.value = S.music ? MUSIC_VOL : 0;
    AUD.duck.gain.setTargetAtTime(AUD.ducked ? DUCK_VOL : 1, AC.currentTime, .06);
  } catch (e) {}
}
function audioUnlock() {
  if (!audioInit()) return;
  try {
    if (AC.state !== "running") { const p = AC.resume(); if (p && p.then) p.then(() => { if (AC.state === "running") { audioGestureDone(); musicSync(); } }, () => {}); }
    const s = AC.createBufferSource(); s.buffer = AC.createBuffer(1, 1, 22050); s.connect(AC.destination); s.start(0);   // a silent blip inside the gesture wakes iOS audio
  } catch (e) {}
  musicSync();
}
const GESTURES = ["pointerdown", "keydown", "touchend", "click"];
function audioGestureDone() { if (AC && AC.state === "running") GESTURES.forEach(ev => document.removeEventListener(ev, audioUnlock, true)); }
GESTURES.forEach(ev => document.addEventListener(ev, audioUnlock, true));
document.addEventListener("visibilitychange", () => {      // a hidden tab is silent and idle; coming back resumes it
  if (!AC) return;
  try {
    if (document.hidden) { musicPause(); AC.suspend && AC.suspend(); }
    else { const p = AC.resume(); const go = () => { musicResume(); musicSync(); }; p && p.then ? p.then(go, go) : go(); }
  } catch (e) {}
});

/* ---- one voice: an oscillator with an envelope, on any bus, at an absolute time ---- */
function voice(freq, t, dur, type, vol, bus, o = {}) {
  const osc = AC.createOscillator(), g = AC.createGain(); let out = osc;
  osc.type = type; osc.frequency.setValueAtTime(freq, t);
  if (o.to) osc.frequency.exponentialRampToValueAtTime(o.to, t + dur);
  if (o.lp) { const f = AC.createBiquadFilter(); f.type = "lowpass"; f.frequency.setValueAtTime(o.lp, t); f.frequency.exponentialRampToValueAtTime(Math.max(200, o.lp / 3), t + dur); osc.connect(f); out = f; }
  g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + (o.attack || .008)); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
  out.connect(g); g.connect(bus); osc.start(t); osc.stop(t + dur + .03);
}
function noiseVoice(t, dur, vol, ftype, f0, f1, bus, q = 1) {
  const src = AC.createBufferSource(), f = AC.createBiquadFilter(), g = AC.createGain();
  src.buffer = AUD.noise; src.loop = true; f.type = ftype; f.Q.value = q;
  f.frequency.setValueAtTime(f0, t); f.frequency.exponentialRampToValueAtTime(f1, t + dur);
  g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + Math.min(.04, dur * .35)); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
  src.connect(f); f.connect(g); g.connect(bus); src.start(t); src.stop(t + dur + .03);
}
// sound effects only run with Sound on and a running context; a failure never reaches the game
const sfxOn = () => !!(S.sound && AC && AC.state === "running" && AUD.sfx);
function tone(freq, dur = .12, type = "square", vol = .22, delay = 0, o) { if (!sfxOn()) return; try { voice(freq, AC.currentTime + .005 + delay, dur, type, vol, AUD.sfx, o); } catch (e) {} }
function noise(dur, vol, ftype, f0, f1, delay = 0, q = 1) { if (!sfxOn()) return; try { noiseVoice(AC.currentTime + .005 + delay, dur, vol, ftype, f0, f1, AUD.sfx, q); } catch (e) {} }
function beep(freq, dur = .12, type = "square", vol = .22) { tone(freq, dur, type, vol); }   // kept for old callers
const sfx = {
  whoosh: () => noise(.4, 1.1, "bandpass", 350, 2600, 0, .9),                                    // cast: a rising filtered-noise sweep
  splash: () => { noise(.3, .34, "lowpass", 2200, 350); tone(260, .12, "sine", .16, .02, { to: 120 }); },   // bobber lands: a low-passed noise burst + a plop
  bite: () => { tone(1320, .16, "sine", .26); tone(1976, .2, "triangle", .2); tone(1320, .16, "sine", .26, .15); tone(1976, .22, "triangle", .2, .15); },   // two bright pings
  hit: () => tone(520, .12, "square", .2, 0, { to: 1040 }),                                          // a rising blip
  miss: () => { tone(110, .24, "sawtooth", .24, 0, { lp: 900 }); tone(104, .24, "square", .12); },   // a low buzz
  fail: () => tone(560, .5, "triangle", .27, 0, { to: 150 }),                                        // escape: a falling tone
  catch: () => [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => { tone(f, i === 3 ? .42 : .16, "triangle", .27, i * .11); tone(f * 2, i === 3 ? .3 : .12, "sine", .1, i * .11); }),   // 4-note fanfare
  coin: () => { tone(1318.5, .09, "square", .17); tone(1760, .2, "square", .17, .075); },            // two quick high notes
  tick: () => tone(760, .05, "triangle", .2, 0, { to: 380 }),                                        // equip / lock / Title toggles: their own confirmation tick
  reelTick: tension => tone(640 + 700 * tension, .03, "square", .045, 0, { to: 420 + 500 * tension }),   // the reel ratchet while fighting: quiet, faster and higher with tension (Fight feel, Playtest 2 part 2)
  bigSplash: () => { noise(.45, .5, "lowpass", 1500, 160); tone(150, .28, "sine", .24, 0, { to: 65 }); },   // a Legendary / Mythical leap: a deeper, bigger splash
  click: () => tone(1900, .035, "sine", .05, 0, { to: 1500, attack: .002 }),                         // ordinary menu buttons: a very short, soft, high tick (quieter than every other effect)
};
sfx.cast = sfx.whoosh;                               // the cast sound is the whoosh
// One delegated listener gives every ordinary button a soft click (Playtest 1, part 14). Buttons that make their own sound or feedback carry data-nosound
// (the CAST / HOOK / REEL button, SELL ALL / SELL A FISH, single SELL, buying, EQUIP / USE and the rod / bait cards, the Bag lock, the Title SOUND / MUSIC toggles);
// disabled buttons are silent. Sound OFF is silent because tone() checks it.
document.addEventListener("click", e => {
  const b = e.target && e.target.closest ? e.target.closest("button") : null;
  if (!b || b.disabled || b.closest("[data-nosound]")) return;
  sfx.click();
}, true);

/* ---- music: themes ---- */
// root: MIDI note of scale degree 1; scale: semitones (any length); chords: scale degree of the chord root for each of 8 bars (stacked in thirds from the scale);
// mel: two 4-bar phrases, 8 eighth-note slots per bar ("." rest, 1..n scale degrees, n above the scale length = next octave); bass: 8 slots (1 root, 2 fifth, 3 octave);
// hat: 8 slots; lead: instrument; pad: held chord volume; bpm counts quarter notes (a slot is an eighth)
const THEMES = {
  home: { root: 60, scale: [0, 2, 4, 5, 7, 9, 11], bpm: 80, lead: "tri", chords: [1, 5, 6, 4, 1, 5, 4, 5], bass: [1, 0, 0, 0, 2, 0, 0, 0], hat: [0, 0, 0, 0, 0, 0, 0, 0], pad: .16,
    mel: "3 . 5 . 6 . 5 3 | 2 . 3 . 5 . . . | 3 . 5 . 8 . 6 5 | 3 . 2 . 1 . . . | 6 . 8 . 9 . 8 6 | 5 . 6 . 8 . . . | 9 . 8 . 6 . 5 3 | 2 . 3 . 5 . 1 ." },
  harbor: { root: 62, scale: [0, 2, 4, 5, 7, 9, 10], bpm: 112, lead: "square", chords: [1, 4, 1, 5, 1, 4, 5, 1], bass: [1, 0, 2, 0, 1, 0, 2, 0], hat: [0, 0, 1, 0, 0, 0, 1, 0], pad: .08,
    mel: "1 . 3 5 6 . 5 3 | 4 . 6 8 6 . 4 . | 1 . 3 5 6 . 5 3 | 5 . 4 3 2 . 1 . | 5 . 6 8 9 . 8 6 | 8 . 9 11 9 . 8 . | 7 . 6 5 4 . 5 6 | 8 . 5 3 1 . . ." },
  frost: { root: 72, scale: [0, 2, 4, 7, 9], bpm: 64, lead: "bell", chords: [1, 3, 4, 2, 1, 3, 5, 1], bass: [1, 0, 0, 0, 0, 0, 0, 0], hat: [0, 0, 0, 0, 0, 0, 0, 0], pad: .12,
    mel: "5 . . . 3 . . . | . . 4 . 2 . . . | 5 . . . 6 . 5 . | . . 3 . . . . . | 6 . . . 8 . . . | . . 7 . 5 . . . | 6 . 5 . 3 . . . | 2 . . . 1 . . ." },
  desert: { root: 64, scale: [0, 1, 4, 5, 7, 8, 10], bpm: 104, lead: "pluck", chords: [1, 1, 2, 1, 1, 4, 5, 1], bass: [1, 0, 1, 0, 2, 0, 3, 0], hat: [0, 0, 1, 0, 0, 0, 1, 1], pad: .06,
    mel: "1 . 2 3 4 . 3 2 | 1 . 2 3 5 . 4 3 | 2 . 3 4 5 . 4 3 | 2 . 1 . . . . . | 5 . 6 7 8 . 7 6 | 5 . 6 7 9 . 8 7 | 6 . 5 4 3 . 2 3 | 1 . . . 1 . . ." },
  forest: { root: 67, scale: [0, 2, 4, 5, 7, 9, 11], bpm: 76, lead: "flute", chords: [1, 6, 4, 5, 1, 6, 4, 5], bass: [1, 0, 0, 0, 2, 0, 0, 0], hat: [0, 0, 0, 0, 0, 0, 0, 0], pad: .12,
    mel: "1 2 3 5 3 2 1 . | 6 7 8 6 5 3 2 . | 4 5 6 8 6 5 4 . | 5 3 2 3 5 . . . | 3 5 6 8 9 8 6 5 | 6 8 9 10 9 . 8 . | 8 6 5 4 5 6 4 . | 5 . 3 . 1 . . ." },
  secret: { root: 50, scale: [0, 1, 3, 5, 7, 8, 10], bpm: 54, lead: "flute", melOct: 12, chords: [1, 1, 2, 1, 6, 5, 2, 1], bass: [1, 0, 0, 0, 0, 0, 0, 0], hat: [0, 0, 0, 0, 0, 0, 0, 0], pad: .26,
    mel: "5 . . . . . 6 . | . . . . 5 . . . | 4 . . . 3 . . . | . . 2 . . . . . | 5 . . . 8 . 7 . | . . . . 6 . . . | 5 . . . 4 . 3 . | 2 . . . 1 . . ." },
};
for (const id in THEMES) {                           // parse the melody once: slot -> MIDI note + length in slots
  const T = THEMES[id], toks = T.mel.split(/[\s|]+/).filter(Boolean), L = T.scale.length;
  T.note = i => T.root + T.scale[((i % L) + L) % L] + 12 * Math.floor(i / L);
  T.m = toks.map((k, i) => { if (k === ".") return null; let n = 1; while (toks[i + n] === "." && n < 4) n++; return { midi: T.note(parseInt(k, 10) - 1) + (T.melOct || 0), len: n }; });
}
const MUSIC_BARS = 8, MUSIC_LOOK = .35;
function musicTheme() { return typeof current !== "undefined" && current === "fishing" && THEMES[island] ? island : "home"; }
const mhz = m => 440 * Math.pow(2, (m - 69) / 12);
function musicStep(inst, step, t) {                  // schedule everything that sounds on one eighth-note slot
  const T = THEMES[inst.id], bus = inst.gain, sd = 30 / T.bpm, slot = step % 8, bar = Math.floor(step / 8) % MUSIC_BARS, deg = T.chords[bar] - 1, n = T.m[step % T.m.length];
  if (n) {
    const m = n.midi, d = n.len * sd * .95, f = mhz(m);
    if (T.lead === "bell") { voice(f, t, d * 3.2, "sine", .55, bus, { attack: .004 }); voice(f * 2.76, t, d * 1.4, "sine", .16, bus, { attack: .004 }); }
    else if (T.lead === "pluck") voice(f, t, Math.min(d, .4), "sawtooth", .34, bus, { lp: 2600, attack: .004 });
    else if (T.lead === "flute") { voice(f, t, d * 1.1, "sine", .5, bus, { attack: .07 }); voice(f * 2, t, d, "sine", .06, bus, { attack: .09 }); }
    else if (T.lead === "square") voice(f, t, Math.min(d, .5), "square", .2, bus, { lp: 3200, attack: .006 });
    else voice(f, t, d * 1.05, "triangle", .55, bus, { attack: .012 });
    AUD.notes++;
  }
  const b = T.bass[slot];
  if (b) { const bi = deg + (b === 2 ? 4 : 0), m = T.note(bi) - 24 + (b === 3 ? 12 : 0); voice(mhz(m), t, sd * 1.8, "triangle", .6, bus, { attack: .01 }); AUD.notes++; }
  if (slot === 0 && T.pad) for (const k of [0, 2, 4]) voice(mhz(T.note(deg + k) - 12), t, sd * 8, "sine", T.pad, bus, { attack: sd * 1.5 });
  if (T.hat[slot]) noiseVoice(t, .05, .1, "highpass", 7000, 9000, bus);
}
function musicTick(inst) {
  if (inst.dead || !AC) return;
  const T = THEMES[inst.id], sd = 30 / T.bpm;
  try { while (inst.next < AC.currentTime + MUSIC_LOOK) { musicStep(inst, inst.step, inst.next); inst.step++; inst.next += sd; } } catch (e) {}
  inst.timer = setTimeout(() => musicTick(inst), 120);
}
function musicStop(fade = .25) {
  const inst = AUD.cur; AUD.cur = null; if (!inst) return;
  inst.dead = true; clearTimeout(inst.timer); inst.timer = null;
  try { inst.gain.gain.cancelScheduledValues(AC.currentTime); inst.gain.gain.setValueAtTime(inst.gain.gain.value, AC.currentTime); inst.gain.gain.linearRampToValueAtTime(0, AC.currentTime + fade);
    setTimeout(() => { try { inst.gain.disconnect(); } catch (e) {} }, fade * 1000 + 250); } catch (e) {}
}
function musicStart(id) {
  const old = AUD.cur; if (old) musicStop(.6);        // crossfade: the old theme fades out while the new one fades in
  const g = AC.createGain(); g.gain.setValueAtTime(0, AC.currentTime); g.gain.linearRampToValueAtTime(MUSIC_TRIM, AC.currentTime + .6); g.connect(AUD.duck);
  const inst = { id, gain: g, step: 0, next: AC.currentTime + .08, timer: null, dead: false }; AUD.cur = inst; musicTick(inst);
}
// start, change or stop the music so it matches the screen / island and the Music switch (called by go(), the toggles and the gesture)
function musicSync() {
  try {
    if (!AC || AC.state !== "running") return;
    if (!S.music || document.hidden) { if (AUD.cur && !document.hidden) musicStop(); return; }
    const id = musicTheme(); if (AUD.cur && AUD.cur.id === id) return;
    musicStart(id);
  } catch (e) {}
}
function musicPause() { const c = AUD.cur; if (c) { clearTimeout(c.timer); c.timer = null; } }
function musicResume() { const c = AUD.cur; if (c && !c.timer && AC) { c.next = Math.max(c.next, AC.currentTime + .05); musicTick(c); } }
function musicDuck(on) { AUD.ducked = !!on; if (AC) try { AUD.duck.gain.setTargetAtTime(on ? DUCK_VOL : 1, AC.currentTime, .06); } catch (e) {} }
// for the tests: what the audio layer is doing right now
function audioState() {
  return { ctx: AC ? AC.state : null, master: AUD.master ? AUD.master.gain.value : null, sfx: AUD.sfx ? AUD.sfx.gain.value : null, music: AUD.music ? AUD.music.gain.value : null,
    duck: AUD.duck ? AUD.duck.gain.value : null, theme: AUD.cur ? AUD.cur.id : null, ticking: !!(AUD.cur && AUD.cur.timer), notes: AUD.notes, ducked: AUD.ducked };
}
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
  if (f.plan) return f.plan;                  // the 9 creature plans (jellyfish, crab, ...)
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
/* Creature plans (Playtest 1, part 10): fish with a `plan` (see RAW in data.js) are not drawn from the fish template but from a hand-made 24x16 map of
   palette letters: O outline, B body, D dark back, L belly, F fin / tentacle / leg, G fin edge, S accent (the fish's stripe colour), W shine.
   The maps are generated by tools/make_fish_plans.py (python tools/make_fish_plans.py --write). */
/* PLANS BEGIN */
const FISH_PLANS = {   // generated by tools/make_fish_plans.py; letters: O outline, B body, D dark back, L belly, F fin, G fin edge, S accent, W shine
  jellyfish: [
    "........................",
    ".........OOOOOO.........",
    ".......OODDDDDDOO.......",
    ".....OOWWBBBBBBBBOO.....",
    "....OBBWBBBBBBBBBBBO....",
    "...OBBBBBBSBBSBBBBBBO...",
    "...OBBBBBBBSSBBBBBBBO...",
    "...OBBBBBBBBBBBBBBBBO...",
    "..OLLLLLLLLLLLLLLLLLLO..",
    "...OGOGOGOLSGLGOGOGOO...",
    ".....F..F.L.SL.F..F.....",
    "......F..FLS.L..F..F....",
    ".....F..F.L.SL.F..F.....",
    "......F..FLS.L..F..F....",
    ".....F..F......F..F.....",
    "......F............F....",
  ],
  crab: [
    "........................",
    "........................",
    "OOOOO....O....O....OOOOO",
    "FFGFFO..OWO..OWO..OFFGFF",
    "FFFFFO..OBO..OBO..OFFFFF",
    "FFFFFO.OOBOOOOBOO.OFFFFF",
    "FFFFFOODDWWDDDDDDOOFFFFF",
    "OOFFOBBBBBBSBBBBBBBOFFOO",
    "..OOFBBBSBBBBSBBBBBBFO..",
    "...OFBBBBBBBBBBBBBBFO...",
    "...OBBBSBBSBBBBSBBBBO...",
    "...FBBBBLLLLLLLLBBBBF...",
    "..F.OLLLLLLLLLLLLLLO.F..",
    "..F..OLLLLLLLLLLLLO..F..",
    ".F....OOOOOOOOOOOO....F.",
    ".F....................F.",
  ],
  seahorse: [
    "......OOO...............",
    ".....OFFFOOO............",
    "....OFOBBBBBO...........",
    "....OFOBWOBBOOOOO.......",
    ".....OBBBBBBBBBBLO......",
    "......OBBBBBBBBBLO......",
    ".....FOBBBBBOOOOO.......",
    "....FFOBBSSSBO..........",
    "....FFBBBLLLLBO.........",
    "....FFBBBSSSLBO.........",
    "....FFOBBLLLLO..........",
    "....F.OBBSSSBO..........",
    ".......OBBBOBLO.........",
    ".......OBBOOBBO.........",
    ".......OBBBBBO..........",
    "........OOOOO...........",
  ],
  shark: [
    ".........O..............",
    "........OFO.............",
    ".OOOO...OFO.............",
    "OFFFFO..OFFO............",
    ".OFFO..OFFFFOOOOOO......",
    ".OFFFO.OFFFFFDDDDDOOO...",
    "..OFFOODDDDDWWDDDDDDDO..",
    "..OFFFDDBBBBBBDDDBWOBDO.",
    "...OBBBBBBBBBBDDDBBBBBBO",
    "...OFFLLLLBBBBDDDBBLLOO.",
    "..OFFOOLLLLLLLLLLLLOOO..",
    ".OFOFO.OOOLLLLLLLLOOO...",
    ".OFFO.....OGGGOOOO......",
    "OFFFFO...OGGGO..........",
    ".OOOO.....OOO...........",
    "........................",
  ],
  squid: [
    "...........OO...........",
    ".........OODLOO.........",
    "........OFODBOFO........",
    ".......OGFDBBLFGO.......",
    "......OGFFDSBLFFGO......",
    ".......OGFDBSLFGO.......",
    ".......ODFSBBBFLO.......",
    ".......ODDDBBSLLO.......",
    "......ODDDDSBBLLLO......",
    "......OBBWOBBOWBBO......",
    "......OBBOBBBBOBBO......",
    ".......OLLLLLLLLO.......",
    "........FOFOOFOF........",
    "........F..FF..F........",
    "........F.F..F.F........",
    "........G..GG..G........",
  ],
  turtle: [
    "........................",
    "........................",
    "........................",
    "........................",
    "........OOOOOOO.........",
    ".......OSWWSBBSOO.......",
    ".....OOBWBBSBBSBBOO.....",
    "....OBSSSSSSSSSSSSBOOOO.",
    "....OBBBSBBSBBSBBBBFFWOO",
    "...OBBBBSBBSBBSBBBBFFFFO",
    ".OOOBBBBBBBBBBBBBFFFFFFO",
    "OFFFDDDDDDDDDDDDDFFFFFOO",
    "OFFFLLLLLLLLLLLLLFFLLOO.",
    ".OOOOFFFOFFOOFFOFFFOO...",
    "....OFFFOFFOOFFOFFFO....",
    ".....OOO.OO..OO.OOO.....",
  ],
  frog: [
    "........................",
    "........................",
    "................OO......",
    "...............OBBO.....",
    "..............OBBBBO....",
    "..............OWWOBO....",
    ".......OOOOOOOBWWOBBO...",
    ".....OOBBWWBBBSBBBBBBO..",
    "....OBBBBSBBSBBBBBBBBBO.",
    "...ODDDDDBBBBBBBBBBBBBO.",
    "..ODDDDSDDBSBBBBBOOOOOOO",
    "..ODDDDDDDBBBBLLLLLLLLO.",
    "..ODDDDDDDLLLLLLLBBBOO..",
    ".OODDDDDDDLLLLBBBBBO....",
    "OBBBBBBBBLLLLLFFFFFO....",
    ".OOOOOOOOOOOOOOOOOO.....",
  ],
  axolotl: [
    "........................",
    ".............G.G.G......",
    "..............F.F.F.....",
    "..........L..LF.FOFO....",
    "..........BO.BFOFBFBOO..",
    "......OOOOBBOBBBBBBBBBO.",
    "..OOOOBBBBBSBBBBBBBWOBBO",
    ".OBBBBBBBSBBBBBBBBBBBBBO",
    "OBBBBLBLBBBBBBBBBBBBBBBB",
    ".OBBBBBBSLLLLLLBBBBBBBBO",
    "..OOOOBBLLLLLLLBBBBWOBBO",
    "......OOOOBLOBBBBBBBBBO.",
    "..........BO.BFOFBFBOO..",
    "..........L..LF.FOFO....",
    "..............F.F.F.....",
    ".............G.G.G......",
  ],
  crayfish: [
    "........................",
    "....................OOO.",
    "...................OFFFO",
    "...........F.F.F..OFFFFF",
    "............F.FOFOFFFGOF",
    ".OOOOOOOOOO.OOBBBFFOFFFO",
    "OGFFFSDSDSDOBWWBBBWOOOO.",
    "OFFFFSDSDSDBBBBBBBBBBO..",
    "OGGFFSDSDSDBBBBBBBBBFFF.",
    "OFFFFSDSDSDBBBBBBBBBBO..",
    "OGFFFSDSDSDOBBBBBBWOOOO.",
    ".OOOOOOOOOO.OOBBBFFOFFFO",
    "............F.FOFOFFFGOF",
    "...........F.F.F..OFFFFF",
    "...................OFFFO",
    "....................OOO.",
  ],
};
/* PLANS END */
function drawPlan(cv, f) {
  const c = cv.getContext("2d"), map = FISH_PLANS[f.plan], dark = f.dark, OUT = "#0b1d27";
  const pal = dark ? { O: OUT, B: f.body, D: f.body, L: f.body, F: f.body, G: f.body, S: f.body, W: f.body }
    : { O: OUT, B: f.body, D: shade(f.body, -.22), L: f.belly, F: f.fin, G: shade(f.fin, -.3), S: f.stripe || shade(f.body, -.3), W: "#ffffff" };
  const grid = new Array(24 * 16).fill(null);
  map.forEach((row, y) => { for (let x = 0; x < 24; x++) { const k = row[x]; if (k !== "." && pal[k]) grid[y * 24 + x] = pal[k]; } });
  const get = (x, y) => (x >= 0 && x < 24 && y >= 0 && y < 16) ? grid[y * 24 + x] : null, set = (x, y, col) => { grid[y * 24 + x] = col; };
  const tier = { Rare: 1, Epic: 2, Legendary: 3, Mythical: 3 }[f.rarity] || 0;
  if (!dark && tier) {                                                    // glint: one white pixel on the first body pixel found from the top, left of centre
    for (let y = 0; y < 16; y++) { const x = [10, 9, 11, 8, 12].find(x => get(x, y) === f.body); if (x !== undefined) { set(x, y, "#ffffff"); break; } }
  }
  if (!dark && tier >= 2) {                                               // sparkles around Epic and better, like the fish template
    const spark = (x, y, col) => { if (get(x, y) || get(x - 1, y) || get(x + 1, y) || get(x, y - 1) || get(x, y + 1)) return;
      set(x, y, "#ffffff"); set(x - 1, y, col); set(x + 1, y, col); set(x, y - 1, col); set(x, y + 1, col); };
    const gold = f.rarity === "Mythical" ? "#ff80ab" : "#fff59d";
    if (tier === 2) { if (!get(21, 2)) set(21, 2, "#fff59d"); } else { spark(21, 2, gold); spark(2, 13, gold); }
  }
  for (let y = 0; y < 16; y++) for (let x = 0; x < 24; x++) { const col = grid[y * 24 + x]; if (col) { c.fillStyle = col; c.fillRect(x, y, 1, 1); } }
}
function drawFish(cv, f) {
  const c = cv.getContext("2d"); cv.width = 24; cv.height = 16; c.clearRect(0, 0, 24, 16);
  if (f.plan && FISH_PLANS[f.plan]) return drawPlan(cv, f);
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
const rod = () => RODS[S.rodEq];                     // equipped rod
const allowedMiss = () => rod().miss + (S.mastery.forest ? 1 : 0);
const bagFull = () => S.bag.length >= S.bagMax;   // locked fish count too
const unlockedIdx = () => S.bag.map((b, i) => b.locked ? -1 : i).filter(i => i >= 0);
const unlockedTotal = () => unlockedIdx().reduce((t, i) => t + S.bag[i].price, 0);   // prices already include the Golden Hook bonus
// Rarity chances in % (Common, Rare, Epic, Legendary) for one cast: base odds + bait + Lucky Rod + Lucky Lure,
// each tier at least 0, scaled to 100%, then Legendary capped at LEGENDARY_CAP (the rest goes to Epic).
function rarityWeights(baitId = "none", rodId = S.rodEq) {
  const w = [...BASE_ODDS], add = d => d.forEach((v, i) => w[i] += v);
  if (BAITS[baitId]) add(BAITS[baitId].odds);
  if (RODS[rodId] && RODS[rodId].luck) add(LUCKY_ROD_ODDS);
  if (S.mastery.desert) add(LUCKY_LURE_ODDS);
  const pos = w.map(v => Math.max(0, v)), tot = pos.reduce((a, b) => a + b);
  const p = pos.map(v => v / tot * 100);
  if (p[3] > LEGENDARY_CAP) { p[2] += p[3] - LEGENDARY_CAP; p[3] = LEGENDARY_CAP; }
  return p;
}
const pct = v => `${Math.round(v * 10) / 10}%`;
const oddsText = w => TIERS.map((t, i) => `${t} ${pct(w[i])}`).join(" · ");
// one-line effect of a rod, e.g. "1 miss allowed, green zone 35% wider."
function rodFx(id) {
  const r = RODS[id], p = [`${misses(r.miss)} allowed`];
  if (r.zone !== 1) p.push(`green zone ${Math.round((r.zone - 1) * 100)}% wider`);
  if (r.luck) p.push("better rarity odds (like Shrimp bait)");
  if (r.speed !== 1) p.push(`minigame ${Math.round((r.speed - 1) * 100)}% faster`);
  if (p.length === 1) p.push("normal zone and speed");
  return p.join(", ") + ".";
}
const baitName = id => BAITS[id] ? BAITS[id].name : "No bait";
// equip a float you own (Tackle Box, the FLOAT chip, or right after buying it); never mid-cast
function equipFloat(id) {
  sfx.tick();
  if (!FLOATS[id] || !S.floatsOwned.includes(id) || (typeof F !== "undefined" && F.phase !== "idle")) return;
  S.floatEq = id; save(); toast(`Equipped: ${FLOATS[id].name}`); render();
}
// equip a rod you own / select a bait you have (or "none"); used by the Tackle Box and the fishing HUD
function equipRod(id) {
  sfx.tick();
  if (!S.rods.includes(id) || (typeof F !== "undefined" && F.phase !== "idle")) return;
  S.rodEq = id; save(); toast(`Equipped: ${RODS[id].name}`); render();
}
function selectBait(id) {
  if ((id !== "none" && !(S.baits[id] > 0)) || (typeof F !== "undefined" && F.phase !== "idle")) return;
  S.baitSel = id; save(); sfx.tick(); toast(id === "none" ? "No bait: your bait is saved for later." : `Using ${BAITS[id].name}: ${BAITS[id].blurb}`); render();
}
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
