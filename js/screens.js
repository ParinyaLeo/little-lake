// Screen navigation and the Title, Home, Map, Bag, Shop, Tackle Box, Collection and Demo screens. Loaded last; starts the game.
/* ===================== NAVIGATION ===================== */
let current = "titleScreen", prevScreen = "home";
function go(id) {
  // a caught fish is waiting for KEEP / RELEASE: only the Result screen (and the Bag, to make room) can be opened
  if (S.pending && !["result", "bag", "titleScreen"].includes(id)) {
    if (current === "result") return;
    id = "result"; setTimeout(() => toast(`Your ${fishById(S.pending.fishId).name} is waiting: keep it or release it.`), 50);
  }
  if (current === "fishing" && id !== "fishing") stopFishing();
  if (id === "bag") prevScreen = current;
  document.querySelectorAll(".screen").forEach(s => s.classList.toggle("active", s.id === id));
  current = id; document.body.classList.toggle("plain", id === "fishing"); document.body.classList.toggle("on-title", id === "titleScreen");
  document.body.classList.toggle("on-home", id === "home");
  render(); window.scrollTo(0, 0);
}
document.addEventListener("click", e => { const b = e.target.closest("[data-go]"); if (b) go(b.dataset.go); });

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
  const sound = S.sound;                              // keep the player's sound choice
  S = DEFAULT(); S.name = name; S.sound = sound; save();
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
$("howBtn").onclick = () => openModal("howBox", "howPanel");
$("howOk").onclick = () => closeModal("howBox");
$("soundBtn").onclick = () => { S.sound = !S.sound; saveSound(); renderTitle(); sfx.coin(); };
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  ["confirmBox", "nameBox", "howBox"].forEach(id => $(id).classList.contains("show") && closeModal(id));
});

/* ===================== MAP ===================== */
function renderMap() {
  const box = $("islands"); box.innerHTML = "";
  [...ISLAND_IDS, "secret"].forEach(id => {
    const I = ISLANDS[id], locked = id === "secret" && !secretOpen();
    const b = document.createElement("button");
    b.className = `island ${I.bg}` + (locked ? " locked" : "");
    b.innerHTML = locked ? `???<small>Master all 4 islands</small>` :
      `${I.name}${S.mastery[id] ? " ★" : ""}<small>${id === "secret" ? "Mythical fish" : discCount(id) + " / 10 found"}</small>`;
    b.onclick = () => { if (locked) { toast("Master all four islands first."); return; } island = id; go("fishing"); };
    box.append(b);
  });
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
    const s = document.createElement("button"); s.className = "btn green"; s.textContent = `SELL ${fmt(b.price)}`;
    s.onclick = () => sell([i]); row.append(s); L.append(row);
  });
  $("sellAll").disabled = !S.bag.length;
}
function sell(idx) {
  let total = 0; idx.sort((a, b) => b - a).forEach(i => { total += S.bag[i].price; S.bag.splice(i, 1); });
  S.coins += total; save(); sfx.coin(); toast(`Sold for ${fmt(total)} coins!`); render();
}
$("sellAll").onclick = () => sell(S.bag.map((_, i) => i));
$("bagBack").onclick = () => go(prevScreen === "bag" ? "home" : prevScreen);

/* ===================== SHOP ===================== */
// every item says exactly what it does, whether you own / use it, and why it can't be bought
function shopItem({ buy, icon, name, tag, fx, odds, note, label, can }) {
  return `<div class="item${tag === "EQUIPPED" ? " equipped" : ""}"><b><span class="ico i-${icon}"></span>${name}</b>` +
    (tag ? `<span class="tag">${tag}</span>` : "") + `<span class="fx">${fx}</span>` + (odds ? `<span class="odds">${odds}</span>` : "") +
    (note || "") + `<button class="btn green" data-buy="${buy}"${can ? "" : " disabled"}>${label}</button></div>`;
}
const needMore = price => S.coins < price ? `<span class="need">Need ${fmt(price - S.coins)} more coins</span>` : "";
function renderShop() {
  $("shopRods").innerHTML = ROD_IDS.map(id => {
    const r = RODS[id], own = S.rods.includes(id), eq = S.rodEq === id;
    return shopItem({ buy: `rod:${id}`, icon: `rod-${id}`, name: r.name, tag: eq ? "EQUIPPED" : own ? "OWNED" : "",
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
function buyBait(id) {
  const b = BAITS[id], auto = S.baitSel === "none";        // with no bait selected, the new bait is selected
  buy(b.price, () => { S.baits[id] += b.pack; if (auto) S.baitSel = id; }, `Bought ${b.pack} ${b.name}.` + (auto ? ` ${b.name} is now your bait.` : ""));
}
document.querySelector("#shop .panel").addEventListener("click", e => {
  const btn = e.target.closest("[data-buy]"); if (!btn || btn.disabled) return;
  const [kind, id] = btn.dataset.buy.split(":"); kind === "rod" ? buyRod(id) : buyBait(id);
});
$("buyBag").onclick = () => buy(150, () => S.bagMax += 5, "Bag expanded by 5 slots.");

/* ===================== TACKLE BOX ===================== */
// all gear in one place: equip a rod, select a bait, see bag and island rewards; every row has an icon and its effect
function renderTackle() {
  const row = (icon, name, fx, right, cls = "") => `<div class="gear-row ${cls}"><span class="ico i-${icon}"></span>` +
    `<div class="grow"><b>${name}</b><div class="fx">${fx}</div></div>${right}</div>`;
  const chip = t => `<span class="chip">${t}</span>`, charm = S.mastery.forest ? " +1 miss from Master's Charm." : "";
  const rods = ROD_IDS.map(id => {
    const r = RODS[id], own = S.rods.includes(id), eq = S.rodEq === id;
    return row(`rod-${id}`, r.name, rodFx(id) + (own ? charm : ""),
      eq ? chip("EQUIPPED") : own ? `<button class="btn small green" data-equip="${id}">EQUIP</button>` : chip(`SHOP · ${r.price} COINS`),
      eq ? "active" : own ? "" : "notowned");
  }).join("");
  const baits = ["none", ...BAIT_IDS].map(id => {
    const b = BAITS[id], n = b ? S.baits[id] : 0, sel = S.baitSel === id;
    return row(`bait-${id}`, b ? `${b.name} x${n}` : "No bait", (b ? b.blurb + " " : "Saves your bait. ") + oddsText(rarityWeights(id)) + ".",
      sel ? chip("EQUIPPED") : (!b || n) ? `<button class="btn small green" data-bait="${id}">USE</button>` : chip("BUY IN SHOP"),
      sel ? "active" : (!b || n) ? "" : "notowned");
  }).join("");
  $("gearList").innerHTML =
    `<h3>Rod <small>${misses(allowedMiss())} allowed in total with your ${rod().name}</small></h3>` + rods +
    `<h3>Bait <small>one per cast from the bait you choose</small></h3>` + baits +
    `<h3>Bag</h3>` + row("bag", `Bag ${S.bag.length} / ${S.bagMax}`, `Holds up to ${S.bagMax} fish. Sell them in the Bag for coins.`, chip("BAG")) +
    `<h3>Island rewards <small>always on once unlocked, on top of your rod – nothing to equip</small></h3>` +
    ISLAND_IDS.map(i => { const I = ISLANDS[i], on = !!S.mastery[i];
      return row(on ? I.icon : "lock", I.reward, I.effect + ".", chip(on ? "UNLOCKED" : `LOCKED · ${discCount(i)} / 10 ${I.name} fish`), on ? "active" : "locked"); }).join("");
}
$("gearList").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.equip) equipRod(b.dataset.equip); else if (b.dataset.bait) selectBait(b.dataset.bait);
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
