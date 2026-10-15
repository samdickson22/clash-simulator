# LIVE step B: perception (exploration tier), PROGRESS

Owner: step-B perception sub-agent (parent: LIVE LEAD). Started 2026-10-14 ~22:50Z.
Code is in `live/perception/` (branch `live/lead` worktree on 127x05; a synced copy on 127x01 at
`/mpac/sdicks02/repos/clasher-live-perception/`). Job dir on both 01 and 05: `/mpac/sdicks02/jobs/clasher/live-perception-20261014/`.
**HEALDOUT is never read.** Every loader filters episodes through `common.HeldoutGuard` (frozen split.json, sha `3edbd25b…`),
and nothing under a heldout match dir is opened.

## GPU grant

127x01 A6000 granted 2026-10-14T23:01Z for about 10 h (until ~2026-10-15T09:00Z). **Tell the LIVE LEAD when done.**
Rules: ≤16 CPU cores, everything under `nice`; write only to `live-perception-*` job dirs and `repos/clasher-live-perception`.

## Inventory (done)

| item | location / fact |
|---|---|
| split | `127x01:/mpac/sdicks02/repos/clasher-v4-data/registration/v4-registration-460aabbd70b894da/split.json`, sha `3edbd25b…`. It lists 2400 planned matches; the 645 collected match dirs are 513 train / 64 val / 64 heldout (+4 non-split) |
| match data | `127x01:/mpac/sdicks02/repos/clasher-v4-data/matches/<ep>/` (frames, hud, events, objects.jsonl.gz, rich-objects.jsonl.gz, video.mp4) |
| pixel cache | `127x01:/mpac/sdicks02/repos/clasher-v4-cache/<ep>/` holds only **349** of the 577 train/val matches (the formal union was sharded across 01/03/16). The other 228 were built by `cache_build.py` into `JOB/cache/` (pixels only) |
| T7 final (PerceptionV4) | sha `e5d1acd124158dc9410a1f10bb1aaa51b180bc2abd9547da27e66a8da62f7e9c`. Canonical mirror at `127x04:/mpac/sdicks02/repos/clasher-v4-training/checkpoint-mirrors/127x09/t7-formal-20261008-09r2/20261008T173151750416Z/model/last.pt`. Copies at `JOB/ckpt/t7-final/` on 05 and 01, together with epoch-12/18/24, the manifest and the `source/` snapshot |
| "legacy T6" `a3860deb…` | Verified on 04 (`checkpoint-mirrors/127x15/t6-formal-20261008-15r2/20261008T171027126698Z/run/model/last.pt`). It is the **v3 stream model** (`train_l1_stream_v3.py`), not PerceptionV4, so it **can't warm-start V4**. Its 2003/2826 recall and 2003/2523 precision were **play-event** metrics, not body detection |
| T7 vocab | 56 cards; **39 body identities** (no Archer, Knight, Valkyrie, Wizard, Tesla, …), because the formal cleaner only trusts a body when exactly one payload matches its max HP |
| T7 label density | formal unit truth requires a same-tick rich snapshot, and there are only ~42 per match. Result: ~0.07 trusted visible units per frame. **The T7 body head was trained on almost no unit positives**; its final body loss was ≈0.001 |
| own side | the recorded viewpoint is native owner **1** (HUD hand = deck[1]; own king at native y=29, screen bottom) |
| label inputs | gamedata/body-catalog/calibration pinned to the T7 training snapshot (`live/perception/snapshot/`); the repo's `gamedata.json` has drifted since |

## Code

- `common.py`: split guard, cache reader, formal labels, decoding, and `frame_record()` (the downstream schema).
- `dense_labels.py`: dense card-level labels. Every object with HP is labelled with the card it spawned from (card_id), and towers by their anchor. Ghost and unknown ids become ignore regions. Output `JOB/labels/<ep>.npz` (577 done).
- `cache_build.py`: rebuilds the missing pixel caches from video.mp4.
- `eval_val.py`: validation metrics with `--truth dense|formal`.
- `finetune.py`: frame-batch fine-tune of encode() (backbone + body + HUD) on dense labels. Body head = 58 identities × 2 owners, and `body_box[0:2]` is repurposed as a sub-cell offset. Temporal head frozen and untrained.
- `detach.sh LOG CMD…`: setsid + nice launcher on 01.

## Running / done (update every step)

- 23:05Z: T7 eval against formal truth crashed on an uncached val match (superseded; the 1-match smoke result is in `JOB/eval/smoke`).
- 23:08Z: dense labels done (577 npz).
- 23:10–23:35Z: cache build of the missing 228 matches. **Done** (`JOB/cache/`, pixels only).
- **23:13Z: fine-tune `ft-r1` RUNNING** on 01, launched via detach.sh (PID 3866474 = bash wrapper; the python child is in the same session). Run: `--hours 6 --workers 5 --epoch-steps 1500`, ~6 steps/s × 32 frames, est. 105k steps, ends ~05:15Z. Checkpoints `JOB/ft-r1/epoch-N.pt` + `last.pt` (resumable with `--resume`); quick-val history in `JOB/ft-r1/history.json`.
- 23:30Z: **T7 baseline, dense truth, full val stride 2** (`JOB/eval/t7-dense-s2/metrics.json`): hand 97.9%/slot, all4 94.2%; elixir MAE 0.25, int 96.4%; tower HP MAE 0.151, alive 98.4%; units at 0.5: recall 0.3%; best owner-only F1 0.35 (t=0.2, r=1). Reported to the LEAD.
- ft-r1 quick val (16 val matches): epoch 1: unit id F1 0.28; epoch 3: F1 0.58 (P 0.95, R 0.42), tower MAE 0.024, elixir MAE 0.075.
- 23:40Z: T7 rerun with steady-state hand/elixir breakdown (stride 4, offset 1) → `JOB/eval/t7-dense-s4-steady`.

- 23:45Z: ft-r1 epoch-7 full-val check, stride 8 (`JOB/eval/ft1-e7-s8`): tower HP MAE 0.016, alive 99.85%; elixir MAE 0.073, int 97.0% (steady 99.4%); hand 98.5%/slot (steady 99.35%); units id×owner F1 0.73 @0.4 (P 0.90 R 0.61, r=1), 0.54 at r=¼.
- T7 steady-state (`JOB/eval/t7-dense-s4-steady`): hand 98.9%/slot, elixir int 99.1%, so most HUD errors fall within ±150 ms of a change.
- 23:50Z: 05-side mirror loop `JOB/mirror-ft.sh` (05 PID 2979127) pulls ft-r1 every 30 min. **Mirror for ft-r2 still to add.**
- **LEAD priority change (~23:55Z): play events (opponent spells first).** T7 temporal head on 2 val matches: positions roughly right, card identity wrong, scores ~0.3, recall ≈1%.
- 00:03Z: ft-r1 stopped at 21,000 steps (14 epochs; quick val unit F1 0.80, hand 98.9%, tower MAE 0.0087). NOTE: I SIGTERMed a DataLoader worker by mistake. `detach.sh` execs, so **the PID it prints is the python main process**; signal that PID, not a child. Last good checkpoint: `JOB/ft-r1/stopped-last.pt` (= last.pt at step 21000).
- **00:04Z: ft-r2 RUNNING** (`finetune2.py`, python main PID 4120260 on 01): joint body/HUD frame batches + TemporalHead event windows, init ft-r1 stopped-last, 5.5 h, ends ~05:34Z, ~2.7 steps/s, epoch = 1000 steps → `JOB/ft-r2/epoch-N.pt`, history.json (includes window-level event P/R).
- 00:10Z: T7 event baseline full val, stride 2 → `JOB/eval/ev-t7-s2/events.json` (PID 4133403).

- 00:15Z: T7 event baseline, full val (`JOB/eval/ev-t7-s2`): 2,826 truth events, best R 0.09 / P 0.05 (t=0.3). Unusable.
- Export now includes `event.pt` (temporal head) and frame.pt emits `features`. `infer.py:LivePerception` = frame.pt + event.pt + ring + visual births + `events.EventTracker` → `frame_record` with events. Smoke-tested on raw val frames (`test_infer.py`).
- `events.py` EventTracker (location-level, card voted over frames, one emission per track) beats l1_v4.EventFusion. On ft-r2 epoch 5, 8 val matches, W=1 s, t=0.5: all P 0.80 R 0.72; opp spells P 0.83 R 0.47 (fusion: 0.61/0.36 and 0.62/0.19).
- Full val, epoch 5, old fusion (`JOB/eval/ev-r2e5-s2`): opp troop/bldg R 0.92 @t0.3 (P 0.26); spells weak.
- 00:55Z: interim events update sent to the LEAD.

- 02:31Z: ft-r2 epoch 20, **full val** streaming events (`JOB/eval/ev-r2e20-s2`), tracker t=0.5, W=1 s: all P 0.72 R 0.73; opp troop/bldg P 0.83 R 0.84; opp spell P 0.52 R 0.53.
- FP analysis (16 matches): spell FPs = 36 spurious, 29 duplicate/late, 11 wrong card, 6 wrong side. Added a same side+card repeat suppression (3 s, 4 tiles) in EventTracker: no recall loss. At t=0.6, 16 matches: all P 0.88 R 0.76; opp spell P 0.875 R 0.59; opp troop P 0.91 R 0.85. Defaults now: event threshold 0.6, unit threshold 0.4.
- Unit FN analysis (`analyze_fn.py`, ft-r1, 16 matches, t=0.4): recall 0.80 on established single units, 0.70 on units deployed <1 s ago, 0.44 on same-class crowds (merged peaks; representation limit).

- 04:16Z: ft-r2 stopped by plan after its cosine schedule ended (step 40,011): `JOB/ft-r2/final.pt` sha `cba64d2a…`.
- 04:25Z: the LEAD released 01's GPU to the bot lead. **No further GPU training on renderer data** (LEAD decision).
- 04:28Z: final full-val evals done: `JOB/eval/final-dense-s2/metrics.json`, `JOB/eval/ev-final-s2/events.json`.
- 04:29Z: export `JOB/export-final/` (frame.pt `20f77a71…`, event.pt `1f7af56d…`, parity 0.0, latency.json).
- 04:34Z: sample records `JOB/sample-records/` (2 val matches, pred + truth per frame).
- 04:35Z: final checkpoint, exports, evals, sample records and 01 logs copied to 05 (same paths; SHAs verified on both hosts). The 05 mirror loops are stopped.
- RESULTS.md written. **No processes of ours are running on 01 or 05.**

## State: DONE (exploration tier step B)

Next perception step (LEAD): a domain-gap check and fine-tune on official-client frames once the emulator works. Cheap follow-ups
that need no GPU retraining: fuse newborn-unit identity into troop events; count-aware swarm decoding; Mac MPS/CoreML latency.

## Commands

```
# on 127x01
J=/mpac/sdicks02/jobs/clasher/live-perception-20261014; P=/mpac/sdicks02/repos/clasher-live-perception/live/perception; PY=/mpac/sdicks02/envs/clasher-gpu/bin/python
OMP_NUM_THREADS=4 $P/detach.sh $J/logs/eval-X.log $PY $P/eval_val.py --checkpoint CKPT --out $J/eval/X --device cuda --threads 4 --stride 2 --truth dense
OMP_NUM_THREADS=4 $P/detach.sh $J/logs/ft-r1.log $PY $P/finetune.py --init $J/ckpt/t7-final/last.pt --out $J/ft-r1 --hours 5 --workers 11
```
