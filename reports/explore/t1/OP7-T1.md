# OP-7 candidate: source-proven Ubuntu apt maintenance

Authority: coordinator commit 33d0fc06bd8f42dd2e34db4b99b57027b3c551b9,
label 21:24Z; r1 correction rulings a3b7d82b/c1c9a38d (actual21:46Z),
and EACCES argv0 authorization 7c581dc5 (actual22:03Z). Candidate base is the exact reporting freeze
aeeb3003d2a877bd7ff538a1977cbbc37adb404f. NOT ADMITTED: independent Claude
Opus high review and fresh source qualification/smoke precede any new phase.
08 continues on unchanged OP-6 bytes; 01 stopped at21:03:53Z. Outcomes SEALED.

## Provenance

Capture `/proc/<pid>/cgroup` between command/identity collection and the existing
PID-generation/UID/PPID recheck. Only unified or `name=systemd` hierarchy evidence
is accepted; conflicting evidence fails closed. Exact paths:
`/system.slice/apt-daily.service`, `/system.slice/apt-daily-upgrade.service`.
Unavailable evidence, suffixes, other prefixes and child cgroups receive no
exception. A root requires real/effective UID0 from `/proc/<pid>/status` and an exact Ubuntu command path:
`/usr/lib/apt/apt.systemd.daily`, `/usr/bin/unattended-upgrade`, `/usr/bin/apt-get`,
`/usr/lib/update-notifier/apt-check`, `/usr/bin/dpkg`; known system shell/Python
wrappers are recognized. Relative paths and lookalikes are denied.

Descendants require a cycle-free observed parent tree to an approved root,
real/effective UID0 or an approved `_apt` method, and the same proven cgroup throughout. Root receipts bind PID/start/UID, real/effective UID evidence,
cmd SHA, PPID/PGID. Missing ancestors or changed provenance receive no inherited
exception. Unproven apt commands are foreign even when not Python. Other
foreign/console, system-bus, idle-service and unknown-source SSH rules remain.

The trust anchor is the kernel protected systemd cgroup: only privileged code
can place processes there. `/proc/<pid>` directory ownership alone is not UID
proof because non-dumpable user processes can appear root-owned. Read and recheck
real/effective UIDs from `/proc/<pid>/status`, within the generation recheck.
The base guard's directory-owner rule outside this exception remains unchanged.

Resolve `_apt` from `/etc/passwd` (no hard-coded UID); both real/effective UIDs
must match. Methods require the same exact cgroup and an observed approved root.
Their resolved kernel executable must be a direct child of `/usr/lib/apt/methods/`.
Only EACCES permits the narrowly authorized fallback: raw captured argv0 must be
absolute, contain no `..`, resolve to an existing regular direct-child file under
that directory, owned by root and unwritable by group/others. Record `proc/exe`
or `argv0 (proc/exe EACCES, unprivileged)` with file UID/mode/inode/device and errno.
ENOENT, EPERM, other errors, bad paths/files/UIDs and absent ancestry fail closed.
No `_apt` grandchildren with other executables inherit a name-only exception.

## Meter and disclosure

One summed apt host-family meter, shared within each rotated eight-arm block:
self deltas plus unobserved `cutime+cstime` deltas for all observed members.
Generation-bound subtree credits subtract CPU already metered for observed
children when reaping advances the parent's child counters. Credits transfer
from deepest to shallowest for nested simultaneous exits, persist across a
scan-before-wait race, and are clamped against actual child-counter increments.
Unobserved short-lived child CPU remains counted; PID reuse gets a fresh baseline.
Both the block meter and the persistent host sample meter use this correction. Flag strictly >0.5% of one core averaged
over a block; count and disclose the block. Stop strictly >10% average after
elapsed>=60s or strictly >150% in one census sample. Integer ticks and rational
denominators govern inclusive boundaries. OP-6 SSH thresholds are unchanged and evaluated independently; its meter uses
the same correction only in the new OP-7 phase, never in the running r1 phase. Each occurrence records block IDs, PID/start/UID,
cmd SHA and command, protected cgroup/root generation, self/reaped ticks and
readable child commands. Complete/interference proofs carry apt_flagged and SHA.

Residuals: auto-reaped/orphaned CPU may escape; pre-block CPU reaped inside a
block is charged. A process scan is not atomic: credit settlement can cross
samples, and unobserved residual CPU can arrive in a single sample. There is no
promise of exact real-time attribution for children that vanish between scans.
New proofs declare cpu_accounting_rule=OP-7-observed-child-credit-v1; preserved
original/replacement-r1 proofs retain their legacy meter and flags unchanged. Orphans without
an observed approved ancestor fail closed. No privileged reader, system-service
mutation or retrospective reclassification of completed OP-6 proofs is used.

## Prespecified descriptive sensitivity

Add a separate descriptive analysis excluding entire apt-flagged blocks, with
retained empirical occupied-cell weights, fresh RNG2026101040 and the registered
resampling count. Empty retained populations: NO_UNFLAGGED_BLOCKS. It never
replaces primary or SSH analysis and never advances their RNGs. Add another separate descriptive analysis excluding blocks flagged by SSH OR
apt, with the same fresh seed and occupied-cell treatment, never altering the
primary or separate SSH/apt analyses. Disclose both-flag and either-flag counts
by population and cell. The standalone health ledger carries all three flags and verifies exact meter/proof bindings.
Legacy OP-5/OP-6 proofs have no apt flag. Missing flags fail closed. PC4 must check all three flags, both/union counts and
counts of complete proofs with apt/SSH stop=True (completion-edge disclosure) before either
release route; reducer semantic checks precede outcome output. Amendment1 and
PC1–PC3 remain mandatory. No actual outcomes are used by candidate tests.

## Reviewed recovery mechanics

After confirmation, first stop 08, wait final durable copies and drain the
original owned copier. The reviewed supervisor has only a hard-stop fallback;
use it with its reviewed completion-race handling. Then qualify and smoke new
admitted bytes on both named hosts in fresh directories; preserve all completed 08 blocks
and final durable copies. Inventory only newly stopped replacement-r1 phases,
never the original phases again. Existing ledger/full dispatch history,
unchanged unstarted seeds and cell/seat/rotation-preserving banks govern.
Commit inventory and balanced01/08 dispatch before launch. No one-host dispatch.
At admission only, restore manifest status FROZEN, re-hash and bind the actual
independent confirmation plus authorization to its SHA. STOP-127x08 remains authoritative. Live runtime/source files stay untouched.
