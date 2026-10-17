# Isolated L16 driver for live-diag

Entry: `l16_diag.py` (`python -m l16_diag`); wrapper `run-l16-diag.sh SOURCE_CHECKOUT WORKERS [driver args]`. Helpers live in `/mpac/sdicks02/jobs/clasher/bot-deckopt2-sam/`, shared frozen factory/model inputs in `/mpac/sdicks02/jobs/clasher/bot-deckopt2/`. Copy the four helper files `sam_common.py`, `l16_diag.py`, `run-l16-diag.sh` and this note to the compute host if absent. Do not modify the running deck-search source or banks.

Use your isolated source checkout containing main `6d90040d8` (or a reviewed descendant) for the new `NoisyPlayer.bind_rsim` hook. This driver's metadata records that checkout/commit; it does not claim the unmodified deck-search source `1a65dcd1`. It verifies the same RoyaleSim identity, native/gamedata pins and all copied model hashes. CLI/syntax are checked; this extra diagnostic driver has not yet run a full-pool noise game. First use a fresh `--cases 1` smoke under your own lease before the full bank.

Exact launch on03/04, after setting `L16_DIAG_SOURCE` to that isolated checkout and choosing unused job paths:

```bash
L16_DIAG_SOURCE=/mpac/sdicks02/repos/clasher-bot-live-diag
L16_DIAG_BASE=$(/mpac/sdicks02/repos/clasher-bot/.venv/bin/python -c 'import os; print(int.from_bytes(os.urandom(6), "little"))')
/mpac/sdicks02/repos/clasher-bot/bot/detach.sh \
  /mpac/sdicks02/jobs/clasher/bot-live-diag/l16-fullpool-noise-20261017.log \
  /mpac/sdicks02/jobs/clasher/bot-live-diag/l16-fullpool-noise-20261017-launch.json \
  bash /mpac/sdicks02/jobs/clasher/bot-deckopt2-sam/run-l16-diag.sh "$L16_DIAG_SOURCE" 4 \
  --out /mpac/sdicks02/jobs/clasher/bot-live-diag/l16-fullpool-noise-20261017 \
  --base "$L16_DIAG_BASE" --cases 100 \
  --opponents LIVE-K4CW-r16,R3a --players base,res --noise clean,live
```

`--cases N` means N paired cases PER policy. The example has200 cases ×2players ×2noise arms =800 games. Case arms share seed, seat, ordered decks and worker/host, with randomized arm order. `--out` must not exist: put detach logs/receipts outside it. No automatic retry/exclusion or existing-out resume is implemented. The driver writes its bank before any game. `--base` accepts decimal or0x integers; the example draws it with os.urandom. All cards and both towers are explicitly16. Own deck is Valkyrie/Archers/Bats/Cannon/Fireball/Zap/MiniPekka/Giant; opponent decks are sampled uniformly from the91 original Battle Log rows, with no C56 projection.

The wrapper selects ROOT/PINS `live16402b-r3`:03/04 root `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3`,01 root `/mpac/sdicks02/jobs/clasher/bot-fullpool/roots/live16402b-r3`. `CLASHER_DELAY_NATIVE_DIR=$ROOT/native`; native SHA `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`; gamedata `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb`. Truth is RoyaleSim0.1.34/client16.402, binary `97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb`. L16 verified without clamping: King7728, Princess4858; ValkyrieHP3047 versus2771 atL15.

Environment: `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`, `PYTHONDONTWRITEBYTECODE=1`, noCUDA, OMP/OPENBLAS/MKL/RAYON threads1. `CLASHER_LOPP_MODELS=$OLD/fullpool/models/lopp-fp`; `BOT_FULLPOOL_POLICIES=v1=$OLD/fullpool/models/ext/main02-fp.pt,R3a=$OLD/fullpool/models/ext/R3a-fp.pt`. `CLASHER_LEVELS_PLACEMENT_PROOF=$OLD/placement-proof.json`. The shared fixed cpu_job lease is WORKERS+2, nice15, in its own detach session. Follow the BOT LEAD's current host/capacity authorization.

## Construction and wrappers

`fullpool_eval.players(rt, LIVE_NAME, opponent, seat, strong_rt=strong)` builds our side with `bot.live.player.make_live_player`, then explicitly scopes its f1a2 fast tier and wraps it in `Observed(Recorder(live))`. R3a/v1 use `bot.eval.headline.make_player(rt, opponent)` with full-pool policy env. Strong is built directly as `LivePlayer(strong_rt,tier='search',wall_ms=None,threads=1,r3a=16,fast_spec=it5s2@0.5375,cutoff_default='it5s2')` using a separate C56-belief Runtime and the extended R3a proposer.

Our Runtime gets `FullPoolBelief` (`fullpool:11433651:freq=b53b02a1fde4`) and copied k1a1 model/f1a2 fast tier; strong gets `LiveBelief`, `c56`, and oldit5s2. Process-wide `BOT_BELIEF_PRIOR` and `CLASHER_LIVE_FAST` are UNSET; do not let the full-pool belief/fast leak into strong. Each side logs/asserts start config.

The approved serial twin begins with the actual live factory and clears deadlines on search, LivePlayer AND its existing Recorder. Native threads1, pool0, chunks4. Explicit f1a2 fallback differs from the default R3a fallback of the named serial bundle; keep that disclosure. Existing serial repeat proof is `$OLD/fullpool/repeat-proof.json`.

The diagnostic driver configures this before wrappers, replaces only `Observed.rec.inner` with `NoisyPlayer(rt,live,noise_arm,label)`, supplies the synthetic noise generator's `opp_deck`, and then puts `PacketRecorder(rt,Observed)` outside. Thus bind_rsim forwards through PacketRecorder→Observed→Recorder→NoisyPlayer, and Recorder's deadline remainsNone. Noise is candidate-seat-only. The clean arm skips NoisyPlayer but keeps PacketRecorder. A wrapper created before deadline clearing can cache200ms and reintroduce wall-lateness—assert the effective outer deadline too.

RoyaleSim `play_match` calls `players[a].bind_rsim(m)` before start. Its original path does not call fair_player.observe or observe_alias. At accepted execution, `RsimMatch.execute` appends `PublicEvent(tick,'card',card)` to `events[1-seat]`, `(tick,card)` to `plays[seat]`, and a seat-tagged dict to public_events. `RsimMatch.information` calls Translator.information; Translator.observation separately builds opponent history/ages/seen IDs from plays[1-seat]. Therefore the new hook must corrupt candidate-local events AND the corresponding opponent plays copy before constructing the packet, and use the same noise decisions for recorder public-event rows. main6d90040d8 supplies this in NoisyPlayer.bind_rsim/act. Do not mutate global truth lists or the other seat.

## Output and gotchas

One JSON per case/player/noise arm under `OUT/rows/`. Top-level fields: id,index,seed,seat,opponent,source_index,own_deck,opponent_deck,player,noise_arm,bank_sha256,started_utc,host,win,draw,issues,failures,live_errors,unmapped,truth_levels,truth_tower_levels,packet_perc,packet_dec,noise_counts,result. Errors keep error/traceback and stop the worker; no row is silently retried or discarded.

`result` includes terminal,winner,ticks,crowns,towers,command_sha256,state_hash,channels,timing,deploy_reasons,translator,public_diagnostics, and **play_log for BOTH seats**, plus command_events. `play_log[seat]` entries are `(tick,card,action,accepted)`; JSON object keys become strings. This is the ground-truth accepted/refused log, not the noisy observed history. In contrast, the production deck-search worker deliberately aggregates then drops these detailed logs to save bytes.

Opponent deploy refusals are normal clean policy behavior; our refusals/native failures/live errors/nonterminal results remain flags. `unmapped_unit:SpearGoblin_Dummy` is the sole declared exception: a Goblin Hut garrison sprite in NO_COUNTERPART, deliberately omitted by the translator. Keep its raw counter; do not broadly ignore unmapped rows. No ExactLevelRoot B is installed; the deployed planner's all-L11/root/belief handling stays unchanged while only simulator truth receivesL16. Cutoff0 is by construction and is not wall200 timing evidence.
