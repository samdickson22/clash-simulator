# LIVE loop: handoff (self-contained)

Written by `live-loop-owner-r1` (Opus) on 2026-10-16 for the next owner of the live ladder loop (babysitting: run
battle sessions, keep the logs and inventory current, swap perception exports). Parent: **LIVE LEAD**
(`clasher-live-lead-20261014-r1`). Code changes go back to an Opus worker through the LIVE LEAD.

## 1. What this is

A Clash Royale bot plays **ranked ladder battles in the official client** in BlueStacks Air on the Mac mini, on a
throwaway account **bigdiddle**:

```
ScreenCaptureKit window capture → canvas mapping → LivePerception → readers (elixir bar, tower HP digits)
  → LiveSession(LivePlayer K4L, RL r5 v10 fallback) → ADB taps in the Android guest
```

Results table: `reports/live/loop/RESULTS.md`. Log: `PROGRESS.md`.

## 2. Current state (2026-10-16 ~00:45Z)

- **Trophies and arena:** ~391+, Arena 2 Bone Pit (sand). Record through s6-m01: 16 W – 5 L. 2 of the losses were
  driver incidents: s2-m02 and s4-m01, the dim screen.
- **Live session:** `s8`, driver PID 45077, `--matches 4 --autonav`, perception r5e3 (s7 finished its 4 battles
  unattended; s8 was started by `scratch/live-loop/chain.sh 773 s8`). Video up to s7 is on 05 `runs/` and pruned on
  the Mac (14 GiB free).
- **Perception live:** r3 ft-r5 final, `export-interim-r5e3`:
  - frame.pt `81697f5b1be73e97…`, event.pt `638276a0…`, vocab `d39b06bb…`; threshold .5 (defaults).
  - On the Mac: `~/clasher-live/perc-exports/interim-r5e3/`. On 05: `/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3/`.
- **Rollback, r1:** `~/clasher-live/clasher-live-macbench/data/perc-export` (frame.pt `20f77a71…`). This is also
  the run.sh default if `--export` is omitted.
- **Bot:** `LIVE-K4L-R-gs-rw-fc-w200-t4-p4` with `CLASHER_LIVE_FAST=student:~/clasher-live/students-live/rl5-v10/policy-00010.pt@0.5375`
  (sha `e188e2ae…`). Rollback for the fast tier: it5s2 in `~/clasher-live/clasher-live-macbench/students/`.
- **Deck:** Knight, Archers, Minions, Arrows, Fireball, Giant, MiniPekka, Musketeer. Set from the control page (§4.4),
  saved in `~/clasher-live/loop/deck.json`; `drive.py` `DECK` is only the default. A deck change in the game must be
  applied on the page (Read deck from screen → Apply), or the bot holds wrong cards.
- **Screen:** the BlueStacks output has been **dimmed** since ~01:00Z, cause unknown (white level ~178 instead of
  255; Sam: "if the bot can see good it's fine"). The driver normalizes brightness, so this is OK.

## 3. Paths

| what | where |
|---|---|
| Driver code (repo) | `live/loop/` (`drive.py`, `canvas.py`, `towers.py`, `overlay.py`, `frames.py`, `battlelog.py`, `pocket.py`, `reconstruct.py`, `report_run.py`), `live/loop/mac/` (`bsgrab.swift`, `bsclick.swift` (unused), `run.sh` copy), `live/loop/ops/` (05 helpers) |
| Card templates (NOT in git) | `live/loop/cards/<Card>/*.png`, `cards/_header_digits.npz` |
| Mac code tree the driver runs | `~/clasher-live/loop/code/15117b86b-w1/` (the repo at 15117b86b + the bench bundle's `reports/` subset). **Deploy changed files with rsync into this tree** |
| Mac launcher | `~/clasher-live/loop/run.sh <name> <drive.py args>` (sets PYTHONPATH, pins, fast tier, lopp models) |
| Mac runs | `~/clasher-live/loop/runs/<session>/mNN/` (`frames, decisions, taps, events, perception .jsonl`, `session-config.json`, `session.json`, `video/*.jpg`), `bsgrab.stderr` per session |
| Mac logs | `~/clasher-live/loop/logs/<session>.log` |
| Arena backgrounds (perception r3 asked for these) | Mac `~/clasher-live/loop/arena-bgs/<arena>/`, 05 `/mpac/sdicks02/scratch/live-loop/arena-bgs/` |
| 05 scratch | `/mpac/sdicks02/scratch/live-loop/`: `runs/` (full copies with video), `runs-all/<run>/` (logs, video-free; the bot lead reads these), `shots/`, `bl2/` (Battle Log pages), `venv/` (cv2, torch-cpu, scipy), `pydeps/` |
| 05 python for bot code | `/mpac/sdicks02/repos/clasher-bot/.venv/bin/python` with `PYTHONPATH=…/pydeps` (cv2, scipy) |
| Inventory | `reports/live/loop/opponent-decks.jsonl`, `opponent-cards-non-c56.json` |
| Pocket moments | `reports/live/loop/pocket-moments.jsonl` |
| Overlay (what the bot sees) | Mac `http://localhost:8765` (MJPEG; also `ops/ovpeek.sh <name>` from 05) |

## 4. Per-battle routine (sessions)

### 4.1 Start a session (3–4 battles in one driver)

```sh
ssh macmini-fleet '(nohup ~/clasher-live/loop/run.sh s8 --tap adb --autonav --matches 4 --seconds 3600 \
   --arena bone-pit --export $HOME/clasher-live/perc-exports/interim-r5e3 \
   > ~/clasher-live/loop/logs/s8.log 2>&1 < /dev/null & echo DRV_PID=$!)'
```

- **Write down `DRV_PID`.** It's the only PID you may stop.
- **Waiting for the battle:** the driver loads in ~8 s and then waits for the battle HUD.
- **`--autonav`** taps **only** these:
  - OK on the result screen (705, 1740);
  - OK on the trophy road (540, 1845);
  - Battle on home (550, 1489).
- **Unknown screens** (rewards, chests, "Choose" rewards, popups, Sam in menus) get **no tap**. After 60 s the
  driver logs `nav_stuck`; then look (`ops/gshot.sh name`) and clear the screen by hand with single
  `ops/tap.sh x y` taps on close/OK buttons.
- **Start/end:** each battle starts when the HUD (elixir drop) is seen on 3 frames, which anchors the clock. It ends
  when the HUD has been gone for 3 s; the next battle gets fresh logs in `mNN+1/`.
- **Session end:** after `--matches` battles or `--seconds`.

### 4.2 Check during a battle

- **Status:** `ssh macmini-fleet 'grep -E "match_|nav_|step_error" ~/clasher-live/loop/runs/s8/m0*/events.jsonl'`.
- **Look:** use `ops/ovpeek.sh name` (the overlay stream). **Do not take macOS screenshots during battles**: a
  second ScreenCaptureKit client interrupts the main stream (SCK -3805; the driver restarts it in <1 s, but you lose
  frames). Guest screenshots via adb (`ops/gshot.sh`) do not touch SCK, but avoid them mid-battle too.

### 4.3 After each session, or each battle when convenient

1. **Copy runs to 05:** `rsync -a macmini-fleet:clasher-live/loop/runs/s8/ /mpac/sdicks02/scratch/live-loop/runs/s8/`
   (full), and `rsync -a --exclude video macmini-fleet:clasher-live/loop/runs/s8/mNN/ …/runs-all/s8-mNN/`.
2. **Summary row:** `venv/bin/python live/loop/report_run.py runs-all/s8-mNN --json` gives FPS, latencies, plays,
   confirmed plays, step errors and restarts. Add a row to the RESULTS.md battle table, with the **perception column**
   (`r1` / `r5e3` / …; the export sha is in `events.jsonl` `loaded`).
3. **Battle Log inventory** (CARD LEAD priority):
   - In the client: Battle tab → ☰ (929, 253) → Battle Log (610, 188).
   - Then on 05:
     ```sh
     cd /mpac/sdicks02/scratch/live-loop
     venv/bin/python $R/live/loop/battlelog.py capture blN --pages 16    # list must be at the top
     venv/bin/python $R/live/loop/battlelog.py extract blN
     venv/bin/python $R/live/loop/battlelog.py label blN --templates $R/live/loop/cards
     #   unknown cards -> blN/unknown/cNN/: look, name, copy one crop to $R/live/loop/cards/<Card>/, re-run label
     venv/bin/python $R/live/loop/battlelog.py decks blN --templates $R/live/loop/cards --runs runs-map.json \
        --out $R/reports/live/loop/opponent-decks.jsonl
     ```
   - Add each new battle to `runs-map.json` (`"<our trophies before>:<W|L>": {"run", "arena"}`).
   - The log keeps ~25 battles, so do this at least every ~20 battles.
   - Close the log with its X (1010, 222).
   - If a new header digit misreads, rebuild `_header_digits.npz` with `build_header_digits` (see the code).
   - Card names: use the CR internal names as in the vocab (`SpearGoblins`, `GoblinCage`, `Tombstone`, `Bomber`, …).
     `opp_non_c56` uses the C56 set in `battlelog.py`.
4. **Pocket moments:** `venv/bin/python $R/live/loop/pocket.py runs-all --out $R/reports/live/loop/pocket-moments.jsonl`.
   It prints per-stretch counts. Compare the r1 and r5e3 rows (see §7).
5. **Tell the LIVE LEAD** the new rows, results and anything odd.

### 4.4 Control page (Sam): pause, resume, deck

`http://localhost:8765` on the Mac (the overlay) has buttons:

- **Pause bot / Resume bot:**
  - Paused, the bot makes **no taps at all**: no plays, no autonav.
  - A battle in progress is then not played by the bot.
  - Events `paused_by_user` / `resumed_by_user` (with reason page / file / deck_out_of_scope) go into `events.jsonl`;
    count them in RESULTS.
  - The file `~/clasher-live/loop/PAUSE` has the same effect (for a babysitter): `touch` it to pause, `rm` it to resume.
- **Read deck from screen:**
  - With the in-game **Cards → Decks → Battle Deck** page open, it recognizes the 8 cards with the card templates
    (`deckread.py`) and fills the deck box.
  - Unrecognized slots are reported, and their crops saved to `<run>/deck-unknown/` (label them into `cards/<Card>/`).
  - Cards outside C56 (`battlelog.C56`) are flagged **OUT OF SCOPE**.
- **Apply deck:**
  - Records the 8 names. They're used from the next battle (a new LiveSession), and saved to `~/clasher-live/loop/deck.json`,
    which later sessions start with.
  - `session-config.json` has `deck` and `deck_out_of_scope`.
  - **A deck with any out-of-scope card blocks battles:** the driver stays paused and the page shows BLOCKED until a
    C56-only deck is applied. This holds until the CARD LEAD's proxies land.
- **Sam's routine:** Pause → upgrade or change the deck in the game → stay on Battle Deck → Read deck from screen →
  Apply deck → Resume.
- **Test:** `live/loop/tests/control_test.sh` runs on 05, no Mac: the live path with a fake bsgrab streaming real
  screenshots and a fake adb with real dumpsys output; 18 checks.

## 5. Swap a perception export (and roll back)

1. Copy the export to the Mac:
   `ssh macmini-fleet 'mkdir -p ~/clasher-live/perc-exports/<name>'; scp <05 export>/{frame.pt,event.pt,vocab.json} macmini-fleet:clasher-live/perc-exports/<name>/`
2. Check: `ssh macmini-fleet 'shasum -a 256 ~/clasher-live/perc-exports/<name>/*'` must equal the hashes in the
   perception owner's message.
3. Quick offline replay on 05 of one recorded Bone Pit battle, units per frame vs the current export:
   `venv/bin/python cmp_perc.py runs/s2m01` (edit the two export paths in it). Expect more units, not fewer, and no
   errors.
4. At a **session boundary**, start the next session with `--export $HOME/clasher-live/perc-exports/<name>`.
   `events.jsonl` (`loaded`) and `session-config.json` record the export sha per battle.
5. **Rollback:** start the next session with the previous export path. r1 is the bundle default.
6. **Interface rule:** `LivePerception(export_dir)`, `step(bgr_540x1140, ts_ms)`, and the record schema must stay the
   same. Additive keys (e.g. ft-r6 `unknown_units`) are ignored by the driver until code uses them.

## 6. Stop or restart the driver safely

- **Stop:** only by the recorded PID: `ssh macmini-fleet 'kill -TERM <DRV_PID>; sleep 3; ps -p <DRV_PID> >/dev/null && echo STILL || echo STOPPED'`.
  The driver closes its bsgrab child and the adb shell itself. **Never `pkill -f`.**
- **Restart only between battles.** Mid-battle restarts lose the clock anchor; the bot then plays with a wrong
  elixir/phase model for that battle.
- **Gotchas:**
  - **ssh exit status:** `ssh macmini-fleet` always exits 0. Check output tokens (`echo LOADED`, `__RC=$?`), never
    the exit status.
  - **CGEvents** posted from ssh go to the **console session** (simonfarshid's locked screen), not Sam's session. That
    is why input is ADB, not `bsclick`.
  - **SCK:** see §4.2. One capture client only.
  - **Dimmed screen:** handled by normalization (`drive.normalize`).
    - Frames darker than 80% of the battle's own brightness, or black, **pause** the driver: no decisions, no taps.
    - Princess towers die only after 60 healthy frames with no number.
    - If the overlay says `PAUSED`, look at the screen.
  - **BlueStacks Prime ad window:** a second BlueStacks window, layer 3, over the game (Sam: an ad). Harmless.
  - **Tower OCR:** reads the drawn numbers with templates; on a new arena check the overlay's tower numbers early. A
    false low king HP made the bot spell a full-HP king once (fixed).
  - **Deck change:** see §2.

## 7. Open items

1. **Pocket play** (bot lead):
   - Past-bridge vs defensive plays after we take a tower, r1 vs r5e3. Through s6-m01: r1 29/100 plays in the pocket,
     r5e3 7/29.
   - Keep adding r5e3 battles.
   - Decision states for replay: `perception.jsonl` + `session-config.json` (live-logged from s6). Earlier runs are
     reconstructed (`logged='reconstructed'`, `live/loop/reconstruct.py`; run with 05's 4×8 cores, script
     `scratch/live-loop/recon_all.sh`).
2. **Inventory:** keep `opponent-decks.jsonl` current, and re-run `decks` after each session.
3. **Overlay naming:** done ("Skeleton (SkeletonArmy)"), display only.
4. **Not committed yet:** drive.py, overlay.py, towers.py, bsgrab.swift, pocket.py, reconstruct.py, report_run.py
   changes. The LIVE LEAD commits when told they are stable. `cards/` and all images stay out of git.
5. **Coming from other owners:**
   - ft-r6 perception (adds `unknown_units`, ~05:30Z);
   - non-C56 cards in the engine (CARD LEAD);
   - the multi-body play-count check;
   - translator placeholders.
   All of them need code changes (Opus).

## 8. Rules

- **Mac:**
  - Write only under `~/clasher-live/`. Input is ADB through **our** adb server on port **5047** only (serial
    `127.0.0.1:5555`).
  - Never touch other users, the UTM VM, Codex or Chrome, `~/Desktop/code/*`, `~/.cache/clasher-native-reference`,
    or the adb servers on 5042–5044.
  - No `pkill -f`; kill only PIDs you started.
  - Free disk is ~13 GiB; the driver stops below 6 GiB. Prune old `runs/*/video` on the Mac after copying them to 05.
- **In-game** (Sam: full authority on the throwaway account):
  - ladder battles, gold/gems, chests, deck changes and menus are OK;
  - **never** real-money purchases (anything that opens a Google Play payment sheet), never type credentials or
    sign in, never modify the client or emulator to hide the bot;
  - **stay out of menus while Sam is using them** (he upgrades cards and changes the deck himself).
- **Repo:**
  - **no opponent player names, no screenshots or video in git**;
  - `opponent-decks.jsonl` has no names;
  - don't commit: the LIVE LEAD commits.
- **Reporting:** the LIVE LEAD is your parent. Perception exports arrive from `live-perc-r3-owner-r1` (or its
  successor) via the LIVE LEAD. Report W/L per battle, the perception export, and anything that needed manual
  intervention.
