# T1 Amendment 1 release barrier candidate

This candidate is isolated from reporting on branch
`worker/t1-amendment1-release-20261010`. Independent review is required before
admission for outcome reduction. It changes no reporting runner, schedule, seeds,
arms, hypotheses, thresholds, or statistical reducer. No actual pool, check,
registration, or outcome release has been produced.

`outcome_release` checks Amendment 1 before either `committed_mac_summary` or
`fourteen_day_escape`. The escape still requires the exact committed reporting
completion and fourteen full days. A bare coordinator release remains invalid.
The reducer calls this barrier before loading any reporting game bytes.

## Common evidence on both release routes

The coordinator release receipt adds `amendment_1_prerelease` with schema
`clasher.t1.amendment1-prerelease.v1`. Its eight artifact bindings are
`amendment`, `completion`, `end_evidence`, `descriptor`, `pool_manifest`,
`pool_check`, `registration_manifest`, and `attempt_roots`. Each binding is:

```json
{"path":"repository/relative/file.json","commit":"FULL_40_HEX","sha256":"FULL_64_HEX"}
```

Every binding must be an ancestor of HEAD and equal both committed bytes and
current working bytes. Absolute paths, traversal, escaping symlinks, shortened
commits, and shortened SHAs are rejected. Every sealed child file is checked at
the seal's commit as well. The actual signed Amendment 1 path/SHA is fixed in
code. No standalone completed boolean opens this barrier.

Completion must retain sealed outcomes and all 2400 primary/600 guard blocks,
with every counted reporting/replacement host and phase. The END inventory must
bind that exact committed completion and all those phases. Only production
`counted-reporting` evidence and the all-host/all-attempt E4 v2 descriptor qualify.
Stopped counted phases are retained verbatim, as are additional source/loss
phases. Completion binds the committed blind ledger and counted inventory. The
real E4 pool check validates logical coverage, source phases and raw exits.

The complete FLEET-POOL seal must include all six E4 output files. The counted
host population, descriptor, END SHA, source attempts and passing-source seals
must agree. No counted host may be excluded. Three repeats, nice10, physical
cores, reporting load and raw-host-times-repeat pooling are required. Both host
ratios must be finite and inside inclusive [0.95,1.05]. Attempt order and every
original source receipt are retained; E4's mechanical classifier governs repeats.

## Pool recheck

After the reviewed E4 pool is available, run `check_reference.py` with
`--descriptor`, `--pool`, `--measurement-root`, and a fresh `--output` path.
It invokes E4's unmodified `measure_tiers.py --pool-fleet-references`, with the
three thread environment variables pinned to1, into an exclusive temporary
directory under `/mpac`. This is read-only reference pooling, not measurement
or Mac access. It compares the complete output SHA inventory and every pooled
output byte. Failure retains private stderr, E4 failure.json and health diagnostics, and
writes no successful check receipt. Stdout contains only
check health, input count and receipt SHA.

The check receipt schema is `clasher.t1.pool-check.v1`. It binds the descriptor,
original pool seal, all output SHAs, checker SHA, and all original source/context
and measurement-file SHAs, checked again after pooling. The barrier requires
these inputs to remain unchanged, checks that its receipt and checker are
committed, and bounds the check time between reporting completion and the
coordinator authorization. It reruns check() itself before either release
route, comparing all fresh input/output identities with the committed receipt.
The predeclared original attempt-root listing must match the descriptor before
and after that rerun; failed attempts cannot be omitted. All measurement source
files must equal an explicit committed E4 source inventory. Actual E4 validation still checks END provenance,
exactness, warmup, CPU/clock receipts and raw state/repeat populations.

## Reviewed registration packet

The packet receives a committed `receipt-manifest.json` with
`scope=T1-REGISTRATION`, `status=complete`, and a relative `files` SHA inventory.
It includes `registration.json`, corpus receipt, golden/belief/student references,
the exact checked speed/deadline references, and every original source receipt
and its complete file inventory. This seal records the packet bytes submitted
for independent review; it does not grant that review itself.

The existing registration fields remain: `sets`, `packet_schedule`,
`fleet_reference`, `deadline_replay_semantics`, and `corpus_receipt`. Added
lineage fields are `pooled_reference_manifest_sha256`, `pool_check_sha256`, and
`source_receipts`. The fleet metadata must equal E4's pooled metadata byte for
JSON value; deadline replay is `committed-copy`; own-tier speed sets each contain
300 unique IDs. `source_receipts` maps every counted host to its chronological
list of `{path, manifest_sha256}` bindings to original FLEET-REFERENCE seals
inside the packet. Both failed and passing attempts are preserved. These files
contain reference/public-state evidence only, never reporting outcomes.

## Validation and remaining gates

The test receipt records the final passing count. The existing barrier tests
and expanded receipt/check tests
use explicitly synthetic Git repositories, not reporting games. Positive
fixtures execute the unmodified committed E4 pooling CLI and check() success
path, including in-barrier checks on both routes. Coverage includes
both permitted routes, missing pool/check/registration, uncommitted modifications,
host/phase/smoke mismatch, original source changes, inclusive ratios, bad ratios,
escaping paths/symlinks, differing recheck output, counted-host exclusion, wrong
load/repeat profile, bad completion/repeat classification, registration lineage,
replay/corpus/attempt omissions, and invalid or incomplete check receipts.

The reporting checkout remains on the reviewed operational candidate. The
isolated branch needs review and later deliberate admission before reduction.
Corpus approval/build, E4 END/guard fixes, A6 smoke, reporting completion, END
reference measurements, pooling, packet review and coordinator outcome release
remain outstanding. None is represented by a synthetic success receipt.

C1–C4 response and release-envelope additions are specified in
RELEASE-REVIEW-RESPONSE-20261010.md. The first actual production check and packet
require independent review; synthetic tests grant no outcome release.
