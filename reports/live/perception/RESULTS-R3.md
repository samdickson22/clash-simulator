# LIVE perception round 3 (exploration tier): units on the official client, RESULTS

Owner: `live-perc-r3` (parent: LIVE LEAD), 2026-10-15/16. Log and resume state: [PROGRESS-R3.md](PROGRESS-R3.md). Earlier rounds:
[RESULTS.md](RESULTS.md), [RESULTS-R2.md](RESULTS-R2.md).
Exploration tier: no preregistration; epochs and thresholds were chosen on the official labelled set described below, so its
numbers are optimistic for out-of-sample use. Training Camp and Bone Pit were never used as training floors (held-out arenas).
**Heldout was never opened** (every renderer loader goes through `common.HeldoutGuard`). No images or video are committed.

**Status: DRAFT** — ft-r6 (any-unit head) and the full renderer/event evaluations are still running; sections marked
*pending* are filled in when they finish.

## TL;DR

1. **"Zero units" was a scene-context domain gap, not a pipeline bug.** Mapping, colour order and scaling were checked; the
   round-1 heatmap was sub-threshold (.3–.7) on official frames, and a paste test showed the score collapses when the arena
   around a unit changes (renderer Goblins .95 → .45 on a Goblin Stadium floor; official Giant .72 → .26 on a renderer floor).
2. **Fix 1: background-invariant compositing.** Renderer unit pixels pasted onto official Goblin Stadium floors, recoloured floors and
   procedural textures, plus empty official floors as hard negatives.
3. **Fix 2: level-badge stripping.** The renderer draws a level badge and HP bar over every unit; the official client draws none on
   full-HP units, and the model had learned to rely on the badge. Training randomly strips them.
4. **Deployed candidate: ft-r5 final (epoch 3) = `export-interim-r5e3`.** Official units at thr .5, identity×owner ≤1 tile:
   Goblin Stadium P/R **.959/.440** (round 1 .833/.063), Training Camp **1.000/.485** (.176/.031), Bone Pit **.857/.400** (.750/.200);
   **0 false units on empty official frames** in every arena (round 1: 1.0/frame on Training Camp).
5. Capture resolution is not the limit for small units (renderer recall is flat from full resolution down to the 720×1280
   capture equivalent). Minions remain the weakest card (GS 13/51).

## Official labelled set

| set | frames (excluded) | units | source |
|---|---:|---:|---|
| Goblin Stadium | 48 (2) | 159 | ladder1 + live1–5 recordings (bot-played ladder) |
| Training Camp (held-out arena) | 26 (4) | 97 | tc2 recording (tutorial battles) |
| Bone Pit (held-out arena) | 25 (0) | 76 (16 off-vocab) | s1m01 recording |
| empty official frames | 18 | 0 | TC 4, GS 9 (5 from a match never used as a floor), BP 5 |

Labelled by 7 Opus helpers (high effort) from gridded sheets, with per-frame confidence and exclusions, then verified by the owner on
overlays (owner by badge colour; identity; feet / shadow position, which matches the renderer's own label convention). Verifier
exclusions: intro / game-end camera shifts and one ambiguous placement preview; one cross-helper relabel (Barbarian Hut).
Label JSONs and sheets are in 05 `scratch/live-perc-r3/{labels,label}/` (not committed).

## Results

### Official frames (thr .5, identity×owner, ≤1 tile; P / R)

| model | GS | TC (held out) | BP (held out) | empty-frame false units/frame (GS / TC / BP) |
|---|---|---|---|---|
| round 1 (`export-final`, cba64d2a…) | .833 / .063 | .176 / .031 | .750 / .200 | 0 / 1.0 / 0 |
| interim e1 (ft-r4 epoch 1) | .975 / .245 | .926 / .258 | .842 / .267 | 0 / 0 / 0 |
| **ft-r5 final (epoch 3)** | **.959 / .440** | **1.000 / .485** | **.857 / .400** | **0 / 0 / 0** |
| ft-r6 (any-unit) | *pending* | *pending* | *pending* | *pending* |

Threshold sweep (ft-r5 epoch 3, GS): .40 .856/.522, .45 .921/.516, .50 .959/.440. The win-rate proxy from ABLATION.md
(.230·recall − .128·phantoms/frame) is flat over .40–.50; .5 is the only setting with zero decor false units on every empty frame,
so **the recommended threshold stays .5** (the `LivePerception` default). *Final re-sweep: pending.*

Per-card recall at thr .5, round 1 → ft-r5 final (epoch 3), hits/n:
- **GS:** Archers 3/37 → 16/37, Giant 5/15 → 9/15, Knight 0/21 → 16/21, MiniPekka 0/19 → 10/19, Minions 0/51 → 13/51, Musketeer 2/16 → 6/16.
- **TC:** Archers 0/46 → 25/46, Giant 3/14 → 10/14, Goblins 0/7 → 6/7, Knight 0/9 → 1/9, MiniPekka 0/9 → 3/9, Minions 0/12 → 2/12.
- **BP:** Archers 3/16 → 8/16, Goblins 3/13 → 8/13, Knight 2/6 → 2/6, MiniPekka 1/7 → 1/7, Minions 3/18 → 5/18.

Full tables: `r3/sweep_table.py` on `scratch/live-perc-r3/{eval-r1.json,evals-r5/epoch-3.json}`.

### Renderer validation (no large regression)

| metric | round 1 | ft-r5 final |
|---|---|---|
| quick val (16 val matches, every 8th block): unit id F1 | .846 | .828 |
| quick val: event window P/R | .915 / .742 | .912 / .706 |
| quick val: tower HP MAE | .0061 | .0092 |
| quick val: hand acc / elixir MAE | .9905 / .057 | .9897 / .067 |
| full val (`eval_val.py --stride 2 --truth dense`) | see RESULTS.md | *pending* |
| full play events (`eval_events.py --stride 2`) | see RESULTS.md | *pending* |

### Latency

TorchScript export, A6000 fp32 batch 1: frame 4.3 ms p50 (same network as round 1, so CPU/Mac latency is unchanged; `latency.json`
beside each export).

## What was done

1. **Diagnosis** (`r3/diag_zero.py`, `r3/paste_test.py`): see TL;DR 1.
2. **Data** (`r3/prep_bg.py`, `r3/prep_official.py`): an empty match-start frame for all 577 train+val matches (the renderer has a
   single sand skin; a median template removes replay-control overlays); 8 empty Goblin Stadium floors via `live/loop/canvas.py`.
3. **Training** (`r3/finetune_r3.py`, the finetune2 joint run plus compositing): floors per frame are plain .30 / official .30 (half
   recoloured) / hard negative .06 / recoloured own floor .14 / procedural texture .20. Unit mask = difference vs the match-start frame
   AND vs the template, inside label boxes. Stronger resolution loss. Badge strip p=.6 per unit (ft-r5). The event head keeps
   training on renderer windows.
4. **Runs:** ft-r4 (init round-1 ft-r2 final; 4k steps), ft-r5 (from ft-r4 epoch 4, badge strip; 8k steps, stopped on plateau),
   ft-r6 (from ft-r5 epoch 3, + any-unit head).

## Downstream interface

Unchanged: `LivePerception(export_dir)`, same TorchScript signatures and record schema; `vocab.json` has the same `cards` and
`identities` as round 1 plus metadata keys. ft-r6 adds identities `AnyTroop`(58)/`AnyBuilding`(59) and an **additive** record key
`unknown_units: [{owner, kind, x, y, score}]` (`units` unchanged).

## Weaknesses

1. Recall is still ~.44 on Goblin Stadium. Small units (Minions 13/51) and units under effects are the misses.
2. The labelled set is small (99 frames, 332 units), from few matches; numbers move by several points between epochs.
3. Off-vocab cards (Goblin Cage, Barbarian Hut, …) are not identified; ft-r6's unknown class is the first step.
4. Same-sprite cards (Skeletons vs SkeletonArmy, Goblins vs GoblinGang, Minions vs MinionHorde) are guessed from context; the
   sprite-level body classes (round 4) address this.

## Artifacts

| artifact | path (01 and 05 unless noted) | sha256 |
|---|---|---|
| ft-r5 final checkpoint (epoch 3) | `/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/ft-r5/epoch-3.pt` (05 copy: `scratch/live-perc-r3/mirror/ft-r5/`) | `1f227f9b010f0eb53b69b769e2b45eb6a3e40b70bd1b17aed8fd81fa4c4ee4e4` |
| ft-r5 final export | `…/export-interim-r5e3/` frame.pt / event.pt / vocab.json | `81697f5b…` / `638276a0…` / `d39b06bb…` |
| interim e1 export | `…/export-interim-e1/` | frame `9b06f968…`, event `cc75886f…` |
| ft-r6 export | *pending* | |
