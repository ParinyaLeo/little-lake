// Hold Fight (Playtest 2, part 3): the pure fight simulation. NO DOM, NO audio, NO globals except the constants below and DIFF (data.js):
// the whole fight is `fightInit(cfg, rng)` + `stepFight(st, dt, holding, rng)`, so the tests (and the balance bots) can run it with a seeded random number generator.
// fishing.js reads `st` to draw the fight and calls the same caught() / escape() functions as the classic tap minigame.
// Loaded after data.js and before state.js / fishing.js (classic script, no modules).
const DEFAULT_FIGHT = "hold";                       // the fight style of new and old saves: "hold" (Hold Fight) or "tap" (the classic marker minigame); flip it here in one line
const FIGHT_STYLES = ["hold", "tap"];
const FIGHT_LIMIT = 35;                             // hard time limit (seconds): the fish escapes
// the fish personality (its movement) follows the rarity; the visual effects of Playtest 2 part 2 use the same names
const FIGHT_PERS = { Common: "steady", Rare: "dash", Epic: "zigzag", Legendary: "leap", Mythical: "leap" };
// physics and rules of the Hold Fight. Track = 0..1. The player's zone accelerates right while the hold is pressed and back left when it is released (a little gravity), drag keeps it
// controllable, the walls bounce it softly. The catch bar fills while the fish is inside the zone and drains (more slowly) while it is outside.
const HF = {
  fill: .27,                                         // catch progress per second while the fish is inside the zone (the same for every rarity)
  start: .22,                                        // progress at the start
  accUp: 3.4, accDown: 3, drag: 2, bounce: .35, // zone acceleration while holding / released (track lengths per second squared), drag per second, wall bounce
  steadyK: .9, dashK: 2, dashRest: .2, zigK: .45, zigMin: .8, zigVar: .6, leapK: 3.2, leapWander: .55,   // fish speed factors by personality (x the fish's speed)
};
// fish speed (track lengths per second) and the player's zone width by rarity, from the existing DIFF table of the classic minigame:
// Common .35 / .22 ... Legendary .9 / .14 (Mythical follows the same line, a little faster and narrower)
function holdParams(rarity) {
  const d = DIFF[rarity] || DIFF.Common;
  return { speed: .35 + (d.speed - .55) / (1.35 - .55) * .55, zone: .14 + (d.zone - .11) / (.26 - .11) * .08 };
}
// Playtest 2, part 11: the green zone also depends on the rod (Hold Fight only; the classic tap minigame keeps RODS[id].zone) and never gets narrower than MIN_ZONE_PX on a narrow track.
// ROD_ZONE multiplies the zone share (Bamboo 1, Precision 1.35 as before; Sturdy and Lucky now widen it a little). Tune the numbers here.
const ROD_ZONE = { bamboo: 1, sturdy: 1.1, precision: 1.35, lucky: 1.25 };
const MIN_ZONE_PX = 44;                              // the zone is at least this many pixels wide (a phone track is ~300 px, a PC track ~900 px: only phones are affected)
const MAX_ZONE = .5;                                 // the zone never covers more than half of the track
// final zone share of the track for a rarity and a rod; trackPx = the track's width in pixels (0 or missing = unknown: no minimum, the PC-sized shares the bot harness uses)
function holdZone(rarity, rodId, trackPx) {
  const z = holdParams(rarity).zone * (ROD_ZONE[rodId] || 1);
  return Math.min(MAX_ZONE, trackPx > 0 ? Math.max(z, MIN_ZONE_PX / trackPx) : z);
}
// the catch bar drains this fast (per second) while the fish is outside the zone, by rarity (after the first contact); the secret-island Lake Guardian uses Mythical
const DRAIN = { Common: .10, Rare: .15, Epic: .185, Legendary: .30, Mythical: .40 };   // tuned with the bot harness (see docs/bug_log.md, Playtest 2 parts 4+5)
// progress after the Nth lost heart (the bar reached 0): 30%, 24%, 18%, 12%, then 10% for the 5th and later
const RESTORE = [.30, .24, .18, .12, .10];
const FISH_MIN = .26;                              // the fish never swims into the first quarter of the track (where the zone rests with no hold), so doing nothing can never win
const fclamp = (v, a, b) => v < a ? a : v > b ? b : v;
// cfg = { personality, speed (fish, track lengths/s), zoneW, hearts (misses allowed: allowedMiss()), limit }
function fightInit(cfg, rng) {
  const c = Object.assign({ rarity: "Common", personality: "steady", speed: .35, zoneW: .22, hearts: 1, limit: FIGHT_LIMIT }, cfg);
  return { cfg: c, t: 0, fx: .6, tx: .6, nextAt: 1, dir: rng() < .5 ? -1 : 1, dashing: false, leapAt: -1, leapN: 0, zx: .3, zv: 0, progress: HF.start, started: false,
    misses: 0, slips: 0, slipAt: -1, inside: false, result: null, reason: "" };
}
function fishMove(st, dt, rng) {
  const c = st.cfg, s = c.speed, p = c.personality;
  let v = 0;
  const toward = (spd, k) => fclamp((st.tx - st.fx) * k, -spd, spd);
  if (p === "dash") {                               // rests, then a short fast dash to a far spot every 1-2 s
    if (!st.dashing && st.t >= st.nextAt) { st.dashing = true; st.tx = farSpot(st, rng, .25); }
    if (st.dashing) { v = toward(HF.dashK * s, 12); if (Math.abs(st.tx - st.fx) < .012) { st.dashing = false; st.nextAt = st.t + 1 + rng(); } }
    else v = Math.sin(st.t * 2.3) * HF.dashRest * s;
  } else if (p === "zigzag") {                      // keeps going one way, reverses every .45-.95 s and at the walls
    if (st.t >= st.nextAt) { st.dir = -st.dir; st.nextAt = st.t + HF.zigMin + rng() * HF.zigVar; }
    v = st.dir * HF.zigK * s;
  } else if (p === "leap") {                        // wanders, and every 2-4 s leaps to a far spot (the leap is drawn for .4 s)
    if (st.t >= st.nextAt) { st.dashing = true; st.tx = farSpot(st, rng, .3); st.leapAt = st.t; st.leapN++; st.nextAt = st.t + 2.2 + rng() * 1.8; }
    if (st.dashing) { v = toward(HF.leapK * s, 12); if (Math.abs(st.tx - st.fx) < .012) { st.dashing = false; st.tx = fclamp(st.fx + (rng() - .5) * .3, FISH_MIN, .92); } }
    else v = toward(HF.leapWander * s, 2);
  } else {                                          // steady: slow side-to-side, a new spot every 1.4-2.6 s
    if (st.t >= st.nextAt) { st.tx = FISH_MIN + rng() * (.92 - FISH_MIN); st.nextAt = st.t + 1.4 + rng() * 1.2; }
    v = toward(HF.steadyK * s, 3);
  }
  st.fx += v * dt;
  if (st.fx < FISH_MIN) { st.fx = FISH_MIN; st.dir = 1; } else if (st.fx > .96) { st.fx = .96; st.dir = -1; }
}
function farSpot(st, rng, minDist) {                // a new target at least `minDist` from the fish
  let x = FISH_MIN + rng() * (.92 - FISH_MIN); if (Math.abs(x - st.fx) < minDist) x = st.fx > .6 ? st.fx - minDist - rng() * .1 : st.fx + minDist + rng() * .1;
  return fclamp(x, FISH_MIN, .92);
}
// advance the fight by dt seconds (dt <= .05). holding = is the player holding the REEL button / Space / the scene. rng() returns [0, 1). Sets st.result = "caught" | "escaped" (st.reason "slips" | "time").
function stepFight(st, dt, holding, rng) {
  if (st.result) return st;
  const c = st.cfg; st.t += dt;
  fishMove(st, dt, rng);
  st.zv += (holding ? HF.accUp : -HF.accDown) * dt; st.zv *= Math.exp(-HF.drag * dt); st.zx += st.zv * dt;
  const max = 1 - c.zoneW;
  if (st.zx < 0) { st.zx = 0; st.zv = Math.abs(st.zv) * HF.bounce; } else if (st.zx > max) { st.zx = max; st.zv = -Math.abs(st.zv) * HF.bounce; }
  st.inside = st.fx >= st.zx && st.fx <= st.zx + c.zoneW;
  if (st.inside) { st.progress += HF.fill * dt; st.started = true; }
  else if (st.started) st.progress -= (DRAIN[c.rarity] || DRAIN.Common) * dt;
  if (st.progress >= 1) { st.progress = 1; st.result = "caught"; return st; }
  if (st.started && st.progress <= 0) {             // the bar ran empty: it slips, one heart is lost (a slip with no hearts left = the fish escapes)
    st.misses++; st.slips++; st.slipAt = st.t; st.progress = RESTORE[Math.min(st.misses, RESTORE.length) - 1];
    if (st.misses > c.hearts) { st.result = "escaped"; st.reason = "slips"; return st; }
  }
  if (st.t >= c.limit) { st.result = "escaped"; st.reason = "time"; }
  return st;
}
// a small seeded random number generator (mulberry32) for the tests and the bots
function seededRng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
