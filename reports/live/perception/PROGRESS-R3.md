# LIVE perception round 3: units on the official client, PROGRESS (exploration tier)

Owner: `live-perc-r3` sub-agent (parent: LIVE LEAD), 127x05 worktree `live/lead`; code `live/perception/r3/`.
Scratch (05): `/mpac/sdicks02/scratch/live-perc-r3/`. Jobs (01): `/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/`.
Never commit images or video. Heldout never opened (HeldoutGuard on every renderer loader).

## HANDOFF (state 2026-10-16T07:05Z; owner live-perc-r3, Opus; keep this current)

### Standing duties (survive restarts)
1. **YOLO candidate gates** (LIVE LEAD, accepted 2026-10-16 ~07:00Z), all on EVAL-SPLIT held-out (227 frames incl. s19-m01/m02), thr .5,
   ≤1 tile: (a) owner: enemy→ours ≤ 3% overall AND per building class (`yolo/owner_eval.py`); (b) friendly UNDAMAGED recall ≥ .75 and
   (c) swarm per-body recall ≥ .80 for ours and for opp (`yolo/damage_recall.py --labels labels --damaged damaged`, damaged flags =
   label `damaged` or Sol side files `scratch/live-perc-r3/damaged/<ID>.json`); plus id P/R not worse than v2l-e11 per arena incl. BB,
   0 empty-frame FPs. The moment a run clears all: send the candidate record (weights + sha256, imgsz, classes, offsets, thr, numbers) to the
   LIVE LEAD, babysitter `live-ladder-babysitter-sol-r1` and `live-yolo-integration-opus-r1`.
2. **Dense-frame weakness audit** (Sam, via LIVE LEAD 2026-10-16): every live session, or ≥ every ~3 h while the ladder runs.
   - Sample: `yolo/audit_dense.py scan` (current best YOLO on every 4th battle frame of recent sessions, GPU host) → `sheets` (dense set =
     top 15% per battle by YOLO unit count + overlapping pairs; seeded random 30–50 frames; sheet = clean | live-log units (the model that
     played) | YOLO boxes) + held-out replay frames through the current best YOLO candidate.
   - Review: a Sol helper lists every miss, merge, wrong owner, wrong class and phantom per frame; I review its summary.
   - Output: `reports/live/perception/WEAKNESSES.md`, newest first, UTC: weakness list with counts; each item gets a DATA fix
     (targeted synthetic, Null's captures, or hard-example labels from these frames) and, if it recurs, a new eval slice that joins the gates.
   - No images in git (overlays stay in `scratch/live-perc-r3/audit-*`). No hand-coded rules: fixes go through data or the model; a
     post-processing setting may be tuned on eval data.
3. Every Sol helper/monitor question goes up via `t3_thread_send`; give Sam times in PT.

**Candidate sent 07:09Z: `yolo-v4lo1024-e16`** (gates PASS; stripped sha256 b1d02445…; imgsz (1024,672)). Integration: CoreML fp16
1024×672 parity 756/756, Mac ANE p50 36 ms; deploys only with the fixed letterbox in `live/perception/yolo_units.py` (ultralytics
LetterBox upscales 568×896 → 649×1024; the old adapter capped scale at 1).

**07:05Z state:** live = r5e3 → **ft-r6 e31** at the next boundary (owner check passed: enemy→ours 0/168 vs r5e3 0/158). YOLO runs: 08
V4lo (owner .039, Cannon 0/14) → queued **V6lo** (init V4lo-e14; KataCR real cut to `katacr-part2-bal2.txt` .05; picks up
`lists/hard-owner2.txt` = mirror + own-deploy labels when converted); 04 V4lo1024 (eval loops fixed 06:50Z; old evalloop ignored imgsz);
01 **V5ext** (box-up .5) since 06:44Z. Sol labelling (05 scratch): hard2-1..3 (mirror battles, `OWNER-HARD2-BRIEF.md`, 120 frames),
own-1..4 (s20–s22 own deploys, `OWN-DEPLOY-BRIEF.md`, 160), dmg-1/2 (damaged flags on eval truth, `DAMAGE-FLAG-BRIEF.md`, 178). When
they land: `official_to_cr.py` on `labels-yolo-raw/{HARD2,OWN}-*` (index `label-hard2`, `label-own`) → `$J/lists/hard-owner2.txt` on
04/08/01 (+ tower pseudo-labels as `convert_hard.sh`), and re-run `damage_recall.py`. Compositor v1team3 (official art at equal per-class
rate on both teams) → add `synth-team3-<host>` lists to the next runs.

**03:25Z update:** LIVE = `yolo-v2l-e11` (deployed at s19). V2m finished (40 ep, late epochs GS P .92, empty FP .22 → not used).
**Keep-alive queues:** `$J/queue.sh` on 04 and 08 runs the scripts listed in `$J/queue/<hostname>.txt` back-to-back (log `$J/logs/queue.log`;
done markers `$J/queue/done/`). 08: **V3l** (init V2l epoch 24 `$J/candidates/v2l-e24.pt`, BB-heavy synth + official incl. BB, 12k/epoch,
30 ep, lr 3e-4) started 03:15Z, eval loop `evalloop.sh v3l`. 04: V2l (to ep 40) → **V3l1024** (same init, imgsz 1024, eval with
`--imgsz 1024,672`). Add the next run = append a script path to the host's queue file. Sol `yolo-gpu-watch-sol` watches GPU idle (>10 min),
health and candidates until ~07:30Z. V1c on 01 after ft-r6: data pre-staged on 01 (`$J` copy from 04 + 150 s03b shards in `$J/synth-extra`).


J=`/mpac/sdicks02/jobs/clasher/live-yolo-20261016` (same path on 05 master, 04, 08). Env on 04/08: `. $J/env.sh`. Code: clasher-live
`live/perception/{r3,yolo}/` (rsync to `$J/code/live/perception` on the host after edits; jobs read code at start, lists live).

**Running jobs (all setsid; stop = `kill -TERM -<PGID>`, never `pkill -f`):**
| host | job | PGID | log | outputs |
|---|---|---|---|---|
| 04 | YOLO **V2l** (yolov8l, init V1a ep11) via `cpu_job.sh 12 $J/run-v2l.sh` | 2693417 (cpu_job) | `$J/logs/v2l.log` | `$J/runs/v2l/weights/{epochN,last,best}.pt` |
| 04 | eval loop v2l | 2681754 | `$J/logs/evalloop-v2l.log` | `$J/evals/v2l/epochN.json` |
| 08 | YOLO **V2m** (yolov8m, init V1b ep9) via `cpu_job.sh 12 $J/run-v2.sh` | 2750934 | `$J/logs/v2m.log` | `$J/runs/v2m/weights/` |
| 08 | eval loop v2m | 3263060 | `$J/logs/evalloop-v2m.log` | `$J/evals/v2m/` |
| 04, 08 | `synth_list.sh` (rebuilds `$J/lists/synth-<host>.txt` from complete shards every 5 min) | 2521530 / 2698010 | `$J/logs/synth_list.log` | |
| 01 | ft-r6 (round-3 model + any-unit head), PID 2814805 | 2814805 | `/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/logs/ft-r6.log` | `…/ft-r6/epoch-N.pt`, ends ≈04:10Z |
| 05 | ft-r6 mirror (856471) + official-set eval loop (662622) | | `scratch/live-perc-r3/{mirror,evals-r6}/` | |

**YOLO recipe** (`live/perception/yolo/train_cr.py`, KataCR CRDetectionModel = ultralytics 8.1.24 fork; nc 156 = KataCR unit_list 155
+ team channel 'padding_belong'): input KataCR crop 568×896 (capture 720×1280 box x 42.2–674.2, y 31.3–1019.3); `--share` lists:
compositor synth v1 (`/mpac/sdicks02/scratch/yolo-synth/v1/*` + `$J/synth-extra`, 600k+ frames, MIT KataCR cut-outs on official floors)
.55, official (`$J/lists/official-train.txt`: 190 hand-boxed training-battle frames + 60 empty arenas + tower pseudo-labels) .30, KataCR
part2 real .15; p_real .8 (rest = KataCR on-the-fly generator); AdamW 4–5e-4 cosine, 6000 frames/epoch, 40 epochs, batch 16, 10 loaders.
**V1c plan (01 after ft-r6):** same mix, init = best of V2l/V2m.

**Gate + eval:** `eval_yolo.py --weights W --katacr-src $J/katacr-src --labels $J/eval/labels --index $J/eval/index.json --empties
$J/eval/empties.txt --offsets $J/ground-offsets.json --out OUT.json` (EVAL-SPLIT.md held-out: 148 frames/518 units + 18 empties;
sprite-level identity, ≤1 tile; table: `yolo/yolo_table.py NAME=OUT.json`). **Live-trial bar:** identity P ≥ .90 at thr .5 on GS and BP
with recall above ft-r5 final (GS .440, TC .485, BP .388) and ≤ .1 false units per empty frame.

**Candidate record** (to the Sol babysitter `live-ladder-babysitter-sol-r1` + LIVE LEAD + `live-yolo-integration-opus-r1`): weights path +
sha256, input/crop + imgsz (896,576), head layout (channels 0..154 names, 155 team), `live/yolo_synth/classes.json`, `$J/ground-offsets.json`,
threshold, EVAL-SPLIT P/R per arena vs ft-r5 final.

**ft-r6 export (01, after it ends ≈04:10Z):** pick the epoch on `scratch/live-perc-r3/evals-r6/` (GS P ≥ .95, max GS+BP recall), then on 01
`cd /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/code-any/live/perception && NUMPY_MADVISE_HUGEPAGE=0 python export_live.py
--checkpoint CKPT --output …/export-ft-r6 --device cuda --cpu-threads 4,2`; full renderer evals `eval_val.py --device cuda --stride 2
--truth dense` + `eval_events.py --stride 2`; rsync export to 05; send record (path, frame/event/vocab sha256, thr .5, P/R vs r1/r5) to the
babysitter + LEAD; `unknown_units` is an additive record key. Then 01's A6000 → YOLO V1c.

**Labels:** all 208 new-card training frames boxed (`scratch/live-perc-r3/labels-yolo-raw/`, Opus yb1–7 + Sol ybs1–3); converter
`yolo/official_to_cr.py` → `$J/official-cr/`; towers `yolo/pseudo_towers.py`. Held-out truth: `scratch/live-perc-r3/labels/`.
**Rules:** never train on EVAL-SPLIT held-out battles; 04/08 CPU via `/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh N`, niced,
NUMPY_MADVISE_HUGEPAGE=0; don't touch bot-lead processes or 03's T1 corpus / k4s-end-r1 / 08's v4-b-20261012-r1 / t1-*; GPUs 04+08 (+01 after
ft-r6) are YOLO's for the 12–24 h window.
**Queued:** hand-icon head for all 122 cards incl. greyed state (needs official icons: Null's / deck-screen captures; KataCR's card set has
only 12); round-4 sprite-level classes; unknown-class follow-up.

## Resume here (round 3, older) (state at 2026-10-16T00:15Z)

- **UPDATE 00:25Z:** ft-r5 stopped after epoch 8 (plateau; LEAD-approved). **ft-r5 final = epoch-3 = `export-interim-r5e3`** (sent).
  **ft-r6** (= ft-r5 e3 + AnyTroop/AnyBuilding head, `--any-unit`) on 01, PID **2663210**, log `…/logs/ft-r6.log`, code `…/code-any/`,
  3.9 h / 40k steps → ~04:20Z. Mirror/eval loops now follow ft-r6 (05 PIDs 856471 / 856473, `evals-r6/`). The ft-r5 lines below are history.
- **Training (history):** ft-r5 on **127x01** A6000, PID **2425017** (setsid via `live/perception/detach.sh`), log
  `01:/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/logs/ft-r5.log`, out `…/ft-r5/epoch-N.pt` every 1000 steps (~2.9–3.3 steps/s),
  deadline 4.8 h from 23:31Z (≈04:19Z), cosine horizon 60k steps. Code snapshot `…/code-next/` (= `live/perception` incl. `r3/`).
  GPU window on 01 until ~06:00Z, then the bot lead owns 01. Stop cleanly: `kill -TERM 2425017` (saves final.pt after a quick val),
  then kill its loader children by PID (`ps -o pid= --ppid 2425017` first). Never `pkill -f`.
- **Mirror + scoring on 127x05:** `scratch/live-perc-r3/mirror.sh` (PID 3116421, pulls `ft-r5/*.pt` + logs every 5 min into
  `scratch/live-perc-r3/mirror/`) and `evalloop.sh` (PID 3116423, scores each mirrored epoch → `scratch/live-perc-r3/evals-r5/epoch-N.json`);
  both stop by themselves ~07:30Z. Table: `python3 live/perception/r3/sweep_table.py NAME=evals-r5/epoch-N.json …`.
- **Eval sets (05 `scratch/live-perc-r3/`):** `labels/` (99 frames / 332 units: GS 48/159, TC 26/97, BP 25/76; 7 excluded; images stay in
  scratch, never committed), `label/index.json` (frame → source jpg), `empties.txt` (18 verified empty frames: TC 4, GS 9, BP 5).
  Score any checkpoint/export: `eval_official.py --ckpt X.pt | --export DIR --labels labels --out OUT.json --empty $(cat empties.txt)`.
- **Exports sent to the loop owner** (thread `…delegate-task%3Alive-loop-owner-r1`, copy LIVE LEAD; include path on 05, frame/event/vocab
  sha256, threshold, official GS P/R vs round 1, interface note): `export-interim-e1` (ft-r4 e1), **`export-interim-r5e3`** (ft-r5 e3,
  live candidate). Export: on 01 `cd …/code-next/live/perception && NUMPY_MADVISE_HUGEPAGE=0 python export_live.py --checkpoint CKPT
  --output …/export-NAME --device cuda --cpu-threads 4,2`, rsync to the same path on 05, re-score the export with `eval_official.py --export`
  (must equal the checkpoint's metrics).
- **Rules:** never heldout (HeldoutGuard); ≤16 loader cores on 01; `NUMPY_MADVISE_HUGEPAGE=0`; write only `/mpac/sdicks02/jobs/clasher/live-*`
  on 01; don't touch the bot lead's processes/dirs; copy checkpoints off-host; never commit images/video.
- **Open:** (1) final ft-r5 pick + export + threshold re-sweep + full renderer `eval_val.py --device cuda --stride 2 --truth dense` and
  `eval_events.py --stride 2` (round-1 numbers in RESULTS.md) → RESULTS-R3.md; (2) any-unit class (`finetune_r3.py --any-unit`, smoke-tested;
  decode in `common.py`, additive `unknown_units`), needs ~2–2.5 GPU h; (3) new identities per `reports/live/loop/ARENA-CARDS.md` priority;
  (4) sprite-level body classes (round 4).
- **Observation 00:10Z:** ft-r5 official metrics plateau from epoch 3 (GS .44–.44 recall at P ~.95; TC .45–.52; BP .33–.40); renderer quick
  val flat (unit F1 ~.82, events ~.92/.71).

## Log

- 2026-10-15T22:50Z **Diagnosis of "zero units" (CPU, deployed export-final, frames 540x1140 via live/loop/canvas.py).**
  Scripts: `r3/diag_zero.py`, `r3/paste_test.py`; outputs in 05 scratch `diag-zero.json`, `paste/paste.json`.
  - (a) **Pipeline: no bug found.** Recorder and driver both deliver BGR (bsgrab 32BGRA → [:,:,:3]; cv2.imread for replays).
    canvas() maps official → canvas with the inverse warp (official = 1.806·canvas + t in Android px = 0.903 at 540 width),
    so the official arena is scaled UP by 1/0.903 onto the canvas; the renderer tile grid overlaid on the mapped frames lands on
    the same tower/bridge/river cells (renderer, Goblin Stadium, Training Camp). The same prepare_pixels → /255 float path
    is used for both. Arena mean BGR renderer (120,152,197) vs official (77,159,143), std 56 vs 33–42: a colour/content shift, not a range or channel bug.
  - (b) **Not zero: sub-threshold.** Max unit-heatmap score per frame: renderer .89–.95 (10–22 cells ≥ .5); official ladder
    .28–.72 (0–2 cells ≥ .5, 6–21 ≥ .2); Training Camp .44–.66. The peaks that exist sit on the real units but often with the wrong identity
    (opp Giant at our tower: Giant .72 in one frame and sub-.5 in others; our Knight in TC → "DarkPrince" .66). Fixed-position
    phantoms from arena decor reach .3–.4 in every frame (Goblin Stadium: "Balloon" at (16.3, 19.2) native; TC fences: "GoblinHut" .3–.39),
    so simply lowering the threshold is not safe.
  - (c) **Sprite art/size: same family.** After mapping, tower and unit sizes match the renderer's; units carry the same
    level badge + HP bar (blue own / red opp). Differences: grass vs sand floor, level badges 1–4 vs 11, newer art for a few cards.
  - (d) **Paste test: context, not sprites, kills the score.** Identical renderer pixel rectangles (incl. their own sand patch)
    pasted at the same canvas coordinates into an empty Goblin Stadium frame: Goblins .95/.93/.88 → .45/.40/.40; Rascals-area
    units .87/.80 → .29/.28. Reverse: the official Giant crop pasted onto a renderer frame drops .72 → .26. The heatmap is strongly
    conditioned on the surrounding arena (large receptive field), so any new arena skin collapses calibration.
  - **Conclusion:** domain shift of the scene context, not a pipeline bug; there's no free fix for the loop owner's mapping (it is correct).
    Round 3 = background-invariant compositing (renderer unit pixels onto many backgrounds: official arenas, renderer skins,
    random textures, strong colour jitter), validated on hand-labelled official frames plus a held-out arena (Training Camp held out).
- 23:04Z **GO (LIVE LEAD).** 01 A6000 granted 22:49:20Z (window to ~06:00Z, ≤16 loader cores).
  - Data: `r3/prep_bg.py`: 577/577 train+val matches have an empty match-start frame (frame 0) → `JOB/bg/<ep>.png`; the renderer
    has ONE arena skin (sand); ~1/4 of start frames carry replay-control overlays → `bg/template.png` = median of 120 starts.
    `r3/prep_official.py`: 8 Goblin Stadium floors (loop owner's 7 arena-bgs, 720x1280 + 1020x1816, + ladder1 f255) → `JOB/official-bg.npz`.
  - `r3/finetune_r3.py` (= finetune2 joint run + per-frame compositing on the GPU): kinds plain .30 / official .30 (half recoloured) /
    hardneg .06 (empty official floor, no units) / recolour .14 (own floor hue/sat/val/contrast shifted) / texture .20 (procedural floor
    + template towers). Unit mask = (|f−bg|>.08)&(|f−template|>.08)&label boxes, closed 3x3, feathered. Non-plain frames: tower targets
    = 6 alive full HP. Stronger resolution loss (45% of frames at .45–.7 scale, matching the 720x1280 capture). Training Camp never a floor.
    Dumps checked by eye (no sand halos after the mask fix; towers cut by colour, not rectangles).
  - 22:59Z launched ft-r4 (init ft-r2/final cba64d2a, 5 h). 0.8 steps/s: event-window loaders saturated → killed (PIDs) and relaunched
    23:05Z with 6 frame + 9 window workers, 4 windows/step (PID 2307911). Mirror 01→05 every 5 min: `05 scratch/live-perc-r3/mirror/`.
  - Init (= round 1) quick val: hand .9905, elixir MAE .057, unit id P/R .952/.762, owner F1 .869, tower MAE .0061, event window P/R .915/.742.
  - Labelled official set: 81 sheets (51 Goblin Stadium from ladder1 + live1–5, 30 Training Camp from tc2), 5 Opus helpers (high effort,
    brief `scratch/live-perc-r3/LABEL-BRIEF.md`), per-frame confidence + exclusion; I verify samples.
  - Empty official frames (verified by eye): TC 265/270/275/1180, GS live5 280–300 (match not used for floors), ladder1 262/275, live1 318,
    live4 350. Round 1 at thr .5: **TC 1.0 false units/frame** ("BombTower" under the opp king tower, .61–.65), GS 0 (.3: 1.0–1.6/frame).
- 23:11Z 23:07Z relaunch #3 (cosine horizon was set from a rate that included the init val → --max-steps 60000, t0 after
  init val; PID 2322178). ~4 steps/s steady (2.66 at step 150 incl. warmup) → ~03:35Z.
  - **Labelled official set done.** 5 Opus helpers, 81 frames; verified by overlay on 12 frames (owners by badge colour, identities, feet
    positions all plausible) and the renderer's own truth convention checked on renderer frames (truth = feet; flying units = shadow
    below the body, as the helpers did). Exclusions: helper 1 (GS-live4-426, crowded deploys), verifier 6 (TC 260 intro camera; TC 870/1560/1590
    and GS-live1-803 game-end camera shift; GS-live4-370 translucent placement preview). **Eval set: 74 frames (48 GS, 26 TC), 256 units
    (159 GS, 97 TC), all in the C56 vocabulary**; frame confidence GS 15 high / 32 medium / 1 low, TC 12 / 12 / 2; unit confidence
    138 high / 105 medium / 13 low. Label files: 05 `scratch/live-perc-r3/labels/` (`finalize_labels.py`).
  - **Round 1 on the official set** (`r3/eval_official.py`, export-final, thr .5, ≤1 tile): GS id×owner P/R **.833/.063**, owner-only .833/.063;
    TC .176/.031 (owner .353/.062). Thr .4: GS .615/.101.
  - 05 `evalloop.sh` scores every mirrored epoch on this set + the empties.
- 23:21Z **Interim export e1 sent to the loop owner** (Sam's request): `JOB/export-interim-e1/` on 01 and 05, frame.pt 9b06f968…,
  event.pt cc75886f…, from ft-r4 epoch-1 81c9f1c5…; renderer parity max err 0.0; official-set metrics identical to the checkpoint.
  Official set, thr .5: GS P/R .975/.245 (r1 .833/.063), TC .926/.258 (r1 .176/.031), empty-frame false units 0 (r1 TC 1.0/frame).
  Renderer quick val e1: unit F1 .816 (r1 .846), events .898/.684 (.915/.742), tower MAE .011 (.006). Trainer PID 2322178 is the only one;
  GPU 62–83% over 8 s.
- 23:31Z **LEAD checks (threshold sweep, resolution) + badge finding → restart as ft-r5.**
  - Sweep, ft-r4 epoch-3, official set (≤1 tile; GS id P/R, FP/frame on labelled frames): .30 .679/.478 (.75); .35 .774/.453 (.44);
    .40 .840/.396 (.25); .45 .875/.352 (.17); .50 .911/.321 (.10); .60 .974/.233 (.02). Empty official frames: GS 0 at every thr;
    TC .75/frame at ≤.45, 0 at .50. Owner-only at .5: .946/.333 → misses are non-detections, not identity errors. Median position
    offset of matched detections dx 0.0, dy −0.05 tiles; ≤1.5 tile adds ~1–2 pp → no label-convention bias.
    The ABLATION proxy (.230·R − .128·phantoms/frame) is flat over .40–.50 (.059/.059/.061) → **recommend .5** (unchanged; zero
    empty-frame decor FPs on TC at .5); re-sweep on the final model.
  - Resolution probe (`r3/res_probe.py`, renderer val, 8 matches, arena input degraded to each capture path; factor 1.0 renderer,
    .85 ≈ official native 1020x1816, .60 ≈ official 720x1280): r1 R .745/.746/.746, ft-r4 e3 .719/.714/.718; Archers .79–.83 at every
    factor. **Capture resolution is not what limits small units** (the 448-px model input is coarser than either capture path).
  - **Cause found: level badge + HP bar.** The renderer draws badge ("11") + HP bar over EVERY unit; the official client draws none on
    full-HP units (only once damaged). Side-by-side crops: the missed official Archers/Minions/Knights are the badge-less ones. The
    model keys on the badge. Fix (`CompBlocks.unit_mask`): unit masks built on the CPU loaders; with p=.6 per unit the top 16 px band
    of its mask (badge + bar) is dropped (composites) or repainted with the match-start floor (plain frames).
  - 23:31Z ft-r4 stopped at step 4000 (PIDs); **ft-r5** from ft-r4 epoch-4 (PID 2425017, code `JOB/code-next`, 60k steps / 4.8 h cap,
    badge_p .6). Mirror + eval loops restarted for ft-r5 (`scratch/live-perc-r3/evals-r5/`); ft-r4 evals in `evals-r4/`.
- 23:44Z **Bone Pit = second unseen arena** (LEAD; not in training). Run `runs/s1m01` on 05 is a Bone Pit battle (sand, 300 trophies,
  868 frames, battle from f238). 25 sheets (f262–850) → 2 Opus helpers (lab-bp1/2; deck read from each frame's hand). Empty BP frames
  236/240/245/250/255 added to the empty set; round 1 gives 0 false units on them at every threshold (sand ≈ renderer floor).
  `eval_official.py`/`sweep_table.py` report BP separately.
- 23:55Z Bone Pit labels done (lab-bp1/2; 25 frames, 76 units, 0 excluded; verifier relabelled bp1's "GoblinHut" 532/556 →
  OOV:BarbarianHut (same building as bp2's 580–728, spawns a Barbarian) and bp2's low-conf 850 building → UNKNOWN). Eval set now
  **99 frames / 332 units** (GS 48/159, TC 26/97, BP 25/76). Round 1 on BP at .5: .750/.200 (owner .960/.316): less blind on sand, as the LEAD expected.
  - **ft-r5 (badge strip) works:** epoch-3 at .5 GS .959/.440, TC 1.000/.485, BP .857/.400 (e1: .975/.245, .926/.258, .842/.267); empty
    frames 0 false units everywhere. Renderer quick val step 3000: unit F1 .828, events .912/.706, tower .009, hand .9897.
  - **Interim 2 exported + sent to the loop owner** (copy LEAD): `JOB/export-interim-r5e3/` frame.pt 81697f5b…, event.pt 638276a0…,
    vocab.json d39b06bb… (byte-identical to e1), ckpt 1f227f9b…; parity max err 0.0 (renderer) and identical official metrics; thr .5.

## Next: off-vocab units (coordinator priority, 2026-10-16) — design

**A. Unknown troop / building ("any-unit" objectness), run after ft-r5.**
- Two identities appended AFTER the towers: `AnyTroop` (58), `AnyBuilding` (59). C56 card ids and KingTower/PrincessTower keep
  their indices; hand/event heads (56 cards) are untouched. Body heatmap goes 2×58 → 2×60 channels (new channels init bias −4,
  all old channels copied by name).
- Training: every body is positive for its card channel AND for AnyTroop/AnyBuilding (by card type; buildings = BombTower, Cannon,
  FirespiritHut, GoblinHut, InfernoTower, Tesla, Xbow). Same compositing/badge-strip recipe as ft-r5.
- Decode (`common.decode_frame`, backward compatible, active only when the vocab has `Any*`): an Any* peak with no same-owner card
  peak ≥ the unit threshold within 1 tile → `unknown_units: [{owner, kind: troop|building, x, y, score}]`. **`units` is unchanged**,
  so the translator sees nothing new until it opts in to the extra key.
- Eval: official hand labels' OOV/UNKNOWN entries (BP: BarbarianHut ×~9, GoblinCage ×4, GoblinBrawler, Barbarian, 1 UNKNOWN) →
  unknown-class P/R (same owner, ≤1 tile); plus any-unit owner-only P/R over all labelled units; plus "known unit reported as unknown"
  rate. More OOV examples: label further Bone Pit battles as they're recorded.
- Generalisation question (does objectness fire on sprites it has never seen?): measured directly on the official OOV labels; if
  weak, variant B' holds a card subset out of identity training (objectness-only positives) so "unit without identity" is learned.
- GPU: ~2 h fine-tune from ft-r5 final + ~0.5 h eval/export.

**B. Body class per sprite (round 4, not this run; LEAD/loop owner note).** Detection classes = sprites (Skeleton, Goblin,
SpearGoblin, Minion, Barbarian, …) from the labels' `body_name`; the card is inferred at spawn (event head / translator burst).
Removes the Skeletons/SkeletonArmy, Goblins/GoblinGang, Minions/MinionHorde coin flips for lone bodies. Needs a sprite→card table
agreed with the translator owner.

**C. Specific identities for frequent missing cards.** Renderer has no examples, so: rank OOV cards from the loop owner's Battle-Log
inventory (`reports/live/loop/opponent-decks.jsonl`) × arena card lists; first candidates from what we've seen: BarbarianHut (+Barbarian),
GoblinCage (+GoblinBrawler), Bomber, Barbarians, Tombstone, SpearGoblins, MegaMinion. Data path: AnyTroop/AnyBuilding detections on
official recordings + the opponent deck from the Battle Log → label proposals → Opus-verified; then cut each verified sprite from its
frame (diff vs the match's empty-arena frame) and composite it like the renderer units (floors, badge strip, jitter) → tens of real
sprites become thousands of training frames. Target ≥ 30 verified instances per card before adding its identity.
- 00:25Z Epoch-8 scored; ft-r5 SIGTERM'd (final.pt saved after its quick val; 15 loader PIDs killed; 0 left). Selection (GS P≥.95
  at .5, max pooled GS+BP recall): e3 .429 vs e5 .411, e7 .402, e8 .393 (e4/e6 fail P). **ft-r5 final = e3** (= interim 2), record sent to the
  loop owner (copy LEAD). ft-r6 launched from e3 with `--any-unit` (PID 2663210). ft-r5 epochs + final.pt mirrored to 05.
- 00:47Z ft-r6 epochs 1–2 (thr .5): GS id .925/.390 → .915/.409 (r5e3 .959/.440), TC .958/.474 → 1.0/.495, BP .786/.367 → .821/.383;
  unknown class on BP OOV (16 units): e1 TP 9 / FP 9 / FN 7, e2 2/8/14; of all unknown "FPs", 28–30 of 29–33 sit on in-vocab units whose card
  score is below threshold (unidentified, not phantoms); any-unit owner-only P/R e2 .970/.392. Renderer quick val e2: unit F1 .820,
  events .900/.676. Empty frames: 0 false units at .5 everywhere.
  - More OOV truth: 3 new Bone Pit battles on 05 (s2m01, s5m01, s5m02); 36 uniformly sampled frames → lab-bp3/bp4 (Opus, OOV naming list).
- 01:02Z Labels: lab-bp3/bp4 done (36 BP frames; 1 excluded end-of-game). **Eval set now 134 frames / 472 units: GS 48/159, TC 26/97,
  BP 60/216 incl. 32 off-vocab** (BarbarianHut 14, GoblinCage 8, Tombstone skeletons 6, GoblinBrawler 3, UNKNOWN 1). Re-scored at .5:
  r1 BP .791/.185, r5e3 BP .818/.342 (GS/TC unchanged).
  - ft-r6 was loader-bound (frame workers 82% CPU with CPU masks, 1.8–2.5 steps/s → would stop at ~25k of 40k steps, LR not annealed).
    01:00Z killed by PID (2663210 + children), renamed to `ft-r6a`, relaunched **ft-r6 from ft-r6a epoch-4** with 9 frame / 6 window
    workers, 3.35 h / 34k steps (PID **2814805**, ends ≈04:22Z). 05 mirror ft-r6a → `mirror/ft-r6a`, evals `evals-r6a/`; new run → `evals-r6/`.
  - ft-r6a e4 at .5: GS .984/.390, TC 1.0/.495, BP .882/.326. Unknown class weak so far: OOV units carry weak card evidence (.2–.4), so
    "known-but-unidentified" units dominate unknown FPs. Added `unknown_card_max` (decode: unknown only if max card heat at the peak <
    cutoff; default 1.0 = off) + sweep in eval: best .20/.19 (thr .4, cutoff .3) vs .13/.25 (off). Any-unit owner-level recall .549 vs
    card-level .532 (thr .4).
- 01:33Z **Direction change (Sam/coordinator): units → YOLO** (KataCR baseline, then a YOLO fine-tune that I own). ft-r7 cancelled
  (no ft-r7 code run; `sprite_bank.py` + composite plan kept for the YOLO synthetic data). ft-r6 continues to completion (fallback).
  - New-card targeted labels: 7 helpers (nc1–7), 207/208 frames from 13 training battles; sprite bank 133 instances (ellipse patches).
  - Held-out eval truth: nc-eval1 relabelled s1m01/s2m01/s5m01 with CARD LEAD names (GoblinCage 9 + Brawler 3, Tombstone skeletons 6,
    SpearGoblins 4) and showed "OOV:BarbarianHut" is the Goblin Hut (Battle Log decks) → my earlier relabel reverted (`DECK_RELABEL`);
    nc-eval2 labelled s7-m04 (14 frames, 46 units, no new-card units on sampled frames). **Eval set now 148 frames / 518 units**
    (`EVAL-SPLIT.md`); r1 / r5e3 re-scored (BP .806/.242 → .853/.388).
  - YOLO data: `r3/yolo_labels.py` (points → KataCR body-class × team boxes, draft priors; 372 classes = 185 names × 2 teams incl.
    'unknown'), `r3/prelabel.py` (targeted human labels + ft-r6 e4 detections ≥.5 as proposals: 246 human + 358 model units on 208
    frames), `r3/yolo_sheets.py` (numbered draft boxes + pixel ruler). 7 Opus helpers (yb1–7, `YOLO-BRIEF.md`) verify/complete every unit
    and draw `box_px` → `labels-yolo-raw/`. Held-out eval boxes: draft priors (`yolo-heldout/`), scoring stays point-based.
  - ft-r6 epoch 3 (thr .5): GS .975/.497, TC 1.000/.557, BP .849/.397 (old BP labels).

## YOLO (units), owner live-perc-r3; job dir `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/` (05 master, 04, 08)

- 01:54Z **Setup.** KataCR dataset (MIT, 1.3 GB, git clone) → job dir; env on 04/08 by helper yolo-env (Py 3.11, torch 2.2.2+cu118,
  ultralytics 8.1.24, KataCR src @36ceb9f with a dataset-path patch; `. env.sh`). Input = KataCR arena crop 568x896: capture crop box
  (720x1280 px) x 42.2–674.2, y 31.3–1019.3 maps our tile grid onto KataCR's grid (checked visually). Classes = KataCR unit_list (155) +
  head channel 'padding_belong' (team) = nc 156; init copies detector1's class rows by name (82 + belong).
  - Code: `live/perception/yolo/{train_cr.py, official_to_cr.py, eval_yolo.py, pseudo_towers.py}`; real lists re-read live (mtime).
  - **V1a** 04: KataCR detector1 init, YOLOv8-L, AdamW 5e-4 cos, 60 ep × 6000 synthetic, batch 16, p_real .35 (KataCR part2 6,639 ×1 +
    official ×3). **V1b** 08: COCO yolov8m init, AdamW 1e-3, same data. Both via `cpu_job.sh 12`, 10 loaders. KataCR-val mAP50 after
    3–5 epochs: .85 / .89.
  - Official real frames: 108 complete box-labelled training frames (helpers yb1–7 Opus 114/208 before the usage stop; Sol ybs1–3 on the
    remaining 94) + 60 empty battle-start crops (hard negatives) + KataCR detector1 tower pseudo-labels (567 boxes) → `lists/official-train.txt`.
  - Eval (EVAL-SPLIT, sprite-level identity, ≤1 tile): box → ground point with per-class offsets measured on TRAINING box labels
    (`ground-offsets.json`: minion +.56, goblin-hut −.74, tombstone −.98, others ≈0). **V1b epoch 5, thr .5: GS .650/.667, TC .859/.629,
    BP .742/.462; 0.5 false units / empty frame** (r5e3: .959/.440, 1.0/.485, .853/.388, 0). GS false positives = river-side bushes read as
    spear-goblin (44) → empty-arena hard negatives + towers added.
  - Barbarians / BarbarianHut / BattleRam / MegaMinion / Mortar / FlyingMachine / Witch mapped to KataCR classes in `r3/yolo_labels.py`.
- 02:02Z Usage-limit stop ~01:45–01:50Z (Opus helpers yb1–7 failed after 114/208 frames). **Resumed**: Sol helpers ybs1–3 finished the
  other 94 (82 complete; spot-checked: boxes tight, teams right). Official set now **190 complete frames / 894 unit boxes + 1,009 tower
  pseudo-boxes + 60 empty arenas** (`lists/official-train.txt`, 250 lines), live on 04/08 (lists reload on mtime).
  - V1b stopped at epoch 9 (group kill, last.pt kept as `runs/v1b-last-at-stop.pt`) → **V2m on 08**: init V1b, `--share` lists synth .55
    (compositor v1 shards: 10k copied from 03 into `synth-extra/` + 08's own shards via `synth_list.sh`), official .30, KataCR part2 .15,
    p_real .75, AdamW 5e-4, 40 ep. Eval loops: 04 v1a, 08 v2m (`evals/<run>/epochN.json`; table `yolo/yolo_table.py`).
  - V1a epoch 4 at .5: GS .882/.610, TC .788/.536, BP .705/.466, empty .17/frame (ft-r5 final: .959/.440, 1.0/.485, .853/.388, 0).
- 02:28Z **First YOLO live-trial candidate `yolo-v2m-e2`** (V2m epoch 2): eval now drops KataCR spell/object classes (poison/fireball FPs;
  `yolo/rescore.py` re-scores stored evals offline). At .5: **GS .950/.843, TC .976/.835, BP .851/.718, 0 empty-frame FPs** (ft-r5 final
  .959/.440, 1.0/.485, .853/.388). Gate decision (owner): precision within .02 of ft-r5 on every arena + higher recall (my earlier BP P≥.90
  bar was stricter than ft-r5's own .853). Stripped fp16 52 MB `/candidates/yolo-v2m-e2-stripped.pt` sha256 ee76ad2c…, reproduces the
  metrics exactly. Record sent to the babysitter (swap only after the integration worker's `--units yolo:` adapter + Mac bench) and to
  live-yolo-integration-opus-r1. Monitoring delegated to Sol (`yolo-monitor-sol`, until ~04:30Z).
- 02:41Z Mac latency (integration worker; M4 Pro, CoreML fp16 ANE, full adapter): **yolo-v2m-e2 896×576 p50 18.7 / p95 31.5 ms**;
  640×416 p50 13.0 but half the units (not used); v8-L (V1a e10) p50 27.0 / p95 39.3 ms. Both overlap the ~115 ms frame model → **M vs L is
  decided by accuracy only.** CoreML parity vs eval_yolo predict(): 444/445 units (1 borderline), pos err ≤ .12 tile. Next candidates: send the
  .pt to the integration worker for a ~1 min CoreML export.
  - BB: held-out s14-m02 + s15-m01 (42 frames, Sol bb1/bb2 labelling from scratch); 110 BB training frames (11 battles) pre-labelled by
    yolo-v2m-e2, verified by Sol bbt1–3; compositor added BB floors (58) + BB-weighted shards s04b/s08b (100k each, BB .40).
- 02:44Z **Barbarian Bowl eval** (held-out s14-m02 + s15-m01; 40 frames / 179 units, Sol bb1/bb2): at .5 **yolo-v2m-e2 .894/.754**
  vs **r5e3 .922/.472** (r5e3 card-level; Barbarians/off-vocab are ignore regions for it). Recall +28 pp → no go-live delay (LEAD gate).
  BB training: 99 complete frames (Sol bbt1–3, 444 unit boxes + 521 tower pseudo-boxes) added → `official-train.txt` 349 lines (190 GS/BP/TC +
  99 BB + 60 empties), live on 04/08. EVAL-SPLIT now 188 frames / 697 units + 18 empties.
- 02:46Z **YOLO candidate 2 `yolo-v2l-e11`** (V2l epoch 11, YOLOv8-L) supersedes v2m-e2: at .5 GS .946/.887, TC .988/.856, BP .860/.752,
  **BB .940/.793**, 0 empty FPs (v2m-e2: .950/.843, .976/.835, .851/.718, .894/.754). Stripped 88 MB `/candidates/yolo-v2l-e11-stripped.pt`
  sha256 46b5752a…, metrics reproduced exactly. Record → babysitter + LEAD + integration (CoreML export/parity). V2m e22 at .5: GS .885/.868,
  BP .858/.786, BB .908/.827 (more recall, less precision on GS). Compositor BB shards done (300k/host).
- 02:48Z BB eval labels were revised by bb1/bb2 after my first snapshot (21 files) → re-finalized + re-scored: BB at .5 **v2l-e11
  .954/.809, v2m-e2 .907/.770, r5e3 .922/.476** (earlier .940/.793, .894/.754, .922/.472); other arenas unchanged. Eval set 188 frames / 696 units.
- 03:20Z **Owner (team) accuracy** (`yolo/owner_eval.py`, location-matched units, thr .5): r5e3 .993, enemy→ours 0/120;
  **v2l-e11 (live) .984, enemy→ours 8/167 (4.8%)**, ours→enemy 1/410; v2l-e24 .982 (9/184); v2l latest .969 (17/181, 9.4%) → owner errors are
  asymmetric (enemies called ours) and grow with synthetic exposure (red↔blue `swap` sprites). Crowded mixed-team subset is tiny (15 units).
  - Fixes: `train_cr.py --owner-weight` (team channel BCE weight); **08: V3l stopped → V3lo** (owner weight 3; shares synth .35 / official .40 /
    KataCR real .25; init V2l e24); 04 queue: V3lo1024 (same, imgsz 1024). Compositor asked for `v1team` shards: no swap, ≥50% crowded mixed-team,
    team-balanced. Sol watcher tracks owner accuracy; candidate rule adds enemy→ours ≤ 3%.
- 03:26Z **v1team** shards (compositor, on 03: no swap, 85% mixed-team clash frames, 50/50 both-team classes) pulled to 04/08 every
  5 min (`team_pull.sh` → `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/synth-team-extra`, list `synth-team-<host>.txt`). v1 frames without any swap box (~33%) → `synth-noswap-<host>.txt`
  (`noswap_list.py`). Queued **V4lo** (08, after V3lo) and **V4lo1024** (04, after V3lo1024): init = previous run's last.pt, owner weight 3,
  shares team .35 / noswap .15 / official .30 / KataCR real .20. Own GPU-idle watchdog (05 background loop, alerts after ~10 min idle).
- 03:28Z **Cannon/building owner** (Sam: enemy Cannons tagged ours). `owner_eval.py` now prints per-class owner confusion (buildings first).
  Held-out set has **no enemy Cannon** (ours 19); enemy buildings there are fine for v2l-e11 (goblin-hut 0/12, goblin-cage 0/4, tombstone 0/2
  enemy→ours). **Training-data cause found:** KataCR part2 real frames label cannon ours 1533 vs opp 118 → `balance_katacr.py` drops 85% of
  frames with an ours-cannon (list rewritten in place on 04/08 → live in all running/queued runs): now 237/105 (5,346 of 6,639 frames kept).
  Synth v1 cannon ~balanced (507/464 in a 20k sample); official 4/2. Only enemy-Cannon battle in the inventory = s14-m04 (training-eligible;
  2 enemy Cannon instances, 1 matched, correct) → need future battles with an enemy Cannon held out for eval.
- 03:32Z **Owner fixed in the model (Sam: no hand-coded rules).** YOLO boxes (ours + KataCR) exclude badge/HP bar → added a learned
  **owner classifier** on context crops (badge/bar above, facing; balanced team × class × damaged; buildings both teams; crowded) — spawned
  Opus sub-worker `owner-net-opus` (code `live/perception/owner/`, report `OWNER-NET.md`): also mines s19+ live owner errors (Sol-verified →
  `lists/hard-owner.txt`, used by YOLO V4 runs at share .10) and labels held-out **s19-m01** (owner eval incl. enemy Cannon). Gate:
  enemy→ours ≤ 3% overall and per building class. Live: s20 rolled back to r5e3 units after s19 (YOLO) went 1–3.
- 03:47Z **Owner baseline with s19 held-out** (s19-m01 19 + s19-m02 20 frames, Sol own1/own2 from scratch; eval set 238 frames / 833 units):
  v2l-e11 owner .969 (BB .941); **enemy→ours 20/214 (9.3%)**; **Cannon 5/13**, minion 4/13, musketeer (earlier subset 5/6) — enemy copies of OUR deck
  cards are called ours (official frames are ours-dominated: archer 153 ours vs 16 enemy) + KataCR cannon bias. owner-net-opus stopped (Sam: one model);
  its s19 eval labels + 40 HARD frames (s19-m03, hrd1; 241 units + 207 towers) → `lists/hard-owner.txt` (`convert_hard.sh`; hrd2/s19-m04 pending).
  - **v1team2** (compositor, 04/08, 100k): game badge rule (enemy ALWAYS crimson badge; ours badge+bar only when damaged). Lists
    `synth-team2-<host>.txt` (01 pulls from 08). Queued V4lo (08) / V4lo1024 (04) / V5ext (01: `--box-up .5`, extends unit boxes upward so the box covers
    badge/bar; bottom edge kept → ground points unchanged): team2 .35, team .15, noswap .10–.15, official .30, hard .10, KataCR .15–.20; owner weight 3.
  - Fixed: owner-weight lambda broke checkpoint pickling (V3lo crash 03:23Z, V4lo 7 s) → `BCEWithLogitsLoss(weight=…)`; V3lo restarted 03:34Z.
