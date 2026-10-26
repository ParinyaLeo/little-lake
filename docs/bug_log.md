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
- **Test:** `the last bait still gives bait odds`.

### BUG-6b – Bait was used automatically with no choice
- **Fix:** a **USE BAIT: ON / OFF (count)** button on the fishing screen and in the Tackle Box (`S.useBait`, saved; older saves default to ON). Bait is used only while it is ON. The button can't change mid-cast.
- **Tests:** `fishing HUD shows USE BAIT: ON with the bait count`, `USE BAIT can be turned off and is saved`, `casting with USE BAIT off keeps the bait`, `older save without the bait toggle loads with USE BAIT on`.

### BUG-7 – Players couldn't see what the rod does
- **Fix:** during reeling, hearts show the misses you have left (one heart per allowed miss; "NO MISSES LEFT!" means the next miss loses the fish).
- **Tests:** `reeling shows one heart per allowed miss and a miss empties one`, `hearts are hidden when not reeling`.

### BUG-8 – The Shop didn't say what an item would do
- **Fix:** each item shows its effect before buying: "Rod Lv.2: 2 misses allowed (now 1)", "Bait: better chance of Rare+ fish while USE BAIT is on (60% instead of 40%)", "Bag: 10 slots (now 5)". The text updates after each purchase.
- **Tests:** `Shop: rod shows 'Rod Lv.2: 2 misses allowed (now 1)'`, `Shop: bait says it works while USE BAIT is on`, `Shop: bag shows new and current size`, `Shop effect text updates after buying`.

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
