# Clasher training handoff — verified September 8, 2026

Read this first, then verify the files it points to. This is a restart of the reasoning context, not a request to restart all experiments. The user wants you to take ownership, question failed assumptions, and move toward a competent Hog 2.6 policy. Do not inherit the previous thread's confidence or reporting habits as evidence.

## Objective and authority

Long-term user intent: a model that can play one fixed Hog 2.6 deck competently against a mid-ladder human, then expand its own deck choices. Opponent diversity still matters.

Current scoped objective, verbatim:

> Build and rigorously validate a calibrated actor-visible Hog 2.6 outcome model from complete games, predicting undiscounted win/draw/loss and terminal tower margin across held-out seeds, opponents, seats, and game phases; permit privileged information only in a training-only teacher and do not begin search, policy updates, PPO, or self-play until public-state calibration and counterfactual ranking gates pass.

The user is transferring this work to a fresh task. Check `get_goal` there; if no goal exists and the new prompt authorizes continuation, create this objective there. The old task's goal was returned as `usageLimited`, not complete, on September 8. Do not mark it achieved to facilitate transfer.

“No search before ranking gates” means no deployed search/controller improvement before acceptance. A bounded counterfactual evaluation is necessary to establish the ranking gate after public-state validation. Do not turn this wording into a circular blocker.

## Work in the correct checkout

- Active research worktree: `/Users/sam/.codex/worktrees/clasher-event-policy`
- Branch: `codex/hog26-event-policy-redesign`
- Verified source HEAD: `559fe9fc75e7ae64078d1887d6c17bc5b5e0ed59`
- Saved Desktop project: `/Users/sam/Desktop/code/clasher` — a separate checkout. Do not merge/reset it or assume it contains these experiments.
- Python runtime: `/Users/sam/Desktop/code/clasher/.venv/bin/python`
- Ruff: `/Users/sam/Desktop/code/clasher/.venv/bin/ruff`
- Run with cwd set to the research worktree and `PYTHONPATH=src:.`.
- Source was tracked-clean at handoff. There are more than 120 untracked dataset/report entries that belong to this work. Many checkpoints are ignored. A clean git archive or a new worktree alone will not carry them.
- Read the Desktop `AGENTS.md` and any applicable `AGENTS.local.md`. No AGENTS file was found at the active research worktree root in this check.

Use the existing research worktree directly for continuity. If isolation is needed, preserve and explicitly reference/copy the required local datasets/checkpoints. Do not stash, clean, reset, or delete unexplained state.

## Current state — replaces the old “chunk 5” messages

No matching Clasher collection/training process was running at handoff. Old PID 74366 and tool session 66231 are historical, not handles to resume blindly.

The first procedural shard FINISHED on September 3 and was independently audited during this handoff on September 8:

- Corpus: `datasets/derived/hog26_procedural_train_balanced_random_seed1278501/corpus.npz`
- Corpus SHA-256, recomputed and matching report: `7edd615cfe63400bd64644b6be7d26dbd9532fca00f05bebfb3e29d7e7849a3f`
- Collection report: `reports/hog26_procedural_train_balanced_random_seed1278501.json`
- Newly published audit: `reports/hog26_procedural_train_balanced_random_seed1278501_audit.json`
- Audit SHA-256: `7eb140faaac9023936d9fadd3512661fc9d315f3ea8a3f9b56d0cedcc5f69ba0`
- 128 complete games, 58,161 retained decision rows, 77 losses, 51 wins, zero draws.
- Balanced opponent: 24 wins / 40 losses. Random: 27 wins / 37 losses. This is evidence that the frozen behavior policy is still weak, not human-level play.
- 32 generated training decks × 2 opponent modes × 2 learner seats.
- 12 chunks, 9,458.704 seconds = 2.627 hours. Longest episode 750 decisions; median 450.
- Retained useful throughput: 58,161 / 9,458.704 = approximately 6.15 decision rows/s, or 48.7 completed games/hour.
- Previous ~10.4 decisions/s reports counted every executed slot, including work beyond streams' retained episode quota. Do not present that as retained-data throughput. The earlier “10 chunks / 2.2 hours” forecast was too optimistic.
- Audit passed declared deck/style coverage, terminal outcomes, complete streams, finite values, actor/public-mask metadata, and SHA authority.
- Phase rows: early 31,884; middle 24,833; late 1,444. Matchup clusters: 64 early, 64 middle, 11 late. Only 2 late clusters contain a win; late evidence remains sparse.
- Audit success does not prove exact real-game mechanics or actual live-vision equivalence. Some causal checks inspect metadata declarations; inspect code/tensors when stronger proof is needed.

All other new procedural corpora are ABSENT: training seeds 1278502/1278503, selection 1278601, calibration 1278602, final tests 1278701/1278702. The primary outcome candidate seed1278801 does not exist. No new policy has been promoted.

## Critical protocol defect discovered at handoff

The committed protocol calls `split-lane` an unseen final-test opponent, but three retained legacy TRAINING corpora explicitly include it:

1. `datasets/derived/hog26_crossed_train4_seed1276001/corpus.npz`
2. `datasets/derived/hog26_broad_train_fold_a_seed1277001/corpus.npz`
3. `datasets/derived/hog26_broad_train_fold_b_seed1277002/corpus.npz`

Their `metadata_json.opponents` is `[balanced, slow-push, split-lane, random]`. This was verified from NPZ metadata on September 8. Existing protocol tests inspect only the new shard schedule and therefore miss the contradiction.

Before training or claiming opponent generalization, fix this design. Options include filtering split-lane episodes out of legacy training with exact episode/provenance preservation, or predeclaring genuinely new opponent behavior for final testing. Check the frozen base-policy's prior exposure too: an opponent unseen by the new outcome head is not necessarily unseen by the entire lineage. Document the scope honestly. Do not retroactively call the existing plan unseen. No correction was made during handoff; the defect is open and reviewable.

## Evidence that led here

Main chronology: `reports/hog26_actor_outcome_train4_gate_20260902.md`. Read its later sections first: early “Decision” paragraphs describe superseded development acceptance.

Historical development-selected outcome checkpoint:
`checkpoints/hog26_actor_outcome_accepted_development_v3_seed1277501/candidate.pt`

Despite its filename, it was REJECTED on untouched holdout. This is a small outcome head attached to a frozen policy, not the old six-million-parameter policy itself.

- Frozen test: 72 natural games plus 8 physical symmetric draw games represented as 16 actor views = 88 episodes / 41,719 rows.
- Decisive AUC early/middle/late: 0.6667 / 0.7667 / 0.8750.
- Clustered lower 95% bounds: 0.4830 / 0.5776 / 0.6997. Early misses 0.50.
- NLL 0.8032 versus prior 1.2943; ECE 0.1182. Classification has some signal.
- Terminal-margin MAE improvement −0.00630 overall, late −0.03995: learned prediction is worse than current public tower margin.
- Report: `reports/hog26_actor_outcome_accepted_holdout_seed1277501.json`.
- The opened holdout is diagnostic only, permanently unavailable as fresh final proof.

Three static margin repair variants and a 15,981-parameter GRU with 16 memory units improved development but reversed on the opened holdout. The GRU's improvement was +0.01061 development, −0.00078 opened holdout. Relevant reports: `hog26_margin_public_p6_diag_seed1278201.json`, `hog26_margin_full_p4_diag_seed1278201.json`, `hog26_margin_full_p6_diag_seed1278201.json`, `hog26_temporal_margin_diag_seed1278301.json` under `reports/`.

Interpretation: broader deck coverage is a plausible next hypothesis, not a proven sole cause. Do not claim these few failures ruled out recurrence or that more decks must fix it. The progress-power-6 margin correction suppresses late predictions strongly; audit whether it learns useful future damage rather than winning a metric through near-zero corrections.

## Frozen procedural campaign

Machine-readable authority: `reports/hog26_procedural_outcome_protocol_seed1278401.json`.

Base behavior policy: `checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt`
SHA `f609b60b3e7b7b574e084b15255e0fc247447e3c18d8552714213ccd0c709336`.

Generated supported manifest: `training_decks/hog26_procedural_supported_seed1278401.json`
SHA `6cb22eed1111ce2a21e240eaa5e6adcdd0357fdb04b97127c58ff6600b535ac8`.

Original supported manifest: `training_decks/simple_gym_supported_v1.json`
SHA `c93de9989841743b535fe5fde182abe19e1983c8f67a0a27d0c191ea9ccd212f`.

Generator: `scripts/generate_hog26_procedural_decks.py`. 32 eligible parent decks used once each, 16 parent-pair families, 4 variants/family, each an eight-card 4+4 cross. Family variants cover all parent cards. Structural validation enforces spell/troop/building/elixir/anti-air/pressure constraints; this is not evidence of strategically coherent human meta decks. Review representative generated decks if interpreting results.

65 compiled rows = fixed Hog 2.6 learner + 64 opponents, no simulator-support rejections. Train families cover 63 roots; Archer Queen, Royal Delivery and Royal Hogs appear only in the separately reserved `RHogs AQ 2.9 Cycle` deck. This makes that final test both a new-deck and new-card shift. Overall current game support remains narrower than the full game.

| Stage | Seed | Opponents | Families | Games | State |
|---|---|---|---|---:|---|
| Train shard 0 | 1278501 | balanced, random | 000–007 | 128 | completed + audited |
| Train shard 1 | 1278502 | bridge-pressure, reactive-defense | 000–007 | 128 | absent |
| Train shard 2 | 1278503 | slow-push, spell-control | 000–007 | 128 | absent |
| Selection | 1278601 | balanced, reactive-defense | 009,010 | 64 | absent |
| Calibration | 1278602 | balanced, reactive-defense | 013,014 | 64 | absent |
| Generated final | 1278701 | split-lane (see defect) | 008,011,012,015 | 96 | absent/sealed |
| Reserved original final | 1278702 | split-lane (see defect) | RHogs AQ deck | 6 | absent/sealed |

Primary candidate as currently declared: seed1278801, 398-feature structured actor summary, hidden16, separate draw trunk, independent public-global margin correction scale0.5 and progress power6, 30 epochs, AdamW LR0.0001, batch512, sequence128, phase-balanced losses, loss/draw/win training mass .45/.10/.45. See protocol and trainer for exact current semantics. Reassess protocol defects before launch; preserve test-set isolation when amending design.

Training inputs: three procedural shards + the three legacy natural corpora listed above + `hog26_symmetric_draw_outcomes_seed1270001/corpus.npz`. Selection adds the old controlled draw corpus seed1271001 to the new selection corpus. Calibration is a separate new natural corpus. Final controlled-draw and multi-seed acceptance need explicit predeclaration; the current JSON final section only names natural games, despite draw gates in the objective.

## Resume commands and priorities

First inspect status, dependencies, actual processes, and protocol. Do not blindly rerun completed shard0 or its audit; tools refuse overwrite.

```sh
cd /Users/sam/.codex/worktrees/clasher-event-policy
git status --short --branch
git rev-parse HEAD
```

Then inspect the newly completed shard audit, including outcome balance by style/seat and late cluster counts. Repair the split-lane exposure plan above before claiming the final experiment is frozen. Run the next authorized TRAINING collection after checking local CPU/MPS/memory use:

```sh
PYTHONPATH=src:. /Users/sam/Desktop/code/clasher/.venv/bin/python scripts/run_hog26_procedural_outcome_shard.py --protocol reports/hog26_procedural_outcome_protocol_seed1278401.json --training-shard 1 --device mps
PYTHONPATH=src:. /Users/sam/Desktop/code/clasher/.venv/bin/python scripts/audit_hog26_procedural_outcome_shard.py --protocol reports/hog26_procedural_outcome_protocol_seed1278401.json --training-shard 1
```

Use shard2 similarly. Collection/audit scripts also accept `--development-selection` or `--probability-calibration` instead of `--training-shard`. These are outcome-data jobs, not policy updates. Each stage is sequentially auditable; no requirement to wait idly when useful independent work exists.

After all required data passes the applicable audits and protocol defects are resolved:

```sh
PYTHONPATH=src:. /Users/sam/Desktop/code/clasher/.venv/bin/python scripts/train_hog26_procedural_outcome_candidate.py --protocol reports/hog26_procedural_outcome_protocol_seed1278401.json --device mps
```

Inspect this wrapper first. It currently checks file existence and authority pins; existence alone is not proof of passed audits. Underlying trainer performs corpus validation, seed/hash checks, and deck disjointness. Check that intended family isolation and legacy filtering are actually enforced after any protocol correction.

Only an accepted development candidate earns a frozen state digest and fresh final evaluation. Preserve undiscounted complete-game labels, actor-only inputs, calibration isolation, whole-family split isolation, and predeclared thresholds. Then perform seed replication and bounded exact-terminal action-ranking evaluation with phase-, seat-, and opponent-balanced roots before any policy update/search deployment.

## Files worth reading, in order

1. This document and current protocol JSON.
2. Completed shard0 collection report + new audit.
3. Later rejection sections of `reports/hog26_actor_outcome_train4_gate_20260902.md`.
4. `scripts/collect_hog26_complete_outcomes.py`, `scripts/audit_hog26_outcome_corpora.py`.
5. `scripts/train_hog26_actor_outcome.py`, `src/clasher/rl/outcome_model.py`, protocol training wrapper.
6. `reports/hog26_architecture_research_20260901.md` and `reports/hog26_back_to_drawing_board_20260901.md` only as needed for rejected alternatives.
7. `scripts/evaluate_hog26_outcome_counterfactual_pairs.py` and its plan/tests when public-state acceptance is earned.

Targeted tests exist for collector, protocol, runner, audit, trainer, model and temporal margin. The prior thread repeatedly added wrappers/tests while waiting; avoid more scaffolding without a concrete defect. Metadata assertions are weaker than inspecting actual tensors, outcomes, trajectories and gameplay.

## Resources, neighboring work, and user preferences

- Local Mac mini has 24GB unified memory and MPS. Last completed collection used eager MPS. RSS alone excludes substantial GPU/driver memory; inspect whole-system pressure.
- CUDA is preferred for production speed where available, but certify exact source and useful retained throughput; old CUDA benchmark numbers cannot be carried to changed code.
- Prior Prime wallet check (September 3) was −$17.23 with zero pods. This is stale; check current account before assuming money or capacity. The school SSH host timed out at that time. No fresh cloud purchase or school access was attempted for this handoff.
- User previously authorized reasonable paid compute and ordinary school-user writes, explicitly no sudo on the school machine. Never copy historical credentials into prompts/docs/logs. Do not assume current auth or allocation.
- User later told Clasher/RoadForge to share compute, replacing the earlier elaborate exclusive-window coordination. Observe live workloads; don't kill other work.
- Training source task: `019fd3ea-23fc-7453-b38e-4399dafde4c4`.
- PyTorch Gym task: `01a002c2-79ac-7ad2-9078-c9fde8423819` (delivery sometimes required finding its current title via task list).
- Viewer task: `019fd9ca-27fd-7002-91f2-2ce714b13f24`.
- Historical optimizer task: `019fdedb-7f58-7cb1-b1b5-c531237cc88c`; Rust work was replaced by PyTorch.
- RoadForge task: `019fd8fd-a3ae-7181-8ed6-fbd5a9d89fc2`.
- Task IDs are pointers, not proof those tasks are active. Do not spawn substitutes accidentally.

The user wants autonomous substantive work, honest failure analysis, and a willingness to rebuild. Do not endlessly report an unchanged chunk or create tiny “pin another field” commits as a substitute for progress. Prior claims that ended streams stop consuming compute were not established: the fixed batch continues collecting and discards surplus episodes. Timing estimates must include this tail cost.

Keep user communication concise. State what the bot actually does well or badly. A calibrated outcome predictor is still not a competent playing policy, and simulator results are not a measured mid-ladder rating.

## Scope of this handoff

On September 8 I verified current HEAD, local corpus/report existence and SHA, process absence, legacy opponent metadata, and ran the shard0 audit successfully. I created this document and the audit artifact only; no new trainer, collector, cloud instance, merge, push, or goal-completion action was started. Read current state again on resumption because it can change.
