// Screen navigation and the Title, Home, Map, Bag, Shop, Tackle Box, Collection and Demo screens. Loaded last; starts the game.
/* ===================== NAVIGATION =====================
   navStack = the screens behind the current one, so BACK (sticky bar, the Bag's BACK button and Esc) returns to
   where the player came from, like a browser's back button. Home and Title start a fresh history. A Result screen
   is only remembered on the way to the Bag (to make room for the waiting fish), and the same screen is never stored
   twice in a row, so catching fish over and over doesn't grow the history. */
// screens with the BACK bar (Home is the root screen: no BACK bar, it has its MENU button)
const NAV_SCREENS = { map: "TOWN MAP", bag: "BAG", shop: "SHOP", collection: "COLLECTION", tackle: "TACKLE BOX" };
let current = "titleScreen", navStack = [];
function go(id, back = false) {
  // a caught fish is waiting for KEEP / RELEASE: only the Result screen (and the Bag, to make room) can be opened
  if (S.pending && !["result", "bag", "titleScreen"].includes(id)) {
    if (current === "result") return;
    id = "result"; setTimeout(() => toast(`Your ${fishById(S.pending.fishId).name} is waiting: keep it or release it.`), 50);
  }
  if (current === "fishing" && id !== "fishing") stopFishing();
  if (!back && id !== current) {
    if (id === "home" || id === "titleScreen") navStack = [];
    else if (current !== "titleScreen" && !(current === "result" && id !== "bag") && navStack[navStack.length - 1] !== current) {
      navStack.push(current); if (navStack.length > 20) navStack.shift();
    }
  }
  document.querySelectorAll(".screen").forEach(s => s.classList.toggle("active", s.id === id));
  current = id; document.body.classList.toggle("plain", id === "fishing"); document.body.classList.toggle("on-title", id === "titleScreen");
  document.body.classList.toggle("has-nav", !!NAV_SCREENS[id]); $("navName").textContent = NAV_SCREENS[id] || "";
  document.body.classList.toggle("fit", FIT_SCREENS.includes(id));
  document.body.classList.toggle("center", CENTER_SCREENS.includes(id));
  setBackdrop();
  audioApply(); musicSync();                           // the theme follows the screen / island
  render(); window.scrollTo(0, 0);
}
// BACK: the previous screen (skipping a Result screen whose fish was already kept or released), else Home;
// on Home it goes back to the Title screen, where the player came from
// wide windows: these screens are exactly one window tall and their list scrolls inside the panel (css: body.fit)
const FIT_SCREENS = ["bag", "shop", "tackle"];
// wide windows: the panel + buttons of these screens are centred (slightly high) below the header and grow with the window (css: body.center)
const CENTER_SCREENS = ["home", "map", "collection"];   // the Bag is anchored at the top so its buttons never move
function goBack() {
  if (current === "home") return go("titleScreen");
  let id; do { id = navStack.pop(); } while (id && (id === current || (id === "result" && !S.pending)));
  go(id || "home", true);
}
document.addEventListener("click", e => { const b = e.target.closest("[data-go]"); if (b) go(b.dataset.go); });
$("navBack").onclick = goBack;

/* full-screen backdrop: harbor_clean.jpg (no fisherman) on menu screens, the current island while fishing.
   Layers crossfade with opacity; each picture is applied only after it loaded, so a missing file leaves the gradient. */
const BACKDROPS = { harbor: "assets/harbor_clean.jpg", frost: "assets/frost.png", desert: "assets/desert.png", forest: "assets/forest.png", secret: "assets/secret.png" };
function setBackdrop() {
  const k = current === "fishing" && BACKDROPS[island] ? island : "harbor";
  document.querySelectorAll("#backdrop .bd").forEach(el => el.classList.toggle("on", el.dataset.isle === k));
}
function preloadBackdrops() {
  for (const k in BACKDROPS) {
    const im = new Image(), el = document.querySelector(`#backdrop .bd-${k}`);
    im.onload = () => { el.style.backgroundImage = `url("${BACKDROPS[k]}")`; el.classList.add("loaded"); };
    im.onerror = () => el.classList.add("failed");
    im.src = BACKDROPS[k];
  }
}

function render() {
  $("coinTop").textContent = fmt(S.coins);
  if (current === "titleScreen") renderTitle();
  if (current === "home") {
    $("homeName").textContent = S.mythical ? `🏆 ${S.name} – Lake Legend` : S.name;
    $("hCoins").textContent = fmt(S.coins); $("hCaught").textContent = fmt(S.totalCaught);
    $("hColl").textContent = `${totalDisc()} / 40`; $("hBag").textContent = `${S.bag.length} / ${S.bagMax}`;
    $("hBag").style.color = bagFull() ? "#ffb4a2" : ""; $("hRod").textContent = rod().short; $("hMastery").textContent = `${masteredCount()} / 4`;
  }
  if (current === "map") renderMap();
  if (current === "fishing") renderFishingHud();
  if (current === "bag") renderBag();
  if (current === "result") renderResult();
  if (current === "shop") renderShop();
  if (current === "tackle") renderTackle();
  if (current === "collection") renderCollection();
}

/* ===================== TITLE ===================== */
function renderTitle() {
  $("contBtn").disabled = !hasSave();
  $("soundBtn").textContent = S.sound ? "🔊 SOUND: ON" : "🔇 SOUND: OFF";
  $("soundBtn").setAttribute("aria-pressed", S.sound);
  $("musicBtn").textContent = S.music ? "🎵 MUSIC: ON" : "🔇 MUSIC: OFF";
  $("musicBtn").setAttribute("aria-pressed", S.music);
}
let modalReturn = null;
function openModal(id, focusId) {
  modalReturn = document.activeElement; $(id).classList.add("show"); $(focusId).focus();
}
function closeModal(id) {
  $(id).classList.remove("show"); if (modalReturn && document.contains(modalReturn)) modalReturn.focus(); modalReturn = null;
}
function openNameBox() { $("nameInput").value = ""; $("nameErr").textContent = ""; openModal("nameBox", "nameInput"); }
function startNewGame(name) {
  const sound = S.sound, music = S.music, fightStyle = S.fightStyle;            // keep the player's sound, music and fight style choices
  S = DEFAULT(); S.name = name; S.sound = sound; S.music = music; S.fightStyle = fightStyle; save();
  island = "harbor"; collTab = "harbor";
  go("home"); toast(`Welcome to Little Lake, ${name}!`);
}
$("newBtn").onclick = () => hasSave() ? openModal("confirmBox", "confirmNo") : openNameBox();
$("confirmNo").onclick = () => closeModal("confirmBox");
$("confirmYes").onclick = () => { $("confirmBox").classList.remove("show"); openNameBox(); };
$("nameCancel").onclick = () => closeModal("nameBox");
$("nameForm").onsubmit = e => {
  e.preventDefault();
  const name = $("nameInput").value.trim();
  if (!name) { $("nameErr").textContent = "Please enter a name."; $("nameInput").focus(); return; }
  if (name.length > 12) { $("nameErr").textContent = "Names can be at most 12 characters."; $("nameInput").focus(); return; }
  $("nameBox").classList.remove("show"); modalReturn = null; startNewGame(name);
};
$("contBtn").onclick = () => { if (!hasSave()) return; S = load(); go("home"); };
function renderFightBtn() { const b = $("fightBtn"); b.textContent = "FIGHT: " + (S.fightStyle === "tap" ? "TAP" : "HOLD"); b.setAttribute("aria-pressed", String(S.fightStyle !== "tap")); }
$("fightBtn").onclick = () => { S.fightStyle = S.fightStyle === "tap" ? "hold" : "tap"; saveSound(); renderFightBtn(); };   // the reel minigame style (Playtest 2, part 3); only reachable from the Title screen, never mid-fight
$("howBtn").onclick = () => { renderFightBtn(); openModal("howBox", "howPanel"); };
$("howOk").onclick = () => closeModal("howBox");
$("soundBtn").onclick = () => { S.sound = !S.sound; saveSound(); audioApply(); renderTitle(); sfx.tick(); };   // the click confirms (only when Sound is on)
$("musicBtn").onclick = () => { S.music = !S.music; saveSound(); audioApply(); musicSync(); renderTitle(); sfx.tick(); };
// Esc closes an open popup and does nothing else; with no popup open it works as BACK on the screens with the
// BACK bar (so never on Home, where BACK would leave the game for the Title screen)
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (document.querySelector(".banner.show")) {
    ["confirmBox", "nameBox", "howBox", "pickBox"].forEach(id => $(id).classList.contains("show") && closeModal(id));
    return;
  }
  if (NAV_SCREENS[current]) goBack();
});
// keep Tab inside an open dialog (wraps from the last button to the first and back)
document.addEventListener("keydown", e => {
  const m = e.key === "Tab" && document.querySelector(".banner.modal.show"); if (!m) return;
  const f = [...m.querySelectorAll("button:not(:disabled), input")].filter(x => x.offsetParent); if (!f.length) return;
  const i = f.indexOf(document.activeElement);
  if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
  else if (!e.shiftKey && (i === -1 || i === f.length - 1)) { e.preventDefault(); f[0].focus(); }
});

/* ===================== MAP ===================== */
// 4 island cards: picture, name (+ gold star when mastered), progress bar "x / 10" and the Mastery reward;
// the secret island is a separate wide strip below them (locked: padlock + "???")
function renderMap() {
  const box = $("islands"); box.innerHTML = "";
  ISLAND_IDS.forEach(id => {
    const I = ISLANDS[id], n = discCount(id), done = !!S.mastery[id], b = document.createElement("button");
    b.className = `island ${I.bg}` + (done ? " mastered" : "");
    b.setAttribute("aria-label", `${I.name}: ${n} of 10 fish found${done ? ", mastered" : ""}. Go fishing here.`);
    b.innerHTML = `<span class="isl-plate"><span class="isl-name">${I.name}${done ? `<span class="ico i-star" title="Mastered"></span>` : ""}</span>` +
      `<span class="isl-prog"><span class="isl-bar"><span style="width:${n * 10}%"></span></span><span class="isl-count">${n} / 10</span></span>` +
      `<small class="isl-reward"><span class="ico i-${done ? I.icon : "lock"}"></span>${I.reward}</small></span>`;
    b.onclick = () => { island = id; go("fishing"); };
    box.append(b);
  });
  const locked = !secretOpen(), n = discCount("secret"), s = document.createElement("button");
  s.className = "island secret-strip bg-secret" + (locked ? " locked" : "") + (n ? " mastered" : "");
  s.innerHTML = locked
    ? `<span class="ico i-lock"></span><span class="isl-name">???</span><small>Master all 4 islands to unlock</small><span class="isl-count">${masteredCount()} / 4 mastered</span>`
    : `<span class="ico ${n ? "i-star" : "i-fish"}"></span><span class="isl-name">Little Lake</span><small>Secret island · Mythical fish</small><span class="isl-count">${n} / 1 found</span>`;
  s.setAttribute("aria-label", locked ? "Secret island, locked: master all 4 islands to unlock" : "Little Lake, the secret island. Go fishing here.");
  s.onclick = () => { if (locked) { toast("Master all four islands first."); return; } island = "secret"; go("fishing"); };
  box.append(s);
}

/* ===================== BAG ===================== */
function renderBag() {
  $("bagCount").textContent = `${S.bag.length} / ${S.bagMax}`;
  const L = $("bagList"); L.innerHTML = "";
  if (!S.bag.length) { L.innerHTML = `<div class="row">Your bag is empty. Go fishing!</div>`; }
  S.bag.forEach((b, i) => {
    const f = fishById(b.fishId), row = document.createElement("div"); row.className = "row";
    const c = document.createElement("canvas"); drawFish(c, f);
    row.append(c);
    row.insertAdjacentHTML("beforeend", `<div class="grow"><b>${f.name}</b><br><span class="rar-${f.rarity}">${f.rarity}</span> · ${b.weight} kg</div>`);
    const lk = document.createElement("button"); lk.className = "lockbtn"; lk.type = "button"; lk.dataset.nosound = "";
    lk.setAttribute("aria-label", b.locked ? "Unlock fish" : "Lock fish"); lk.setAttribute("aria-pressed", b.locked ? "true" : "false");
    lk.innerHTML = `<span class="ico ${b.locked ? "i-padlock" : "i-padlock-open"}"></span>`;
    lk.onclick = () => { b.locked = !b.locked; save(); sfx.tick(); renderBag(); };
    row.append(lk); row.classList.toggle("locked", !!b.locked);
    const s = document.createElement("button"); s.className = "btn green"; s.dataset.nosound = ""; s.textContent = `SELL ${fmt(b.price)}`;
    if (b.locked) { s.classList.add("is-locked"); }
    s.onclick = () => sell([i]); row.append(s); L.append(row);
  });
  const ut = unlockedTotal();
  $("sellAll").innerHTML = `<span class="ico i-coin"></span>SELL ALL${ut ? ` <span class="amt">${fmt(ut)}</span>` : ""}`;   // value of the unlocked fish only
  $("sellAll").disabled = !S.bag.length;
  bagFade();
}
// the Bag list's bottom fade shows only while more fish are hidden below
function bagFade() { const l = $("bagList"); l.classList.toggle("has-more", l.scrollHeight > l.clientHeight + 4); }
window.addEventListener("resize", () => { if (current === "bag") bagFade(); });
function sell(idx) {
  if (idx.some(i => S.bag[i].locked)) { toast("Unlock it first"); return; }
  let total = 0; idx.sort((a, b) => b - a).forEach(i => { total += S.bag[i].price; S.bag.splice(i, 1); });
  S.coins += total; save(); sfx.coin(); toast(`Sold for ${fmt(total)} coins!`); render();
}
$("sellAll").onclick = () => { const u = unlockedIdx(); if (!u.length) { if (S.bag.length) toast("All your fish are locked"); return; } sell(u); };

/* ===================== SHOP ===================== */
// every item says exactly what it does, whether you own / use it, and why it can't be bought
function shopItem({ buy, icon, name, tag, fx, odds, note, label, can }) {
  return `<div class="item${tag === "EQUIPPED" ? " equipped" : ""}"><b>${icon.startsWith("fl:") ? floatIcon(icon.slice(3)) : `<span class="ico i-${icon}"></span>`}${name}</b>` +
    (tag ? `<span class="tag">${tag}</span>` : "") + `<span class="fx">${fx}</span>` + (odds ? `<span class="odds">${odds}</span>` : "") +
    (note || "") + `<button class="btn green" data-nosound data-buy="${buy}"${can ? "" : " disabled"}>${label}</button></div>`;
}
const needMore = price => S.coins < price ? `<span class="need">Need ${fmt(price - S.coins)} more coins</span>` : "";
function renderShop() {
  $("shopRods").innerHTML = ROD_IDS.map(id => {
    const r = RODS[id], own = S.rods.includes(id), eq = S.rodEq === id;
    return shopItem({ buy: `rod:${id}`, icon: `rodlg-${id}`, name: r.name, tag: eq ? "EQUIPPED" : own ? "OWNED" : "",
      fx: rodFx(id), odds: r.luck ? `Odds without bait: ${oddsText(rarityWeights("none", id))}` : "",
      note: own ? "" : needMore(r.price), can: !own && S.coins >= r.price,
      label: own ? (eq ? "EQUIPPED" : "OWNED") : r.price ? `${r.price} COINS` : "FREE" });
  }).join("");
  $("shopBaits").innerHTML = BAIT_IDS.map(id => {
    const b = BAITS[id];
    return shopItem({ buy: `bait:${id}`, icon: `bait-${id}`, name: `${b.name} x${b.pack}`, tag: S.baitSel === id ? "EQUIPPED" : "",
      fx: `${b.blurb} You have: ${S.baits[id]}.`, odds: `With your ${rod().short} rod: ${oddsText(rarityWeights(id))}`,
      note: needMore(b.price), can: S.coins >= b.price, label: `${b.price} COINS` });
  }).join("");
  $("shopFloats").innerHTML = FLOAT_IDS.map(id => {
    const f = FLOATS[id], own = S.floatsOwned.includes(id), eq = S.floatEq === id;
    return shopItem({ buy: `float:${id}`, icon: `fl:${id}`, name: f.name, tag: eq ? "EQUIPPED" : own ? "OWNED" : "", fx: f.blurb + " Only a look.",
      note: own ? "" : needMore(f.price), can: !own && S.coins >= f.price, label: own ? (eq ? "EQUIPPED" : "OWNED") : f.price ? `${f.price} COINS` : "FREE" });
  }).join("");
  $("shopNoBait").textContent = `Without bait (${rod().short} rod): ${oddsText(rarityWeights("none"))}`;
  $("sBagFx").textContent = `Bag: ${S.bagMax + 5} slots (now ${S.bagMax})`;
  $("sBag").textContent = `${S.bag.length} / ${S.bagMax}`;
  $("buyBag").disabled = S.coins < 150;
}
function buy(cost, fn, msg) { if (S.coins < cost) { toast("Not enough coins."); return; } S.coins -= cost; fn(); save(); sfx.coin(); toast(msg); render(); }
function buyRod(id) {
  const r = RODS[id]; if (!r || S.rods.includes(id)) return toast("You already own this rod.");
  buy(r.price, () => S.rods.push(id), `Bought the ${r.name}! Equip it in your Tackle Box.`);
}
function buyFloat(id) {
  const f = FLOATS[id]; if (!f || S.floatsOwned.includes(id)) return toast("You already own this float.");
  buy(f.price, () => { S.floatsOwned.push(id); S.floatEq = id; }, `Bought: ${f.name}`);        // a new float is equipped at once
}
function buyBait(id) {
  const b = BAITS[id], auto = S.baitSel === "none";        // with no bait selected, the new bait is selected
  buy(b.price, () => { S.baits[id] += b.pack; if (auto) S.baitSel = id; }, `Bought ${b.pack} ${b.name}.` + (auto ? ` ${b.name} is now your bait.` : ""));
}
document.querySelector("#shop .panel").addEventListener("click", e => {
  const btn = e.target.closest("[data-buy]"); if (!btn || btn.disabled) return;
  const [kind, id] = btn.dataset.buy.split(":"); kind === "rod" ? buyRod(id) : kind === "float" ? buyFloat(id) : buyBait(id);
});
$("buyBag").onclick = () => buy(150, () => S.bagMax += 5, "Bag expanded by 5 slots.");

/* ===================== TACKLE BOX ===================== */
// all gear in one place: equip a rod, select a bait, see bag and island rewards; every row has an icon and its effect
function renderTackle() {
  const row = (icon, name, fx, right, cls = "") => `<div class="gear-row ${cls}">${icon.startsWith("fl:") ? floatIcon(icon.slice(3)) : `<span class="ico i-${icon}"></span>`}` +
    `<div class="grow"><b>${name}</b><div class="fx">${fx}</div></div>${right}</div>`;
  const chip = t => `<span class="chip">${t}</span>`, charm = S.mastery.forest ? " +1 miss from Master's Charm." : "";
  const rods = ROD_IDS.map(id => {
    const r = RODS[id], own = S.rods.includes(id), eq = S.rodEq === id;
    return row(`rodlg-${id}`, r.name, rodFx(id) + (own ? charm : ""),
      eq ? chip("EQUIPPED") : own ? `<button class="btn small green" data-nosound data-equip="${id}">EQUIP</button>` : chip(`SHOP · ${r.price} COINS`),
      eq ? "active" : own ? "" : "notowned");
  }).join("");
  const baits = ["none", ...BAIT_IDS].map(id => {
    const b = BAITS[id], n = b ? S.baits[id] : 0, sel = S.baitSel === id;
    return row(`bait-${id}`, b ? `${b.name} x${n}` : "No bait", (b ? b.blurb + " " : "Saves your bait. ") + oddsText(rarityWeights(id)) + ".",
      sel ? chip("EQUIPPED") : (!b || n) ? `<button class="btn small green" data-nosound data-bait="${id}">USE</button>` : chip("BUY IN SHOP"),
      sel ? "active" : (!b || n) ? "" : "notowned");
  }).join("");
  const floats = FLOAT_IDS.map(id => {
    const f = FLOATS[id], own = S.floatsOwned.includes(id), eq = S.floatEq === id;
    return row(`fl:${id}`, f.name, f.blurb + " Only a look.",
      eq ? chip("EQUIPPED") : own ? `<button class="btn small green" data-nosound data-float="${id}">EQUIP</button>` : `<button class="btn small" data-go="shop" title="Buy it in the Shop">SHOP · ${f.price} COINS</button>`,
      eq ? "active" : own ? "" : "notowned");
  }).join("");
  $("gearList").innerHTML =
    `<h3>Rod <small>${misses(allowedMiss())} allowed in total with your ${rod().name}</small></h3>` + rods +
    `<h3>Bait <small>one per cast from the bait you choose</small></h3>` + baits +
    `<h3>Float <small>how your bobber looks: no effect on fishing</small></h3>` + floats +
    `<h3>Bag</h3>` + row("bag", `Bag ${S.bag.length} / ${S.bagMax}`, `Holds up to ${S.bagMax} fish. Sell them in the Bag for coins.`, chip("BAG")) +
    `<h3>Island rewards <small>always on once unlocked, on top of your rod – nothing to equip</small></h3>` +
    ISLAND_IDS.map(i => { const I = ISLANDS[i], on = !!S.mastery[i];
      return row(on ? I.icon : "lock", I.reward, I.effect + ".", chip(on ? "UNLOCKED" : `LOCKED · ${discCount(i)} / 10 ${I.name} fish`), on ? "active" : "locked"); }).join("");
}
$("gearList").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.equip) equipRod(b.dataset.equip); else if (b.dataset.bait) selectBait(b.dataset.bait); else if (b.dataset.float) equipFloat(b.dataset.float);
});

/* ===================== COLLECTION ===================== */
let collTab = "harbor";
function renderCollection() {
  $("collTotal").textContent = `${totalDisc()} / 40`;
  const tabs = $("tabs"); tabs.innerHTML = "";
  [...ISLAND_IDS, ...(secretOpen() ? ["secret"] : [])].forEach(id => {
    const t = document.createElement("button"); t.className = "tab" + (id === collTab ? " on" : "");
    t.textContent = ISLANDS[id].name + (S.mastery[id] ? " ★" : ""); t.onclick = () => { collTab = id; renderCollection(); }; tabs.append(t);
  });
  const total = collTab === "secret" ? 1 : 10, n = discCount(collTab), I = ISLANDS[collTab];
  $("collHead").innerHTML = `<div>${I.name}: ${n} / ${total} found</div><div class="bar"><div style="width:${n / total * 100}%"></div></div>` +
    (collTab !== "secret" ? `<div class="reward">${S.mastery[collTab] ? "★ UNLOCKED" : "Reward"}: <b>${I.reward}</b> – ${I.effect}</div>` : "");
  const G = $("collGrid"); G.innerHTML = "";
  FISH.filter(f => f.island === collTab).forEach(f => {
    const d = document.createElement("div"), known = S.discovered[f.id];
    d.className = `cell r-${f.rarity}` + (known ? "" : " unknown");   // border colour by rarity
    const c = document.createElement("canvas"); known ? drawFish(c, f) : silhouette(c, f); d.append(c);
    d.insertAdjacentHTML("beforeend", known ? `<div><b>${f.name}</b></div><div class="rar-${f.rarity}">${f.rarity}</div><div>Best: ${S.records[f.id] || "-"} kg</div>` : `<div><b>Not found yet</b></div><div>${f.rarity}</div>`);
    G.append(d);
  });
}

/* ===================== DEMO MODE ===================== */
let taps = 0, tapT;
$("title").onclick = () => { taps++; clearTimeout(tapT); tapT = setTimeout(() => taps = 0, 1500); if (taps >= 5) { taps = 0; $("demo").classList.toggle("show"); go("home"); toast("Demo mode toggled"); } };
function completeIsland(isl) { FISH.filter(f => f.island === isl).forEach(f => { S.discovered[f.id] = true; S.records[f.id] = S.records[f.id] || f.max; }); }
$("dCoins").onclick = () => { S.coins += 1000; save(); render(); toast("+1000 coins"); };
$("dHarbor").onclick = () => { completeIsland("harbor"); save(); render(); checkMastery(); };
$("dAll").onclick = () => { ISLAND_IDS.forEach(completeIsland); ISLAND_IDS.slice(0, 3).forEach(i => S.mastery[i] = true); save(); render(); checkMastery(); };
$("dFill").onclick = () => { while (!bagFull()) { const f = FISH[Math.floor(Math.random() * 40)]; S.bag.push({ fishId: f.id, weight: f.min, price: f.price, time: Date.now() }); } save(); render(); toast("Bag filled"); };
$("dReset").onclick = () => { localStorage.removeItem(SAVE_KEY); S = load(); render(); toast("Save reset"); };

render();
setTimeout(() => { preloadScenes(); preloadBackdrops(); }, 0);   // island pictures and backdrops load after the Title screen is up
