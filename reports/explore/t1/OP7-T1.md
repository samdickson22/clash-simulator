# OP-7 candidate: source-proven Ubuntu apt maintenance

Authority: coordinator commit 33d0fc06bd8f42dd2e34db4b99b57027b3c551b9,
label 21:24Z. Candidate base is the exact reporting freeze
aeeb3003d2a877bd7ff538a1977cbbc37adb404f. NOT ADMITTED: independent Claude
Opus high review and fresh source qualification/smoke precede any new phase.
08 continues on unchanged OP-6 bytes; 01 stopped at21:03:53Z. Outcomes SEALED.

## Provenance

Capture `/proc/<pid>/cgroup` between command/identity collection and the existing
PID-generation/UID/PPID recheck. Only unified or `name=systemd` hierarchy evidence
is accepted; conflicting evidence fails closed. Exact paths:
`/system.slice/apt-daily.service`, `/system.slice/apt-daily-upgrade.service`.
Unavailable evidence, suffixes, other prefixes and child cgroups receive no
exception. A root requires UID0 and an exact Ubuntu command path:
`/usr/lib/apt/apt.systemd.daily`, `/usr/bin/unattended-upgrade`, `/usr/bin/apt-get`,
`/usr/lib/update-notifier/apt-check`, `/usr/bin/dpkg`; known system shell/Python
wrappers are recognized. Relative paths and lookalikes are denied.

Descendants require a cycle-free observed parent tree to an approved root,
UID0 and the same proven cgroup throughout. Root receipts bind PID/start/UID,
cmd SHA, PPID/PGID. Missing ancestors or changed provenance receive no inherited
exception. Unproven apt commands are foreign even when not Python. Other
foreign/console, system-bus, idle-service and unknown-source SSH rules remain.

## Meter and disclosure

One summed apt host-family meter, shared within each rotated eight-arm block:
self plus `cutime+cstime` deltas for all observed members; distinct process
generations have distinct baselines. Flag strictly >0.5% of one core averaged
over a block; count and disclose the block. Stop strictly >10% average after
elapsed>=60s or strictly >150% in one census sample. Integer ticks and rational
denominators govern inclusive boundaries. OP-6 SSH budgets are unchanged and
evaluated independently. Each occurrence records block IDs, PID/start/UID,
cmd SHA and command, protected cgroup/root generation, self/reaped ticks and
readable child commands. Complete/interference proofs carry apt_flagged and SHA.

Residuals: auto-reaped/orphaned CPU may escape; observed child CPU can be charged
again on reaping; pre-block CPU reaped inside a block is charged. Orphans without
an observed approved ancestor fail closed. No privileged reader, system-service
mutation or retrospective reclassification of completed OP-6 proofs is used.

## Prespecified descriptive sensitivity

Add a separate descriptive analysis excluding entire apt-flagged blocks, with
retained empirical occupied-cell weights, fresh RNG2026101040 and the registered
resampling count. Empty retained populations: NO_UNFLAGGED_BLOCKS. It never
replaces primary or SSH analysis and never advances their RNGs. The standalone
health ledger carries both flags and verifies exact meter/proof bindings.
Legacy OP-5/OP-6 proofs have no apt flag. PC4 must check both flags before either
release route; reducer semantic checks precede outcome output. Amendment1 and
PC1–PC3 remain mandatory. No actual outcomes are used by candidate tests.

## Reviewed recovery mechanics

After confirmation, qualify and smoke new admitted bytes on both named hosts
in fresh directories. If graceful clean-boundary draining is unavailable, use
the previously reviewed hard-stop fallback; preserve all completed 08 blocks
and final durable copies. Inventory only newly stopped replacement-r1 phases,
never the original phases again. Existing ledger/full dispatch history,
unchanged unstarted seeds and cell/seat/rotation-preserving banks govern.
Commit inventory and balanced01/08 dispatch before launch. No one-host dispatch.
STOP-127x08 remains authoritative. Live runtime/source files stay untouched.
