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
// [name, rarity, price, minKg, maxKg, len, h, body, belly, fin, stripe]
const RAW = {
  harbor: [["Sardine","Common",20,.1,.3,16,4,"#9fb3c8","#e3edf5","#7d93a8",null],["Striped Mullet","Common",25,.5,2,17,5,"#8fa1ad","#dfe7ec","#6f818c","#5c6b75"],
           ["Sea Bream","Common",30,.5,3,14,7,"#d98c8c","#f6d6c6","#b86a6a",null],["Mackerel","Common",25,.3,1.5,17,5,"#3f7f8f","#dfeee8","#2f6170","#1f4652"],
           ["Clownfish","Rare",60,.1,.3,13,7,"#f57c1f","#ffb36b","#1b1b1b","#ffffff"],["Blue Tang","Rare",70,.3,.8,14,8,"#1e5bd6","#3c7cf0","#ffd21f","#0c2a66"],
           ["Pufferfish","Rare",65,.5,2,12,9,"#e7c76b","#fff3c4","#c9a443",null],["Lionfish","Epic",150,.5,1.5,14,8,"#e0563c","#ffd6c9","#ffe9e0","#ffffff"],
           ["Manta Ray","Epic",180,20,90,16,9,"#2c3e66","#cfd9f2","#1b2747",null],["Oarfish","Legendary",450,30,120,21,4,"#e9eef5","#ffffff","#e8384f","#b9c4d4"]],
  frost:  [["Ice Smelt","Common",20,.05,.2,15,4,"#cfe3ee","#ffffff","#9cc0d4",null],["Arctic Cod","Common",30,1,6,17,6,"#8d8a6e","#e9e4cf","#6e6b52","#a9a586"],
           ["Herring","Common",25,.2,.8,16,5,"#6f9bb8","#e6f0f6","#4f7c99",null],["Lake Perch","Common",25,.2,1,14,6,"#b3a23b","#f2e8b5","#8f8023","#4e4a1c"],
           ["Snow Trout","Rare",70,1,5,17,6,"#a7b7c4","#f2f6f9","#8a9aa7","#e57373"],["Frost Salmon","Rare",80,2,8,18,6,"#9db8d6","#fde3d8","#7895b4","#f28b82"],
           ["Lumpsucker","Rare",60,.5,3,12,9,"#6aa36b","#cfe8c8","#4c7d4d",null],["Ice Pike","Epic",160,3,12,20,5,"#7fa7c9","#e4eef7","#5b84a8","#d9e7f3"],
           ["Glacier Sturgeon","Epic",200,10,60,21,6,"#5d6f7d","#d5dde3","#43525e","#8fa0ad"],["Aurora Koi","Legendary",480,3,10,15,8,"#7c4dff","#b39ddb","#18ffff","#69f0ae"]],
  desert: [["Oasis Tilapia","Common",20,.3,1.5,14,7,"#8a9a72","#e5e8cf","#6b7a55",null],["Sand Carp","Common",25,1,5,16,7,"#c9a66b","#f3e3c0","#a8864d",null],
           ["Pupfish","Common",15,.01,.05,12,5,"#4e88c9","#d8e7f5","#2f6aa8",null],["Mud Catfish","Common",30,1,8,18,5,"#6e5a46","#cdbba5","#54432f",null],
           ["Golden Perch","Rare",75,.5,3,14,7,"#e6b422","#fff1b8","#c99410","#a87a00"],["Mirage Minnow","Rare",60,.02,.1,12,4,"#7fdbff","#e8fbff","#39c0ef",null],
           ["Scarab Gar","Rare",80,2,10,20,4,"#3e8e5a","#cfead8","#2b6b42","#1b4a2c"],["Sun Arowana","Epic",170,1,6,19,6,"#ffb300","#ffe7a3","#ff6f00","#ff8f00"],
           ["Sandstorm Eel","Epic",150,2,9,21,3,"#b0884f","#e9d3a8","#8a6633","#6b4d24"],["Pharaoh Koi","Legendary",500,3,12,15,8,"#ffd700","#fff8dc","#1565c0","#ffffff"]],
  forest: [["Bluegill","Common",20,.1,.6,13,7,"#5b7fa6","#f2c38b","#3f6085","#2e4a68"],["Brook Trout","Common",30,.3,2,16,5,"#6b7f4a","#f0a27a","#4f6133","#e6d36a"],
           ["River Chub","Common",20,.2,1,15,5,"#9aa5a0","#e8ece9","#78837e",null],["Forest Carp","Common",30,2,10,16,8,"#9b7b3a","#efdcae","#7a5d25",null],
           ["Rainbow Trout","Rare",80,1,5,17,6,"#7a9c6a","#f7c6d8","#5c7d4d","#ef5b8a"],["Moss Bass","Rare",70,1,4,15,7,"#4f7f3a","#d7e8c4","#355e25","#2a4a1c"],
           ["Leaf Fish","Rare",65,.05,.3,13,7,"#a68a3a","#e8d79a","#7f6a26",null],["Waterfall Salmon","Epic",170,3,12,19,6,"#c0504d","#f7d1c7","#8e3431","#e0786f"],
           ["Ancient Sturgeon","Epic",210,20,100,22,6,"#5e5546","#d8d0bf","#463f33","#857a66"],["Spirit Koi","Legendary",520,4,12,15,8,"#ffffff","#ffebee","#e53935","#e53935"]],
  secret: [["Lake Guardian","Mythical",2000,50,150,22,9,"#00bfa5","#b2fff2","#ffd54f","#ffd54f"]],
};
const FISH = [];
for (const isl in RAW) RAW[isl].forEach((r, i) => FISH.push({ id: `${isl}_${i}`, island: isl, name: r[0], rarity: r[1], price: r[2], min: r[3], max: r[4], len: r[5], h: r[6], body: r[7], belly: r[8], fin: r[9], stripe: r[10] }));
const fishById = id => FISH.find(f => f.id === id);
const DIFF = { Common: { speed: .55, zone: .26 }, Rare: { speed: .8, zone: .2 }, Epic: { speed: 1.05, zone: .15 }, Legendary: { speed: 1.35, zone: .11 }, Mythical: { speed: 1.6, zone: .09 } };

/* ===================== GEAR ===================== */
// Rods: bought once, one is equipped. miss = misses allowed; zone / speed multiply the green zone width and
// the marker speed; luck = the same odds boost as Shrimp bait. Island rewards apply on top.
const RODS = {
  bamboo:    { name: "Bamboo Rod",    short: "Bamboo",    price: 0,   miss: 1, zone: 1,    speed: 1,   luck: false },
  sturdy:    { name: "Sturdy Rod",    short: "Sturdy",    price: 200, miss: 2, zone: 1,    speed: 1,   luck: false },
  precision: { name: "Precision Rod", short: "Precision", price: 450, miss: 1, zone: 1.35, speed: 1,   luck: false },
  lucky:     { name: "Lucky Rod",     short: "Lucky",     price: 700, miss: 1, zone: 1,    speed: 1.1, luck: true },
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
const BASE_ODDS = [60, 30, 8, 2];            // no bait, no bonuses
const LUCKY_ROD_ODDS = BAITS.shrimp.odds;    // Lucky Rod: "like Shrimp bait"
const LUCKY_LURE_ODDS = [-8, 0, 5, 3];       // Desert mastery reward
const LEGENDARY_CAP = 20;                    // stacked boosts never push Legendary above 20%
const TIERS = ["Common", "Rare", "Epic", "Legendary"];
