# Null’s full-frame block, 2026-10-16

Capture ended early and the block was released at 23:17Z. All owned Mac producer, watchdog and reference-emulator processes exited; both 05 importers are stopped. The live ladder can resume under its babysitter.

Captured and shipped 171 native full frames: 81 from each of two completed pilot runs and 9 from one partial priority run. The fresh diagnostic attempt captured none. The healthy pilot averaged 1,038 raw frames/hour including scene setup. All 171 retained source records pass image/observation hashes, full native schema and paired synchronization checks.

05 holds 173 checksum-verified chunks (120,937,518 bytes, about 115.3 MiB) at `/mpac/sdicks02/scratch/nulls/full-v7/`, including images, paired observations, action logs and manifests. Mac source chunks were pruned only after checksum acknowledgement. Pilot acknowledgement latency was median 2.19 seconds, p95 3.33 seconds and maximum 3.73 seconds. Old, invalid and partial artifacts remain preserved.

Three fresh v3 complete records contain eight corrected troop labels at `/mpac/sdicks02/scratch/nulls/admitted-full-v7-v3/`. Independent Sol visual review confirmed their body identities and owners, accepted walking/flying/idle extents, and supplied the three attacking-weapon corrections now applied. Camera checks passed; r3 applies its independently measured crop offset. R3 confirmed admission of all three frames and eight troop labels to the live V13a/b/c training lists on 01, 04 and 08; it also added eighteen tower boxes, for twenty-six training label lines. The source images were never altered. The other 168 captured frames remain held.

| Card | Raw ours | Raw opponent | Corrected QA labels ours | Corrected QA labels opponent |
|---|---:|---:|---:|---:|
| Giant | 80 | 0 | 2 | 0 |
| Musketeer | 71 | 13 | 2 | 1 |
| Knight | 0 | 30 | 0 | 1 |
| MegaMinion | 30 | 79 | 0 | 1 |
| Cannon | 13 | 63 | 0 | 1 |
| MiniPekka | 0 | 8 | 0 | 0 |

Raw counts mean frames containing a native card instance, including possible deployment phases; they are not admitted labels and can overlap within a frame. All other requested cards have zero capture coverage in this block. QA counts are troop instances in the three audited frames, not eight distinct frames. The five-run and 1,000-labelled-frame milestones were not reached.

The priority run stopped when full native object data differed across a screenshot even though tick, epoch and count remained stable. The original rejected pair was not retained, so the sync root cause is unproven. A fresh diagnostic build retained the same strict rejection and added failure-pair/JPEG preservation, but then stopped before configuration on transient null focus after startup system dialogs. No sync comparison, watchdog threshold or admission rule was relaxed.

Offline changes now have fresh Sol code GO: explicit native tower ownership plus separate detector belong, `towers_boxed:false`, bounded initial null-focus waiting, and rejected-pair preservation. The latter startup change is not deployed or host-tested. All attacking extents require per-frame rendered-weapon/body audit; static anchor extents cannot qualify those poses.

The working emulator used 1,536 MiB guest RAM and two cores with background scheduling; the smaller profile produced startup ANRs. The working full-v7 capture stayed around 10.7 GiB free disk with 896 MiB free swap. Start and runtime gates remain unchanged.

Before the next production block, reproduce and explain the sync mismatch from an actually retained rejected pair, then review any required correction. Use a short separately reserved diagnostic pilot with the approved startup handling, a fresh immutable namespace, the same resource guards and immediate checksum shipping. Resume broad opponent-frequency capture only after that proof; continue to hold every source until per-body box/team/pose QA. No timer or automatic launch is scheduled.

Receipts: `FULL-BLOCK-RELEASE-2317.json`, `FULL-BLOCK-RAW-COVERAGE-2319.json`, `FULL-V7-V3-HANDOFF-2322.json`, `label-contract-review14.md`, and `startup-null-review15.md`, `FULL-V7-CONSUMER-ADMITTED-2324.json`, and `FULL-BLOCK-FINAL-2324.json` under `/mpac/sdicks02/scratch/nulls/qa/`.
