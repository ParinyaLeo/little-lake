# Little Lake

A pixel-art fishing game (version 0.1). Final project for **1305311 Low-Code Application Development**.

## Project rules (must follow)

- **Plain HTML, CSS and JavaScript only.** No frameworks, no libraries, no npm, no TypeScript.
- **No build step.** The files in the repo are exactly what the browser runs.
- **The game must open by double-clicking `index.html`** (a `file://` URL). This means:
  - Use normal `<script src="...">` tags. **No ES modules** (`type="module"`, `import`/`export`) and no `fetch()` of local files, because both fail over `file://`.
  - Use relative paths only. Paths inside `css/style.css` are relative to `css/` (e.g. `url("../assets/harbor.jpg")`). Paths in JS are relative to `index.html` (e.g. `"assets/harbor.jpg"`).
- **Save data lives in `localStorage` under the key `"littleLakeSave"`** (`SAVE_KEY` in `js/state.js`). Don't rename the key. `load()` must keep accepting old or broken saves and fall back to safe defaults.
- **The layout must work from 360px to 1280px wide**, with no horizontal scrolling at 360px. The breakpoint for small screens is `@media (max-width: 700px)`.
- Don't change gameplay (numbers, rules, timings) unless asked. Run the tests after every change.

## Folder structure

```
index.html        Page markup (all screens) + <link>/<script> tags
css/style.css     All styles
js/data.js        Static data: ISLANDS, ISLAND_IDS, RAW fish table → FISH, fishById, DIFF
js/state.js       Save/load (S, load, save), helpers ($, fmt, toast, sfx, confetti, banner),
                  drawFish/silhouette, derived values (discCount, secretOpen, allowedMiss, bagFull),
                  rarityWeights/rarePlus, checkMastery, multi-tab "storage" sync
js/fishing.js     Fishing screen: canvas scene, cast → bite → hook → reel minigame, caught/escape,
                  result screen KEEP/RELEASE
js/screens.js     Navigation (go, render) and the Title, Map, Bag, Shop, Tackle Box, Collection and Demo screens;
                  calls render() last to start the game
assets/harbor.jpg Harbor background image
assets/fonts/     Pixelify Sans (PixelifySans.woff2) + its licence OFL.txt (SIL Open Font License 1.1)
play_test.py      Playwright end-to-end tests
docs/bug_log.md   Playtest bugs: problem, cause, fix and the test that covers each one
```

### Script load order matters

`data.js` → `state.js` → `fishing.js` → `screens.js`. The scripts are classic scripts, so their top-level
`const`/`let`/`function` declarations share one global scope. Later files use names from earlier ones,
and the tests read globals such as `S`, `F`, `save()`, `render()`, `secretOpen()` and `allowedMiss()`.
Keep those names global. Don't wrap the files in IIFEs or modules.

## Game rules

**Screens:** Title (`titleScreen`), Home, Town Map, Fishing, Result, Bag, Shop, Tackle Box (`tackle`), Collection Book. Move between
them with `go(id)` or with any element that has `data-go="<screen id>"`.

**Title screen** (shown first; the top bar is hidden here):
- **NEW GAME** asks for a name (trimmed, 1–12 characters). If a save exists, it first shows a confirm dialog
  ("This will delete your current progress"). Nothing is reset until START is pressed with a valid name.
- **CONTINUE** loads the save and goes to Home. It is disabled when `hasSave()` is false.
- **HOW TO PLAY** opens a short help panel. **SOUND** toggles `S.sound`.
- The **☰ MENU** button on Home returns to the Title screen.

**Sound:** `S.sound` (default `true`; old saves without it load as on). Every sound effect goes through
`beep()`, which does nothing when sound is off. A save that holds only `{ sound }` (sound toggled before
any game was started) does not count as a game, so CONTINUE stays disabled.

**New save:** 300 coins, rod level 1, 0 bait, bag capacity 5, `useBait: true`, `pending: null`.
Other save fields added later: `useBait` (older saves load as `true`) and `pending` (the catch waiting on the
Result screen, or `null`). If another tab saves, the `storage` listener reloads `S` so tabs don't overwrite each other.

**Islands:** Harbor, Frost, Desert and Forest each have 10 fish (4 Common, 3 Rare, 2 Epic, 1 Legendary).
The secret island **Little Lake** has one Mythical fish, the *Lake Guardian*. It unlocks only after all
4 islands are mastered.

**Fishing:**
1. **CAST**. You can't cast if the bag is full. One bait is used per cast only while **USE BAIT** is ON
   (`S.useBait`, toggled on the fishing screen or in the Tackle Box; it can't change mid-cast).
2. A bite comes after a random **1–5 s** wait. Press **HOOK!** within **1 s** or the fish swims away.
3. **Reel minigame:** a marker moves across a meter. Press **REEL** while it is inside the green zone.
   **3 hits** = caught. You may miss up to `allowedMiss()` times (= rod level, +1 with the Forest reward).
   One more miss and the fish escapes. The HUD shows one heart per allowed miss; each miss empties one. After every press the marker resets and the zone moves.
   Marker speed and zone width depend on rarity (`DIFF`).
4. **Rarity odds** (Common/Rare/Epic/Legendary): 60/30/8/2 without bait, 40/30/24/6 with bait.
   The Desert reward changes them by −8/0/+5/+3. They live in `rarityWeights(withBait)` (also used for the % text).
5. **Weight** is random between the fish's min and max (skewed toward light). **Price** = base ×
   (0.7 + 0.3 × weight / mid-weight), ×1.2 with the Harbor reward. Heavier than your best = **NEW RECORD**.
6. Every catch is added to the Collection Book and saved as `S.pending` until the player decides, so a reload
   can't lose it (CONTINUE returns to it, and `go()` only allows the Result, Bag and Title screens meanwhile).
   On the Result screen, **KEEP** puts the fish in the bag ("+1 Name added to bag"); **RELEASE** throws it back.
   If the bag is full, KEEP is replaced by **SELL A FISH** (sells the cheapest fish, keeps the new one),
   **OPEN BAG** (BACK returns to the catch) or **RELEASE**. A fish is never dropped silently.

**Main action:** the CAST / HOOK! / REEL button (`#actBtn`), the **Space** key, and a tap anywhere on the scene
all call `act()`. It does nothing while the button is disabled or outside the fishing screen.

**Fishing screen layout (don't break this):** the CAST/HOOK/REEL button must not move between phases, and the
screen must fit 1366x768, 1280x720 and phones without page scroll. While fishing, `.app` is exactly one viewport
tall and the scene takes the leftover height. The meter is hidden with `visibility` (never `display: none`), and the
message line, bait/reward row and dots/hearts row have fixed heights. Anything new on this screen needs a fixed
size too; the `stays put in every phase` tests in `play_test.py` check it.

**Bag:** sell fish one at a time or **SELL ALL** for coins.

**Shop:** Rod upgrade 200 coins (+1 allowed miss), Bait pack ×5 for 100 coins (better rare odds),
Bigger bag +5 for 150 coins. Each item shows its effect before buying, e.g. "Rod Lv.2: 2 misses allowed (now 1)".

**Tackle Box** (button on Home): rod level and misses allowed, bait count and USE BAIT, bag, and each island
reward with icon, effect and UNLOCKED / LOCKED (with progress). Rewards are automatic; there is no equip system.

**Mastery:** find all 10 fish on an island to master it and unlock its reward:
- Harbor → *Golden Hook*: fish sell for 20% more
- Frost → *Steady Hands*: marker moves 20% slower
- Desert → *Lucky Lure*: higher Epic/Legendary chance
- Forest → *Master's Charm*: one extra allowed miss (renamed from "Master Rod" so it isn't confused with the shop rod)

Active rewards also show as small icons on the fishing screen (hover or tap for the effect).

Catching the Lake Guardian sets `S.mythical`. The Home screen then shows the "Lake Legend" trophy title.

**Demo mode** (for presenting): on any screen except Title, tap the **LITTLE LAKE** title 5 times. Its buttons give +1000 coins,
complete Harbor, complete 4 islands, fill the bag, or reset the save.

## Visual style notes

- **Fonts:** Pixelify Sans (local, `assets/fonts/`) for titles, buttons, tabs and island names; Courier New for
  small text and numbers. The `@font-face` leaves out the digits (`unicode-range`) because the font's 5 and 7 look
  like letters. Ligatures are off because "fi" turned into one odd glyph.
- **Icons:** 12x12 pixel art in `css/style.css` as inline SVG data URIs (`.ico .i-coin`, `i-fish`, `i-book`,
  `i-bag`, `i-rod`, `i-star`, `i-map`, `i-shop`, `i-box`, `i-bait`, `i-heart`, `i-heart0`, `i-lock`, and the reward icons
  `i-hook`, `i-hands`, `i-lure`, `i-charm` named by `ISLANDS[id].icon`). Icon rules must come after the `.ico` rule,
  because its `background` shorthand resets `background-image`. Use `<span class="ico i-NAME"></span>` inside a button or card.
- **Rarity colours:** Common `#cfd8dc`, Rare `#64b5f6`, Epic `#ce93d8`, Legendary `#ffd54f`, Mythical `#ff80ab`.
  The Result screen reads them from `#result[data-rarity]`, Collection cards from `.cell.r-<Rarity>`.
- **Island scenes** (`js/fishing.js`, `SCENES`): Harbor uses `assets/harbor.jpg`; Frost, Desert, Forest and
  Little Lake are pixel art painted on a small canvas (1 art pixel = 3 screen pixels), cached, and scaled up.
  Only the light effects (snow, heat shimmer, waterfall, stars, water glints) are redrawn each frame.
  To swap a painted island for a picture: `frost: { image: "assets/frost.jpg", rod: { x: .3, y: .3 } }`, where
  `rod` is the rod-tip position in the picture as 0-1 fractions.
- **Fish drawings** (`drawFish` in `js/state.js`, 24x16 grid): `fishShape(f)` picks slim / regular / flat / round /
  long / eel / ray from the fish's `len` and `h` (named exceptions in `FISH_SHAPES`). Rare and better fish get glints;
  Legendary and Mythical get sparkles. Keep the 24x16 size: it scales to exactly 8x (Result), 4x (Collection), 3x (Bag).
- **Animation:** animate only `transform` and `opacity` so phones stay smooth, and add every new animation to
  the `prefers-reduced-motion` block.

## Releasing (cache-busting)

Every `css/` and `js/` link in `index.html` ends in a version string such as `css/style.css?v=2`.
**On every release, bump the number on all of these links together** (e.g. `?v=2` → `?v=3`). If you
don't, browsers can load the new `index.html` with old cached CSS/JS, and the game breaks until a hard
refresh. Use the same number on every link, and add it to any new CSS/JS file you link.

## Testing

```
pip install playwright
python -m playwright install chromium
python play_test.py
```

The script opens `index.html` over `file://` at 1280×800 and 360×780 and prints PASS/FAIL for each check.
It writes screenshots to `shots/` and a summary to `results.json` (both are git-ignored).
All checks must pass before committing.
