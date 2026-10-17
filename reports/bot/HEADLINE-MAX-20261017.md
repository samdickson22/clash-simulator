# Early max-level HEADLINE, 2026-10-17 (exploration)

BASE **3313223055714752**, drawn 2026-10-17T03:30:02Z, committed before any conforming game in `980e9d67199d584226a802251273a7cd8f2a55cc`. Executed source snapshot: `980e9d67199d584226a802251273a7cd8f2a55cc`; selected turn-based bot code unchanged from `2b88b10c7`. Host **127x03** only, 4 detached sessions, 11 workers + parent per shared lease12, 44 workers total, nice15, PYTHONHASHSEED=0, NUMPY_MADVISE_HUGEPAGE=0, BLAS/torch threads1. Data: `03:/mpac/sdicks02/jobs/clasher/bot-hlmax-20261017/` (`strong-0`…`strong-3`, `pool-0`…`pool-3`).

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

