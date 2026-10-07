# Linux fleet parity, 2026-10-07

**Overall: blocked.** The hub build, all four Python identity modes, fast unit tests, and Stage 2/4/5/6 regression suites pass. The stronger Stage 5 replay against 200 recorded Mac Python traces fails at root 4. That failure also reproduces on frozen Mac native build 42. It is a pre-existing native chain-targeting bug, not Linux drift. No peer replication or peer smoke test was started.

Clasher compute hosts are **127x01, 02, 03, 04, 07, 08**. Per the coordinator's later instruction, **127x05 is the shared T3 command center**. This task only checked its connectivity and console users before the reservation; it copied no repo/venv there and ran no build, test, identity or heavy job there. No roader host was used.

## Build and input provenance

Hub: `127x02:/mpac/sdicks02/repos/clasher`. Logs and receipts: `/mpac/sdicks02/jobs/clasher/`. Small evidence copies are in this folder's `evidence/` directory.

- Python **3.12.13**, Rust **1.97.1**, NumPy **2.3.5**, Torch **2.10.0**, Pydantic **2.13.4**, msgspec **0.20.0**, cloudpickle **3.1.2**, pytest **9.0.2** match the Mac. Linux is x86_64/glibc 2.31; Mac is Apple M4 Pro/arm64. Environment receipts are `environment-mac.json` and `evidence/environment-linux.json`.
- `uv sync --frozen --python 3.12.13`, then the existing `bash engine-rs/build.sh`, produces an importable PyO3 extension. A venv `.pth` points to `engine-rs`, matching the source-tree import layout. No maturin-specific build was needed: the Mac's authoritative build script uses Cargo and copies its release library.
- `PYO3_PYTHON=$PWD/.venv/bin/python cargo test --manifest-path engine-rs/Cargo.toml -j 2` exits **0**, but discovers **zero Rust tests**. This does not replace the differential tests below.
- Initial release compilation took **51.45 s**. The final bootstrap retry took **19.33 s**, reusing that ABI3 release build and compiling the Cargo test target. The first environment selection downloaded Python 3.12.15; it was corrected to the Mac's 3.12.13 before any parity run. The first Cargo test attempt selected system Python 3.8 and failed the ABI3 minimum; explicitly exporting `PYO3_PYTHON` resolved it. Failed attempt logs are retained.
- Linux extension SHA256: `830fcc54cee623da0e9db021d943a7043474f08faa8e677e21d360c266b962fd`.
- Canonical gamedata SHA256: `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65`, the admitted Ice Spirit 84 HP / Goblin_Stab 49 data.
- The original transfer was neither restarted nor killed. It ended **21:54:31 UTC**; parallel copy, local-data copy and final sweep all exited **0**. Its dry-run reported **200 differing entries**, not zero: concurrent Git metadata, the Mac Stage 6 control log, and transfer log/verify files. The complete listing is retained.
- A concurrent Mac worker began the Fisherman repair during transfer. This run freezes the earlier **1,150-file** source snapshot in `source-mac.json`. After the final sweep, 13 changed incoming files were preserved under `/mpac/sdicks02/snapshots/clasher-post-sweep-20261007`, then restored from `/mpac/sdicks02/snapshots/clasher-fleet-20261007`. `evidence/snapshot-restoration.json` lists every hash pair. Later Fisherman/Mirror fixes are outside this qualification.
- Before and after testing, all **1,150 source files**, **34 replay inputs**, the Linux extension, and **179 historical receipt hashes across 17 incremental certificates covering 66 cards** verified exactly. See `evidence/verify-inputs-final.json`. Historical certificate integrity is distinct from fresh Linux execution and does not grant final S122 admission.

## Four-mode identity

`identity.sh` calls the same unchanged Python harnesses and baseline paths as `engine-speed/check_identity.sh`. `fleet_run.sh` supplies GNU `/usr/bin/time -v`; the Mac's `/usr/bin/time -l` script and admitted baselines are unchanged.

| Mode | Exact coverage and result | Linux wall | Linux CPU | Historical M4 Pro wall | M4 Pro CPU |
|---|---|---:|---:|---:|---:|
| P16 | 12 episodes, 15,949 digest boundaries, zero mismatches | 246.91 s | 246.76 s | 111.30 s | 110.99 s |
| C56 | 7 episodes, 2,900 digest boundaries, zero mismatches | 45.59 s | 45.54 s | 20.08 s | 20.02 s |
| Random | 24 episodes, 7,198 boundaries, zero mismatches | 102.81 s | 102.73 s | 46.63 s | 46.28 s |
| Recorded SRP | All 8 exact admitted rows, zero mismatches | 1,416.48 s | 4,435.10 s | 2,285.98 s | 2,053.18 s |

CPU is user + system time. Recorded replay used **four workers**, so its wall time is not a single-core comparison. Each worker executed the unchanged `oq_lib.play_game`; each completed game has an independent receipt. The original `broad_identity.py recorded check` then verified the merged eight actual replay rows. No synthetic rows were inserted. Recorded identity checks outcome, crowns, ticks and planner-call count, not every tick's state digest.

The historical Mac measurements come from `engine-speed/logs/*_stage6-entry.log`, copied into `evidence/mac-*.log`. These are not simultaneous controlled benchmarks. The four CPU-time comparisons put Linux at roughly **2.16–2.27 times the Mac's per-core time** for these workloads.

Key output:

```text
{"checked_episodes": 12, "digest_boundaries": 15949, "mismatches": []}
C56: episodes=7, digest_boundaries=2900, mismatches=[]
{"suite": "random", "checked": 24, "mismatches": []}
{"suite": "recorded", "checked": 8, "mismatches": []}
```

Commands used, from the hub repo:

```sh
fleet=reports/strategy_council_20260928/fleet
bash "$fleet/fleet_run.sh" gate-sequence-linux-20261007 bash "$fleet/gate_sequence.sh"
bash "$fleet/fleet_run.sh" recorded-linux-20261007 bash "$fleet/recorded.sh"
bash "$fleet/fleet_run.sh" stage6-linux-20261007 bash "$fleet/regressions.sh" stage6
```

The sequence ran `identity.sh p16|c56|random linux-20261007`, then `regressions.sh fast|stage2|stage4|stage5|stage5-replay|speed`. Individual commands, timestamps, exit codes and resource timings are in each named `.log`/`.exit` pair. `HUB-RESULTS.json` collects the numbers.

## Native regression and speed gates

| Gate | Result | Linux process wall |
|---|---|---:|
| Fast pytest selection | 47 passed | 6.56 s |
| Stage 2 plus canonical-data regression | 38 passed | 154.21 s |
| Stage 4 C56 differential suite | 88 passed | 301.32 s |
| Stage 3/5/5b search/deadline regressions | 10 passed | 35.30 s |
| Stage 6 cumulative regressions | 60 unique methods pass after the provenance recovery below | 549.84 + 32.21 s |
| 24-scenario native differential | 42,734 ticks; zero digest/action/RNG mismatches | 88.00 s |
| Full Stage 5 recorded planner replay | **FAIL** at zero-based root 4; roots 0–3 match | 25.09 s |

The 24-scenario differential also passes **4,600 MT checks** and **2,000 A* cases**. Stepping: Python **702.44 ticks/core-second**, Rust **26,506.62 ticks/core-second**, **37.735×** speedup. Maximum sampled clone mean: **8.091 microseconds**. Its parity, >=30× speed, and <20 microsecond clone gates all pass. This is the four-card differential workload, not a new whole-S122 speed certificate.

Fast selection: `tests/test_battle_clone.py`, `test_card_mechanics.py`, `test_scope_engine_cards.py`, `test_elixir_leak_penalty.py`. Exact complete unittest lists are in `regressions.sh`.

### Saved-root provenance recovery

The first Stage 6 run reports 46 passing methods and 14 failures **before replay**, because saved roots expect source hashes predating cleanup commit `2def50e8d60acb574b571d47da4f42cfd7ce0d41`. The source change removes unused imports/bindings. Every old hash was verified against the commit's parent, every new hash against the commit, and every pinned runtime file against the new hash. The complete reviewed diff and proof are retained.

`audited_suite.py` translates only those exact expected source-hash expressions in memory. It leaves source files, fixture hashes, replay logic, digest/action/RNG checks and tolerances unchanged. Stage 4 uses the same mapping for one saved-root precheck. Stage 6 reran only the 14 blocked methods; all passed in 30.897 s of unittest time. `evidence/stage6-resolved.json` accounts for all 60 unique methods. The failed original run remains intact. The first resolver attempt also remains intact: its parser rejected an assertion with an optional message; the corrected r2 accepted that syntax and performed all 14 replays.

```sh
bash "$fleet/fleet_run.sh" stage6-resolved-linux-20261007-r2 \
  env PYTHONPATH=engine-rs:src:reports/strategy_council_20260928/engine-speed/stage6 \
  .venv/bin/python -B "$fleet/resolve_stage6.py"
```

## Blocking native regression

The stronger `stage5_replay.py` adapts the existing `stage5/replay_qualified.py` gate only to use fleet-owned output paths. It compares all native candidate/score/continuation trace hashes to `stage5/parity-r3.json`, which records Mac Python results.

At **root 4, seat 0, tick 900**, both engines choose action **120**, but the native trace differs. Linux Python independently reproduces the recorded Mac hash exactly:

```text
Mac recorded Python / Linux Python:
0323ee822a6f04af26c264314c85517ecd6108e32b025e79fb1754c73ed51114
Linux native / frozen Mac native build42:
5f6d1864ecb07f1327ce1cd0e14c2ee46ffefc4b90bb008728d246d5b4d972db
```

First public state divergence: **tick 1007**, 107 ticks into the **balanced, candidate 109** continuation. Electro Spirit creates chain entity **128**. Python chooses Bat **127**, whose remaining spawn stagger is `0.05000000000000007`; Rust excludes it and chooses Bat **124**. Both are at effectively equal distance; Python's existing tie-break selects 127.

- Python chain position: **(4.167, 17.456)**.
- Rust chain position: **(4.544, 17.833)**.
- The state digest first differs here; the full RNG digest still matches.
- Later candidate score 14 is `-0.001769718360278746` in Python versus `-0.001955628983916651` in Rust. Scores 15 and 17 also differ. Equal selected action does not pass the gate.

Cause: `engine-rs/src/c56.rs:305` excludes spawn-staggered candidates in `chain_tick`; line 361 also rejects an in-flight target while staggered. Python `src/clasher/entities.py:5921` delegates chain eligibility to `is_secondary_effect_targetable_by` at line 730, which has no spawn-stagger exclusion. Effect receipt/damage gating is separate. This is a native target-eligibility mismatch, not float/libm/hash/dictionary-order drift.

The same reduced root was replayed on frozen Mac build 42. Its full native planner hash, first divergent tick, targets and coordinate differences are identical to Linux. A diagnostic-only in-memory Python counterfactual that adds Rust's stagger exclusion changes the chosen target to 124 and reproduces Rust's exact first-tick digest. This counterfactual is explicitly **not accepted** and was never used in a passing gate. No oracle or native behavior was changed by this worker.

Reproduce the Linux reduction:

```sh
bash "$fleet/fleet_run.sh" reduce-root4-linux-action109-20261007 \
  .venv/bin/python -B "$fleet/reduce_root4.py" \
  --root /mpac/sdicks02/jobs/clasher/stage5-root4.pkl \
  --output /mpac/sdicks02/jobs/clasher/root4-linux-action109.json
```

Evidence: `evidence/stage5-root4-diagnosis.json`, `root4-linux-action109.json`, `root4-mac-build42-action109.json`, `root4-mac-build42-direct.log`, and `chain-stagger-counterfactual.json`. The original root and first-divergence continuation pickles remain under the hub job directory; local diagnostic copies are ignored by Git. Failed preliminary diagnostic launches are retained; the Mac proof is the completed direct run, not the empty detached attempt or the launchd attempt denied Desktop access.

## Handoff

All task-owned hub jobs have exited. The original Mac build, oracle, admitted baselines and historical results were not edited. No commits were made. No file written in this folder exceeds 5 MB; diagnostic pickles and native binaries must remain uncommitted.

The coordinator/native owner must resolve the chain eligibility mismatch and rerun the full 200-root Stage 5 replay on fresh, pinned source/binary receipts before fan-out. Coordinate that change with the separately running Fisherman/Mirror work. `fanout.sh` is prepared, excludes 127x05 and all roader hosts, and refuses to copy while the hub gate has exit 1. Consequently peer installation and P16 smoke tests are **not performed**, not passing. GPU training is outside this CPU-engine qualification.
