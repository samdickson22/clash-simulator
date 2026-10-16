# LIVE YOLO synthetic frames: PROGRESS (exploration tier)

Owner: `live-yolo-synth-compositor-opus-r1` (child of LIVE LEAD). Consumer: `live-perc-r3-owner-r1` (YOLO v2 fine-tune on the 04/08
A6000s). Code: clasher-live `live/yolo_synth/` (05 worktree `live/lead`, uncommitted; the LEAD commits). No images or data in git.
Nothing is sealed: numbers are reported as soon as they exist.

## Resume here (state at 2026-10-16T01:55Z)

- **v1 (KataCR cut-outs) bulk run is IN FLIGHT** (launched 01:55Z), all under `/mpac/sdicks02/scratch/yolo-synth/v1/` on each host:
  - **03:** `s03a-00000..00009` (10k pilot, done); `s03b` shards 0:300 (seed 2) and `s03c` 0:300 (seed 3), 32 workers each.
  - **04:** `s04a` 0:200 (seed 4), 32 workers.
  - **08:** `s08a` 0:200 (seed 5), 32 workers.
  - Logs: `/mpac/sdicks02/jobs/clasher/yolo-synth-20261016/logs/<tag>-<a>-<b>.log` on the host. `ALL DONE` is the last line when finished.
  - The 04/08 jobs are one lease of 33 each: the r3 YOLO data loaders on 04/08 take priority. If their GPU util drops (sampled
    `nvidia-smi` average under ~70%), kill our 04/08 job by PID (`ps -o pid= --ppid <cpu_job PID>` first, never `pkill -f`) and move
    the remaining shards to 03.
  - **Expected:** about 1000 frames per 50–60 s per worker; 1.01M frames ≈ 110 GB in total (~66 GB on 03, ~22 GB each on 04/08).
- **Monitor:** Sol worker (codex gpt-6.1-sol, high), thread `thread:delegated-task:command%3Amcp%3A47b1951e-9d6c-4f67-8c7a-804a949ba722%3Adelegate-task%3Ayolo-synth-sol-monitor-r1`.
  It watches v1 to completion (manifest + report to r3 + LEAD), then polls for Null's cut-outs and runs v2. Code changes go back to the Opus owner.
  At 01:57Z shards take ~120 s each under host load (08: 4 done); expect v1 to finish at ~02:15–02:25Z.
- **After it finishes:**
  1. On each host run `cd /mpac/sdicks02/jobs/clasher/yolo-synth-20261016/code && ../venv/bin/python inspect_shards.py manifest
     /mpac/sdicks02/scratch/yolo-synth/v1` to get `v1/manifest.json`.
  2. Report frames, boxes and missing name/team to the r3 owner + LEAD.
- **Next, v2 = Null's cut-outs.** They arrive on 05 at `/mpac/sdicks02/scratch/nulls/cutouts/` (`cutouts.jsonl` + PNG with alpha;
  per card, team, state and frame; scale in official capture px). The directory does not exist yet as of 01:55Z. Steps:
  1. Read a few rows of `cutouts.jsonl`, check that `sprites.py nulls` parses them (fields card|name, team|belong|owner,
     path|file|png, scale), and fix the adapter if the schema differs. The adapter is code: an Opus change, or a trivial
     field-name fix.
  2. For every card body without a KataCR name, append it to the class map:
     `python classes.py append <kebab-name> <Card> troop|building|spell|object <air 0|1>`. Append-only: indices never move.
     Re-sync `classes.json` to the r3 owner and the integration owner.
  3. `python sprites.py BANK nulls /mpac/sdicks02/scratch/nulls/cutouts`, which writes `BANK/sprites-nulls.jsonl` and rebuilds
     `sprites.jsonl` = katacr + nulls. Rsync the bank to 03/04/08.
  4. Generate into a NEW root `/mpac/sdicks02/scratch/yolo-synth/v2/` with new tags. Consider `--weights` to oversample Null-only cards.
  5. Run `inspect_shards.py manifest` and check that every card appears for both teams (`missing_name_team` empty except
     ui/unknown).
  6. Do a visual check on 20 frames (`inspect_shards.py overlay SHARD sheet.jpg`).

## Interface (agreed with the r3 owner, 2026-10-16)

- **Image:** KataCR arena crop **568×896** = capture box x 42.2..674.2, y 31.3..1019.3 of a 720×1280 official capture (scale 0.8987 x,
  0.9070 y; for 1020×1816 captures scale the box by 1020/720 and 1816/1280). The tile grid lands exactly on KataCR `xyxy_grids`
  (6, 64, 562, 864), 18×32 cells of 30.89×25 px (unit test `test_crop_maps_tile_grid_onto_katacr_grid`).
- **Label txt:** `name_idx cx cy w h belong`, normalised to 568×896. `name_idx` = index in KataCR `unit_list` (commit 36ceb9f);
  `unknown` = 155; new names are appended after it. Belong 0 = ours (bottom, blue), 1 = opponent (top, red).
  Plain YOLO id = 2·name_idx + belong.
- **Class map: `live/yolo_synth/classes.json`** (canonical, owned here; built by `classes.py build` from KataCR `label_list.py` +
  `/mpac/sdicks02/jobs/clasher/katacr-20261016/katacr_to_clasher.json`). Per name it gives:
  - `kind`: tower 4, troop 103, building 15, spell 16, object 4, ui 13, unknown 1;
  - `layer`: KataCR draw level;
  - `labelled`;
  - `card` / `identity` / `air`.
  Plus `classes` (id → name, team, card).
- **Labelled:** towers, troops, buildings, spells/projectiles (`spell`/`object`; filter by kind if unwanted). **Never labelled:** bar,
  bar-level, tower-bar, king-tower-bar, clock, elixir, emote, text, background items (blood, flowers, ribbons, …).
- **Box** = tight box of the unit's VISIBLE pixels (z-ordered id map; occlusion by units, bars and badges excluded). This matches the
  r3 hand-label convention (body incl. weapons; badge, HP bar and shadow excluded). Units with less than 30% of their pixels
  visible are removed before drawing.

## Shard layout (what the r3 owner reads)

`ROOT/<tag>-<k:05d>/images/<id>.jpg` (568×896, JPEG q90) + `labels/<id>.txt` + `meta.jsonl` (per frame: id, bg, arena, n, dropped,
damaged, units [name, belong, box px, src, swap, sprite, tile]) + `DONE.json` (frames, boxes, seconds, seed, cfg, weights,
counts per `idx_belong`). A shard is written as `.<name>.tmp` and renamed when complete: a dir without `DONE.json` never exists, and
reruns skip finished shards. Frame RNG = `default_rng([seed, crc32(tag), shard, i])`, so frames are reproducible.
`ROOT/manifest.json`: totals, per-name team counts, missing name/team.

## Design (live/yolo_synth/compose.py)

- **Floors (`prep_bgs.py`):**
  - **Official floors:** frames n0+5 and n0+10 after `match_start` (events.jsonl) of TRAINING-ELIGIBLE runs only. EVAL-SPLIT held-outs
    are skipped: ladder1-r1, live1–5, tc2-r1, s1-m01, s2-m01, s5-m01, s5-m02, s7-m04. So are
    `arena-bgs/goblin-stadium/live1–4*`. Each frame is warped with the crop box and white-normalised (BlueStacks recordings have
    white ~178).
    - All were eyeballed empty. Rejected: s2-m02 (mid-match, level-up banner, damaged towers) and s4-m01 (ruin, unit on the board).
    - **56 official floors:** bone-pit 32 (s6–s10 runs), goblin-stadium 12 (live6–11), barbarian-bowl 16 (s11, s12).
    - Their 6 towers are found by masked template matching against the KataCR tower cut-outs. The matched alpha × floor pixels
      becomes a labelled, depth-sorted tower layer, so units behind a tower are occluded correctly.
  - **KataCR's 27 empty arenas:** towers pasted from cut-outs. King tower, or a ruin at p .04. Queen slot: queen .6, cannoneer .1,
    duchess .1, ruin .2. Tower HP bars as decoration at p .5.
  - **Mix:** official p .6 (Bone Pit ×3 within official), KataCR .4.
- **Units:**
  - Class sampling: uniform over 135 labelled non-tower names that have cut-outs; spells ×.4, objects ×.6, r3 priority bodies ×2
    (`default_weights`).
  - Team: uniform 0/1. If the team has no cut-out, swap the red↔blue accents (p .5, meta `swap`), else fall back to the real team.
  - Placement on KataCR `map_ground` (ground) / `map_fly` (air, spells).
  - Swarms: p .35 per troop pick, 2–9 bodies, σ .8 tile, kept on allowed cells.
  - Bodies per frame: 0 (4%), 1–8 (36%), 8–22 (40%), 22–45 (20%).
  - Per-unit augmentation: scale .92–1.08, h-flip .5, KataCR colour filters (red/blue/golden/white/violet) p .10, ghost/queen
    transparency p .5.
- **Decoration (unlabelled):** HP bar + level badge (team-coloured KataCR cut-outs) only on damaged units (p .35); deploy clock .06;
  elixir pop-up .05; emotes .1; text .015; KataCR background items.
- **Global augmentation:** gain .85–1.15, bias ±12, saturation .8–1.2, hue ±4; down-up resample (.55–.9) p .3; blur p .15;
  noise p .3; **BlueStacks dim** (white 168–190) p .5; JPEG q90.
- **Throughput:** ~21 frames/s per process (1000 frames in 50–57 s on 03 under load); ~110 KB per frame.

## Commands

All run from `/mpac/sdicks02/jobs/clasher/yolo-synth-20261016/` (`venv/` = uv Python 3.11 + numpy, opencv-headless, pillow on
03/04/05/08). `code/` is an rsync of `live/yolo_synth/`; `bank/` is the floor + cut-out bank (115 MB).

```bash
# (05) build / refresh
cd /mpac/sdicks02/repos/clasher-live/live/yolo_synth
W=/mpac/sdicks02/jobs/clasher/yolo-synth-20261016; PY=$W/venv/bin/python; export NUMPY_MADVISE_HUGEPAGE=0
python3 classes.py build                                   # classes.json (append-safe)
$PY sprites.py $W/bank katacr $W/src-data/crdd/images/segment
$PY prep_bgs.py $W/bank --sheet /tmp/bgs.jpg --exclude off-s2-m02-001555,off-s2-m02-001560,off-s4-m01-000008,off-s4-m01-000013
rm -f $W/bank/bgs/off-s2-m02-* $W/bank/bgs/off-s4-m01-*
$PY test_yolo_synth.py                                     # 6 tests
rsync -a --delete --exclude __pycache__ ./ $W/code/
for h in 127x03 127x04 127x08; do rsync -a --delete $W/code $W/bank $h:$W/; done
# (any host) one leased, niced, detached job: OUT TAG A:B WORKERS [gen_shards args]
ssh 127x03 $W/code/run_host.sh /mpac/sdicks02/scratch/yolo-synth/v1 s03b 0:300 32 --seed 2
# progress / manifest / overlay sheet
ssh 127x03 'grep -c frames /mpac/sdicks02/jobs/clasher/yolo-synth-20261016/logs/s03b-0-300.log'
ssh 127x03 'cd /mpac/sdicks02/jobs/clasher/yolo-synth-20261016/code && ../venv/bin/python inspect_shards.py manifest /mpac/sdicks02/scratch/yolo-synth/v1'
ssh 127x03 'cd .../code && ../venv/bin/python inspect_shards.py overlay /mpac/sdicks02/scratch/yolo-synth/v1/s03b-00000 /tmp/ov.jpg --n 20'
```

`run_host.sh` = `setsid nohup nice -n 19 env NUMPY_MADVISE_HUGEPAGE=0 PYTHONHASHSEED=0 bot/exit/cpu_job.sh (WORKERS+1) gen_shards.py …`,
and it prints the PID. Use distinct `--seed` and tag per job; the same tag + seed + shard reproduces the same frames.

## Rules

- **Hosts:** 03/04/08 only, always via `cpu_job.sh`, `nice -n 19`, `NUMPY_MADVISE_HUGEPAGE=0`. Check `who`; go lighter if someone is at
  the console.
- **04 and 08:** at most one 32-worker lease each (r3 training loaders first).
- **Disk:** ≤300 GB per host under `/mpac`.
- **Never touch:** 03's T1 corpus, `k4s-end-r1`, 08 `v4-b-20261012-r1`, `t1-*`, hosts 09–18, tailscale, crontab. Kill only our own
  PIDs.
- **Held-out data:** never use frames of EVAL-SPLIT held-out battles (any role).

## Log

- 2026-10-16T01:35Z start. KataCR segment set: sparse clone of `wty-yy/Clash-Royale-Detection-Dataset` @31b4151 (MIT) `images/segment`
  → 05 `/mpac/sdicks02/jobs/clasher/yolo-synth-20261016/src-data/crdd/`. It holds 4,622 cut-outs over 154 dirs, at KataCR crop scale.
  Belong 0 = blue/ours (back view), 1 = red/opp (front view), confirmed by eye. About 110 classes have one team only (mostly opp).
- Interface agreed with the r3 owner (above).
- Floors built: 56 official (training-eligible only) + 27 KataCR; tower template boxes checked by eye on all of them.
- Compositor + tests (6 pass). Visual checks on 30 frames (boxes, depth order, damaged-only bars, dim, swaps).
  - Fixed: swarm bodies in the river / off-map; big-text too frequent; spell overlays too frequent (weights).
  - Team swap is plausible but leaves artefacts on warm skin (hog-rider's mouth) → swap p .5, flagged in meta.
- **10k pilot** (`v1/s03a-*`, 03): 10,000 frames, 162,820 boxes (16.3 per frame), 139 names with boxes. Floors: bone-pit 4,480, KataCR
  4,019, barbarian-bowl 869, goblin-stadium 632. Unit boxes: 106,537 real-team KataCR + 20,403 team-swapped; 35,880 floor towers.
  - Names never boxed: mirror, tesla-evolution-shock, zap-evolution (no cut-outs).
  - Least frequent: dirt, mortar, elixir-collector, rage, tesla-evolution, giant-snowball, freeze (~500 each).
  - 1.1 GB per 10k.
- **Card coverage vs our 144-card gamedata list:** 102 cards map to a KataCR body via `katacr_to_clasher.json`.
  - Of the rest, multi-body cards are covered through their body (GoblinGang, SkeletonArmy, MinionHorde, IceSpirits,
    RoyalRecruits, ThreeMusketeers).
  - Truly missing: newer cards (GoblinDemolisher, GoblinMachine, Goblinstein, Berserker, BossBandit, SuspiciousBush, MergeMaiden,
    Vines, GoblinCurse, DarkMagic, …) plus event variants. These come with Null's cut-outs (v2).
- 01:55Z bulk v1 launched (03 s03b/s03c 0:300; 04 s04a 0:200; 08 s08a 0:200). r3 owner told the paths and format. The 04/08 GPUs
  were at 88–95% at launch.
