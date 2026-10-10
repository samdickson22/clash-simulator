# G sealed pause corpus and current status

Updated 2026-10-10T07:13:12Z. Coordinator released **03 only** at07:03Z. It resumed at07:11:44Z withPID/PGID2669314,56-worker staggered ramp oncores0–55 andmanager/packer59. 01/04/08 remain stopped. The sealed pause corpus below remains immutable and fully verified; new03 roots are tracked separately by the active03 combined manifest. See [resume amendment](RESUME03-RAMP56-AMENDMENT.json) and [progress](PROGRESS-G.md). The6Mtarget remains unfinished.

Every game sealed at the original02:13:34Z pause is packed and verified. All raw and packed file SHAs passed, along with exact seed/identity coverage. The producer, fleet and pack-only PGIDs 4150219, 4151857 and 65468 have no members. The admission PSI latch and stop markers remain retained. [Pause verification](receipts/pause-receipt.json).

| Source | Games | Root decisions | Rows |
| --- | ---: | ---: | ---: |
| 04 | 1,422 | 177,223 | 1,141,229 |
| 01 | 81 | 10,152 | 65,337 |
| 03 | 204 | 25,167 | 161,631 |
| Total | 1,707 | 212,542 | 1,368,197 |

That immutable pause corpus contains4,012,822stored root candidate scores and hadzero pendingunpacked roots. Current03pendingnewroots aredisclosed in03:$job/fleet-concat-manifest.json. Root decisions and candidate scores are different counts. Smoke is excluded. No 6 M target overshoot occurred.

The canonical manifest is on **127x04**, under `/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/pause-concat-manifest.json`; `fleet-concat-manifest.json` has the same sealed pause contents. Manifest SHA: `4e8faf7edc7164a6676f76e4f7a7d6ea237d4eba88d19252a0921c40cf409ef8`. A small review copy is [pause-concat-manifest.json](receipts/pause-concat-manifest.json). It pins all five shard manifests and three host manifests.

A future fit can combine parent r1 corpus `1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b` with these five TeacherStore shards through the existing `combined_batch` cumulative row ends. Root scores and root-valid masks remain stored; offsets stay local to each shard. All shards are physically on 04, including the read-only imports of stopped 01/03 output. Original source games and all verified packs are retained.

The unchanged frozen r1 packer completed under one nice-19/SCHED_IDLE process on core 39. It was a pack-only operation: no teacher initialized and no games admitted. The intentionally interrupted idle producer packer returned SIGTERM143; all game workers exited 0 and the separate pack-only operation passed. The admission pressure latch was never cleared for this operation. Final full PSI avg10 was 0, MemAvailable 115,291,308,032 bytes.

The sole continuation runs every5minutes while03 is active to report pressure alerts. There is no second timer. Every otherhost staysstopped until explicitrelease. Anynew03PSItrip stayslatched and reported;noautoretry. The03supervisor publishes combinedaccounting locally, withSHA-pinned static04/01coverage and no04fleet.

On a future authorized resume, preserve the same seeds/scientific source and SHA-verified packs. 04 already has the third standard batch, so its normal packer skips every preserved game. The future fleet uses the SHA-pinned imported host manifest only when a stopped host's full-vacate totals exactly match that baseline. Four metadata qualification checks passed. A resumed host with new data uses its new full host manifest and replaces the imported logical host corpus wholesale; never concatenate both versions of the same baseline seeds. The current pack-only script deliberately pins 81/204 stopped-host games; update expected sealed counts and freeze a new packing operation before reusing it after any host generates more data.
