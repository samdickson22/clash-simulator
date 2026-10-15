# LIVE step B: perception (exploration tier), RESULTS

The step-B perception sub-agent wrote this on 2026-10-15 for the LIVE LEAD. It is exploration tier: there's no preregistration, and the
thresholds and epoch were chosen on validation, so these numbers are **optimistic for out-of-sample use**.
Every number below is measured on the **validation split** (64 matches) of the registered v4 split (`split.json`
sha `3edbd25b…`). **Heldout was never opened.** Every loader goes through `live/perception/common.py:HeldoutGuard`, which
asserts that no heldout episode is ever listed, read or loaded.

> **Caveat: domain gap unmeasured.** All data is from the offline private-server renderer (APK 15.535 content) at
> 1080×2280, sanitized to a 540×1140 canvas. The official client (≥16.402: art, UI and HUD changes; arbitrary emulator
> resolution) has never been captured, so how these numbers transfer to official frames is **unknown**. Training adds
> resolution, colour and noise augmentation; that's a hedge, not a measurement.

## Headline (final model `ft-r2/final.pt`, sha `cba64d2a…`)

| quantity | T7 baseline | **final** |
|---|---:|---:|
| own hand, accuracy per slot (4 slots) | 97.9% | **98.85%** (steady state 99.49%) |
| next card | 98.0% | **98.5%** |
| all 4 hand slots right | 94.2% | **97.0%** |
| own elixir MAE / exact integer | 0.25 / 96.4% | **0.064 / 97.1%** (steady state 99.4%) |
| tower HP MAE (fraction of max; destroyed = 0) | 0.151 | **0.0089** |
| tower alive/destroyed accuracy | 98.4% | **99.98%** |
| units, identity×owner, ≤1 tile, P / R / F1 (score ≥ 0.4) | 0.11 / 0.09 / 0.10 (best thr) | **0.907 / 0.774 / 0.835** |
| units, identity×owner, ≤¼ tile, P / R / F1 | 0.01 / 0.01 / 0.01 | **0.789 / 0.673 / 0.726** |
| units, owner only, ≤1 tile, P / R / F1 | 0.40 / 0.32 / 0.35 | **0.948 / 0.810 / 0.874** |
| units, owner only, ≤¼ tile, P / R / F1 | 0.06 / 0.05 / 0.05 | **0.813 / 0.694 / 0.749** |
| play events, all, P / R (≤1 s, score ≥ 0.6) | 0.05 / 0.09 (best thr) | **0.872 / 0.750** |
| play events, **opponent spells**, P / R | 0.39 / 0.06 | **0.745 / 0.490** |
| play events, opponent troops+buildings, P / R | 0.04 / 0.12 | **0.904 / 0.845** |
| event placement (matched): median / ≤1 tile | n/a | **0 tiles / 99.2%** |
| event detection latency after execution (median) | n/a | **150 ms** |

"Steady state" = no hand or elixir change within ±3 frames (150 ms). Most HUD errors fall within 150 ms of a change, which is
largely label/frame timing. Hand, elixir and tower numbers are per frame (64 val matches, every 2nd frame, 53,388 frames).

**Inference latency** (batch 1, fp32 TorchScript; `export-final/latency.json`). A6000, shared with the bot lead's jobs at
the time: frame 4.3 ms p50, event head 6.7 ms p50. 01 Threadripper (loaded host): frame 46 ms at 16 threads / 122 ms at 4,
event head 81 / 107 ms, decode + record 9 ms. End to end through `LivePerception` (prep + both heads + decode + tracker,
12 threads): **107 ms/frame**. **Mac MPS/CPU/CoreML: not measured yet.** The event head is the expensive part on CPU.
A Mac at ~10 FPS needs MPS or CoreML, or the event head run every other frame.

### Frame metrics, full validation (`eval_val.py --truth dense --stride 2`)

Units: a hit = same card identity and owner within 1 tile (or ¼ tile), greedy by score. Predictions near ignore objects
(Ghost, unknown card ids) don't count as false positives. "Owner only" ignores identity. The T7 column maps its
39 body identities onto cards. Per-tower detail is in `eval/final-dense-s2/metrics.json`.

| metric | T7 (e5d1acd1) | ft-r2 final (cba64d2a) |
|---|---:|---:|
| frames | 53388 | 53388 |
| hand acc / slot (4 slots) | 0.9790 | 0.9885 |
| next-card acc | 0.9800 | 0.9849 |
| all 4 slots correct | 0.9424 | 0.9701 |
| hand acc / slot, steady state | 0.9892¹ | 0.9949 |
| elixir MAE | 0.2519 | 0.0643 |
| elixir exact integer | 0.9643 | 0.9707 |
| elixir integer, steady state | 0.9911¹ | 0.9944 |
| tower HP MAE (all, destroyed = 0) | 0.1512 | 0.0089 |
| tower alive/destroyed acc | 0.9836 | 0.9998 |
| king tower HP MAE (alive) | 0.0363 | 0.0158 |
| princess tower HP MAE (alive) | 0.2257 | 0.0059 |
| units id×owner ≤1 tile: best-F1 threshold | 0.2 | 0.4 |
|   P / R / F1 | 0.108 / 0.086 / 0.096 | 0.907 / 0.774 / 0.835 |
|   same threshold, ≤¼ tile P / R / F1 | 0.012 / 0.009 / 0.010 | 0.789 / 0.673 / 0.726 |
|   at score 0.5, ≤1 tile P / R / F1 | 0.435 / 0.003 / 0.005 | 0.955 / 0.738 / 0.832 |
| units owner-only ≤1 tile: threshold | 0.2 | 0.4 |
|   P / R / F1 | 0.398 / 0.319 / 0.354 | 0.948 / 0.810 / 0.874 |
|   ≤¼ tile P / R / F1 | 0.057 / 0.046 / 0.051 | 0.813 / 0.694 / 0.749 |
| mean match distance (tiles, score 0.5) | 0.321 | 0.119 |

¹ T7 steady-state values are from its stride-4 run (`eval/t7-dense-s4-steady`, 26,690 frames).

### Play events, full validation streaming (`eval_events.py --stride 2`, ~10 FPS, 2,826 events)

Match rule: same native side and card, emitted at a frame time in [execution, execution + W]; Hungarian. This is the same
idea as `scoring_v4` point mode, plus a 1 s variant. The thr column = tracker emission threshold. The T7 temporal head with
the old EventFusion peaks at P 0.05 / R 0.09 (thr 0.3, W 1 s). The retrained head with the old EventFusion is in
`eval/ev-final-s2/events.json` (`metrics`); it is strictly worse than the tracker at equal precision.


**ft-r2 final** (64 matches, 53388 processed frames at ~10.0 FPS, 2826 events)

| fusion | thr | W | all P/R | opp P/R | opp spell P/R | opp troop+bldg P/R | own P/R | placement median / p90 / ≤1 tile | latency median |
|---|---|---|---|---|---|---|---|---|---|
| tracker | 0.3 | 500ms | 0.422/0.657 | 0.425/0.711 | 0.166/0.546 | 0.690/0.768 | 0.418/0.605 | 0.0 / 0.0 / 0.9747 | 75.0 |
| tracker | 0.4 | 500ms | 0.619/0.681 | 0.629/0.714 | 0.337/0.487 | 0.772/0.792 | 0.608/0.650 | 0.0 / 0.0 / 0.9855 | 100.0 |
| tracker | 0.5 | 500ms | 0.741/0.705 | 0.743/0.715 | 0.487/0.434 | 0.823/0.812 | 0.739/0.695 | 0.0 / 0.0 / 0.9905 | 100.0 |
| tracker | 0.6 | 500ms | 0.807/0.695 | 0.811/0.700 | 0.592/0.389 | 0.865/0.808 | 0.803/0.689 | 0.0 / 0.0 / 0.9959 | 150.0 |
| tracker | 0.7 | 500ms | 0.816/0.627 | 0.829/0.638 | 0.655/0.314 | 0.863/0.750 | 0.803/0.616 | 0.0 / 0.0 / 0.9977 | 175.0 |
| tracker | 0.3 | 1000ms | 0.447/0.695 | 0.450/0.752 | 0.205/0.672 | 0.701/0.780 | 0.443/0.640 | 0.0 / 0.0 / 0.9644 | 75.0 |
| tracker | 0.4 | 1000ms | 0.655/0.722 | 0.670/0.760 | 0.419/0.605 | 0.793/0.814 | 0.641/0.685 | 0.0 / 0.0 / 0.9824 | 100.0 |
| tracker | 0.5 | 1000ms | 0.790/0.751 | 0.789/0.759 | 0.588/0.524 | 0.852/0.841 | 0.790/0.744 | 0.0 / 0.0 / 0.9882 | 125.0 |
| tracker | 0.6 | 1000ms | 0.872/0.750 | 0.873/0.753 | 0.745/0.490 | 0.904/0.845 | 0.871/0.748 | 0.0 / 0.0 / 0.9915 | 150.0 |
| tracker | 0.7 | 1000ms | 0.927/0.712 | 0.929/0.715 | 0.836/0.401 | 0.946/0.823 | 0.925/0.710 | 0.0 / 0.0 / 0.994 | 200.0 |

Opponent spells per card (tracker thr 0.4, W 1 s; TP/FP/FN): BarbLog 48/44/13, Log 27/30/25, Zap 33/27/16,
Tornado 33/14/9, GoblinBarrel 22/46/12, Earthquake 18/50/15, RoyalDelivery 12/27/20, Poison 7/18/13, Arrows 9/20/9,
Fireball 6/20/6, Rocket 0/2/3, Lightning 1/2/0. Per-card counts for all cards are in `events.json`.


## What changed vs T7 (why the jump)

1. **Dense card-level unit labels** (`dense_labels.py`). T7's formal labels admitted a unit only when its identity
   was uniquely resolvable from max HP *and* a same-tick rich snapshot existed (~42 per match). That gave ~0.07 labelled
   units per frame, a 39-body vocabulary (no Archer, Knight, Valkyrie, Wizard, Tesla) and an essentially untrained
   body head. Now every object with hit points is a positive, with identity = the card that spawned it (C56 order) plus
   KingTower/PrincessTower: 58 identities × 2 owners. Ghost and unknown card ids are ignore regions; objects without HP
   (projectiles, spell areas) are background.
2. **Frame-batch training** of encode() (32 frames per step, ~7 steps/s) instead of one 16-frame window per step.
   T7 saw 9.6k windows in total; ft-r1 saw ~670k frames.
3. **Sub-cell offset head:** `body_box[0:2]` is repurposed as the object's (x, y) offset inside its half-tile cell, which helps the
   ¼-tile metric.
4. **TemporalHead retrained** on play events (ft-r2: ~45k joint steps, 8 windows per step at 8–25 FPS, spell endpoints
   oversampled), and decoded with a **location-level event tracker** (`events.py`) instead of the per-card EventFusion.
5. Augmentation: down/up-sampling to 45–90% resolution, gain, gamma, tint, noise, horizontal flip.

## Model and files

| artifact | path (same path on **127x01** and **127x05**) | sha256 |
|---|---|---|
| final checkpoint (live-dense-v1) | `/mpac/sdicks02/jobs/clasher/live-perception-20261014/ft-r2/final.pt` | `cba64d2a8c53a0ce431ff20a3a60b990d782bdefc9d9311f34828c3df274a37a` |
| TorchScript frame module | `…/export-final/frame.pt` | `20f77a71cf5f3369d1a8ffe78cab822f126842fd25c8bec149039c26055b7dd2` |
| TorchScript event head | `…/export-final/event.pt` | `1f7af56d4c6ac04a0c0839e05a9f7a53e57fd81c8b8b2fbbd2ad87ba387c5cfe` |
| vocab / parity / latency | `…/export-final/{vocab,parity,latency}.json` | parity: max abs error 0.0 on all frame outputs and the event head (64 real val frames + padding/gap variants); 64/64 identical hand and unit decisions |
| ft-r1 (stage 1, body+HUD only) | `…/ft-r1/stopped-last.pt` | `dd393bf8247009065f03a5deb34df518e382ae7b3a253b6c1dc7072875a9de96` |
| T7 baseline (copy) | `…/ckpt/t7-final/last.pt` | `e5d1acd124158dc9410a1f10bb1aaa51b180bc2abd9547da27e66a8da62f7e9c` |
| eval outputs | `…/eval/{final-dense-s2,ev-final-s2,t7-dense-s2,ev-t7-s2}/` | |
| sample records for the bot side | `…/sample-records/` (2 full val matches, ~10 FPS, pred + truth per frame, README) | |
| labels / extra caches (01 only) | `…/labels/*.npz` (577 train+val), `…/cache/` (228 pixel caches) | |

Training: ft-r1 = T7 init, 21,000 steps × 32 frames, body/HUD only (~46 min A6000). ft-r2 = ft-r1 init, 40,011 joint
steps (32 frames + 8 event windows each, ~4.2 h), stopped by plan at the end of its cosine schedule. Epoch = final; no
epoch selection beyond "last".

## Downstream interface

`live/perception/infer.py:LivePerception(export_dir, device)`. Call `.step(bgr_540x1140, timestamp_ms)` on every
processed frame and `.reset()` per match. It returns `common.frame_record` (`clasher.live.perception-frame.v1`):

- `units`: [{cls, card, owner, x, y, hp_frac, score}]. `cls` = `card` = a C56 card name (units are labelled by spawning card;
  e.g. Golem → Golemites are both "Golem", GoblinGang members are "GoblinGang").
- `towers`: 6 × {owner, kind king/princess, side left/center/right (screen), alive, hp_frac, score}.
- `hand`: {cards[4], probs[4], next, next_prob}; `elixir` (float); `clock_s`, `phase`.
- `events`: [{owner, card, x, y, tick, score}]. `tick` = estimated execution time in ms on the caller's timestamp clock.
- Coordinates: **owner 0 = us, 1 = opponent**; x in tiles from the screen left (0..18); y in tiles from the screen
  bottom (0..32), so our king is at (9, 3). That is the native frame with y flipped (`y = 32 − native_y`; x unchanged). hp is a
  fraction of max HP.
- Vocabulary mapping: `vocab.json` beside the export (identities = C56 cards from `split.json` + KingTower,
  PrincessTower; heatmap channel = native_owner × 58 + identity; native owner 1 = own).
- Defaults: unit score ≥ 0.4, tower alive ≥ 0.5, event emission ≥ 0.6 (all chosen on validation).

## Weaknesses (most important first)

1. **Domain gap (unmeasured, biggest risk).** These are renderer frames only. The official client's art, HUD and resolution differ.
   The next step is official-frame capture, then a check and fine-tune.
2. **Opponent spells: recall 0.49 at precision 0.75** (thr 0.6), or 0.61 at P 0.42 (thr 0.4). Weak cards: Poison, RoyalDelivery,
   Fireball, Arrows, Earthquake (high FP), Rocket and Lightning (too few samples to learn). Long-lived spells (Earthquake,
   Poison) produce late or duplicate tracks. Only 357 opponent spell events exist in val, so these per-card numbers are noisy.
3. **Swarms and crowds:** one heatmap peak per class per half-tile neighbourhood. Same-class units within ~1 tile merge,
   so recall is 0.31–0.55 for SkeletonArmy, MinionHorde, GoblinGang and AngryBarbarians (precision stays 0.82–0.96). Counts within swarms are
   undercounted. Established single units have ~0.80 recall; units deployed <1 s ago ~0.70.
4. **Card-level identity:** units are labelled by spawning card. Golem and Golemites are both "Golem"; GoblinHut goblins sometimes read
   as GoblinGang (1,255 confusions). hp_frac is relative to that body's own max HP.
5. **Opponent king tower HP while damaged:** MAE 0.137 (p95 0.53) on frames where it is damaged, against ≤0.011 for every other
   tower. Princess towers and our king are accurate.
6. **Hand/elixir at transitions:** ~1–3% of frames around a card play or elixir tick are wrong (steady state 99.5% / 99.4%).
   Gate-level own-hand accuracy (≥99.5%) is met only in steady state.
7. **The event tracker emits once and never revises the card.** On 16 val matches at epoch 20 (thr 0.5), 85 of 140 troop false
   positives were the right place and time with the wrong card. Combining with the body head's identity of the newborn unit
   (units F1 0.84) should fix most of them; not done yet.
8. **Thresholds and stopping were chosen on validation** (exploration tier). The clock output is unreliable (MAE 4.4 s), and phase accuracy is 99.98%.
9. **CPU cost:** the event head costs ~80 ms on 16 fleet threads. On a Mac CPU it would cap the loop well below 10 FPS without MPS or CoreML.

## Reproduce

```
# 127x01, env /mpac/sdicks02/envs/clasher-gpu, code /mpac/sdicks02/repos/clasher-live-perception/live/perception
J=/mpac/sdicks02/jobs/clasher/live-perception-20261014
python dense_labels.py --out $J/labels --workers 11          # train+val labels
python cache_build.py --workers 10                           # pixel caches missing on 01 (228 matches)
python finetune.py  --init $J/ckpt/t7-final/last.pt --out $J/ft-r1 --hours 6 --workers 5   # stopped at 21k steps
python finetune2.py --init $J/ft-r1/stopped-last.pt --out $J/ft-r2 --hours 5.5 --workers 5 --wworkers 8
python eval_val.py    --checkpoint CKPT --out OUT --device cuda --stride 2 --truth dense
python eval_events.py --checkpoint CKPT --out OUT --stride 2
python export_live.py --checkpoint CKPT --output EXPORT_DIR --device cuda
python make_tables.py --frame NAME=metrics.json ... --events NAME=events.json ...
```
