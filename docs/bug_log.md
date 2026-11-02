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

## Report (i): polish and moving a save between devices

### BUG-14 – Forest picture: white block floating on the water, white dots in the sky
- **Problem:** in `assets/forest.png` a solid white bar hung above the water in front of the trees at the foot of the waterfall, and the top-left sky was full of isolated white dither dots.
- **Cause:** the foam was a 26x3 rectangle drawn *above* the horizon, and the front row of trees covered the bottom of the fall, so the bar floated over the trees. The dots were the dithered "sunbeams" (`beam` colour) from review round 3.
- **Fix:** in `tools/make_backgrounds.py` the sunbeams (and their colour) are removed; no tree is planted in front of the fall, so it runs down to the water; the new `splash_pool()` is drawn *after* the water: a dithered mist cloud beside the fall, a foam mound sitting on the water line (solid middle, bubbly edge) and ripples spreading out. Only `assets/forest.png` and `tools/water_masks/forest.png` changed (25 colours, 17 KB); the other three pictures came out byte-identical.
- **Test:** `Forest picture: no white dots in the top-left sky, foam sits on the water line (no floating white bar)`; the existing `forest: the bobber lands on water` still passes with the new mask.

### BUG-15 – Fishing panel had a large empty area between the ROD/BAIT chips and the buttons
- **Problem:** outside the reel minigame, the space kept for the meter and the dots/hearts row (90px) was empty brown wood.
- **Fix:** a progress box (`#isleProg`, `renderIsleProgress()` in `js/fishing.js`) lies over exactly that space: "<Island>: X / 10 found" with a bar, then the island's Mastery reward ("Mastery reward: Golden Hook – …", or "★ Mastered! Golden Hook is active: …" with a gold bar). Little Lake shows "Little Lake: X / 1 found" and the Lake Guardian line. `showMeter(on)` swaps the meter and the progress box with `visibility`, so their space never changes and the CAST/HOOK/REEL button doesn't move. The line updates the moment a fish is caught (during the 700 ms celebration), not only after KEEP.
- **Tests:** `<size> <island>: progress line '<Island>: X / 10 found' with bar and reward text, fits between the chips and CAST` (5 islands at 1280x720 and 360x640), `progress line updates right after a catch (and after KEEP)`, `while reeling the meter replaces the progress line, CAST/REEL doesn't move`, plus all existing `stays put in every phase` tests.
- **Found while testing:** the first REEL-position check measured during the 280 ms screen fade-in and saw a 1.7px offset; it now waits for the animation.

### BUG-16 – Town Map: Harbor card text covered the fisherman
- **Problem:** the island name and "x / 10 found" sat in the bottom-left corner, right over the fisherman on the dock in the Harbor picture.
- **Fix:** card text now sits in the bottom-right corner over a dark corner shade (`--card-shade`, a radial gradient), on every card for consistency.
- **Test:** `<size>: Harbor card text sits bottom-right, clear of the fisherman (left part of the card)` at 1280x720 and 360x640.

### BUG-17 – Saves can't move between a phone browser, the home-screen app or another device
- **Problem:** progress lives in one browser's `localStorage` (`littleLakeSave`). A home-screen app or another device starts empty, and there was no way to carry a save over.
- **Fix:**
  - **EXPORT SAVE** (Tackle Box): a popup with the save as a text code (base64 of the save JSON, UTF-8 so names like "Señor 🎣" survive) in a read-only box, **COPY** (clipboard, falling back to selecting the text) and **DOWNLOAD .TXT**.
  - **IMPORT SAVE** (Tackle Box, and a small link under the Title buttons for a new device): paste the code or **LOAD FILE**. `readCode()` ignores spaces and line breaks, rejects broken, cut-off and non-save codes with a clear message, and runs the same checks as `load()` (now `cleanSave()`, shared by both), so an old or partly broken save is repaired the same way. Before replacing an existing game it asks "This will replace your current progress (…) with …"; CANCEL changes nothing. With no game yet it loads straight away.
  - Esc, tapping outside and CLOSE/CANCEL close the popups; Tab stays inside them. HOW TO PLAY says "Saves stay in this browser. Use Export / Import to move progress."
  - The save key and format are unchanged.
- **Tests:** `EXPORT SAVE (Tackle Box) shows the save as a base64 code in a read-only box`, `download .txt holds the same code`, `COPY confirms (or selects the code)`, `Esc closes the Export popup`, `broken or wrong codes show a clear message and change nothing` (garbage, cut off, `{"foo":1}`, an array, `{sound}` only, empty), `a valid code asks first: 'This will replace your current progress'`, `CANCEL on the confirm keeps the current save`, `Esc closes the Import popup`, `export then import gives an identical save (line breaks in the pasted code are ignored)`, `LOAD FILE reads the .txt and asks before replacing`, `the loaded file restores the save`, `an old or partly broken save code goes through the same checks as load()`, `360x640: Title shows IMPORT SAVE with no page scroll`, `on a new device the code loads straight from the Title screen`, `360px: Tackle Box with EXPORT / IMPORT SAVE has no side scroll`, `360x640: Export popup fits …`, `360x640: Import popup and its confirm step fit with every button visible`, `Tab stays inside the Import popup`, `tapping outside closes the Import popup without importing`, `HOW TO PLAY: 'Saves stay in this browser. …'`.
- **Found while testing:** the confirm step didn't fit at 360x640 (REPLACE SAVE was below the fold), so the code box is hidden during the confirm. The `hidden` attribute also lost to `.btns { display: grid }`, which showed both button rows; a global `[hidden] { display: none !important }` fixes that.
- **Removed later (Report k, owner decision):** the owner decided that saving in the browser is enough, so Export / Import Save was taken out completely (Tackle Box buttons, Title link, both popups, `exportCode()` / `readCode()`, CSS and tests). The entry above is kept as history. The save key, format and `cleanSave()` are unchanged. See BUG-19.

## Report (j): Town Map cards show only places, and the fisherman dresses for each island

### BUG-18 – Harbor card showed the fisherman baked into the photo; same outfit on every island
- **Problem:** the Harbor card on the Town Map used `assets/harbor.jpg`, which has a fisherman painted into it, while the Frost, Desert and Forest cards show only scenery. And the drawn fisherman (`js/fisherman.js`) wore the same straw hat and blue shirt on every island, even in the snow and at night.
- **Cause:** the photo's fisherman was only hidden on the fishing canvas (`cleanPlate()` at runtime); CSS can't run that patch, so the card showed the raw photo. The sprite had one fixed palette and one set of maps.
- **Fix:**
  - `tools/make_harbor_clean.py` opens the game in headless Chromium, runs the game's own `cleanPlate(img, SCENES.harbor.fisher)` on `harbor.jpg` (loaded as a data URL so the canvas isn't tainted over `file://`) and saves the result as `assets/harbor_clean.jpg`. `.bg-harbor` uses it, with the original photo behind it as the fallback layer. The Title screen keeps `harbor.jpg` with the fisherman as cover art, and the Harbor fishing scene still draws the animated fisherman over the clean plate.
  - `OUTFITS` in `js/fisherman.js`: each island's `SCENES[island].fisher.outfit` picks a palette plus head/body/legs maps on the same grids (head 22x15, body 18x16, legs 28x11) and arm colours. Frames are cached per outfit. Body frames, hand positions and the rod code are shared, so every pose and the rod tip are exactly where they were. Harbor = straw hat, blue shirt, olive trousers (unchanged); Frost = red parka with a fur-trimmed hood, yellow scarf and mittens, dark trousers, white boots; Desert = wide light-tan sun hat, sleeveless light shirt, light khaki shorts, sandals; Forest = green explorer cap with a red feather, olive vest over a cream shirt, brown trousers; Little Lake = purple hooded cloak with glowing cyan trim, a dark belt and a small lantern drawn over the arm.
- **Found while checking the contact sheet:** the Frost scarf first showed only as a box on his back (the hood hides the neck), so it now wraps below the hood with a tail; the Desert shorts were the same tan as the dock wood, so they are a lighter khaki; the Little Lake cloak was too dark on the night dock and is a brighter purple.
- **Tests:** `harbor_clean.jpg = the clean plate (same size, matches cleanPlate, differs from the photo where the fisherman sat)`, `1366x768 / 360x640: Harbor map card shows no fisherman (clean picture first, old photo behind it as fallback), no side scroll` (shirt/hat pixels in his spot on the card vs the same card with the old photo), `Title screen keeps the original harbor.jpg cover art`, `each island draws a different outfit (5 different pixel hashes)`, `every outfit keeps the sprite size and the exact rod tip in all 7 poses`, `<island>: the fisherman wears the <island> outfit`, `<island>: fisherman pose follows the phase (all 7 poses)`, plus the existing `<island>: the line starts at the rod tip in every phase (<= 2px)`, `<island>: CAST button stays put in every phase` and `1366x768 / 360x640: Town Map cards show the island pictures, no side scroll` (now including Harbor). Screenshots: `shots/outfits_contact.png` (5 outfits x 7 poses over their islands), `shots/51_harbor_card_*.png`.

## Report (k): cleanup before the final presentation

### BUG-19 – Export / Import Save removed (owner decision)
- **Problem:** the owner does not want the Export / Import Save feature (BUG-17): saving in this browser is enough for the presentation.
- **Fix:** removed the Tackle Box "Save" section (EXPORT SAVE / IMPORT SAVE), the IMPORT SAVE link under the Title buttons, the `#exportBox` / `#importBox` popups, `exportCode()`, `readCode()` and `SAVE_KEYS` (`js/state.js`), the export/import code in `js/screens.js`, their CSS and their tests. Normal saving is untouched: same key `littleLakeSave`, same format, `load()` still runs `cleanSave()`. HOW TO PLAY (Saving) now says: "Your progress is saved automatically in this browser on this device. A different browser, device or home-screen app has its own separate save."
- **Tests:** `no Export / Import / save code anywhere (every screen, popups, HOW TO PLAY, the game files)`, `HOW TO PLAY (Saving): …`, `normal saving still works (key littleLakeSave, CONTINUE)`, plus all existing save/load tests.

### BUG-20 – iPhone Safari: the LITTLE LAKE sign was cut off at the top of the Title screen
- **Problem:** in portrait on iPhone Safari the top edge of the Title sign was cut off.
- **Cause (likely; a real iPhone was not available):** the Title screen's height was `100vh`/`100svh` minus the body padding, with only `3vh` of top padding on phones (about 17–20px). With the sign's bob animation (−6px) that left 11–14px, and on iOS `100vh` is the large viewport (toolbar hidden), so the screen could be taller than the visible area and scroll or bounce. There was no safe-area padding either.
- **Fix:** `viewport-fit=cover`; the Title screen is exactly `100dvh` tall (`100vh` fallback) with `overflow: hidden` on the page, top padding `max(4vh, env(safe-area-inset-top) + 20px)` (phones: `max(3vh, …)`) and bottom padding with `env(safe-area-inset-bottom)`, so the sign stays at least 12px from the top even at the top of its bob and nothing scrolls. The body padding and the fishing screen's height also include the safe areas.
- **Tests:** `<size>: Title sign >= 12px from the top (even at the top of its bob), 4 buttons on screen, no page scroll` at 390x844, 375x667, 360x640, 390x700 (Chromium), `WebKit iPhone 13 / iPhone SE: …` (Playwright WebKit with the iPhone device profiles), `viewport-fit=cover is set`, `Title uses 100dvh (100vh fallback) and env(safe-area-inset-top / bottom)`.
- **Found while testing:** WebKit's iPhone SE profile (320x568) still showed 11px: the phone media query kept the old `padding: 3vh 0 1vh` and overrode the new rule. It now uses the same safe-area `max()`.
- **Not tested:** a real iPhone (notch, collapsing toolbar). Playwright's WebKit on Windows has no safe-area insets.

### BUG-21 – Leaving Shop or Tackle Box meant scrolling almost three screens
- **Problem:** on a phone the Shop is about 2150px tall and the Tackle Box about 2240px, and HOME/BACK were only at the very bottom.
- **Fix:** a sticky bar (`#navbar`) on Home, Map, Bag, Shop, Collection and Tackle Box with **< BACK** on the left and the screen name in the middle. It is `position: sticky` in the normal flow, so it never covers the top of a screen, and `scroll-padding-top` keeps focused controls from hiding under it. BACK uses a small history (`navStack` in `js/screens.js`, max 20): it returns to the screen the player came from (Home as the fallback; on Home it returns to the Title screen). A Result screen is only remembered on the way to the Bag, and the same screen is never stored twice in a row, so repeated catches don't grow the history. The Bag's own BACK button uses the same history. Esc closes an open popup and does nothing else; with no popup open, Esc works as BACK (not on Home). The HOME buttons at the bottom stay. The bar is hidden on Title, Fishing and Result; on the Fishing screen TOWN MAP and OPEN BAG stay next to CAST.
- **Tests:** `<size> <screen>: BACK + '<NAME>' visible at the top, still visible and clickable after scrolling 1500px down` and `the bar doesn't cover the screen's content, no side scroll` (6 screens at 360x640 and 1366x768), `Shop and Tackle Box really scrolled …`, `Fishing (Frost) > GO TO SHOP > BACK returns to the Fishing screen on the same island`, `Home > Bag > BACK returns to Home`, `Map > Fishing > TOWN MAP > BACK …`, `Shop > Tackle Box > BACK = Shop …`, `BACK on Home returns to the Title screen`, `no BACK bar on the Fishing screen …`, `no BACK bar on the Result screen`, `Esc with a popup open only closes the popup …`, `Tab order: BACK is the first control on a screen`, plus the existing `after selling in the bag, BACK returns to the catch` and every `stays put in every phase` test.

### BUG-22 – Backgrounds: harbor banner only at the top (with the old fisherman), plain blue while fishing
- **Problem:** Home, Map, Bag, Shop, Collection and Tackle Box showed `harbor.jpg` as a banner at the top of the page (fisherman included) above a blue gradient, with pixel clouds and water dashes (`.bgfx`). The Fishing screen had a plain blue background (`body.plain`).
- **Fix:** one fixed full-viewport layer (`#backdrop`, `position: fixed; inset: 0`, behind `.app`; not `background-attachment: fixed`, which iOS ignores) with one layer per picture: `harbor_clean.jpg` (no fisherman) on the menu screens and the current island's picture (harbor_clean, frost, desert, forest, secret) while fishing. `background-size: cover`, `image-rendering: pixelated`, no blur. A dark shade sits on top: about 35% on menus (stronger toward the bottom) and about 55% while fishing, so the framed scene stays the focus. Changing island crossfades the layers in 300 ms (off with reduced motion). `preloadBackdrops()` loads the five pictures after the Title screen appears and sets each one only once it has loaded, so a missing picture leaves its matching gradient and causes no JavaScript error. The body keeps only a fallback colour; `.bgfx`, the clouds, the water dashes and their CSS are gone.
- **Tests:** `<size>: menu screens show harbor_clean.jpg (no fisherman) full-viewport, fixed while scrolling, cover + pixelated, ~35% shade`, `<size>: Fishing backdrop changes with the island (5 pictures), full viewport, ~55% shade` (1600x900, 1366x768, 360x640, 390x844), `<size> <screen>: all text sits on solid panels (readable over the backdrop)`, `changing island crossfades the backdrop in about 300 ms`, `prefers-reduced-motion: no backdrop crossfade`, `a backdrop that fails to load keeps its gradient colour, no JavaScript errors`, `old pixel clouds and water dashes are gone`. Screenshots of every screen at 1600x900 and 390x844: `shots/60_*.png`.

## Report (l): pages didn't fit a laptop window

### BUG-23 – On a laptop the player had to scroll to reach buttons on most screens
- **Problem:** at a CSS viewport of 1536x730 (Windows at 125% scaling) the pages were taller than the window: Home 834px, Bag 788, Collection 810, Shop 1237, Tackle Box 1441 (and Map 637 at 1280x600), so buttons like HOME, SELL ALL or the Home menu sat below the fold.
- **Cause:** a 150px `.spacer` on Home that only existed to show the old harbor banner (no longer needed with the fixed backdrop, BUG-22); the sticky BACK bar (BUG-21, about 70px) stacked under the LITTLE LAKE header, and also shown on Home where BACK makes no sense; fixed-size panels, tiles and buttons that never shrank on short windows; Shop and Tackle Box lists made the whole page long.
- **Fix:**
  - `.spacer` removed (markup and CSS).
  - No BACK bar on Home (it is the root screen and keeps its MENU button; Esc does nothing there). The bar now lives inside the header row (`.app > .top`): on windows 900px and wider it sits in the middle (LITTLE LAKE | < BACK + screen name | coins). Below 900px it wraps to its own row and the whole header is `position: sticky` with a negative `top` (header height + gap), so only the BACK row stays on screen while a phone page scrolls.
  - Wide windows (`@media (min-width: 900px)`): paddings, gaps, header height, buttons, stat tiles, map cards, collection cards and tabs follow the window height with `clamp(…, vh, …)`, so they shrink on short windows (e.g. 1280x600) and stay at full size on tall ones. Text never goes below 12px. The Collection shows 5 cards per row (2 rows).
  - Bag, Shop and Tackle Box (`body.fit`, `FIT_SCREENS` in `js/screens.js`): on wide windows the page is exactly one window tall (`100dvh`, `100vh` fallback); the header and the bottom buttons stay put and only the list inside the panel (`.scroll-list`) scrolls, with a thin gold-on-dark scrollbar and a small sticky fade at its bottom edge. Phones scroll the whole page as before.
  - HOW TO PLAY's GOT IT! button is sticky at the bottom of its panel, so it stays on screen when the help text scrolls on a short window.
- **Tests:** at 1920x915, 1536x730, 1366x625 and 1280x600: `<size> <screen>: no page scroll, every main button fully on screen, no side scroll` (Home, Map, Bag, Collection, Shop, Tackle Box, Fishing, Result with a full bag, Result), `no BACK bar on Home; BACK bar in the header row on the other menu screens`, `header is one row`, `<shop / tackle / bag>: the list scrolls inside the panel (thin scrollbar, fade at the bottom), the page doesn't, bottom buttons stay visible`, `Collection shows all 10 cards, the island progress bar and the reward line, text >= 12px`, `no text smaller than 12px on the menu screens`, `1280x600: rod / bait picker, HOW TO PLAY, confirm, name and mastery popups fit`; `CAST/HOOK/REEL button stays put in every phase` and `the page doesn't scroll while fishing` now also run at 1366x625 and 1280x600; phones (360x640, 390x844): BACK visible after scrolling 1500px and no side scroll; `no BACK bar on Home` at every size. Screenshots: `shots/70_*.png` (every screen at 1536x730 and 1366x625), `shots/71_picker_*.png`.
- **Found while testing:** at 1280x600 HOW TO PLAY's GOT IT! was below the bottom of its scrolling panel (fixed with the sticky button above).

## Report (m): short screens looked empty on big windows

### BUG-24 – Home, Town Map, Bag and Collection stuck to the top of a tall window
- **Problem:** after BUG-23 the short screens fit, but on a tall window (e.g. 1920x915) everything sat at the top and the bottom 40% showed only the backdrop water, so the screens looked empty.
- **Fix:**
  - On windows 900px and wider these four screens get `body.center` (`CENTER_SCREENS` in `js/screens.js`). `.app` is at least one window tall (`100dvh`, `100vh` fallback); the header row stays at the top and the active screen fills the rest. Its `::before` / `::after` spacers (`flex-grow` 45 / 55) centre the panel and buttons with a slight upward bias. The content is up to 1100px wide (980px elsewhere).
  - Sizes grow with the window height through `clamp(…, vh, …)` up to a maximum and shrink on short windows as before: stat tiles up to 120px high, bigger stat values and icons, larger buttons and headings, Town Map cards up to 220px, Collection fish up to 80px, Bag fish pictures up to 96px. Text never goes below 12px; small buttons (MENU, SELL) keep their size.
  - Home: **TOWN MAP** is the main action, a big green button two rows tall and 1.6x as wide, beside OPEN BAG / SHOP / COLLECTION / TACKLE BOX in a 2x2 grid. Same colours and art.
  - Shop, Tackle Box, Fishing and phones (under 900px) are unchanged.
- **Tests:** at 1920x915, 1536x730, 1366x625 and 1280x600: `<screen>: centred layout, no page scroll, every main button fully on screen` (Home, Map, Bag, Collection), `TOWN MAP is the main Home action (wider and taller than …)`; at 1920x915: `Home panel + buttons are vertically centred (within 10% of the window) and use at least 55% of its height`, `Map, Bag and Collection are centred below the header too`, `the content is at most about 1100px wide`; `Fishing screen is not affected by the centred layout`, `Shop and Tackle Box keep their fixed layout`; `360x640 / 390x844: phones keep the current Home layout`; plus all BUG-23 fit tests. Screenshots: `shots/80_<screen>_1920x915.png` and `_1366x625.png`.
- **Found while checking the screenshots:** the bigger button font also reached the small SELL buttons in the Bag rows, so their rivets overlapped the text; small buttons keep their size, and the SELL buttons get 22px side padding (they were always slightly too narrow for the corner rivets).
