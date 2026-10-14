# Bot ExIt: expert iteration on the K4S search teacher (exploration tier)

Owner: bot lead. Exploration only: no prereg, no sealing. Code is in `bot/exit/`; progress is in
[PROGRESS.md](PROGRESS.md).

## Loop

```
student S_k ──plays──► games (our engine, HEADLINE match loop, pool: v1, R3a, S_k itself)
      ▲                    │ at every S_k root decision state
      │                    ▼
   GPU refit ◄── labels: K4S-b64 search on the SAME public state (its choice + its root scores)
      │
      └─► calibrate gate ─► HEADLINE-v1 eval (vs v1 and vs R3a, 300 cases, paired vs R3a)
```

## Components

**Match engine (pluggable).** `bot.exit.generate` calls `bot.players.ours.play_match`, the X4S loop from HEADLINE-v1.
The labeller is an ordinary `Player` (`bot/exit/label.py:LabelingPlayer`) wrapping two Players. RoyaleSim can
therefore swap in through `bot/players/royalesim_match.py:play_match` without touching the labeller. The planner
stays on `clasher_core` (the model-mismatch setting).

**Behavior.** The current student acts: DAgger with β = 0 by default. `--beta` executes the teacher's choice at
labelled states with probability β, using a domain-separated RNG.

**Teacher.** `SearchPlayer(mode='budget', budget=64, default='R3a')`, i.e. the HEADLINE candidate K4S-b64. It is
deterministic (virtual 64-rollout clock) and has one thread. It is fixed across iterations: its proposer and cutoff
default stay R3a, so labels from different iterations are comparable. It gets the same public views as the student,
and keeps its own belief, poller and RNG streams.

**Which states.** Every state where the teacher runs a root search:
- the student seat's channel is free and the tick is a multiple of 10 (the search cadence);
- there is more than one candidate.

These are ROOT decisions only. No poll-WAIT, timed-WAIT or pending-continuation rows are written: those
continuation rows made earlier students passive. Budget-cut roots (`teacher_hit`) are flagged and excluded from
training by default.

**Label.**
- The teacher's chosen root action (`teacher_search_action`, including the timed waits 2400–2402).
- `expert_actions` = that action, or WAIT for any wait.
- The teacher's complete candidate list with 3-style W-screen8 scores (`core.last`), stored as `root_actions`,
  `root_scores` and `root_valid`. This is exactly R3a's training-target format.

**Student inputs (fair information).** `exit_r3.rows.observation(reserved packet, student's v5 mask, student's D1)`.
This is the same public v5 packet plus event-derived D1 that the student reads when serving. The self-test checks
that the trainer's features equal the serving `single_features` bit for bit.

**Storage.** One sealed teacher-v6 shard per (game, labelled seat), via the frozen `exit_r3.rows.seal`. Shards are
packed with `imitation.exit_r1.pack` and read by the frozen `exit_r3.student.RootTeacherStore`.

**Seeds.** The training bank `TRAIN1 = 874184153281168` was drawn with `int.from_bytes(os.urandom(6),'big')<<4` at
2026-10-14T04:05:19Z. `generate.check_bank` refuses any overlap with HEADLINE `1455777415631152+[0,1e5)`.

Game g:
- uses `x4s_setup(g, TRAIN1)`: student seat g%2, X-deck g%5 vs X-deck (g//5)%5;
- plays opponent `pool[g % len(pool)]`;
- 'self' games label both seats.

The X decks are the HEADLINE decks; the seeds and shuffles are disjoint.

**Student architecture.**
- **Start:** R3a's SetPolicy (width 192, 4 layers, 2.28 M params), warm-started from R3a.pt (37509a43, EMA
  weights).
- **Wider option (2–4×):** `ModelConfig(width=384/ffn=1536)`. It cannot load R3a weights directly, so it needs
  from-scratch training on the union corpus (r1 + ExIt). It is deferred until the warm-start loop stops improving.

**Loss.** `exit_r3.student.teacher_loss` with T = 0.003, play weight 1 and per-batch denominators, i.e. R3a's
recipe. This is cross-entropy against the softmax of the teacher's complete root scores: gate (wait/play) plus
card plus tile, where timed waits fold into WAIT.

Training settings:
- AdamW at lr 1e-4, 100-step warmup then cosine, grad clip 1, batch 4096, EMA rate 0.01 per step (the EMA is what
  is served);
- optional mixing with R3a's own r1 root corpus (`exit-r2-20261010-r1/corpus`, 53 GB, read-only on 08) at
  `--new-ratio`, as a forgetting anchor.

**Threshold recalibration.** The gate is the calibrated threshold (sampling it costs about 26 pp, bot-gate-r1). The
threshold is set on held-out ExIt rows, a 5% game-hash split, with `proposals.calibrate`. It makes the student's
play rate on those student-visited root states equal the **teacher's** play rate there. It is written to
`<ckpt>.calibration.json`, so the checkpoint is directly usable as `student:<ckpt>`.

**Offline metrics (diagnostic only; stage-1 agreement does not predict strength).** On held-out rows: teacher-target
loss, gate accuracy, play recall/precision, top-1 on teacher plays, and full-decision agreement. Each is reported at
step 0, i.e. R3a at its own deployed threshold.

## Evaluation (decides everything)

The student is judged by HEADLINE-v1 (`bot.eval.headline`):
- it plays as `student:<ckpt>` against v1 and against R3a;
- 300 cases, i = 0…299 from the HEADLINE bank;
- score: win 1, draw 0.5.

**Paired vs R3a.** Per case i, Δ_i = score(student vs v1, i) − score(R3a vs v1, i). R3a vs v1 on the same cases
comes from our own run (deterministic given the seed). A 5,000-resample bootstrap over cases gives the 95% CI.

The direct head-to-head vs R3a is also reported. 0.5 = parity.

**Iteration.** Iterate (S_{k+1} = refit on all labels so far, plus new labels from S_k play) only if it helps.
