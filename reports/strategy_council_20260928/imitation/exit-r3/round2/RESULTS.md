# R3 extended results — pending

Exploration, outcome-informed extension; no multiplicity adjustment. Original R3a/b remain killed. R3a descriptive is ALWAYS NEVER-ADOPTABLE. No live replacement is authorized.

Training freeze7e939c06; r1(b) fallback evaluation freezea0beb995, prelaunch/deployment f07acdb3. [Evaluation amendment](K0-FALLBACK-ADDENDUM.md). Snapshot 2026-10-10T08:28:44Z.

| Arm | Host | Final steps | Temperature | Seed | Final EMA sealed |
|---|---|---:|---:|---:|---|
| R3c | 127x09 | 5000 | 0.003 | 2026101013 | pending |
| R3d | 127x16 | 2500 | 0.003 | 2026101014 | yes |
| R3e | 127x13 | 5000 | 0.01 | 2026101013 | pending |

Stage1 final-EMA calibration and64 common frozen-W replay gates pending. No intermediate checkpoint selection.

R3a descriptive — NEVER ADOPTABLE.

| Arm | Loss %, seed95CI | Student−K0 loss pp, paired95CI | Result |
|---|---|---|---|
| K0 | 52.833 [48.833, 56.833] | — | control |
| R3a | 24.167 [20.833, 27.667] | -28.667 [-33.667, -23.333] | NEVER-ADOPTABLE |

600fresh complete same-core rotated paired blocks, coarse-first deadline W at1core/200ms/8ms reserve. Student supplies calibrated cutoff fallback+top8; K0 is common init-W v1 fallback/proposer. Report deadline/fallback/completed-root/overrun/proposer diagnostics in the sealed decision receipt. Draw loss0; paired95CI upper>=0 kills; descriptive R3a never adopts.

| Arm | Wins / draws | Deadline hits / calls | Fallback uses | Completed roots | Positive wall overruns | Proposer median / p95 ms |
|---|---|---|---:|---:|---:|---|
| K0 | 283.0 / 0 | 109966 / 134238 | 73846 | 336718 | 573 | 9.454 / 10.318 |
| R3a | 455.0 / 0 | 49612 / 89094 | 13576 | 460337 | 539 | 0.084 / 0.099 |

The student proposal callback reuses ranks computed by the fallback on the same packet. Its reported latency covers cache access and proposal conversion; the model forward pass runs during the earlier timed fallback callback. The full decision timer includes both callbacks. The comparison includes the frozen policy, calibration, proposal and timing behavior.

Round2 Stage2 survivors.
Pending complete600 paired terminal blocks; no partial reporting reduction.

Known round2/descriptive metered costs: **40.543134 CPUh**, **1.273993 GPU reservation-wallh**. Open process costs pending; these are lower bounds.

[Once-only cost ledger](receipts/cost-summary.json) deduplicates exact original meter SHAs across histories and03→01 copies. Whole fit/pool trees include failed/void/replayed work; nested game/case/block/segment diagnostics are never added again. Original R3a/b10.735822CPUh/2.968378GPUh are reported separately until the final combined audit.

Initial synthetic test, small command-center/admission metadata and remote read-only copy sender CPU; failed bare-Python3.8 AST verifier and scanner/report overhead. No scientific replay omitted.

Full source/input/native/checkpoint/seed SHA bindings: training and evaluation freezes, retained exact JSON process snapshots, final decisions and command/game/block proofs. Final experiment completion additionally requires independent all-owned-PGID absence, CPU/GPU vacancy, coordinator notification and continuation deletion.

| Provenance | SHA256 |
|---|---|
| Training freeze | 7c91632956601f3ff623d2a7c2baed8bcaadea51f8bc3cd389eaf36ae7b4ef54 |
| Evaluation freeze | f7e1439c5e81f648e005a66bf5f27cbe2de3e537a7f86940b0eaf2ee71126409 |
| R1 corpus manifest | 1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b |
| Heldout manifest | 0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f |
| Shared03 regret-only operational freeze | b6acb31432eeea1f5a410bb63e5c7dbafd2ec9d445ce296b512395d9cb0f597b |
| inputs/main02.pt | d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed |
| inputs/assets.npz | 3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737 |
| eval-source/imitation/exit_r1/screen.py | 17d1b4086585840f5073285c9345355b4187c8342963963360213c3a9cff176e |
| reporting-native/clasher_core.abi3.so | f387b2d288ed280de9eeae3164d38f465045685ee53819e279930c2ee10699a8 |
| scorer-native/clasher_core.abi3.so | 06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10 |

[Shared03 operational amendment](shared03/PLAN.md): manager59 and three workers56–58 coexist with authenticated G on0–55. Regret seals bind the03-only amended evaluation SHA; all GPU offline and paired01 game seals retain the original a0beb995 SHA. The byte-unchanged Stage1 reducer runs in the replay manager after all64 children finish; its CPU is included in the whole replay pool once.

Combined original + extension known costs: **51.278955 CPUh / 4.242371 GPU reservation-wallh**. Lower bounds while fits/pools or audits remain pending.

[Combined globally deduplicated ledger](receipts/combined-cost-summary.json).
