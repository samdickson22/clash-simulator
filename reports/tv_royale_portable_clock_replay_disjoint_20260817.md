# Portable clock replay-disjoint audit — 2026-08-17

## Decision

The frozen portable clock provider **does not pass the replay-disjoint expansion
gate**. It remains valid for the exact retained 1182x2560 H200 smoke source, but
886x1920 and 888x1920 native layouts remain fail-closed. No templates were
retrained and no provider threshold was tuned on this canary.

The audit used all 120 already-retained JPEG frames from ten different YouTube
replays. No download or network operation occurred. Each low-resolution
format-18 frame was hash-verified, its clock crop was isolated and explicitly
normalized from 296x640 retained geometry to a 230x192 clock crop, and the
frozen provider was run current-frame-only. An independently compiled macOS
Vision accurate-text reader supplied teacher labels only when it found an exact
`d:dd` timestamp with confidence at least 0.8.

## Overall result

| Metric | Result |
|---|---:|
| Retained frames | 120 |
| Confident Vision teacher labels | 108/120 (90.000%) |
| Portable accepted given teacher | 88/108 (81.481%) |
| Exact portable labels | 87/88 (98.864%) |
| Replay-disjoint mismatches | 1 |

The gate required at least 99% conditional exact accuracy. One low-resolution
red `0:09` frame from `Xf8Y9GdxlLo` was incorrectly accepted as `0:00` at
portable confidence 0.2475. Visual inspection confirms the teacher is correct;
this is not an annotation ambiguity.

## Native-layout provenance

The native dimensions below come from the sanitized channel metadata. The
retained pixels are all explicit 296x640 format-18 frames, so this is a domain
audit by replay and native-layout provenance—not direct proof that the current
provider handles native 886/888 pixel geometry.

| Native source layout | Frames | Teacher | Joint accepted | Exact / joint |
|---|---:|---:|---:|---:|
| 1182x2560 | 36 | 28 | 28 | 28/28 (100%) |
| 886x1920 | 60 | 56 | 55 | 55/55 (100%) |
| 888x1920 | 24 | 24 | 5 | 4/5 (80%) |

The 888x1920 provenance group is clearly not ready: only 5/24 teacher-labelled
retained frames were accepted and one was wrong. Silently scaling those native
layouts into the existing production provider would therefore be unjustified.
The 886x1920 group is promising but still requires direct native-resolution
held-out evidence before adding an explicit production geometry version.

## Reproducibility

- frozen provider SHA-256:
  `8c98ebffdf20689db8ec33e79e5f9f5e200a92d1fc1982bdf4f08a2a5fd0e910`;
- audit source SHA-256:
  `3e97973ea491b9d1a11367a51fcb9220f91aad6510e1ecc48f6d49668c3edc91`;
- report JSON SHA-256:
  `f50e46bd3f60cd3b101dfaa82083a90146ec6f5fd4a2fa56393f87e49c1079a1`;
- frame audit JSONL SHA-256:
  `6ee727a1b40f40e564de6f1da96cc311ad11617b9bfd44fc430e3478019f7d54`;
- mismatch visual SHA-256:
  `25ae4ab004042160ce4664fd81fb704458713ee0525f6872217a110ba15b51ee`.

Two complete executions produced byte-identical stdout, JSON report, frame
audit, and mismatch visual. The correct next step is to run the exact
1182x2560 H200 smoke as planned while retaining fail-closed behavior for the
other layouts. Native-resolution replay-disjoint sections—not threshold tuning
on these 120 evaluation frames—should gate any later layout expansion.
