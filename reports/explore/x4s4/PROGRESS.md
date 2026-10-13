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
