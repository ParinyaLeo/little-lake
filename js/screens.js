// Screen navigation and the Title, Home, Map, Bag, Shop, Collection and Demo screens. Loaded last; starts the game.
/* ===================== NAVIGATION ===================== */
let current = "titleScreen", prevScreen = "home";
function go(id) {
  if (current === "fishing" && id !== "fishing") stopFishing();
  if (id === "bag") prevScreen = current;
  document.querySelectorAll(".screen").forEach(s => s.classList.toggle("active", s.id === id));
  current = id; document.body.classList.toggle("plain", id === "fishing"); document.body.classList.toggle("on-title", id === "titleScreen");
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
    $("hBag").style.color = bagFull() ? "#ffb4a2" : ""; $("hRod").textContent = S.rod; $("hMastery").textContent = `${masteredCount()} / 4`;
  }
  if (current === "map") renderMap();
  if (current === "fishing") renderFishingHud();
  if (current === "bag") renderBag();
  if (current === "shop") renderShop();
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
  lastCatch = null; island = "harbor"; collTab = "harbor";
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
function renderShop() {
  $("sRod").textContent = S.rod; $("sBait").textContent = S.bait; $("sBag").textContent = S.bagMax;
  $("buyRod").disabled = S.coins < 200; $("buyBait").disabled = S.coins < 100; $("buyBag").disabled = S.coins < 150;
}
function buy(cost, fn, msg) { if (S.coins < cost) { toast("Not enough coins."); return; } S.coins -= cost; fn(); save(); sfx.coin(); toast(msg); render(); }
$("buyRod").onclick = () => buy(200, () => S.rod++, "Rod upgraded!");
$("buyBait").onclick = () => buy(100, () => S.bait += 5, "Bought 5 bait.");
$("buyBag").onclick = () => buy(150, () => S.bagMax += 5, "Bag expanded by 5 slots.");

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
    d.className = "cell" + (known ? "" : " unknown");
    const c = document.createElement("canvas"); known ? drawFish(c, f) : silhouette(c); d.append(c);
    d.insertAdjacentHTML("beforeend", known ? `<div><b>${f.name}</b></div><div class="rar-${f.rarity}">${f.rarity}</div><div>Best: ${S.records[f.id] || "-"} kg</div>` : `<div><b>?</b></div><div>${f.rarity}</div>`);
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
