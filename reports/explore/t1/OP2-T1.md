# T1 operational delta OP-2

Coordinator authorization: 2026-10-10 15:28Z user instruction. Reviewed freeze
base: `95883be0bfd4d0a6e8dade56ca6a6669637c4a49`. Reporting remains at zero,
with outcomes SEALED, pending fast review and a fresh post-delta smoke.

## Evidence

The stopped03 diagnostic captured21 approved direct cat reads beneath
authenticated parent776414, start137136686, UID3822945. Connection source was
`129.65.221.14 35798 129.65.221.13 22`. Three frozen census reproductions
retained valid cat/path snapshots but subsequently found the children exited
before environment lookup. The diagnostic receipts retain those exact identities
and commands; they contain no game outcomes. All failed smoke attempts remain
preserved and excluded, including the entire smoke-after-freeze-r3 attempt.

## Enforcement

Collection retains only SSH_CONNECTION from the environment, together with child
PID/start/UID/raw cmdline SHA and command/path. It captures the authenticated
ancestor's PID/start/UID/cmdline SHA during that same collection and requires it
to match the parent in the census. Identity changes during collection discard
that row. A captured exited reader remains evidence; there is no late environment
lookup. A proven source is cached only for that exact authenticated parent
identity, in memory, within one job namespace. It is never inferred from a path.

Only UID3822945 authenticated03 sessions proven to originate from
129.65.221.14 receive a fork/exec confirmation window. Its deadline is at most
two seconds from the first unresolved snapshot, measured by the monotonic clock.
Every child observed in the window is retained by PID/start/UID. A reader's frozen
cat/sha256sum command and approved path at snapshot time count as resolution,
including when it subsequently exits. Empty argv or the inherited SSH process
title may resolve by exec within the window. Existing OP-1 shell intermediaries
still require their entire subtree to be attributable; their command set is
unchanged.

Unproven/wrong sources receive no grace. Wrong UID or parent identity, changed
connection evidence, non-readers, exited unresolved children and late resolution
deny admission. A denial remains foreign even if the child disappears from the
next snapshot. Newly observed children are included in the final OP-1 subtree
check. The frozen reader command/path set and other process allowlists are
unchanged.

`op2-confirmations.jsonl` records exact parent and source evidence, every observed
and resolved child command/SHA, elapsed confirmation time, acceptance/denial and
block IDs. Existing allowlist occurrence records carry this receipt per block.
Their counts remain part of the interference disclosure. No outcome or per-game
timing output is introduced.

## Validation and next admission

`receipts/op2-unit-tests.json` binds the tested candidate bytes:20/20 guard tests
passed on stopped03, nice10/SCHED_OTHER, physical cores0–4. Fifteen OP-2 tests
cover positive admission, the exited-before-env race, bounded fork/exec, the
two-second limit, wrong source, non-reader, unresolved exit, all observed children,
changed parent PID-generation/UID/cmdline, contemporaneous source-parent binding,
the first fork with source captured before reader exec,
and the final foreign-process guard. Five existing OP-1 tests also pass.

This delta changes the guard, its tests and the qualification test list only.
The previous scientific source-bound qualification and freeze remain historical
records. After fast reviewer confirmation, refresh the source-bound qualification
on01/03/08, record the reviewed OP-2 file hashes in the admission manifest, and
retry smoke in a new namespace. No reporting starts before successful all-host
smoke. Host set01/03/08, lost-host mechanics and08's B stop remain unchanged.
