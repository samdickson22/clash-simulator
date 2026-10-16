# R27 primary acceptance failure — first interim

Observed2026-10-16T12:41:33Z; detailed row
01:job/pilot-r27/rows/B-00000.json, raw outcome retained (score1, terminaltrue).
Child exit1, zero native FAILURES, four rejected deployments:

| tick | seat | card | action | reason |
| --- | --- | --- | --- | --- |
| 6027 | 1 | Knight | 1261 | GAME_OVER |
| 6057 | 1 | Knight | 1272 | GAME_OVER |
| 6087 | 0 | Giant | 1965 | GAME_OVER |
| 6087 | 1 | Knight | 1272 | GAME_OVER |

The prior accepted command in this row is at5997. All rejections are late
GAME_OVER(code10), not placement WATER/territory. This is observed command
evidence, not a diagnosed source cause or a permission to waive it. Parent and
children continue the originally authorized job while essential action is
requested; source, inputs and caches remain frozen. No retry/exclusion/repair.

Preserved first interim has22observed/300requested rows,21clean scored rows,
B6clean primary pairs, qualityfalse/parent incomplete. The existing report
excludes the invalid B0-index row from clean-pair metrics; all original outcome
rows remain on disk. These partial clean-only statistics cannot decide the
preregistered primary rule. Raw row and every rejected event will be retained.

Next decision requested from parent: stop the verified owned primary process
under its existing cleanup to conserve invalid-run compute, or finish all300
as failed exploratory evidence. No dependent acceptance or confirmation step
can proceed on this zero-rejection failure.

## Directed stop and source audit — supersedes the pending decision above

The owner directed STOP. At2026-10-16T12:43:32Z, PID632390/PPID632373 and its
exact primary command were verified, then only that parent received SIGTERM.
Its existing bounded cleanup reaped the8 owned children; parent and shell
finished143 at12:43:33Z. All verified owned PIDs are gone. R27 is permanently
INVALID/INCOMPLETE; no retry, exclusion, relabelling or restart occurred.
Original text is preserved byte-for-byte as pilot-r27-first-failure-initial.md.
Correction to the initial receipt's wording: the excluded row is **B/case0**,
not the B0 arm. Its raw winning outcome and all four refusals remain intact.

Post-stop inventory:55rows/300requested,47terminal,43clean,8terminated,
245missing. Four terminal rows(A/case10,A/case12,B/case0,B0/case13)
contain16GAME_OVER refusals; all four raw outcomes are wins. The unambiguous
identifiers are A-00010.json, A-00012.json, B-00000.json and B0-00013.json.
The post-stop report exited1; its clean-only metrics cannot determine the
primary strength rule. No native FAILURES in terminal rows. Interrupted rows
retain explicit signal exit-15 and missing diagnostics rather than fabricated
game outcomes. See pilot-r27-stop-audit.json for full counts/event records.

Pinned calibration/API/source audit establishes a separate public no-command
phase from6000 while HP drain continues toward final game_over. Do not stop
drain/scoring early or filter the recorded GAME_OVER events. The recommended
common adapter guard preserves last-accepted commands and unsent reservations,
skips dispatch/polls only in that public phase, then drains the native engine
to its actual terminal winner/crowns/HP/tick. No source or tests were changed.
Detailed evidence and meaningful late-pending/last-accepted/final-score test
proposal:pilot-r27-terminal-order-audit.md. Owner review remains the next step.
