# Pilot v7r3 recipe proposal

Status: drafted 2026-10-01 after the v7r2 second early checks (368,640 decisions).
APPROVED 2026-10-01 ~19:10Z in revised form (see "Approved form" at the end).

## Evidence (v7r2 second early checks, monitoring only)

| seed | script win rate, warm-start window | current window | bars |
|---|---|---|---|
| 2901 | 0.137 (16/117, Wilson 0.086-0.211) | 0.043 (3/69, Wilson 0.015-0.120) | win rate FAIL, wait OK |
| 2902 | 0.198 (n=111) | 0.093 (n=75, Wilson 0.046-0.180) | win rate FAIL, wait OK |
| 2903 | 0.214 (n=117) | 0.000 (0/109, Wilson 0.000-0.034) | win rate FAIL, wait OK |

Win rate vs the frozen warm-start mirror stays ~0.47 (no exploitation of the mirror either).
Drift direction differs by seed: 2901/2902 wait less and narrow onto 1-3 cost cards
(entropy_collapse_card); 2903 goes passive (wait 0.98, plays/match 49 -> 28).
Per-update KL is small (0.003-0.01, KL early stop hit every update), yet the drift is systematic
over 25 actor updates: the advantage signal is biased, not just noisy.

## Diagnosis

* Credit horizon. gamma 1.0 with GAE lambda 0.95 gives a ~20-decision (~5 s) credit window on
  ~1,200-decision matches. Beyond that window the advantage relies on the critic, whose
  explained variance is weak on some seeds (s2901 ev +0.16 at update 36; s2903 +0.67).
  Within it, the objective-v1 tower potential (scale 0.05) dominates: immediate chip is credited,
  the counterpush that follows 10-20 s later mostly is not.
* No restoring force. anchor_policy_kl_coef is 0, so nothing keeps the actor near the warm start
  while the critic is still poor.
* The warm start itself is weak (0.14-0.20 vs the scripts it imitated) and cheap-card biased
  (4-cost play-when-held ~9%, 5-cost ~1.5%).

## Proposed changes (training-only modules; ADMISSION_BOUND scope unchanged)

1. gae_lambda 0.95 -> 0.99 (credit window ~100 decisions ~ 25 s).
2. anchor_policy_kl_coef 0 -> 0.05, anchored to the scripted warm start (trainer already implements
   policy_anchor_kl; council_pilot currently pins 0). Scratch arm keeps 0 (no anchor exists).
3. critic_warmup_updates 20 -> 60 for the scripted arm (ev should be well above the current
   +0.16 before the actor moves).
4. Keep factorized-v2 entropy, target_kl 0.02, lr 1e-4, the opponent pool and the early-check bars.
   Add a third check at 532,480 decisions.

Implementation: Literal pins in src/clasher/rl/council_pilot.py (gae_lambda, critic_warmup_updates,
new anchor field + recipe id), a pilot-runtime-v3 snapshot, new kit pilot/v7r3-launch. v7r2 runs are
kept as evidence with a stopped-for-recipe-fix.json.

## Alternative / follow-on

Improve the warm start instead of (or as well as) PPO: human-prior pre-train from IL_Replay
(m0/human-prior-scan; 6,386 matches at the 66-card set, 262 at the 16 pilot cards).

## Approved form (user decision, 2026-10-01)

The 1M diagnostics arrived after the first approval: s2903 won 46/96 holdout games vs
scripts (warm start 19/96) after failing its 368k early check; s2901 9/96, s2902 0/96.
The user then chose to run both in parallel:

* (a) pilot/v7r2c-launch: continue s2903 from its v7r2 1M checkpoint
  (sha c7aae667...), v7r2 recipe, weights only, level 11, then nominal-league to 5M.
* (b) pilot/v7r3-launch: 3 seeds, lambda 0.99, critic warm-up 60, anchor KL **0.01**
  (not 0.05: a strong anchor might block the kind of move s2903 made), nominal-league
  to 5M at level 11. Early checks are report-only, never stop signals.
