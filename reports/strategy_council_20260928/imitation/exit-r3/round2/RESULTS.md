# R3 extended results — complete

Exploration, outcome-informed extension; no multiplicity adjustment. Original R3a/b remain killed. R3a descriptive is ALWAYS NEVER-ADOPTABLE. No live replacement is authorized.

Training freeze7e939c06; r1(b) fallback evaluation freezea0beb995, prelaunch/deployment f07acdb3. [Evaluation amendment](K0-FALLBACK-ADDENDUM.md). Snapshot 2026-10-10T11:20:04Z.

| Arm | Host | Final steps | Temperature | Seed | Final EMA sealed |
|---|---|---:|---:|---:|---|
| R3c | 127x09 | 5000 | 0.003 | 2026101013 | yes |
| R3d | 127x16 | 2500 | 0.003 | 2026101014 | yes |
| R3e | 127x13 | 5000 | 0.01 | 2026101013 | yes |

[Host reallocation](STAGE2-HOST03-ADDENDUM.md):01 released to S1 at08:45:23Z after all611 R3 groups drained. Any complete Stage1 survivors require separately admitted03 cores0–55 after coordinator-arranged G stop/full drain. Regret-only03 now uses cores56–58 with manager58 sharing a worker, nice19 and the PSI guard.

No adoption: C/D/E all miss both frozen binary point gates. Doubling steps raises recall by0.465pp versus original R3a, the new-seed replicate differs by−0.036pp, and T=.01 lowers recall by1.001pp versus same-seed5000/T=.003. These outcome-informed comparisons are exploratory; intervals crossing gate values do not override the predeclared point decisions. R3a descriptive remains ineligible regardless of its paired benefit.

| Arm | Effective training rows | Rows/s, all retained fit attempts | Charged fit GPUh | Fit CPUh |
|---|---:|---:|---:|---:|
| R3c | 40,960,000 | 4670.65 | 2.436018 | 6.484337 |
| R3d | 20,480,000 | 4561.50 | 1.247154 | 3.445003 |
| R3e | 40,960,000 | 4072.78 | 2.793615 | 8.441899 |

| Arm | Play recall %, game95CI | Binary agreement %, game95CI | Mean positive W regret, game95CI | Stage1 |
|---|---|---|---|---|
| R3c | 63.438 [60.882, 66.033] | 74.703 [73.385, 76.132] | 0.008871 [0.006671, 0.011475] | KILLED: calibrated play recall <.6375; binary play/WAIT agreement <allWAIT+.10 |
| R3d | 62.938 [60.479, 65.333] | 74.357 [72.872, 75.902] | 0.008409 [0.006580, 0.010490] | KILLED: calibrated play recall <.6375; binary play/WAIT agreement <allWAIT+.10 |
| R3e | 62.437 [59.688, 65.023] | 74.011 [72.654, 75.479] | 0.009713 [0.007466, 0.012198] | KILLED: calibrated play recall <.6375; binary play/WAIT agreement <allWAIT+.10 |

All64 common command-exact replay games /8088 unique scored roots required; point gates .6375/allWAIT+.10/.010, calibrated34.6%. Bootstrap5000/game/80991013; calibration slice reuse is exploratory.

| Arm | Gate threshold | Calibrated plays / roots | Teacher-play top8 exact action recall %, game95CI | Signed W regret, game95CI | Play-root positive W regret, game95CI |
|---|---:|---|---|---|---|
| R3c | 0.548408895731 | 2798 / 8088 | 31.701 [30.040, 33.483] | 0.005081 [0.002447, 0.007955] | 0.011867 [0.006530, 0.018509] |
| R3d | 0.499014124274 | 2798 / 8088 | 30.558 [28.867, 32.382] | 0.004842 [0.002475, 0.007329] | 0.010360 [0.006265, 0.015483] |
| R3e | 0.629314929247 | 2798 / 8088 | 31.165 [29.397, 33.073] | 0.005558 [0.002544, 0.008619] | 0.013957 [0.008045, 0.020866] |

R3c positive regret median/p90/p95/p99/max: 0.003352, 0.010336, 0.015671, 0.032708, 4.000000.

R3d positive regret median/p90/p95/p99/max: 0.003809, 0.010932, 0.016481, 0.034714, 4.000000.

R3e positive regret median/p90/p95/p99/max: 0.004042, 0.011416, 0.017140, 0.035076, 4.000000.

R3a descriptive — NEVER ADOPTABLE.

| Arm | Loss %, seed95CI | Student−K0 loss pp, paired95CI | Result |
|---|---|---|---|
| K0 | 52.833 [48.833, 56.833] | — | control |
| R3a | 24.167 [20.833, 27.667] | -28.667 [-33.667, -23.333] | NEVER-ADOPTABLE |

600fresh complete same-core rotated paired blocks, coarse-first deadline W at1core/200ms/8ms reserve. Student supplies calibrated cutoff fallback+top8; K0 is common init-W v1 fallback/proposer. Report deadline/fallback/fully-scored-candidate/overrun/proposer diagnostics in the sealed decision receipt. Draw loss0; paired95CI upper>=0 kills; descriptive R3a never adopts.

| Arm | Wins / draws | Deadline hits / calls | Fallback uses | Fully scored candidates | Positive wall overruns | Proposer median / p95 ms |
|---|---|---|---:|---:|---:|---|
| K0 | 283.0 / 0 | 109966 / 134238 | 73846 | 336718 | 573 | 9.454 / 10.318 |
| R3a | 455.0 / 0 | 49612 / 89094 | 13576 | 460337 | 539 | 0.084 / 0.099 |

The student proposal callback reuses ranks computed by the fallback on the same packet. Its reported latency covers cache access and proposal conversion; the model forward pass runs during the earlier timed fallback callback. The full decision timer includes both callbacks. The comparison includes the frozen policy, calibration, proposal and timing behavior.

The frozen diagnostic field `completed_roots` counts fully scored candidates, not distinct decision roots. Both arms face v1+W; the K0 control is a v1+W mirror, with a 50% reference loss. Positive wall overruns are logged but do not advance game ticks in r1(b). These opponent and lateness rules differ from the K-v2/K2 studies, so their absolute losses are not directly comparable.

[Independent descriptive audit](../AUDIT-R3A-DESCRIPTIVE-20261010.md) confirms the paired result with caveats: it combines learned policy, calibrated gate and inference caching effects; strict return timing and generalization beyond the five archetypes remain unqualified.

Round2 Stage2 survivors.
Skipped: all round2 arms binary-killed; zero qualification/control/reporting games.

Known round2/descriptive metered costs: **57.978570 CPUh**, **6.490708 GPU reservation-wallh**. Complete process meters collected.

[Once-only cost ledger](receipts/cost-summary.json) deduplicates exact original meter SHAs across histories and03→01 copies. Whole fit/pool trees include failed/void/replayed work; nested game/case/block/segment diagnostics are never added again. Original R3a/b10.735822CPUh/2.968378GPUh remain separately identifiable in the combined audit.

Initial synthetic test, small command-center/admission metadata and remote read-only copy sender CPU; failed bare-Python3.8 AST verifier and scanner/report overhead. No scientific replay omitted. Failed proposal staging attempt1 preflight stopped before its meter; its CPU cannot be recovered and is disclosed as small unmetered failed-preflight overhead (no fabricated zero). Two predeployment Python3.8 AST comparisons had only a Constant kind=None representation mismatch; unsuccessful small metadata/test CPU unmetered, original failed candidate retained. Guard draft corrected by inspection before any deployment. Metadata snapshot deployment attempt1 failed at read-only path preflight before any mutation; its small preflight CPU is unmetered, with original code/stdout/stderr retained.

Full source/input/native/checkpoint/seed SHA bindings: training and evaluation freezes, retained exact JSON process snapshots, final decisions and command/game/block proofs. Final experiment completion additionally requires independent all-owned-PGID absence, CPU/GPU vacancy, coordinator notification and continuation deletion.

| Provenance | SHA256 |
|---|---|
| Training freeze | 7c91632956601f3ff623d2a7c2baed8bcaadea51f8bc3cd389eaf36ae7b4ef54 |
| Evaluation freeze | f7e1439c5e81f648e005a66bf5f27cbe2de3e537a7f86940b0eaf2ee71126409 |
| R1 corpus manifest | 1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b |
| Heldout manifest | 0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f |
| Shared03 admission-repair freeze | 4fbbe3d5f46a7db78ddedd7bd2d67e5e5116c4e1480117bca3a7b84d635dd0f7 |
| Shared03 regret-only operational freeze | b6acb31432eeea1f5a410bb63e5c7dbafd2ec9d445ce296b512395d9cb0f597b |
| inputs/main02.pt | d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed |
| inputs/assets.npz | 3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737 |
| eval-source/imitation/exit_r1/screen.py | 17d1b4086585840f5073285c9345355b4187c8342963963360213c3a9cff176e |
| reporting-native/clasher_core.abi3.so | f387b2d288ed280de9eeae3164d38f465045685ee53819e279930c2ee10699a8 |
| scorer-native/clasher_core.abi3.so | 06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10 |
| R3c final EMA | 9d21e505e247889d1f337d00bb2d8840d2377a0db11fc691f9ebd5675cd0deb7 |
| R3d final EMA | 23becbd8aa09885514e2504d003822fdb107439ff308e9303c5812064fbf0b58 |
| R3e final EMA | 61081f122c47a5db2f43ad2f4f66d638e50bf1004c5cea5429357ecb6bcfbdfa |

[Priority and PSI amendment](shared03/nice19/ADDENDUM.md): nice19/SCHED_OTHER and full memory PSI avg10 >10% stop. The first replay pool was drained after the explicit coordinator priority instruction arrived; eight complete seals and their streams are SHA-pinned for reuse, unsealed games replay fully, and every attempt whole-tree meter is charged. Score arithmetic/seeds/gates stay unchanged.

Historical nice19 amendment freeze SHA: 86ed5d060591556469b2bfe29aee046dc48ccacb729b96e675bf5abf75b93b5d.

[Admission receipt repair](shared03/repair/ADDENDUM.md) was pushed before the first round2 regret replay: the dynamic admission binds the current freeze/grant/evidence and exact lane. Proposal staging attempt1 failed on a stale static receipt pin before copying/scoring; its preflight CPU was not metered and is disclosed as small unrecoverable overhead. The failed log, original receipt and reviewed version2 retry are retained.

[Historical shared03 operational amendment](shared03/PLAN.md): the prior manager59 allocation was superseded by the core58 correction below; authenticated G remains untouched. Regret seals bind the03-only amended evaluation SHA; all GPU offline and paired01 game seals retain the original a0beb995 SHA. The byte-unchanged Stage1 reducer runs in the replay manager after all64 children finish; its CPU is included in the whole replay pool once.

[Manager core58 correction](shared03/core58/ADDENDUM.md): all four replay processes are confined to physical56–58; manager58 shares a scoring worker core, nice19/Other and PSI terms unchanged. Thirteen complete pre-stop seals/streams are SHA-pinned, unsealed games replay fully, both interrupted pool trees are charged once. No score arithmetic, gate or seed changes.

Historical core58 regret freeze SHA: 3b945bd6a6a7e8c9b6fde8b628c308c97e68ecc75260ae7a0a02bf43023f0207.

[Fail-closed guard diagnostics](shared03/diagnostics/ADDENDUM.md): pool3204444 stopped after41 complete games when game42 failed its admission check. The original failed census was not recorded; the cause remains unclassified. All old groups drained and a fresh unchanged guard passed. Added predicate-equivalent denial receipts preserve the same safety conditions; all41 exact complete seals/streams are retained. Failed/unsealed work is charged once and replayed fully.

Guard-diagnostics operational freeze SHA: 2f69ea84029c6704bc3608cb27ac433317f421c09d208ca774f77e1b1b29dcd3.

[Verified producer snapshot exception](shared03/metadata-helper/ADDENDUM.md): pool3337091 stopped after46 sealed games when a read-only G snapshot had a separate process group. It stayed oncore54/Idle19 with PSI0. The exact source and snapshot command hashes are now pinned; the target mode, unknown commands, altered source and bad thread/core/priority are denied. Scientific G group rules and all R3 limits/scoring/gates/seeds stay unchanged. All46 exact complete seals are retained; failed/unsealed work is charged and replayed fully.

Final regret-only operational freeze SHA: 993dfb1133346e1bcb8ba14edb5f3c00e5d514601cdca1e2db89b9fb18a48809.

Shared-host incident: R3 diagnostic qualification helper3375515 triggered G priority STOP at10:52:33Z. G drained all54 workers and packer by10:53:58Z; its177,196 pending raw roots were preserved. Coordinator serialized the final R3 replay and G return, and forbade further03 helper tests. Final attempt5 therefore starts after full G vacancy. G work is a separate experiment and is not added to R3 whole-tree meters. If attempt5 stops for any reason, the authorized closeout is partial with no further retry.

Combined original + extension known costs: **68.714392 CPUh / 9.459087 GPU reservation-wallh**. Final whole-tree costs.

[Combined globally deduplicated ledger](receipts/combined-cost-summary.json).

Returned-GPU vacancy evidence uses the completed independent all-group audits and later empty owned-runtime censuses. Their SSH observers returned, but no new observer-specific /proc check was made after leases ended; no new leased-host access. Final03 observer absence is independently rechecked.
