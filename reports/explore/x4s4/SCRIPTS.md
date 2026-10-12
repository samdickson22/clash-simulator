# X4S-4 scripts for the single Sol review (exploration, NEVER ADOPTABLE)

Design is frozen at PLAN r3 87809ae0 (COORDINATOR). Nothing has been run on any host. This file lists every script and config
with its SHA-256, and records the offline synthetic test results from 127x05.

| File | Kind | SHA-256 |
|---|---|---|
| `run_collect.py` | new | `6d8239fde6a231704457edf7848a819eb337e55a80d8e3057b402a3f7a9beae2` |
| `collect.py` | new | `d5706ed98cfd806b2d14d5de069eb36a3df249aced57640413c60b79a457c599` |
| `label.py` | new | `15991804d87cdd5c3a58ba13cf4abf38945a0962da355f6640d1f2b0cfe8c3e5` |
| `collect_w.py` | new | `c0308e743cf753e00d676a18b42422903c6c699ef9165ccf37728dfbdac14c65` |
| `verify_onpolicy.py` | new | `42e9d22ec46cc1d7767257b396be87fdd4e028087c19cc2dd945f70d730d4ef7` |
| `diagnose.py` | new | `0dc9a6c7bf2d7040813f32a3b4f4e121efb141ce7d9fc053db6e59ce7d47b36f` |
| `contention.py` | new | `47f981b609f65b1857793990623dc1f6d4ac4a5870cf2bd140783716a5fd5028` |
| `qualify4.py` | new | `f57c17f5c7379a28329e2c664dcaec7904748fa07712d28c30e9ea10138d69b5` |
| `supervise.py` | modified (from x4s3) | `12564c3a8e238bb219e550b016ee25e1db2c2fc21fc4d1729f5b426864b8063f` |
| `run_fit.sh` | modified (from x4s3) | `c6cd9f0d909348ac227e96b032e1df3d3142f6869680163ab2b630ddd5364aae` |
| `driver.py` | modified (from x4s3) | `d7087213b16111fc4f2c70522214cbe30f14341e314fd5d9ad6c2e2f2b05470c` |
| `reduce.py` | modified (from x4s3) | `8ad67ba2f12a46872363c06a26cec72288dadf518d703417d573e5cab8e123a1` |
| `write_report.py` | modified (from x4s3) | `0a3a33e5e8e023c79be4e4e00cf2b5f6fb4f255ffdb6b96dac1f0280f8611892` |
| `audit_seeds.py` | modified (from x4s3) | `78cb6b3a568631f8e982c27c1ffc5e540e08780da990b0c8684254858b60b8fa` |
| `plan.json` | config | `f44103b5ce76496f3237906110f1d7e5a97a43696cd69def421c16d49a2db18a` |
| `plan-collect.json` | config | `d5414cefe851e67234915396ba028a46be26cae32fc18f9f780dfe1422b75861` |
| `plan-qual-capture.json` | config | `dcaab36cd66f8e11895f3f5965cbc55f2879af4c33d9169fb2e11c030224aa8c` |
| `idx-qual.json` | config | `4587c7edd4a17da602e224777e96b98af33e570cea9fcbf3e5ed9543b82d606b` |
| `idx-smoke.json` | config | `4587c7edd4a17da602e224777e96b98af33e570cea9fcbf3e5ed9543b82d606b` |
| `test_x4s4_offline.py` | test | `08aab8d67b5524d6cd3d320fce4677388d9be25ae01afeec85ae918b69cc6453` |

## Reused byte-identical (not for review)

- `reports/explore/x4s3/run.py` (evaluation games), `runtime.sh`, `detach.sh`, `calibrate.py`;
- the X4S/S1 kernels;
- the frozen R3 trainer `exit-r3/source`, `fit_runtime.py`, `loader_prefetch.py`, `proposals.py`;
- `imitation/exit_r1/{rows,pack,emitter}.py` (emitter SHA dab61651 is asserted by `collect_w.py`).

## Points for the reviewer

**`run_collect.py`.** Byte copy of `x4s3/run.py` plus exactly two additions (six added lines): `CAPTURE = None`, and the
explicit post-`apply_lateness` hook call (C7c).

**`collect.py`** covers C7a, C8 and C9:
- **Belief (C7a):** the opponent hidden state is sampled from a deep copy of the agent's belief.
- **C8:** captures `reserved_packet`, `opponent_elixir` and `pending`. A non-empty `pending` is skipped and counted.
  The triple also gets a SHA-256 for the round-trip test.
- **C9:** a domain-separated SHA-256 RNG and a `persistent_id` guard that raises on any `BattleState`/`PlayerState`.
- **Qualification modes:** a live-belief pickle-hash check, and fair-information permutation of the opponent's
  unrevealed hand/cycle with a reseeded battle RNG; the payload must be byte-identical.

**`label.py`** builds the W teacher exactly as `x4s/qualify.py` does, with `reserve_floor=False` asserted.
- Digest mismatch: the state is dropped, and more than 0.1% fails the receipt.
- Per-arm caps, a separate O-holdout set (indices ≥ 3500), and a feature-only duplicate report by 600-tick bucket.

**`collect_w.py`** calls the **unchanged** emitter (R2-4/R2-11):
- per-game `decks()`/`index` give the X4S (own, opponent, seat) mapping;
- the realized schedule, seed, v1 opponent and checkpoint SHA d77005d5 are asserted;
- no new game is dispatched while memory PSI > 10% or MemAvailable < 24 GiB;
- the smallest root prefix is selected, and unselected games are renamed to `-unused`.

**`verify_onpolicy.py`.** Modes O, holdout and OW, built on the verify_g r3 safety primitives. They enforce:
- the C6 O gate: 0.30–0.45 M rows, per-arm caps, label receipts passed;
- the E11 O_W gate: C′ only (not C or E), roots in [|O|, |O| + last game], sources equal to the selected prefix,
  single-candidate root share reported.

**`supervise.py`** adds (R2-9, E7):
- `--script`;
- census `foreign_cores_host`: host-wide CPU of processes outside the X4S-4 tree (own and child groups, driver and fit
  groups from receipts), any core;
- `reduced_concurrency`, the yield state.

**`contention.py`** (C5, E7) reads only census timing fields, `launch.json` worker counts, game mtime and top-level
`wall_seconds`. An `object_pairs_hook` drops all other keys during parsing. The receipt is O_EXCL.

**`driver.py`** (C4, E1, E6):
- fits first; reporting only when no fit runs and all three fits are done and calibrated;
- ABBA order R3a, R5, R5-rep, R3a-rep, R5W; all games always run;
- no game outcome is read (the only `loss` read is the fit's training loss).

**`reduce.py`** (E1–E4, E8–E10):
- refuses to run before the C5 receipt exists, and needs all four primary students;
- fixed N, or `--allow-prefix` (the E8 largest seed-index prefix; R5W on its own prefix);
- primary Δ with the three-way outcome and the pooled single-fit clause;
- fit-inflated interval with σ_fit = 0.65; the harmful and attribution sub-labels; 2-df σ_fit; the contention view;
  the parity table.

**Explicit checks.** No `assert` remains in X4S-4-owned scripts, except those inherited byte-identically in
`run_collect.py`. Checks raise explicitly, so they are valid under `-O`.

## Offline test results (127x05, synthetic fixtures, no host contact)

`test_x4s4_offline.py` gave **40/40 passed under -O0, -O and -OO**. Receipts:
[receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl), `-O1`, `-O2`.

**Environment.** A Python 3.12 venv built offline from the local uv cache, with numpy 2.5.3 and no torch. The two
torch-only imports of `exit_r1.rows` are stubbed. Real `BattleState`/`PlayerState`/`DiscreteTileActionSpace`, `seal`
and `pack` are used.

**Coverage:**
- capture RNG, guard, eligibility, permutation, and the detection of hidden-hand reads and belief mutation;
- per-game capture files;
- label plan (holdout, interruption drop, dedup, caps, duplicate report);
- labeling (mismatch drop, resume), then seal → pack → verify O, with negatives for row mismatch, failed receipt,
  mismatch rate > 0.1%, below the minimum, and a symlink;
- verify OW (root rule, upper bound, bank-C seed);
- driver: no reporting during fits, ABBA, no futility;
- contention: all four flag types, only `wall_seconds` parsed, O_EXCL;
- reducer: requires the C5 receipt, fixed N, primary, sub-labels, R5W prefix, contention view, parity;
- report rendering; the `collect_w` mapping (50 cells); the supervisor census; `run_fit.sh` shard lists and gates.

**Not covered offline** (engine, W scoring and trainer; these are qualification §6 on 01 after the GO):
- real capture payloads and command-hash non-perturbation;
- labeler versus the 125 frozen references;
- digest round trip;
- the emitter acceptance replay;
- `RootTeacherStore` compatibility;
- `diagnose.py`.
