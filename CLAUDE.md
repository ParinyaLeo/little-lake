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
js/state.js       Save/load (S, load, cleanSave, save), helpers ($, fmt, toast, sfx, confetti, banner),
                  drawFish/silhouette, derived values (discCount, secretOpen, allowedMiss, bagFull),
                  rarityWeights/rarePlus, checkMastery, multi-tab "storage" sync
js/fisherman.js   Animated fisherman: cleanPlate() (patches the figure out of the photo), sprite parts, OUTFITS (one per island), poses,
                  drawFisherman(), fisherPoseFor(), fisherEvent()/fisherTug(), fisherPose()/fisherTip()/fisherOutfit() for tests
js/fishing.js     Fishing screen: canvas scene, cast → bite → hook → reel minigame, caught/escape,
                  result screen KEEP/RELEASE
js/screens.js     Navigation (go, goBack, navStack, render), the sticky BACK bar, the full-screen backdrop (setBackdrop,
                  preloadBackdrops) and the Title, Map, Bag, Shop, Tackle Box, Collection and Demo screens;
                  calls render() last to start the game
assets/harbor.jpg Harbor background image (Title cover art, fishing scene under cleanPlate())
assets/harbor_clean.jpg
                  harbor.jpg with the baked-in fisherman patched out (Town Map card, menu backdrop), written by tools/make_harbor_clean.py
assets/frost.png, desert.png, forest.png, secret.png
                  Island backgrounds painted by tools/make_backgrounds.py (1920x800 = 480x200 art pixels x4)
tools/make_backgrounds.py
                  Pillow script (tool only, never loaded by the game) that paints the 4 island PNGs with fixed seeds,
                  writes tools/water_masks/<island>.png (white = open water, used by the tests) and shots/backgrounds_contact.png
tools/make_harbor_clean.py
                  Playwright script (tool only) that runs the game's cleanPlate() on harbor.jpg in headless Chromium and saves
                  assets/harbor_clean.jpg; run it again if SCENES.harbor.fisher.patch / rodClear change
assets/fonts/     Pixelify Sans (PixelifySans.woff2) + its licence OFL.txt (SIL Open Font License 1.1)
play_test.py      Playwright end-to-end tests
docs/bug_log.md   Playtest bugs: problem, cause, fix and the test that covers each one
```

### Script load order matters

`data.js` → `state.js` → `fisherman.js` → `fishing.js` → `screens.js`. The scripts are classic scripts, so their top-level
`const`/`let`/`function` declarations share one global scope. Later files use names from earlier ones,
and the tests read globals such as `S`, `F`, `save()`, `render()`, `secretOpen()`, `allowedMiss()`, `fisherPose()` and `fisherTip()`.
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
`load()` = parse localStorage + `cleanSave(raw)`.

**Saving:** automatic, in this browser only (HOW TO PLAY: "Your progress is saved automatically in this browser on this device.
A different browser, device or home-screen app has its own separate save."). **Export / Import Save was removed on purpose**
(owner decision, see `docs/bug_log.md` BUG-17 / BUG-19): don't add save codes, copy/download or import UI back.

**Navigation / BACK bar** (`#navbar`, inside the header row `.app > .top`): shown on Map, Bag, Shop, Collection and Tackle Box
(`NAV_SCREENS`), **not on Home** (root screen, it has the ☰ MENU button), Title, Fishing or Result. It has **< BACK** (`#navBack`) on the
left and the screen name in the middle; the empty third column (`.nav-end`) keeps the name centred. **No HOME button in the top bar**
(one navigation rule: BACK is the way back). HOME buttons: the Town Map has one in its panel header (`#mapHome`, house icon `i-home`,
styled like MENU on Home; it is the only way Home from Fishing: Fishing > TOWN MAP > HOME); Shop and Tackle Box keep their bottom HOME;
the Bag and the Collection have none. On windows 900px and wider it sits in the middle of the header (LITTLE LAKE | < BACK + name | coins). Below 900px it
wraps to its own row and the whole header is `position: sticky` with a negative `top` (header height + gap), so only the BACK row stays
visible while a phone page scrolls; it is in the normal flow, so it never covers content.
`go(id)` keeps a small history (`navStack`, max 20; Home and Title clear it; a Result screen is only stored on the way to the Bag; never
the same screen twice in a row); `goBack()` returns to the previous screen, Home as the fallback. **Esc** also uses
`goBack()` (the Bag has no separate BACK button any more: the bar's BACK does the same, including Result > OPEN BAG > BACK to the
waiting catch); Esc first closes an open popup and then does nothing else, and does nothing on Home. Fishing > GO TO SHOP > BACK returns to
Fishing on the same island; Fishing > SELL > BACK and Fishing > SHOP > BACK too.

**Fishing screen buttons** (Playtest 1, BUG-32 / BUG-33): the bottom row (`.actions`) is **CAST | SHOP | TOWN MAP**; selling is the
**SELL** button in the top bar (`#sellTop`, bag icon, blue, title/aria-label "Sell your fish", glows when the bag is full), directly left of
the coin counter and as tall as it. SELL is shown **only on the Fishing screen** (`body.plain .top-sell`); no other screen gets it, and
there is no SELL FISH in the bottom row (no duplicates). SELL opens the Bag, SHOP (`#fShopBtn`, shop icon) the Shop; both are plain
`data-go` buttons, so BACK returns to Fishing through `navStack`. Wide windows: CAST, SHOP and TOWN MAP are three equal buttons on one row.
Phones: CAST is full width on top, SHOP and TOWN MAP two equal smaller buttons below (icon above the label, no corner rivets). On phones the
Fishing header keeps LITTLE LAKE, SELL and the coins on one line (smaller title, SELL without rivets; fits up to 999,999 coins at 360px).
The Choose Rod / Bait popup keeps its GO TO SHOP. The Home and Result screens keep their own OPEN BAG buttons.

**Laptop / desktop fit (don't break this):** on windows 900px and wider, every screen fits the window without page scrolling, down to
1280x600 (e.g. 1536x730 = a 1920x1080 laptop at 125%). Sizes inside `@media (min-width: 900px)` follow the window height with
`clamp(…, vh, …)` (header, paddings, gaps, buttons, stat tiles, map cards, Collection cards and tabs); text stays at least 12px.
Bag, Shop and Tackle Box (`FIT_SCREENS` → `body.fit`) are exactly one window tall and only their `.scroll-list` scrolls inside the panel
(thin gold scrollbar, sticky fade at the bottom); the header and bottom buttons stay visible. Phones (below 900px) scroll the page.
Anything new on these screens must keep fitting: the tests check 1920x915, 1536x730, 1366x625 and 1280x600.
Home, Town Map and Collection (`CENTER_SCREENS` → `body.center`, wide windows only) use the whole window: `.app` is at least
`100dvh` tall and up to 1100px wide, the header stays at the top, and the panel + buttons are centred below it with a slight upward
bias (`::before` / `::after` spacers, flex-grow 45 / 55). Tiles, fonts and buttons grow with the window height up to a maximum (stat tiles
<= 120px, island cards <= 250px high) and shrink on short windows. On Home, TOWN MAP is the main action: a big button two rows tall beside the
other four (2x2). Shop, Tackle Box, Fishing and phones don't use this.
The **Bag** is not centred: it is anchored at the top and its list has a fixed area of about 5 rows (`#bag .scroll-list`, 380px, it only
shrinks on a too-short window), so the panel and SELL ALL stay in the same place at every fish count; more fish scroll inside it. Every row
(and the empty-bag message) has one fixed height, `--bag-row`: 64px (56px on desktop windows under 760px high, fish drawn at 2x), never
stretched (`#bagList { align-content: start }`); rows are listed top-down in catch order and their text lines never wrap (ellipsis).
The bottom fade shows only while more fish are hidden below (`bagFade()` sets `.has-more`).

**Islands:** Harbor, Frost, Desert and Forest each have 10 fish (4 Common, 3 Rare, 2 Epic, 1 Legendary).
The secret island **Little Lake** has one Mythical fish, the *Lake Guardian*. It unlocks only after all
4 islands are mastered.

**Fishing:**
1. **CAST**. You can't cast if the bag is full. One bait of the selected kind (`S.baitSel`) is used per cast;
   when it runs out the selection goes back to `"none"`. Rod and bait can't change mid-cast.
2. A bite comes after a random **1–5 s** wait. Press **HOOK!** within **1 s** or the fish swims away.
3. **Reel minigame:** a marker moves across a meter. Press **REEL** while it is inside the green zone.
   **3 hits** = caught. You may miss up to `allowedMiss()` times (= equipped rod's `miss`, +1 with the Forest reward).
   One more miss and the fish escapes. The HUD shows one heart per allowed miss (up to 6 as icons, "♥ xN" above that); each miss empties one.
   On phones the 6 hearts (18px) fit on one line beside the one-line "HIT ○○○" counter. After every press the marker resets and the zone moves.
   Marker speed and zone width depend on rarity (`DIFF`) × the rod's `speed` / `zone` (× 0.8 speed with Steady Hands).
4. **Rarity odds** (Common/Rare/Epic/Legendary, `rarityWeights(baitId, rodId)`): base 60/30/8/2, plus the selected
   bait's change (Worm −10/+10/0/0, Shrimp −20/0/+16/+4, Golden Lure −35/−5/+22/+18), plus Shrimp's change again with
   the Lucky Rod, plus −8/0/+5/+3 with the Desert reward. Each tier is at least 0, the total is scaled to 100%, and
   Legendary is capped at 20% (the rest goes to Epic). So no bait = 60/30/8/2 and Shrimp = 40/30/24/6 as before.
5. **Weight** is random between the fish's min and max (skewed toward light). **Price** = base ×
   (0.7 + 0.3 × weight / mid-weight), ×1.2 with the Harbor reward. Heavier than your best = **NEW RECORD**.
6. Every catch is added to the Collection Book and saved as `S.pending` until the player decides, so a reload
   can't lose it (CONTINUE returns to it, and `go()` only allows the Result, Bag and Title screens meanwhile).
   A catch reeled in on the fishing screen first shows the fisherman celebrating for 700 ms (`FISHER_HOLD.caught`,
   CAST disabled), then the Result screen opens. On the Result screen, **KEEP** puts the fish in the bag ("+1 Name added to bag"); **RELEASE** throws it back.
   If the bag is full, KEEP is replaced by **SELL A FISH** (sells the cheapest fish, keeps the new one),
   **OPEN BAG** (BACK returns to the catch) or **RELEASE**. A fish is never dropped silently.

**Main action:** the CAST / HOOK! / REEL button (`#actBtn`), the **Space** key, and a tap anywhere on the scene
all call `act()`. It does nothing while the button is disabled or outside the fishing screen.

**Fishing screen layout (don't break this):** the CAST/HOOK/REEL button must not move between phases, and the
screen must fit 1366x768, 1280x720 and phones without page scroll. While fishing, `.app` is exactly one viewport
tall and the scene takes the leftover height. The meter is hidden with `visibility` (never `display: none`), and the
message line, rod/bait/reward row and dots/hearts row have fixed heights. Anything new on this screen needs a fixed
size too; the `stays put in every phase` tests in `play_test.py` check it.

**Island progress** (`#isleProg`, `renderIsleProgress()`): lies over the meter + dots/hearts space (fixed 90px) and shows
"<Island>: X / 10 found" with a bar and the Mastery reward line ("★ Mastered!" when done; Little Lake: "X / 1" + Lake Guardian).
`showMeter(on)` swaps meter and progress with `visibility`; always use it instead of setting the meter's visibility directly.
It re-renders with the HUD and right after a catch.

**Bag:** sell fish one at a time or **SELL ALL** for coins (from Fishing: the SELL button beside the coins). Its only bottom button is SELL ALL; the way out is the top bar's BACK.

**Rods** (`RODS`, bought once, one equipped in `S.rodEq`; each is a clear step up in forgiveness, 1 / 2 / 3 / 5 misses, and
Master's Charm adds 1, so up to 6 hearts with the Lucky Rod):

| Rod | Price | Misses | Other |
|-----|-------|--------|-------|
| Bamboo Rod | free (starter) | 1 | – |
| Sturdy Rod | 200 | 2 | – |
| Precision Rod | 450 | 3 | green zone 35% wider |
| Lucky Rod | 700 | 5 | Shrimp-like odds boost, but marker 10% faster |

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
  `i-bag`, `i-rod`, `i-star`, `i-map`, `i-home`, `i-shop`, `i-box`, `i-bait`, `i-heart`, `i-heart0`, `i-lock`, `i-rod-<rod id>`,
  `i-bait-<bait id>` / `i-bait-none`, and the reward icons
  `i-hook`, `i-hands`, `i-lure`, `i-charm` named by `ISLANDS[id].icon`). Icon rules must come after the `.ico` rule,
  because its `background` shorthand resets `background-image`. Use `<span class="ico i-NAME"></span>` inside a button or card.
- **Rarity colours:** Common `#cfd8dc`, Rare `#64b5f6`, Epic `#ce93d8`, Legendary `#ffd54f`, Mythical `#ff80ab`.
  The Result screen reads them from `#result[data-rarity]`, Collection cards from `.cell.r-<Rarity>`.
- **Title screen:** `assets/harbor.jpg` as a full-screen `<img class="title-bg">` (fixed, `object-fit: cover`,
  pixelated, `object-position` keeps the fisherman in view; a different position below 700px). No frame. The screen is exactly
  `100dvh` tall (`100vh` fallback, no page scroll) and its padding uses `env(safe-area-inset-top / bottom)` (`viewport-fit=cover`), so the
  sign stays at least 12px from the top on iPhones, even at the top of its bob. The sign floats
  near the top and the 4 buttons sit at the bottom (2x2 on phones) over a dark gradient (`.title-shade`). The only
  effect is `.title-shimmer`, a soft blurred light band. Its fade-in is opacity-only, because a transform on the screen would
  detach the fixed picture.
- **Backdrop** (`#backdrop` in `index.html`, `.bd-*` layers in CSS, `setBackdrop()` / `preloadBackdrops()` in `js/screens.js`): one
  `position: fixed; inset: 0` layer behind `.app` (never `background-attachment: fixed`, which iOS ignores). Menu screens show
  `assets/harbor_clean.jpg` (no fisherman) with ~35% dark shade; the Fishing screen shows the current island's picture with ~55% shade.
  Layers crossfade in 300 ms (no transition with reduced motion). `cover`, `pixelated`, never blurred. Pictures load after the Title
  appears and are applied only once loaded; until then, or on failure, each layer shows its matching gradient. The body keeps only a
  fallback colour. All text must sit on solid panels/buttons (the tests check this on every screen).
- **Island scenes** (`js/fishing.js`, `SCENES`): every island is a picture: Harbor uses `assets/harbor.jpg`, the
  others `assets/<island>.png` from `tools/make_backgrounds.py` (run `pip install pillow`, then
  `python tools/make_backgrounds.py`; same output every run). Pictures are cover-cropped to the canvas; `anchor: [x, y]`
  (0-1) picks which part stays in view (new islands use `[0, .8]` so the dock in the lower-left is never cut off on wide
  screens; Harbor has none = top-left). `fisher: { x, y, scale }` (image pixels) places the drawn fisherman on the crate:
  every PNG has its dock and crate in the same spot, so all four use `{ x: 232, y: 400, scale: 6 }`. The bobber lands at
  `BOB` (canvas fractions), which is open water in every picture at every screen size. Frost also gets falling snow (`picFx`). Forest's waterfall ends in `splash_pool()` (mist + foam drawn after
  the water so it sits on the water line); the sky has no sunbeam dither.
  `preloadScenes()` starts loading the pictures after the Title screen appears; `sc.img` is set only when a picture is
  ready. Until then, or if it fails (`sc.failed`), Frost, Desert, Forest and Little Lake fall back to their painted
  scenes (pixel art painted on a small canvas, 1 art pixel = 3 screen pixels, cached; only snow, heat shimmer,
  waterfall, stars and water glints are redrawn each frame). To use an artist's picture later, replace the PNG (same
  name) and adjust `anchor` and `fisher`; `CROP` holds the part of the picture currently shown.
- **Town Map** (`renderMap()`): the 4 islands are equal cards in one row on wide windows (2x2 below 900px; about 250px wide on
  desktop). Each card is the island picture with a dark progress plate at the bottom (`.isl-plate`): name + gold star (`i-star`) when
  mastered, a bar with "x / 10" (gold when mastered) and the reward name with its icon (padlock until mastered). The secret island is a
  separate wide strip below (`.secret-strip`): locked = padlock, "???", "Master all 4 islands to unlock" and "x / 4 mastered" on its
  dark night gradient (no picture, no moon); unlocked = `secret.png`, "Little Lake" and "x / 1 found". HOME is a small button at the right
  end of the panel header (no button row below the panel).
  Every card shows only the place (no figure). Harbor uses `assets/harbor_clean.jpg` (the photo after `cleanPlate()`, made by
  `tools/make_harbor_clean.py`) with `harbor.jpg` behind it as the fallback layer; the Title screen keeps `harbor.jpg` with its
  fisherman as cover art. `.bg-<island>` = `--card-shade`, the island picture (`cover`, positioned on its best part), then the old
  gradient as a fallback if the picture can't load.
- **Fisherman** (`js/fisherman.js`, `SCENES.<island>.fisher`; on Harbor): the man baked into `harbor.jpg` is hidden by
  `cleanPlate()`, which copies water, chest and dock pixels from beside him (`patch` rects and the `rodClear` band, in
  photo pixels) into an offscreen canvas built once. A new 28x36 pixel-art fisherman is drawn at `x, y` with `scale`
  photo pixels per art pixel. Body frames are cached canvases; the rod is a curve of art-pixel blocks drawn each frame,
  and the line starts at its drawn tip (`ROD_TIP` is updated from it). Poses: idle (breathing), casting (wind-up, swing),
  waiting (head tilt, tip dips with the bobber), bite (startled), reeling (rod bent; `fisherTug()` = tug on a hit,
  slack wobble on a miss), caught (700 ms) and escaped (1.4 s). With reduced motion each pose is one still frame.
  A scene without `fisher` draws no figure. Don't allocate objects per frame in this code.
- **Fisherman outfits** (`OUTFITS` in `js/fisherman.js`, picked by `SCENES[island].fisher.outfit`, passed in `cfg.outfit`): each has its
  own palette, head/body/legs maps and arm colours (`arm` = sleeve, sleeve highlight, forearm, hand, hand shade as palette letters;
  optional `front` = a small map drawn over the arm, e.g. the Little Lake lantern). Maps must keep the grids (head 22x15, body
  18x16, legs 28x11) so the size, hands and rod tip match in every pose; frames are cached per outfit. Harbor: straw hat, blue
  shirt. Frost: red parka, fur hood, yellow scarf/mittens, white boots. Desert: wide sun hat, sleeveless shirt, khaki shorts,
  sandals. Forest: green explorer cap with a feather, olive vest, cream shirt. Little Lake: purple cloak, cyan trim, lantern.
  Check new outfits on `shots/outfits_contact.png` (written by the tests: 5 outfits x 7 poses).
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
python -m playwright install webkit     # optional: iPhone-profile Title checks (skipped with a NOTE if WebKit is missing)
python play_test.py
```

The tests don't need Pillow; only `tools/make_backgrounds.py` does. The script opens `index.html` over `file://` at 1280×800 and 360×780 and prints PASS/FAIL for each check.
It writes screenshots to `shots/` and a summary to `results.json` (both are git-ignored).
All checks must pass before committing.
