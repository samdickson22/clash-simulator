# Portable TV Royale clock pin — 2026-08-17

## Decision

The exact retained 1182x2560 YouTube source passes the predeclared portable
clock gate. The provider is suitable for the single-video H100/H200 smoke. It
is **not** yet a bulk-channel compatibility claim: other resolutions, HUD
layouts, or game themes fail closed until separately calibrated and held out.

## Provider

- executable: `/Users/sam/Desktop/code/clasher/tools/recognize_public_clock.py`
- SHA-256: `8c98ebffdf20689db8ec33e79e5f9f5e200a92d1fc1982bdf4f08a2a5fd0e910`
- implementation: deterministic OpenCV digit segmentation plus ten embedded
  calibration templates;
- state: none; each anchor uses only its current decoded frame;
- dependencies: the project Python environment, NumPy, OpenCV, and FFmpeg;
- output: schema `clasher.youtube.clock_anchor.v1` JSONL;
- uncertainty behavior: ambiguous segmentation/classification emits no row.

The ten digit templates were fit outside five fixed, contiguous held-out
blocks: 30–45 s, 90–105 s, 150–165 s, 210–225 s, and 270–285 s. This avoids
frame-adjacent random leakage while ensuring the held-out timestamps must be
composed from digit concepts rather than memorized as 600 independent labels.

## Exact evidence

| Partition | Teacher anchors | Accepted | Coverage | Exact / accepted |
|---|---:|---:|---:|---:|
| Calibration | 475 | 415 | 87.368% | 415/415 (100%) |
| Untouched temporal holdout | 148 | 120 | 81.081% | 120/120 (100%) |
| All | 623 | 535 | 85.875% | 535/535 (100%) |

- monotonic violations across every published anchor: 0;
- source duration: 320.353 s;
- full provider wall time including FFmpeg decode: 16.36 s (20.12x realtime);
- isolated recognizer latency measured during the calibration build: 0.164 ms
  per anchor;
- published anchor SHA-256:
  `5495aead8db5290c7c4eba9e5c366b64fee76fedc4ea6f59c240d42d9336f482`;
- exact launcher merger publication: 2,675/3,204 clock-valid 10 Hz frames
  (83.489%); merged manifest SHA-256
  `03beef99cd1748a4f5257bcee2c58c756f10580502802446afeb7e01c9f3c5f1`;
- machine-readable verification report SHA-256:
  `d85e9c88d9af93903ff284ad8c1cbdc94249ac3417aed29f20948959b6cda5aa`.

All six verification gates passed. Ruff and mypy are clean for the three new
programs; the provider/merger focused gate is 5 passed.

## Fail-closed boundary

Version 1 intentionally rejects any source geometry other than 1182x2560.
Within the supported video it omits clock-transition frames, uncertain digits,
and the red final `0:00` styling rather than guessing. Within-stride propagation
is performed later by the already pinned merger, never by this recognizer.

The next H200 operation should therefore be the exact one-video smoke. Before a
bulk wave, run a separate multi-video, multi-arena/theme compatibility gate and
add explicitly calibrated layout variants only when each has its own untouched
holdout evidence.
