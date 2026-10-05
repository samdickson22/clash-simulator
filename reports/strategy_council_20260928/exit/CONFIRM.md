# Proposal-network confirmation

Preregistered in PREREG-CONFIRM.md. Intervals resample complete matchup pairs.

## Confirmation: FAIL

Student search head-to-head: 123/256 = 0.480469, 95% CI [0.425781, 0.531250]
Primary gate: False; required script gate: True.
H2H hog26: 38/86 = 0.441860, 95% CI [0.337209, 0.546512]
H2H holdout: 85/170 = 0.500000, 95% CI [0.441176, 0.558824]

hog26 scripts, previous: 30/64 = 0.468750, 95% CI [0.343750, 0.593750]
hog26 scripts, student: 31/64 = 0.484375, 95% CI [0.359375, 0.609766]
Paired drop, previous minus student: -0.015625, 95% CI [-0.125000, 0.109375].
balanced: previous 12/22, student 13/22.
defense: previous 6/20, student 6/20.
pressure: previous 12/22, student 12/22.

holdout scripts, previous: 102/128 = 0.796875, 95% CI [0.703125, 0.882812]
holdout scripts, student: 104/128 = 0.812500, 95% CI [0.726562, 0.890625]
Paired drop, previous minus student: -0.015625, 95% CI [-0.078125, 0.046875].
balanced: previous 37/44, student 33/44.
defense: previous 28/42, student 31/42.
pressure: previous 37/42, student 40/42.

All 640 planned games included. Candidate rejected plays: 0. Maximum measured candidate decision wall time: 0.098129s. Timing does not include the opposing H2H planner.

Policy-alone is descriptive and was not rerun: initial 83/192, iteration-1 student 64/192; Hog26 32/96 and 18/96.

Recommended proposer: /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt

Stopped at the first failed gate. No later iteration is authorized by this protocol. Retain the last accepted proposer; consider a separately preregistered change before another experiment.

## Final audit

All 640 scheduled receipts are present, unique and bound to the frozen source and
checkpoint hashes. The 128 H2H pairs preserve world decks and swap controller
seats. All 192 script games match across proposers by style, seed, seat and decks.
All three workers exited 0; driver and worker PIDs have exited. No iteration 2 or
3 artifacts exist. Total exit storage is about 40.5 MB. See confirm/final-audit.json.

The prior 39/64 signal did not meet the confirmation gate. This result does not
establish that the student is worse as a proposer; the primary interval includes
0.50. The confirmation also follows the requested one-third Hog26 and
development/training deck protocol, while the exploratory exit test used half
Hog26 and symmetric holdout decks. Both protocols are retained for interpretation.
