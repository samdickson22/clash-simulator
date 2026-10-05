# v7r2c seed 2903 continuation: 2M checkpoint (coordinator, 2026-10-03)

Chain stopped at the 2M checkpoint (policy_decisions_002000000.pt, sha256 prefix 339fb1058c1eb00c) by
pilot/stop_s2903_at_2m.sh at 06:38Z; resumable from that checkpoint with the kit's launch.sh.

Scored with human-prior-p16/scripts/run_eval.py (fresh seeds, base 770031; 6 cells x 32 games), paired with
the earlier rows (human-prior-p16/evaluation/).

| Checkpoint | Holdout wins /96 | hog26 wins /96 |
|---|---|---|
| scripted warm start | 14 | 9 |
| v7r2 1M | 38 | 5 |
| **v7r2 2M** | **20** | **0** |
| human-bc-natural | 22 | 18 |

Paired exact McNemar, 2M vs 1M: holdout 4 vs 22 discordant wins (p=0.001), hog26 0 vs 5 (p=0.06), all 192
games 4 vs 27 (p<0.001). 2M vs human clone: holdout p=0.85, hog26 0 vs 18 (p<0.001). 2M vs scripted warm start
overall p=0.72. Crowns in the balanced cells: holdout 16 for / 68 against (1M: 17/27); hog26 0/88 (1M: 6/46);
median game length fell from ~3600-4300 to ~2200 ticks (2M is three-crowned early).

Reading: the second million (the nominal-league phase, mostly self-play against its own past checkpoints)
erased the 1M gain and is now no better than the scripted warm start; the training win rate against scripts
kept rising meanwhile, so training metrics did not detect it. v7r4h uses the same league phase after 1M
(with a KL anchor 0.05 to the human prior): watch its 2M/3M cells against this failure.
