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
