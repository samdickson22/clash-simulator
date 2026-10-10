# T1 OP-4 — LAN SSH interference budgets

Coordinator 16:25Z authorizes this delta on reviewed OP-3 `9cd518d3`.
Reporting remains zero/SEALED until independent confirmation, final-source
qualification and a fresh healthy all-host smoke. This candidate does not refresh
FROZEN-T1.json or admit itself.

## Source and scope

Only authenticated `sshd: sdicks02@notty` sessions with UID 3822945 and
captured `SSH_CONNECTION` source in 129.65.221.0/24 receive the SSH budget
exception. Their observed descendants receive the same exception, regardless of
command. Source evidence is captured with the child's identity and a separately
captured parent PID/start/UID/cmd SHA; the collector rechecks child generation,
parent and UID after reading evidence. Unlike OP-2's reader provenance,
OP-4's separate parent traversal supports arbitrary descendants (64 ancestors).
The source cache is scoped to the job and exact authenticated parent identity;
a changed generation cannot inherit it. Unknown, non-LAN and conflicting sources
retain OP-1/2/3 identity rules. A previously captured source remains evidence
through a childless gap. Approved idle-service identities and descendants also
participate in the aggregate host budget.

OP-2's module, tests and frozen command set are unchanged. LAN-budget rows are
removed from its identity-only input; any remaining identity input follows its
existing logic. Newly captured source evidence is applied again before final
foreign classification. Non-SSH foreign work stops immediately. System dbus
continues OP-1 identity/meter rules; owned workers continue OP-3. Any positive
console census stops immediately, including during admission.

## CPU accounting and receipts

Every census records all observed authenticated SSH-family processes, including
identity-only unknown/non-LAN sessions, and approved idle services. Receipts bind
block IDs, PID, start, cmd SHA, readable command, CPU ticks, captured source,
parent identity and readable child commands. LAN-budget classification is explicit.
Per-block receipts retain each budgeted process/command identity, attributed CPU
ticks and seconds, and child commands. These records contain no game outcomes.

CPU ticks are self user+system ticks, not child-inclusive counters, so descendants
are not counted twice. Existing processes start from the block's baseline;
newly observed processes born within the block count CPU since birth. Generation
keys prevent PID reuse from subtracting a predecessor's ticks. Disappeared
processes retain their last observed CPU; work entirely between one-second
censuses cannot be recovered from /proc and is not claimed as measured.

The host's aggregate budget is applied to every concurrent block, because it is
host exposure shared by those slots. At completed block average:

- At most 0.5% of one core passes; greater than 0.5% flags interference.
- At most 2% is within the stop threshold; greater than 2% stops the host run.
- A single census average greater than 25% of one core stops the host run.

The 2% stop is checked against cumulative elapsed block time during execution;
a short early burst can therefore stop conservatively before a completed-block
average is available. Comparisons use integer ticks and exact rational forms of
the captured elapsed seconds, with inclusive thresholds. Final health reports
both all interfered blocks and SSH-family interfered blocks.

All eight rotated arms execute in the same slot and share this host exposure.
Tiny SSH CPU is paired noise; disclose the measured exposure and flagged-block
counts with the freeze/launch and final health. No scientific runner, seed,
replacement allocation, reducer or per-game outcome emitter changes.

## Copier exit race

The collector retains only SSH_CONNECTION and the two owned-copier identity
variables from the environment. The existing copier command, path, lease,
PID/PGID and source predicate uses those captured values if its child has exited.
Other environment fields are not recorded. An unmatched copier identity still
fails that predicate; proven LAN descendants separately remain budgeted by OP-4.

## Tests and failed smoke

41/41 guard tests pass: existing OP-1/2/3 26 plus OP-4 15. OP-4 covers below-budget
pass, exact thresholds, flag, average/sample stop, LAN descendants and childless
gap, reused parent, unknown/non-LAN fallback, invalid parent binding, non-SSH
foreign stop, console admission/run stop, newborn/exited CPU accounting, source
revocation, approved idle budget, exited copier attribution and integrated census
receipts. Independent fast confirmation is pending.

Fresh OP-3 qualification passed on 01/03/08: 81 tests,125 frozen states,125 belief
histories/250 ON/OFF variants and53 stable source files. Smoke-r4 failed its guards
and is entirely excluded: 01 own STOP (3 failed),03 foreign-active SSH parent
776414 (3 failed),08 foreign-compute SSH parent1896254 (2 failed),0 complete
blocks. Copier312275 and supervisor312425 on01 have drained.

03 post-failure evidence captures the exact approved04 archive cat source.
08's failing child was not recorded by the old stop receipt. A100-snapshot
post-failure reproduction of an own01→08 rsync metadata copy observed no child
under1896254; this does not establish that the original child was the copier.
Full metadata evidence remains in the owned smoke-r4 diagnosis directory.
