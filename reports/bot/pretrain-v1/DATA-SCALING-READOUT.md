# Data scaling read

Updated from the atomic reader at 2026-10-22T09:22:45.363063+00:00. Five of six selected points are available; M25 is still training.

The frozen snapshot has 19,410 usable matches and 3,902,495 rows. Each fraction uses the same match-held-out DEV population: 379,752 rows, including 244,125 actor rows and 79,072 commands, across 1,887 physical matches. Hog metrics cover 78 physical DEV matches. Training fractions select donor perspectives, so exact row proportions vary slightly.

| Size/fraction | Train rows | Donors | Broad NLL | Hog NLL | Card top-1 | Tile within 1 | ECE | Value Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S25 | 784,048 | 7,752 | 0.384250 | 0.514621 | 0.515100 | 0.318760 | 0.002767 | 0.597703 |
| S50 | 1,565,207 | 15,504 | 0.370990 | 0.507610 | 0.556468 | 0.359988 | 0.005819 | 0.608505 |
| S100 | 3,124,681 | 31,008 | 0.358235 | 0.509618 | 0.579889 | 0.400812 | 0.006309 | 0.561030 |
| M25 | pending | pending | pending | pending | pending | pending | pending | pending |
| M50 | 1,565,207 | 15,504 | 0.364624 | 0.564444 | 0.575981 | 0.398295 | 0.013132 | 0.614383 |
| M100 | 3,124,681 | 31,008 | 0.347816 | 0.523859 | 0.601389 | 0.439448 | 0.006352 | 0.588279 |

More training data improves broad NLL and placement accuracy over these observed intervals. S100 improves broad NLL by 0.026015 over S25. M100 improves it by 0.016808 over M50. This supports continuing the larger-snapshot comparison; it does not establish that data is the sole limit. Hog NLL and value calibration are not monotonic across all fractions. M25 is needed to complete the larger model curve.

Fraction runs preserve the registered nominal optimizer-step budget by increasing passes on smaller subsets, with checkpoint selection and early stopping. They are not equal-pass experiments. The immutable run receipts and selected-checkpoint hashes remain the source of truth.

The separate 1,600-case game comparison passes the registered M preference rule. See [the power readout](POWER-READOUT.md). No size default or deployment was changed. The next frozen snapshot has 41,328 usable matches and 8,143,577 rows; its S100/M100 retrains are running on 02/01 respectively.

## Selected checkpoints

- S25, epoch 3: `e72411434a666a5237ecd531d7620fbc455063656695470a0680a2eed3ddfcf7`.
- S50, epoch 3: `13488264e9ccdd11be634cc21cd3b3232c6239d601cd701132c79ea935235447`.
- S100, epoch 3: `e9366c55503f3d826fa6add0beb9880883be9274158e728f03f932dcd19acbc7`.
- M100, epoch 4: `caa5f58ff250fdd689734ad80eb426e654ab4828ff4b08e655df7265e8486f7e`.
- M50, epoch 5: `b9e2acb2e715aab6c77abe0224595d4de9e0e0d6b84dd2f032c6a1e7bb86509c`.

Atomic reader source: `/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022/scaling-read.json`. Captured JSON SHA256: `35d379e04ded75c39a58123579f5aeba862411acb014756309dccbaf1225c905`.
