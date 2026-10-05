# v7r4h (PPO from the human prior, KL anchor 0.05): 1M results (coordinator, 2026-10-03)

Fresh-seed paired cells (human-prior-p16/scripts/run_eval.py, seed base 770031, 6 cells x 32 games; engine and
eval code identical in runtimes v4 and v5):

| Checkpoint | Holdout /96 | hog26 /96 | Total /192 |
|---|---|---|---|
| scripted warm start s2903 | 14 | 9 | 23 |
| human-bc-natural (v7r4h start) | 22 | 18 | 40 |
| v7r2 1M s2903 | 38 | 5 | 43 |
| v7r2 2M s2903 (league collapse) | 20 | 0 | 20 |
| **v7r4h 1M s2901** | 29 | 31 | **60** |
| **v7r4h 1M s2902** | 42 | 46 | **88** |

Exact McNemar on identical games: s2902 vs human start 57 vs 9 (p<0.0001; holdout p=0.0008, hog26 p<0.0001);
s2901 vs human start 41 vs 21 (p=0.015); s2902 vs v7r2 1M 60 vs 15 (p<0.0001; holdout n.s., hog26 44 vs 3).
On the runs' own diagnostic seeds (vs the human start on the same games): s2901 76 vs 31, s2902 86 vs 31 /192.

Reading: PPO from the human prior keeps the deployment-deck (hog26) skill the scripted-start run lost, and
s2902 at 1M is the strongest policy so far on both slices. Seeds differ a lot (60 vs 88). s2902 1M is the
default student for the srp DAgger kit. Seeds 2901/2902 continue to 2M only (anchored league test).

## 2M (league phase 1M -> 2M, anchored), fresh-seed paired cells

| Checkpoint | Holdout /96 | hog26 /96 | Total /192 |
|---|---|---|---|
| v7r4h 1M s2901 | 29 | 31 | 60 |
| v7r4h 2M s2901 | 36 | 43 | 79 |
| v7r4h 1M s2902 | 42 | 46 | 88 |
| v7r4h 2M s2902 | 34 | 25 | 59 |

McNemar 2M vs 1M: s2901 48 vs 29 (p=0.04, up); s2902 22 vs 51 (p=0.0009, down; hog26 11 vs 32, p=0.002).
Reading: the KL anchor prevents the v7r2c-style collapse to scripted level, but the league phase as configured
moves seeds in opposite directions — not a dependable improver. Decision: no further league training in this
form; checkpoints are selected by fresh-seed evaluation (s2902 1M remains best, 88/192); improvement continues
through search-teacher distillation (srp-dagger) and later C56 human BC + PPO to 1M.
