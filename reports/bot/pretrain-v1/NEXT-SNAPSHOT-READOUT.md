# Next-snapshot BC selection and game comparison

Both sizes are admitted on the 41,328-match, 8,143,577-row snapshot. Full DEV is
4,080 physical matches with 515,173 actor rows and 163,009 plays, including 153
Hog matches. These metrics use the expanded DEV set; they are separate from the
controlled 25/50/100% read on the prior snapshot. The registered game rule chooses
the preferred size. No size/default or deployment decision is made here.

| Size | Epoch | Broad NLL | Hog NLL | Card top-1 | Tile within one | ECE | Value Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| S100 | 3 | 0.336666 | 0.469532 | 0.601224 | 0.440264 | 0.005477 | 0.561125 |
| M | 4 | 0.328198 | 0.515936 | 0.624880 | 0.475606 | 0.005127 | 0.572595 |

Selected file SHA256 values:

- S100: `74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f`
- M: `947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4`

M has lower broad NLL and higher card/tile accuracy. S100 has lower Hog NLL and
value Brier. These losses do not decide the game comparison. Both-arm evaluation
uses the frozen fresh 1,600-case bank and unchanged paired accounting.

The receipt owner completed both exact run/summary publications. Both reviewed 64-worker expansions on 05
finished all 1,600 assigned cases per size. No failures were replaced or retried. The original owners and
frozen scientific runtime were preserved. Results are separate from the prior 400-case and 1,600-case banks.

## Final fresh-bank game comparison

Bank SHA256 is `10c24cd429416344d6ee69342bc6317a2c90387bb73a97eb38c9dbf4cf30a276`.
There are 1,591 complete pairs and nine common R3a failure cases. The registered equally weighted LIVE/R3a
paired score difference M minus S100 is **+16.2107 percentage points**, 95% CI **[+13.3666, +19.1365]**.
The conservative all-assigned lower estimate is **+15.5625 points**, CI **[+12.6563, +18.4688]** across all
1,600 assignments. Both registered preference conditions pass. M is preferred by the registered game rule;
Sam retains the model/default and deployment decision. Both sizes still have their approved RL stage.

| Opponent | S100 wins / valid | S100 draws | M wins / valid | M draws | Assigned per arm |
|---|---:|---:|---:|---:|---:|
| Current LIVE bot | 348 / 800 | 1 | 486 / 800 | 0 | 800 |
| R3a | 414 / 791 | 1 | 535 / 791 | 0 | 800 |

Against the current live bot the win rates are **43.5% S100** and **60.75% M**. The registered pooled statistic
uses game score, with draws worth one half, and fixed 50/50 controller weights. Its delta is not a pooled win-rate
delta. The nine failed indices are 857, 938, 1217, 1264, 1305, 1309, 1476, 1520 and 1542 in both arms.
They are separately recorded opponent execution errors and remain failures in all-assigned bounds.

Operational rejected taps are separate. S100 has **22 / 53,094 executed taps, 0.041436%**, M has
**19 / 60,104, 0.031612%**. S100's rejected taps are 21 Cannon and one Skeletons; M's 19 are all Cannon.
The sidecars preserve all assignments and the nine other failures per arm. Terminal pending taps,
328 S100 and 386 M, do not enter executed-rejection denominators. See [OPERATIONAL-REJECTIONS.md](OPERATIONAL-REJECTIONS.md).

Outputs and immutable rows are under
`/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022/next-snapshot/`.
The registered comparison is `followup-20261022/comparison-next-snapshot.json`; expansion completion receipts are
`next-expansion/{S100,M}-complete.json`. Read-only, hash-bound sidecars and independent outcome counts are in
`rl-readiness/rejection-amendment-20261022/`. No RL, precision adoption or deployment follows automatically.
