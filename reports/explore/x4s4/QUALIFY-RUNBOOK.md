# X4S-4 PLAN §6 qualification-stage launch runbook (exploration, NEVER ADOPTABLE)

This was prepared offline on 127x05 on 2026-10-12 and updated for scripts r9 (commit `C` below), which implement
coordinator ruling SR-1 (the external watchdog) after Sol r8 returned REQUEST_CHANGES on 86fa3c5d (earlier rounds: r7
81d78349, r6 0fc0f243, r5 ffde20ac). It authorizes nothing: every step on 127x01 waits for an explicit coordinator GO,
and runs only if Sol approves the script set (now r9). If a later
round asks for changes, the commit and SHAs below are updated before use. Production (collection, labeling, fits,
reporting) is **not** part of this runbook; it needs its own GO after the qualification evidence is reviewed.

**Coordinator decisions Q-D1 to Q-D4** (COORDINATOR 2026-10-12 22:50Z; effective once Sol approves the script set):
- **Q-D1. One combined GO:** §6 qualification plus **conditional** production (section G). Production continues
  automatically only if every gate passes with its exact receipts. Any failure, anomaly or STOP pauses for the
  coordinator. T starts at the first qualification launch (Q1).
- **Q-D2. §6.5 trainer compatibility:**
  - If r5 requests changes: (a), a narrow `qualify4 smoke-pack`, reviewed in the next round.
  - If r5 approves: (b), `qualify4 trainer` on the first real O batch after the O gate and before R5 fit admission
    (section G, P8). A trainer failure blocks all fits.
  - **Applicable variant: (a).** Sol r5 requested changes, so r6 added `qualify4 smoke-pack` (strict since r7, under guard.py since r8) and Q6 runs inside the
    qualification stage (section D). Production step P8 is not used.
- **Q-D3. Smoke parity at 8 games per arm:** the designed pause applies. The coordinator decides on any exact-receipt
  exception.
- **Q-D4. Q0 seed audit:** included. It runs once on 05 at nice 19 on a few cores, over pinned blobs only. It does
  not touch the shared checkout's worktree: the reviewed code runs from a /dev/shm export, and its output is written
  there (see Q0).

**Budget disclosure.** PLAN §7 allots 0.8 h to staging plus qualification. This runbook expects about 2.0–3.6 h,
including the 10–20 min smoke-pack labelling of variant (a). With PLAN's 18 h for production, the margin to T+24 h is
about 2.5–4 h. E8 truncation rules apply if it runs out.

## A. Fixed identities

| Item | Value |
|---|---|
| Host | 127x01 only. No other host; 03/04/Mac never. |
| Job root `J` | `/mpac/sdicks02/jobs/clasher/x4s4-onpolicy`. It must not exist before staging. |
| X4S-3 job `J3` (read-only source) | `/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012` |
| Script commit `C` | `a701d610bb2e4f95100251ee74fc769d70cd5711` (scripts r9, pending Sol r9) |
| Runtime python | `/mpac/sdicks02/repos/clasher/.venv/bin/python`, via `x4s3/runtime.sh` |
| GPU python | `/mpac/sdicks02/envs/clasher-gpu/bin/python` |
| Pins | native `44874fd6…`; v1 `d77005d5…`; R3a `37509a43…` (threshold 0.5005528330802917); R3a-rep `8d537a78…` (threshold 0.49952925741672516); emitter `dab61651…`; `x4s3/run.py` `e7f90d76…` |
| External read-only inputs | the R1 corpus `/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1` (fits only); held-out64 `/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/heldout-corpus` (manifest `0ecce0f0…`, diagnostic only) |
| Banks used in qualification | qualification `4503606337370496+[0,8)`; smoke `4503606327370496+[0,8)`. No E, C or C′ seed is played in this stage. |

**Never touched:**
- `t1-*`, `fleet-end-attempts*`;
- the paused hub mirror (PGID 516161);
- any T1/K4S/TIERS directory;
- `J3`, except read-only copies;
- `tailscaled`.

No `pkill`, no pattern kills: every stop is the reviewed PID-only path or `J/STOP`.

## B. Resource caps (every step)

- **Cores:** games and CPU work on 0–49 (supervisor-enforced `taskset -c 0-49`, `nice 10`, SCHED_OTHER). GPU work on
  56–61 with loaders on 120–125. The watchdog runs on core 62. Cores 50–55 and 63 stay free.
- **Processes and disk:** ≤ 70 X4S-4 processes (studytree admission reserves each phase's workers) and ≤ 100 GB
  under `J`. The expected peak is about 15 GB, mostly the copied base and captures.
- **Memory:**
  - Nothing is dispatched while MemAvailable < 24 GiB or memory PSI some avg10 > 10 (or PSI is unreadable).
  - Running work is killed only on MemAvailable < 24 GiB or owned PSS > 50 GiB.
- **GPU ≤ 40 GB.** The only GPU step is the trainer check (Q6, about 1 GB).
- **Console user:** yield, then ≤ 16 game processes (supervisor).
- **The external watchdog (r9, coordinator ruling SR-1) is the authoritative host-safety backstop.**
  - **Placement:** `watchdog.py` starts right after staging (W0 below), before any study process, and runs outside
    the study tree: its own session, no study marker, core 62.
  - **The study tree:** every process whose environment carries `X4S4_STUDY=$J`. The driver, `supervise.py` and
    `guard.py` refuse to start without that marker and without a live watchdog, and every study child inherits it.
  - **Checks:** every ≤ 10 s, with each measurement bounded:
    - STOP;
    - the deadline;
    - MemAvailable ≥ 24 GiB;
    - PSI readable (readable high PSI only inhibits dispatch, the frozen rule);
    - ≤ 70 study processes;
    - study PSS ≤ 96 GiB;
    - `du` of `J` ≤ 100 GB, within 5 s;
    - GPU ≤ 40 GB via nvidia-smi, within 3 s.
  - **The deadline works like STOP.** At T+24 h the study's guards stop production work, and production study
    processes still alive 180 s later are a breach. Only the E8 readout steps (P13–P15, `X4S4_READOUT=1` with
    `guard.py --readout`) may run after the deadline. `guard.py` refuses that marker on any other step, and the
    driver and supervisor refuse it too.
  - **Breaches:** any breach, failed measurement, or watchdog cycle stalled for more than 30 s causes a **HALT**:
    1. the watchdog writes `J/HALT.json` (read-only, fsync'd) and `J/STOP`;
    2. it stops every study process one at a time by verified (pid, starttime): TERM, then KILL after 20 s;
    3. it re-scans until the tree is empty.
- **HALT is a hard stop.** The watchdog keeps killing any later study process, and every entry point refuses new work.
  I post HALT.json to the coordinator. The study is not restarted under the same T, and outputs completing at or
  after the HALT never count (rule H-1).
- **STOP** (`J/STOP`, may be a dangling symlink) is an operator pause.
  - The study's own guards stop their work; the driver leaves its loop once nothing lives.
  - The tree must be empty within 180 s, which covers the frozen trainer's 120 s checkpoint grace. Otherwise the
    watchdog HALTs.
  - The watchdog logs STOP periods, and outputs completing during a STOP never count (H-1).
  - To resume after a coordinator decision: remove STOP, check `watchdog.py status`, then relaunch the step or the
    driver.
- **Rule H-1 (enforced by every consumer and the reducer):** an output whose completion time is at or after a HALT,
  at or after the deadline, or inside a STOP period is never counted. The readout outputs (P13–P15) are exempt from
  the deadline only, by design (E8). The completion time is:
  - for guarded outputs: the guard receipt's write time;
  - for games: the block proof's write time;
  - for runtimes: the READY receipt's write time.
- **In-process guards (defence in depth since SR-1):** `supervise.py`, the driver and `guard.py` (`$GRD`) still admit,
  monitor and stop their work as before (SCRIPTS.md "Guard audit (r8)"). They are no longer required to be perfect;
  their known residuals are listed in SCRIPTS.md and covered by the watchdog.
  - Every consumer still accepts an output only through its producer's matching passed receipt (R8-F4).
  - Admission: no STOP or HALT; before the hard stop; MemAvailable ≥ 24 GiB; PSI readable and ≤ 10; ≤ 70
    processes; ≤ 100 GB; a live watchdog.
  - `--readout` (contention, reduce, report only) exempts the readout from the deadline, because the E8 reduction
    follows the stop. STOP, HALT and the resource rules still apply.
- **Hard stop:** `J/HARD-STOP-UTC.txt` = T+24 h, written once at Q1.

## C. Staging (S0–S3)

Every command below runs as `ssh 127x01 '…'` from 127x05, one command per call, and I record each exit status.

**S-U2: hand-off from U2 (read-only; before S0).** U2, the fit-seed replicates, may be live on 01 when the GO arrives.
It belongs to another thread and runs only under `J2=/mpac/sdicks02/jobs/clasher/x4s3b-fitseed-20261013`. Its GO
says that on "STOP U2" (the X4S-4 GO) it stops immediately and drains by PID.
- **No touching U2.** I never write under `J2`, never signal a U2 process and never create its STOP. The coordinator
  or U2's own thread issues "STOP U2".
- **U2 may already be gone.** It might have finished by its own `STOP_AT` (launch + ≤ 8 h).
- **What I wait for.** I verify, read-only, that U2 has drained, polling every 60 s:

```bash
ssh 127x01 'ls -la /mpac/sdicks02/jobs/clasher/x4s3b-fitseed-20261013/STOP 2>&1'             # STOP U2 recorded (or U2 finished)
ssh 127x01 'ps -eo pid,lstart,args | grep "x4s3b-fitseed-2026101[3]"; echo __RC=done'       # must list nothing
ssh 127x01 'for d in /proc/[0-9]*; do readlink $d/cwd 2>/dev/null; done | grep -c -F x4s3b-fitseed-20261013'   # must print 0
ssh 127x01 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; grep MemAvailable /proc/meminfo'
```

The bracket in the pattern stops the check from matching its own command line. Nothing is written on 01.
- **Go/no-go for S0:**
  - no process command line or working directory refers to `J2`;
  - GPU used ≤ 8 GiB;
  - MemAvailable ≥ 64 GiB.
- **Why U2 must be fully drained before W0.** The watchdog's GPU and memory checks are host-wide. A still-running
  U2 fit would be outside the study tree, so the watchdog would not stop it, but it could push GPU memory over 40 GB
  or MemAvailable under 24 GiB. That would HALT X4S-4.
- **If U2 is still live after 15 min:** I post its PIDs (read-only listing) to the coordinator and wait. I do not
  stop it myself.
- **Timing.** T starts at Q1, so this wait does not consume T. The U2 drain (about 2 min for a fit checkpoint) is
  reported in PROGRESS.

**S0: read-only preflight on 01.**

```bash
hostname; who; uptime; nproc; free -g; cat /proc/pressure/memory
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
df -h /mpac; test ! -e /mpac/sdicks02/jobs/clasher/x4s4-onpolicy && echo J-absent
du -sh /mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012/{base,inputs,fit}
find /mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012/base -type f -links +1 | wc -l      # must be 0
sha256sum /mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012/inputs/{main02.pt,R3a.pt,R3a-rep.pt,assets.npz}
/usr/bin/python3 -V; /mpac/sdicks02/repos/clasher/.venv/bin/python -V; /mpac/sdicks02/envs/clasher-gpu/bin/python -V
```

**Go/no-go:**
- no console user;
- S-U2 passed: no U2 process, and U2's GPU memory released;
- MemAvailable ≥ 64 GiB;
- PSI ≤ 10;
- GPU used ≤ 8 GiB;
- ≥ 120 GB free on /mpac;
- `J` absent;
- 0 hard links;
- all four pins match.

**S1: build `J` (writes only under `J`).**

```bash
J=/mpac/sdicks02/jobs/clasher/x4s4-onpolicy; J3=/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012
mkdir -p $J/{inputs,fit,receipts,qual,smoke,collect,data,driver,logs,staging} && cd $J
cp -a $J3/base $J/base                                   # repo + native + corpus (read-only copy of S1/X4S-3 base)
cp -a $J3/inputs/{main02.pt,R3a.pt,R3a-rep.pt,assets.npz,assets.npz.json} $J/inputs/ && chmod 0444 $J/inputs/*
cp -a $J3/fit/source $J3/fit/ops $J3/fit/loader6.json $J/fit/
```

From 127x05, stream exactly the reviewed X4S-4 files from git (no worktree file):

```bash
git -C /mpac/sdicks02/repos/clasher archive a701d610 reports/explore/x4s4 | ssh 127x01 'tar -x -C /mpac/sdicks02/jobs/clasher/x4s4-onpolicy/staging'
```

**S2: verify, then overlay.**
- Every staged `x4s4/*` file must equal its SCRIPTS.md SHA.
- `base/repo/reports/explore/x4s3/{run.py,runtime.sh,detach.sh,calibrate.py}` must equal the c86d928d SHAs.
- `base/repo/imitation/exit_r1/{rows,pack,emitter}.py` must equal origin/main; the emitter is `dab61651…`.
- `base/corpus/{states-ready.pkl,symmetric-screen-samples.json}` must equal the X4S-3 corpus pins `8b188918…` and
  `86ecbb60…` (the 125-state Q3 corpus).

```bash
cp -a $J/staging/reports/explore/x4s4 $J/base/repo/reports/explore/x4s4
cp $J/base/repo/reports/explore/x4s4/plan.json $J/base/repo/reports/explore/x4s3/plan.json   # bank E/C/C'/smoke/qual + R3a student
cp $J/base/repo/reports/explore/x4s4/run_fit.sh $J/fit/run_fit.sh
cp -a $J/base $J/rt-R3a                                   # R3a runtime (plan student = R3a)
cp -a $J/base $J/rt-R3a-rep                               # then replace its x4s3/plan.json student block with R3a-rep
```

The R3a-rep student block is:

```text
id R3a-rep, checkpoint $J/inputs/R3a-rep.pt, checkpoint_sha256 8d537a78…, threshold 0.49952925741672516
```

It is written by a one-line python3 `json` edit; then `rt-R3a-rep/READY.json` is written.

**S3: `J/RUNTIME-INVENTORY.json`.** The files and their SHAs from the reviewed commit and pins:
- `reports/explore/x4s4/{supervise.py,x4s4io.py,studytree.py,qualify4.py,guard.py,watchdog.py}`;
- `reports/explore/x4s3/{run.py,runtime.sh}`;
- `fit/run_fit.sh`, `fit/loader6.json`;
- `inputs/assets.npz`.

The staging transcript (every SHA compared) is saved as `J/receipts/staging-check.txt`. **Staging writes nothing
outside `J`.**

Expected duration: about 10–20 min, dominated by copying `base`.

**W0: start the external watchdog (SR-1), before any study process.**

```bash
cd $J && env -u X4S4_STUDY taskset -c 62 nice -n 10 /usr/bin/python3 -B $J/rt-R3a/repo/reports/explore/x4s4/watchdog.py start
/usr/bin/python3 -B $J/rt-R3a/repo/reports/explore/x4s4/watchdog.py status     # must print ok=true and exit 0
```

`start` detaches the watchdog into its own session, without the study marker, and waits for its first heartbeat.
Until Q1 writes the deadline, the watchdog only requires that no study process exists. From then on it holds the
deadline in memory. W0 must pass before Q1. Every later step begins with `watchdog.py status`, and the entry points
check the watchdog themselves.

## D. Qualification steps (Q0–Q8), with exact commands

Common variables:

```bash
J=/mpac/sdicks02/jobs/clasher/x4s4-onpolicy
RT=$J/rt-R3a; R=$RT/repo; X=$R/reports/explore/x4s4
DET="bash $R/reports/explore/x4s3/detach.sh"      # setsid detach (log, launch receipt, command)
RTPY="/bin/bash $R/reports/explore/x4s3/runtime.sh"                            # the runtime python, as a guarded child
GRD="taskset -c 0-49 nice -n 10 env X4S4_STUDY=$J X4S3_RT=$RT /usr/bin/python3 -B $X/guard.py"      # guard runner, CPU steps
GRDG="taskset -c 56-61 nice -n 10 env X4S4_STUDY=$J X4S3_RT=$RT /usr/bin/python3 -B $X/guard.py"    # guard runner, GPU steps
SUP="nice -n 10 taskset -c 0-49 env X4S4_STUDY=$J X4S3_RT=$RT bash $R/reports/explore/x4s3/runtime.sh reports/explore/x4s4/supervise.py --job $J --rt $RT"
# X4S4_STUDY=$J marks the study tree for the watchdog; only GRD, GRDG, SUP and the driver command carry it
```

**Q0, on 127x05 (no host contact): seed audit at the pinned inventory.**

```bash
Q=/dev/shm/x4s4-q0; rm -rf $Q; mkdir -p $Q
git -C /mpac/sdicks02/repos/clasher archive a701d610 reports/explore/x4s4 | tar -x -C $Q    # the reviewed code, not the worktree
git -C /mpac/sdicks02/repos/clasher cat-file -e 7f82af0d4b3b6a465cba9a1b6dd26c708bcf25d1
nice -n 19 taskset -c 0-3 /dev/shm/x4s4-venv/bin/python -B -c "import sys; sys.path.insert(0, '$Q/reports/explore/x4s4')
import x4s4io as io; io.REPORT_ROOT = '$Q/reports/explore/x4s4'
import audit_seeds as A; A.main(['audit'])"
```

This reads git objects of the repository by object id only, plus `seed-sources.json` and `plan.json` from the export.
It writes `$Q/reports/explore/x4s4/seed-audit.json`, never the shared worktree. It must exit 0, with
`intersections=[]`. The receipt is committed through a temp index from the /dev/shm file. About 1–3 min on 4 cores at
nice 19.

**Q1: start T, and run the unit tests.**

```bash
date -u -d '+24 hours' +%Y-%m-%dT%H:%M:%SZ > $J/HARD-STOP-UTC.txt     # ONCE; T recorded in receipts/T.json
cd $J && $GRD --name q1-unit-tests --cwd $R -- $RTPY -m pytest -q reports/explore/x4s/test_sdefault.py \
   reports/explore/s1/test_anchor.py reports/explore/s1/test_latency.py      # output: logs/guard-q1-unit-tests.log
```

The tests must pass as in X4S-3 (31 tests), with `receipts/guard-q1-unit-tests.json` passed=true. This takes about
1 min.

**Q2: capture non-perturbation (§6.2). Two detached phases, run sequentially.**

```bash
cd $J && $DET logs/q-run.log receipts/q-run-launch.json $SUP --phase qual/run --range qualification \
   --indices $X/idx-qual.json --config $X/plan-qual-capture.json --stop-at $(cat $J/HARD-STOP-UTC.txt)
# after qual/run/supervisor-exit.json shows reason null / returncode 0:
cd $J && $DET logs/q-collect.log receipts/q-collect-launch.json $SUP --phase qual/collect --range qualification \
   --indices $X/idx-qual.json --config $X/plan-qual-capture.json --stop-at $(cat $J/HARD-STOP-UTC.txt) \
   --script reports/explore/x4s4/collect.py
cd $J && $GRD --name q2-hashes --output $J/qual/hashes.json -- $RTPY $X/qualify4.py hashes --run-phase $J/qual/run \
   --collect-phase $J/qual/collect --config $X/plan-qual-capture.json --out $J/qual/hashes.json
```

**Pass:**
- 16/16 cases are terminal and proof-authenticated;
- equal command hashes;
- the live belief is unchanged;
- fair invariance, with ≥ 1 perturbed decision per game and ≥ 50% of early checks perturbed;
- capture SHA, identity and parity flags hold.

Each phase is 10 five-core slots × 8 blocks of 2 games at 1,000 s budgets. Expected 15–40 min per phase, so 30–80
min for Q2.

**Q3: labeler equals the frozen teacher (§6.3).** The 125 states, at the labeler's thread count of 1:

```bash
cd $J && $DET logs/q3.log receipts/q3-launch.json $GRD --name q3-frozen --output $J/qual/frozen.json -- \
   $RTPY $X/qualify4.py frozen --corpus $J/base/corpus --threads 1 --out $J/qual/frozen.json
```

Pass: 125/125 equal. About 5–15 min, on one core.

**Q4: collection smoke, round trip and smoke parity (§6.2 deadline mode, §6.4).**

```bash
cd $J && $DET logs/s-col-k.log receipts/s-col-k-launch.json $SUP --phase smoke/collect-K4S-120 --range smoke \
   --indices $X/idx-smoke.json --config $X/plan-collect.json --arms K4S-120 --script reports/explore/x4s4/collect.py \
   --stop-at $(cat $J/HARD-STOP-UTC.txt)
cd $J && $DET logs/s-col-s.log receipts/s-col-s-launch.json $SUP --phase smoke/collect-S-200 --range smoke \
   --indices $X/idx-smoke.json --config $X/plan-collect.json --arms S-200 --script reports/explore/x4s4/collect.py \
   --stop-at $(cat $J/HARD-STOP-UTC.txt)
cd $J && $DET logs/q4-rt.log receipts/q4-rt-launch.json $GRD --name q4-roundtrip --output $J/qual/roundtrip.json -- \
   $RTPY $X/qualify4.py roundtrip --phases $J/smoke/collect-K4S-120 $J/smoke/collect-S-200 --threads 1 --out $J/qual/roundtrip.json
cd $J && $GRD --name q4-parity --output $J/qual/parity-smoke.json -- $RTPY $X/qualify4.py parity \
   --phases $J/smoke/collect-K4S-120 $J/smoke/collect-S-200 --bank smoke --min-games 8 --out $J/qual/parity-smoke.json
```

**Pass:**
- both phases exit clean;
- round trip: 100% of smoke captures, 0 digest mismatches, repeat-label identity, the C8 triple present and hashed,
  empty pending;
- parity within ±2 pp of X4S-3's R3a. A failure is decision point 3.

Timings: about 2–3 min per phase (8 blocks; K4S-120 is 10 five-core slots, S-200 is 50 lanes). The round trip is
about 1,900 captures × 2 labels × about 0.3–0.6 s on one core, so 20–40 min.

**Q5: emitter acceptance smoke (§6.6).** Two excluded games on the qualification bank:

```bash
cd $J && $DET logs/q-ow-acc.log receipts/q-ow-acc-launch.json $GRD --name q5-ow-acceptance --add 3 \
   --output $J/data/raw-OW-acceptance-smoke.json -- $RTPY reports/explore/x4s4/collect_w.py --checkpoint $J/inputs/main02.pt \
   --count 1 --workers 1 --acceptance-smoke
```

Pass: `data/raw-OW-acceptance-smoke.json` `passed=true` (2 games, replay_exact, sealed). The gate re-verifies it
later. About 3–5 min.

**Q6: trainer compatibility (§6.5), variant (a) per Q-D2.** It runs after Q4 and needs Q4's two smoke collection
phases. First, `smoke-pack` labels every authenticated smoke capture with the unchanged `label.label_game` (frozen
teacher, 1 thread), seals each game under `$J/qual/smoke-raw`, and packs them once with the frozen `pack()` into the
fresh `$J/qual/smoke-pack/batch-0000` (plan `$J/qual/smoke-plan.json`). It writes nothing under `$J/data`. Then the
trainer check re-verifies that batch's complete seal and opens it with the frozen RootTeacherStore and targets:

```bash
cd $J && $DET logs/q6-sp.log receipts/q6-sp-launch.json $GRD --name q6-smoke-pack --output $J/qual/smoke-pack.json \
   --output $J/qual/smoke-pack/batch-0000 -- $RTPY $X/qualify4.py smoke-pack \
   --phases $J/smoke/collect-K4S-120 $J/smoke/collect-S-200 --threads 1 --out $J/qual/smoke-pack.json
cd $J && env PYTHONPATH=$J/fit/source:$J/fit/source/src:$J/fit/ops $GRDG --name q6-trainer --gpu --cwd $J/fit/source \
   --output $J/qual/trainer.json -- /mpac/sdicks02/envs/clasher-gpu/bin/python -B $X/qualify4.py trainer \
   --packed $J/qual/smoke-pack/batch-0000 --assets $J/inputs/assets.npz --out $J/qual/trainer.json
```

**Pass:**
- `smoke-pack.json` `passed=true`: all 16 smoke games labelled, as `sealed` or as `no_rows` for a game whose captures
  all lack a scored root. Every capture is attempted, and rows + drops = attempted for each game. Any digest mismatch
  fails (r7, R6-F3). STOP, the hard stop or a guard breach during labelling or packing fails it, and no packed batch
  is accepted;
- `trainer.json` `passed=true`: rows = roots > 0, and the targets are finite and normalized;
- both guard receipts (`guard-q6-smoke-pack.json`, `guard-q6-trainer.json`) passed=true. Every qualification step's
  guard receipt is part of its evidence.

A failure blocks all fits. smoke-pack takes about 10–20 min on one core (about 1,900 captures × 1 label); the trainer
check takes about 1 min and about 1 GB of GPU memory.

**Q7: evaluation smoke, 8 + 8 R3a games (§6.7).** The runtime plan is the x4s4 plan, so these games are on the
smoke bank:

```bash
cd $J && $DET logs/s-ev-k.log receipts/s-ev-k-launch.json $SUP --phase smoke/eval-K4S-120 --range smoke \
   --indices $X/idx-smoke.json --arms K4S-120 --stop-at $(cat $J/HARD-STOP-UTC.txt)
cd $J && $DET logs/s-ev-s.log receipts/s-ev-s-launch.json $SUP --phase smoke/eval-S-200 --range smoke \
   --indices $X/idx-smoke.json --arms S-200 --stop-at $(cat $J/HARD-STOP-UTC.txt)
```

Pass: both exit clean, with 8 block proofs each. Outcomes are not inspected; these games are excluded. About 2–3 min
each.

**Q8: live STOP test (§6.7), on the collection path (the newer code).**

```bash
cd $J && $DET logs/s-stop.log receipts/s-stop-launch.json $SUP --phase smoke/stoptest --range smoke \
   --indices $X/idx-smoke.json --config $X/plan-collect.json --arms S-200 --script reports/explore/x4s4/collect.py \
   --stop-at $(cat $J/HARD-STOP-UTC.txt)
sleep 60; ln -s nowhere $J/STOP          # a DANGLING link: exercises lexists, not exists()
# wait for smoke/stoptest/supervisor-exit.json, then:
cat $J/smoke/stoptest/supervisor-exit.json; rm $J/STOP
```

**Pass:**
- `reason = owned_STOP`;
- `remaining_group_pids = []`;
- supervisor exit within ≤ 2 min of the STOP;
- no X4S-4 process left (`studytree` tree count back to the baseline);
- the unfinished smoke games have no block proof.

About 4 min.

**Expected total wall time** is about 1.7–3.3 h, plus 10–20 min of staging. It is CPU-bound on cores 0–49, and the GPU
is idle except Q6. The order is Q0 (05) → S-U2 (U2 drained) → S0–S3 → W0 (watchdog) → Q1 → Q2 → Q3 → Q4 → Q6 → Q5 →
Q7 → Q8.
Independent CPU steps never overlap phases: one supervisor phase at a time.

## G. Conditional production (Q-D1): runs only after every §6 gate passes

These commands run in this order with no further GO. Any failed gate, ANOMALY, PARITY-PAUSE, STOP or guard stop
pauses the study for the coordinator. The common variables are as in D. Every step runs under its guard (B): the
supervisor, the driver, or `$GRD` (`guard.py`); `…` after `$DET` stands for that step's own log and launch receipt
(`logs/<name>.log receipts/<name>-launch.json`). I do not hand-edit any receipt.

| Step | Command (on 01, detached as in D) | Gate to continue |
|---|---|---|
| P1 | `printf` the K4S-120 indices `[0,2000) ∪ [3500,3750)` into `$J/collect/idx-K4S-120.json`; `$SUP --phase collect/K4S-120/a1 --range reporting --indices $J/collect/idx-K4S-120.json --config $X/plan-collect.json --arms K4S-120 --script reports/explore/x4s4/collect.py --stop-at …` (≈2.3 h) | clean or interrupted exit; no PARITY-PAUSE (the in-supervisor C7b watch) |
| P2 | Same for S-200: `[2000,3500) ∪ [3750,4000)`, `collect/S-200/a1` (≈0.6 h) | as P1 |
| P3 | `$GRD --name p3-parity --output $J/receipts/parity-collection.json -- $RTPY $X/qualify4.py parity --phases $J/collect/K4S-120/a1 $J/collect/S-200/a1 --bank collection --min-games 100 --out $J/receipts/parity-collection.json` | passed and final, guard passed; otherwise the Q-D3 pause |
| P4 | `$GRD --name p4-label-plan --output $J/data/label-plan.json -- $RTPY $X/label.py plan --phases <P1,P2 phases> --parity $J/receipts/parity-collection.json --out $J/data/label-plan.json` | plan written; guard passed |
| P5 | `$DET … $GRD --name p5-label-O --add 50 --new-files $J/data/label-receipt-O- -- $RTPY $X/label.py run --plan $J/data/label-plan.json --set O --workers 48`, then the same with `p5-label-holdout`, `label-receipt-holdout-` and `--set holdout` (≈0.8 h) | both run receipts passed; both guards passed |
| P6 | `$DET … $GRD --name p6-pack-O --add 2 --output $J/data/onpolicy/batch-0000 -- $RTPY -m imitation.exit_r1.pack --roots $J/data/raw-O/K4S-120 $J/data/raw-O/S-200 --output $J/data/onpolicy/batch-0000`; then `p6-pack-holdout` the same way, with raw-holdout and `--output $J/data/onpolicy-holdout/batch-0000` | both guards passed. The packer stays byte-identical; its batch counts only through the guard receipt. |
| P7 | `$GRD --name p7-verify-O --output $J/data/O-VERIFIED.json -- $RTPY $X/verify_onpolicy.py --mode O --plan $X/plan.json --label-receipts <O receipts>`, then `p7-verify-holdout` with `--output $J/data/HOLDOUT-VERIFIED.json … --mode holdout …` | gates written; guards passed (0.30–0.45 M rows) |
| P8 | Not used: Q-D2 resolved to variant (a), and §6.5 trainer compatibility is Q6 in the qualification stage. | — |
| P9 | `$DET … $GRD --name p9-collect-w --add 50 --output $J/data/raw-OW-selection.json -- $RTPY reports/explore/x4s4/collect_w.py --checkpoint $J/inputs/main02.pt --count 6000 --workers 48` (≈1.2 h, beside the R5 fit); `$GRD --name p9-pack-OW --add 2 --output $J/data/onpolicy-w/batch-0000 -- $RTPY -m imitation.exit_r1.pack --roots $J/data/raw-OW --output $J/data/onpolicy-w/batch-0000`; `$GRD --name p9-verify-OW --output $J/data/OW-VERIFIED.json -- $RTPY $X/verify_onpolicy.py --mode OW --plan $X/plan.json --selection $J/data/raw-OW-selection.json` | selection reached; `OW-VERIFIED.json`; all three guards passed |
| P10 | Driver (after P7; in parallel with P9): `$DET logs/driver.log receipts/driver-launch.json nice -n 10 taskset -c 56-61 env X4S4_STUDY=$J python3 -u $R/reports/explore/x4s4/driver.py`. After a STOP, the driver leaves its loop once nothing lives; it is relaunched with the same command after the coordinator resumes. It runs the R5 and R5-rep fits after the O gate and R5W after the O_W gate, then calibrations and runtimes. | all three fits done and calibrated; no ANOMALY |
| P11 | Diagnostic, once no fit is live and before reporting: `env PYTHONPATH=… $GRDG --name p11-diagnose --gpu --output $J/analysis/diagnostic.json -- /mpac/sdicks02/envs/clasher-gpu/bin/python -B $X/diagnose.py` | descriptive only. A failure, or a guard that did not pass, is disclosed as "unavailable" and does not block. |
| P12 | `touch $J/REPORTING.GO`; the driver runs the ABBA block (≈8.5 h) | every phase settled; no ANOMALY |
| P13 | `env X4S4_READOUT=1 $GRD --name p13-contention --readout --output $J/receipts/contention-exclusion.json -- $RTPY $X/contention.py --job $J`; commit the receipt bytes to `reports/explore/x4s4/receipts/contention-exclusion.json` via temp index and push | the receipt SHA committed on origin/main **before** any reduction |
| P14 | `env X4S4_READOUT=1 $GRD --name p14-reduce --readout --output $J/analysis/results.json -- $RTPY $X/reduce.py --job $J --students R3a R5 R5-rep R3a-rep R5W --out $J/analysis/results.json --contention-sha <S> --freeze-commit <C>`. Add `--allow-prefix` only for an E8 hard-stop cut, which is disclosed. | guard passed |
| P15 | `env X4S4_READOUT=1 $GRD --name p15-report --readout -- $RTPY $X/write_report.py --contention-sha <S> --freeze-commit <C>`; commit RESULTS.md, the small receipts and every `guard-*.json` | the report is rendered; guard passed |

Production evidence returned:
- the parity, label, verify, gate, trainer, selection and acceptance receipts;
- the driver's events, anomalies and retired list;
- the phase exits and census summaries;
- the contention receipt and its commit;
- results.json, RESULTS.md and the diagnostic.

All of it is small JSON/Markdown, posted with SHAs at each milestone.

## E. Pass/fail and stopping rules

- **A HALT (J/HALT.json) ends the study.** The watchdog has already stopped the tree. I post HALT.json and the
  watchdog log, and nothing is restarted under the same T.
- Any failed step stops the stage. It is not retried silently.
  - I post the failing receipt and wait for the coordinator.
  - A retry needs a fresh phase directory; phase directories are never reused.
  - Every retry counts against T.
- A guard stop (memory, PSI, console user) is retried only after the condition clears, and is disclosed.
- **The qualification passes** when every one of these holds:
  - Q0, Q1, Q2, Q3, Q4, Q5, Q7 and Q8 pass;
  - Q6 passes (`smoke-pack.json` and `trainer.json`);
  - the smoke parity passes, or there is an exact-receipt PARITY-EXCEPTION.

## F. Evidence returned (small JSON/text receipts only; no game bytes, captures, checkpoints or corpora)

These are copied to `reports/explore/x4s4/receipts/qualification/`, committed via temp index with the secret scan,
and posted with their SHAs:

| Receipt | Content |
|---|---|
| `staging-check.txt`, `RUNTIME-INVENTORY.json`, `T.json` (T and HARD-STOP) | Staging and identity |
| `watchdog/heartbeat.json`, `watchdog/watchdog.log`, `watchdog/stop-periods.jsonl`; `HALT.json` if any | SR-1 backstop: last readings, signals, STOP periods; HALT absent for a passing stage |
| every `receipts/guard-*.json` | The producer receipts that consumers require (R8-F4), with their completion times (H-1) |
| `seed-audit.json` (Q0) | Pinned audit, intersections, omissions |
| `unit-tests.log` (Q1) | Pass count |
| `hashes.json` (Q2) | 16 cases: command hashes, belief, fair coverage |
| `frozen.json` (Q3) | 125/125 |
| `roundtrip.json`, `parity-smoke.json` (Q4) | 100% round trip; parity with its pinned phase evidence |
| `raw-OW-acceptance-smoke.json` (Q5) | 2 games, seals, replay_exact |
| `smoke-pack.json`, `smoke-plan.json` (Q6) | Games labelled, statuses, rows, drops, plan SHA, packed manifest SHA |
| `trainer.json` (Q6) | Store/targets, packed manifest SHA |
| Each phase's `launch.json`, `supervisor-exit.json` and `census.jsonl` summary (Q2/Q4/Q7/Q8) | Execution identity, exits, resource census |
| `stop-test.json` (Q8) | STOP time, exit time, remaining PIDs |
| `QUALIFICATION-SUMMARY.json` | Per-step pass/fail, durations, peak MemAvailable/PSI/process count/disk, all receipt SHAs |

PROGRESS is updated at each step, with `date -u` stamps. A post to the coordinator thread follows S3, then Q2, then
completion or any failure.
