# Full-pool packing/refit recovery, 2026-10-16

Outcome: packing retained; both F1 attempts invalid for the intended mixed-corpus experiment; both KF1 attempts
stopped for inadequate CPU leases. No completed refit, screening result or promotion. Corrected source is prepared
only. Authority: owning-parent direction at 16:13:09Z, recorded in
`/mpac/sdicks02/jobs/clasher/coordinator-sol-20261016/fullpool-fit-existing-jobs-direction.json`.

All times below are UTC from host `date -u` or the timestamped process audit. `J` denotes
`/mpac/sdicks02/jobs/clasher/bot-fullpool`. Recovery evidence on 05 is
`J/refit-recovery-20261016T1611Z/`: `commands.jsonl` records argv/stdout/stderr/exit status; exact snapshots,
failed/current logs, receipts, inputs and train logs are retained separately. The earlier generation audit
`J/babysit-g1k1.log` is unchanged; an append-only recovery pointer was added after the existing history.

## Adopted identities and disposition

All four used `J/repo-93c1fe1af8ca`, nice 15 and a `cpu_job.sh 10` lease. Actual runtime was
`live16402b-r2`, with `PYTHONHASHSEED=0`. Exact argv, allowlisted environment, UID, boot ID, process start ticks,
parent graph, executable, working directory and stdout/stderr targets are in `snapshot{01,04,08}.json`.

| host/job | current leader/PGID | trainer | receipt launch | guarded TERM / no live members |
|---|---:|---:|---|---|
| 04 F1b | 855251 | 855446 | 16:10:38 | 16:17:21 / 16:17:22 |
| 08 F1a | 1918203 | 1918288 | 16:10:37 | 16:17:27 / 16:17:27 |
| 01 KF1a | 2895857 | 2896071 | 16:06:11 | 16:17:36 / 16:17:40 |
| 01 KF1b | 2896463 | 2896759 | 16:06:12 | 16:17:49 / 16:17:53 |

F1 leaders actually started at 16:10:37Z on both hosts; the 04 receipt clock crossed to 16:10:38Z. F1 used
`/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python` (prior probe torch 2.7.1+cu118). KF1 used
`/mpac/sdicks02/repos/clasher-bot/.venv/bin/python`, entirely on CPU. The warning about CUDA initialization in
its backward pass did not prove GPU training; source creates CPU tensors/net and GPU01 had no trainer process.

The initial F1 attempts used the CPU venv's incompatible CUDA build and failed at `model.to(cuda)` by 16:10:02Z.
Their logs survive as `04:J/fit-f1b.fail1.log` and `08:J/fit-f1a.fail1.log`. Their historical detach identities
were 04 PGID 812758 (16:10:01Z) and 08 PGID 1905505 (16:10:00Z). The retry command printed those old receipts
because `detach.sh` accepts any existing nonempty receipt before its new session overwrites it. They were
**not** retry process identities. The prior provider deleted the first output directories before retrying;
recovery performed no further output deletion. First-run directory contents cannot be reconstructed.

The original wrappers lacked `set -e` and ended with `echo ... rc $?`; command substitution ran `date` first,
and `echo` itself returned success. Both CUDA failures misleadingly printed `rc 0`. Tracebacks override that
marker. Recovery copied all surviving failed/current evidence and did not reinterpret it as completion.

## Source/data and footprint findings

Actual host source hashes matched the reviewed pre-change checkout:

| source | SHA256 |
|---|---|
| `bot/exit/train.py` | `58c579de4ea0a571ce7667440577c291488bc823cd5bf1f98fde13be0ab2e1b1` |
| `bot/search/lopp_train.py` | `f161cb9af23011bc24de70010b6a7144f9f447b93359a144016cb08eebd8484d` |
| `run/fit_f1.sh` | `a7ed1962fa17b12220e000c12eb86949e4e8c74a945ce17293ebaccd5f6c0ccf` |
| `run/fit_kf1.sh` | `b63d60eb02925879d5c000ec4d373f774fa667ace18fae28b05afe0318e7cd87` |

F1 actual arguments were ratios 1.0 (08, seed 2026101601) and 2.0 (04, seed 2026101602), both with three
`--old packed-kc7a-*` paths. `train.py` created old stores only under `a.old and a.new_ratio < 1`; both left
`old=None`. `StepBatches` then used the entire batch from new stores. `old_rows=0` was accurate actual exclusion
of the required C56 replay corpus, not header-only accounting. Hashing old manifests happened independently of
loading them. This finding does **not** say G1 has no observations involving C56 cards.

Both loaded G1 splits of 6,836,154 training rows and 356,639 held-out rows. Init SHA256 was
`a6565cabe728e8842405cb7a9e040970893566596b11980ad7ddf867df3dddcc`; assets SHA256 on 04 was
`3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737`.
No checkpoint or complete marker existed at the terminal snapshot. Last train records were step 202 (04) and
208 (08); printed progress stopped at 200. These are incomplete invalid attempts, not experiment results.

F1 configured OMP/MKL 8 plus default 8 concurrent DataLoader workers: demand envelope 16 versus lease 10.
KF1 explicitly called `torch.set_num_threads(16)` versus lease 10 per arm. Its 8 extraction workers finish before
threaded fitting; peak compute is 16, not 24. NLWP counts include idle/support threads and were not used as a CPU
demand measurement. All four failed the configured-demand gate; no live lease file was edited.

KF1 inputs were exactly `01:J/K1-fit/x0`, `01:J/K1-fit/x11`, `01:J/K1-x10`, with opponents R3a, v1 and extended
RL5 student. Both reported 3,292,938 rows, 184,388 plays, 322,555 validation rows. Arm a initialized from
`J/lopp-fp/poolfp.npz`; arm b was fresh. They omitted the legacy pool recording union required by PLAN.
Both reached epoch 4 before stopping; no exported NPZ/JSON existed. Source also exposed a late arm-a failure:
the `Path` in `args.init` would fail JSON serialization after NPZ export, before the old printed gate check.

## Review, authority and safe stop

Independent Sol reviewer `/root/review_refit_recovery` confirmed the corpus omission and capacity findings,
and checked actual process starts independently. Approved stop script SHA256:
`c15032d1a166d9d63f1f2d8ec42ad3245ec0586c959517e092f0958254c72dc3`.

Before one SIGTERM per exact PGID, the reviewed guard checked independent boot/start/receipt anchors, exact
leader→shell→trainer ancestry, trainer-direct loaders, UID/argv/cwd/executable, live lease, source hashes and
own log file descriptors, then rechecked core identities immediately before signaling. Assertions were enabled.
It failed closed; no broad matching, SIGKILL, live lease edits, retries or output changes were used. Each group's
own `cpu_job.sh` EXIT trap removed its lease. Independent terminal snapshots at 16:18:20Z confirmed no live refit
members, no refit leases and no GPU compute processes. Brief zombie members on 08 were recorded, not signaled.

LIVE's temporary loan covered only these exact F1 jobs on GPU0 of 04/08. GPU UUIDs:
04 `GPU-1a9e3761-7394-18fd-844e-7572e6686771`; 08 `GPU-6cb558a5-e557-239c-60ed-be7ddb4de59c`.
No idle reading was treated as new allocation authority. The loan did not waive data or CPU validity.
LIVE received the essential GPU handback at 16:17Z; both GPUs reverted to LIVE when these jobs exited.

Other work was untouched: K1 first-pass groups 04/2819629 and 08/2850352 still ran at the terminal snapshot,
each lease 4. No failed-game retry, old preflight, protected job or earlier completion gate was revived.

## Packing and prepared corrections

The existing G1 packs have complete manifests and source-index hashes matching their manifest entries:

| source host | sealed shards | rows | manifest SHA256 |
|---|---:|---:|---|
| 03 | 7,315 | 2,262,299 | `ed629f9b2bfdb51af81bac81104bce903a97d2942aa2ec9838b0882a4c9285a3` |
| 04 | 9,564 | 2,953,699 | `e558929348f405a8d07fa09f1d9b93621f9d0f60dd822ba70d58eeaecd7b5dda` |
| 08 | 6,387 | 1,976,795 | `d643dbfe782670f2b8ff1e6e83ed7d653ef4296cd3c8f9f2e1ca35fb71734113` |

Total 7,192,793 rows, 23,266 sealed source shards, zero duplicate source paths across packs. Source row sums
match manifests and the earlier label total. Recovery verified metadata/disjointness, not every multi-GB array
payload hash. Manifest copies on both F1 hosts matched the recorded training header hashes. No repack was run.
Original pack job identities: 03 PID/PGID1594987 (16:05:25–16:07:41), 04 PID/PGID558472
(16:05:25–16:08:39), 08 PID/PGID1660796 (16:05:26–16:07:37). Logs and receipts remain at their original hosts.

Prepared source fixes: fractional F1 mixing with invalid/unused-old rejection; required `OLD_REC` for KF1;
bounded compute/loaders validated against existing leases; fresh output names; compatible CUDA interpreter
default; propagated trainer errors; corrected `set -e` environment sourcing; KF1 Path serialization and finite,
tolerance-checked gate/card/tile export parity before completion JSON. Existing host sources were not patched.

Light tests cover exact mixed batch composition and determinism, rejected input configurations before runtime
load, Path export serialization, and rejected corrupted/nonfinite serving logits. Four tests and shell syntax
checks passed. Actual corrected fit/export parity and experimental evaluation remain unrun. The independent
review is for preparation, not resource allocation or launch permission.

Concrete blockers: identify/review the legacy KF1 recording union and immutable inputs; approve fresh CPU/GPU
capacity; review/stage exact corrected host sources and fresh job/output identities; separately authorize a
relaunch and new result gates. No promotion, replacement attempt or extension is authorized by this report.
