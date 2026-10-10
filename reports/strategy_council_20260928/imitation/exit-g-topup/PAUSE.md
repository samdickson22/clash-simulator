# G pause receipt

Updated 2026-10-10T02:18:23Z. All generation is paused until explicit coordinator host release. X GPU fits, stage-1/2 evaluation and R2 labeling have priority. The 6 M root target remains unfinished.

Every currently sealed game is packed and verified. All raw and packed file SHAs passed, along with exact seed/identity coverage. The producer, fleet and pack-only PGIDs 4150219, 4151857 and 65468 have no members. The admission PSI latch and stop markers remain retained. [Pause verification](receipts/pause-receipt.json).

| Source | Games | Root decisions | Rows |
| --- | ---: | ---: | ---: |
| 04 | 1,422 | 177,223 | 1,141,229 |
| 01 | 81 | 10,152 | 65,337 |
| 03 | 204 | 25,167 | 161,631 |
| Total | 1,707 | 212,542 | 1,368,197 |

There are 4,012,822 stored root candidate scores and zero pending unpacked roots. Root decisions and candidate scores are different counts. Smoke is excluded. No 6 M target overshoot occurred.

The canonical manifest is on **127x04**, under `/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/pause-concat-manifest.json`; `fleet-concat-manifest.json` has the same sealed pause contents. Manifest SHA: `4e8faf7edc7164a6676f76e4f7a7d6ea237d4eba88d19252a0921c40cf409ef8`. A small review copy is [pause-concat-manifest.json](receipts/pause-concat-manifest.json). It pins all five shard manifests and three host manifests.

A future fit can combine parent r1 corpus `1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b` with these five TeacherStore shards through the existing `combined_batch` cumulative row ends. Root scores and root-valid masks remain stored; offsets stay local to each shard. All shards are physically on 04, including the read-only imports of stopped 01/03 output. Original source games and all verified packs are retained.

The unchanged frozen r1 packer completed under one nice-19/SCHED_IDLE process on core 39. It was a pack-only operation: no teacher initialized and no games admitted. The intentionally interrupted idle producer packer returned SIGTERM143; all game workers exited 0 and the separate pack-only operation passed. The admission pressure latch was never cleared for this operation. Final full PSI avg10 was 0, MemAvailable 115,291,308,032 bytes.

The sole continuation runs every 30 minutes, next scheduled 02:37:26.592Z. Expected releases around 06–07Z or after K-v2 are estimates, not permission. No retry or admission before explicit release.

On a future authorized resume, preserve the same seeds/scientific source and SHA-verified packs. 04 already has the third standard batch, so its normal packer skips every preserved game. The future fleet uses the SHA-pinned imported host manifest only when a stopped host's full-vacate totals exactly match that baseline. Four metadata qualification checks passed. A resumed host with new data uses its new full host manifest and replaces the imported logical host corpus wholesale; never concatenate both versions of the same baseline seeds. The current pack-only script deliberately pins 81/204 stopped-host games; update expected sealed counts and freeze a new packing operation before reusing it after any host generates more data.
