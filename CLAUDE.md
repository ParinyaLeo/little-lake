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
js/data.js        Static data: ISLANDS, ISLAND_IDS, RAW fish table → FISH, fishById, DIFF, RODS, BAITS, odds constants
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

**New save:** 300 coins, `rods: ["bamboo"]`, `rodEq: "bamboo"`, `baits: { worm: 0, shrimp: 0, golden: 0 }`,
`baitSel: "none"`, bag capacity 5, `pending: null` (the catch waiting on the Result screen).
**Old saves** (from before rods/baits) have `rod` (level), `bait` (count) and `useBait`. `load()` migrates them once:
level 1 → Bamboo; level 2+ → also owns and equips the Sturdy Rod, and each level above 2 is refunded 200 coins; the old
bait count becomes Shrimp, selected unless `useBait` was false. A selected bait with 0 left loads as `"none"`.
If another tab saves, the `storage` listener reloads `S` so tabs don't overwrite each other.

**Islands:** Harbor, Frost, Desert and Forest each have 10 fish (4 Common, 3 Rare, 2 Epic, 1 Legendary).
The secret island **Little Lake** has one Mythical fish, the *Lake Guardian*. It unlocks only after all
4 islands are mastered.

**Fishing:**
1. **CAST**. You can't cast if the bag is full. One bait of the selected kind (`S.baitSel`) is used per cast;
   when it runs out the selection goes back to `"none"`. Rod and bait can't change mid-cast.
2. A bite comes after a random **1–5 s** wait. Press **HOOK!** within **1 s** or the fish swims away.
3. **Reel minigame:** a marker moves across a meter. Press **REEL** while it is inside the green zone.
   **3 hits** = caught. You may miss up to `allowedMiss()` times (= equipped rod's `miss`, +1 with the Forest reward).
   One more miss and the fish escapes. The HUD shows one heart per allowed miss; each miss empties one. After every press the marker resets and the zone moves.
   Marker speed and zone width depend on rarity (`DIFF`) × the rod's `speed` / `zone` (× 0.8 speed with Steady Hands).
4. **Rarity odds** (Common/Rare/Epic/Legendary, `rarityWeights(baitId, rodId)`): base 60/30/8/2, plus the selected
   bait's change (Worm −10/+10/0/0, Shrimp −20/0/+16/+4, Golden Lure −35/−5/+22/+18), plus Shrimp's change again with
   the Lucky Rod, plus −8/0/+5/+3 with the Desert reward. Each tier is at least 0, the total is scaled to 100%, and
   Legendary is capped at 20% (the rest goes to Epic). So no bait = 60/30/8/2 and Shrimp = 40/30/24/6 as before.
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
message line, rod/bait/reward row and dots/hearts row have fixed heights. Anything new on this screen needs a fixed
size too; the `stays put in every phase` tests in `play_test.py` check it.

**Bag:** sell fish one at a time or **SELL ALL** for coins.

**Rods** (`RODS`, bought once, one equipped in `S.rodEq`; each is a trade-off):

| Rod | Price | Misses | Other |
|-----|-------|--------|-------|
| Bamboo Rod | free (starter) | 1 | – |
| Sturdy Rod | 200 | 2 | – |
| Precision Rod | 450 | 1 | green zone 35% wider |
| Lucky Rod | 700 | 1 | Shrimp-like odds boost, but marker 10% faster |

**Baits** (`BAITS`, consumable, one kind selected in `S.baitSel` or `"none"`): Worm x5 60 coins (small Rare boost),
Shrimp x5 100 coins (the old bait odds), Golden Lure x3 250 coins (strong Epic/Legendary boost).

**Shop:** rods, baits and Bigger bag +5 (150 coins). Every item shows its exact effect (rods: `rodFx()`; baits: the
odds with your equipped rod), OWNED / EQUIPPED tags, and "Need N more coins". Buttons are disabled for items you
own or can't afford. A new rod is not equipped automatically; a new bait is selected if no bait was selected.

**Tackle Box** (button on Home and in the Shop): EQUIP a rod you own and USE a bait you have (EQUIPPED labels), plus
the bag and each island reward with icon, effect and UNLOCKED / LOCKED (with progress). The fishing HUD shows the
equipped rod and selected bait as buttons. Tapping one opens the **Choose Rod / Choose Bait** popup (`#pickBox`,
`openPicker()` in `js/fishing.js`): every rod or bait as a card with its effect, odds and status. Owned rods and baits you
have are buttons (one tap equips or selects and closes); the rest are disabled and greyed out with "N COINS · Buy in Shop" (just "🪙N" below 700px). The popup has
GO TO SHOP and CLOSE, and closes with Esc or a tap outside. Tab stays inside open dialogs, and focus returns to the chip.
The chips are disabled outside idle, so the popup never opens mid-catch, and Space never casts while a dialog is open.

**Mastery:** find all 10 fish on an island to master it and unlock its reward:
- Harbor → *Golden Hook*: fish sell for 20% more
- Frost → *Steady Hands*: marker moves 20% slower
- Desert → *Lucky Lure*: higher Epic/Legendary chance
- Forest → *Master's Charm*: one extra allowed miss (renamed from "Master Rod" so it isn't confused with the shop rod)

Rewards are automatic and apply on top of the equipped rod. Active rewards also show as small icons on the fishing
screen (hover or tap for the effect).

Catching the Lake Guardian sets `S.mythical`. The Home screen then shows the "Lake Legend" trophy title.

**Demo mode** (for presenting): on any screen except Title, tap the **LITTLE LAKE** title 5 times. Its buttons give +1000 coins,
complete Harbor, complete 4 islands, fill the bag, or reset the save.

## Visual style notes

- **Fonts:** Pixelify Sans (local, `assets/fonts/`) for titles, buttons, tabs and island names; Courier New for
  small text and numbers. The `@font-face` leaves out the digits (`unicode-range`) because the font's 5 and 7 look
  like letters. Ligatures are off because "fi" turned into one odd glyph.
- **Icons:** 12x12 pixel art in `css/style.css` as inline SVG data URIs (`.ico .i-coin`, `i-fish`, `i-book`,
  `i-bag`, `i-rod`, `i-star`, `i-map`, `i-shop`, `i-box`, `i-bait`, `i-heart`, `i-heart0`, `i-lock`, `i-rod-<rod id>`,
  `i-bait-<bait id>` / `i-bait-none`, and the reward icons
  `i-hook`, `i-hands`, `i-lure`, `i-charm` named by `ISLANDS[id].icon`). Icon rules must come after the `.ico` rule,
  because its `background` shorthand resets `background-image`. Use `<span class="ico i-NAME"></span>` inside a button or card.
- **Rarity colours:** Common `#cfd8dc`, Rare `#64b5f6`, Epic `#ce93d8`, Legendary `#ffd54f`, Mythical `#ff80ab`.
  The Result screen reads them from `#result[data-rarity]`, Collection cards from `.cell.r-<Rarity>`.
- **Title screen:** `assets/harbor.jpg` as a full-screen `<img class="title-bg">` (fixed, `object-fit: cover`,
  pixelated, `object-position` keeps the fisherman in view; a different position below 700px). No frame. The sign floats
  near the top and the 4 buttons sit at the bottom (2x2 on phones) over a dark gradient (`.title-shade`). The only
  effect is `.title-shimmer`, a soft blurred light band. Its fade-in is opacity-only, because a transform on the screen would
  detach the fixed picture. The pixel clouds and water dashes (`.bgfx`) are used only on Home.
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
