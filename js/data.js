// Static game data: islands, fish species, minigame difficulty, rods and baits. Loaded first.
/* ===================== DATA ===================== */
const ISLANDS = {
  harbor: { name: "Harbor", bg: "bg-harbor", reward: "Golden Hook", icon: "hook", effect: "Fish sell for 20% more coins" },
  frost:  { name: "Frost",  bg: "bg-frost",  reward: "Steady Hands", icon: "hands", effect: "Minigame marker moves 20% slower" },
  desert: { name: "Desert", bg: "bg-desert", reward: "Lucky Lure", icon: "lure", effect: "Higher chance of Epic and Legendary fish" },
  forest: { name: "Forest", bg: "bg-forest", reward: "Master's Charm", icon: "charm", effect: "One additional miss is allowed" },
  secret: { name: "Little Lake", bg: "bg-secret", reward: "", effect: "" },
};
const ISLAND_IDS = ["harbor", "frost", "desert", "forest"];
// [name, rarity, price, minKg, maxKg, len, h, body, belly, fin, stripe, plan]   (plan = optional drawing plan, see FISH_PLANS in state.js; most fish have none)
const RAW = {
  harbor: [["Sardine","Common",20,.1,.3,16,4,"#9fb3c8","#e3edf5","#7d93a8",null],["Moon Jellyfish","Common",25,0.2,1.5,17,5,"#bfc9e8","#eef0ff","#9aa5d6","#e58fb3","jellyfish"],
           ["Hermit Crab","Common",30,0.02,0.2,14,7,"#e8833a","#ffd0a0","#c95f1f","#7a3b12","crab"],["Mackerel","Common",25,.3,1.5,17,5,"#3f7f8f","#dfeee8","#2f6170","#1f4652"],
           ["Clownfish","Rare",60,.1,.3,13,7,"#f57c1f","#ffb36b","#1b1b1b","#ffffff"],["Seahorse","Rare",70,0.01,0.05,14,8,"#f2b134","#ffe39a","#d98a1a","#a35f0c","seahorse"],
           ["Pufferfish","Rare",65,.5,2,12,9,"#e7c76b","#fff3c4","#c9a443",null],["Reef Shark","Epic",150,10,30,14,8,"#7f93a3","#e6eef3","#5d7080","#3c4a56","shark"],
           ["Manta Ray","Epic",180,20,90,16,9,"#2c3e66","#cfd9f2","#1b2747",null],["Oarfish","Legendary",450,30,120,21,4,"#e9eef5","#ffffff","#e8384f","#b9c4d4"]],
  frost:  [["Ice Smelt","Common",20,.05,.2,15,4,"#cfe3ee","#ffffff","#9cc0d4",null],["Arctic Cod","Common",30,1,6,17,6,"#8d8a6e","#e9e4cf","#6e6b52","#a9a586"],
           ["Snow Crab","Common",25,0.3,3,16,5,"#cfe6f2","#ffffff","#9cc0d6","#6f9bb8","crab"],["Lake Perch","Common",25,.2,1,14,6,"#b3a23b","#f2e8b5","#8f8023","#4e4a1c"],
           ["Snow Trout","Rare",70,1,5,17,6,"#a7b7c4","#f2f6f9","#8a9aa7","#e57373"],["Frost Salmon","Rare",80,2,8,18,6,"#9db8d6","#fde3d8","#7895b4","#f28b82"],
           ["Comb Jelly","Rare",60,0.05,0.5,12,9,"#5eead4","#d5fff7","#18c8b4","#b8fff0","jellyfish"],["Ice Pike","Epic",160,3,12,20,5,"#7fa7c9","#e4eef7","#5b84a8","#d9e7f3"],
           ["Greenland Shark","Epic",200,80,400,21,6,"#7a6a5c","#cfc4b8","#5a4c40","#4a3f36","shark"],["Aurora Squid","Legendary",480,1,15,15,8,"#7e57c2","#80deea","#26c6da","#b388ff","squid"]],
  desert: [["Oasis Tilapia","Common",20,.3,1.5,14,7,"#8a9a72","#e5e8cf","#6b7a55",null],["Sand Carp","Common",25,1,5,16,7,"#c9a66b","#f3e3c0","#a8864d",null],
           ["Oasis Turtle","Common",15,0.5,4,12,5,"#5f9a4b","#e8e2a8","#4d7a3a","#2f5a25","turtle"],["Mud Catfish","Common",30,1,8,18,5,"#6e5a46","#cdbba5","#54432f",null],
           ["Golden Perch","Rare",75,.5,3,14,7,"#e6b422","#fff1b8","#c99410","#a87a00"],["Oasis Crayfish","Rare",60,0.02,0.15,12,4,"#c8553d","#f0a58a","#a63e2a","#6e2416","crayfish"],
           ["Scarab Gar","Rare",80,2,10,20,4,"#3e8e5a","#cfead8","#2b6b42","#1b4a2c"],["Sun Arowana","Epic",170,1,6,19,6,"#ffb300","#ffe7a3","#ff6f00","#ff8f00"],
           ["Sandstorm Eel","Epic",150,2,9,21,3,"#b0884f","#e9d3a8","#8a6633","#6b4d24"],["Pharaoh Koi","Legendary",500,3,12,15,8,"#ffd700","#fff8dc","#1565c0","#ffffff"]],
  forest: [["Bluegill","Common",20,.1,.6,13,7,"#5b7fa6","#f2c38b","#3f6085","#2e4a68"],["Brook Trout","Common",30,.3,2,16,5,"#6b7f4a","#f0a27a","#4f6133","#e6d36a"],
           ["Green Frog","Common",20,0.05,0.4,15,5,"#5cb85c","#d9f0b0","#3f9a3f","#2a6e2a","frog"],["Forest Carp","Common",30,2,10,16,8,"#9b7b3a","#efdcae","#7a5d25",null],
           ["Rainbow Trout","Rare",80,1,5,17,6,"#7a9c6a","#f7c6d8","#5c7d4d","#ef5b8a"],["Moss Bass","Rare",70,1,4,15,7,"#4f7f3a","#d7e8c4","#355e25","#2a4a1c"],
           ["Axolotl","Rare",65,0.05,0.3,13,7,"#f4a6c0","#ffe0ea","#e5527f","#b5546f","axolotl"],["Waterfall Salmon","Epic",170,3,12,19,6,"#c0504d","#f7d1c7","#8e3431","#e0786f"],
           ["Snapping Turtle","Epic",210,5,35,22,6,"#6b7a4a","#cfc8a0","#56633a","#3a4528","turtle"],["Spirit Koi","Legendary",520,4,12,15,8,"#ffffff","#ffebee","#e53935","#e53935"]],
  secret: [["Lake Guardian","Mythical",2000,50,150,22,9,"#00bfa5","#b2fff2","#ffd54f","#ffd54f"]],
};
const FISH = [];
for (const isl in RAW) RAW[isl].forEach((r, i) => FISH.push({ id: `${isl}_${i}`, island: isl, name: r[0], rarity: r[1], price: r[2], min: r[3], max: r[4], len: r[5], h: r[6], body: r[7], belly: r[8], fin: r[9], stripe: r[10], plan: r[11] || null }));
const fishById = id => FISH.find(f => f.id === id);
const DIFF = { Common: { speed: .55, zone: .26 }, Rare: { speed: .8, zone: .2 }, Epic: { speed: 1.05, zone: .15 }, Legendary: { speed: 1.35, zone: .11 }, Mythical: { speed: 1.6, zone: .09 } };

/* ===================== GEAR ===================== */
// Rods: bought once, one is equipped. miss = misses allowed; zone / speed multiply the green zone width and
// the marker speed; luck = the same odds boost as Shrimp bait. Island rewards apply on top.
// Every rod is a step up in forgiveness: 1, 2, 3, 5 misses (Master's Charm adds 1, so up to 6 hearts with the Lucky Rod).
const RODS = {
  bamboo:    { name: "Bamboo Rod",    short: "Bamboo",    price: 0,   miss: 1, zone: 1,    speed: 1,   luck: false },
  sturdy:    { name: "Sturdy Rod",    short: "Sturdy",    price: 200, miss: 2, zone: 1,    speed: 1,   luck: false },
  precision: { name: "Precision Rod", short: "Precision", price: 450, miss: 3, zone: 1.35, speed: 1,   luck: false },
  lucky:     { name: "Lucky Rod",     short: "Lucky",     price: 700, miss: 5, zone: 1,    speed: 1.1, luck: true },
};
const ROD_IDS = Object.keys(RODS);
// Baits: bought in packs, one is used per cast from the selected kind. odds = change to the
// [Common, Rare, Epic, Legendary] chances (in % points) on top of BASE_ODDS.
const BAITS = {
  worm:   { name: "Worm",        pack: 5, price: 60,  odds: [-10, 10, 0, 0],   blurb: "Small boost to Rare fish." },
  shrimp: { name: "Shrimp",      pack: 5, price: 100, odds: [-20, 0, 16, 4],   blurb: "Better chance of Epic and Legendary fish." },
  golden: { name: "Golden Lure", short: "Golden", pack: 3, price: 250, odds: [-35, -5, 22, 18], blurb: "Strong boost to Epic and Legendary fish." },
};
const BAIT_IDS = Object.keys(BAITS);
// Floats (the bobber on the water): pure cosmetics, bought once in the Shop, one equipped in S.floatEq; no effect on odds, bites, rods, baits, rewards or timing.
const FLOATS = {
  classic: { name: "Classic Float", short: "Classic", price: 0,   blurb: "Red and white, the one every angler knows." },
  candy:   { name: "Candy Float",   short: "Candy",   price: 150, blurb: "A pink-and-white swirl, sweet as a lollipop." },
  frog:    { name: "Frog Float",    short: "Frog",    price: 250, blurb: "A green float with two tiny eyes watching the water." },
  duck:    { name: "Duck Float",    short: "Duck",    price: 350, blurb: "A yellow float with an orange beak." },
  golden:  { name: "Golden Float",  short: "Golden",  price: 600, blurb: "Shiny gold with a slow sparkle." },
};
const FLOAT_IDS = Object.keys(FLOATS);
const BASE_ODDS = [60, 30, 8, 2];            // no bait, no bonuses
const LUCKY_ROD_ODDS = BAITS.shrimp.odds;    // Lucky Rod: "like Shrimp bait"
const LUCKY_LURE_ODDS = [-8, 0, 5, 3];       // Desert mastery reward
const LEGENDARY_CAP = 20;                    // stacked boosts never push Legendary above 20%
const TIERS = ["Common", "Rare", "Epic", "Legendary"];
