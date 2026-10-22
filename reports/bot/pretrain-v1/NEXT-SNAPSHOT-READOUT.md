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

The receipt owner completed both exact run/summary publications. The reviewed
05 expansion waiter admitted both anchors and launched the S100 expansion
controller PID 3741363. Its original 24-worker parent PID 3709397 is held at
case boundaries while the 64-worker pool runs. Per-case claims and sealed outputs
remain idempotent, with no failed-case replacement. It runs S100, then M.

Outputs are under
`/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022/next-snapshot/`.
Evidence/gates: `next-run-receipts-owner.json`, `next-run-receipts/{S100,M}`,
`next-expansion/S100-intent.json`, `S100-controller.json` and `S100-controller.log`.
Game results remain pending.
