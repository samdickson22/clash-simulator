# Hog 2.6 strategy-majority curriculum — seed 1075001

This phase keeps the learner deck fixed to Hog 2.6 while sampling opponent
decks from the strict card-balanced training pool. Ten of twelve actor slots
use PFSP-weighted public-information strategy bots; the remaining slots use a
stationary random opponent and the frozen update-46 parent. Human causal
rehearsal remains active. Additional learner decks stay locked.

## Parent

- Checkpoint: `checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`
- Matched random seed 1071001: 8-4, +0.833 crowns/game.
- Matched direct-policy seed 1071003: 10-2, +1.417 crowns/game.
- Six-strategy seed 1071002: 3 wins, 20 losses, 1 draw; mean score 0.1458.

## Update 56 milestone

- Random: 8-4, +0.917 crowns/game; no regression.
- Direct policy: 10-2, +1.250 crowns/game; win floor preserved.
- Six strategies: 1 win, 23 losses; mean score 0.0417.
- Decision: **not promotable** because strategy performance regressed.

Training continues to the predeclared update-66 milestone. The milestone
watcher also evaluates updates 86, 106, 126, and 146. A later checkpoint must
preserve the parent random/direct floors and materially improve the
per-strategy result before it can replace update 46.

The earlier reward A/B (`reports/fresh_f1_reward_screen_seed1067101`) already
tested gamma-correct potential shaping and did not promote it, so this phase
does not change reward semantics mid-run.
