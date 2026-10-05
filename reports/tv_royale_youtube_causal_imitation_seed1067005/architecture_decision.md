# YouTube causal imitation architecture decision — seed 1067005

## Decision

Retain `oracle_gate_f1_clock1500.pt` as the outcome-RL parent. Reject the human
timing gate, the full equivariant pointer replacement, and every tested
mechanics-query blend. The negative candidates remain useful quarantine evidence;
none may be silently stacked into the next lineage.

This is not a checkpoint promotion and does not claim human skill. It selects the
least-damaged initializer for a consequence-based reward/PFSP experiment.

## Evidence

The causal corpus contains 52 replay groups and 139,646 recurrent rows. Only
1,205 rows carry complete trusted human card-and-tile play supervision; waits and
unsupervised context dominate. On 32 complete recurrent episodes, the parent
deterministically played on 75.79% of evaluated frames while the human play rate
was 1.21%. Its play ranking was worse than random (`ROC-AUC=0.4403`,
`AP=1.01%`). Training the play/wait gate on this sparse camera label process did
not produce a calibrated decision rule and is rejected.

Training the shared equivariant card pointer did improve conditional card choice
from 22.69% to 54.62% and played-card accuracy from 11.76% to 31.09%. However,
the complete replacement changed 5,675/9,843 deterministic actions and regressed
the matched six-strategy development screen from 10-2 with +4 crowns to 8-4 with
+1 crown. Offline card accuracy did not transfer safely to free-running play.

A mass-preserving mechanics-query blend kept the parent's play timing fixed.
Alpha 0.25 and 0.50 improved conditional human card accuracy to 28.57% and
39.50%, respectively, but both regressed the same gameplay screen to 9-3 with
+2 crowns; the balanced matchup flipped from a win to a loss. Smaller alphas
0.10 and 0.15 changed 79 and 173 deterministic actions but improved neither
conditional card accuracy (22.69%) nor played-card accuracy (11.76%). They were
rejected without another gameplay screen to avoid tuning against the same twelve
games.

## Consequence

Human video remains valuable for observation realism, causal state construction,
card identity supervision, and no-regression diagnostics. It is not a trustworthy
standalone teacher for action timing because unobserved/censored plays and sparse
positive events distort the frame-level wait/play target. The next skill update
therefore learns timing and card consequences from complete simulator outcomes,
with frozen-policy KL and simulator-native rehearsal protecting the causal actor.

The next experiment is predeclared in
`reports/fresh_f1_reward_screen_seed1067101/plan.md`: legacy reward shaping versus
gamma-correct potential shaping versus gamma-correct shaping with elixir leak
disabled. Architecture, decks, opponents, seed, optimizer, and transition count
remain matched.

## Outcome-PPO closure

The predeclared reward screen and one fresh-seed replication are now complete.
The first development seed scored parent 14-22, legacy 15-21, gamma-correct
14-22, and gamma-correct/no-leak 13-23. Legacy did win 8-4 versus random and 7-5
head-to-head, but gained only one broad win and regressed spell-control from four
wins to two. Gamma-correct lost 4-8 head-to-head and increased camera overplay;
no-leak lost 5-7 head-to-head.

The only promising arm, legacy, was repeated from the immutable parent with a new
training seed and new matchup seeds. It scored 14-22 versus the same-seed
parent's 16-20. Across both seeds, legacy totaled 29-43 versus parent 30-42: a
combined broad change of -1 win. Both training runs were numerically stable, so
the failure is behavioral rather than an optimizer crash.

The F1 outcome-PPO continuation is rejected. No held-out deck or archetype gate
was opened, and neither update-20 checkpoint may seed the next lineage. The
replacement is a fresh F3 hierarchical/equivariant policy trained first on
complete simulator trajectories, with human video kept out of frame-level
timing optimization.

## Bound evidence

- parent SHA-256: `55eb6c5babcb809c853e0db7f7dc9677f60c94f636540c55d4a54a49cf1d1a87`
- causal corpus SHA-256: `986dcd7c7768dbcd39b93185ffe22333e8cc9aa8b9ce7b6ab4a7614c6055647d`
- public sidecar SHA-256: `66fca7413795f4233a9f1b032262bc1b671ab12277c29ab6a5689a5d278ec9d2`
- full pointer SHA-256: `afffa42ddb8e37d41d9c223697990d4e223a21c757e1ebd4fda279c65aa705ca`
- alpha 0.25 SHA-256: `b7458407cf357dec5918af35571e66e578c38f0c1772c1b22854117228960cc2`
- alpha 0.50 SHA-256: `892ca59bac1bddff7e36d7f3a8f6482e9e0de7df6804295f959c96e4049a94df`
- alpha 0.10 SHA-256: `54529e2d3cc01069e38149e4ba2dabf590b7d679f0d9796aa400338ce20b7f54`
- alpha 0.15 SHA-256: `26557bcd577cdf48daa5e1a273046c8e38fccf2a34e31876a873c2f8a5beff89`
