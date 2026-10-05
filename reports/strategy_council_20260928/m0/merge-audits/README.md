# Merge-plan audits and pilot hygiene (items 4 to 8)

Date: 2026-09-28. Source: `reports/external_review_20260928/merge-plan.md`. There was no gameplay fitting. The only optimizer runs were synthetic tests on tiny models over 100-tick rollouts, run in pytest temporary directories, and no weights were kept.

## 4a. Half-tile lattice audit

Script: `lattice_audit.py`. Output: `lattice-audit.json`, SHA-256 `eccf70cc…6cee`. The script is read-only and takes about 18 s.

| Source | Placements | Tile centre (x.5, y.5) | Tile corner (integer) | Other |
|---|---|---|---|---|
| Native development commands (all `native-prefix-development-v2*` episodes) | 262 | 262 | 0 | 0 |
| IL_Replay human shard 0 (SHA `9f612709…b656`, 5,000 replays) | 365,362 | 356,792 | 8,570 | 0 |

Notes on each source:

- **Native commands.** We submitted these through our tile-centre action space, so they say nothing about native preference. Eight of the commands come from the partial artifacts of the interrupted claim `-remaining/episode-11`. Its frame stream is truncated, so it was read only up to the break. That claim is still an interrupted failure.
- **Native building objects.** This is the informative native result. After a Tesla command at a tile centre, the native Tesla object always appears on a tile corner (8/8). For example, a command at (7500, 21500) produced an object at (7000, 21000). The Cannon object always sits on a tile centre (14/14). `clasher.placement.building_anchor` predicted all 22 anchors exactly.
- **Human placements.** Every human corner placement belongs to a 2×2 card: Tesla (5,587 of 5,587 corners) or the out-of-scope Goblin Drill (2,983). Cannon has 8,638 plays, all on tile centres. Its collision radius is 0.6, so its placement footprint is 3 tiles, which is odd, and it anchors on tile centres. The external review's statement that Cannon is 2×2 does not hold for our pinned data. Among the 16 pilot cards, Tesla is the only even-footprint card.
- **Round trip.** I sent 122,290 in-scope human plays through the path: world → our 576-tile action → tile centre → `building_anchor`. All 122,290 reproduced the recorded coordinate to within 1 unit, and all 5,587 Tesla corners were reproduced. The result is the same whether the coordinate is floored directly or first rounded to the 500-unit lattice. A human adapter should still round to the 500-unit lattice before flooring, as a guard against 999/1 jitter.
- **KataCR.** Its card ids are numeric detector classes and its xy values are noisy camera estimates, so it cannot resolve the half-tile lattice. I excluded it. TV-Royale positions are vision-marker estimates whose identities are unconfirmed; I noted them but did not use them.

**Recommendation: do not add the optional sub-tile residual for the 16-card pilot.** The game itself quantizes placements to the half-tile lattice. Point and odd-footprint cards land on tile centres, and even-footprint buildings land on corners. The flooring anchor maps each corner one-to-one onto a tile-centre action. Projection therefore does not change any observed useful choice. Revisit this only if the scope adds even-footprint cards whose native anchor rule differs from `building_anchor`. Each such card needs its own native anchor check, like the Tesla check here.

## 4b. Wait-row off-by-one (ClashAI R8)

`scripted_demonstrations.collect_public_script_game` builds both public packets before `env.step`, then stores the pre-step observation, the mask and the label on the same row. The terminal row is context only (`valid=False`), and `previous_actions` is the label shifted by one row. `council_warmstart` and `imitation._sequence_batch_inputs` index hands and labels by the same row indices, with no roll or shift.

The new test `tests/test_scripted_demo_wait_rows.py` drives the real collector and engine from both seats for a bounded 240-decision prefix. It records each seat's hand just before every step and the card that actually leaves the hand during that step. It asserts four things:

- every row carries the pre-decision hand;
- each accepted placement's labelled slot is the card the engine deployed;
- no supervised wait row coincides with a deployment;
- the supervised batch keeps rows, hands and labels aligned.

A negative control shifts hands by one row, which is the ClashAI failure mode, and the checker flags it. **The bug is not present, so there was nothing to fix.**

## Items 5–8 (implemented in source)

- **5. Critic warm-up**, scripted arm only: `critic_warmup_updates = 20`. During those updates the value loss is the only loss, and every parameter outside `critic_encoder.*` and `value_head.*` keeps a `None` gradient. AdamW therefore never creates optimizer state for the actor. The scratch arm is forced to 0. The count is recorded in the TOML, the checkpoint `council_recipe`, the launch record and the plan.
- **6. Target-KL early stop** at 0.02 in both arms. This replaces the forced `0`.
- **7. Monitoring-only alarms.** They are written to `training-monitor.jsonl` and `training-alarms.jsonl` in the run directory, and `TRAINING_ALARM` lines go to the training log. Per-match opponent outcomes are written to `opponents/worker-*-outcomes.jsonl`. No alarm changes any setting or stops a run.
- **8. League.** The initial policies (the scripted warm start and the matched scratch control) are sampled inside the 50% historical share after the pool switches to league, which happens at ≥1M decisions. They are deduplicated by hash. Scripts fill that share only when no frozen policy exists.

The pilot config SHA changed from `5192e437ecd1a4857b0193ffdd8a419e31008244b649a6e2ceb60beda5f87f6f` to `b7b12ab9e4f50300baf8493d0db167a557aea4fc82725f0251ccebacade8d3fa`. The evaluation protocol does not pin the config and was unchanged. No run or checkpoint exists yet that pins the old SHA.
