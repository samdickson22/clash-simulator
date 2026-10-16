# KataCR v0.7.13 official-frame baseline — 2026-10-16

Frozen r3 labels: 134 frames / 472 units; GS 48/159, TC 26/97, BP 60/216. Identity truth: 440 C56 units; 32 OOV/UNKNOWN units are same-owner ignore regions for identity and positive truth for any-unit. Empty frames: GS 9, TC 4, BP 5. No older sealed data used.

| Model | Arena | Confidence | Identity×owner P/R | Any-unit×owner P/R | Empty FPs / frames |
|---|---|---:|---:|---:|---:|
| KataCR | GS | 0.7 | 0.790/0.308 | 0.839/0.327 | 0/9 |
| r5e3 | GS | 0.5 | 0.959/0.440 | 0.973/0.447 | 0/9 |
| KataCR | TC | 0.7 | 0.812/0.268 | 0.812/0.268 | 0/4 |
| r5e3 | TC | 0.5 | 1.000/0.485 | 1.000/0.485 | 0/4 |
| KataCR | BP | 0.7 | 0.692/0.196 | 0.863/0.319 | 0/5 |
| r5e3 | BP | 0.5 | 0.818/0.342 | 0.935/0.398 | 0/5 |

Original 99-frame set (BP 25 frames / 76 units), retained to match the brief:

| Model | BP identity×owner P/R | BP any-unit×owner P/R |
|---|---:|---:|
| KataCR | 0.600/0.150 | 0.931/0.355 |
| r5e3 | 0.857/0.400 | 1.000/0.487 |

| Model | Threshold | GS id P/R | TC id P/R | BP id P/R | GS any P/R | TC any P/R | BP any P/R | Empty FPs GS/TC/BP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| KataCR | 0.1 | 0.491/0.358 | 0.465/0.340 | 0.415/0.293 | 0.655/0.478 | 0.775/0.567 | 0.715/0.523 | 0/0/0 |
| KataCR | 0.25 | 0.621/0.340 | 0.569/0.340 | 0.531/0.283 | 0.724/0.396 | 0.793/0.474 | 0.762/0.444 | 0/0/0 |
| KataCR | 0.4 | 0.711/0.340 | 0.674/0.320 | 0.636/0.266 | 0.789/0.377 | 0.804/0.381 | 0.819/0.398 | 0/0/0 |
| KataCR | 0.5 | 0.732/0.327 | 0.732/0.309 | 0.634/0.245 | 0.803/0.358 | 0.780/0.330 | 0.808/0.370 | 0/0/0 |
| KataCR | 0.6 | 0.773/0.321 | 0.789/0.309 | 0.683/0.234 | 0.818/0.340 | 0.789/0.309 | 0.835/0.352 | 0/0/0 |
| KataCR | 0.7 | 0.790/0.308 | 0.812/0.268 | 0.692/0.196 | 0.839/0.327 | 0.812/0.268 | 0.863/0.319 | 0/0/0 |
| KataCR | 0.8 | 0.789/0.283 | 0.828/0.247 | 0.711/0.174 | 0.825/0.296 | 0.828/0.247 | 0.873/0.287 | 0/0/0 |
| KataCR | 0.9 | 0.867/0.164 | 0.923/0.124 | 0.750/0.065 | 0.867/0.164 | 0.923/0.124 | 0.895/0.157 | 0/0/0 |
| KataCR | 0.95 | 1.000/0.069 | 1.000/0.093 | 0.857/0.033 | 1.000/0.069 | 1.000/0.093 | 0.963/0.120 | 0/0/0 |
| r5e3 | 0.3 | 0.716/0.604 | 0.870/0.619 | 0.595/0.495 | 0.754/0.635 | 0.870/0.619 | 0.725/0.597 | 0/3/0 |
| r5e3 | 0.4 | 0.856/0.522 | 0.981/0.526 | 0.794/0.440 | 0.876/0.535 | 0.981/0.526 | 0.916/0.505 | 0/0/0 |
| r5e3 | 0.5 | 0.959/0.440 | 1.000/0.485 | 0.818/0.342 | 0.973/0.447 | 1.000/0.485 | 0.935/0.398 | 0/0/0 |
| r5e3 | 0.6 | 0.980/0.308 | 1.000/0.381 | 0.911/0.277 | 0.980/0.308 | 1.000/0.381 | 0.972/0.319 | 0/0/0 |
| r5e3 | 0.7 | 0.970/0.201 | 1.000/0.196 | 0.886/0.168 | 0.970/0.201 | 1.000/0.196 | 0.957/0.204 | 0/0/0 |
| r5e3 | 0.8 | 0.933/0.088 | 1.000/0.082 | 1.000/0.092 | 0.933/0.088 | 1.000/0.082 | 1.000/0.079 | 0/0/0 |

Best recall at precision gates over the recorded sweep (thresholds .10,.20,.25,.30,.35,.40,.45,.50,.60,.70,.80,.85,.90,.95; r5e3 cache floor .30). Entries: recall @ threshold (TP/truth). `none` = no tested nonempty operating point meets the gate.

| Model | Arena | Metric | P≥.95 | P≥.90 |
|---|---|---|---:|---:|
| KataCR | GS | id | 0.069 @ 0.95 (11/159) | 0.069 @ 0.95 (11/159) |
| KataCR | GS | any_owner | 0.069 @ 0.95 (11/159) | 0.069 @ 0.95 (11/159) |
| KataCR | TC | id | 0.093 @ 0.95 (9/97) | 0.124 @ 0.9 (12/97) |
| KataCR | TC | any_owner | 0.093 @ 0.95 (9/97) | 0.124 @ 0.9 (12/97) |
| KataCR | BP | id | none | none |
| KataCR | BP | any_owner | 0.120 @ 0.95 (26/216) | 0.120 @ 0.95 (26/216) |
| r5e3 | GS | id | 0.440 @ 0.5 (70/159) | 0.516 @ 0.45 (82/159) |
| r5e3 | GS | any_owner | 0.447 @ 0.5 (71/159) | 0.522 @ 0.45 (83/159) |
| r5e3 | TC | id | 0.526 @ 0.4 (51/97) | 0.567 @ 0.35 (55/97) |
| r5e3 | TC | any_owner | 0.526 @ 0.4 (51/97) | 0.567 @ 0.35 (55/97) |
| r5e3 | BP | id | 0.092 @ 0.8 (17/184) | 0.277 @ 0.6 (51/184) |
| r5e3 | BP | any_owner | 0.319 @ 0.6 (69/216) | 0.505 @ 0.4 (109/216) |

| Card (pooled C56 truth) | n | KataCR .70 P/R | KataCR .25 P/R | r5e3 .50 P/R | KataCR R at P≥.95 | KataCR R at P≥.90 |
|---|---:|---:|---:|---:|---:|---:|
| Archers | 131 | 1.000/0.076 | 0.923/0.092 | 1.000/0.435 | 0.076 @ 0.6 (10/131) | 0.092 @ 0.1 (12/131) |
| Giant | 38 | 0.861/0.816 | 0.756/0.816 | 0.926/0.658 | 0.658 @ 0.95 (25/38) | 0.658 @ 0.95 (25/38) |
| GoblinHut | 2 | 0.000/0.000 | 0.000/0.000 | 0.500/0.500 | none | none |
| Goblins | 25 | 0.933/0.560 | 0.625/0.600 | 1.000/0.680 | 0.120 @ 0.9 (3/25) | 0.600 @ 0.6 (15/25) |
| Knight | 51 | 0.842/0.314 | 0.806/0.569 | 0.963/0.510 | 0.216 @ 0.85 (11/51) | 0.216 @ 0.85 (11/51) |
| MiniPekka | 51 | 0.545/0.118 | 0.522/0.235 | 1.000/0.373 | none | none |
| Minions | 112 | 0.462/0.054 | 0.524/0.098 | 0.957/0.196 | none | none |
| Musketeer | 30 | 0.875/0.933 | 0.829/0.967 | 0.867/0.433 | 0.400 @ 0.9 (12/30) | 0.733 @ 0.85 (22/30) |

Targeted, partial-label supplement: 201 frames / 221 labelled bodies. Only recall is estimable; these frames do not enter the primary P/R table. Body hits require the correct visual body, owner and ≤1 tile. Fixed-source hits additionally require the canonical source card; shared Skeleton/SpearGoblin sprites cannot determine Tombstone/GoblinHut provenance.

| Source card / body | n | Body hits .25 | Body hits .50 | Body hits .70 | Fixed-source hits .70 |
|---|---:|---:|---:|---:|---:|
| Bomber/Bomber | 15 | 7 | 7 | 6 | 6 |
| GoblinCage/GoblinBrawler | 12 | 10 | 10 | 10 | 10 |
| GoblinCage/GoblinCage | 6 | 2 | 2 | 2 | 2 |
| GoblinHut/SpearGoblin | 47 | 34 | 34 | 34 | 0 |
| SpearGoblins/SpearGoblin | 104 | 79 | 79 | 77 | 77 |
| Tombstone/Skeleton | 27 | 9 | 9 | 8 | 0 |
| Tombstone/Tombstone | 10 | 9 | 9 | 9 | 9 |

Nearest same-owner C56 class confusions at .70 (spatially paired, counts): Knight→Musketeer: 3; Archers→Rascals: 2; GoblinHut→Goblins: 1; Archers→DarkPrince: 1; Minions→DarkPrince: 1.

Off-vocab visual error: BarbarianHut→goblin-hut, 13 spatial matches at .70. GoblinCage→Cannon and GoblinBrawler→Knight are intentional proxy mappings, not visual confusions.

CPU-only on 127x05, Ryzen Threadripper 3990X, cores 0–7, nice 19, 8 Torch threads: 353 calls / 352 unique source images; wall mean 5.978 s/frame, median 4.387; process CPU mean 36.402 core-s/frame. Primary frames: wall mean 5.864, CPU mean 34.632. Warm-up/load excluded; crop, both models and cross-model NMS included. Shared-host timings, batch 1.

Recipe: both pinned weights; custom team-aware predictor; 896×576 inference; confidence floor .10; per-model IoU .60; concatenate then class-agnostic NMS .60; no tracker. KataCR no-tracker default confidence .70; bare Ultralytics default .25; August script default .40 (all shown). Upstream tracker mode lowers confidence to .10; tracking is disabled here, and the .10 stateless point is also shown. Official→r3 calibrated arena crop, resized to August 428×683 crop. Ground troops = bbox bottom centre; buildings = bbox centre (upstream convention); flying troops = bbox centre + 1 native tile. Team 0→r3 owner 1; team 1→owner 0. Mapping is fixed, with no label/deck oracle. GoblinBrawler uses the proxy table's Knight body, not the cage's Cannon building.

Scoring: verbatim frozen r3 `match` and identity `score`, radius 1 tile, score-greedy one-to-one. Any-unit explicitly keys on owner: the evaluator's legacy `owner` branch passes `key=False`, so it is identity- and owner-agnostic. The requested owner-aware metric above corrects that branch without modifying the repository evaluator. r5e3 predictions are the frozen r3 `eval-r5e3.json` cache, with a .30 floor; no new r5e3 inference was needed. Full counts, per-arena/per-card sweep: `results.json`, `per-card.csv`.

Original all-ground-bottom-centre anchor at .70 (building reference correction shown separately): GS 0.790/0.308; TC 0.812/0.268; BP 0.486/0.196. Tall hut bottoms were 1.3–1.8 tiles below labelled base centres; the primary uses upstream bbox centres for buildings, without fitted offsets.

Position sensitivity at .70, identity P/R at radius 1.5 (primary remains ≤1.0): GS 0.839/0.327; TC 0.812/0.268; BP 0.692/0.196.

Class inventory: 155 global labels; shipped heads expose 150 visual labels plus padding. Absent global labels: mirror, selected, tesla-evolution-shock, text, zap-evolution. Unmapped visual class (unplaced object): phoenix-egg; emitted boxes at .70: 0. Towers, bars, UI, spell/projectile objects excluded from unit scoring. `katacr-coverage.json`: 122 cards = 106 covered / 4 partial / 12 missing (inventory, not measured accuracy); per-body class/sprite counts and current-evolution gaps included.

| Component | Licence finding |
|---|---|
| KataCR pinned code | [MIT](https://github.com/wty-yy/KataCR/blob/36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8/LICENSE), copyright 2024 wty |
| v0.7.13 weights | AGPL-3.0 explicitly declared in BOTH checkpoint metadata; `checkpoint-metadata.json`. Training version 8.1.32; timestamps 2024-04-23 / 2024-05-06. No external exception found. |
| Upstream detection dataset | [MIT](https://github.com/wty-yy/Clash-Royale-Detection-Dataset/blob/31b4151fedb1b914e99c3c122c16dca61cb2b905/LICENSE); tree metadata only fetched, no dataset images downloaded |
| Ultralytics 8.1.24 | [AGPL-3.0](https://github.com/ultralytics/ultralytics/blob/v8.1.24/LICENSE) |

Artifacts: `/mpac/sdicks02/jobs/clasher/katacr-20261016/`; `MANIFEST.json` contains URLs and SHA-256s; `weights/READY` present. Source commit `36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8`; proxy table `a382530c9`. No model/data vendored or committed.

Exact run commands (download/setup logs and frozen inputs retained under J):

```bash
J=/mpac/sdicks02/jobs/clasher/katacr-20261016
nice -n 19 git clone https://github.com/wty-yy/KataCR.git "$J/src"
git -C "$J/src" checkout 36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8
python3 -m venv "$J/venv"
nice -n 19 "$J/venv/bin/pip" install gdown
nice -n 19 "$J/venv/bin/gdown" 1DMD-EYXa1qn8lN4JjPQ7UIuOMwaqS5w_ -O "$J/weights/detector1_v0.7.13.pt"
nice -n 19 "$J/venv/bin/gdown" 1yEq-6liLhs_pUfipJM1E-tMj6l4FSbxD -O "$J/weights/detector2_v0.7.13.pt"
nice -n 19 uv venv --python 3.11 "$J/venv311"
nice -n 19 uv pip install --python "$J/venv311/bin/python" torch==2.2.2+cpu torchvision==0.17.2+cpu --index-url https://download.pytorch.org/whl/cpu
nice -n 19 uv pip install --python "$J/venv311/bin/python" ultralytics==8.1.24 numpy==1.26.4 opencv-python==4.9.0.80 scipy==1.13.1 matplotlib==3.8.2 pandas==2.2.2 pillow==10.3.0
nice -n 19 env OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 "$J/venv311/bin/python" "$J/infer_katacr.py" --inspect
nice -n 19 "$J/venv311/bin/python" "$J/prepare.py"
nice -n 19 taskset -c 0-7 env OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 "$J/venv311/bin/python" "$J/infer_katacr.py" > "$J/inference.log" 2>&1
nice -n 19 taskset -c 0-7 "$J/venv311/bin/python" "$J/inspect_checkpoint_metadata.py"
nice -n 19 taskset -c 0-7 "$J/venv311/bin/python" "$J/score.py"
nice -n 19 taskset -c 0-7 "$J/venv311/bin/python" "$J/coverage.py"
nice -n 19 taskset -c 0-7 "$J/venv311/bin/python" "$J/write_report.py"
nice -n 19 taskset -c 0-7 "$J/venv311/bin/python" "$J/finalize_manifest.py"
```
