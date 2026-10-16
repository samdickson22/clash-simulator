# Full-pool learned components (BOT LEAD worker, exploration)

What this delivers, so self-play and ExIt label generation can start on the 121 playable ladder cards as soon as
the CARD LEAD's pin `r1-cards1` passes its gate. Where things are hard-wired to C56 and what each fix does:
`INVENTORY.md`. Running log: `PROGRESS.md`. Rule (Sam, 10-16): nothing is sealed; results are reported as they
come.

## 1. Model extension (C56 bit-identical)

`python -m bot.fullpool.extend policy --in CKPT --out OUT [--init row|input]` (v1, R3a, it5s2, RL snapshots) and
`python -m bot.fullpool.extend lopp --in X.npz --out Xfp.npz --meta META.json` (K4L nets; `META.json` from
`extend meta-tokens` under `CLASHER_BOT_RUNTIME_PINS=r1-cards1`). Each output gets `OUT.fullpool.json` (source and
output sha256, row map). The rows are initialised from the proxy card (`bot/cards/proxy_table.py` `proxy_card`,
`body_map`). Rows are appended (K4L) or rewritten only where no C56 card can produce the token (policy); nothing is
renumbered.

Parity test (`bot/fullpool/parity.py`). Policy nets: 600 roots from 10 recorded C56 games, all 56 cards. K4L: 1000
recorded native views. Every output and decision is identical: **PASS** for RL r5 v10, R3a, v1, K4L `pool` and
`pool2L` (numbers in `INVENTORY.md`).

Extended files (05 and 08 `/mpac/sdicks02/jobs/clasher/bot-fullpool/`, not in git):

| model | source sha256 | extended | sha256 |
|---|---|---|---|
| RL r5 v10 | e188e2ae… | `ext/rl5-v10-fp.pt` (+ `.calibration.json`, 0.5375) | a6565cab… |
| RL r5 v10, `--init input` | e188e2ae… | `ext/rl5-v10-fp-input.pt` | see receipt |
| R3a | 37509a43… | `ext/R3a-fp.pt` | ce7b0ea4… |
| v1 main02 | d77005d5… | `ext/main02-fp.pt` | 69313468… |
| K4L pool / pool2 / pool2L / R3a / v1 | bot-lopp-models | `lopp-fp/{pool,pool2,pool2L,R3a,v1}fp.npz` | faf6efbe… / e202b0ff… / 19b9def8… / 7b894d3e… / 04828a3a… |

Use: `student:<ext>/rl5-v10-fp.pt@0.5375`. For K4L, `CLASHER_LOPP_MODELS=<lopp-fp>` plus the `-mpoolfp` token
(e.g. `K4L-R-gs-mpoolfp`). For extended v1/R3a as `rt.POLICY`/`rt.STUDENT`:
`BOT_FULLPOOL_POLICIES='v1=…,R3a=…'`, which is accepted only if the receipt names the pinned source.
To fine-tune K4L from an extended net: `bot.search.lopp_train --init poolfp.npz`, which keeps the vocab order and
normalisation.

## 2. Deck sampler (`bot/fullpool/decks.py`)

`Sampler.from_spec('fullpool:<seed>').deck(i)` returns 8 distinct cards from the 121, with at most one champion.
The result is deterministic in (spec, i, salt) and in the two pinned inputs.

Per-card weight = 0.65 × observed + 0.25 × next arenas + 0.10 × uniform:

- **observed**: LIVE Battle Log shares (`reports/live/loop/arena-card-freq.json`). Current pin b53b02a1… (origin/main
  e7beb00f): Goblin Stadium n=12, Bone Pit n=21, Barbarian Bowl n=8. Each arena's shares are smoothed with 4
  pseudo-battles of its unlock list. Arenas are pooled with weight n × 0.5^(A − a), where A is the current (highest
  observed) arena, giving BB 8, BP 10.5, GS 3.
- **next**: cards first unlocked in the next two arenas per `ARENA-CARDS.md` (sha 75a8a0ab…). Arena 4 Spell Valley
  gets 2/3 and arena 5 Builder's Workshop (Bats, Flying Machine, Hog Rider, Mortar, Rocket, Zap) 1/3.
- **uniform**: a floor over all 121 cards.

Unresolved list names: "Skeleton Tower" and "Cannoneer" (a tower troop).

**Refresh** (LIVE re-commits the table about every 15 battles): `python -m bot.fullpool.decks --refresh` freezes it
to `reports/bot/fullpool/freq/arena-card-freq-<sha12>.json` and prints the new `FREQ` pin to paste into
`decks.py`. A one-off run can use `BOT_FULLPOOL_FREQ=<path>@<sha256>`; a sha mismatch raises. The named banks pin a
frozen table (`:freq=b53b02a1fde4`), so a refresh never moves their cases. A spec without `freq=` follows the
current pin (generation can track the ladder).

What the sampler produces (spec `fullpool:846496:freq=b53b02a1fde4`, 20,000 decks):

| statistic | value |
|---|---|
| decks with at least one non-C56 card | 95.9% |
| mean non-C56 cards per deck | 2.32 |
| decks with a champion | 5.7% |
| cards seen | all 121 |

Highest inclusion: Giant .39, Goblins .38, GoblinCage .36, Fireball .35, SpearGoblins .35, GoblinHut .34,
Valkyrie .33, Tombstone .32, Bomber .32, MiniPekka .31. Barbarians .12, MegaMinion .10, BattleRam .08. Mortar and
Flying Machine are .13 each (next arena). The 89 floor-only cards are each in 0.56–0.91% of decks.
`fullpool-uniform:<seed>` draws uniformly (4.3 new cards per deck). Options: `:obs=…,next=…,floor=…,freq=<sha12>` and
`own=c56` / `opp=c56`.

## 3. Generation / eval options

`case(rt, i, base, decks)` (`bot/fullpool/banks.py`) is `x4s_setup` with the deck lists swapped. Seed, seat
and shuffle are the same, and the cases are the same across opponents.

- `python -m bot.eval.headline … --decks fullpool:<seed>[:own=c56] | --bank NAME [--belief-prior c56|SPEC]`
- `python -m bot.exit.generate … --decks … | --bank FP-TRAIN1`. The bank must be disjoint from every eval bank,
  and this is checked.
- `BOT_RL_DECKS=fullpool:<seed> python -m bot.rl.actor …`. League games vs `K4C-r16` get a C56 opponent deck.
- `python -m bot.search.lopp_record … --decks fullpool:<seed>:own=c56` (K4L retrain data).

The default `x4s` is HEADLINE-v1 unchanged. With full-pool decks the search players' belief uses the sampler
prior (`bot/fullpool/belief.py`), and rows carry `decks` and `deck_lists`.

**Constraint while `R.bots` is C56:** every search seat (K4S teacher, K4C, K4L) needs a C56 own deck
(`own=c56`). Otherwise `C56RolloutPlanner` raises 'own hand outside C56 action scope'. Policy seats take any deck.

## 4. Banks: C56 regression vs full pool

All banks are fresh: `os.urandom(6)<<4`, drawn 2026-10-16 01:38Z, each at least 1e12 from every base in bot/ and
reports/bot.

| bank | base | decks | use |
|---|---|---|---|
| C56-REG | 1455777415631152 (HEADLINE) | x4s | C56 regression. r1 / r1-total / r1-cards1 and extended models must give identical command hashes. Already used for selection |
| FP-DEV | 1017731189512176 | fullpool:846496:freq=b53b02a1fde4 | full-pool development and selection |
| FPO-DEV | 1017731189512176 | …846496:freq=b53b02a1fde4,own=c56 | same, with the candidate on a C56 deck (search candidates; live-like) |
| FP-FRESH1 | 3314739122528544 | fullpool:11574762:freq=b53b02a1fde4 | honest full-pool claims, never used for selection |
| FPO-FRESH1 | 4370374256243600 | …10434953:freq=b53b02a1fde4,own=c56 | honest live-like claims (C56 candidate deck vs full-pool opponents) |
| FP-TRAIN1 | 2613058991490864 | fullpool:11433651:freq=b53b02a1fde4 | generation and self-play (span 1e8) |

A claim on a FRESH bank is reported as soon as it exists. Once a bank has been used to pick between candidates it
is a dev bank, and the next claim draws a new FRESH bank.

## 5. Smoke under r1-cards1

`bot/exit/cpu_job.sh 14 bot/fullpool/smoke.sh OUT` (arms stu, k4l, c56s, c56k, gen) and
`python -m bot.fullpool.smoke_summary OUT`. Results: `PROGRESS.md`.
