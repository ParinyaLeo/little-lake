// Screen navigation and the Title, Home, Map, Bag, Shop, Tackle Box, Collection and Demo screens. Loaded last; starts the game.
/* ===================== NAVIGATION =====================
   navStack = the screens behind the current one, so BACK (sticky bar, the Bag's BACK button and Esc) returns to
   where the player came from, like a browser's back button. Home and Title start a fresh history. A Result screen
   is only remembered on the way to the Bag (to make room for the waiting fish), and the same screen is never stored
   twice in a row, so catching fish over and over doesn't grow the history. */
// screens with the BACK bar (Home is the root screen: no BACK bar, it has its MENU button)
const NAV_SCREENS = { map: "TOWN MAP", bag: "BAG", shop: "SHOP", collection: "COLLECTION", tackle: "TACKLE BOX", aquarium: "AQUARIUM" };
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
const FIT_SCREENS = ["bag", "shop", "tackle", "aquarium"];
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
  if (current === "aquarium") { renderAquarium(); tankStart(); } else tankStop();      // the tank loop runs only while this screen is open
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
  shopFilter = "all"; S = DEFAULT(); S.name = name; S.sound = sound; S.music = music; S.fightStyle = fightStyle; save();
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
function shopItem({ buy, icon, name, tag, fx, odds, note, label, can, kind }) {
  return `<div class="item${tag === "EQUIPPED" ? " equipped" : ""}">` + (kind ? `<span class="kind">${kind}</span>` : "") + `<b>${icon.startsWith("fl:") ? floatIcon(icon.slice(3)) : icon.startsWith("tk:") ? `<img class="tkthumb" alt="" src="${tankThumb(...icon.slice(3).split(":"))}">` : `<span class="ico i-${icon}"></span>`}${name}</b>` +
    (tag ? `<span class="tag">${tag}</span>` : "") + `<span class="fx">${fx}</span>` + (odds ? `<span class="odds">${odds}</span>` : "") +
    (note || "") + `<button class="btn green" data-nosound data-buy="${buy}"${can ? "" : " disabled"}>${label}</button></div>`;
}
const tankName = (kind, id) => kind === "theme" ? TANK_THEMES[id].name + " Theme" : TANK_DECOS[id].name;     // one wording for the Shop and the Aquarium lists
const needMore = price => S.coins < price ? `<span class="need">Need ${fmt(price - S.coins)} more coins</span>` : "";
let shopFilter = "all";                                   // ALL | RODS | BAIT | FLOATS | THEMES | DECOR: a plain variable (not saved), so a reload or NEW GAME goes back to ALL
function applyShopFilter(toTop) {                         // only hides / shows the sections with a class; nothing is rebuilt
  document.querySelectorAll("#shop .shop-sec").forEach(e => e.classList.toggle("sec-off", shopFilter !== "all" && e.dataset.sec !== shopFilter));
  document.querySelectorAll("#shopFilter .tab").forEach(b => { const on = b.dataset.filter === shopFilter; b.classList.toggle("on", on); b.setAttribute("aria-pressed", on ? "true" : "false"); });
  if (toTop) $("shopScroll").scrollTop = 0;
}
document.querySelectorAll("#shopFilter .tab").forEach(b => b.onclick = () => { shopFilter = b.dataset.filter; applyShopFilter(true); });
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
  $("shopThemes").innerHTML = TANK_THEME_IDS.map(id => {         // Playtest 2, part 9b: Tank Themes and Tank Decorations are two separate sections (a look only)
    const t = TANK_THEMES[id], own = S.tankThemes.includes(id), use = S.tankTheme === id;
    return shopItem({ buy: `theme:${id}`, icon: `tk:theme:${id}`, name: tankName("theme", id), tag: use ? "EQUIPPED" : own ? "OWNED" : "", fx: t.blurb + " Only a look.",
      note: own ? "" : needMore(t.price), can: !own && S.coins >= t.price, label: own ? (use ? "IN USE" : "OWNED") : t.price ? `${t.price} COINS` : "FREE" });
  }).join("");
  $("shopDecos").innerHTML = TANK_DECO_IDS.map(id => {
    const d = TANK_DECOS[id], own = S.tankDecos.includes(id), on = S.tankDecoOn.includes(id);
    return shopItem({ buy: `deco:${id}`, icon: `tk:deco:${id}`, name: tankName("deco", id), kind: "DECOR", tag: on ? "EQUIPPED" : own ? "OWNED" : "", fx: d.blurb + " Only a look.",
      note: own ? "" : needMore(d.price), can: !own && S.coins >= d.price, label: own ? (on ? "SHOWN" : "OWNED") : `${d.price} COINS` });
  }).join("");
  applyShopFilter(false);
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
function buyTheme(id) {
  const t = TANK_THEMES[id]; if (!t || S.tankThemes.includes(id)) return toast("You already own this theme.");
  buy(t.price, () => { S.tankThemes.push(id); S.tankTheme = id; }, `Bought: ${t.name} (now in your Aquarium)`);        // like a float, a new theme is used at once
}
function buyDeco(id) {
  const d = TANK_DECOS[id]; if (!d || S.tankDecos.includes(id)) return toast("You already own this decoration.");
  buy(d.price, () => { S.tankDecos.push(id); if (S.tankDecoOn.length < TANK_DECO_MAX) S.tankDecoOn.push(id); }, `Bought: ${d.name}`);   // shown at once when there is room
}
function buyBait(id) {
  const b = BAITS[id], auto = S.baitSel === "none";        // with no bait selected, the new bait is selected
  buy(b.price, () => { S.baits[id] += b.pack; if (auto) S.baitSel = id; }, `Bought ${b.pack} ${b.name}.` + (auto ? ` ${b.name} is now your bait.` : ""));
}
document.querySelector("#shop .panel").addEventListener("click", e => {
  const btn = e.target.closest("[data-buy]"); if (!btn || btn.disabled) return;
  const [kind, id] = btn.dataset.buy.split(":"); kind === "rod" ? buyRod(id) : kind === "float" ? buyFloat(id) : kind === "theme" ? buyTheme(id) : kind === "deco" ? buyDeco(id) : buyBait(id);
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

/* ===================== AQUARIUM (Playtest 2, part 8) =====================
   S.tank = up to TANK_SIZE caught fish (the same entries as the bag; a fish MOVES between bag and tank, a locked fish keeps its lock). Cosmetic only: SELL / SELL ALL never touch the tank,
   it gives no money. drawTank() paints the whole tank (water, light rays, plants, rocks, sand, bubbles, the swimming fish) on a small canvas (1 tank pixel = TANK_SCALE screen pixels);
   the requestAnimationFrame loop runs only while this screen is open (render() starts it, any other screen stops it). */
const TANK_SCALE = 2;
const TK = { on: false, raf: 0, last: 0, sim: [], tip: null, grads: {} };   // grads: cached gradients, one per theme and height
function tankMake(b, i) {                            // one swimming fish: its own depth, speed, bob and size
  const f = fishById(b.fishId), r = seededRng(9100 + i * 37 + b.fishId.length * 7 + Math.round(b.weight * 100)), norm = Math.min(1, Math.max(0, (b.weight - f.min) / Math.max(.001, f.max - f.min)));
  return { b, f, spr: fishSprite(f), norm, u: r(), dir: r() < .5 ? -1 : 1, spd: 10 + r() * 16, depth: .1 + .62 * ((i * .61803 + r() * .25) % 1), ph: r() * 6.28, bobA: 1.5 + r() * 2.5, bobS: .0012 + r() * .0012, x: 0, y: 0, w: 24, h: 16 };
}
function tankSync() {                                // rebuild the swimmers when the set of tank fish changed (a fish that stays keeps its place)
  if (TK.sim.length === S.tank.length && TK.sim.every((s, i) => s.b === S.tank[i])) return;
  TK.sim = S.tank.map((b, i) => TK.sim.find(s => s.b === b) || tankMake(b, i));
}
// ---- the tank looks (Playtest 2, part 9). Every theme in TANK_ART has a water gradient, a sand palette and up to four layers (back = behind everything, floor = on the sand but behind the fish,
// front = in front of the fish, top = last, over everything); every decoration in TANK_DECO_ART draws itself standing on the floor. All canvas code, no images; the Shop thumbnails reuse
// drawTank / drawDeco. u = the drawing unit (a share of the tank height), sy = the y of the sand line.
const TANK_FLOOR = .86;
const TANK_DECO_SLOT = { chest: .1, anchor: .27, castle: .5, bigcoral: .74, bubbler: .92 };   // fixed places on the floor (centres, a share of the width), spread so the decorations never overlap
const tkR = (c, col, x, y, w, h) => { c.fillStyle = col; c.fillRect(Math.round(x), Math.round(y), Math.max(1, Math.round(w)), Math.max(1, Math.round(h))); };
const tkBub = (c, x, y, r) => c.strokeRect(Math.round(x) + .5, Math.round(y) + .5, r, r);
function tkRays(c, w, h, t, sy, a) {                // light rays from the surface, slowly swaying
  c.fillStyle = `rgba(255,255,255,${a})`;
  for (let i = 0; i < 4; i++) { const x = w * (.12 + i * .26) + Math.sin(t / 2600 + i * 1.7) * w * .03, rw = w * .07; c.beginPath(); c.moveTo(x, 0); c.lineTo(x + rw, 0); c.lineTo(x + rw * 2.2 + h * .25, sy); c.lineTo(x - rw * .6 + h * .25, sy); c.closePath(); c.fill(); }
}
function tkSand(c, w, h, sy, pal) {                 // sandy bottom with a few darker and lighter grains
  tkR(c, pal[0], 0, sy, w, h - sy); c.fillStyle = pal[1]; for (let x = 3; x < w; x += 11) c.fillRect(x, sy + 2 + (x * 7) % 5, 2, 2);
  c.fillStyle = pal[2]; for (let x = 8; x < w; x += 17) c.fillRect(x, sy + 1 + (x * 3) % 6, 2, 1);
}
function tkPlant(c, x, base, ht, t, ph, c1, c2, sway) {   // a swaying strand (kelp / seaweed)
  for (let j = 0; j < ht; j += 3) tkR(c, j % 6 ? c1 : c2, x + Math.sin(t / 700 + j * .09 + ph) * (j * sway), base - j, 3, 3);
}
function tkCoral(c, x, base, ht, c1, c2, t, ph) {   // a branching coral: a trunk with two pairs of side branches that sway a little
  const sw = j => Math.sin(t / 900 + ph + j * .05) * j * .03;
  for (let j = 0; j < ht; j += 2) tkR(c, c1, x + sw(j), base - j, 3, 2);
  for (const k of [.4, .68]) { const by = base - ht * k, bl = ht * (.34 - k * .12); for (let s = -1; s <= 1; s += 2) for (let j = 0; j < bl; j += 2) tkR(c, c1, x + s * (3 + j * .8) + sw(ht * k + j), by - j, 2, 2); }
  tkR(c, c2, x - 1 + sw(ht), base - ht - 2, 5, 3); for (const k of [.4, .68]) { const by = base - ht * k, bl = ht * (.34 - k * .12); tkR(c, c2, x - 4 - bl * .8 + sw(ht * k), by - bl, 3, 3); tkR(c, c2, x + 3 + bl * .8 + sw(ht * k), by - bl, 3, 3); }
}
function tkGlow(c, x, y, r, rgb, a) { c.fillStyle = `rgba(${rgb},${a})`; c.beginPath(); c.arc(x, y, r, 0, 6.2832); c.fill(); }

const TANK_ART = {
  pond: {
    water: ["#5fd0e8", "#1f8fbd", "#0b4a6e"], sand: ["#d9c07a", "#b99d5c", "#efdca0"], ray: .07,
    back(c, w, h, t, sy) { for (let i = 0; i < 5; i++) tkPlant(c, Math.round(w * (.07 + i * .22)), sy, Math.round(h * (.22 + (i % 3) * .08)), t, i * 2, "#2e9e52", "#3fbf68", .06); },
    front(c, w, h, t, sy) {
      for (let i = 0; i < 3; i++) { const rx = Math.round(w * (.16 + i * .34)), rw = Math.round(h * (.09 + (i % 2) * .05)), rh = Math.round(rw * .62); tkR(c, "#6f7d86", rx, sy - rh + 3, rw, rh); tkR(c, "#8c9aa3", rx + 2, sy - rh + 3, rw - 6, 2); tkR(c, "#515d65", rx, sy - 1, rw, 4); }
      for (let i = 0; i < 3; i++) tkPlant(c, Math.round(w * (.31 + i * .3)), sy + 3, Math.round(h * .16), t, i, "#237f42", "#2e9e52", .08);
    },
  },
  reef: {
    water: ["#8ff3e6", "#20bfcf", "#0a7a9c"], sand: ["#f4e4b0", "#d9c58a", "#fff3cc"], ray: .14,
    back(c, w, h, t, sy) {
      for (let i = 0; i < 2; i++) {                // sea fans: a purple fan on a stem
        const x = Math.round(w * (.2 + i * .45)), fh = Math.round(h * .3);
        for (let j = 0; j < fh; j += 2) { const half = Math.round(j * .55), sway = Math.sin(t / 1100 + i * 2 + j * .04) * j * .03; tkR(c, j % 6 ? "#b5409a" : "#d867b8", x - half + sway, sy - j, half * 2, 2); if (j > 6) { tkR(c, "#7a2a6c", x - half + sway, sy - j, 1, 2); tkR(c, "#7a2a6c", x + half + sway, sy - j, 1, 2); } }
        tkR(c, "#7a2a6c", x - 1, sy - 6, 3, 6);
      }
      tkCoral(c, Math.round(w * .07), sy, Math.round(h * .3), "#ff7a59", "#ffd166", t, 0); tkCoral(c, Math.round(w * .4), sy, Math.round(h * .22), "#ff5d8f", "#ffc2d9", t, 2); tkCoral(c, Math.round(w * .88), sy, Math.round(h * .34), "#ff9248", "#fff1a8", t, 4);
      for (let i = 0; i < 16; i++) { const tw = Math.sin(t / 380 + i * 2.3); if (tw > .75) { const x = Math.round(w * ((i * .173 + .07) % 1)), y = Math.round(sy * ((i * .291 + .05) % .8)); c.fillStyle = "rgba(255,255,255,.9)"; c.fillRect(x - 1, y, 3, 1); c.fillRect(x, y - 1, 1, 3); } }   // sparkling light
    },
    floor(c, w, h, t, sy) { for (let i = 0; i < 3; i++) { const x = Math.round(w * (.22 + i * .27)), r = Math.round(h * (.05 + (i % 2) * .02)); c.fillStyle = i % 2 ? "#e8a05a" : "#e0709a"; c.beginPath(); c.arc(x, sy + 1, r, Math.PI, 0); c.fill(); c.fillStyle = "rgba(255,255,255,.35)"; c.fillRect(x - r * .5, sy - r * .7, 2, 2); } },
    front(c, w, h, t, sy) { tkCoral(c, Math.round(w * .62), sy + 4, Math.round(h * .16), "#ff8fb1", "#ffe0ec", t, 6); },
  },
  deep: {
    water: ["#0d2a5c", "#081840", "#030a1e"], sand: ["#27324d", "#1a2238", "#3a4a6e"], ray: .035,
    back(c, w, h, t, sy) {
      for (let i = 0; i < 26; i++) {                // glowing specks drifting up
        const p = (t / 1000 * (.015 + (i % 3) * .01) + i * .137) % 1, x = w * ((i * .337) % 1) + Math.sin(t / 1500 + i) * 3, a = .25 + .5 * Math.max(0, Math.sin(t / 600 + i * 1.7));
        c.fillStyle = `rgba(120,230,255,${a.toFixed(2)})`; c.fillRect(Math.round(x), Math.round(sy * (1 - p)), 2, 2);
      }
      for (let i = 0; i < 3; i++) {                 // a few slow jellyfish: a glowing dome with waving tentacles
        const r = Math.max(5, h * .065), x = w * (.2 + i * .3) + Math.sin(t / 3000 + i * 2) * w * .05, y = sy * (.3 + i * .13) + Math.sin(t / 2300 + i * 1.3) * h * .05, rgb = i % 2 ? "255,150,230" : "130,230,255";
        tkGlow(c, x, y, r * 1.9, rgb, .08); c.fillStyle = `rgba(${rgb},.5)`; c.beginPath(); c.arc(x, y, r, Math.PI, 0); c.fill(); c.fillStyle = `rgba(${rgb},.8)`; c.fillRect(Math.round(x - r), Math.round(y), Math.round(r * 2), 2);
        c.strokeStyle = `rgba(${rgb},.55)`; c.lineWidth = 1;
        for (let k = -2; k <= 2; k++) { c.beginPath(); c.moveTo(x + k * r * .4, y + 2); for (let j = 1; j <= 5; j++) c.lineTo(x + k * r * .4 + Math.sin(t / 400 + j * .8 + k + i) * 2, y + 2 + j * r * .4); c.stroke(); }
      }
    },
    floor(c, w, h, t, sy) { for (let i = 0; i < 4; i++) { const x = Math.round(w * (.14 + i * .24)), rw = Math.round(h * (.08 + (i % 2) * .05)); tkR(c, "#1b2338", x, sy - rw * .55 + 3, rw, rw * .55); tkR(c, "#2d3a5a", x + 2, sy - rw * .55 + 3, rw - 5, 2); const g = .4 + .4 * Math.sin(t / 700 + i); c.fillStyle = `rgba(90,255,220,${g.toFixed(2)})`; c.fillRect(x + rw * .5, sy - rw * .4, 2, 2); } },
    top(c, w, h) {                                  // a soft vignette
      const key = "vig" + w + "x" + h; let g = TK.grads[key];
      if (!g) { g = TK.grads[key] = c.createRadialGradient(w / 2, h / 2, Math.min(w, h) * .3, w / 2, h / 2, Math.max(w, h) * .72); g.addColorStop(0, "rgba(0,0,12,0)"); g.addColorStop(1, "rgba(0,0,12,.6)"); }
      c.fillStyle = g; c.fillRect(0, 0, w, h);
    },
  },
  garden: {
    water: ["#7fd8c8", "#3a9a96", "#1d6468"], sand: ["#e8dcc0", "#c9b88f", "#f6eed8"], ray: .09,
    back(c, w, h, t, sy) { for (let i = 0; i < 3; i++) tkPlant(c, Math.round(w * (.05 + i * .45)), sy, Math.round(h * (.18 + (i % 2) * .08)), t, i * 3, "#4f9f62", "#78c58a", .05); },
    floor(c, w, h, t, sy) {
      for (let x = 4; x < w; x += 9) { c.fillStyle = "rgba(160,140,100,.35)"; c.fillRect(x, sy + 3 + (x % 7), 5, 1); }      // raked sand lines
      const st = [[.06, .1, "#8f979c"], [.16, .07, "#a8b0b4"], [.44, .09, "#7e878d"], [.62, .06, "#9ea6aa"], [.86, .11, "#8a9398"]];   // round stones
      for (const [fx, fr, col] of st) { const x = Math.round(w * fx), r = Math.round(h * fr * .5); c.fillStyle = col; c.beginPath(); c.ellipse(x, sy + 1, r * 1.4, r, 0, Math.PI, 0); c.fill(); c.fillStyle = "rgba(255,255,255,.3)"; c.fillRect(x - r * .7, sy - r * .7, Math.max(2, r * .6), 2); }
      const lx = Math.round(w * .2), u = Math.max(2, h * .035), glow = .55 + .25 * Math.sin(t / 500);   // the stone lantern
      tkR(c, "#6e7479", lx - 2 * u, sy - u, 4 * u, u); tkR(c, "#858c91", lx - u, sy - 3 * u, 2 * u, 2 * u); tkR(c, "#6e7479", lx - 2 * u, sy - 4 * u, 4 * u, u);
      tkGlow(c, lx, sy - 5.5 * u, 3 * u, "255,214,110", .16 * glow); tkR(c, "#a1a8ad", lx - 1.6 * u, sy - 7 * u, 3.2 * u, 3 * u); tkR(c, `rgba(255,214,110,${glow.toFixed(2)})`, lx - .9 * u, sy - 6.4 * u, 1.8 * u, 1.8 * u);
      tkR(c, "#6e7479", lx - 2.6 * u, sy - 8 * u, 5.2 * u, u); tkR(c, "#858c91", lx - 1.6 * u, sy - 8.9 * u, 3.2 * u, u); tkR(c, "#6e7479", lx - .5 * u, sy - 9.8 * u, u, u);
    },
    top(c, w, h, t) { for (let i = 0; i < 9; i++) { const x = ((i * .211 * w + t * .012 * (.6 + (i % 3) * .2)) % (w + 8)) - 4, y = 3 + (i * 7) % 12 + Math.sin(t / 700 + i) * 1.5; tkR(c, i % 2 ? "#ffc9d9" : "#fff0f4", x, y, 3, 2); if (i % 3 === 0) tkR(c, "#f08aab", x + 1, y + 1, 1, 1); } },   // petals drifting on the surface
  },
  ship: {
    water: ["#2260a8", "#12407e", "#081f44"], sand: ["#b8a06a", "#8f7a4a", "#d5c08a"], ray: .13,
    floor(c, w, h, t, sy) {                         // a broken hull lying on the sand, a snapped mast and a torn sail
      const x0 = w * .5, hw = w * .42, hh = h * .36;
      c.fillStyle = "#6b4a2b"; c.beginPath(); c.moveTo(x0, sy + 2); c.lineTo(x0 + hw * .06, sy - hh * .45); c.lineTo(x0 + hw * .2, sy - hh * .8); c.lineTo(x0 + hw * .42, sy - hh * .95); c.lineTo(x0 + hw * .5, sy - hh * .7); c.lineTo(x0 + hw * .58, sy - hh); c.lineTo(x0 + hw * .72, sy - hh * .75); c.lineTo(x0 + hw * .8, sy - hh * .9); c.lineTo(x0 + hw, sy - hh * .35); c.lineTo(x0 + hw, sy + 2); c.closePath(); c.fill();
      c.fillStyle = "#4a3019"; for (let k = 1; k < 4; k++) c.fillRect(Math.round(x0 + hw * .04 * k), Math.round(sy - hh * .22 * k), Math.round(hw * (1 - .08 * k)), 1);   // planks
      c.fillStyle = "#2a1a0c"; for (let k = 0; k < 3; k++) { c.beginPath(); c.arc(x0 + hw * (.25 + k * .22), sy - hh * .35, Math.max(2, h * .028), 0, 6.2832); c.fill(); }   // port holes
      c.fillStyle = "#8a6a44"; for (let k = 0; k < 5; k++) c.fillRect(Math.round(x0 + hw * (.1 + k * .2)), Math.round(sy - hh * .8), 2, Math.round(hh * .75));   // ribs
      c.save(); c.translate(x0 + hw * .55, sy - hh * .8); c.rotate(.42); tkR(c, "#5a3d22", -1, -h * .42, 3, h * .42); tkR(c, "#5a3d22", -h * .12, -h * .32, h * .24, 2);
      c.fillStyle = "rgba(226,218,190,.72)"; c.beginPath(); c.moveTo(-h * .1, -h * .3); c.lineTo(h * .1, -h * .3); c.lineTo(h * .02 + Math.sin(t / 900) * 2, -h * .12); c.closePath(); c.fill(); c.restore();
    },
  },
};

const TANK_DECO_ART = {
  chest(c, x, sy, u, t) {
    const cyc = t % 6500, open = cyc < 1300, w = 4 * u, bh = 1.6 * u, lh = u;
    tkR(c, "#7a4a22", x - w / 2, sy - bh, w, bh + 1); tkR(c, "#5b3516", x - w / 2, sy - 3, w, 4); tkR(c, "#e0b030", x - w / 2, sy - bh * .55, w, 2); tkR(c, "#e0b030", x - 1, sy - bh, 3, bh); tkR(c, "#fff0a0", x - .5, sy - bh * .75, 2, 2);
    if (open) { tkR(c, "#ffd84a", x - w / 2 + 2, sy - bh - 2, w - 4, 3); tkR(c, "#8f5a2a", x - w / 2, sy - bh - lh - u * .5, w, lh); tkR(c, "#e0b030", x - w / 2, sy - bh - lh - u * .5, w, 1); }
    else { tkR(c, "#8f5a2a", x - w / 2, sy - bh - lh, w, lh); tkR(c, "#e0b030", x - w / 2, sy - bh - lh, w, 1); tkR(c, "#e0b030", x - 1, sy - bh - lh, 3, lh); }
    if (open) { c.strokeStyle = "rgba(255,255,255,.8)"; for (let k = 0; k < 4; k++) { const p = Math.min(1, cyc / 1300 + k * .15); tkBub(c, x + (k - 1.5) * u * .6 + Math.sin(t / 200 + k) * 1.5, sy - bh - lh - p * 4.5 * u, 1 + (k % 2)); } }
  },
  anchor(c, x, sy, u, t) {
    const col = "#4b5563", hi = "#7b8696";
    tkR(c, col, x - .3 * u, sy - 5 * u, .6 * u, 5 * u); tkR(c, col, x - 1.6 * u, sy - 4.2 * u, 3.2 * u, .5 * u); tkR(c, hi, x - .3 * u, sy - 5 * u, 1, 5 * u);
    c.strokeStyle = col; c.lineWidth = 2; c.strokeRect(Math.round(x - .5 * u), Math.round(sy - 6.4 * u), Math.round(u), Math.round(1.2 * u));
    for (let k = 0; k < 4; k++) { tkR(c, col, x - 2 * u + k * .5 * u, sy - (.6 + k * .5) * u, .6 * u, .6 * u); tkR(c, col, x + 1.4 * u - k * .5 * u, sy - (.6 + k * .5) * u, .6 * u, .6 * u); }
    tkR(c, col, x - 2.3 * u, sy - 1.9 * u, .9 * u, .5 * u); tkR(c, col, x + 1.4 * u, sy - 1.9 * u, .9 * u, .5 * u); tkR(c, col, x - 2 * u, sy - .5 * u, 4 * u, .5 * u);
  },
  castle(c, x, sy, u, t) {
    const sand = "#d2c08f", dark = "#a8966a", lt = "#e6d6a8", tw = 2.2 * u;
    tkR(c, sand, x - 3 * u, sy - 4 * u, 6 * u, 4 * u); tkR(c, lt, x - 3 * u, sy - 4 * u, 6 * u, 1);
    for (const sx of [-1, 1]) { const tx = x + sx * 2.9 * u - tw / 2; tkR(c, sand, tx, sy - 6 * u, tw, 6 * u); tkR(c, dark, tx + tw - 2, sy - 6 * u, 2, 6 * u); for (let k = 0; k < 3; k++) tkR(c, sand, tx + k * tw / 2.4, sy - 6.9 * u, tw / 3.2, .9 * u); tkR(c, "#4a3b20", tx + tw / 2 - 1, sy - 4.6 * u, 2, 3); }
    tkR(c, sand, x - tw / 2, sy - 7.5 * u, tw, 3.6 * u); for (let k = 0; k < 3; k++) tkR(c, sand, x - tw / 2 + k * tw / 2.4, sy - 8.4 * u, tw / 3.2, .9 * u);
    tkR(c, "#4a3b20", x - .6 * u, sy - 2.2 * u, 1.2 * u, 2.2 * u); tkR(c, "#4a3b20", x - .6 * u, sy - 2.8 * u, 1.2 * u, .6 * u);
    tkR(c, "#8a7a52", x, sy - 11.4 * u, 1, 3 * u); const wv = Math.sin(t / 250) * 1.5; c.fillStyle = "#e05050"; c.beginPath(); c.moveTo(x + 1, sy - 11.4 * u); c.lineTo(x + 1 + 1.4 * u + wv, sy - 10.6 * u); c.lineTo(x + 1, sy - 9.8 * u); c.closePath(); c.fill();
  },
  bigcoral(c, x, sy, u, t) { tkCoral(c, Math.round(x - u * 1.2), sy, 6 * u, "#ff6f91", "#ffc4d6", t, 1); tkCoral(c, Math.round(x + u * 1.4), sy, 8.4 * u, "#ff9248", "#ffe08a", t, 3); tkCoral(c, Math.round(x), sy, 5 * u, "#d86bd0", "#f3c2ee", t, 5); },
  bubbler(c, x, sy, u, t) {
    tkR(c, "#6b7280", x - 1.2 * u, sy - 1.4 * u, 2.4 * u, 1.4 * u); tkR(c, "#9aa3b0", x - 1.2 * u, sy - 1.4 * u, 2.4 * u, 1); tkR(c, "#1f2937", x - .4 * u, sy - 1.6 * u, .8 * u, 2);
    c.strokeStyle = "rgba(255,255,255,.85)"; for (let k = 0; k < 7; k++) { const p = (t / 1500 + k / 7) % 1; tkBub(c, x + Math.sin(t / 300 + k * 1.7) * .5 * u, sy - 1.8 * u - p * 8 * u, p > .6 ? 3 : p > .3 ? 2 : 1); }
  },
};
// one decoration standing on the floor at its slot (the Shop thumbnails call this too)
function drawDeco(c, id, x, sy, u, t) { const f = TANK_DECO_ART[id]; if (f) f(c, x, sy, u, t); }

// the whole tank. w, h = tank pixels, t = ms, themeId = the look (a TANK_THEMES id), decos = the decoration ids shown (default: the player's), fish = the swimmers (default: the tank's)
function drawTank(c, w, h, t, themeId, decos, fish) {
  const A = TANK_ART[themeId] || TANK_ART.pond; decos = decos || S.tankDecoOn; fish = fish || TK.sim;
  c.imageSmoothingEnabled = false;
  const gk = themeId + ":" + h; let g = TK.grads[gk];
  if (!g) { g = TK.grads[gk] = c.createLinearGradient(0, 0, 0, h); g.addColorStop(0, A.water[0]); g.addColorStop(.55, A.water[1]); g.addColorStop(1, A.water[2]); }
  c.fillStyle = g; c.fillRect(0, 0, w, h);
  const sy = Math.round(h * TANK_FLOOR), u = Math.max(2, h / 26);   // u: the drawing unit of the decorations
  tkRays(c, w, h, t, sy, A.ray);
  if (A.back) A.back(c, w, h, t, sy);
  tkSand(c, w, h, sy, A.sand);
  if (A.floor) A.floor(c, w, h, t, sy);
  for (let i = 0; i < decos.length; i++) drawDeco(c, decos[i], Math.round(w * (TANK_DECO_SLOT[decos[i]] || .5)), sy + 1, u, t);   // the decorations stand on the floor, the fish swim in front of them
  for (let k = 0; k < fish.length; k++) {           // the fish: mirrored when they swim left, a gentle bob and tilt
    const s = fish[k]; c.save(); c.translate(Math.round(s.x), Math.round(s.y)); c.scale(s.dir, 1); c.rotate(Math.sin(t * s.bobS + s.ph) * .06);
    c.drawImage(s.spr, -s.w / 2, -s.h / 2, s.w, s.h); c.restore();
  }
  if (A.front) A.front(c, w, h, t, sy);
  c.strokeStyle = "rgba(255,255,255,.7)"; c.lineWidth = 1;   // rising bubbles
  for (let i = 0; i < 12; i++) { const p = ((t / 1000) * (.07 + (i % 4) * .025) + i * .37) % 1; tkBub(c, w * ((i * .137 + .05) % 1) + Math.sin(t / 600 + i) * 2, sy * (1 - p), 1 + (i % 3)); }
  if (A.top) A.top(c, w, h, t, sy);
}
// small pictures for the Shop and the Aquarium lists: a theme (no fish, no decorations) or one decoration alone on a plain panel, as PNG data URLs (made once)
const TK_DECO_U = { castle: 3.8, bigcoral: 4.6, chest: 6, anchor: 5.2, bubbler: 5.5 };   // drawing unit per decoration so each one fills its thumbnail
const TK_THUMBS = {}, TK_PANEL = "#245a8c";      // a decoration thumbnail is the decoration alone on this plain dark-blue panel (no tank background)
function tankThumb(kind, id) {
  const key = kind + ":" + id; if (TK_THUMBS[key]) return TK_THUMBS[key];
  const cv = document.createElement("canvas"); cv.width = 72; cv.height = 48; const c = cv.getContext("2d");
  if (kind === "theme") drawTank(c, 72, 48, 1500, id, [], []);
  else { c.fillStyle = TK_PANEL; c.fillRect(0, 0, 72, 48); c.imageSmoothingEnabled = false; drawDeco(c, id, 36, 45, TK_DECO_U[id] || 4.6, 1500); }
  return TK_THUMBS[key] = cv.toDataURL();
}
function tankFrame(t, dt) {
  const cv = $("tankCv"), W = cv.clientWidth, H = cv.clientHeight; if (!W || !H) return;
  const w = Math.max(40, Math.round(W / TANK_SCALE)), h = Math.max(30, Math.round(H / TANK_SCALE));
  if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
  const k = Math.min(2.4, Math.max(.6, Math.min(w / 230, h / 105)));
  for (let i = 0; i < TK.sim.length; i++) {
    const s = TK.sim[i]; s.w = Math.round(24 * k * (.8 + .7 * s.norm)); s.h = Math.round(s.w * 2 / 3);
    const range = Math.max(1, w - s.w); s.u += s.dir * s.spd * k * dt / range;
    if (s.u >= 1) { s.u = 1; s.dir = -1; } else if (s.u <= 0) { s.u = 0; s.dir = 1; }            // turns (mirrors) at the edges
    s.x = s.w / 2 + s.u * range; s.y = s.h / 2 + s.depth * (h * .86 - s.h) + Math.sin(t * s.bobS + s.ph) * s.bobA;
  }
  drawTank(cv.getContext("2d"), w, h, t, S.tankTheme);
  const tip = $("tankTip");
  if (TK.tip && t < TK.tip.until) { const s = TK.tip.s; tip.hidden = false; tip.style.transform = `translate(${Math.round(s.x * TANK_SCALE)}px, ${Math.round((s.y - s.h / 2) * TANK_SCALE)}px) translate(-50%, -110%)`; }
  else if (!tip.hidden) { tip.hidden = true; TK.tip = null; }
}
function tankLoop(t) { if (!TK.on) return; TK.raf = requestAnimationFrame(tankLoop); const dt = Math.min(.05, Math.max(0, (t - TK.last) / 1000)); TK.last = t; tankFrame(t, dt); }
function tankStart() { if (TK.on) return; TK.on = true; TK.last = performance.now(); TK.raf = requestAnimationFrame(tankLoop); }
function tankStop() { TK.on = false; if (TK.raf) cancelAnimationFrame(TK.raf); TK.raf = 0; TK.tip = null; }
function tankState() { return { on: TK.on, raf: TK.raf, fish: TK.sim.map(s => ({ id: s.f.id, x: s.x, y: s.y, dir: s.dir, w: s.w })), tip: TK.tip && !$("tankTip").hidden ? $("tankTip").textContent : null, w: $("tankCv").width, h: $("tankCv").height }; }   // tests only
// tap a swimming fish: its name and rarity show for a moment
$("tankCv").addEventListener("pointerdown", e => {
  const cv = $("tankCv"), r = cv.getBoundingClientRect(), x = (e.clientX - r.left) / TANK_SCALE, y = (e.clientY - r.top) / TANK_SCALE;
  for (let i = TK.sim.length - 1; i >= 0; i--) {
    const s = TK.sim[i];
    if (Math.abs(x - s.x) <= s.w / 2 + 2 && Math.abs(y - s.y) <= s.h / 2 + 2) { $("tankTip").innerHTML = `<b>${s.f.name}</b> <span class="rar-${s.f.rarity}">${s.f.rarity}</span>`; TK.tip = { s, until: performance.now() + 2200 }; $("tankTip").hidden = false; return; }
  }
});
function tankPut(b) { if (S.tank.length >= TANK_SIZE) return; const i = S.bag.indexOf(b); if (i < 0) return; S.bag.splice(i, 1); S.tank.push(b); save(); render(); }
function tankTake(b) { if (bagFull()) return; const i = S.tank.indexOf(b); if (i < 0) return; S.tank.splice(i, 1); S.bag.push(b); save(); render(); }
function aqRow(b, label, fn, disabled, why) {
  const f = fishById(b.fishId), row = document.createElement("div"); row.className = "row"; row.classList.toggle("locked", !!b.locked);
  const c = document.createElement("canvas"); drawFish(c, f); row.append(c);
  row.insertAdjacentHTML("beforeend", `<div class="grow"><b>${f.name}</b>${b.locked ? ' <span class="ico i-padlock"></span>' : ""}<br><span class="rar-${f.rarity}">${f.rarity}</span> · ${b.weight} kg</div>`);
  const btn = document.createElement("button"); btn.className = "btn no-rivets"; btn.type = "button"; btn.textContent = label; btn.disabled = !!disabled; if (why) btn.title = why; btn.onclick = fn; row.append(btn); return row;
}
let aqTab = "fish";                                  // FISH | THEME | DECOR (not saved)
function aqPick(id, kind) { return kind === "theme" ? TANK_THEMES[id] : TANK_DECOS[id]; }
function aqThumbRow(kind, id, label, fn, on, note) {   // an owned theme / decoration: a small picture, its name and one button
  const it = aqPick(id, kind), row = document.createElement("div"); row.className = "row" + (on ? " on" : "");
  row.insertAdjacentHTML("beforeend", `<img class="tkthumb" alt="" src="${tankThumb(kind, id)}"><div class="grow"><b>${tankName(kind, id)}</b>${kind === "deco" ? ' <span class="kind in">DECOR</span>' : ""}<br><span class="small">${note}</span></div>`);
  const btn = document.createElement("button"); btn.className = "btn no-rivets"; btn.type = "button"; btn.textContent = label; btn.onclick = fn; btn.setAttribute("aria-pressed", on ? "true" : "false"); row.append(btn); return row;
}
function tankUse(id) { if (!S.tankThemes.includes(id)) return; S.tankTheme = id; save(); render(); }
function tankDecoToggle(id) {
  if (!S.tankDecos.includes(id)) return;
  const i = S.tankDecoOn.indexOf(id);
  if (i >= 0) S.tankDecoOn.splice(i, 1);
  else if (S.tankDecoOn.length >= TANK_DECO_MAX) { toast("Max 4 decorations"); $("aqMsg").textContent = "Max 4 decorations"; return; }
  else S.tankDecoOn.push(id);
  save(); render();
}
function renderAquarium() {
  const full = S.tank.length >= TANK_SIZE;
  $("tankCount").textContent = `Tank: ${S.tank.length} / ${TANK_SIZE}`;
  document.querySelectorAll("#aqTabs .tab").forEach(b => { b.classList.toggle("on", b.dataset.tab === aqTab); b.setAttribute("aria-selected", b.dataset.tab === aqTab ? "true" : "false"); });
  const L = $("aqLists"); L.innerHTML = "";
  if (aqTab === "theme") {
    $("aqMsg").textContent = "Tap a theme to use it. More themes are sold in the Shop.";
    S.tankThemes.forEach(id => L.append(aqThumbRow("theme", id, S.tankTheme === id ? "IN USE" : "USE", () => tankUse(id), S.tankTheme === id, TANK_THEMES[id].blurb)));
  } else if (aqTab === "decor") {
    const on = S.tankDecoOn.length;
    $("aqMsg").textContent = on >= TANK_DECO_MAX ? "Max 4 decorations" : `Tap a decoration to switch it on or off (${on} / ${TANK_DECO_MAX} shown).`;
    if (!S.tankDecos.length) L.insertAdjacentHTML("beforeend", `<div class="row aq-empty">No decorations yet. Buy some in the Shop.</div>`);
    S.tankDecos.forEach(id => L.append(aqThumbRow("deco", id, S.tankDecoOn.includes(id) ? "ON" : "OFF", () => tankDecoToggle(id), S.tankDecoOn.includes(id), TANK_DECOS[id].blurb)));
  } else {
    const msg = [full ? `Tank is full (${S.tank.length}/${TANK_SIZE})` : "", S.tank.length && bagFull() ? "Bag is full" : ""].filter(Boolean).join(" · ");
    $("aqMsg").textContent = msg || "Tap a swimming fish to see its name. Fish in the tank are safe from SELL ALL.";
    L.insertAdjacentHTML("beforeend", `<h3 class="aq-h">In the tank <small>${S.tank.length} / ${TANK_SIZE}</small></h3>`);
    if (!S.tank.length) L.insertAdjacentHTML("beforeend", `<div class="row aq-empty">The tank is empty. Put a fish in from your bag.</div>`);
    S.tank.forEach(b => L.append(aqRow(b, "TAKE OUT", () => tankTake(b), bagFull(), "Bag is full")));
    L.insertAdjacentHTML("beforeend", `<h3 class="aq-h">In your bag <small>${S.bag.length} / ${S.bagMax}</small></h3>`);
    if (!S.bag.length) L.insertAdjacentHTML("beforeend", `<div class="row aq-empty">Your bag is empty. Go fishing!</div>`);
    S.bag.forEach(b => L.append(aqRow(b, "PUT IN TANK", () => tankPut(b), full, `Tank is full (${S.tank.length}/${TANK_SIZE})`)));
  }
  tankSync();
}
document.querySelectorAll("#aqTabs .tab").forEach(b => b.onclick = () => { aqTab = b.dataset.tab; renderAquarium(); });

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
