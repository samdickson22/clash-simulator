# Interim M retrain, registered 2026-10-22

Sam authorizes M primary, S100 secondary, no deployment. This work starts from exact published parent
7f3b1cbaa9d1ee33d59faed4e5f9e9bfd9f4f305 in an isolated worktree. Parent owns merging.

Input registration precedes compute. Frozen oldest acked prefix of 240 sealed batches, part-000000-b00 through
part-000024-b05, contains 119,970 source matches. Input receipt-map SHA256 is
2422eb7321982a60b14f5152d3a4338f456294d1cd249b6cbb973de834c765c2.
It is stored at /mpac/sdicks02/datasets/pretrain-v1/05/interim-20261022-b240/input.json.
Raw receipt hashes pin all per-match bytes. Open batches are excluded. Reuse the verified immutable 83-batch
shards, hardlink only immutable shards, independently copy the manifest, build 157 new shards with 24 CPU workers
on 05. Current host05 load is 2.9 and MemAvailable 116 GiB. No existing builder/driver/trainer was found.

Builder and featurizer stay unchanged. Both seats and duplicate physical games retain existing 80/10/10 split.
Final is untouched by optimization, calibration and selection. Exact/outcome tiers retain value labels; other
tiers retain imitation truncated at the client end. Live own-bot memory is validation/evaluation only.
Re-drive raw bytes are SHA checked by the existing builder; missing/mismatched source or perspective exceptions
block readiness. Every built file is verified locally and again on 08 before atomic STORE-READY publication.

M is d320 L6 H8 FFN1280, dropout 0 as explicitly requested in the new authorization. This differs from the previous
next-M's dropout 0.1. No new architecture or strategy. Random initializations 2026102001 and 2026102002.
AdamW 2e-4, wd .01, bf16, batch512, 3 torch threads, 8 passes maximum, patience2, one-pass warmup and cosine,
64 GPU-hour per seed cap, capped DEV each pass and registered full-DEV select_bc across both seeds/all epochs.
Hog donor balance, exposure cap5, domain/IPW/value weights and missing-age augmentation stay unchanged.
R7 consumed-future release stays intact. Only optional environment-driven cooperative host checks are added to
Store construction and batch preparation; they exit our own workload without process signals.

Reserve GPU08 only. Existing measured M train allocator peak 26.0234375 GiB gives 39.03515625 GiB cap plus
.7 GiB context. Two exceed 43.5 GiB admission budget, so seeds run serially. No third seed now because the two
requested seeds establish the repeat and a third would extend the same single-GPU queue.
Require empty compute GPU, no duplicate BC/legacy drivers, all legacy locks, MemAvailable >=50 GiB and load <80
at launch; cooperative checks require >=29 GiB and load <=90 thereafter. Stop on failure, retain all attempts,
never auto-restart. Existing HP1 actors on08 are untouched. No04, Mac, 01/02,09/12/17 or13-16 workload launched.
Logs and owner/intent/completion receipts live under /mpac/sdicks02/jobs/clasher/pretrain-v1/interim-20261022-b240.

Independent Sol high review is required before these source/config changes run. Pin reviewed code bytes in the
launch receipt, recheck resources and duplicates, then run preparation and the authorized BC pipeline. Report
measured build/train throughput and ETA, source/usable match counts, rows, hashes and owner PIDs within one hour.

## Review R1 response

R1 returned NO-GO. All four blockers are addressed before a fresh R2 review: exact frozen input hash is
required before preparation; the reused 83 input hashes must agree; 25 source job files have a separate
jobs-input.json registration with SHA256 2b0cebed9a2988690dc1fd6545c1dd43e745d1e5896b3af2f4f9c175ed5291e9.
The launch pin records the base, reviewed diff, all pretrain package inputs and all imported/new drivers plus
Python/NumPy/Torch runtime identities for each host. Its expected SHA is supplied in the immutable launch receipt
and enforced again immediately before every build/train/select spawn, including after resource waits.
Store checks projected allocation headroom for eager loads, derived row arrays and every concatenation. Fixed
shard arrays are released after concatenation, preserving array contents and batch order. Both local and remote
readiness reject extra visible shard directories without deleting them. Training rechecks the exact shard set.
Build admission needs 60 GiB available and load below60. Training admission stays 50 GiB and load below80.
