# Pre-training label and loader amendment — 2026-10-08 06:38 UTC

Recorded before formal T6/T7 fitting, model selection, or any heldout payload
access. The base PREREG, prior amendments, producer, split, stopping rule and
all evaluation thresholds remain unchanged. This applies to training labels
and operational data loading, not outcome-dependent evaluation changes.

The 121-train/15-validation snapshot contains 275,223 contradictory body-name/
card-hint rows. Retained ordinary/rich observations agree on every checked
same-tick join, while the producer catalog assigns incorrect names to some
runtime body IDs. A parent deployment's hint also legitimately differs from
its spawned children. See LABEL-AUDIT.md for counts, evidence and limitations.

Use `labels_v4.BodyLabels` in training and in later authorized validation/heldout
label preparation. Resolve a body only when the pinned gamedata's reachable
card payload graph has exactly one identity with the observed level-11 maximum
HP, or a validated crown-tower anchor and HP. Normalize explicit aliases.
Ambiguous/no-match identities remain unknown and spatially masked. Never use
CSV ordinal as a certified runtime identity, or a parent hint alone as truth.
Visibility/deploying status requires a same-tick ordinary/rich join agreeing on
owner, card ID, position and HP. Preserve all original observations unchanged.
These are weak training labels; this does not certify board annotation quality.

OpenCV's frame-number seek was demonstrated to return sequential frame 1,866
when asked for 1,867 in the timestamped source. Use exact sequential frame
ordinal for uncached reference loading and predecode. The cache stores lossless
uint8 832x448 BGR arenas, 64x448 HUD atlases and sanitized source pixels, in
indexed Zstd/XOR blocks. Source pixels preserve the existing JPEG-before-resize
augmentation exactly. Require per-file hashes and an independent random 1%
frame equality check. No heldout media is cached during preparation.

T7 may prepare samples on six CPU threads with serialized RNG plans and ordered
delivery. The augmentation distribution, sample order, batch size, optimizer,
initialization and 24x400 training steps are unchanged. Checkpoint the RNG state
of the consumed sample, not prefetched work; checkpoint and exit on SIGTERM.
The historical sampler and concurrent loader agree exactly on 32 tested
windows, including JPEG, affine and flip augmentations and RNG states.

The authentic producer-completion gate admits training after either registered
collection stop: coverage met, or the 36-hour cap (including its existing
380-second complete-match reserve). Cap completion with insufficient coverage
records a failed coverage gate; it neither extends collection nor passes any
evaluation gate. Completion evidence, split and registration hashes remain
mandatory. Leased training requires a checksum-verified complete population;
GPU-only hosts require preconverted T6 data. No automatic heldout opening is
added.

No storage-budget increase is authorized by this amendment. The existing 40 GB
fleet footprint remains binding pending an explicit answer to the raised
storage question. A bounded five-match cache is an engineering pilot, not a
subsample authorized for formal training.
