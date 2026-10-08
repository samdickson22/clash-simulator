# T7 engineering shakedown (validation/heldout quality not claimed)

Completed on 127x01 A6000, eager Torch 2.7.1+cu118, bf16. Eight training matches,
254 fixed windows, one epoch / 64 sampled steps, seed 6108. No heldout payloads
opened. This starts T7; it does not qualify the §5.1 gates.

| Measurement | Result |
|---|---:|
| Total parameters | 2,422,997 |
| Shared backbone / body heads | 2,086,560 / 40,762 |
| HUD / temporal event head | 78,729 / 216,946 |
| Training compute | 11.02 windows/s; 176.32 encoded frames/s |
| End-to-end training, including video decode | 1.282 windows/s |
| Mean sample loading | 672ms |
| 64-step wall time | 49.92s |
| CUDA peak allocated / reserved | 2,033.95 / 2,526MiB |
| Warm-cache CUDA frame+event invocation p50 / p95 | 7.03 / 7.35ms |

The compute rate includes optimizer steps; each window encodes sixteen 448x832
arena frames, even padded frames. Initialization affects the mean. The runtime
probe includes one current-frame encode plus a T16 head with repeated cached
features, but excludes decode, tracking, fusion and the emulator. It is a shape
throughput measurement, not video replay accuracy or a Mac budget pass. Video
decode currently dominates training wall time; no heavy work ran on 127x05.

The implementation is a compact CNN candidate, below all parameter ceilings,
with a shared stem for the ordered own-HUD atlas. It provides body identity/owner,
weak boxes, masked HP, own HUD, temporal heatmaps, age/sigma, top-three card mass,
cast-origin scores, calibrated existence probability and execution-time NMS.
History persists across gaps. High/low-confidence tracking requires two hits to
admit a body and retains last seen HP. Birth features are pixel-derived, with v3
spawner suppression in the streaming adapter. Integration with T5/P2 is still
required; `PixelPerception.step` provides the reference dictionary ABI.

Fifteen focused tests pass on 01: shape/parameter ceilings, masked-token invariance
(including NaN padding), irregular time sensitivity, gap history, execution-time
NMS, own-spell corroboration, isotonic monotonicity, phantom filtering/HP retention,
tiny joint overfit, pixel allowlist, runtime gap handling, body-label quarantine,
train/heldout isolation and refusal of incomplete Phase A admission (some tests
cover multiple properties). TorchScript frame and event stages reload with zero
max absolute eager difference in three test variants each. CoreML is planned,
not converted; no Mac operation occurred. See EXPORT.md.

## Label limitation

The eight-match audit contains 153,902 object rows: 108,210 have conservatively
consistent body identity, 19,473 have contradictory name/hint metadata, and only
3,911 have consistent identity plus explicit visible/nondeploying status.
Projectiles/non-hitpoint objects and contradictions are excluded from positives;
unknown visibility/identity regions are masked, not treated as background.
This is necessary given S2's board-precision finding. The collector is unchanged.
These weak native labels cannot certify board precision without a reviewed
annotation audit. PREREG-AMENDMENT-01 records the prospective training rule.

## Pending formal work

Phase A completion; complete-population fresh fitting; validation checkpoint,
threshold and isotonic selection with a source/checkpoint seal; a full v4 heldout
scorer and T5/S3/T8 contract integration; authorized Mac CoreML conversion and
emulator-on replay. Every §5.1 gate remains UNMEASURED/BLOCKED. RUNBOOK.md prepares
fail-closed formal fitting commands, not an automatic heldout evaluation.

Post-shakedown changes only improve completed-checkpoint recovery and stamp runtime
availability after fusion/serialization and normalize native body aliases before
v3 spawner suppression. Exact measured model/trainer sources
are retained under receipts/, with hashes matching the shakedown manifest.
