# Amendment 15 — prospective epoch assembly file admission

DRAFT FOR INDEPENDENT REVIEW. Prepared 2026-10-09 after the A13/A14 review
(c6eeb4e6007993862489afac039cf6198be0ac0d52a38a16ed4c2e12a84ce41d).
This draft does not authorize a body seal, bound, selection or heldout opening.
The Amendment 12 draft, pins and freeze record remain byte-identical.

## Why a new file-layer amendment is necessary

Frozen `record_capture_admission_v4.py` (9d646763…) requires an actual
single-host epoch launch and its full completion receipt. Frozen
`clock_free_body_score_v4.py` (475dcba9…) opens that directory directly.
Per-match queue outputs and retained matches have several real producers.
A synthetic old-format completion would falsely attribute them to one run.
We therefore retain every original source and describe them in a new explicit
`clasher.v4.epoch-capture-assembly.v1` manifest. No legacy manifest substitution.

## Scientific scope

Only file location, population assembly and provenance authentication change.
The 24 checkpoints, all 64 validation matches, all nine body thresholds,
original decoder/tracker/cleaner, body counts and ranking, event predictions,
truth mapping, bound arithmetic, complete selection key, standalone deciding
measurements, D4 verifier, calibration, joint-seal and heldout rules do not change.
Journals remain quarantined. Their declared digests are preserved as opaque
provenance and their files are never opened by assembly, body scoring or bounds.

This first implementation admits original record-only producers exclusively.
It rejects vectorized/unknown producer classes. A14 qualification does not
implicitly change this restriction. Adding the separately qualified vectorized
whole-match worker needs an explicit pin-table extension reviewed before use.
Deciding measurements, measured D4(b) outputs, all availability/timing, heldout
replay and T6 always retain the original path.

## Assembly and admission contract

Each epoch manifest contains its checkpoint, bundle and original non-clock
equality pins and exactly 64 entries, one per registered validation episode.
Every entry pins its real host and directory, original manifest, nine compressed
record SHAs, nine uncompressed record SHAs, frame count and opaque journal SHAs.

Retained sources bind a closed-match inventory from the immutable queue plan
(or the separately pinned final 02 inventory), the exact inventory row, actual
original launch plan and capture driver source. Admission authenticates the
actual manifest and every record stream against these pins. It verifies the
original launch assignment, output location and source snapshot; it never
reinterprets a retained source as a queue producer.

Queue sources bind the immutable queue plan, exact task/claim, externally pinned
host plan, controller identity, intent when required, launch, successful outcome,
complete receipt and original worker SHA194dbbe3. A separate verifier rereads the
entire chain and all nine record streams. Assembly rereads this evidence rather
than trusting a `verified` status or a producer's metric claims.

Missing/duplicate episodes, duplicate retained-plus-queue sources, wrong
checkpoint or bundle, altered bytes, unknown/mixed schemas, absent provenance,
unverified queue outcomes, suspended queue or nonterminal retained tasks fail
closed. No first-wins choice among two completed sources. Failed/partial
attempts remain in the ledger and are never silently promoted.

The 24 assembly-manifest SHAs become the externally pinned 24 complete capture
identities for A1. This means 24 full authenticated populations, not 24 fabricated
single-run complete receipts. The admission result keeps the existing record-only
contract, with an explicit assembly identity and per-episode locations/provenance.

## Staged authority and review requirements

Before A1: independently review/freeze this amendment and its exact file-layer
pin delta; verify all 953 new queue outputs, all 61 retained terminal entries,
R13-3's four complete-match audit on two leases under production load (including
e01/708 and the longest late-epoch match), all 24 assemblies and the immutable
execution snapshot. Obtain coordinator-approval-A1.json before any real body seal.

After the verified body seal: A2's timed real bound pass. No preseal bound or
real body-score benchmark. Submit bound hashes, actual cost and the full B
preconditions package before coordinator-approval-B.json. No elimination or
standalone deciding run is authorized by this file layer.

Required tests include exact structural equivalence to the retained full-epoch
layout, all 64 members and nine branches, missing/duplicate/mixed producer
rejection, retained-plus-queue duplicate rejection, wrong checkpoint, tampered
record/proof/source/manifest, refusal to open any journal, unchanged synthetic
body scoring/ranking and unchanged synthetic event/bound arithmetic. Test file
SHAs, immutable snapshot and complete PYTHONPATH tree accompany the review.

## Implementation status

The independent queue verifier is running separately on 04; it does not score.
Implemented in new files: `epoch_assembly_v4.py`,
`epoch_assembly_admission_v4.py`, `assemble_epoch_manifest_v4.py`,
`clock_free_body_score_assembly_v4.py` and
`dominance_orchestration_assembly_v4.py`. The last module exposes A1 body sealing
and the post-seal A2 bound pass only. It requires independent file-layer approval,
coordinator A1 approval binding all 24 assembly hashes, and the unchanged A12
freeze. Its scientific calls are AST-identical to the existing orchestration.

The first focused run passes 69 tests: 24 A15 tests and 45 prerequisite queue,
non-clock and transport checks. The retained epoch-1 file-layout verification passed all 64 matches, 106,744
frames and 576 record streams, with compressed and uncompressed digests checked
against the original complete receipt. No journal was opened and no score was
computed. The exact source/test/runtime-tree pins accompany the immutable review
package. Equivalent full-layout checks for retained epochs 2 and 3 remain required
before A1. No real assembly is complete yet.

B remains separately blocked. The existing deciding controller and measurement
admission still import the old orchestration; they must not be pointed at these
manifests without a separately reviewed file-access integration. That integration
must keep the original D4 algorithm, standalone driver, measured outputs and all
scientific comparison semantics unchanged. This A1/A2 package does not claim to
close the eleven B preconditions or authorize a deciding run. Actual retained
producer authority mappings, all 24 completed assembly pins, R13-3 production
qualification and A1 approval are still required at execution; placeholders
cannot satisfy the executable guards.


## Revision 2: review RC1–RC4 and separately authorized additions

The submitted r1 draft, delta and snapshot remain preserved byte-for-byte.
This revision is prospective and requires an independent delta review. It is
not an execution approval, and it does not modify frozen Amendment 12.

RC1: admission counts candidates across every pinned retained inventory plus
independently verified queue tasks, requires exactly one, and requires the
manifest entry to identify that candidate. A queue entry cannot hide a retained
copy; two retained inventories cannot choose a first winner. The builder also
rejects a retained source alongside an in-flight queue task.

RC2: every R13-3 reference differs from the audit output and binds the unique
retained original's host, directory, inventory and manifest. Each of the nine
reference gzip hashes equals its retained inventory hash. A cross-host reference
copy additionally needs an externally pinned copy receipt naming the original,
the destination and those exact hashes. Neither self-comparison nor an arbitrary
same-shaped reference can satisfy admission.

RC3: fixtures have distinct bytes per branch. Tests cover actual admission,
assembly, queue, scorer and bound entry points, record order/time/availability,
forbidden journal access, all-24 pins and precise threshold mapping. A synthetic
old/new scorer comparison and an explicitly authorized isolated real-data RC3
comparison cover all nine branches. The latter uses real e3/738 (444 frames),
recomputed retained-source provenance and pinned real truth. Test-only adapters
bypass full-fit/all-24 authorization solely to exercise both scorer implementations
on the same authenticated files; this is not full formal admission or body-stage
selection. Only equality and count digests are published. No seal or bound is
created. Final tests and mutation results are in the review package.

RC4: the delta pins queue_audit_io and every new dependency. E1, E2 and E3 full
retained-layout proofs are rerun with this exact file set. R1's proof cannot
stand in for the new pins. The original A12 admission/scorer/ranking/orchestration
remain unchanged.

### Explicit archive relocation

A relocated queue entry requires an external receipt pin in the assembly
authority, equal to the closed queue's relocation pointer. The receipt binds
claim/task, original host/directory, original independent proof, complete and
manifest, and all 18 stream hashes. Allowed destinations are the preserved
04 verified-retention prefix and the new dedicated 03 prefix:
`/mpac/sdicks02/v4-archive/verified-capture-20261009-r1/`.
The exact destination includes source host/task/claim. There is no implicit
fallback, missing-file substitution or destination inference. Only receipt-bound
output files route to the archive. Original producer plan/source/controller/
intent/launch/outcome remain authenticated at their actual locations. The full
independent audit is recomputed through this transport and must equal the
original proof. Journal hashes remain opaque; journals cannot be opened.

The running transport checksums and fsyncs the destination before writing a
relocation receipt and retiring only copied stream files. It preserves source
completion/manifest metadata, all failed attempts and prior relocation receipts.
03 is named explicitly in each new receipt. The separate 2.0 TB reservation
ledger and 40% per-host free-space guard govern storage; active producer plans
remain unchanged.

### Process-local sealed epoch admission

The prospective A1/A2 CLI opens an exclusive admission session. Each epoch is
fully authenticated once in that process. Its exclusive JSON-round-trip-checked
receipt records every opened/hashed evidence file, the exact assembled admission,
authority, closure, checkpoint identity and source tree. Reuse requires the same
in-memory receipt and exact persisted receipt hash/content. Authority, assembly,
closed live queue and source bytes are rechecked; compact provenance evidence
is SHA-rechecked in batches per host on every reuse. Each score/bound record
read still authenticates its compressed and uncompressed bytes; body scoring
rechecks them afterwards. Weights are not loaded by this cache. A new process
always authenticates again: loaded JSON alone has no admission authority.

This is the proposed non-weakening optimization for independent review, not an
assertion of reviewer acceptance. The file-layer cost sample on actual e3/738
measured full retained reauthentication at 4.70–4.83 seconds and compact provenance
rechecks at 0.39–0.44 seconds. Record reading/scoring remains additional work.
This sample is one match, not a full-epoch estimate or an A2 measurement. The
actual per-step A2 cost must be measured by the real timed post-seal pass, after
24 complete assemblies and coordinator A1 approval. No pre-seal bound benchmark.

### Remaining execution gates

Every item in the independent review's 13-step A1 checklist still applies.
In particular, the live queue must close unchanged, all 953 queue proofs must
be recomputed, R13-3 must pass under production load with the new reference
bindings, and the coordinator must bind all 24 assembly hashes in A1 approval.
B and its eleven preconditions are separate and unresolved. Neither cached
admission nor relocation grants deciding-measurement, joint-seal or heldout
access. Vectorized producers remain rejected by this A15 revision.
