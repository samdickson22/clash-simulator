# Revised offline PPO fixture results

Both exact selected next-snapshot starts pass the bounded FP64 fixture after Sam's operational-rejection
amendment. Fresh independent Sol high R38 gave GO for source
`8fe59e7d2246baefb908d793122086f790e9cc33`, package SHA256
`a77548c1c0bd63fa072290b91b3ddecfd72767a10f896f3b953c77c6f0c8d69c`.
The documentation amendment preceded implementation, review and relaunch. Mask, engine, actor, learner,
model, public history and reward behavior are unchanged. Forty-two focused tests pass.

Both fixtures started 2026-10-22T12:40:32Z. S100 ran on own02 for 365.0 seconds; M on own01 for 677.8 seconds.
Each retained exactly **8,448 generated/published polls, zero discards**, trained **8,192** polls in three
critic warmups and one PPO update, then checked **256 fresh version-4 polls**. Effective batch was 2,048,
microbatch 128, two epochs per update and eight total optimizer steps, on the pinned Torch 2.7.1 environment.
Both completed and exited; no fixture remains running.

| Quantity | S100 | M |
|---|---:|---:|
| Selected BC file SHA prefix | 74c7640776fd | 947af5cb5ac2 |
| Completed games | 10 | 11 |
| Unfinished budget-stop games | 1 | 1 |
| Maximum pre-update logp error | 8.374e-7 | 1.309e-6 |
| Maximum post-PPO CPU/GPU logp error | 3.292e-7 | 6.414e-7 |
| Post-PPO value error, all probes | <8.3e-15 | <1.4e-14 |
| Peak observed GPU reserved GiB | 1.525 | 3.744 |
| Combined process peak RSS GiB | 3.652 | 3.754 |
| Readiness capture games/hour, excluding barriers | 143.26 | 97.55 |
| Critic update seconds, range | 8.97–9.10 | 33.85–34.93 |
| PPO update seconds | 13.83 | 56.18 |
| Final update mean human KL, nats/poll | 0.00002405 | 0.00067098 |
| Other execution failures | 0 | 0 |

All parity errors stay below the unchanged absolute **2e-6** bound at batch widths 128 and 256. The post-PPO
probe also passes with wider masked padding. Every policy head has a nonzero finite gradient and changes during
PPO; critic-only warmups leave those heads fixed. Human anchors remain frozen, and AdamW coverage/counters pass.
These are one-process, one-R3a-opponent readiness costs, not full-league throughput or isolated actor PSS.
M's capture costs about 1.62 times as much wall time per poll; its same-batch PPO update costs about 4.06 times
as much. Both use the same registered optimizer semantics. Observed entity widths are small; these memory
figures do not qualify the full 262,144-row production rollout or theoretical maximum shapes.

## Operational rejections retained

| Quantity | S100 | M |
|---|---:|---:|
| Submitted taps | 418 | 447 |
| Executed taps | 417 | 442 |
| Accepted taps | 415 | 441 |
| Rejected taps | 2 | 1 |
| Unexecuted pending taps | 1 | 5 |
| Rejected / executed | 0.479616% | 0.226244% |
| Cannon rejected / Cannon executed | 2 / 63 | 1 / 66 |

All rejected taps are Cannon. Other own cards have zero rejected taps. Both sizes' rejections were submitted
under version 2, with 2 / 97 S100 and 1 / 116 M executions attributed to that snapshot. The other versions
have zero rejections. Both tap outcomes and every sampled action/log probability/actor mask/step are retained;
there is no resampling, WAIT substitution, penalty or budget top-up. Pending taps remain separate.
The original failed S100 attempt remains failed and immutable under its original gate. All **4,334** original
prefix rows, across **722** retained arrays, match the successful revised run **bit for bit**, including features,
actions, log probabilities, values, actor masks, rewards and terminal flags.

Reports include per-card and per-version counts. The exact >2x BC-reference alert is implemented and tested
without a kill path. This fixture has different readiness exposure from the frozen BC evaluation banks, so its
matched-reference comparison is explicitly unavailable. It does not invent a zero baseline or claim a registered
RL snapshot comparison. Complete, own-size BC evaluation references are now available separately, retaining
all 1,600 assignments and nine other failures per arm. See [OPERATIONAL-REJECTIONS.md](OPERATIONAL-REJECTIONS.md).

## Evidence and remaining gates

On 05, all results, queue receipts and checkpoints are retained under
`/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/rejection-amendment-20261022/{S100,M}-evidence/`.
Evidence archive SHA256s are:

- S100, 183,316,480 bytes: `294a728f70b57cc2ab33b82abc3e972e47d9d5bc3b87f7b6ca810269c49e1b8e`
- M, 718,786,560 bytes: `45319b68abe536bcc7aa1ffb3346517029a9f2664723586e8294956c25ef960e`

Source/anchor-bound originals remain on 02 and 01 beneath
`jobs/clasher/pretrain-v1/fp64-qualification-staging-20261022/fixture-8fe59e7d2/qualification-artifacts/`.
The separate initial failure and diagnostic archives are unchanged.

This is offline numerical/behavior qualification only. Full rollout memory/queue admission, league throughput,
six-hour soak, recycling/continuation/reclaim qualification, production precision adoption and integrated
launch-config review remain gates. No registered RL experiment, new model default or deployment has launched.
The prior FP64 Mac M result remains over budget under shared load. An idle rerun is held: fresh Canvasdoc
telemetry at 12:55Z observed a 10.2% CPU peak and 851,424 KiB RSS. No new Mac benchmark owner launched,
and no VM/replay process was changed. Exact next checkpoints are staged only in the benchmark directory.
