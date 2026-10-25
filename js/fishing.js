/* ===================== FISHING ===================== */
// Fishing scene, bite timing and the reeling minigame. Loaded after state.js, before screens.js.
let island = "harbor";   // island currently being fished (chosen on the Town Map)
const cv = $("sceneCanvas"), ctx = cv.getContext("2d");
const harborImg = new Image(); harborImg.src = "assets/harbor.jpg";
let ROD_TIP = { x: .27, y: .25 }; const BOB = { x: .58, y: .66 };
function fitCanvas() { const r = cv.getBoundingClientRect(); if (r.width) { cv.width = 900; cv.height = Math.round(900 * r.height / r.width); } ROD_TIP = island === "harbor" ? { x: .34, y: .31 } : { x: .27, y: .25 }; }
window.addEventListener("resize", () => current === "fishing" && fitCanvas());
let F = { phase: "idle" }, raf = null, timers = [];
function later(fn, ms) { const t = setTimeout(fn, ms); timers.push(t); return t; }
function clearTimers() { timers.forEach(clearTimeout); timers = []; }

function drawScene(t) {
  const W = cv.width, H = cv.height;
  ctx.imageSmoothingEnabled = false;
  if (island === "harbor" && harborImg.complete && harborImg.naturalWidth) {
    const ir = harborImg.naturalWidth / harborImg.naturalHeight, cr = W / H;
    let sw = harborImg.naturalWidth, sh = harborImg.naturalHeight, sx = 0, sy = 0;
    if (ir > cr) { sw = sh * cr; sx = 0; } else { sh = sw / cr; sy = 0; }
    ctx.drawImage(harborImg, sx, sy, sw, sh, 0, 0, W, H);
  } else {
    const pal = { frost: ["#cfe9ff", "#f2fbff", "#7fb8e0"], desert: ["#ffcf7a", "#e8b45e", "#2fb8a8"], forest: ["#7cc6e8", "#2f7d3a", "#2a8fb0"], secret: ["#1b1440", "#3b2a7a", "#12325e"], harbor: ["#7fd0f5", "#5aa", "#1f8fc4"] }[island];
    ctx.fillStyle = pal[0]; ctx.fillRect(0, 0, W, H * .4);
    ctx.fillStyle = pal[1]; ctx.fillRect(0, H * .4, W, H * .12);
    ctx.fillStyle = pal[2]; ctx.fillRect(0, H * .52, W, H * .48);
    ctx.fillStyle = "rgba(255,255,255,.25)";
    for (let i = 0; i < 18; i++) ctx.fillRect((i * 97 + t / 30) % W, H * (.58 + (i % 6) * .07), 40, 3);
    if (island === "secret") { ctx.fillStyle = "#fff6c2"; ctx.beginPath(); ctx.arc(W * .8, H * .18, 26, 0, 7); ctx.fill(); }
    // dock + fisherman
    ctx.fillStyle = "#6b4423"; ctx.fillRect(0, H * .55, W * .3, H * .1);
    ctx.fillStyle = "#4a2d14"; for (let i = 0; i < 4; i++) ctx.fillRect(W * (.03 + i * .08), H * .62, 14, H * .3);
    ctx.fillStyle = "#2b4e9b"; ctx.fillRect(W * .2, H * .38, 34, 46);
    ctx.fillStyle = "#f1c27d"; ctx.fillRect(W * .2 + 6, H * .3, 24, 22);
    ctx.fillStyle = "#e0b04a"; ctx.fillRect(W * .2 - 8, H * .28, 50, 9);
    ctx.strokeStyle = "#3b2a1a"; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(W * .2 + 30, H * .45); ctx.lineTo(W * ROD_TIP.x, H * ROD_TIP.y); ctx.stroke();
  }
  // line + bobber
  if (F.phase !== "idle") {
    let bx = W * BOB.x, by = H * BOB.y;
    if (F.phase === "casting") { const k = Math.min(1, (t - F.castAt) / 500); bx = W * (ROD_TIP.x + (BOB.x - ROD_TIP.x) * k); by = H * (ROD_TIP.y + (BOB.y - ROD_TIP.y) * k) - Math.sin(k * Math.PI) * H * .25; }
    else if (F.phase === "waiting") by += Math.sin(t / 300) * 3;
    else if (F.phase === "bite") by += 8 + Math.sin(t / 40) * 5;
    else if (F.phase === "reeling") by += Math.sin(t / 60) * 6;
    ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(W * ROD_TIP.x, H * ROD_TIP.y); ctx.quadraticCurveTo(W * .45, H * .45, bx, by); ctx.stroke();
    if (F.phase === "bite" || F.phase === "reeling") {
      ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 2;
      const r = 10 + ((t / 8) % 30); ctx.beginPath(); ctx.ellipse(bx, by + 6, r, r / 3, 0, 0, 7); ctx.stroke();
    }
    ctx.fillStyle = "#e53935"; ctx.fillRect(bx - 6, by - 10, 12, 8); ctx.fillStyle = "#fff"; ctx.fillRect(bx - 6, by - 2, 12, 7);
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
  $("fBag").textContent = `${S.bag.length} / ${S.bagMax}`; $("fBait").textContent = S.bait;
  $("fBagBtn").classList.toggle("glow", bagFull());
  const a = $("actBtn");
  if (F.phase === "idle") {
    a.disabled = bagFull(); a.textContent = bagFull() ? "BAG FULL" : "CAST"; a.className = "btn green";
    $("fMsg").textContent = bagFull() ? "Bag full! Sell fish or buy a bigger bag." : `${ISLANDS[island].name}: Ready? Cast your line!`;
    $("dots").textContent = "";
  }
  fitCanvas(); startLoop();
}

function pickFish() {
  if (island === "secret") return FISH.find(f => f.island === "secret");
  let w = S.bait > 0 ? [40, 30, 24, 6] : [60, 30, 8, 2];
  if (S.mastery.desert) w = [w[0] - 8, w[1], w[2] + 5, w[3] + 3];
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
  const usedBait = S.bait > 0; if (usedBait) { S.bait--; save(); }
  F = { phase: "casting", castAt: performance.now(), fish: pickFish() };
  sfx.cast(); $("actBtn").disabled = true; $("actBtn").textContent = "...";
  $("fMsg").textContent = usedBait ? "Cast with bait... waiting" : "Waiting for a bite..."; renderFishingHud();
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
function updateDots() { $("dots").textContent = "HIT " + "●".repeat(F.hits) + "○".repeat(3 - F.hits) + "   MISS " + "✖".repeat(F.misses) + "·".repeat(Math.max(0, allowedMiss() + 1 - F.misses)); }
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
let lastCatch = null;
function caught() {
  const f = F.fish; clearTimers(); F = { phase: "idle" }; $("meter").style.display = "none";
  const skew = Math.pow(Math.random(), 1.6);
  const weight = +(f.min + (f.max - f.min) * skew).toFixed(2);
  const mid = (f.min + f.max) / 2;
  const price = Math.round(f.price * (0.7 + 0.6 * (weight / mid) / 2) * (S.mastery.harbor ? 1.2 : 1));
  const rec = !S.records[f.id] || weight > S.records[f.id];
  const isNew = !S.discovered[f.id];
  lastCatch = { fishId: f.id, weight, price };
  S.discovered[f.id] = true; S.totalCaught++; if (rec) S.records[f.id] = weight;
  if (f.rarity === "Mythical") S.mythical = true;
  save();
  sfx.catch(); vibrate([60, 40, 120]); confetti();
  drawFish($("resCanvas"), f);
  $("resName").textContent = f.name + (isNew ? "  (NEW!)" : "");
  $("resRarity").innerHTML = `<span class="rar-${f.rarity}">${f.rarity}</span> · ${ISLANDS[f.island].name}`;
  $("resWeight").textContent = `Weight: ${weight} kg`;
  $("resPrice").textContent = `Value: ${fmt(price)} coins` + (S.mastery.harbor ? " (Golden Hook +20%)" : "");
  $("resRecord").textContent = rec ? "NEW RECORD!" : "";
  go("result");
  if (f.rarity === "Mythical") setTimeout(() => banner("You caught the Lake Guardian!", "You completed Little Lake. A trophy has been added to your Home screen."), 600);
  else setTimeout(checkMastery, 400);
}
$("keepBtn").onclick = () => {
  if (lastCatch && !bagFull()) { S.bag.push({ ...lastCatch, time: Date.now() }); save(); toast("Saved to your bag."); }
  else if (lastCatch) toast("Bag is full. The fish was released.");
  lastCatch = null; go("fishing");
};
$("releaseBtn").onclick = () => { lastCatch = null; toast("Released. It stays in your Collection Book."); go("fishing"); };
