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
