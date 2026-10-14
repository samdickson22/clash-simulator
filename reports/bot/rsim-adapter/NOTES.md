# Our bots playing inside RoyaleSim: adapter notes

Exploration tier, 2026-10-14, by the bot-lead implementation sub-agent. The code is in `bot/players/royalesim_*.py` on
the `bot/lead` worktree; nothing is committed. All runs were on 127x03 with runtime
`/mpac/sdicks02/repos/clasher-bot-runtime/r1` (native 44874fd6, v1 d77005d5, R3a 37509a43 verified at start).
Outputs are in `/mpac/sdicks02/jobs/clasher/bot-rsim-adapter/` on 03.

## What works

**Players.** Our players play full, deterministic matches inside RoyaleSim 0.1.34, in either seat:
- `PolicyPlayer('v1')` and `PolicyPlayer('R3a')`;
- `SearchPlayer` in `budget` / `unbounded` / `wall` mode, with default `R3a` (K4S) or `v1` (K4);
- `ScriptedPlayer` (our PublicScriptedOpponent: `balanced`, `pressure`, `defense`);
- `RoyaleGymPlayer`: RoyaleGym's built-ins `first-affordable`, `defend`, `push`, `patient`, `random`, `noop`.

**Rules.** The default rules are `client_arms("15.535.29")`; `--client 16.402` runs RoyaleSim's default rules.

**Planner model.** The search player still plans on **our** Rust engine. Each decision it builds its root from the
translated public view (`R.root`). This is the intended model-mismatch configuration.

## Files (`bot/players/`)

| File | What |
|---|---|
| `royalesim_match.py` | `play_match(rt, players, seed, decks, client=...)`, the X4S loop on RoyaleSim; `RsimMatch` (battle plus public bookkeeping) |
| `royalesim_translate.py` | `Translator`: `state_json` → `fair_player.Information` (a contract-v5 packet through the frozen `project_public_v5`); `OwnCycleView` |
| `royalesim_vocab.py` + `royalesim_vocab.json` | RoyaleSim row → our (token, kind), the static v5 columns, level and motion mode. Built from paired demos of all 56 C56 cards in both engines |
| `royalesim_opponents.py` | `ScriptedPlayer`, `RoyaleGymPlayer` (executes upstream `opponents.py` 0.1.24, sha256 5894e848…) |
| `royalesim_run.py` | N games of A vs B in RoyaleSim or ours (`--engine ours`), sharded; JSONL |
| `royalesim_summary.py` | loss/win per arm (Wilson 95%) and RoyaleSim − ours loss, paired by index (bootstrap) |
| `royalesim_crosscheck.py` | the same scripted opening in both engines; our `build_public` vs the translated RoyaleSim packet |
| `test_royalesim_translate.py` | 7 translator tests |
| `royalesim_adapter.py` | the shared helpers: card names and action → command |

## Match loop: same semantics as `ours.play_match`

**Mirrored exactly:**
- **Decks:** `x4s_setup` decks in initial order. RoyaleSim `shuffle=0` deals `deck[:4]` as the hand and `deck[4:]` as
  the queue, as ours does.
- **Levels:** card and tower level 11, giving King 4824 and Princess 3052.
- **Lag:** per-seat `CommandQueue(27, capacity 1)` with reservation.
  - RoyaleSim's own delay is set to 0. The command is sent at the due tick and RoyaleSim validates it in full there.
  - A rejection is recorded and not refunded.
- **Polling:** both seats every 5 ticks from tick 90, blocked polls included. Search acts on 10-tick multiples.
- **Waits and lateness:** timed waits, honest lateness for wall players, and the GC window, all as in ours.
- **Command hash:** the same string format.
- **Events:** the public stream comes only from commands the harness applied: `PublicEvent` to the opponent, plus a
  recorder row with the tile where RoyaleSim placed the card.

**Starting elixir is 6 in both engines.** Ours uses the PlayerState default. RoyaleSim's measured `match.START_MANA` is 6
on all 60/60 recorded sides. The `[5000, 5000]` in RoyaleSim's API example and in the INVENTORY sketch is wrong;
INVENTORY §2's "elixir starts at 5" should read 6.

**Result:**
- It is RoyaleSim's own: crowns, the three-crown end, 3 min plus 2 min overtime, then its weakest-tower tie-break. The
  15.535 arm runs that tie-break as an HP drain that can pass tick 6000; the safety cap is 7200.
- Ours decides the same tie-break at 300 s on the lowest tower HP.
- `winner=None` is a draw.

**Time stepping:** the loop jumps from event to event (polls and due commands), decoding `state_json` about once every 5
ticks.

## Translator field map (our v5 row ← RoyaleSim)

| v5 field | Source |
|---|---|
| x, y (0, 1) | `x, y` subtiles / 18000 → tiles, /18, /32, rotated 180° for seat 1 |
| own/enemy (2, 3) | `team == seat` |
| kind (4–8) and token | Units: `unit_type` name = our troop/building token name (case-insensitive; 47 C56 bodies, plus a lazy same-name lookup for unseen bodies). Towers: kind 2/3 → KingTower/Tower tokens. Spell objects: (card, motion) table, 17 rows (e.g. Log airborne+rolling → our `Log` Projectile; Balloon death bomb → `Balloon` AreaEffect; IceGolem freeze → `FreezeIceGolemite`). Shots: `firer_card_id` → that card's projectile token in ours (22 cards); −1 → king or princess shot, chosen as the tower the shot lies on the line from (min triangle slack) |
| hp_fraction (9) | `hp/max_hp` for units and towers; our engine's constant for shots and effects |
| statics 23–26, 30 | our engine's value for that body: base speed, range, sight, collision radius, base damage (`royalesim_vocab.json` statics, 88 bodies; card data, so public once the body is identified) |
| motion (27, 28) | per body as our engine fills it, measured: `dynamic` = unit `facing` normalised (troops), `forward` = the owner's forward (all our spells, shots and buildings; ours does not use flight direction), `none` (spirit self-shots) |
| entity levels | our engine's public level (11; towers their publicLevel) |
| globals | progress = tick/6000; double ≥120 s, overtime ≥180 s, triple ≥240 s, each from the start of the tick (checked against our engine at all 3 boundaries); own elixir/10; crowns; six tower fractions with lanes mirrored for seat 1; own refill; enemy king alive. Champion clocks are 0 and exposed only while an own champion (ArcherQueen, MightyMiner, Goblinstein doctor) stands, as v5 does; abilities are never pressed |
| hand | own `hand` from RoyaleSim (−1 → empty) plus the next card |
| history and seen cards | the harness's accepted enemy plays (last 4 with ages; first 8 distinct) |
| own_last_play | the harness's own accepted plays |
| own HUD (`info.own`) | elixir and hand from RoyaleSim. Cycle and refill come from the frozen `OwnCycle`, fed own plays and reconciled with RoyaleSim's hand and next card (0 mismatches in every smoke game) |

**Not mappable; defaults used.** All of these lie outside v5 and are zeroed by `project_public_v5` anyway: 10 shield, 11
airborne, 12–22 status timers and flags, 29 effect progress, 31 tower_active. Inside `R.root`, unit internals (targets,
attack clocks, deploy timers) come from template defaults, exactly as in our own harness.

**Visibility.** Enemy units with RoyaleSim status bit 0 (underground) or bit 1 (invisible) are dropped. This matches
v5 `hidden_from_enemy` for a tunnelling Miner or a cloaked Ghost. A hidden Tesla (bit 2) stays visible, as in ours.

**Dropped and counted** (`result['translator']`): RoyaleSim bodies with no counterpart in ours (the Goblin Hut garrison
sprite `SpearGoblin_Dummy`; Lightning's bolt projectiles, where ours shows only the Lightning area row), and any row
without a public template, which would make `R.root` fail closed. Every smoke-2 game had 0 drops, 0 defaulted statics
and 0 unmapped rows.

## Fair information (audited)

- **Translator:** from `players[1-seat]` it reads only `crowns`, `tower_hp` and `tower_max_hp`. A test poisons the
  opponent's hand, next card, deck, pending and elixir and asserts that the packet is byte-identical.
- **Opponent elixir and cycle:** derived only by the players' own D1/belief from the public play events.
- **v1/R3a:** read the packet plus public events.
- **Search:** belief from public events, plus the root from the packet and own HUD.
- **Scripted:** the packet.
- **RoyaleGym players:** read only their own legality (the opponents' documented input is the mask). Here that is
  RoyaleSim `check_deploy(own seat, slot, tile)`: own hand, own elixir and the public board. The wrapper holds the
  battle object for that call only.

## Validation

**(a) Unit tests:** 7/7 pass in 16 s. Run:
`CLASHER_BOT_RUNTIME=… bot/players/run.sh -m pytest -q -p no:cacheprovider bot/players/test_royalesim_translate.py`.
They cover:
- action → command and the seat flip;
- seat-0 rows (a troop, an enemy building, our spell, an enemy shot, the king's shot, 6 towers, hidden enemies dropped);
- seat 1 as the exact 180° rotation, with own hidden units visible to their owner;
- globals: lane mirroring, hand, history, ages and own last play;
- the opponent-record invariance;
- phase flags equal to our engine's at ticks 2400, 3600 and 4800;
- a real RoyaleSim battle where both seats' views mirror.

**(b) Cross-check** (`crosscheck3/`): same opening in both engines, 9 alternating plays at ticks ≡ 2 (mod 5) as the
harness executes them, compared every 10 ticks for both seats. Five cases, one per own X4S deck.

| case (own deck) | plays agree | to tick 300: rows equal | pos err mean / max (tiles) | HP / statics max | to tick 600: rows equal | what diverges |
|---|---|---|---|---|---|---|
| 0 bridge | 9/9 | 21/21 | 0.002 / 0.12 | 0 / 0 | 50/50 | nothing |
| 6 siege | 7/9 | 17/21 | 0.17 / 9.8 | 0.035 / 0 | 32/50 | RoyaleSim accepted a Tesla tap that ours refused (building relocation); the games then differ |
| 12 beatdown | 8/8 | 21/21 | 0.004 / 0.55 | 0 / 0 | 44/50 | Arrows: ours shows the volley as up to 30 projectile rows, RoyaleSim as 1–2 spell rows |
| 18 bait | 9/9 | 21/21 | 0 / 0 | 0.045 / 0 | 49/50 | Wallbreaker hit on a princess tower: ours 0.771, RoyaleSim 0.816 (physics) |
| 24 chip | 9/9 | 20/21 | 0.008 / 0.86 | 0 / 0.099 | 46/50 | Miner tunnel facing and emergence tick |

- **Hand, history, seen cards and champion button:** equal on every compared tick, except case 6 after the divergence.
- **Globals:** at most 0.002 apart (rounding of `elixir_milli`) until physics diverge.
- **The one translation-level timing difference is on the execution tick itself.** Ours already shows the new body and
  an empty slot then. RoyaleSim adds the body one tick later and refills the slot at once. Harness polls never fall on
  an execution tick (due ≡ 2 or 7 mod 5), so players never see it.

**(c) Smoke** (`smoke2/` final code; smoke bank 4503604817370496; indices 0–1 = bridge mirror, siege vs bridge):

| game | engine | A seat | A result | crowns | ticks | command hash, rep 0 = rep 1 | CPU s/game | A decisions, mean rollouts, ms/decision |
|---|---|---|---|---|---|---|---|---|
| K4S-b48 vs v1, i0 | RoyaleSim 15.535 | 0 | win | 2–1 | 4763 | fd0a215f… = | 52.1 / 50.8 | 150, 40.5, 214 |
| K4S-b48 vs v1, i1 | RoyaleSim 15.535 | 1 | win | 1–0 | 3600 | 895b4bc3… = | 35.3 / 34.2 | 111, 37.0, 184 |
| v1 vs v1, i0 | RoyaleSim 15.535 | 0 | win | 1–0 | 3600 | 7ce574b9… = | 16.9 / 16.6 | – |
| v1 vs v1, i1 | RoyaleSim 15.535 | 1 | loss | 0–1 | 4199 | 920b369c… = | 19.6 / 18.5 | – |
| K4S-b48 vs v1, i0 (smoke1) | ours | 0 | win | 1–0 | 3601 | db144442… = | 41.1 / 39.8 | 120, 39.0, 186 |
| K4S-b48 vs v1, i1 (smoke1) | ours | 1 | loss | 0–1 | 3601 | bd615fb6… = | 40.4 / 38.3 | 113, 35.4, 184 |
| v1 vs v1, i0 / i1 (smoke1) | ours | 0 / 1 | loss / loss | 0–1 / 0–1 | 3601 | bbd4df61… / 8f7cca74… = | 21.5 (i0) / 19.7 (i1) | – |
| R3a vs v1, i2 | RoyaleSim | 0 | win | 3–1 | 2983 | 3bff135f… | 12.9 | – |
| scripted-balanced vs v1, i3 | RoyaleSim | 1 | win | 1–0 | 3600 | 27fcb1ef… | 11.1 | – |
| rgym-patient vs v1, i4 | RoyaleSim | 0 | loss | 1–3 | 4000 | 8c66a908… | 10.7 | – |
| K4S-b48 vs rgym-patient, i5 | RoyaleSim | 1 | win | 3–0 | 1673 | 7016a357… | 10.9 | 45, 37.4, 164 |

**Smoke takeaways:**
- **Determinism:** every repeat gives an identical command hash, in both engines.
- **Cleanliness:** 0 rejected commands, 0 translator drops and 0 own-cycle mismatches in all smoke-2 games.
- **CPU per game** (one core, plus about 16 s of process setup): RoyaleSim costs about the same as ours.
  - K4S-b48 vs v1: 34–52 s in RoyaleSim against 38–41 s in ours.
  - v1 vs v1: 17–20 s against 19–21 s.
- **Not a strength result:** two games say nothing about strength, and the win/loss differences between engines here
  are anecdotes.
- **Smoke 1 used an older vocabulary** that left 146 rows with default statics. It played the same outcomes with one
  hash difference (i0). Smoke 2 is the reference.
- **The 16.402 arm runs:** a 900-tick K4S-b48 vs v1 game had 12 plays, all accepted, and 0 drops.

## Known gaps (none blocks running games)

1. **Engine physics differ:** the planner models ours while the match runs RoyaleSim. That is intended.
   - Placement differs too: RoyaleSim relocates a building tap that doesn't fit, where ours refuses it. Troop taps clamp
     under RoyaleSim's 15.535 placement rules.
   - The policy's mask is our engine's. `result['deploy_reasons']` records RoyaleSim's verdict for each command; all
     were OK in the smoke games.
2. **Arrows in flight** show as 1–2 rows rather than our ~30 projectile rows. This affects the policy view and the
   `R.root` damage model for about 1 s per Arrows play.
3. **Other unmatched rows:**
   - our ElectroSpirit chain-lightning effect row (10 ticks) has no RoyaleSim row;
   - Firecracker explosion shards map to our FirecrackerProjectile token;
   - the king vs princess shot assignment is geometric.
4. **Miner while tunnelling:** its facing and its emergence tick differ by a few ticks.
5. **RoyaleGym players** poll every 10 ticks (RoyaleGym's 500 ms default) through our 27-tick lag. Their mask is
   up to 2,304 `check_deploy` calls per decision. A whole rgym-vs-v1 game costs about 11 s of CPU.
6. **The vocabulary covers C56 only**, as do the players. A non-C56 body would be dropped and counted, or resolved
   lazily by name.
7. **The `16.402` arm** is RoyaleSim's default overrides (`{}`), matching FIDELITY's 16.402 column. The vocabulary is
   checked against the unit-type digest, which is the same for both arms.

## Commands

Setup on 03: the frozen runtime `export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1`, from
`/mpac/sdicks02/repos/clasher-bot`. `run.sh` pins `BOT_CPU`, runs at nice 19, single-threaded, with `PYTHONHASHSEED=0`.

```bash
# rebuild the vocabulary (≈1.7 min; only after a royalesim / token-vocabulary change)
BOT_CPU=5 bot/players/run.sh -m bot.players.royalesim_vocab
# tests, cross-check
BOT_CPU=5 bot/players/run.sh -m pytest -q -p no:cacheprovider bot/players/test_royalesim_translate.py
BOT_CPU=5 bot/players/run.sh -m bot.players.royalesim_crosscheck --index 0 6 12 18 24 --ticks 600 --out OUT.json
# N games, K processes, one core each; BANK = a fresh seed bank (x4s/audit_seeds.py), N a multiple of 50 keeps decks x seats balanced
OUT=/mpac/sdicks02/jobs/clasher/bot-rsim-<run>; N=200; K=40; BANK=<fresh>
for eng in rsim ours; do
  off=$([ $eng = ours ] && echo $K || echo 0)
  for k in $(seq 0 $((K-1))); do
    BOT_CPU=$((8+off+k)) bot/detach.sh $OUT/$eng-s$k.log $OUT/$eng-s$k.receipt.json \
      bot/players/run.sh -m bot.players.royalesim_run --a search:budget:48 --b v1 --range 0 $N \
        --shard $k/$K --base $BANK --engine $eng --out $OUT/$eng-s$k.jsonl
  done
done
.venv/bin/python -B -m bot.players.royalesim_summary $OUT/*.jsonl   # per-engine loss + paired RoyaleSim−ours
```

**Cost:** about 40 s of CPU per K4S-b48-vs-v1 game. 200 games × 2 engines is about 4.5 CPU-h: roughly 5 min on 80
cores (K = 40 per engine), plus about 16 s of setup per process. Other A specs: `search:unbounded` (KU), `R3a`, `v1`,
`scripted:balanced`, `rgym:patient`; add `--client 16.402` for current rules.
