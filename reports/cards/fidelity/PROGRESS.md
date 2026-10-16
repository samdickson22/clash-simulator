# Card fidelity progress — complete

2026-10-15. All 66 cards completed, in the requested priority order. Final results: **4 PASS, 62 DIFF, 0 NOT-IN-ROYALESIM, 0 HARNESS-GAP** against RoyaleSim’s full 16.402 table.

| Priority | Cards | PASS | DIFF |
|---|---:|---:|---:|
| Group 1 | 14 | 2 | 12 |
| Group 2 | 13 | 0 | 13 |
| Remaining | 39 | 2 | 37 |

PASS: MegaMinion, Pekka, SkeletonKing, Mirror. These verdicts cover the measured base-card scenarios; active abilities and evolved/hero forms were not tested.

- 620 unique paired scenarios: 196 natural + 114 controlled, each under two table arms.
- Full 16.402 table (`cards-160402017-20261006.1`) is primary; adapter default (`cards-15535.1` + measured 16.402 corrections) has 6 PASS / 60 DIFF. GoldenKnight and RageBarbarian account for the change.
- Final numbers imported read-only r1 src and r1 gamedata on 127x08. All runtime hashes rechecked unchanged at completion.
- RoyaleSim installed at `/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/royalesim/` on 08, build `ffe0d27de00cd2cc1121e573eba8796bfb8f5f6a` (clean).
- Every final deployment accepted; no engine exceptions. Six explicit reference-hand interventions put Collector in the test hand (one per scenario/arm); no elixir top-ups.
- Collector ran 175 seconds to observe both idle lifetimes. Controlled spell probes used 19 offsets for Freeze, Snowball, Vines, Rage, DarkMagic and GoblinCurse.
- Verified all 66 report rows, all 620 unique scenario keys, r1 source pin/hash, and cited source symbols. `verification.json` records the successful check.
- Only `reports/cards/fidelity/` changed by this worker. No commits or pushes.

## Outputs and resume

`RESULTS.md` contains the 66-card verdict table, concrete paired numbers, likely causes and r1 file/functions. `results.jsonl` retains every final paired measurement and difference; `summary.json` is the per-card verdict index. `causes.json` supplies reviewed attribution notes. `REPRODUCE.md` explains how to resume or rebuild reports.

No jobs remain running. All raw runs, logs, and PID files are retained under `/mpac/sdicks02/jobs/clasher/cards/fidelity/20261015/` on 08. `provenance.json` lists every supervisor PID and its exited status. Group-1 and initial broad outputs were written incrementally; early harness failures were repaired and superseded. Collector opening-hand forcing, Clone/Mirror lineage, and variant lineage corrections are in the harness, with explicit counters where they intervene.
