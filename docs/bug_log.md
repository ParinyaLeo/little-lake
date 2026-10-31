# Little Lake – Bug log

Problems found while playtesting version 0.1, what caused them, how they were fixed, and the
Playwright check in `play_test.py` that covers each fix. Test names are the exact text printed by
`python play_test.py`.

## Report (a): "I caught 3-4 fish, but later they were gone from my bag"

The playtest note pointed to five things to check. Three were real bugs; two are how browsers work.

| # | Checked | Finding |
|---|---------|---------|
| 1 | Local file vs GitHub Pages | **Not a bug, but a likely cause.** `index.html` opened from the computer (`file://`) and the website (`https://parinyaleo.github.io`) are different origins, so each has its own `localStorage` and its own save. Fish caught on one never appear on the other. Can't be shared without a server; now explained in HOW TO PLAY ("Saving"). |
| 2 | RELEASE vs KEEP | Working as designed. RELEASE never puts the fish in the bag, but it still counts in **FISH CAUGHT** and the Collection, so FISH CAUGHT can be higher than the bag count. KEEP now shows a clear toast and bounces the bag counter (BUG-1b). |
| 3 | Full bag | **Real bug (BUG-2).** KEEP with a full bag dropped the fish with only a short toast. |
| 4 | NEW GAME overwriting | Working as designed: NEW GAME over a save asks "This will delete your current progress" first (existing tests). |
| 5 | Real save bug | **Real bugs (BUG-1, BUG-3).** A catch on the Result screen was only held in memory, and two open tabs overwrote each other's saves. |

### BUG-1 – A catch on the Result screen could be lost
- **Problem:** after catching a fish, closing or reloading the page (or leaving the Result screen another way, e.g. the 5-tap demo shortcut) lost the fish. FISH CAUGHT and the Collection still counted it, so it looked like it had vanished from the bag.
- **Cause:** `caught()` saved the discovery and the counter, but the fish itself lived only in the in-memory variable `lastCatch` until KEEP was pressed.
- **Fix:** the catch is saved as `S.pending` the moment it is caught and is cleared only by KEEP, SELL A FISH or RELEASE. CONTINUE returns to the waiting catch, and the game won't open other screens (except the Bag) until you decide. `load()` checks `pending` and drops it if broken.
- **Tests:** `catch waiting on Result is stored in the save`, `reload + CONTINUE returns to the waiting catch`, `can't leave the Result screen without KEEP or RELEASE`, `several catches in a row all stay in the bag (and after reload)`.

### BUG-1b – Keeping a fish wasn't obvious
- **Problem:** KEEP only showed "Saved to your bag." and the bag number changed quietly.
- **Fix:** toast "+1 Sea Bream added to bag" and the BAG counter on the fishing screen bounces.
- **Test:** `KEEP shows '+1 Sea Bream added to bag' and bounces the bag count`.

### BUG-2 – Full bag on the Result screen released the fish silently
- **Cause:** the KEEP handler did `else toast("Bag is full. The fish was released.")`.
- **Fix:** when the bag is full, the Result screen hides KEEP and shows a "Bag full!" panel with **SELL A FISH** (sells your cheapest fish and keeps the new one; the panel says which fish and its price), **OPEN BAG** (sell what you like, then BACK returns to the catch), or **RELEASE**.
- **Tests:** `full bag on Result shows SELL A FISH / OPEN BAG / RELEASE instead of KEEP`, `SELL A FISH sells the cheapest fish and keeps the new one`, `OPEN BAG from a full Result opens the bag`, `after selling in the bag, BACK returns to the catch with KEEP available`, `RELEASE on a full bag leaves the bag unchanged`, `mobile full-bag choice no side scroll`.

### BUG-3 – Two open tabs overwrote each other's save
- **Problem:** with the game open in two tabs, fish kept in tab A disappeared the next time tab B saved anything.
- **Cause:** each tab keeps its own copy of the save (`S`) and writes the whole copy back, so the last tab to save won.
- **Fix:** listen for the browser's `storage` event; when another tab saves, this tab reloads `S` before it can write an old copy.
- **Test:** `a fish kept in another tab is not wiped by this tab's next save`.

## Report (b): shop items and bait felt invisible

### BUG-6 – The last bait was used up with no-bait odds
- **Cause:** `cast()` took the bait first, then `pickFish()` checked `S.bait > 0`. With 1 bait left the check saw 0, so the last bait was spent but the fish was rolled with the no-bait odds (60/30/8/2 instead of 40/30/24/6).
- **Fix:** `cast()` passes whether bait was used to `pickFish(withBait)`. The odds themselves are unchanged (they now live in `rarityWeights()`, also used for the % shown in the Shop and Tackle Box).
- **Test:** `the last bait still gives bait odds` (now checks that the last Shrimp is rolled with Shrimp odds).

### BUG-6b – Bait was used automatically with no choice
- **Fix:** a **USE BAIT: ON / OFF (count)** button on the fishing screen and in the Tackle Box (`S.useBait`, saved; older saves default to ON). Bait is used only while it is ON. The button can't change mid-cast.
- **Tests:** `fishing HUD shows USE BAIT: ON with the bait count`, `USE BAIT can be turned off and is saved`, `casting with USE BAIT off keeps the bait`, `older save without the bait toggle loads with USE BAIT on`.
- **Superseded by GEAR-1 (report e):** the ON/OFF toggle became a bait choice (Worm / Shrimp / Golden Lure / no bait). Choosing "no bait" replaces OFF; these four tests were replaced by the bait-selection and migration tests listed there.

### BUG-7 – Players couldn't see what the rod does
- **Fix:** during reeling, hearts show the misses you have left (one heart per allowed miss; "NO MISSES LEFT!" means the next miss loses the fish).
- **Tests:** `reeling shows one heart per allowed miss and a miss empties one`, `hearts are hidden when not reeling`.

### BUG-8 – The Shop didn't say what an item would do
- **Fix:** each item shows its effect before buying: "Rod Lv.2: 2 misses allowed (now 1)", "Bait: better chance of Rare+ fish while USE BAIT is on (60% instead of 40%)", "Bag: 10 slots (now 5)". The text updates after each purchase.
- **Tests:** `Shop: rod shows 'Rod Lv.2: 2 misses allowed (now 1)'`, `Shop: bait says it works while USE BAIT is on`, `Shop: bag shows new and current size`, `Shop effect text updates after buying`.
- **Superseded by GEAR-1 (report e):** rod levels became separate rods. `Shop: bag shows new and current size` is kept; the rod/bait text tests were replaced by `Shop lists 4 rods with exact effects` and `Shop lists 3 baits with pack size, price and exact odds`.

## Report (c): Island Mastery rewards were invisible

### BUG-4 – No place showed your gear and rewards
- **Fix:** a **TACKLE BOX** screen (button on Home) listing the rod (level and misses allowed), bait (count and ON/OFF), bag, and all four island rewards with icon, one-line effect, and UNLOCKED or LOCKED with progress ("3 / 10 Desert fish"). The fishing screen shows small icons for active rewards; hover or tap explains them.
- **Tests:** `TACKLE BOX opens from Home and lists rod, misses, bait, bag`, `Tackle Box shows each island reward as unlocked or locked with progress`, `every Tackle Box row has an icon and a one-line effect`, `active rewards show as small icons with tooltips`, `tapping a reward icon explains it`, `mobile Tackle Box no side scroll`, `mobile fishing HUD (bait + bonuses) no side scroll`.

### BUG-5 – "Master Rod" sounded like a rod to equip
- **Fix:** renamed to **Master's Charm** everywhere (data, Collection, Tackle Box, HOW TO PLAY, CLAUDE.md). Rewards stay automatic; the mastery banner now says "It works automatically – see your Tackle Box."
- **Test:** `'Master Rod' is renamed to 'Master's Charm' everywhere`.

### Docs
- HOW TO PLAY now covers hearts, the bait toggle, the full-bag choice, the Tackle Box, reward names, and saving.
- **Test:** `HOW TO PLAY explains bait toggle, hearts, Tackle Box and Master's Charm`.

## Report (d): the main fishing button moves around

### BUG-9 – CAST / HOOK / REEL jumped between phases and slid off-screen
- **Problem:** the main action button changed position between phases, which made the timing minigame hard. Measured top of `#actBtn`:
  1366x768: 663px while waiting and at the bite, then 727px when reeling, and the page grew to 833px so the button was almost off-screen.
  390x844 phone: 496 → 467 → 496 → 560.
- **Cause:** parts of the panel above the button changed size per phase: the reel meter was added and removed with `display: none` / `block`, the HIT dots and hearts appeared only while reeling, and the message line wrapped to one or two lines depending on the text (so the BAG label could also wrap). The fishing screen also had a fixed scene shape, so on 1366x768 and 1280x720 the panel didn't fit under it.
- **Fix:**
  - The meter is always in the layout and is hidden with `visibility`; the dots/hearts row, the message line (1 line on desktop, 2 on phones) and the bait/reward row have fixed heights. Many hearts collapse to "♥ xN" so the row never grows.
  - While fishing, the page is exactly one screen tall: the scene takes the height that is left (up to its normal shape) and the harbor picture's rod tip is re-mapped to the cropped picture. On phones the CAST/HOOK/REEL button gets its own full-width row.
  - **Space** (desktop) and **tapping anywhere on the scene** do the same as the main button. They do nothing when the button is disabled or outside the fishing screen, and Space on a focused button doesn't act twice.
  - Rules and timings are unchanged.
- **Tests:** for 1366x768, 1280x720 and 390x844: `<size>: CAST/HOOK/REEL button stays put in every phase (<= 1px)` (idle, waiting, bite, reeling, and reeling after a press) and `<size>: button is inside the viewport and the page doesn't scroll while fishing`. Also `Space casts on the fishing screen`, `tapping the scene hooks the fish`, `Space reels exactly once, even with the button focused`, `Space on a focused button acts only once`, `Space / tap do nothing while the main button is disabled (full bag)`, `Space does nothing outside the fishing screen`.

## Report (e): the shop had no real choices

### GEAR-1 – One rod upgrade and one bait gave players nothing to decide
- **Problem (design):** the Shop had a single "Rod upgrade" (always better) and a single bait, so there was never a trade-off.
- **Change:** four rods, bought once and equipped one at a time, and three baits, one of which (or none) is selected:
  - Bamboo Rod (free, 1 miss), Sturdy Rod (200, 2 misses), Precision Rod (450, green zone 35% wider, 1 miss), Lucky Rod (700, Shrimp-like odds, 1 miss, marker 10% faster).
  - Worm x5 (60, small Rare boost), Shrimp x5 (100, the old bait odds 40/30/24/6), Golden Lure x3 (250, strong Epic/Legendary boost).
  - Bait and Lucky Rod boosts stack, with Legendary capped at 20%. Island rewards still apply on top of the rod.
  - The Shop shows OWNED / EQUIPPED tags, exact effects and odds, and "Need N more coins". The Tackle Box has EQUIP / USE buttons, and the fishing HUD shows the rod and bait (tap to switch).
- **Save migration:** old `rod` level 1 → Bamboo; level 2+ → owns and equips Sturdy. Levels above 2 are refunded 200 coins each, because those players paid for misses the Sturdy Rod doesn't give. The old bait count becomes Shrimp (selected unless USE BAIT was off). It runs once, because the new save has no `rod` level.
- **Tests:** `new game starts with only the Bamboo Rod equipped and no bait`, `Shop lists 4 rods with exact effects`, `Shop: equipped starter rod is marked and can't be bought`, `Shop: items you can't afford are disabled and say how much is missing (300 coins)`, `Shop lists 3 baits with pack size, price and exact odds`, `buying a rod takes the coins, adds it, and marks it OWNED (not equipped yet)`, `can't buy a rod twice or without enough coins`, `can't buy bait without enough coins`, `buying bait with no bait selected selects it`, `buying another bait keeps the current selection`, `Tackle Box: EQUIP the Sturdy Rod (2 misses), labelled EQUIPPED`, `Tackle Box: rods you don't own point to the Shop and can't be equipped`, `Tackle Box: select Shrimp, labelled EQUIPPED`, `Tackle Box: bait you have none of says BUY IN SHOP and can't be selected`, `fishing HUD shows the equipped rod and selected bait`, `a cast uses one of the selected bait only`, `tapping BAIT switches to the next bait (Shrimp -> no bait)`, `casting with no bait uses none`, `tapping BAIT again picks Worm`, `tapping ROD switches to the next rod you own`, `a selected bait with none left loads as no bait`, `rod effects: Bamboo 1 miss, Sturdy 2, Precision zone x1.35, Lucky marker x1.1`, `island rewards stack on the rod (Master's Charm +1 miss, Steady Hands 20% slower)`, `odds unchanged for no bait and Shrimp (60/30/8/2, 40/30/24/6) and the Desert reward`, `Worm boosts Rare, Golden Lure boosts Epic and Legendary, Lucky Rod = Shrimp odds`, `bait and Lucky Rod stack, with Legendary capped at 20%`, `the cast's fish is rolled with those odds`, `old save rod level 1 -> Bamboo Rod`, `old save rod level 2 -> owns and equips Sturdy; bait becomes Shrimp (selected)`, `old save rod level 4 -> Sturdy + 400 coins refunded; USE BAIT off -> no bait selected`, `migration happens once (no second refund after saving)`, `360px: Shop with rods and baits has no side scroll`, `360px: Tackle Box with rods and baits has no side scroll`, `360px: fishing HUD with rod + bait chips fits (no side scroll, no page scroll, chips not cut off)`.

### BUG-10 – "Golden Lure x2" was cut off on 360px phones
- **Problem:** found while testing GEAR-1. On a 360px phone the bait button on the fishing screen showed "Golden Lure…".
- **Cause:** the rod and bait buttons share one row on phones, and the full bait name doesn't fit. The 360px test measured the overflow but its result wasn't part of the check.
- **Fix:** the HUD uses short bait names ("Golden x2"), and the test now fails if either button's text is cut off.
- **Test:** `360px: fishing HUD with rod + bait chips fits (no side scroll, no page scroll, chips not cut off)`.

### BUG-11 – `play_test.py` crashed on Windows when a detail contained "·"
- **Cause:** the Windows console can't print some characters, and Python stopped with a `UnicodeEncodeError` halfway through the tests.
- **Fix:** `play_test.py` sets `sys.stdout.reconfigure(errors="replace")`, so details print with a replacement character instead of crashing.
- **Test:** the full run (`python play_test.py`) completes and prints its summary.

## Report (f): choosing a rod or bait took many taps

### BUG-12 – The ROD and BAIT buttons cycled one item per tap
- **Problem:** on the fishing screen, each tap on ROD or BAIT switched to the next item (`rodChip` / `baitChip` `onclick` in `js/fishing.js`). With 4 rods or 3 baits that took several taps, and you couldn't see what an item did before switching to it.
- **Cause:** a design shortcut from GEAR-1. Cycling was quick to build but doesn't scale and hides the effects.
- **Fix:**
  - Tapping ROD or BAIT opens a **Choose Rod / Choose Bait** popup that reuses the `.banner.modal` style. Every item is a card with its icon, effect (misses, zone, marker speed), odds and status.
  - Owned rods and baits you have are buttons: one tap equips or selects, closes the popup, updates the chip and shows a toast. The equipped item is highlighted with an EQUIPPED label.
  - Rods you don't own and baits with 0 left are disabled, greyed out, and show their price with "Buy in Shop".
  - GO TO SHOP and CLOSE buttons; Esc and tapping outside also close it. Tab stays inside the dialog (and skips disabled items), Enter selects, and focus returns to the chip.
  - The chips are disabled while waiting, at the bite and while reeling, so the popup can't open mid-catch, and Space doesn't cast while a dialog is open.
  - The list scrolls inside the popup on short screens, and the title and buttons stay visible.
  - Any rod or bait now takes 2 taps (open, pick). The Tackle Box keeps its own EQUIP / USE buttons, and the CAST button layout is unchanged.
- **Found while fixing:** the old cycling handlers were removed together with the reward-icon click handler next to them. The existing test `tapping a reward icon explains it` caught it, and the handler was restored.
- **Tests:** `BAIT opens 'Choose Bait': No bait first, then each bait with count, odds and EQUIPPED`, `bait with 0 left is greyed out with 'Buy in Shop' and can't be selected`, `picking 'No bait' selects it in one tap, closes the popup, updates the chip, focus back on BAIT`, `ROD / BAIT disabled and no popup while waiting`, `... while bite`, `... while reeling`, `ROD opens 'Choose Rod': all 4 rods with misses, zone, odds, marker speed and EQUIPPED`, `equipping a non-first rod takes one tap in the popup (Lucky Rod)`, `rods you don't own are greyed out with price and 'Buy in Shop' and can't be equipped`, `Esc closes the popup and focus returns to ROD`, `keyboard: Tab moves between items (skipping locked ones), Enter selects`, `Tab stays inside the popup`, `Space doesn't cast while the popup is open`, `tapping outside closes the popup`, `CLOSE closes the popup without changing anything`, `GO TO SHOP closes the popup and opens the Shop`, `the Tackle Box still equips rods`, `360x640: Choose Rod popup fits with CLOSE and GO TO SHOP visible, no side scroll`, `360x640: Choose Bait popup fits ...`.

### BUG-13 – Long "Buy in Shop" label squeezed item names in the picker on phones
- **Problem:** on a 360px phone, locked items in Choose Rod / Choose Bait showed "100 COINS · Buy in Shop", which pushed the item name onto two lines.
- **Fix:** below 700px the label is just "🪙100" (`lockedLabel()` renders both texts, and CSS shows one). Wider screens keep the full text.
- **Tests:** `360px: locked rod shows the short price label and its name stays on one line`, `360px: locked bait shows the short price label and its name stays on one line`, `wide screens keep the full '700 COINS · Buy in Shop' label`.

## Report (g): the Harbor fisherman never moved

### ANIM-1 – The fisherman was part of the photo, so only the line and bobber moved
- **Problem:** on the Harbor scene the fisherman and his rod are baked into `assets/harbor.jpg`. Casting, a bite, reeling and a catch all looked the same: he sat still while the line moved, and the line started at a fixed point (`SCENES.harbor.rod`).
- **Fix:**
  - `cleanPlate()` (new `js/fisherman.js`) hides him: it copies water, chest lid and dock planks from beside him over the figure and the old rod, once, into an offscreen canvas. `harbor.jpg` itself is unchanged.
  - A new pixel-art fisherman (straw hat with a blue band, blue shirt, olive trousers, brown boots, sitting on the chest) is drawn in code from small pixel maps, with one cached canvas per body frame. The rod is drawn each frame as a bent curve of art pixels from his hands, and the line now starts at its drawn tip.
  - Poses per phase: idle breathing, a wind-up and fast swing when casting (the bobber now leaves the tip after the wind-up), a head tilt while waiting, a startled lean at the bite, leaning back with a bent rod while reeling (a tug on each hit, a slack wobble on each miss), a raised rod for 700 ms after a catch, and drooping shoulders after an escape.
  - The Result screen now opens 700 ms after a reeled catch so the celebration is visible. The catch is saved straight away as before, and CAST is disabled meanwhile.
  - With `prefers-reduced-motion`, each pose is one still frame.
- **Found while fixing:** the first patch missed the dark outline of the old rod (the band followed a guessed line), and copying the chest lid sideways repeated its left edge as stripes. The band was widened and the lid is now filled from a plain slice of it.
- **Tests:** `fisherman pose follows the phase (idle, casting, waiting, bite, reeling, escaped, caught)`, `caught: he celebrates on the fishing screen (button disabled), then the Result screen opens`, `the line starts at the drawn rod tip in every phase (<= 2px)`, `the rod moves between poses`, `360x640: CAST button stays put in every fisherman pose, no side scroll`, `the fisherman baked into the photo is gone (shirt and hat colours in his spot: photo vs patched)`, `prefers-reduced-motion: one still fisherman pose per phase`, and `no JavaScript errors`. The `perfect timing catches fish` check now waits 1 s for the Result screen. Screenshots: `shots/42_fisher_<pose>.png`.

## Report (h): only Harbor looked like a real place

### ART-1 – Frost, Desert, Forest and Little Lake used flat gradients and simple painted scenes
- **Problem:** Harbor had a detailed picture, but the other islands showed flat CSS gradients on the Town Map and simple code-painted scenes while fishing. They didn't look like the same game.
- **Cause:** there were no artist images yet, and no image tool.
- **Fix:**
  - `tools/make_backgrounds.py` (Python + Pillow, fixed seeds) paints each island on a 480x200 pixel grid in layers: dithered sky, clouds, far mountains / dunes / hills, shore with trees, cacti, palms, a mesa, a waterfall or ruins, calm water with streaky ripples, reflections and underwater rocks, and a dock with a crate in the lower-left. It scales the grid 4x with nearest-neighbour, using 23–27 colours per picture (about 16 KB each).
  - Review rounds (compared against `harbor.jpg`): round 1 had noisy speckled reflections, a dock that looked like a fence, blanket-like mountains, hard sunbeams and checker-patterned rocks. Round 2 fixed reflections (whole streaks), the dock (boards seen from above), mountains (peaks with snow caps) and rocks. Round 3 toned down the desert cliff reflection and the sunbeams and made the ice floes thicker. The pictures are still simpler than `harbor.jpg`.
  - The fishing screen uses the pictures with the drawn fisherman on the crate (`SCENES.<island>.fisher`). They are cropped with `anchor: [0, .8]` so the dock stays in view on wide screens (the canvas ranges from 1.15:1 on phones to 3.13:1 at 1280x720).
  - Pictures load after the Title screen appears (`preloadScenes()`). Until a picture is ready, or if it fails to load, the island shows its old painted scene, so there is never a hole or a broken image.
  - Town Map cards show the pictures over the old gradient (the fallback), with a soft dark shade behind the text. The locked secret card is unchanged.
- **Found while fixing:** the test `each painted island is detailed and looks different` read pixels from the scene canvas. A picture loaded from `file://` taints the canvas, so the test crashed. It now hides the pictures and checks the painters, which are still used as the fallback.
- **Tests:** `every island picture loads after the Title screen (naturalWidth > 0)`, `island PNGs are under 400 KB`, `<island>: fisherman pose follows the phase`, `<island>: the line starts at the rod tip in every phase (<= 2px)`, `<island>: CAST button stays put in every phase`, `<island>: the bobber lands on water` (checked against `tools/water_masks/`), `1366x768 / 360x640: Town Map cards show the island pictures, no side scroll`, `locked secret card stays '???' without the picture`, `a blocked picture falls back to the painted scene and the gradient card, no JavaScript errors`. Screenshots: `shots/43_island_<island>.png`, `44_map_*.png`, `45_frost_fallback.png`, `backgrounds_contact.png`.
