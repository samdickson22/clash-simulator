# LIVE step C: bot-side glue, results (exploration tier)

Owner: the step C sub-agent (`live-glueC-owner-r1`), on 127x05, 2026-10-14. Code is in `bot/live/`; the log is in
[PROGRESS.md](PROGRESS.md). Nothing is committed. All 05 runs used ≤4 cores at nice 19.

## TL;DR

- **The bot side of the live loop exists and is tested.** 21 tests pass. It is `LiveSession(LivePlayer(...))`, fed perception schema v1 `frame_record`s, and it returns `slot*576 + row*18 + col` or WAIT, plus per-decision stats.
  - **Search tier:** K4C-r16 under a wall deadline with 1–4 threads; it5s2 is the cutoff default and the error fallback.
  - **Fast tier:** pure it5s2.
  - Without a deadline it is exactly K4C-r16 (identical command hash).
- **Deadline:** p99 equals the budget.
  - On real-client states: w200-t4 defaults to it5s2 on 5.6% of decisions, w150-t4 on 20%, w120-t4 on 23%.
  - Unbounded K4C on 1 core has p95 0.71 s, so live play needs the wall tier. it5s2 takes 14 ms.
- **Perception cost, as agreement with the bot on the true state** (K4C, our engine; its own reseed floor is 0.79 exact):
  - perfect units, plays derived from births: 0.72;
  - the current baseline perception (R .42 / P .95, hand 2%, elixir sd .1): 0.57.
  - it5s2: 0.96 → 0.83.
  - The biggest lever is **play/spell detection**. Births recover about 77% of opponent plays, and missed spells make about 37% of those unusable for the cycle trackers. Recall and elixir accuracy come next.
- **Deadline validation needs the bot lead.** The exact paired HEADLINE command is in §4: K4CW w200/w150/w120 vs the existing K4C-r16 dirs on 03, 1,800 games per engine, about 2.1 h on 60 cores. It was not run.
- **Mac:** build the native from the runtime root's `engine-rs`, pass the parity fixture (already made and self-checked on Linux), then register a `mac-r1` pin set via `bot/live/mac_pins.py`. Footprint: about 120 MB of files, 1.0 GB RSS.

## 1. What exists

| file | what |
|---|---|
| `bot/live/player.py` | `WallCandidatePlayer` (`K4CW-r16[-w<ms>-t<threads>]`): K4C-r16 with SearchPlayer's wall cutoff (8 ms reserve) and 1/2/4 scoring threads through the frozen K kernel. `LivePlayer` (`LIVE-K4CW-…`, `LIVE-fast-it5s2`): it5s2 polls every 5 ticks; search decides on 10-tick multiples with it5s2 as its cutoff default; a search error means it5s2 acts; 3 consecutive failed decisions disable search for the match. `LiveBelief`: an off-prior opponent deck rebuilds the prior instead of raising. |
| `bot/live/translate.py` | `LiveTranslator`: perception record → `fair_player.Information`, built through `royalesim_translate.Translator.observation`. `LiveSession`: the live loop's bot side (poll cadence, buffered events, CommandQueue reservation, completion of the pending command from the HUD). |
| `bot/live/levels.py` | `LevelRoot`: the frozen `Resources.root` plus per-owner level scaling of board bodies and towers. |
| `bot/live/synth.py`, `bot/live/replay.py` | Synthetic perception (perfect or noisy) and the oracle replay harness (engine and T1 sources). |
| `bot/live/headline_wall.py` | `bot.eval.headline` with core-group pinning for wall arms (§4). |
| `bot/live/native_parity.py` | Linux→Mac native parity fixture (§5). |
| `bot/live/births.py` | Card-level perception → bodies, tracks, plays derived from births; HUD clock → tick. |
| `bot/live/perc.py` | `PERC-<arm>:<player>`: play the true game through synthetic perception at a noise arm (win-rate cost). |
| `bot/live/mac_pins.py`, `runtime_manifest.py`, `summarize.py` | Mac pin sets, the runtime file manifest, the RESULTS tables. |
| `bot/live/test_live.py` | 21 tests, all passing on 05, plus 1 that is skipped until real perception records exist. |

### Using it in the live loop

```python
from bot.players.runtime import Runtime            # Mac: import bot.live.mac_pins; bot.live.mac_pins.register() first
from bot.live.player import LivePlayer
from bot.live.levels import Levels
from bot.live.translate import LiveSession
rt = Runtime()                                       # ~15 s, before the match
bot = LivePlayer(rt, tier='search', wall_ms=150, threads=4,          # or tier='fast' (it5s2 only)
                 levels=Levels(own=1, opp=1, own_tower=1, opp_tower=1))   # real levels if known; default all 11
s = LiveSession(rt, bot, own_deck=[...8 C56 cards...], seed=<any int>, command_delay=38)
for image, ts in capture():
    d = s.step(perception.step(image, ts))           # frame_record dict; returns a Decision on 5-tick polls
    if d is not None and d.action < 2304:
        slot, tile = divmod(d.action, 576); row, col = divmod(tile, 18)
        tap_card(slot); tap_tile(x=col + .5, y=row + .5)            # our frame: y from OUR edge (perception frame)
```

- **Coordinates.** Actions are in the perception record's frame: x from the screen left, y from the bottom. The screen point is native y = 32 − y, the inverse of `own_view`.
- **Pending command.** `LiveSession` reserves the slot and elixir until the HUD shows the card has left its slot. It then emits our own play event, which the opponent-cycle and D1 trackers need.
- **Ticks.** The tick comes from the HUD clock, phase and timestamp. Decisions happen every 5 ticks from tick 90; search runs on multiples of 10.
- **Per-decision stats** are in `d.stats`: source, wall/cpu ms, hit, completed, candidates, it5s2's action, belief rebuilds, errors.

### Facts the tests pin down

- **No change at no deadline.** `K4CW-r16` (no deadline) has a command hash identical to `K4C-r16`.
- **Fast tier.** `LIVE-fast-it5s2` has a hash identical to `student:it5s2-step001200.pt@0.5375`. The it5s2 sha (08bdaf32…) is asserted at load.
- **Deadline.**
  - `LIVE-K4CW-r16-w120-t4`: median decision under 120 ms and every decision under 160 ms (05, 5 cores).
  - In the first smoke, w200-t4 peaked at 192 ms with 0 overrun ticks.
- **Translator vs our engine's true view.** A perfect record reproduces the v5 packet exactly over 1,500-tick games: globals, hand ids, enemy history, ages, seen cards, and every troop and building row (token, x, y, HP). It differs in two places:
  - **Unit facing** (cols 27/28). Perception has none, so it is estimated by frame-to-frame tracking.
  - **Spell and projectile rows**, which are not in the perception schema. That means in-flight Fireballs, the Log, and tower and unit shots are absent from the planner root.
- **Fair-information invariance.** Opponent-private keys in a record change nothing. The T1 source reads only our own seat's HUD; poisoning the opponent's record changes nothing.
- **T1 guard.** Every data dir must be registered as `train` or `validation` in `t1-split.json`, or the run aborts. A heldout episode dir makes it abort; heldout data is never opened.
- **Belief.** A deck far off the prior (Golem/Xbow/Rocket/…) no longer raises; the prior is rebuilt as human decks completed with the revealed cards.
- **Levels.** At level 11 everywhere the payload is byte-identical to `Resources.root`. At other levels, HP and damage scale by the game's level table.

### Perception schema v1 (`live/perception/common.py:frame_record`, final per the LIVE LEAD 2026-10-14)

`LiveTranslator` reads the schema directly; a test builds a record with the perception owner's own `frame_record()` and translates it.

- **Units are reported by spawning card** (`cls`/`card`). `bot/live/births.py:CardBodies` maps card → our body tokens from the frozen engine config: the card's units plus its production and death children, using the builder's own tokens.
- **`UnitTracker`** keeps tracks per (card, owner) across missed detections (`ttl` 40 ticks; buildings 400; expired tracks are remembered for 200 ticks). A new track picks its body:
  - a live spawner building of that card → its child (GoblinHut, FirespiritHut);
  - a main body that just vanished nearby → its death child (Golem → Golemite);
  - otherwise a main body (multi-body cards fill their composition).
  - Facing comes from track motion.
- **There are no play events, so opponent plays come from births.** A main-body birth that starts a new cluster (4 tiles / 40 ticks) is a play at the first sighting, if:
  - it is seen a second time within 20 ticks (a one-frame mislabel is not a play);
  - it is in the opponent's zone (y ≥ 15; Miner/GoblinBarrel anywhere; y ≥ 9 on a side whose princess tower we lost).
- **Our own plays** come from our own commands: `LiveSession` emits them when the HUD shows the reserved card left its slot.
- **Tick.** `ClockTracker` turns the HUD clock + elixir phase + `timestamp_ms` into a tick, using the collector convention: clock 180→0, then overtime 120→0; phase 2 with clock > 60, or phase 3, means overtime. Error ≤ 3 ticks on a synthetic 6,000-tick sweep.
- **Known gaps:**
  - **Spells are unseen.** The opponent's spell plays never reach the bot: opponent elixir is over-estimated and its cycle drifts.
  - Missed spells also make some later unit plays look impossible to the cycle trackers. The stream guard drops those plays rather than let the trackers raise; in the engine replay that was about 9 per game.
  - A confirmed play is reported up to one record late (its tick is floored to the previous record, because the belief cannot go back in time).

### Policies to know before going live

- **Non-C56 cards** (Spear Goblins, Goblin Cage, …) are dropped from the bot's public streams by default, which over-estimates opponent elixir by the card's cost. `unknown_card='proxy'` substitutes a same-cost C56 card instead (the table is `translate.PROXY`). Own non-C56 hand cards become empty slots: **the live deck must be all C56** (for example Knight, Archers, Giant, Musketeer, MiniPekka, Fireball, Arrows, Goblins).
- **More than 8 distinct enemy cards** (a perception error) means the 9th card's plays are dropped.
- **Late events** (perception sees a play late) are retimed to the previous record's tick, so the belief never goes backwards.
- **Levels.** Only bodies on the board are scaled. Cards played inside rollouts spawn at level 11 for both sides, which needs an engine change to fix. The nets always see level 11.
- **Command lag.** `LiveSession(command_delay=…)` is the planner's lag. It defaults to 27; the PLAN estimates about 38 for the live stack, to be recalibrated from measured tap→deploy.
- **Pending command.** It is completed when the HUD shows the reserved card left its slot, or our own play event arrives. It expires after 90 ticks.

## 2. Oracle replay: agreement with the bot on the TRUE state, by perception level

### Setup

- **Source (`bot.live.replay --source engine`).** Full games in our engine (X4S loop, opponent v1, fresh cases: base `HEADLINE_BASE + 10^6`). The bot sits in seat 0 and is fed the true public view, so it decides exactly as evaluated.
- **Shadows.** At every poll, each "shadow" gets a perception record synthesised from that true view (`bot/live/synth.py`, schema v1, card-level). Each shadow translates the record and decides with its own LivePlayer: same tier, same seeds, same pending own command.
- **Agreement** is measured on the truth's decisions. "exact" means the same action id, WAIT included. "truth plays" covers the decisions where the truth played: exact action, same card, and same card within 2 tiles.
- **Arms:**
  - `events`: perfect units plus every play event, i.e. the upper bound with a perfect temporal head;
  - `births`: perfect units, opponent plays derived from unit births, spells unseen;
  - `p70` / `p42`: the LIVE LEAD's perception numbers. Unit recall 0.70 / 0.42, precision 0.95 (a confused identity is replaced by another unit card), position sd 0.3 tile, unit HP sd 0.05, tower HP sd 0.03, hand error 2% per slot, elixir sd 0.1, no events. Detections are independent per frame (flicker), the pessimistic case for tracking;
  - `r42-only`: recall 0.42 alone;
  - `hud-only`: hand + elixir + tower noise alone;
  - `reseed`: `events` input with the search and poll seeds shifted by 7. This is **the bot's own noise floor**: what changes with no information change at all.

### it5s2 (fast tier), 12 games, 6,419 decisions

| arm | decisions | exact | 95% CI | play/wait same | truth plays: exact | same card | card+<=2 tiles | truth WAITs kept | shadow plays when truth waits | errors |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| events | 6419 | 0.986 | [0.983, 0.989] | 0.993 | 0.873 (n=450) | 0.947 | 0.916 | 0.995 | 30 | 0 |
| births | 6419 | 0.960 | [0.955, 0.965] | 0.973 | 0.742 (n=450) | 0.889 | 0.813 | 0.976 | 142 | 0 |
| p70 | 6419 | 0.881 | [0.873, 0.889] | 0.905 | 0.389 (n=450) | 0.638 | 0.480 | 0.918 | 488 | 0 |
| p42 | 6419 | 0.833 | [0.824, 0.842] | 0.865 | 0.264 (n=450) | 0.604 | 0.369 | 0.876 | 739 | 0 |
| r42-only | 6419 | 0.857 | [0.849, 0.866] | 0.890 | 0.351 (n=450) | 0.736 | 0.460 | 0.895 | 624 | 0 |
| hud-only | 6419 | 0.931 | [0.925, 0.937] | 0.944 | 0.602 (n=450) | 0.736 | 0.669 | 0.956 | 264 | 0 |
| reseed | 6419 | 0.986 | [0.983, 0.989] | 0.993 | 0.873 (n=450) | 0.947 | 0.916 | 0.995 | 30 | 0 |

12 games/matches

### K4C-r16 (search tier, unbounded, deterministic), 9 games, 1,023 decisions

| arm | decisions | exact | 95% CI | play/wait same | truth plays: exact | same card | card+<=2 tiles | truth WAITs kept | shadow plays when truth waits | errors |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| events | 1023 | 0.936 | [0.922, 0.951] | 0.974 | 0.865 (n=355) | 0.949 | 0.890 | 0.975 | 17 | 0 |
| births | 1023 | 0.718 | [0.691, 0.747] | 0.857 | 0.397 (n=355) | 0.707 | 0.496 | 0.889 | 74 | 0 |
| p70 | 1023 | 0.584 | [0.553, 0.615] | 0.786 | 0.132 (n=355) | 0.544 | 0.239 | 0.823 | 118 | 0 |
| p42 | 1023 | 0.567 | [0.539, 0.597] | 0.763 | 0.079 (n=355) | 0.507 | 0.214 | 0.826 | 116 | 0 |
| r42-only | 1023 | 0.587 | [0.558, 0.619] | 0.784 | 0.149 (n=355) | 0.572 | 0.239 | 0.820 | 120 | 0 |
| hud-only | 1023 | 0.672 | [0.644, 0.701] | 0.834 | 0.301 (n=355) | 0.673 | 0.408 | 0.868 | 88 | 0 |
| reseed | 1023 | 0.790 | [0.765, 0.814] | 0.938 | 0.504 (n=355) | 0.831 | 0.620 | 0.942 | 39 | 0 |

9 games/matches

### Reading

- **The translator itself is lossless where the schema allows.** `events` matches the true state's decisions 98.6% (it5s2) and 93.6% (K4C). The residual comes from:
  - unit facing (estimated);
  - in-flight spell and projectile rows, which are not in the schema.
- **K4C's own floor is low.** With identical information and another seed, K4C repeats its exact play on only 50% of truth plays (same card 83%). So read the search columns against `reseed` (0.79 exact), not 1.0.
- **Deriving plays from births (spells unseen) is the largest single loss for K4C:** 0.72 exact vs 0.79 floor; same card on plays 0.71 vs 0.83.
  - In the 9 search games, births recovered 212 of 276 opponent plays; most of the rest are spells.
  - The cycle guard then had to drop 79 of those 212, because earlier missed spells make the play impossible for the frozen D1 and belief trackers.
  - Only about 48% of opponent plays reach the bot's elixir and cycle tracking.
  - **Spell (or play-event) detection is the highest-value perception addition after unit recall.**
- **The baseline perception (`p42`) costs a lot more.**
  - K4C: 0.57 exact; same card on truth plays 0.51; 116 plays where the truth waited.
  - it5s2: 0.83 exact; truth plays exact 0.26.
  - Recall alone (`r42-only`) accounts for most of it. `p70` is only slightly better for K4C (0.58).
  - The HUD noise alone (`hud-only`: elixir sd 0.1, hand 2%) is surprisingly costly: K4C 0.67, it5s2 0.93. The play gate is sensitive to elixir.
- **What this does NOT say: win rate.** Agreement under noise is a proxy. A different action is not necessarily a worse one; K4C's `reseed` floor shows how many near-ties exist.
  - The direct measure is a perception-noise arm in HEADLINE, i.e. the bot playing through this translator + noise in our engine. The harness can do that with a small Player wrapper; it is not run here.

### T1 recorded official-client states (train/validation split only), it5s2, 8 matches, 3,010 decisions

**Source.** `--source t1`: 8 matches drawn from the 577 train/validation dirs. The guard checks every dir against `t1-split.json` and opens no heldout data. The bot plays our seat (alternating 0/1); the recorded side's own plays are not ours.

**The perfect record:**
- every hit-point object, labelled with its spawning card (`card_id`, the same identity the perception's dense labels use);
- towers by anchor;
- our own HUD only, from `evaluation-only`;
- accepted plays from `events.jsonl`.

**Reference.** The `events` arm, i.e. the bot on the perfect record. The T1 source has no engine-truth bot.

**Caveat.** The recordings start mid-match (`start_tick` 340–2400), so the trackers start late. Our opening order is a guess, which causes a few own-side cycle drops; the same guess is used in every arm.

| arm | decisions | exact | 95% CI | play/wait same | truth plays: exact | same card | card+<=2 tiles | truth WAITs kept | shadow plays when truth waits | errors |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| events | 3010 | 1.000 | [1.000, 1.000] | 1.000 | 1.000 (n=680) | 1.000 | 1.000 | 1.000 | 0 | 0 |
| births | 3010 | 0.929 | [0.920, 0.938] | 0.968 | 0.803 (n=680) | 0.944 | 0.888 | 0.966 | 79 | 0 |
| p70 | 3010 | 0.826 | [0.812, 0.839] | 0.925 | 0.421 (n=680) | 0.757 | 0.584 | 0.944 | 130 | 0 |
| p42 | 3010 | 0.786 | [0.771, 0.801] | 0.908 | 0.299 (n=680) | 0.699 | 0.447 | 0.929 | 166 | 0 |
| r42-only | 3010 | 0.815 | [0.800, 0.829] | 0.930 | 0.359 (n=680) | 0.771 | 0.510 | 0.948 | 121 | 0 |
| hud-only | 3010 | 0.905 | [0.894, 0.915] | 0.949 | 0.744 (n=680) | 0.890 | 0.828 | 0.952 | 113 | 0 |
| reseed | 3010 | 1.000 | [1.000, 1.000] | 1.000 | 1.000 (n=680) | 1.000 | 1.000 | 1.000 | 0 | 0 |

8 games/matches

**Reading.** On real-client states the it5s2 picture matches the engine one: births 0.93, p70 0.83, p42 0.79, hud-only 0.91. It is slightly better than in the engine because these matches have more plays per decision.

### T1, K4C-r16 (unbounded), 2 matches, 654 decisions

| arm | decisions | exact | 95% CI | play/wait same | truth plays: exact | same card | card+<=2 tiles | truth WAITs kept | shadow plays when truth waits | errors |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| events | 654 | 1.000 | [1.000, 1.000] | 1.000 | 1.000 (n=119) | 1.000 | 1.000 | 1.000 | 0 | 0 |
| births | 654 | 0.859 | [0.833, 0.885] | 0.936 | 0.420 (n=119) | 0.790 | 0.521 | 0.957 | 23 | 0 |
| p70 | 654 | 0.791 | [0.760, 0.823] | 0.891 | 0.160 (n=119) | 0.580 | 0.277 | 0.931 | 37 | 0 |
| p42 | 654 | 0.792 | [0.761, 0.824] | 0.875 | 0.126 (n=119) | 0.496 | 0.244 | 0.940 | 32 | 0 |
| reseed | 654 | 0.879 | [0.855, 0.904] | 0.968 | 0.403 (n=119) | 0.849 | 0.613 | 0.985 | 8 | 0 |

2 games/matches

On real-client states, K4C's own floor (`reseed`) is 0.88 exact and 0.85 same card. The losses are:
- births: −0.02 exact, −0.06 same card;
- p70 and p42: about −0.09 exact; same card on truth plays drops to 0.58 / 0.50.

### Legacy schema (body-level classes WITH play events; single-knob sensitivities)

These ran before the schema was final: body-level identity, an event stream, and the noise applied to it. They are kept because they isolate single knobs. it5s2, 6 games:

| arm | decisions | exact | 95% CI | play/wait same | truth plays: exact | same card | card+<=2 tiles | truth WAITs kept | shadow plays when truth waits | errors |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| perfect | 3077 | 0.990 | [0.986, 0.994] | 0.994 | 0.924 (n=210) | 0.962 | 0.962 | 0.995 | 15 | 0 |
| drop10 | 3077 | 0.967 | [0.960, 0.973] | 0.976 | 0.805 (n=210) | 0.910 | 0.848 | 0.978 | 62 | 0 |
| jitter05 | 3077 | 0.955 | [0.948, 0.962] | 0.973 | 0.638 (n=210) | 0.848 | 0.776 | 0.979 | 61 | 0 |
| jitter10 | 3077 | 0.940 | [0.931, 0.948] | 0.962 | 0.557 (n=210) | 0.843 | 0.743 | 0.968 | 93 | 0 |
| hp10 | 3077 | 0.975 | [0.970, 0.981] | 0.985 | 0.786 (n=210) | 0.895 | 0.848 | 0.989 | 31 | 0 |
| hand02 | 3077 | 0.980 | [0.975, 0.985] | 0.985 | 0.895 (n=210) | 0.938 | 0.933 | 0.986 | 40 | 0 |
| elixir05 | 3077 | 0.908 | [0.898, 0.918] | 0.914 | 0.600 (n=210) | 0.652 | 0.629 | 0.931 | 199 | 0 |
| event10 | 3077 | 0.946 | [0.938, 0.955] | 0.958 | 0.743 (n=210) | 0.862 | 0.810 | 0.961 | 112 | 0 |
| evdelay10 | 3077 | 0.987 | [0.983, 0.991] | 0.991 | 0.895 (n=210) | 0.929 | 0.924 | 0.994 | 17 | 0 |
| v4like | 3077 | 0.875 | [0.863, 0.888] | 0.902 | 0.429 (n=210) | 0.752 | 0.567 | 0.908 | 264 | 0 |

6 games/matches

K4C-r16 unbounded, 3 games:

| arm | decisions | exact | 95% CI | play/wait same | truth plays: exact | same card | card+<=2 tiles | truth WAITs kept | shadow plays when truth waits | errors |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| perfect | 343 | 0.918 | [0.886, 0.948] | 0.962 | 0.831 (n=130) | 0.908 | 0.846 | 0.972 | 6 | 0 |
| drop10 | 343 | 0.828 | [0.787, 0.866] | 0.915 | 0.631 (n=130) | 0.808 | 0.692 | 0.948 | 11 | 0 |
| jitter05 | 343 | 0.665 | [0.612, 0.711] | 0.854 | 0.285 (n=130) | 0.715 | 0.515 | 0.897 | 22 | 0 |
| jitter10 | 343 | 0.641 | [0.589, 0.691] | 0.843 | 0.231 (n=130) | 0.669 | 0.438 | 0.892 | 23 | 0 |
| hp10 | 343 | 0.787 | [0.741, 0.828] | 0.895 | 0.554 (n=130) | 0.792 | 0.646 | 0.930 | 15 | 0 |
| hand02 | 343 | 0.869 | [0.828, 0.904] | 0.945 | 0.700 (n=130) | 0.846 | 0.769 | 0.972 | 6 | 0 |
| elixir05 | 343 | 0.714 | [0.665, 0.764] | 0.831 | 0.431 (n=130) | 0.623 | 0.492 | 0.887 | 24 | 0 |
| event10 | 343 | 0.802 | [0.758, 0.845] | 0.930 | 0.569 (n=130) | 0.846 | 0.646 | 0.944 | 12 | 0 |
| evdelay10 | 343 | 0.872 | [0.837, 0.907] | 0.948 | 0.715 (n=130) | 0.869 | 0.792 | 0.967 | 7 | 0 |
| v4like | 343 | 0.577 | [0.525, 0.627] | 0.787 | 0.138 (n=130) | 0.562 | 0.285 | 0.845 | 33 | 0 |

3 games/matches

- `jitter05`: 0.5-tile position noise.
- `elixir05`: elixir sd 0.5.
- `v4like`: recall 0.71, position 0.5, HP 0.1, event recall 0.71, event delay up to 6 ticks; the old v4 numbers.
- **For K4C, position jitter of 0.5 tile is as damaging as losing 10% of events.**

## 3. Decision latency per tier (127x05, nice 19, pinned; full decision = polls + belief + candidates + search)

Wall time per searched decision (search tiers) or per decision (it5s2), in ms, measured by `LivePlayer` (`wall_ms`, which includes the it5s2 poll).

- **"T1 states":** 3 recorded official-client matches (train split), `--source t1`, the bot on the perfect record.
- **"engine":** our-engine games from §2. Those processes also ran 6 shadow bots on the same core, so their CPU is sequential but uncontended.
- **"it5s2 default":** the deadline hit before any play had a complete three-style score, so the it5s2 action was used (the S-default rule, with it5s2 in R3a's place).
- 4-thread runs used cores 2–5 with nothing else on them. Single-core runs ran 3 at a time on separate cores.

| tier | states | decisions | p50 | p95 | p99 | max | it5s2 default |
|---|---|---:|---:|---:|---:|---:|---:|
| it5s2 only (`LIVE-fast-it5s2`) | T1 | 3,010 | 13.7 | 16.7 | 18.6 | 21.5 | — |
| it5s2 only | engine | 6,419 | 14.1 | 25.2 | 32.0 | 44.5 | — |
| K4C-r16 unbounded, 1 core | T1 | 733 | 173.7 | 712.1 | 876.8 | 1016 | — |
| K4C-r16 unbounded, 1 core | engine | 1,023 | ≈245 | ≈430 | ≈550 | 693 | — |
| `LIVE-K4CW-r16-w200-t1` | T1 | 733 | 91.3 | 192.3 | 192.4 | 193.9 | 140 (19.1%) |
| `LIVE-K4CW-r16-w200-t4` | T1 | 733 | 87.1 | 192.1 | 192.2 | 193.5 | 41 (5.6%) |
| `LIVE-K4CW-r16-w150-t4` | T1 | 733 | 88.3 | 142.2 | 142.5 | 167.2 | 146 (19.9%) |
| `LIVE-K4CW-r16-w120-t4` | T1 | 733 | 88.1 | 112.2 | 112.3 | 164.0 | 170 (23.2%) |

**Reading.**
- **The deadline holds.** p99 sits at the budget minus the 8 ms reserve. The rare overshoot (max +25–50 ms at w120/w150) is preparation before the cooperative cutoff: belief update, candidate forward, root build.
- **Unbounded K4C has a long tail on real states.** p95 is 0.7 s, so live play needs the wall tier.
- **4 threads matter at 200 ms:** they cut the decisions that end in the it5s2 default from 19% to 6%.
- **Below 200 ms, 1 in 5 decisions falls back to it5s2,** even with 4 threads. Whether that costs strength is exactly what the §4 paired HEADLINE answers (w200/w150/w120).
- **The fast tier is cheap.** One it5s2 forward is about 14 ms (p99 under 32 ms), comfortably under the 20 ms p50 target.
- **On the Mac,** expect these numbers scaled by the M4 Pro per-core speed relative to a 3990X core. Re-measure with the same command (§5).

## 4. Deadline validation: the paired HEADLINE command (to run on 03, by the bot lead)

**Design.**
- Arms:
  - `K4CW-r16-w200-t4` and `K4CW-r16-w150-t4`: the wall search alone, cutoff default R3a, exactly K4C-r16's search under a deadline;
  - `K4CW-r16-w120-t4`: a proxy for a Mac at about 0.6× fleet per-core speed (X4S: plain K4 collapses below about 0.9×; K4C with the R3a fallback should hold).
- Cases: HEADLINE-v1 default base `1455777415631152`, cases 0–299 × opponents {v1, R3a}. These are the same cases as the existing deterministic side, `bot-headline-r16-ours` and `bot-headline-r16-rsim15535` on 03 (K4C-r16, 300 per opponent, 0 errors). Only the wall arms run.
- Timing: each game gets a dedicated group of 5 physical cores (4 scoring threads + 1 engine/poller), pinned by `sched_setaffinity`. One worker per group.

**Staging (read-only for the bot lead's trees).** `bot/live/` exists only in the `live/lead` worktree on 05. Copy that worktree's `bot/` to a new directory on 03; don't touch `clasher-bot/`:

```bash
# from 05 (LIVE LEAD or bot lead):
rsync -a --delete /mpac/sdicks02/repos/clasher-live/bot/ 127x03:/mpac/sdicks02/repos/clasher-live-eval/bot/
```

**Smoke first (2 games, about 1 minute, RoyaleSim path, which is untested on 05 because 05 has no royalesim):**

```bash
ssh 127x03
cd /mpac/sdicks02/repos/clasher-live-eval
export PYTHONPATH=$PWD CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 PYTHONHASHSEED=0 \
       OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
nice -n 5 $PY -B -m bot.live.headline_wall --out /mpac/sdicks02/jobs/clasher/live-wall-smoke --cores 0-9 \
  --candidate K4CW-r16-w150-t4 --opponents v1 --games 1 --engine rsim15535
cat /mpac/sdicks02/jobs/clasher/live-wall-smoke/games-*.jsonl     # expect 2 rows, no "error"
```

**The run.** `<CORES>` is the reserved physical-core list, for example `0-59`, giving 12 groups. Their SMT siblings (`cpu+64` on a 3990X, e.g. 64–123) must stay idle.

```bash
# primary engine: RoyaleSim 15.535 (the engine the r16 baseline's headline uses)
nice -n 5 $PY -B -m bot.live.headline_wall --out /mpac/sdicks02/jobs/clasher/live-wall-rsim15535 \
  --cores <CORES> --group 5 --engine rsim15535 \
  --candidate K4CW-r16-w200-t4,K4CW-r16-w150-t4,K4CW-r16-w120-t4 --opponents v1,R3a --games 300
# secondary: our engine
nice -n 5 $PY -B -m bot.live.headline_wall --out /mpac/sdicks02/jobs/clasher/live-wall-ours \
  --cores <CORES> --group 5 --engine ours \
  --candidate K4CW-r16-w200-t4,K4CW-r16-w150-t4,K4CW-r16-w120-t4 --opponents v1,R3a --games 300
```

Both runs are resumable: rerunning skips finished (candidate, opponent, index) rows. Jobs are case-major, so a partial run still covers all arms evenly.

**Count and time.**
- Each engine: 3 arms × 2 opponents × 300 = **1,800 games**.
- Per game: the 05 smoke took 33 s for a 3,601-tick game. The unbounded r16 averaged 60–69 s on 03 while sharing cores. Full 6,000-tick games will be longer, so assume about 50 s.
- With 60 cores = 12 groups: 1,800 / 12 × 50 s ≈ **2.1 h per engine**, about **4.2 h for both**. RoyaleSim alone answers the question.
- Fewer cores scale linearly: 30 cores ≈ 4.2 h per engine.

**Pairing** (the existing deterministic K4C-r16 side as A, the wall arm as B), per engine and arm:

```bash
for w in 200 150 120; do
  $PY bot/eval/pair_by_name.py /mpac/sdicks02/jobs/clasher/bot-headline-r16-rsim15535 K4C-r16 \
      /mpac/sdicks02/jobs/clasher/live-wall-rsim15535 K4CW-r16-w$w-t4
done      # prints "B-A vs <opp>: mean [95% bootstrap CI] n=300" for v1 and R3a; same for -ours dirs
```

**Reading it.**
- A wall arm is fit to deploy if B−A is not clearly negative: CI upper bound ≥ 0, or a mean above about −0.02, against both opponents.
- X4S reference: K4+S lost 18/22/26% vs v1 at 160/140/120 ms, so some loss at 120 ms is expected.
- The live tier itself (`LIVE-K4CW-…`, it5s2 as cutoff default) can be added as a 4th arm, for example `LIVE-K4CW-r16-w150-t4`. That adds 600 games per engine. It isn't needed to validate the deadline.

### Optional: what a perception level costs in WIN RATE

`PERC-<arm>:<player>` (`bot/live/perc.py`) plays the true game but sees it only through synthetic perception at a noise arm (§2) and the translator. A tap that the true state cannot honour is ignored, as the client would. Both seats are supported.

A cheap run, it5s2 only (1 core per game, so `--group 1`). Five arms × 2 opponents × 300 = 3,000 games, about 35 s each. On 60 cores that's about 0.5 h:

```bash
nice -n 5 $PY -B -m bot.live.headline_wall --out /mpac/sdicks02/jobs/clasher/live-perc-ours --cores <CORES> --group 1 \
  --engine ours --opponents v1,R3a --games 300 \
  --candidate LIVE-fast-it5s2,PERC-events:LIVE-fast-it5s2,PERC-births:LIVE-fast-it5s2,PERC-p70:LIVE-fast-it5s2,PERC-p42:LIVE-fast-it5s2
# pair each PERC arm against LIVE-fast-it5s2 in the same dir with bot/eval/pair_by_name.py
```

The search version is `PERC-births:LIVE-K4CW-r16,PERC-p42:LIVE-K4CW-r16`. That's 1,200 games at about 60 s on 1 core each.
- `LIVE-K4CW-r16` is the unbounded LivePlayer: K4C-r16's decisions plus LiveBelief, so a false derived play cannot crash it.
- It pairs with the existing K4C-r16 dirs.
- Don't wrap a bare `K4C-r16`: its belief raises on an off-prior card.

## 5. Mac porting note (no Mac access was used; nothing here has run on a Mac)

> **CORRECTION (LIVE LEAD, 2026-10-15, from the Mac-bench owner's check):** the recipe below is incomplete.
> 1. The pinned native 44874fd6 is not built from the runtime root's `engine-rs` as it stands: `rollout_e1`, which the
>    search kernel calls, is patched in by `reports/explore/e1/stage_native.py`.
> 2. The build needs `--features extension-module,gil-release` (`k-anytime/receipts/runtime-pin-03.json`). Without
>    `gil-release`, parity still passes, but the 4 scoring threads are silently serialized.
>
> The corrected recipe is in `reports/live/mac-bench/mac/run.sh`. A rebuild on 05 with it passes parity bit-exactly
> (40/40 roots, 600/600 values).
>
> Also, the latency table in §1 was measured on contended 05 cores, including core 5, which a foreign nice-19 process
> has held at 100% for days. The clean baseline is in `reports/live/mac-bench/PROGRESS.md`:
>
> | tier | p95 | ends in default |
> |---|---|---|
> | w200-t4 | 185 ms | 2.0% |
> | w150-t4 | 142 ms | 13.1% |
> | unbounded, 1 thread | 380 ms | n/a |


**1. Code.**
- Copy this worktree's `bot/`. It holds bot/players, search, exit, eval and live; `bot/players/royalesim_vocab.json` is inside it.
- Also copy `reports/explore/x4s/sdefault.py`. `runtime.py` puts `BOT_REPO/reports/explore/x4s` on `sys.path`, so recreate that path relative to the copied repo root.
- `labels_v4.py` and `body-catalog.json` are needed only for the T1 replay harness, not for live play.

**2. Runtime root.** Start from the r1 root (592 MB on Linux), but copy only the files the live bot reads. These are measured by `python -m bot.live.runtime_manifest` (§5.4 below has the totals; the file list is in `jobs/clasher/live-glueC/runtime-manifest.json` on 05). Never copy:
- `dry-inputs/` (235 MB), `tests/` (43 MB), `train-match/` (20 MB), most of `reports/`;
- the Linux natives in `native/` and `native-r6/`.

Checkpoints are pinned by SHA:

| checkpoint | size | sha256 |
|---|---|---|
| R3a.pt | 35 MB | 37509a43… |
| main02.pt | 35 MB | d77005d5… |
| `students/it5s2-step001200.pt` + `.calibration.json` | 40 MB | 08bdaf32… |

Point `CLASHER_LIVE_FAST` at the it5s2 checkpoint, e.g. `student:<dir>/it5s2-step001200.pt@0.5375`.

**3. Native core.**
- Build `clasher_core.abi3.so` on the Mac from **the runtime root's own `engine-rs/`**. That is the source tree shipped with the Linux pin `44874fd6`; its `build-tiers.json` names source manifest `84c8fe33…`.
- Do not use build48 (`9263a8f7…`): it was built from main `326b2a86` for the old live runtime, a different source.
- Build with `engine-rs/build.sh` (Darwin branch). It runs `cargo build --release --features extension-module -j 1`, then copies `libclasher_core.dylib` to `engine-rs/clasher_core.abi3.so` via a fresh inode. It needs `PYO3_PYTHON` = the arm64 Python 3.12 that will run the bot. The recipe and toolchain match `MAC-NATIVE-BUILD48.md` (rustc 1.97.1 aarch64-apple-darwin, about 41 s).
- Put the binary in `<root>/native-mac/` and set `CLASHER_DELAY_NATIVE_DIR=<root>/native-mac`; `runtime.py` honours it.

Pin it without touching Linux behaviour:
1. **Parity first.** The fixture already exists: `05:/mpac/sdicks02/jobs/clasher/live-glueC/parity.json` (2.1 MB; 40 roots, 600 values). On 05 its Linux self-check passed 40/40 roots, bit-identical with native 44874fd6. To regenerate it, run `python -m bot.live.native_parity dump --out parity.json`: fixed public roots from our engine plus the exact rollout values of WAIT and 4 plays × 3 styles. On the Mac, run `python -m bot.live.native_parity check --fixture parity.json`. It must report `parity: true`, meaning bit-identical values, and it refuses a different engine config. If it fails, the Mac binary is not the same planner, and no Mac timing or decision should be trusted (build48 had to pass the same kind of gate).
2. **Then the pin.** Add `{"mac-r1": {"native_sha256": "<mac sha>", "base": "r1"}}` to `bot/live/mac_pins.json`. Call `bot.live.mac_pins.register()` before `Runtime()` and run with `CLASHER_BOT_RUNTIME_PINS=mac-r1`.
   - `register()` only adds new keys to `runtime.PIN_SETS`. r1 and r2 can't be overwritten, and only `native_sha256` may differ, so Linux is unchanged.
   - The alternative is a one-line upstream edit adding `mac-r1` to `PIN_SETS` in `runtime.py`. That isn't needed; ask the bot lead if you prefer it.

**4. Environment and footprint.**
- Use arm64 Python 3.12 with torch and numpy at the versions in the runtime root's `uv.lock`. The bot's nets run on CPU (`torch.set_num_threads(1)`); MPS isn't needed for the bot.
- Disk: measured by `runtime_manifest` (w200-t4 search tier + fast tier, one game each).
  - Runtime root: **155 files, 80.7 MB**. That is R3a.pt 34.5 + main02.pt 34.8 + native 6.4 + gamedata 3.0 + src 1.2 + reports 0.7 MB + engine-rs/imitation/student-source.
  - Plus it5s2, 37.8 MB, and 19 `bot/` modules, 0.1 MB.
  - Copy whole `src/`, `imitation/`, `student-source/` and `engine-rs/` (no `target/`) for headroom: still under 150 MB. The file list is `jobs/clasher/live-glueC/runtime-manifest.json` on 05.
- RAM: **peak RSS 1.0 GB** for one process (Runtime + torch + three nets + belief). On Linux this is dominated by the 3 nets and the belief arrays: the human prior is 2,925 decks × 1,680 orders × 12 B ≈ 59 MB per belief, and a LivePlayer has one.
- Runtime(): about 15 s of CPU, once, at startup. Do it before the match.
- CPU per decision:
  - search tier: up to 4 threads for ≤ `wall_ms` every 10 ticks (0.5 s at 20 ticks/s);
  - it5s2 + R3a polls: about 13 ms + about 10 ms of 1 core every 5 ticks.
  - At w200-t4 that averages about 2 P-cores with bursts of 4, which fits the PLAN's budget of 1–4 search threads on 8 P-cores (emulator 3–4).
- Speed check: the M4 Pro per-core speed relative to a 3990X core is unknown. Run `python -m bot.live.replay --source t1 --tier search --wall-ms 200 --threads 4 --noise perfect --games 2` on the Mac. Compare the `search-defaulted` share and `completed` counts with §3. If the Mac completes clearly fewer roots per decision, use the w120 arm's HEADLINE result (§4) to choose `wall_ms`.
