# Daily max-level HEADLINE, 2026-10-17b (exploration)

Protocol registered before scored games. BASE registration commit `d7e49eeed4cc590338b6b63e424596d094120a60`. Source snapshot begins at `66fe995449894c02efaa4da646a18a128a23afd7`; the only production harness change is the separately committed alias hook, `4de1083dabdc240b0916ebcc1436af3e6856362d`.

res-wint omitted (landed on main after launch). The scored blocks launched at 2026-10-17T13:16:41Z; BOT LEAD subsequently reported wint merged at `1540f153168696d02e6bbfc347bc4c635c1ea0fe` and directed this already-running bank to retain only (a) and (c), with no restart and no later addition of (b). Its DD1 2x2 result stands; BOT LEAD will run it separately.

## Protocol and players

- Quoted candidate (a): `K4L-R-gs-mk1a1-res`, the current live full-pool player's serial twin.
- Reference (c): **K4L-R-gs-res (C56, aliased in full-pool runtime)**; exact accepted factory name `aliased:K4L-R-gs-mpool-res`. The alias accepts the reserve token, retains the original pool rollout model, and replaces its belief with the live C56 catalog belief. No fallback to the non-reserve arm was needed.
- Both players and all opponents share the deployed bundle environment: `live16402b-r3`, extended v1/R3a, full-pool rollout-model directory, and `BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4`. The alias restores its C56 belief itself. `bot/fullpool/run/env.sh` was compared byte for byte with the full-pool owner's file, then sourced before exporting eval overrides. ROOT/PINS are its required inputs. Bundle runtime selection matches `reports/bot/fullpool/BUNDLE.md`.
- `bot.eval.headline --levels max`: every card and all crown towers L16 on BOTH sides. C56 X4S decks, seed BASE+i, candidate seat i%2; the original lag, polling, search, abilities-off and terminal scoring protocol is retained.
- **HEADLINE pool:** RoyaleSim0.1.34 /16.402 (`rsim16402`), R3a+v1, 400 cases per opponent/player, equal opponent weights. **STRONG:** separate LIVE-K4CW-r16, 150 cases/player on the same bank, live-diag's rl5 v10 fast policy. **rext-bc:** separate 15.535.29 (`rsim15535`), 400 cases/player, its own fresh bank. No pooling across these rows.
- Win1/draw0.5/loss0; 4000 bootstrap draws, Python Random seed0, percentile endpoints sorted[100] and sorted[3899], resampling within opponent. Paired a−c uses the same indices, resampled within opponent. This is the morning worker's statistical implementation and split protocol, with the requested sample sizes. Row (b) and its paired contrast are omitted by BOT LEAD instruction.
- Reaction p50/p90 and undefended-Giant share: **not recorded by harness**. No inference or substitute.

## Fresh banks

| row | BASE | draw time from `date -u` |
|---|---|---|
| main | 3905522882501520 | Sat Oct 17 13:03:14 UTC 2026 |
| rext | 2701262821741664 | Sat Oct 17 13:03:14 UTC 2026 |

## Preflight and alias correction

Both players parsed and started successfully on both case indices and both rulesets, with all reset card levels16 and tower_levels[16,16]. Both seats: KingHP7728, PrincessHP4858/4858. rext-bc started successfully on 15.535; no pool workaround was used. The first copied source omitted pinned ARENA-CARDS.md and produced startup FileNotFoundErrors; supplying that unchanged pinned source file resolved them before validation/evaluation. The rejected startup logs are retained; they are not game results.

The RoyaleSim loop lacked the native loop’s existing observe_alias integration. Fix `4de1083dabdc240b0916ebcc1436af3e6856362d` adds only the same post-start per-seat hook lookup, alias.info before reservation, and alias.recorder when building PublicView. A dedicated unit test passes all three cases (each aliased seat and no alias). Before/after rsim16402/L16 parity: 10 cases each for K4L-R-gs-mk1a1-res, R3a, LIVE-K4CW-r16; **30/30 identical command hashes**, with identical final-state hashes, winners and tick counts as well. Two positive cases (opposite seats) show MegaMinion token225→Minions238 in entity, history and seen-card IDs; Information.events and recorder events also name Minions. Validation used the fixed HEADLINE bank, not the fresh scoring bank. The fix and unit test were committed alone via a private index with secret scan, before scored games.

Raw validation receipts: `04,08:/mpac/sdicks02/jobs/clasher/bot-hl-20261017b/` (`parity-*.jsonl`, `alias-positive.json`, `preflight.json`). Command hashes are retained there.

## Provenance

| file | SHA256 (command-derived) |
|---|---|
| `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3/native/clasher_core.abi3.so` | `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1` |
| `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3/gamedata.json` | `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb` |
| `/mpac/sdicks02/jobs/clasher/bot-hl-20261017b/source/bot/fullpool/run/env.sh` | `04ec25dfd00b04296474b9f7c3d40d65c642fa7972e65f6b846da38cbb1597e8` |
| `/mpac/sdicks02/jobs/clasher/bot-hl-20261017b/strong/policy-00010.pt` | `e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19` |
| `/mpac/sdicks02/jobs/clasher/bot-fullpool/lopp-fp/k1a1.npz` | `477590389c0d6906c5b3b80c131f910dabd286bfde21c990d50b460c54c5a8d3` |
| `/mpac/sdicks02/jobs/clasher/bot-fullpool/lopp-fp/pool.npz` | `1e4bb6a01e06545b02a4f1632d564ef1dd76ceb9df2081273bd869af678b3f9e` |

Strong-policy bytes were copied unchanged from 03’s documented rl5 v10 checkpoint into the eval job directory; their hash matches the morning run. Rext weights stay internal under `/mpac/sdicks02/jobs/clasher/bot-ext2-models`; no weights, data or game bytes are committed.

## Execution

Target2700 scored games:1600 pool,300 strong,800 rext. Hosts04/08; four separately detached blocks,10 game workers each (40 maximum total), lease11 each through the required shared cpu_job.sh at cap105, nice15. Main and strong case shards are disjoint; each rext shard uses its separate BASE. Every process sets hashseed0, hugepage advice0 and all numerical/torch thread counts1; NUMBA_CACHE_DIR is writable under its own job directory. All hosts have been checked with who; no console students were present. Other jobs are untouched. Raw main data: `04,08:/mpac/sdicks02/jobs/clasher/bot-hl-20261017b/`; raw rext data: `04,08:/mpac/sdicks02/jobs/clasher/bot-hl-rext-20261017b/`.

Only COMPLETE rows enter HEADLINE.md. Interim score snapshots, if needed, are limited to one per ~2h in this write-up. Complete rows are reported as soon as they exist. Fixed-bank v3 for the new candidate is considered only after all fresh rows finish and only if CPU permits; no command-hash re-confirmation is claimed.

## COMPLETE STRONG cell (a) — 2026-10-17T13:34:53Z

K4L-R-gs-mk1a1-res (quoted), exact factory `K4L-R-gs-mk1a1-res`: **0.6467 [0.5733, 0.7200]**, 150 unique terminal games, no errors/duplicates/invalid rows. This is the final complete cell; the other player and paired contrast follow separately when complete.

## COMPLETE STRONG — 2026-10-17T13:49:08Z

| player | score [bootstrap95%CI] | games |
|---|---|---|
| K4L-R-gs-mk1a1-res (quoted) (`K4L-R-gs-mk1a1-res`) | 0.6467 [0.5733, 0.7200] | 150 |
| K4L-R-gs-res (C56, aliased in full-pool runtime) (`aliased:K4L-R-gs-mpool-res`) | 0.6400 [0.5667, 0.7200] | 150 |

Paired a−c: **0.0067 [-0.0800, 0.0933]**.

Complete audit for this row: 300/300 unique expected keys; every result terminal, correct ruleset/BASE/seat/levels/score; no errors or duplicates. Reaction metrics: not recorded by harness.

## Load management

04 had load spikes above~110–125 while the eval worker count stayed fixed. Only verified owned groups were temporarily SIGSTOP/SIGCONT’d. Game states and CPU leases were retained; no games restarted and no other jobs were touched. Wall-duration bookkeeping includes these pauses; scored players have no wall deadline. Receipts: `04:bot-hl-20261017b/owned-signals.jsonl`.

Completed pause time: block0 260s, block1 131s. All groups resumed.

2026-10-17T14:20:33Z STOP blocks 0,1; load1=121.53

2026-10-17T14:21:39Z CONT blocks 0; load1=88.64

2026-10-17T14:22:44Z CONT blocks 1; load1=85.19

2026-10-17T14:32:17Z STOP blocks 0; load1=108.26

2026-10-17T14:35:31Z CONT blocks 0; load1=95.25

## COMPLETE POOL cell (a) — 2026-10-17T14:25:50Z

K4L-R-gs-mk1a1-res (quoted), exact factory `K4L-R-gs-mk1a1-res`: **0.8825 [0.8600, 0.9038]**, 800 unique terminal games, no errors/duplicates/invalid rows. This is the final complete cell; the other player and paired contrast follow separately when complete.

## COMPLETE POOL — 2026-10-17T14:55:04Z

| player | score [bootstrap95%CI] | games |
|---|---|---|
| K4L-R-gs-mk1a1-res (quoted) (`K4L-R-gs-mk1a1-res`) | 0.8825 [0.8600, 0.9038] | 800 |
| K4L-R-gs-res (C56, aliased in full-pool runtime) (`aliased:K4L-R-gs-mpool-res`) | 0.8762 [0.8525, 0.8987] | 800 |

Paired a−c: **0.0063 [-0.0213, 0.0338]**.

| opponent | quoted a | reference c | paired a−c |
|---|---|---|---|
| R3a | 0.8200 [0.7825, 0.8575] | 0.8200 [0.7825, 0.8575] | 0.0000 [-0.0450, 0.0450] |
| v1 | 0.9450 [0.9200, 0.9650] | 0.9325 [0.9075, 0.9550] | 0.0125 [-0.0175, 0.0425] |

Complete audit for this row: 1600/1600 unique expected keys; every result terminal, correct ruleset/BASE/seat/levels/score; no errors or duplicates. Reaction metrics: not recorded by harness.

## COMPLETE REXT cell (a) — 2026-10-17T15:09:04Z

K4L-R-gs-mk1a1-res (quoted), exact factory `K4L-R-gs-mk1a1-res`: **0.9425 [0.9200, 0.9650]**, 400 unique terminal games, no errors/duplicates/invalid rows. This is the final complete cell; the other player and paired contrast follow separately when complete.

## COMPLETE REXT — 2026-10-17T15:23:18Z

| player | score [bootstrap95%CI] | games |
|---|---|---|
| K4L-R-gs-mk1a1-res (quoted) (`K4L-R-gs-mk1a1-res`) | 0.9425 [0.9200, 0.9650] | 400 |
| K4L-R-gs-res (C56, aliased in full-pool runtime) (`aliased:K4L-R-gs-mpool-res`) | 0.9325 [0.9075, 0.9550] | 400 |

Paired a−c: **0.0100 [-0.0225, 0.0425]**.

Complete audit for this row: 800/800 unique expected keys; every result terminal, correct ruleset/BASE/seat/levels/score; no errors or duplicates. Reaction metrics: not recorded by harness.
