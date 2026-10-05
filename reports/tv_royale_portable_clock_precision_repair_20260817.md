# Portable clock precision repair — 2026-08-17

## Decision

Accept the precision repair for the exact 1182x2560 H200 smoke. Keep native
886x1920 and 888x1920 expansion blocked.

The provider now rejects any prediction whose minimum per-digit normalized
nearest-template margin falls below `0.5560975423673304`. This boundary is the
minimum confidence observed among all 535 exact teacher-aligned anchors on the
original 1182x2560 calibration source. The replay-disjoint labels were not used
to choose or move the threshold.

## Why the rule is principled

The confidence is not an arbitrary model probability. For each digit it is

`(second_best_distance - best_distance) / second_best_distance`.

The clock confidence is the minimum across its three digits. A value below the
minimum clean calibration support is therefore treated as an out-of-support
template match and omitted. This is intentionally an abstention rule, not a
correction or temporal heuristic; every frame remains independent.

Original exact-source normalized-margin distribution:

- count: 535;
- minimum: 0.556098;
- 1st percentile: 0.677249;
- 5th percentile: 0.740260;
- median: 0.907950;
- 95th percentile: 0.972603;
- maximum: 0.996109.

The one replay-disjoint false acceptance had margin 0.247500, outside clean
calibration support. Correct disjoint predictions before repair ranged from
0.179558 to 0.750973, showing why the repair necessarily trades low-resolution
coverage for precision.

## Evidence

| Gate | Before | Repaired |
|---|---:|---:|
| Exact-source anchors | 535 | 535 |
| Exact-source anchor SHA-256 | `5495aead…9336f482` | `5495aead…9336f482` |
| Replay teacher labels | 108 | 108 |
| Replay accepted | 88 | 57 |
| Replay exact | 87/88 (98.864%) | 57/57 (100%) |
| Teacher-conditioned replay coverage | 81.481% | 52.778% |
| Replay false acceptances | 1 | 0 |

The repaired output on the exact source is byte-identical to v1, so its smoke
semantic hash and 2,675/3,204 merged clock-frame publication are preserved.
The provider still hard-rejects source video dimensions other than 1182x2560.
The normalized retained-frame audit is evidence about replay diversity only;
it does not enable native 886/888 layouts.

Fifty-seven accepted labels across the ten-replay canary provide useful
precision evidence, but not a 99.5% statistical lower confidence bound. The
claim is the observed accepted accuracy (100%), not population-level proof.
Additional untouched native-resolution videos are required before reducing the
support floor or enabling another layout.

## Pins and hashes

- repaired provider:
  `/Users/sam/Desktop/code/clasher/tools/recognize_public_clock.py`;
- provider SHA-256:
  `fd4975980ee960e98d490b5bab8d84ee3999c8c7278cc8421051b9ec15fba5a7`;
- exact-source verification SHA-256:
  `2bc902b79405e350204a3b979893656091b0509c341f4628a40200901355698a`;
- precision repair report SHA-256:
  `7ac656cd9b09fd2d16740d248f1e4ba644d8edda0dfa408778fd22475b149916`;
- repaired replay frame audit SHA-256:
  `ec0264f9737ae4172fc7890ebf3d59e39d725342771b4eea56c5f2ff86b2fa61`.
- packaged exact-source anchor SHA-256:
  `5495aead8db5290c7c4eba9e5c366b64fee76fedc4ea6f59c240d42d9336f482`;
- packaged merged manifest SHA-256:
  `96a386c17f3c1066437e159c8fafc6ef76c5d0786e88a8d36b262399c510a803`;
- CUDA pins SHA-256:
  `76a6e326d63ea119dbd4c9e6d6cc1309d33dd1893c53be1a39de33e7ffcc740c`.

The H200 ready pins must use the repaired provider SHA above; the original v1
provider SHA is obsolete for new smoke attempts even though its anchor output
is identical.
