# Early max-level HEADLINE, 2026-10-17 (exploration)

## Current split protocol — amendment 2026-10-17T04:15:44Z (before any fresh rext game)

BOT LEAD directed retention of the live-balance bank rather than a complete15.535 rerun:
- **Headline pool:** R3a+v1 only, **RoyaleSim0.1.34 /16.402 (`rsim16402`)**, existing BASE**3313223055714752**, cases0–299 per opponent/player. Bootstrap within opponent, equal weight over these TWO opponents.
- **Strong row, separate:** `LIVE-K4CW-r16`, same16.402 bank, cases0–149/player, live-diag rl5v10 fast policy. Never pooled.
- **External row, separate:** **rext-bc (15.535 balance, the only rules rext supports)**, RoyaleSim0.1.34 /15.535.29 (`rsim15535`), fresh BASE**2917645611921008** drawn2026-10-17T04:15:44Z, cases0–299/player. Never pooled with16.402 rows. Its paired contrasts use this bank only.
- **Every card and all crown towers remain MAX level16 on BOTH sides in both engines**, `--levels max`. Players remain `K4L-R-gs`, `K4L-R-gs-res`, paired reference `K4C-r16`.
- Full conforming target remains3150:1800 two-opponent headline +450 strong +900 external. Resume preserves all existing valid rows. Final stopped16.402 attempt has860 raw rows: **762 conforming +98 rejected rext entries** (the earlier snapshot had736+42 before stop finished). All98 errors and every original row remain in the job directory; rext16.402 entries are explicitly excluded, never scored as losses. The53 original wrong-fast rows remain separately excluded as before.
- Preflight every player/opponent start at allL16 on both engines before relaunch, verifying expected rext16.402 refusal and successful rext15.535 start. Three detached lease12 blocks,11workers each, max33 gameworkers; each session resumes its16.402 ranges, completes missing16.402 ranges, then executes100 cases/player of the separate rext bank. No other jobs touched.

The rext restriction is explicit in `bot/players/rext_policy.py:RextPolicyPlayer.evaluation_clients` /`start`: `ValueError('rext policies were trained on 15.535.29 rules, not 16.402')`. The harness does not opt into balance transfer. No checkpoint, guard, or player algorithm is changed.

The deck-search it5s2-fast versus live-diag rl5v10 distinction and no-wall fallback-only source audit below continue to apply. Reaction p50/p90 and undefended Giant share remain unavailable in this unmodified headline harness.

External raw data: `03:/mpac/sdicks02/jobs/clasher/bot-hlmax-rext15535-20261017/`. Main16.402 data stay at `03:/mpac/sdicks02/jobs/clasher/bot-hlmax-20261017/`.

## Earlier registration and snapshots (historical; scope revised above)

BASE **3313223055714752**, drawn 2026-10-17T03:30:02Z, committed before any conforming game in `980e9d67199d584226a802251273a7cd8f2a55cc`. Executed source snapshot: `980e9d67199d584226a802251273a7cd8f2a55cc`; selected turn-based bot code unchanged from `2b88b10c7`. Host **127x03** only, 4 detached sessions, 11 workers + parent per shared lease12, configured44 workers (actual admission below), nice15, PYTHONHASHSEED=0, NUMPY_MADVISE_HUGEPAGE=0, BLAS/torch threads1. Data: `03:/mpac/sdicks02/jobs/clasher/bot-hlmax-20261017/` (`strong-0`…`strong-3`, `pool-0`…`pool-3`).

Engine **RoyaleSim 0.1.34, 16.402 (`rsim16402`)** via `bot.eval.headline --levels max`: every card and all crown towers at **level16 on both sides**. Direct reset probe gave King HP7728 and Princess HP4858 on both seats (L11 control4824/3052). The planner remains the frozen r1-total model; no level-aware search override was added. This changes environment levels, not the selected bot algorithm.

Players: `K4L-R-gs`, `K4L-R-gs-res` (exact parsed reserve token; λ=.015, deck-derived cheapest ground answer), paired reference `K4C-r16`. C56 `x4s_setup(i, BASE)`; cases0–299 per player/opponent vs R3a,v1,rext-bc. Strong opponent `LIVE-K4CW-r16`, cases0–149 per player, is **separate and never pooled**. Full target3150 games (2700 pool,450 strong).

Strong fast policy is live-diag's **rl5 v10**, `student:/mpac/sdicks02/jobs/clasher/bot-rl03/ckpt/policy-00010.pt@0.5375`, SHA256 `e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19`. The deck-search runs used an **it5s2-fast LIVE-K4CW-r16**. Code inspection: the no-wall name parses to `wall_ms=None, threads=1` (`bot/live/player.py:parse_wall_name`). Fast action is passed only as default/fallback, not as candidate/coarse/refine proposals; those come from R3a and its top16 reranking (`_WallMulti.act`, `CandidateSearchPlayer.start`). With no wall and no rollout budget there is no cutoff; `sdefault.apply_default` requires `stats.hit`. Thus the fast tier should not change a normally completed search. It can matter for empty-score fallback, search exceptions, or disabled search. This is a source-path conclusion, not a command-hash parity claim.

Provenance: native-total-r1 `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`; learned-opponent pool `1e4bb6a01e06545b02a4f1632d564ef1dd76ceb9df2081273bd869af678b3f9e`. Rext weights remain under `/mpac/sdicks02/jobs/clasher/bot-ext2-models`, internal evaluation only, never committed. Full source/runtime/checkpoint hashes are in the job's `provenance.txt`.

**Correction retained:** original bank2464432084633360 (pre-registration `c09f2384a588fc7eb2da9dece4e47f6809cad650`) produced53 nonconforming strong rows with generic it5s2-fast before correction. Only individually verified owned PIDs were signalled. Those rows/logs/receipts are preserved under `nonconforming-it5s2/`, excluded from every statistic below. No pool games had run. BOT LEAD accepted the correction and requested standardisation on the documented live-diag rl5 v10 environment. The first n22 snapshot sent to BOT LEAD is superseded.

Statistics: score win1/draw.5/loss0; 4000 bootstrap draws, Python Random seed0, percentile95%CI. Pool is the equal-weight mean of R3a,v1,rext-bc, resampling games within opponent. Paired deltas use common case indices (A−B) within each opponent; the paired pool resamples those differences within opponent, equally weighted. Partial snapshots are descriptive and may have uneven case coverage; read the complete snapshot for the requested full bank.

Reaction p50/p90 and undefended Giant-push share are **not recorded by the unmodified headline harness**. Its RoyaleSim call does not request verbose play logs or live-diag perception traces; those metrics cannot be recovered from the score rows. No substitute is inferred.

### 2026-10-17T03:33:52Z — PARTIAL, running (25/3150 rows)

Errors 0; duplicates 0; nonterminal 0; partial JSON lines 0. Engines `{'rsim16402': 25}`; levels `{'card16-tower16': 25}`.

| player | pool R3a+v1+rext-bc [95% CI] | R3a | v1 | rext-bc | strong LIVE-K4CW-r16 [95% CI], separate |
|---|---|---|---|---|---|
| K4L-R-gs | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | 0.6000 [0.4000, 0.8000] (n=25) |
| K4L-R-gs-res | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) |
| K4C-r16 | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) |

| paired delta | pool [95% CI] | R3a | v1 | rext-bc | strong, separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | pending | pending | pending | pending | pending |
| K4L-R-gs minus K4C-r16 | pending | pending | pending | pending | pending |

Snapshot JSON: `summary.json` in the job directory. No change of champion is inferred from partial rows.

### 2026-10-17T03:40:38Z — PARTIAL, running (110/3150 rows)

Errors 0; duplicates 0; nonterminal 0; partial JSON lines 0. Engines `{'rsim16402': 110}`; levels `{'card16-tower16': 110}`.

| player | pool R3a+v1+rext-bc [95% CI] | R3a | v1 | rext-bc | strong LIVE-K4CW-r16 [95% CI], separate |
|---|---|---|---|---|---|
| K4L-R-gs | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | 0.5340 [0.4369, 0.6311] (n=103) |
| K4L-R-gs-res | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | 0.4286 [0.1429, 0.8571] (n=7) |
| K4C-r16 | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) |

| paired delta | pool [95% CI] | R3a | v1 | rext-bc | strong, separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | pending | pending | pending | pending | -0.2857 [-0.5714, 0.0000] (paired n=7) |
| K4L-R-gs minus K4C-r16 | pending | pending | pending | pending | pending |

Snapshot JSON: `summary.json` in the job directory. No change of champion is inferred from partial rows.

### 2026-10-17T03:49:38Z — PARTIAL, running (222/3150 rows)

Errors 0; duplicates 0; nonterminal 0; partial JSON lines 0. Engines `{'rsim16402': 222}`; levels `{'card16-tower16': 222}`.

| player | pool R3a+v1+rext-bc [95% CI] | R3a | v1 | rext-bc | strong LIVE-K4CW-r16 [95% CI], separate |
|---|---|---|---|---|---|
| K4L-R-gs | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | 0.5315 [0.4414, 0.6216] (n=111) |
| K4L-R-gs-res | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | 0.5882 [0.4902, 0.6863] (n=102) |
| K4C-r16 | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | 0.4444 [0.1111, 0.7778] (n=9) |

| paired delta | pool [95% CI] | R3a | v1 | rext-bc | strong, separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | pending | pending | pending | pending | 0.0686 [-0.0392, 0.1765] (paired n=102) |
| K4L-R-gs minus K4C-r16 | pending | pending | pending | pending | 0.1111 [-0.3333, 0.5556] (paired n=9) |

Snapshot JSON: `summary.json` in the job directory. No change of champion is inferred from partial rows.


Admission observed at snapshot time: `{"0": {"lease": "12 3976664", "receipt": {"launched_at_utc": "2026-10-17T03:30:18Z", "pgid": 3976664, "pid": 3976664}}, "1": {"lease": "12 3976689", "receipt": {"launched_at_utc": "2026-10-17T03:30:18Z", "pgid": 3976689, "pid": 3976689}}, "2": {"lease": "12 3976713", "receipt": {"launched_at_utc": "2026-10-17T03:30:19Z", "pgid": 3976713, "pid": 3976713}}, "3": {"lease": null, "receipt": {"launched_at_utc": "2026-10-17T03:47:39Z", "pgid": 4077624, "pid": 4077624}}}`. Configured capacity44 workers; blocks0–2 were admitted at the corrected start, while block3 waited at default cap105, then was retried under documented 03 cap110 at2026-10-17T03:47:39Z (old waiting receipt retained). No other jobs or host cap files changed.

### 2026-10-17T04:01:40Z — PARTIAL, running (361/3150 rows)

Errors 0; duplicates 0; nonterminal 0; partial JSON lines 0. Engines `{'rsim16402': 361}`; levels `{'card16-tower16': 361}`.

| player | pool R3a+v1+rext-bc [95% CI] | R3a | v1 | rext-bc | strong LIVE-K4CW-r16 [95% CI], separate |
|---|---|---|---|---|---|
| K4L-R-gs | pending (n=0) | 0.7857 [0.6071, 0.9286] (n=28) | pending (n=0) | pending (n=0) | 0.5315 [0.4414, 0.6216] (n=111) |
| K4L-R-gs-res | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | 0.6036 [0.5135, 0.6937] (n=111) |
| K4C-r16 | pending (n=0) | pending (n=0) | pending (n=0) | pending (n=0) | 0.4234 [0.3333, 0.5135] (n=111) |

| paired delta | pool [95% CI] | R3a | v1 | rext-bc | strong, separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | pending | pending | pending | pending | 0.0721 [-0.0270, 0.1712] (paired n=111) |
| K4L-R-gs minus K4C-r16 | pending | pending | pending | pending | 0.1081 [0.0090, 0.2072] (paired n=111) |

Snapshot JSON: `summary.json` in the job directory. No change of champion is inferred from partial rows.


Admission observed at snapshot time: `{"0": {"lease": "12 3976664", "receipt": {"launched_at_utc": "2026-10-17T03:30:18Z", "pgid": 3976664, "pid": 3976664}}, "1": {"lease": "12 3976689", "receipt": {"launched_at_utc": "2026-10-17T03:30:18Z", "pgid": 3976689, "pid": 3976689}}, "2": {"lease": "12 3976713", "receipt": {"launched_at_utc": "2026-10-17T03:30:19Z", "pgid": 3976713, "pid": 3976713}}, "3": {"lease": null, "receipt": {"launched_at_utc": "2026-10-17T03:47:39Z", "pgid": 4077624, "pid": 4077624}}}`. Configured capacity44 workers; blocks0–2 were admitted at the corrected start, while block3 waited at default cap105, then was retried under documented 03 cap110 at2026-10-17T03:47:39Z (old waiting receipt retained). No other jobs or host cap files changed.


Scheduling amendment 2026-10-17T04:00:52Z: the verified, never-admitted block3 waiter (PID4077624) was cancelled before any of its games. Its same-bank cases are appended inside the three existing lease12 sessions, preserving a 33-worker maximum: block b=0,1,2 adds strong start111+13b/count13 and pool start225+25b/count25. The three sessions each execute1050 target games; total remains3150, with the same candidate/opponent/index keys and no algorithm, runtime, level, or bank change. New output directories: strong-r0…r2 and pool-r0…r2. Original blocked receipt retained. This avoids a separate late 11-worker tail without taking resources from other jobs.


## Split-protocol results

Fresh rext registration precedes any rext15.535 game. Subsequent snapshots use the current split protocol above.

### 2026-10-17T04:19:01Z — split protocol, PARTIAL, running (762/3150)

Conforming-target rows762/3150: main16.402=762/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 762}`, levels`{'card16-tower16': 762}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8318 [0.7967, 0.8656] (n=427) | 0.7378 [0.6800, 0.7911] (n=225) | 0.9257 [0.8911, 0.9604] (n=202) | 0.5315 [0.4414, 0.6216] (n=111) | pending (n=0) |
| K4L-R-gs-res | pending (n=0) | 1.0000 [1.0000, 1.0000] (n=2) | pending (n=0) | 0.6036 [0.5135, 0.6937] (n=111) | pending (n=0) |
| K4C-r16 | pending (n=0) | pending (n=0) | pending (n=0) | 0.4234 [0.3333, 0.5135] (n=111) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | pending | 0.0000 [0.0000, 0.0000] (paired n=2) | pending | 0.0721 [-0.0270, 0.1712] (paired n=111) | pending |
| K4L-R-gs minus K4C-r16 | pending | pending | pending | 0.1081 [0.0090, 0.2072] (paired n=111) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T04:29:10Z — split protocol, PARTIAL, running (884/3150)

Conforming-target rows884/3150: main16.402=884/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 884}`, levels`{'card16-tower16': 884}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8327 [0.7976, 0.8664] (n=432) | 0.7378 [0.6800, 0.7911] (n=225) | 0.9275 [0.8889, 0.9614] (n=207) | 0.5333 [0.4533, 0.6133] (n=150) | pending (n=0) |
| K4L-R-gs-res | pending (n=0) | 1.0000 [1.0000, 1.0000] (n=2) | pending (n=0) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | pending (n=0) | pending (n=0) | pending (n=0) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | pending | 0.0000 [0.0000, 0.0000] (paired n=2) | pending | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | pending | pending | pending | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T04:37:26Z — split protocol, PARTIAL, running (1119/3150)

Conforming-target rows1119/3150: main16.402=1119/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 1119}`, levels`{'card16-tower16': 1119}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8311 [0.7956, 0.8644] (n=450) | 0.7378 [0.6800, 0.7911] (n=225) | 0.9244 [0.8889, 0.9556] (n=225) | 0.5333 [0.4533, 0.6133] (n=150) | pending (n=0) |
| K4L-R-gs-res | 0.8157 [0.6397, 0.9202] (n=219) | 0.7981 [0.7465, 0.8498] (n=213) | 0.8333 [0.5000, 1.0000] (n=6) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | pending (n=0) | pending (n=0) | pending (n=0) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | -0.0552 [-0.2312, 0.0493] (paired n=213,6) | 0.0563 [0.0000, 0.1174] (paired n=213) | -0.1667 [-0.5000, 0.0000] (paired n=6) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | pending | pending | pending | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T04:42:42Z — split protocol, PARTIAL, running (1286/3150)

Conforming-target rows1286/3150: main16.402=1286/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 1286}`, levels`{'card16-tower16': 1286}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8311 [0.7956, 0.8644] (n=450) | 0.7378 [0.6800, 0.7911] (n=225) | 0.9244 [0.8889, 0.9556] (n=225) | 0.5333 [0.4533, 0.6133] (n=150) | pending (n=0) |
| K4L-R-gs-res | 0.8587 [0.8236, 0.8916] (n=386) | 0.8044 [0.7511, 0.8533] (n=225) | 0.9130 [0.8696, 0.9503] (n=161) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | pending (n=0) | pending (n=0) | pending (n=0) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0209 [-0.0142, 0.0564] (paired n=225,161) | 0.0667 [0.0133, 0.1200] (paired n=225) | -0.0248 [-0.0683, 0.0186] (paired n=161) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | pending | pending | pending | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T04:50:46Z — split protocol, PARTIAL, running (1527/3150)

Conforming-target rows1527/3150: main16.402=1527/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 1527}`, levels`{'card16-tower16': 1527}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8311 [0.7956, 0.8644] (n=450) | 0.7378 [0.6800, 0.7911] (n=225) | 0.9244 [0.8889, 0.9556] (n=225) | 0.5333 [0.4533, 0.6133] (n=150) | pending (n=0) |
| K4L-R-gs-res | 0.8622 [0.8311, 0.8933] (n=450) | 0.8044 [0.7511, 0.8533] (n=225) | 0.9200 [0.8800, 0.9511] (n=225) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | 0.8714 [0.8371, 0.9029] (n=177) | 0.7429 [0.6743, 0.8057] (n=175) | 1.0000 [1.0000, 1.0000] (n=2) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0311 [-0.0022, 0.0667] (paired n=225,225) | 0.0667 [0.0133, 0.1200] (paired n=225) | -0.0044 [-0.0489, 0.0356] (paired n=225) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | 0.0000 [-0.0371, 0.0343] (paired n=175,2) | 0.0000 [-0.0743, 0.0743] (paired n=175) | 0.0000 [0.0000, 0.0000] (paired n=2) | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T04:55:43Z — split protocol, PARTIAL, running (1677/3150)

Conforming-target rows1677/3150: main16.402=1677/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 1677}`, levels`{'card16-tower16': 1677}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8311 [0.7956, 0.8644] (n=450) | 0.7378 [0.6800, 0.7911] (n=225) | 0.9244 [0.8889, 0.9556] (n=225) | 0.5333 [0.4533, 0.6133] (n=150) | pending (n=0) |
| K4L-R-gs-res | 0.8622 [0.8311, 0.8933] (n=450) | 0.8044 [0.7511, 0.8533] (n=225) | 0.9200 [0.8800, 0.9511] (n=225) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | 0.8484 [0.8101, 0.8826] (n=327) | 0.7556 [0.7022, 0.8133] (n=225) | 0.9412 [0.8922, 0.9804] (n=102) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0311 [-0.0022, 0.0667] (paired n=225,225) | 0.0667 [0.0133, 0.1200] (paired n=225) | -0.0044 [-0.0489, 0.0356] (paired n=225) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | 0.0058 [-0.0374, 0.0507] (paired n=225,102) | -0.0178 [-0.0889, 0.0489] (paired n=225) | 0.0294 [-0.0294, 0.0882] (paired n=102) | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T05:01:23Z — split protocol, PARTIAL, running (1809/3150)

Conforming-target rows1809/3150: main16.402=1809/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 1809}`, levels`{'card16-tower16': 1809}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8276 [0.7932, 0.8601] (n=459) | 0.7308 [0.6709, 0.7863] (n=234) | 0.9244 [0.8889, 0.9556] (n=225) | 0.5333 [0.4533, 0.6133] (n=150) | pending (n=0) |
| K4L-R-gs-res | 0.8622 [0.8311, 0.8933] (n=450) | 0.8044 [0.7511, 0.8533] (n=225) | 0.9200 [0.8800, 0.9511] (n=225) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | 0.8400 [0.8067, 0.8733] (n=450) | 0.7556 [0.7022, 0.8133] (n=225) | 0.9244 [0.8889, 0.9556] (n=225) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0311 [-0.0022, 0.0667] (paired n=225,225) | 0.0667 [0.0133, 0.1200] (paired n=225) | -0.0044 [-0.0489, 0.0356] (paired n=225) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | -0.0089 [-0.0511, 0.0311] (paired n=225,225) | -0.0178 [-0.0889, 0.0489] (paired n=225) | 0.0000 [-0.0489, 0.0489] (paired n=225) | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T05:07:43Z — split protocol, PARTIAL, running (1988/3150)

Conforming-target rows1988/3150: main16.402=1988/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 1988}`, levels`{'card16-tower16': 1988}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8383 [0.8100, 0.8667] (n=600) | 0.7500 [0.7000, 0.8000] (n=300) | 0.9267 [0.8967, 0.9533] (n=300) | 0.5333 [0.4533, 0.6133] (n=150) | pending (n=0) |
| K4L-R-gs-res | 0.8687 [0.8383, 0.8976] (n=488) | 0.8175 [0.7719, 0.8631] (n=263) | 0.9200 [0.8800, 0.9511] (n=225) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | 0.8400 [0.8067, 0.8733] (n=450) | 0.7556 [0.7022, 0.8133] (n=225) | 0.9244 [0.8889, 0.9556] (n=225) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0358 [0.0019, 0.0694] (paired n=263,225) | 0.0760 [0.0266, 0.1293] (paired n=263) | -0.0044 [-0.0489, 0.0356] (paired n=225) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | -0.0089 [-0.0511, 0.0311] (paired n=225,225) | -0.0178 [-0.0889, 0.0489] (paired n=225) | 0.0000 [-0.0489, 0.0489] (paired n=225) | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T05:13:56Z — split protocol, PARTIAL, running (2173/3150)

Conforming-target rows2173/3150: main16.402=2173/2250; separate rext15.535=0/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 2173}`, levels`{'card16-tower16': 2173}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8383 [0.8100, 0.8667] (n=600) | 0.7500 [0.7000, 0.8000] (n=300) | 0.9267 [0.8967, 0.9533] (n=300) | 0.5333 [0.4533, 0.6133] (n=150) | pending (n=0) |
| K4L-R-gs-res | 0.8633 [0.8350, 0.8917] (n=600) | 0.8033 [0.7600, 0.8467] (n=300) | 0.9233 [0.8933, 0.9533] (n=300) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | 0.8393 [0.8064, 0.8690] (n=523) | 0.7587 [0.7063, 0.8077] (n=286) | 0.9198 [0.8819, 0.9494] (n=237) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0250 [-0.0050, 0.0550] (paired n=300,300) | 0.0533 [0.0033, 0.1033] (paired n=300) | -0.0033 [-0.0367, 0.0300] (paired n=300) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | -0.0084 [-0.0479, 0.0309] (paired n=286,237) | -0.0210 [-0.0804, 0.0420] (paired n=286) | 0.0042 [-0.0422, 0.0506] (paired n=237) | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T05:17:15Z — split protocol, PARTIAL, running (2258/3150)

Conforming-target rows2258/3150: main16.402=2248/2250; separate rext15.535=10/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 2248, 'rsim15535': 10}`, levels`{'card16-tower16': 2258}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8383 [0.8100, 0.8667] (n=600) | 0.7500 [0.7000, 0.8000] (n=300) | 0.9267 [0.8967, 0.9533] (n=300) | 0.5333 [0.4533, 0.6133] (n=150) | 1.0000 [1.0000, 1.0000] (n=10) |
| K4L-R-gs-res | 0.8633 [0.8350, 0.8917] (n=600) | 0.8033 [0.7600, 0.8467] (n=300) | 0.9233 [0.8933, 0.9533] (n=300) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | 0.8330 [0.8030, 0.8615] (n=598) | 0.7567 [0.7067, 0.8033] (n=300) | 0.9094 [0.8758, 0.9396] (n=298) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0250 [-0.0050, 0.0550] (paired n=300,300) | 0.0533 [0.0033, 0.1033] (paired n=300) | -0.0033 [-0.0367, 0.0300] (paired n=300) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | 0.0051 [-0.0300, 0.0418] (paired n=300,298) | -0.0067 [-0.0667, 0.0533] (paired n=300) | 0.0168 [-0.0235, 0.0570] (paired n=298) | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T05:18:56Z — split protocol, PARTIAL, running (2305/3150)

Conforming-target rows2305/3150: main16.402=2250/2250; separate rext15.535=55/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 2250, 'rsim15535': 55}`, levels`{'card16-tower16': 2305}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8383 [0.8100, 0.8667] (n=600) | 0.7500 [0.7000, 0.8000] (n=300) | 0.9267 [0.8967, 0.9533] (n=300) | 0.5333 [0.4533, 0.6133] (n=150) | 0.9091 [0.8182, 0.9818] (n=55) |
| K4L-R-gs-res | 0.8633 [0.8350, 0.8917] (n=600) | 0.8033 [0.7600, 0.8467] (n=300) | 0.9233 [0.8933, 0.9533] (n=300) | 0.5933 [0.5133, 0.6733] (n=150) | pending (n=0) |
| K4C-r16 | 0.8333 [0.8033, 0.8633] (n=600) | 0.7567 [0.7067, 0.8033] (n=300) | 0.9100 [0.8767, 0.9400] (n=300) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0250 [-0.0050, 0.0550] (paired n=300,300) | 0.0533 [0.0033, 0.1033] (paired n=300) | -0.0033 [-0.0367, 0.0300] (paired n=300) | 0.0600 [-0.0267, 0.1467] (paired n=150) | pending |
| K4L-R-gs minus K4C-r16 | 0.0050 [-0.0300, 0.0417] (paired n=300,300) | -0.0067 [-0.0667, 0.0533] (paired n=300) | 0.0167 [-0.0233, 0.0567] (paired n=300) | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

### 2026-10-17T05:24:09Z — split protocol, PARTIAL, running (2536/3150)

Conforming-target rows2536/3150: main16.402=2250/2250; separate rext15.535=286/900. Errors0, duplicates0, nonterminal0, invalid engine/level/seed/score rows0, partial JSON lines0. Retained/excluded rext16.402 rows98 (errors98); these are not losses. Engines`{'rsim16402': 2250, 'rsim15535': 286}`, levels`{'card16-tower16': 2536}`.

| player | HEADLINE R3a+v1,16.402 [95%CI] | R3a | v1 | strong LIVE-K4CW-r16,16.402,separate | rext-bc (15.535 balance, the only rules rext supports),separate |
|---|---|---|---|---|---|
| K4L-R-gs | 0.8383 [0.8100, 0.8667] (n=600) | 0.7500 [0.7000, 0.8000] (n=300) | 0.9267 [0.8967, 0.9533] (n=300) | 0.5333 [0.4533, 0.6133] (n=150) | 0.9363 [0.9064, 0.9625] (n=267) |
| K4L-R-gs-res | 0.8633 [0.8350, 0.8917] (n=600) | 0.8033 [0.7600, 0.8467] (n=300) | 0.9233 [0.8933, 0.9533] (n=300) | 0.5933 [0.5133, 0.6733] (n=150) | 0.9474 [0.8421, 1.0000] (n=19) |
| K4C-r16 | 0.8333 [0.8033, 0.8633] (n=600) | 0.7567 [0.7067, 0.8033] (n=300) | 0.9100 [0.8767, 0.9400] (n=300) | 0.4267 [0.3467, 0.5067] (n=150) | pending (n=0) |

| paired A−B | HEADLINE pool,16.402 | R3a | v1 | strong16.402,separate | rext15.535,separate |
|---|---|---|---|---|---|
| K4L-R-gs-res minus K4L-R-gs | 0.0250 [-0.0050, 0.0550] (paired n=300,300) | 0.0533 [0.0033, 0.1033] (paired n=300) | -0.0033 [-0.0367, 0.0300] (paired n=300) | 0.0600 [-0.0267, 0.1467] (paired n=150) | 0.0000 [-0.1579, 0.1579] (paired n=19) |
| K4L-R-gs minus K4C-r16 | 0.0050 [-0.0300, 0.0417] (paired n=300,300) | -0.0067 [-0.0667, 0.0533] (paired n=300) | 0.0167 [-0.0233, 0.0567] (paired n=300) | 0.1067 [0.0200, 0.2000] (paired n=150) | pending |

Banks: main3313223055714752 (preregistered980e9d671), external2917645611921008 (fresh preregistration/split amendmente9976024f). Main pool uses ONLY R3a+v1 on16.402. Strong16.402 and rext15.535 are separate rows, never pooled. Bootstrap4000 draws/seed0/within-opponent/equal weights over the TWO main opponents. External paired contrasts use the external bank only.

Admission at snapshot: `{"0": {"lease": "12 58231", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58231, "pid": 58231}}, "1": {"lease": "12 58274", "receipt": {"launched_at_utc": "2026-10-17T04:18:10Z", "pgid": 58274, "pid": 58274}}, "2": {"lease": "12 58301", "receipt": {"launched_at_utc": "2026-10-17T04:18:11Z", "pgid": 58301, "pid": 58301}}}`. Each of three owned detach sessions holds shared lease12, runs11 gameworkers, resumes only missing16.402 keys then completes its fresh100-case/player rext15.535 shard; max33 gameworkers. Preflight `preflight-split.json`:13 successful starts at allL16 plus expected rext16.402 rejection; no Battle-state changes during starts. Reaction p50/p90 and undefended Giant-push share are not retained by this harness.

