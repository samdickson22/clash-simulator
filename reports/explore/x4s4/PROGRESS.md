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
