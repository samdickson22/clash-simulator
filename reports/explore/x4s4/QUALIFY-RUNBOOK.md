# X4S-4 PLAN §6 qualification-stage launch runbook (exploration, NEVER ADOPTABLE)

This was prepared offline on 127x05 on 2026-10-12, while Sol r5 reviews scripts ffde20ac. It authorizes nothing: every
step on 127x01 waits for an explicit coordinator GO, and runs only if Sol approves the script set. If r5 asks for
changes, the commit and SHAs below are updated before use. Production (collection, labeling, fits, reporting) is
**not** part of this runbook; it needs its own GO after the qualification evidence is reviewed.

**Decision points for the coordinator (read first).**
1. **The T clock.** PLAN §7 defines T as the first launch after GO, and the hard stop as T+24 h, never reset. The
   qualification stage is the first launch, so `HARD-STOP-UTC.txt` is written at Q1 and the review gap between
   qualification and the production GO consumes the 24 h. Options:
   - (a) Accept this as frozen.
   - (b) Issue the production GO conditionally, at the same time as the qualification GO, effective automatically if
     every gate in §E below passes. A failure pauses the study for your decision.

   I recommend (b), because the study's own budget is about 19 h after qualification.
2. **§6.5 trainer compatibility has no reviewed producer.** It needs "a packed smoke batch". The reviewed `label.py
   plan` admits only bank-C collection phases with a bank-C parity receipt, so smoke captures cannot be labeled or
   packed by any reviewed path. Options:
   - (a) A narrow r6 addition, `qualify4.py smoke-pack`, which labels the smoke captures with `label.label_game` and
     packs them under `<job>/qual/` for `qualify4 trainer`. It needs Sol review.
   - (b) Defer §6.5 to the first real O batch: run `qualify4 trainer` on `data/onpolicy/batch-0000` after the O gate
     and before the R5 fit is admitted. That is a recorded amendment to §6 ordering.

   I recommend (a) if r5 returns changes anyway, and otherwise (b).
3. **Smoke C7b parity on 8 games/arm is noisy.** PLAN §6.2 asks for it on the collection smoke. With 8 games per arm
   the ±2 pp band can fail by chance. A failure writes PARITY-PAUSE and creates STOP, as designed. The coordinator
   then decides, through an exact-receipt PARITY-EXCEPTION, whether to continue to production. That decision counts
   against T.
4. **The seed audit (Q0) runs on 127x05**, with no host contact. It reads only git blobs of pinned commit 7f82af0d:
   - 7,705 sources;
   - the 29 sealed declarations Sol approved (r4, `seed-sources.json` v2).

   Please include Q0 in the GO. It can run before the 01 steps.

## A. Fixed identities

| Item | Value |
|---|---|
| Host | 127x01 only. No other host; 03/04/Mac never. |
| Job root `J` | `/mpac/sdicks02/jobs/clasher/x4s4-onpolicy`. It must not exist before staging. |
| X4S-3 job `J3` (read-only source) | `/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012` |
| Script commit `C` | `ffde20acd24ec77012a1d17a366702159c77ef03` (pending Sol r5) |
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
  56–61 with loaders on 120–125. Cores 50–55 and 62–63 stay free.
- **Processes and disk:** ≤ 70 X4S-4 processes (studytree admission reserves each phase's workers) and ≤ 100 GB
  under `J`. The expected peak is about 15 GB, mostly the copied base and captures.
- **Memory:**
  - Nothing is dispatched while MemAvailable < 24 GiB or memory PSI some avg10 > 10 (or PSI is unreadable).
  - Running work is killed only on MemAvailable < 24 GiB or owned PSS > 50 GiB.
- **GPU ≤ 40 GB.** The only GPU step is the trainer check (Q6, about 1 GB).
- **Console user:** yield, then ≤ 16 game processes (supervisor).
- **STOP:** `J/STOP`, which may be a dangling symlink, stops everything within about 2 min.
- **Hard stop:** `J/HARD-STOP-UTC.txt` = T+24 h, written once at Q1.

## C. Staging (S0–S3)

Every command below runs as `ssh 127x01 '…'` from 127x05, one command per call, and I record each exit status.

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
git -C /mpac/sdicks02/repos/clasher archive ffde20ac reports/explore/x4s4 | ssh 127x01 'tar -x -C /mpac/sdicks02/jobs/clasher/x4s4-onpolicy/staging'
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
- `reports/explore/x4s4/{supervise.py,x4s4io.py,studytree.py,qualify4.py}`;
- `reports/explore/x4s3/{run.py,runtime.sh}`;
- `fit/run_fit.sh`, `fit/loader6.json`;
- `inputs/assets.npz`.

The staging transcript (every SHA compared) is saved as `J/receipts/staging-check.txt`. **Staging writes nothing
outside `J`.**

Expected duration: about 10–20 min, dominated by copying `base`.

## D. Qualification steps (Q0–Q8), with exact commands

Common variables:

```bash
J=/mpac/sdicks02/jobs/clasher/x4s4-onpolicy
RT=$J/rt-R3a; R=$RT/repo; X=$R/reports/explore/x4s4
RUN="nice -n 10 taskset -c 0-49 env X4S3_RT=$RT bash $R/reports/explore/x4s3/runtime.sh"
DET="bash $R/reports/explore/x4s3/detach.sh"      # setsid detach (log, launch receipt, command)
SUP="nice -n 10 taskset -c 0-49 env X4S3_RT=$RT bash $R/reports/explore/x4s3/runtime.sh reports/explore/x4s4/supervise.py --job $J --rt $RT"
```

**Q0, on 127x05 (no host contact): seed audit at the pinned inventory.**

```bash
cd /mpac/sdicks02/repos/clasher && git -C . cat-file -e 7f82af0d4b3b6a465cba9a1b6dd26c708bcf25d1 && \
nice -n 19 /dev/shm/x4s4-venv/bin/python -B reports/explore/x4s4/audit_seeds.py audit
```

It writes `reports/explore/x4s4/seed-audit.json` and must exit 0, with `intersections=[]`. It takes about 1–3 min.

**Q1: start T, and run the unit tests.**

```bash
date -u -d '+24 hours' +%Y-%m-%dT%H:%M:%SZ > $J/HARD-STOP-UTC.txt     # ONCE; T recorded in receipts/T.json
cd $R && $RUN -m pytest -q reports/explore/x4s/test_sdefault.py reports/explore/s1/test_anchor.py reports/explore/s1/test_latency.py > $J/qual/unit-tests.log 2>&1
```

The tests must pass as in X4S-3 (31 tests). This takes about 1 min.

**Q2: capture non-perturbation (§6.2). Two detached phases, run sequentially.**

```bash
cd $J && $DET logs/q-run.log receipts/q-run-launch.json $SUP --phase qual/run --range qualification \
   --indices $X/idx-qual.json --config $X/plan-qual-capture.json --stop-at $(cat $J/HARD-STOP-UTC.txt)
# after qual/run/supervisor-exit.json shows reason null / returncode 0:
cd $J && $DET logs/q-collect.log receipts/q-collect-launch.json $SUP --phase qual/collect --range qualification \
   --indices $X/idx-qual.json --config $X/plan-qual-capture.json --stop-at $(cat $J/HARD-STOP-UTC.txt) \
   --script reports/explore/x4s4/collect.py
cd $J && $RUN $X/qualify4.py hashes --run-phase $J/qual/run --collect-phase $J/qual/collect \
   --config $X/plan-qual-capture.json --out $J/qual/hashes.json
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
cd $J && $RUN $X/qualify4.py frozen --corpus $J/base/corpus --threads 1 --out $J/qual/frozen.json
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
cd $J && $RUN $X/qualify4.py roundtrip --phases $J/smoke/collect-K4S-120 $J/smoke/collect-S-200 --threads 1 --out $J/qual/roundtrip.json
cd $J && $RUN $X/qualify4.py parity --phases $J/smoke/collect-K4S-120 $J/smoke/collect-S-200 --bank smoke --min-games 8 --out $J/qual/parity-smoke.json
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
cd $J && $DET logs/q-ow-acc.log receipts/q-ow-acc-launch.json nice -n 10 taskset -c 0-49 env X4S3_RT=$RT \
   bash $R/reports/explore/x4s3/runtime.sh reports/explore/x4s4/collect_w.py --checkpoint $J/inputs/main02.pt \
   --count 1 --workers 1 --acceptance-smoke
```

Pass: `data/raw-OW-acceptance-smoke.json` `passed=true` (2 games, replay_exact, sealed). The gate re-verifies it
later. About 3–5 min.

**Q6: trainer compatibility (§6.5).** Blocked on decision point 2. With option (a), after an r6 review:

```bash
cd $J && $RUN $X/qualify4.py smoke-pack ...            # r6 only
cd $J/fit/source && PYTHONPATH=$J/fit/source:$J/fit/source/src:$J/fit/ops nice -n 10 taskset -c 56-61 \
   /mpac/sdicks02/envs/clasher-gpu/bin/python -B $X/qualify4.py trainer --packed $J/qual/smoke-pack/batch-0000 \
   --assets $J/inputs/assets.npz --out $J/qual/trainer.json
```

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

**Expected total wall time** is about 1.5–3 h, plus 10–20 min of staging. It is CPU-bound on cores 0–49, and the GPU
is idle except Q6. The order is Q0 (05) → S0–S3 → Q1 → Q2 → Q3 → Q4 → Q5 → Q7 → Q8 → Q6 (if available).
Independent CPU steps never overlap phases: one supervisor phase at a time.

## E. Pass/fail and stopping rules

- Any failed step stops the stage. It is not retried silently.
  - I post the failing receipt and wait for the coordinator.
  - A retry needs a fresh phase directory; phase directories are never reused.
  - Every retry counts against T.
- A guard stop (memory, PSI, console user) is retried only after the condition clears, and is disclosed.
- **The qualification passes** when every one of these holds:
  - Q0, Q1, Q2, Q3, Q4, Q5, Q7 and Q8 pass;
  - Q6 passes, or decision 2(b) is ruled;
  - the smoke parity passes, or there is an exact-receipt PARITY-EXCEPTION.

## F. Evidence returned (small JSON/text receipts only; no game bytes, captures, checkpoints or corpora)

These are copied to `reports/explore/x4s4/receipts/qualification/`, committed via temp index with the secret scan,
and posted with their SHAs:

| Receipt | Content |
|---|---|
| `staging-check.txt`, `RUNTIME-INVENTORY.json`, `T.json` (T and HARD-STOP) | Staging and identity |
| `seed-audit.json` (Q0) | Pinned audit, intersections, omissions |
| `unit-tests.log` (Q1) | Pass count |
| `hashes.json` (Q2) | 16 cases: command hashes, belief, fair coverage |
| `frozen.json` (Q3) | 125/125 |
| `roundtrip.json`, `parity-smoke.json` (Q4) | 100% round trip; parity with its pinned phase evidence |
| `raw-OW-acceptance-smoke.json` (Q5) | 2 games, seals, replay_exact |
| `trainer.json` (Q6) | Store/targets, packed manifest SHA |
| Each phase's `launch.json`, `supervisor-exit.json` and `census.jsonl` summary (Q2/Q4/Q7/Q8) | Execution identity, exits, resource census |
| `stop-test.json` (Q8) | STOP time, exit time, remaining PIDs |
| `QUALIFICATION-SUMMARY.json` | Per-step pass/fail, durations, peak MemAvailable/PSI/process count/disk, all receipt SHAs |

PROGRESS is updated at each step, with `date -u` stamps. A post to the coordinator thread follows S3, then Q2, then
completion or any failure.
