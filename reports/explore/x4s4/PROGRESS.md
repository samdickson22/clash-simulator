# X4S-4 PROGRESS (exploration, NEVER ADOPTABLE)

Pins: QUALIFY-RUNBOOK 7b3ec27b (SHA-256 c55ba41d1ddf5e9a7d283d23622f1f53d336f40ccfd9aaf9fa4a6dbf9da0b763),
scripts d09bdef9aecc416cb83b002fcff002ff57579fde. GO: COORDINATOR commit 4b33d68d. This is the single combined
qualification + conditional production GO (Q-D1).

## 2026-10-13T03:37:03Z — Q0 seed audit (127x05, offline): PASS

- Command: exactly as in the runbook, from a git-archive export of d09bdef9 at /dev/shm/x4s4-q0. Pinned commit
  7f82af0d present; nice 19, cores 0–3.
- Exit 0. intersections = [], own_reservation_echoes = [], raw literal scan hits = [].
- 7,705 sources; source-list SHA-256 844ab58918b8e56ed6e367e21073e796fcc4ee90d7901584207add27c8e3f5af (the pinned v2
  inventory); 128 declarations parsed; omitted {not_text 458, outcome_path 812, sealed 2687, own 28, not_regular 1,
  alias_of_excluded 55}.
- Receipt: receipts/qualification/seed-audit.json, SHA-256 9275f2b6cf62535ee14a13bedfad06c674a5f360456e3a8249a07fbe8fb46f64.

## 2026-10-13T03:37:03Z — waiting for "U2 drained" (coordinator)

U2 finishes R3a-rep2's S-200 phase, then drains. There is no contact with 127x01 until the coordinator forwards
"U2 drained". After that come S-U2 (read-only verification), then S0–S3, then W0.

## 2026-10-13T04:48:57Z — "U2 drained" received (COORDINATOR 14d8bdb7); S-U2: PASS (read-only)

- U2's STOP is present; no process command line refers to J2; working directories under J2: 0.
- GPU used 107 MiB; MemAvailable 127,717,088 kB.

## 2026-10-13T04:49Z — S0 preflight on 127x01: PASS (read-only)

- 0 console users; MemAvailable 121 GiB; PSI some avg10 0.00; GPU 107 / 48,682 MiB; 804 GB free on /mpac; J absent;
  0 hard links in the X4S-3 base.
- Pins: main02 d77005d5…, R3a 37509a43…, R3a-rep 8d537a78…, assets 3954af44… (matches X4S-3's committed fit
  receipts).

## 2026-10-13T04:49:28Z — S1 built J; the pinned d09bdef9 x4s4 tree streamed into J/staging (rc 0)

## 2026-10-13T04:49:51Z — S2 verification: FAILED. The stage is stopped and the coordinator is asked

- The transcript is J/receipts/staging-check.txt on 01 (SHA-256 6c640b245198430a8dd5e4a06dbe23cd48e6b2d568a3567e7818f6687356afd8).
- 38 of 41 checks pass: every staged x4s4 file against d09bdef9, and x4s3 run.py, runtime.sh, detach.sh and
  calibrate.py against c86d928d.
- Fails 1–3: `base/repo/imitation/exit_r1/{rows,pack,emitter}.py` are missing. The X4S-3 base contains no
  `imitation/exit_r1` package. A runbook staging-layout error (mine): X4S-4 needs these at runtime (label seals,
  the frozen packer, the O_W emitter).
- Also: `base/corpus/` does not exist. The Q3 corpus is at J3/corpus/; there states-ready.pkl = 8b188918… and
  symmetric-screen-samples.json = 86ecbb60…, both matching the pins.
- Checked read-only: every other module that rows/pack/emitter import is present in the X4S-3 base (fair_player,
  quickwin_resources in engine-rs, stage2_matches, delay, derived_public_state, clasher.rl.*, imitation.evaluation.*,
  imitation.model.*, exit_r3). Inside exit_r1, pack and emitter import only `.rows`.
- T has not started (Q1 has not run). No study process exists, the watchdog is not started, and nothing outside J
  was written.

## 2026-10-13T04:52:29Z — SA-1 approved (COORDINATOR 69345e4a): S1b and S1c done

- S1b: `git archive 04c068f5` of imitation/exit_r1/{__init__,rows,pack,emitter}.py into J/staging, then `cp -a` into
  base/repo/imitation/exit_r1.
- S1c: `cp -a J3/corpus J/base/corpus` (J3 read-only).

## 2026-10-13T04:52:43Z — S2 r2: PASS 44/44

- Every x4s4 file matches d09bdef9; x4s3 run.py, runtime.sh, detach.sh and calibrate.py match c86d928d.
- exit_r1 __init__ 441385ea, rows 835a4104, pack 5442af29 and emitter dab61651 match origin/main.
- Corpus states-ready 8b188918… and samples 86ecbb60… match the pins.
- Transcript: J/receipts/staging-check-r2.txt (final SHA-256 c2dd5ce9e907ebfc341c403d8cf40badda2f90ca3b2b9e3fcbefa365aa552ebe,
  with the S2-overlay and S3 lines appended).

## 2026-10-13T04:53:10Z — S2 overlay and S3 done

- Overlay as written; rt-R3a plan.json = 13840cc6… (the pinned x4s4 plan).
- rt-R3a-rep: one JSON edit of the student block (R3a-rep checkpoint J/inputs/R3a-rep.pt 8d537a78…, threshold
  0.49952925741672516, calibration_sha256 bc98ac28… from X4S-3's rt-R3a-rep). Plan 9fd84588…; READY.json (0444)
  ce05febd….
- S3: J/RUNTIME-INVENTORY.json (0444), SHA-256 5e7a9cf2e351238dcd2afa337409de697ddbaef7d8a86ef4ac587162ff2b93f1. Every
  value was cross-checked against d09bdef9 / c86d928d / the assets pin / J3's loader6.json (30c64b1d…). J is 1.1 GB.

## 2026-10-13T04:53:50Z — W0 watchdog: PASS

- `watchdog.py start` as written: pid 3283869, its own session (sid = pid), nice 10, core 62, no X4S4_* variables in
  its environment.
- `watchdog.py status`: ok=true, exit 0. Heartbeats arrive 9.55 s apart.
- First readings: 0 study processes, MemAvailable 121.8 GiB, PSI 0.0, disk 1.10 GB, GPU 107 MiB. No HALT.

## 2026-10-13T04:55:07Z — Q1: T started; unit tests PASS

- T = 2026-10-13T04:55:07Z. HARD-STOP-UTC.txt = 2026-10-14T04:55:07Z (written once, 0444, SHA-256
  bf6804f010e38fe4d6442b23cf807454978990f7cb42d9b3f75962a827eaaef2). receipts/T.json (0444) SHA-256
  002f86dbfd2d1bd30d7ea80a44402f7a85db7329d71fb788d8ab4697d77f59fe.
- `watchdog.py status` ok before the step. Then `$GRD --name q1-unit-tests …` as written: 31 passed in 0.24 s (as in
  X4S-3). guard-q1-unit-tests.json passed=true, returncode 0, SHA-256
  36ef38cb09011e496e302479016bc44c13406325cc4b3a13fd37183c50bf4f0b.
- Watchdog status ok afterwards; no HALT.

## 2026-10-13T05:05:19Z — Q2 capture non-perturbation: PASS

- `watchdog.py status` ok before each step.
- qual/run: launched 04:56:43Z; exit rc 0, reason null, 8/8 blocks, no remaining pids, 121 s wall (supervisor-exit
  SHA-256 1fe120b0ef0131ba446461698e6da64c2c16764e2f730472fd0852e758b4a35c).
- qual/collect: launched 05:01:05Z; exit rc 0, reason null, 8/8 blocks, 142 s wall (supervisor-exit SHA-256
  74700c0703fe5fe699e9d629d58e6a95ee829dbea59859c7d3e87b9ba1b719d2).
- Both phases ran much faster than the runbook estimate of 15–40 min each. `hashes` enforces the 1,000 s budget in
  each game's projected metadata, so the budget was in force.
- `$GRD --name q2-hashes` as written: passed. hashes.json SHA-256
  0545d4203475f8f65d2fe13bb87fedae9aadb5380efe68f461f44daa346604d7; guard-q2-hashes.json SHA-256
  1a9796a8091421bbb724dfd16a220b4c5dac19696498c41dd9f0b118cbdfa4b5.
  - same_schedule; 16 cases, each block-proved and terminal.
  - Every game: equal command hashes, capture SHA, identity, features/public equal, empty pending, count_ok.
  - Belief unchanged on every decision; fair-identical on every decision.
  - Fair coverage: 23–83 perturbed decisions per game, and every early check perturbed.

## 2026-10-13T05:06:08Z — Q3 labeler equals the frozen teacher: PASS

- `watchdog.py status` ok before the step; `$DET … $GRD --name q3-frozen` as written.
- 125/125 equal, no mismatches, threads 1. frozen.json SHA-256
  7cc7afcb2081d89c1fcff05985c8390ccb661673eb31edd46a2ddfde3f853c44; guard-q3-frozen.json passed, rc 0, SHA-256
  db627c1fb5f1cf691907df725db97f862cdcb2bcb4b3a39c16c80ced12661282.

## 2026-10-13T05:12:17Z — Q4 smoke collection phases done; round trip launched

- `watchdog.py status` ok before each step.
- smoke/collect-K4S-120: rc 0, reason null, 8/8 blocks, 81 s wall (exit SHA-256
  5d95f494a36057cd1ac48bc5d82aa5914cf6eb40f18579334490ee2a11b08f6d).
- smoke/collect-S-200: 50 lanes; rc 0, reason null, 8/8 blocks, 115 s wall (exit SHA-256
  c7a37337c19a310be336a487598df43f98a24bacd5e43257185903127477507d).
- The q4-roundtrip guard step was launched detached at 05:12:17Z, as written.

## 2026-10-13T05:27:34Z — Q4 round trip PASS; smoke parity OUT OF BAND: decision point 3, paused for the coordinator

- Round trip (`$DET … $GRD --name q4-roundtrip`, as written): passed. 1,762 captures checked (100% of smoke
  captures), 0 digest mismatches, 0 repeat-unequal, 0 missing C8 fields. roundtrip.json e905ec5f…;
  guard-q4-roundtrip.json passed, rc 0, 3a0536a0….
- Parity (`$GRD --name q4-parity`, as written): FAILED. Both arms were evaluated (8 games each), and both are
  outside the ±2 pp band:

  | Arm | Metric | X4S-4 smoke, 8 games | X4S-3 R3a | Within ±2 pp |
  |---|---|---:|---:|---|
  | K4S-120 (1,038 decisions) | cutoff % | 58.67 | 64.2 | no (−5.53) |
  | | student-default % | 19.94 | 22.3 | no (−2.36) |
  | | overrun % | 0.10 | 0.16 | yes |
  | S-200 (1,362 decisions) | cutoff % | 69.75 | 75.3 | no (−5.55) |
  | | student-default % | 0.00 | 0.0 | yes |
  | | overrun % | 0.22 | 0.14 | yes |

- qualify4's pause path wrote receipts/PARITY-PAUSE-2026-10-13T052734Z.json (cd48d0d8…) and J/STOP, a 0-byte regular
  file. The parity output parity-smoke.json (10c68b04…) has passed=false, final=true, halted=owned_STOP.
  guard-q4-parity.json (721806ce…) has passed=false, rc 1.
- After the step: the watchdog is ok and saw 0 study processes. There is no HALT. STOP stays in place, and I resume
  only through `watchdog.py resume` after a coordinator decision.
- Per the runbook, this is decision point 3. Q6, Q5, Q7 and Q8 have not run. The receipts are copied, byte-identical,
  to receipts/qualification/.

## 2026-10-13T05:30:28Z — PE-1 (COORDINATOR f6afe586): exception written, resumed

- f6afe586 is on origin/main, and its COORDINATOR.md contains the full parity receipt SHA (10c68b04…).
- J/data/PARITY-EXCEPTION.json was written once, O_EXCL, 0444, fsync'd: `{"parity_receipt_sha256": "10c68b04df32c436325cc966a34b243810f351f98eb1d80f0a93ed2aaaf3b972", "decision": "disclose", "coordinator_commit": "f6afe586288f0f05376d103deeada9d480c526f5"}`.
  Its SHA-256 is afeaf7cb290eec3d3835290f1dfd15d13cf7ac6192df7d27970de98a73badb8f, and the shape matches label.py `check_parity`.
- `watchdog.py resume` returned {"resumed": true}, rc 0. stop-periods.jsonl recorded the period start (05:27:34Z,
  epoch 1791869254.55) and its end (epoch 1791869428.23). STOP is gone, and status is ok.
- The PE-1 control-check procedure was prepared on 05: a fresh export of d09bdef9 (qualify4.py 05cc98fd…) runs
  `parity_once` read-only on a copy, with io.JOB set to the copy.
  - It was validated on a copy of the Q4 smoke-collect phases and reproduced the receipt exactly (58.67 / 19.94 / 0.10
    and 69.75 / 0.00 / 0.22). The validation copy was then deleted.

## 2026-10-13T05:38:54Z — Q6 trainer compatibility: PASS

- smoke-pack (`$DET … $GRD --name q6-smoke-pack`, as written): passed.
  - 16 games, every one `sealed`; 1,762 captures attempted, 1,762 rows, 0 drops.
  - Packed manifest 1dc15961…. smoke-pack.json e3e63c9f12b209573a484be4f73efcafac32ad06916f63fc466d716bd3ace483.
  - guard-q6-smoke-pack.json passed, rc 0, 6624f2eaef159a5a76be3889bc578c116f72fc25351bb87e574fcd448c8b520e.
- trainer (`$GRDG --name q6-trainer --gpu`, as written): passed.
  - rows = roots = 1,762, batch 64, the targets are finite and normalized.
  - trainer.json f5252547fd5216daa158976bd1648263fcece50fe2493ce732e6ab22b02bb681.
  - guard-q6-trainer.json passed, rc 0, d73c984de54fc7a5e38e01cb723f77013c2afe42c50609168bf5909eb56e61c6.
- Q5 was launched at 05:38:59Z, as written.

## 2026-10-13T05:39:19Z — Q5 emitter acceptance smoke: FAILED (stage stopped; coordinator asked)

- `watchdog.py status` ok before the step; `$DET … $GRD --name q5-ow-acceptance --add 3 …` as written.
- data/raw-OW-acceptance-smoke.json (0444, SHA-256 6881ba19380bfcb6f6ebddf34e54e683bc5c8b9ababec3f0acc2e84adf797cfb)
  has passed=false. Game g=0 failed with `ValueError('invalid action')`, so g=1 was never dispatched.
  data/raw-OW-acceptance/ is empty.
- guard-q5-ow-acceptance.json: passed=false, "child exit 1", rc 1, no breach (SHA-256
  095a0a95b89f8896aafff80330410cf08c8711758cf60e0ab630fb2fd962581c).
- There is no STOP and no HALT, and the watchdog is ok with 0 study processes.
- Root cause, from offline reading on 05 plus read-only SHA checks on 01. This is a staging version skew of the
  same class as SA-1:
  - The runtime's `reports/strategy_council_20260928/search-noise-s6/delay.py` is the 20cff68a version (SHA-256
    96b0637c…), the same in base/, rt-R3a/ and rt-R3a-rep/.
  - The O_W emitter (imitation/exit_r1/emitter.py dab61651…, staged by SA-1 from origin/main) builds its teacher with
    `C56SearchConfig(threads=1, wait_screen8=True)` and `DelayAwarePlanner(delay_aware=True, command_delay=27)`.
  - With W-screen8 on, `C56RolloutPlanner.candidates` (runtime = main, 4fa6940f…) appends the timed waits 2400–2402.
  - 59454e1a ("native W-screen8 in shared S6") added two lines to `DelayAwarePlanner.score_candidates`:
    `if self.config.wait_screen8: return super().score_candidates(...)`, which dispatches to the native W-screen8
    scorer. The runtime file lacks them, so it runs its delayed rollouts: `candidate_root` → `CommandChannel.submit(2400)`
    → `ValueError('invalid action')`, since actions above 2305 are rejected.
  - delay.py (origin/main blob 2f7626dc…, SHA-256 fa3d3296…) is the only W-screen8 file that differs.
    c56_rollout_planner.py and wait_screen8.py match origin/main, and the runtime native exports `score_wait_screen8`.
  - Every other runtime path builds `wait_screen8=False`: x4s3/run.py, x4s/run.py, s1/run.py, e1/run.py,
    x4s4/run_collect.py, x4s4/label.py and x4s3/qualify.py. For them the two added lines never execute.
  - Of 602 runtime .py files on the import roots, 574 match origin/main. 15 differ: the frozen X4S-3 base, including
    the imitation/evaluation runtime_dependencies edits and delay.py. 13 are not on main. Only delay.py lies on the
    emitter's W-screen8 path.
- RUNTIME-INVENTORY.json does not pin delay.py.

## 2026-10-13T05:47:48Z — SA-2 (COORDINATOR 55254853) applied; Q5 r2: PASS

- Step 1: `git archive 55254853` (origin/main) of search-noise-s6/delay.py went into J/staging/sa2 (staged SHA-256
  fa3d3296…). From there it was copied, using a temp file and mv, into base/repo, rt-R3a/repo and rt-R3a-rep/repo.
  - All three went from 96b0637c… to fa3d32965e9153f3ef9aed4ad890796574c8e954c9b5f5656ebea7e58a82d67d: PASS ×3.
  - No delay pycache existed. The lines were appended to receipts/staging-check-r2.txt.
- Step 2: the failed data/raw-OW-acceptance-smoke.json (6881ba19…) was moved to receipts/q5-r1-failed/, and the empty
  data/raw-OW-acceptance/ was removed with rmdir. Both were logged to the staging transcript.
- Step 3: `watchdog.py status` ok, then Q5 as written, with `--name q5-ow-acceptance-r2`.
  - The DET log and launch receipt were named logs/q-ow-acc-r2.log and receipts/q-ow-acc-r2-launch.json, so the r1
    files are not overwritten.
  - Result: passed. g=0 (seed …496, index 56, seat 0, 153 roots) and g=1 (seed …497, index 57, seat 1, 111 roots)
    are both `sealed` with replay_exact=true, and the v1/emitter SHAs are as pinned.
  - raw-OW-acceptance-smoke.json 88b884d6117dbe4d6c8059db5d36319c17d49a09a5a57fd9b2cb3bdaba46ecfa;
    guard-q5-ow-acceptance-r2.json passed, rc 0, 0edf5437588b63ab49c42599495d888563977e5406a731853b532b5a1a7753af.
- Q7 smoke/eval-K4S-120 was launched at 05:48:01Z after the tree drained to 0.

## 2026-10-13T05:50:21Z — Q7 evaluation smoke: PASS

- smoke/eval-K4S-120 (05:48:01Z): rc 0, reason null, 8/8 block proofs, 58 s wall (exit b001d6b9…).
- smoke/eval-S-200 (05:49:12Z): rc 0, reason null, 8/8 block proofs, 68 s wall (exit 7a631fe1…).
- Outcomes were not inspected.

## 2026-10-13T05:51Z — PE-1 control check (on 05, read-only, no STOP): neither outcome the ruling defined; the S-200 capture path is implicated

- Method: the two Q7 phases' blocks/ and games/ were copied with rsync from 01 to /dev/shm on 05, together with
  HARD-STOP-UTC.txt and stop-periods.jsonl. The copy was then deleted.
  - pe1_check.py (ec0745c0…) runs the reviewed `qualify4.parity_once` from a d09bdef9 export, with io.JOB set to the
    copy, so nothing is written into J.
  - On the Q4 phases, the same procedure reproduced the Q4 receipt exactly.
- pe1-control.json (a2937fb5…):

  | Arm | Path | Games | Decisions | Cutoff % | Student-default % | Overrun % |
  |---|---|---:|---:|---:|---:|---:|
  | K4S-120 | collection (Q4) | 8 | 1,038 | 58.67 | 19.94 | 0.10 |
  | K4S-120 | evaluation (Q7) | 8 | 924 | 56.06 | 16.13 | 0.00 |
  | K4S-120 | X4S-3 R3a | — | — | 64.2 | 22.3 | 0.16 |
  | S-200 | collection (Q4) | 8 | 1,362 | 69.75 | 0.00 | 0.22 |
  | S-200 | evaluation (Q7) | 8 | 1,056 | 55.78 | 0.00 | 0.28 |
  | S-200 | X4S-3 R3a | — | — | 75.3 | 0.0 | 0.14 |

- Against the ruling's thresholds:
  - K4S-120 evaluation is 2.61 pp below the smoke collection value: just outside the ±2 pp "bank/host" band, and
    8.1 pp from X4S-3.
  - S-200 evaluation is 13.97 pp below the smoke collection value, and 19.5 pp from X4S-3.
  - Neither "within 2 pp of smoke" nor "near X4S-3" holds.
- A descriptive per-seed pairing (pe1_perseed.py 0bc1b873…, output pe1-perseed.json 4290835c…) uses the reviewed
  proved_game/game_meta projection on the same index in both phases, with timing metadata only:
  - S-200: collection cutoff % > evaluation on 8/8 seeds; mean per-seed Δ +9.7 pp (range +0.4 to +26.4); sign test
    p ≈ 0.008.
  - K4S-120: 5/8 seeds; mean Δ +2.2 pp (range −26.0 to +23.9); noisy.
  - The S-200 collection games also have more decisions on 6/8 seeds (for example 299 vs 146).
- Reading:
  - Both paths sit well below X4S-3, so a bank/host effect exists.
  - In addition, the capture/collection path itself raises S-200 cutoffs on the same seeds. This is consistent with
    capture overhead inside S-200's 200 ms deadline.
  - Per PE-1, production does not start; the coordinator is asked.

## 2026-10-13T05:53:25Z — Q8 live STOP test: PASS

- smoke/stoptest launched at 05:52:05Z. `ln -s nowhere $J/STOP` was made at 05:53:05.69Z, 60 s after launch, as a
  dangling link.
- supervisor-exit (a187b9af…): reason owned_STOP, rc −15, remaining_group_pids [], at 05:53:07Z (1.3 s after STOP).
  The tree count is back to 0.
- Block proofs 0002, 0003, 0004 and 0007 all completed before STOP (last at 05:53:04.63Z). Indices 0, 1, 5 and 6 have
  no game and no block proof.
- `watchdog.py resume` returned {"resumed": true}. The STOP period 05:53:05.69–05:53:25.15Z is recorded. Status is
  ok, with 0 processes.

## Qualification verdict (2026-10-13 ~05:55Z)

- Every §6 gate passes:
  - Q0, Q1, Q2 and Q3;
  - Q4: round trip passed; parity carries the PE-1 exact-receipt PARITY-EXCEPTION, decision "disclose";
  - Q5: r2 after SA-2;
  - Q6, Q7 and Q8.
- PE-1's control condition for production is NOT met; see above. Production (G) has not started, and the
  coordinator is asked.
- The SA-2 follow-up sweep (sa2-module-sweep.md) found no other W-screen8/delay skew. The runtime-imported
  differences are the frozen X4S-3 base's paths.py edit and its untracked loss_review/runtime_dependencies modules.
  Nothing was changed.
- search-noise-s6/delay.py (fa3d3296…, in all three runtime copies) is on my pre-production check list.
- T+1.0 h of 24 h is used.

## 2026-10-13T06:01:25Z — PE-2 test B (COORDINATOR b98fda79): contention branch, so SA-3; production started (P1)

- `watchdog.py status` ok before each step.
- smoke/collect-S-200-w10 (05:56:17Z, `--workers 10`, otherwise as in Q4): rc 0, 8/8, 104 s (exit 69df22fd…).
- smoke/eval-S-200-w10 (05:58:29Z, `--workers 10`, otherwise as in Q7): rc 0, 8/8, 107 s (exit 6300dad8…).
- The paired control on 05 used the same procedure: a read-only copy (since deleted), pe2_paired.py (e09fd28e…, the
  reviewed parity_once and proved_game/game_meta at d09bdef9). Output pe2-paired-w10.json is 33396743….
  - Pooled at 10 workers: collection cutoff 64.82 % (1,245 decisions), evaluation 66.69 % (1,381 decisions).
    Overrun 0.24 / 0.22 %.
  - Paired per-seed collection − evaluation: mean **−0.70 pp**; collection higher on 4/8 seeds; range −11.2 to +7.6.
  - This is ≤ 3 pp, so PE-2's contention branch applies. **SA-3:** S-200 collection (P2) runs at `--workers 10`.
  - Disclosure: run-to-run variance on the same seeds is large. Pooled S-200 evaluation cutoff was 55.78 % at 50
    lanes and 66.69 % at 10. So the 8-seed contrasts are noisy, and both 8-game paired tests should be read with that
    in mind.
- Pre-production check list: search-noise-s6/delay.py is fa3d3296… in base, rt-R3a and rt-R3a-rep (3/3). The
  watchdog is ok. No console user.
- P1: collect/idx-K4S-120.json is [0,2000) ∪ [3500,3750), 2,250 indices (36ad48a2…). collect/idx-S-200.json
  ([2000,3500) ∪ [3750,4000), 1,750 indices, 2e96a28e…) was also written; the two are disjoint, and their union is
  4,000.
  - `$DET logs/p1-collect-k.log receipts/p1-collect-k-launch.json $SUP --phase collect/K4S-120/a1 --range reporting …`
    as in G, launched at 06:01:25Z.
- Risk raised with the coordinator: supervise.py's in-loop C7b watch (every 300 s, at ≥ 100 games) compares against
  X4S-3's R3a and has no exception path. If K4S-120 collection stays about 5 pp low, as in the smoke, P1 will
  PARITY-PAUSE, and any relaunch would pause again.

## 2026-10-13T06:11:35Z — P1 a1 paused, low side; PE-3 (COORDINATOR f4a2bc1f) disclose; SA-4 prepared

- P1 a1 stopped with reason parity_pause, rc −15, no pids left, 147 blocks (exit 32320f1e…).
  - Receipt PARITY-PAUSE-2026-10-13T061133Z.json, b63b4a993902de41c01cf216dc2bc64e7b706820a08cb3bf8da97fa6c622a4b9.
  - Reading: K4S-120, 147 games, cutoff 61.30 % vs 64.2 (−2.90 pp, low side); student-default 20.96 % and overrun
    0.12 % in band.
  - STOP is kept in place. PE-3 grants "disclose" for this exact receipt; resume only with SA-4 installed.
- a1 holds 147 captures, 147 blocks and 147 games, all completing before STOP, so there are no H-1-late blocks.
  - The runner runs exactly the `--indices` it is given and does not skip indices other phases already proved.
  - label.py make_plan refuses duplicate (arm, index) capture files across phases.
  - So a2's index file is a1's indices minus a1's 147 proved indices, in the same order: 2,103 indices.
- SA-4 (COORDINATOR 08723c23) changes `supervise.parity_watch` only.
  - It is one-sided: a pause only if any evaluated metric is more than 2 pp above X4S-3. A low-side reading is
    appended to receipts/parity-lowside.jsonl. Monitor or record failures give parity_monitor_failed.
  - Tests: test_sa4 has 6 cases over 11 scenarios, and the R2-F8 fixture moved to the high side.
  - Mutation check: 10/10 mutants killed.
  - Matrix: 6/6 at 134 cases. One O2/u022 run first failed in the r9 SR-1 real-process watchdog case: the no_deadline
    breach HALTed first on "measurement overdue (> 0.8 s)" with 05's load average around 15. watchdog.py is not
    touched by SA-4. The rerun passed.
  - supervise.py goes from ae51e9b9… to 357972487727d2f1471682fc273dd167cc71afb25a3cb7c138ad233780665189.

## 2026-10-13T06:27:49Z — SA-4 installed (COORDINATOR f0156bef); PE-1 file moved; resumed; a2 index file

- `git archive d292cde3` of supervise.py went into J/staging/sa4 (357972487727d2f1…). It was copied, via a temp file
  and mv, into base/repo, rt-R3a/repo and rt-R3a-rep/repo: PASS ×3, from ae51e9b9… to 35797248….
- RUNTIME-INVENTORY was re-sealed. r1 (5e7a9cf2e351238dcd2afa337409de697ddbaef7d8a86ef4ac587162ff2b93f1) is kept,
  unchanged, as receipts/RUNTIME-INVENTORY.r1.json.
  - The new J/RUNTIME-INVENTORY.json is O_EXCL, 0444, fsync'd: 027e468afc3d2459c65536a659b0b7fe9153f3a0cf8706502e81d291745fe280.
  - Only the supervise.py value changed, with r1's formatting kept.
  - All 12 entries match the files in rt-R3a, rt-R3a-rep and base (repo files) and in J (fit and inputs files).
- PE-1 file: data/PARITY-EXCEPTION.json was moved to receipts/PARITY-EXCEPTION-PE1-smoke.json, bytes unchanged
  (afeaf7cb… before and after).
- The staging transcript (receipts/staging-check-r2.txt) is now 122629f8….
- `watchdog.py resume` returned {"resumed": true}, closing the PE-3 STOP period at epoch 1791872869.54. Status ok,
  0 processes.
- **a2 index file**: J/collect/idx-K4S-120-a2.json (0444) =
  **ff40ae398292cb9eb66ca07ed3a1b6986b817d84668feb540e943cfff9400d76**.
  - It is idx-K4S-120 minus a1's 147 proved indices (the proved set equals the captured set), in the same order:
    2,103 indices, first 144, 148, 149, last 3749.
  - The runner does not skip sibling phases, so the index file excludes a1's indices.

## 2026-10-13T08:45:47Z — P1 done (K4S-120: a1 147 + a2 2,103 = 2,250); P2 launched 08:48:57Z at --workers 10 (SA-3)

- collect/K4S-120/a2: rc 0, reason null, remaining_group_pids [], 2,103/2,103 blocks, 8,253 s wall (exit f0678e1f…).
  a1 has 147 blocks and 147 captures, a2 has 2,103 and 2,103, which covers all 2,250 K4S-120 collection indices.
- SA-4 watch in production: 13 low-side records (receipts/parity-lowside.jsonl, 9bd6c4c8…). The last, at 07:35:15Z
  over 1,164 games, read cutoff 62.19 %, student-default 21.42 % and overrun 0.15 %. Later checks were in band, so
  nothing was recorded. There were no pauses and no STOP.
- Watchdog ok throughout. J is 17 GB.
- P2: `$SUP --phase collect/S-200/a1 --range reporting --indices $J/collect/idx-S-200.json (2e96a28e…) --config
  $X/plan-collect.json --arms S-200 --script reports/explore/x4s4/collect.py --workers 10 --stop-at …`, launched at
  08:48:57Z. `watchdog.py status` was ok beforehand and there was no console user.

## 2026-10-13T11:20:16Z — P2 done; P3: K4S-120 in band, S-200 low side only; the exception path is blocked, so SA-5 (approved in principle)

- P2 collect/S-200/a1 (`--workers 10`, SA-3): rc 0, reason null, 1,750/1,750 blocks, 8,727 s wall (exit e8de3a16…).
  The SA-4 watch recorded low-side readings only (39 lines in parity-lowside.jsonl by 11:09Z); no pauses.
- P3: `$GRD --name p3-parity --output receipts/parity-collection.json -- … qualify4.py parity --phases
  collect/K4S-120/a1 collect/K4S-120/a2 collect/S-200/a1 --bank collection --min-games 100`.
  - a2 (from PE-3) is included because check_parity requires exactly the phases that feed the plan.
  - K4S-120: 2,250 games and 276,281 decisions; cutoff 62.46 / student-default 21.53 / overrun 0.15, all within
    ±2 pp.
  - S-200: 1,750 games and 268,769 decisions; cutoff **63.32 vs 75.3 (−11.98, low)**; student-default 0.00 and
    overrun 0.06 in band.
  - parity-collection.json f4082f32524664a4347d7b47417b3b0e1aea3633c949b81b06834d2064facf79: passed=false,
    final=true, halted=owned_STOP.
  - PARITY-PAUSE-2026-10-13T112015Z.json 158d651f…; guard-p3-parity.json b1983061… (passed=false, child exit 1).
  - STOP is in place (created by qualify4's pause path).
- Defect: a failed P3 can never be accepted by label.check_parity, because (1) its guard always fails (exit 1) and
  (2) H-1 excludes it, since the receipt completes inside the STOP that pause() created. The offline fixture had
  blessed the failed receipt.
- SA-5 (COORDINATOR 5483e9d6, approved in principle), prepared offline:
  - `qualify4 parity --final`: no pause, refuses `--watch`, and exits 0 iff `final_check_completed` (final, per-arm
    reading, no error, no halt); the verdict stays in `passed`.
  - test_sa5: real guard.py + real qualify4 child, the end-to-end label.make_plan check, the fixtures fixed. 9/9
    mutants killed. The matrix is running.

## 2026-10-13T11:46:42Z — SA-5 installed (COORDINATOR 6d70070d); P3-r2 low side only; 01 fetch #1

- `git archive 72cc3dfb` of qualify4.py (dc7baf60…) was installed into base, rt-R3a and rt-R3a-rep: PASS ×3, from
  05cc98fd… to dc7baf60….
- RUNTIME-INVENTORY re-sealed. r2 (027e468a…) is kept as receipts/RUNTIME-INVENTORY.r2.json. The new file is
  77582290433fc9d8137b91a19d3697914e53d39373867b4d06df732a3d575fe6, with only the qualify4 entry changed; all 12
  entries match. Staging transcript be918eaf….
- `watchdog.py resume`: the P3 STOP period (11:20:15Z onward) is closed. Status ok.
- P3-r2 (`--final`): receipts/parity-collection-r2.json
  2ec15eb49c2897f3efe0a39132c39270dd91a1914a754b76d464ae6d31161150.
  - passed=false, final=true, final_mode=true, out_of_band ['S-200']; no pause, halt or error.
  - The inventory aadafb16… is the same as r1's.
  - guard-p3-parity-r2.json e566964eac2a839e80978aa8bc8e6d2e9781ac848ee530ff2df348eac679de07: passed=true, rc 0.
  - Values as in r1: K4S-120 in band; S-200 cutoff 63.32 vs 75.3 is the only metric out of band, on the low side.
- 01 fetch #1 (approved; fetch only): refs/remotes/origin/main went from 2df9501b… (11:46:38Z) to
  6d70070dffeb603b757381bf0bf7e84963902575 (11:46:42Z). HEAD db1d17a0 unchanged.
  - A further fetch after the coordinator's exception commit has been requested, because check_parity needs that
    commit on 01's origin/main.

## 2026-10-13T11:52:21Z — PE-4 (COORDINATOR 9ecc275a) exception written; 01 fetch #2; P4 PASS; P5 label O launched

- J/data/PARITY-EXCEPTION.json was written O_EXCL, 0444: `{"parity_receipt_sha256": "2ec15eb4…", "decision":
  "disclose", "coordinator_commit": "9ecc275ac9862fc5e8531fd6705e2af77d7c9884"}`, SHA-256
  8a3317d5cd91450b15833087603a236b8616b636f0a6294167f44b7ac487d7d7.
- 01 fetch #2 (approved; fetch only): refs/remotes/origin/main went from 6d70070d… to
  9ecc275ac9862fc5e8531fd6705e2af77d7c9884. The exception commit is on origin/main; HEAD db1d17a0 is unchanged.
- P4: `$GRD --name p4-label-plan --output data/label-plan.json -- … label.py plan --phases collect/K4S-120/a1
  collect/K4S-120/a2 collect/S-200/a1 --parity receipts/parity-collection-r2.json`. Guard passed, rc 0, 4 m 19 s.
  - label-plan.json 2cc0f62597c2c171015226f4bb2512aa723891de15f3d240dd140093f7e5d2b5; guard 539809439e8f….
  - parity_exception = PE-4 (verified through the git walker).
  - O: 3,500 games, 339,846 captured and kept (K4S-120 173,469; S-200 166,377); 0 dropped, 0 duplicates, 0 over cap.
  - Holdout: 500 games, 49,183 kept (K4S-120 21,652; S-200 27,531).
- P5 O: `$DET … $GRD --name p5-label-O --add 50 --new-files $J/data/label-receipt-O- -- … label.py run --set O
  --workers 48`, launched at 11:52:21Z.
- To disclose in RESULTS (PE-4): S-200 O-states come from 10-lane collection (SA-3), which had fewer cutoffs than
  X4S-3's 50-lane reference (63.32 % vs 75.3 %).

## 2026-10-13T11:57:58Z — **HALT**: the watchdog's du measurement failed during P5 labelling. X4S-4 is ended under this T

- J/HALT.json (0444) 67e792c0371d4f624188fac9b1c4c7a867129aca5dd98893d4b6b0657035bd98:
  `measurement failed: CalledProcessError(1, ['/usr/bin/du', '-sb', '--', '/mpac/sdicks02/jobs/clasher/x4s4-onpolicy'])`,
  readings {}.
- The watchdog stopped all 51 study processes one at a time by verified (pid, starttime) at 11:57:58–59Z: the P5
  guard runner 517537, label.py and 48 workers. STOP → HALT.json. The study tree is now empty; only the watchdog
  (pid 3283869) remains, halted.
- guard-p5-label-O.json (6a7375a7…): passed=false, breach runner_SIGTERM, rc −15. data/raw-O/K4S-120 holds 523
  sealed games completed before the HALT, with no label receipt; nothing after the HALT counts (H-1).
- watchdog.log 528ed6b9…; stop-periods.jsonl 690c8afb….
- Probable cause (my design defect, not a host breach):
  - label.py seals each game into `<raw>/game-NNNN.tmp` and renames it to `game-NNNN`, with 48 workers doing so
    concurrently.
  - GNU `du` exits 1 when an entry vanishes between readdir and stat (a rename or removal during the walk).
  - The watchdog treats any failed reading as a HALT (R9-F4), so the measurement raced the labeller.
  - The offline matrix never ran du against a tree with concurrent renames. Collection only adds files, and the Q6
    smoke-pack ran single-threaded.
- Per the GO, a HALT ends X4S-4: nothing is restarted under T = 2026-10-13T04:55:07Z. HALT evidence is in
  receipts/halt/. Reported to the coordinator.

## 2026-10-13 — HR-1 (COORDINATOR 77a01d88): watchdog disk-walk fix prepared; reuse proposal sent

- Commit af123084: `studytree.tree_bytes` replaces du in the watchdog and in `studytree.disk_bytes`. It is an own
  bounded scandir/lstat walk: vanishing entries are skipped and counted; every other error raises.
  - watchdog.py b1a964f5…; studytree.py dacd6d7f….
  - test_hr1: 6 cases, including the real-watchdog regression under rename and process churn. The r9/r10 watchdog
    cases now run on the real walk.
  - 11/11 mutants killed; matrix 6/6 at 145 cases.
- Read-only facts about J:
  - 7 entries are timed at or after the HALT (HALT.json, STOP, watchdog/, watchdog.log, receipts/, the p5 log, the
    failed guard-p5 receipt).
  - The HALT window has no STOP-period record.
  - data/raw-O holds 523 seals (206 MB) that never count.
- Proposed (a): continue in J under T2, using HR-1 and reviewed tools only.
  1. Archive HALT.json.
  2. Run `watchdog.py resume` on the dangling STOP, which records the HALT window as a STOP period.
  3. Set raw-O aside.
  4. Write a new HARD-STOP and T2.
  5. W0, then a P3-r3 check that reproduces inventory aadafb16.
  6. P5-r2 onward.
  Alternative (b): a clean restart in J2 with a runbook r2 (about 19 h). Awaiting the coordinator's choice.

## 2026-10-13T12:38Z — GO 9a1613fc (HR-1 path a): J continues under T2; W0 PASS; P3-r3 reproduces P3-r2

- Step 1, HR-1 install: `git archive af123084` into J/staging/hr1, then base, rt-R3a and rt-R3a-rep: PASS ×6.
  - watchdog.py aad317db… → **dacd6d7f47442775c3dda8ad1e2ac4efdc28a0d0d56110a9b7d7495bbe0ad25e**.
  - studytree.py 39b0c151… → **b1a964f5c4d7dc74ee320edc55f07ae57c5baffa7a17921062bb4aff15b4f05f**.
  - The first attempt stopped at the staged-SHA check, because I had swapped the two expected SHAs (also swapped in my
    HR-1 message to the coordinator). Nothing was installed by it.
  - RUNTIME-INVENTORY re-sealed: r3 (77582290…) kept; new
    8389b158b8cb0c8240d9dd9fef0c87e74bd2b5d2f91dc447b60708db24415c5e; all 12 entries match. Staging transcript 502cdecf….
- Before-inventory of J, taken after step 1 (62,661 entries; path/type/size/mtime/mode/link, SHA-256 for regular
  files ≤ 64 MiB): x4s4-inv-before.jsonl 9ec05706…, gz 110a2802…. Script x4s4-inv.py f03124c1….
- Step 2: watchdog pid 3283869, starttime 165713612, verified against watchdog/pid.json and its cmdline. SIGTERM at
  12:36:55Z; it exited.
- Step 3: HALT.json moved to receipts/halt-r1/HALT.json, unchanged (67e792c0…). The dangling STOP link was kept
  (mtime 1791892678.184).
- Step 4: `watchdog.py resume` recorded the HALT window as the STOP period [1791892678.184 (11:57:58.184Z),
  1791895022.219 (12:37:02Z)]. STOP was removed.
- Step 5: grep found no consumer listing data/ except for label-receipt-* names. data/raw-O (523 game dirs, 38,704
  entries) was moved to data/halted-r1/raw-O.
- Step 6: HARD-STOP-UTC.txt (bf6804f0…) went to receipts/halt-r1/HARD-STOP-UTC.r1.txt, and receipts/T.json (002f86db…)
  to receipts/halt-r1/T.r1.json.
  - **T2 = 2026-10-13T12:37:13Z.** HARD-STOP-UTC.txt = 2026-10-14T12:37:13Z (0444, 7165844f…).
  - receipts/T2.json (0444) 04c2447d776a4cd16d900ecf6d14fbe5ce8a79bf160e5350c6baa582e212d42b.
- After-inventory (62,664 entries): 6ab3a856…, gz 034afd12…. Diff:
  - all 38,704 raw-O entries are identical (type, size, SHA, mtime) under data/halted-r1/raw-O;
  - gone: HALT.json, STOP, receipts/T.json;
  - new: T2.json and receipts/halt-r1/{HALT.json, HARD-STOP-UTC.r1.txt, T.r1.json};
  - changed: only HARD-STOP-UTC.txt and watchdog/stop-periods.jsonl (two appended lines).
- Step 7, W0: the runbook command. The watchdog is pid 657762 (own session, nice 10, core 62, no X4S4_* env).
  Deadline 1791981433. Disk via the walk: 32.99 GB, 0 vanished. Status ok, rc 0.
- Step 8, P3-r3 (check only): `$GRD --name p3-parity-r3 … qualify4.py parity --phases <3 phases> --bank collection
  --min-games 100 --final`. Guard passed, rc 0 (d92541b6…). parity-collection-r3.json d12bd561….
  - **inventory_sha256 aadafb16…, the same as r2**; the inventory list, phase evidence and arms are identical.
  - Readings: K4S-120 62.46 / 21.53 / 0.15; S-200 63.32 / 0.00 / 0.06.
  - So the carried-over evidence holds under the T2 H-1 history.
- Next, step 9: P5 with new guard names (p5-label-O-r2, then holdout).

## 2026-10-13T13:31:46Z — P5, P6 and P7 PASS (under T2); P9 and P10 launched

- P5 O, `p5-label-O-r2` (12:39:29Z–13:18:35Z): guard passed (5b6aeb28…).
  - label-receipt-O-1791897512.json ead48010…: sealed 3,500/3,500; 339,846 rows; 0 drops; passed.
  - Through the walk, the watchdog stayed ok, with disk_vanished 0 at every sampled heartbeat.
- P5 holdout, `p5-label-holdout` (13:19:54Z–13:26:43Z): guard passed (605ed4f5…).
  - label-receipt-holdout-1791897994.json 9fa781b9…: sealed 500/500; 49,183 rows; 0 drops.
- P6, packw: O batch-0000 manifest 7d01f55f… (guard bfc1d3ca…, 84 s, 521 MB); holdout batch-0000 14cb7013… (guard
  50720fc4…, 25 s, 76 MB).
- P7:
  - O-VERIFIED.json e6d19a81…: 339,846 rows = roots, within the 0.30–0.45 M band; single-candidate share 0; plan
    2cc0f625 and parity 2ec15eb4 bound. Guard 10690fe2….
  - HOLDOUT-VERIFIED.json eb969538…: 49,183 rows. Guard 81e1ea1b….
- P9 `p9-collect-w` (--count 6000 --workers 48), launched 13:31:26Z. P10 driver launched 13:31:46Z (cores 56–61): R5
  and R5-rep after the O gate, R5W after the O_W gate.

## 2026-10-13T14:32:50Z — second HALT (under T2): "measurement overdue (> 8 s)"; HR-2 prepared (two measurement lanes)

- HALT.json: 2026-10-13T14:32:50Z, "measurement overdue (> 8 s)", readings {}.
  - The last heartbeat reading (14:32:42.87Z) was healthy: 58 processes, MemAvailable 95 GiB, PSI 2.94, PSS 35 GB,
    disk 38 GB, GPU 2.6 GB.
  - 111 signals were sent by verified PID: P9 collect-w (runner and 48 workers), the driver, and the R5 trainer and
    its loaders.
  - The thread was down from 14:32Z (API rate limit). The coordinator resumed it at about 22:00Z; 01 had been idle
    about 7.5 h. Watchdog pid 657762 is still alive, halted and in kill mode. It is left alone until the GO.
- Read-only diagnosis (the watchdog had no per-phase timings):
  - **There was no host-wide stall:** O_W games completed up to 0.8 s before the HALT.
  - The R5 fit had one 7.3 s step ending at 14:32:45.7Z (normally 2.0 s).
  - **J has grown to 564,490 entries:** the HR-1 walk takes 2.45 s on the now-idle host (0.24 s at 62k entries).
  - smaps_rollup can't explain it alone: offline on 05, an 8 GB-mapped process under fault and mmap churn read in
    35 ms median, 67 ms max; environ is instant.
  - meminfo, PSI, nvidia-smi and the /proc scan take ≤ 0.03 s idle.
  - **Best-supported cause:** the single 8 s budget held a 4 s-bounded walk, a 2 s-bounded nvidia-smi, and the
    unbounded scan and PSS sum. Each part stayed inside its own bound while the sum crossed 8 s, so the reason was
    "overdue" rather than "failed". This is the measurement-path robustness class, not a resource breach.
- HR-2 (watchdog.py only) splits the readings into two lanes:
  - **fast lane:** scan, STOP, deadline, MemAvailable, PSI, count, GPU, still 8 s;
  - **slow lane:** member PSS and the walk. It starts a pass every 30 s, each pass bounded at 120 s (the walk's
    timeout, plus a main-thread HALT if a pass overruns). The last good result must be ≤ 180 s old, and none within
    180 s of start also HALTs. Breaches and failed readings still HALT.
  - Per-phase timings for both lanes go into the heartbeat.
  - Tests: test_hr2, 4 cases over 7 scenarios. 8/8 mutants killed, including "walk back in the fast lane", which
    reproduces the incident. Full suite 149/149. The matrix is running.
- Resume facts (read-only):
  - **P9** left 2,741 sealed raw-OW games, no partial directory, and no selection receipt (guard-p9-collect-w
    failed: runner_SIGTERM). By R9-F7, games without the guarded selection never count, and collect_w would set each
    aside and replay it. So P9 restarts: set data/raw-OW aside and run P9 again as p9-collect-w-r2.
  - **R5** wrote complete.json (step 1590, stopped) but no segment.json "returned": its DataLoader workers were TERMed
    by the HALT teardown and the trainer raised RuntimeError. step-00001590.pt (14:32:51.26) is after the HALT and is
    H-1-excluded; step-00001500.pt (14:29:34) is admissible.
  - Without a "returned" segment, fit_state is 'failed', which can't be resumed through the reviewed driver path. So
    R5 restarts from step 0: set fits/R5 and receipts/fit-R5-launch.json aside, and resolve ANOMALY-fit-R5 by its ACK.
