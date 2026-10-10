# Human-prior capacity scan results

Completed 2026-10-10 at 02:49Z, well before the leased-host deadline. **No wider
arm met the frozen gain threshold.** Retain width 192 as the human prior; none
of these arms qualifies for promotion as an offline teacher/proposer under this
scan's criterion. Capacity improved dev NLL monotonically at matched quarter
rows, but every gain was below 0.005. Width 480 missed by 0.000206465916232241.
No seeds, arms or thresholds were added after reporting outcomes.

## Matched quarter decision

Scientific freeze `841c44b0`; kill if NLL192−NLLwide<0.005 at the first completed
batch reaching 25% of 380,571,633 scheduled rows: **95,144,680 rows / step 11615**.
Each score uses EMA and all 11,776,480 human-dev rows. Natural joint NLL:

| Width | Dev NLL | Gain over 192 | Disposition |
|---|---:|---:|---|
| 192 | 0.277264362942 | — | Reused control + quarter replay |
| 288 | 0.274181445921 | 0.003082917021 | Killed: gain < 0.005 |
| 384 | 0.272807913545 | 0.004456449396 | Killed: gain < 0.005 |
| 480 | 0.272470828858 | 0.004793534084 | Killed: gain < 0.005 |

All three scientific kill rules fired. There are **no survivors**, resource-censored
arms or terminal infeasible arms. The failed width 480 segments are retained;
the authorized micro 1024 arm subsequently fit and reached a scientific decision.
All final guards exited 0 without a resource stop. GPUs13/14/15/16 were released;
controller 1702652 exited normally after receiving all terminal receipts.

## All measured curves

`curves.csv` contains full-precision values and matched-control gains. Every
wider arm's entire measured curve is its epoch-one point plus its quarter point;
no post-kill measurements were taken. The six-epoch 192 curve was reused from
T11 v2 seed 2026100821, augmented with the exact-row replay quarter point.
A dash means the arm had already stopped, not a missing surviving-arm result.

| Rows |192 NLL|288 NLL|384 NLL|480 NLL|
|---:|---:|---:|---:|---:|
| 63,441,640 | 0.283173892296 | 0.279729737865 | 0.278398034986 | 0.277816193293 |
| 95,144,680 | 0.277264362942 | 0.274181445921 | 0.272807913545 | 0.272470828858 |
| 126,861,418 | 0.273868705168 | — | — | — |
| 190,284,562 | 0.269930718200 | — | — | — |
| 253,711,575 | 0.267613168838 | — | — | — |
| 317,145,261 | 0.266502475918 | — | — | — |
| 380,571,633 | 0.266274209809 | — | — | — |

The original 192 log SHA is
`1f9daf26c94d94b26268e42dbc0a53c3b5c1a31d35d3ea6b2dffd5a47d390647`.
`control-curve.json` preserves its original path and all six points.
`control-complete.json`, `control-boundary.json` and
`control-replay-trajectory.json` preserve the quarter replay and full-state
continuation evidence. Replay began from original step 11000; sampled replay
losses/gradients/LR/rows agreed bit-identically with the original run.

## Recipe, data and disclosed amendment

All arms used the qualified v2 human train/dev store copied over the LAN from 04
(or verified reuse on 16), with 130 file SHA checks completed on each host. Root
store SHA `7180964c1d470807a97ad7a990ac8eb145fb25d15f1c95edf165b3f87743d20f`;
T11 manifest SHA `a4801df32d4a546ed7df07faf070a138d4075cf4db6c193d38373f9194ff2e44`.
The start receipts agree on all token/asset/role/store/T11/qualification hashes.
Frozen T11 trainers and original control artifacts were not modified; the scan
used the separately pinned capacity adapter and immutable source snapshot.
No evaluation/eval_ood store was copied or used for reporting or tuning.

Widths 288/384/480 use four transformer layers, **six heads**, FFN4×width and tile
width 64. T11 v2 seed 2026100821, six epochs, batch 8192, warmup 2000/cosine, AdamW
lr 3e-4 / WD 0.05, clip 1, bf16, dropout 0.1, EMA 0.999 and patience 3 remain fixed.
The original plan disclosed wide micro 2048 versus historical 192 micro 7168.

Width 480 required two pre-dev repairs. Its first run exceeded the free-memory
reserve and saved a full-state step 175 checkpoint before stopping. The next run
with allocator cap 0.78 resumed 175 and failed with confirmed CUDA allocator OOM
in FFN dropout after successful step 598  / 4,898,816 rows: a 1.41 GiB request exceeded
the 37.08 GiB allowance despite 9.68 GiB physical free memory. Latest durable 175
checkpoint SHA `91c66427e0c23ce7d2d2d519a7e2dcffc8a4b449d33219adf8f3e5b86f29ebba`.

Coordinator authorized **only micro 1024** at 20:42Z, before any width 480 dev
outcome. Amendment `AMENDMENT-microbatch-480.md`, commit`f8dd81a6`, pinned new
config SHA `2782e7a92f6f97de910748b719d39b20aeecd05be800f5fb3c74a7046c39952b`
and 15-only freeze before launch. The third run resumed complete model/EMA/
optimizer/scheduler/RNG/cursor state from 175; effective batch 8192 through eight
accumulations and allocator cap 0.78 stayed fixed. Summation order and dropout
random draws can differ, so this is mathematically the same batch objective
but **not bit-identical** to micro 2048. Lost work 176–598 was replayed and charged.
No further scientific adjustment was made. Both failed/paused segments, full
traceback, checkpoint pointers and pre-outcome operational amendments remain
archived; the old signal-complete file at 175 is not treated as final completion.

## Throughput and compute cost

| Width | Final loader-inclusive rows/s | Recorded fit/scoring GPU-hours | Conservative pipeline GPU-hours |
|---|---:|---:|---:|
| 192 | 5480.556 | 0.374255533 | 0.504949280 |
| 288 | 5768.079 | 4.734969255 | 5.214054993 |
| 384 | 4347.044 | 6.271614029 | 6.747876301 |
| 480 | 4459.961 | 6.414883206 | 6.891155311 |

Recorded fit/scoring total: **17.795722024 GPU-hours**.
Conservative controller total: **19.358035878 GPU-hours**;
independent guard-ledger recomputation agrees within 1e-6 hours. The latter
includes staging and guard overhead and stopped below 39.8 hours. Fit/scoring
segments include initialization, loader delays, dev scoring and failures; these
are wall GPU reservations, not utilization-weighted kernel time. The final
loader-inclusive rates are trainer log rates before quarter scoring and do not
include that last dev pass in their denominator. Historical 192 training is
reused and **not charged as new scan compute**; only its 5,038,080-row replay and
scoring are charged here. Its replay rate is not a whole-schedule rate.

Width 480 recorded segments: first run 0.104989599 GPUh,
failed allocator run 0.228205055 GPUh,
final micro 1024 run 6.081688553 GPUh.
All costs include every restart, with no failed artifacts discarded.

Runtime guards enforced ≤16 processes, nice ≥10, 48 GB PSS and ≥8 GiB GPU free.
Final 384 peak PSS 44.53 GB and 480 peak 43.80 GB stayed below 48 GB. The earlier 480
reserve breach and allocator OOM are explicitly disclosed above. Read-only
release checks for 13/14/15 confirmed owned PIDs gone and empty GPU compute
lists at their recorded timestamps;16 was released after its replay. These
checks do not assert anything about later borrowers.

## Checkpoint pointers and evidence

No weights are in git. Quarter checkpoints remain under each listed host's
`/mpac/sdicks02/repos/clasher-lease/capacity-scan-20261009-v1/runs/width<width>/quarter-step-00011615.pt`:

| Width /host | SHA256 |Bytes|
|---|---|---:|
| 192 / 127x16 | `adf708c004ab2c6469a519447eca9d3fa3db451ef45a6d0c01a1e7f51b38a7b3` | 36,477,530 |
| 288 / 127x13 | `0325bef0627e82f4bf46a5abbe2255036aaa387a7a4acedd326c564ad37632f8` | 76,849,050 |
| 384 / 127x14 | `fbee86499c59656d42300c1aaded11ed0dc6f3cc8c3c6bf59f23dc156c4f0061` | 132,556,698 |
| 480 / 127x15 | `becef382c87e7ca262f009ea9aa21b6c91e2b2bd0a52ec6c5c376fa28df1e546` | 203,601,114 |

`width288-result.json`, `width384-result.json`, `width480-result.json` and
`control-complete.json` contain full curves, source pins, segment costs,
guard exits and checkpoint pointers. `width384-release.json` and
`width480-release.json` provide independent release checks; 288's check is
embedded in its result. `terminal-receipt.json` reconciles all costs/decisions.
Results were secret-scanned and pushed in commit `bb14988d`; the coordinator
received the terminal report. The specific temporary continuation schedule is
now disabled (`enabled=false`, `nextRunAt=null`); `shutdown-receipt.json` records
the scheduler response. The scan has no remaining active fits or scheduled work.

## Recommendation and scope

Retain 192. None of 288/384/480 reaches the predeclared meaningful quarter NLL
gain; do not relax the cutoff for 480's near miss. Wider models remain
**offline-only** if separately studied: 288 and 384 exceed the 15 ms live latency
budget (p99 17.98/27.55 ms), while 192 measured 14.92 ms. 480 was prospectively
restricted to offline use. This one-seed exploration scan establishes the
frozen dev-NLL decision, not playing strength, statistical significance or
live-policy adoption. No reporting-data tuning or extension was performed.
