# Perception h38 final evaluator readout

Written 2026-10-18T04:38:37.669228+00:00; scored 2026-10-18T04:38:24.766722+00:00. Run `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/h38`. Old12 pooled verdict: **PENDING re-test**. Deploy-eligible: **no**; the pooled raw gate does not qualify.

Last weights SHA256 `0ccbb43c1aa2e9e3a1d8a5c71866e95ae90a269ef32d380ecf16b37f25fb393b`. Machine evidence: `perception-h38-20261018.json`, SHA256 `cda25c9ae3cd9ba2f28e8871aa6b064880380cb30347f47e78f029ca9be1967c`. No model was deployed.

## Data and launch

All 177 HARD26 and 104 HARD27 frames have finished Sol labels. Four Sol (gpt-6.1-sol, high reasoning) helpers completed the interrupted HARD27 assignments using unchanged prompts. `hard_to_list.sh` converted both sets with the established whole-frame OOV drop and pseudo-tower recipe. HARD26 kept 175 frames (760 unit + 946 tower boxes); HARD27 kept 103 (507 unit + 591 tower boxes). Three GoblinBarrel OOV frames were dropped. The merged list has 278 frames, 1,267 unit boxes and 1,537 tower boxes (2,804 total), with no held-out overlap or duplicate source frames.

`lists/hard-owner26.txt` on 01/04/08: 47,260 bytes, SHA256 `ac20ee32f2c30def5c4d6002b9d182dea9be826b77560e280972aadb0acf2feb`. Pure HARD26 backup on each host: `lists/hard-owner26.only-h38-20261018T032340Z.bak`. Pure HARD26 SHA256 `017e4a6fcd230c47b81d3ae55dc509f8386fd52f232708642cd90f1068b7f2ad`. The list was absent on all three hosts before this build. Separate HARD27 list SHA256 `d87228df95254fedcc3c12229e6436db380e3150632436e2c4b9e24668329d3c`.

Hero forms follow a14abb6df and train as their base classes. The label map exactly matches 25ff86507, SHA256 `e0b995b1ee0e9e8282364218a8b3901d9103d34f46d7733f27c2503834d8d0c9`. Retained hero boxes: Knight 78, MiniPekka 56, MegaMinion 21, Wizard 28. No evolved bodies were observed in the uniform HARD27 frames, so that batch adds no evolved-body examples. Every converted non-tower training row was checked against its source label.

h38 is the h36 recipe with only `--name h38` and one additional `--real $L/hard-owner26.txt:.20`: seed 31, 12 epochs, init v11b-e4, owner weight 3, lr0 .0001, imgsz 1024, datasize 12000, batch 16, workers 10, share and p-real .85. Thread caps OMP 2 / MKL 2 / OpenBLAS 1 and nice19 were applied by the wrapper.

Independent Sol review round 1 blocked a masked evaluator-failure path; an h38-only checker was added. Fresh round 2 approved the exact merge, argv and amended launcher. The checker requires rc 0, parseable JSON, positive frame coverage, h38 weights and expected NMS before downstream steps or COMPLETE. Existing h36 evaluator scripts and outputs were preserved.

Detached launch: `setsid nohup nice -n 19 bash ./chain-h38.sh > logs/chain-h38.log 2>&1 < /dev/null`. GPU compute was empty and 01 load was below 60. Actual trainer PID 2107534, PGID 2107175, nice 19. Loaded-input receipt time 2026-10-18T03:30:23.171280+00:00; the receipt explicitly records HARD26 present at .20 and the exact 278-row list bytes. All 31 training-list hashes and all 556 new image/label asset hashes matched at prelaunch and postrun. Trainer argv and complete launch/script receipts are preserved in the evidence JSON.

Completed 2026-10-18T04:37:20Z. Verified 12 after3 and 16 fresh evaluator outputs. Same h36 evaluator setup: deployed 896×576, IoU .6, agnostic NMS, live-normalize and ground-offsets-v2. Optional raws81b remains unstaged; required old12, RAWS80/81/83 and HOGVID are present. Final weights and held-out hero dump were scored.

## Scoring rule

Unchanged pooled_gate.py / own_conf_report.py / enemy_conf_report.py definitions: score>=.5; nearest unused truth within 1 tile for owner; same identity and owner within 1 tile for identity recall. Old12 is raws76,76b,76c,77,78,78b,78c,78d,79,79b,79c,79d. Qualification requires own-Bats gain>=8pp vs x1h, both owner-error totals no worse, and no class above reference owner errors+1. PENDING re-test requires the Bats gain and every excess <=4. Truth-centred per-class correctness differs from pooled identity matching. No confidence intervals were preregistered.

## Old12 pooled

```json
{
  "verdict": "PENDING re-test",
  "gain_pp": 20.795107033639137,
  "own_bats": [
    1774,
    2289
  ],
  "eo": [
    81,
    3869
  ],
  "oe": [
    74,
    4471
  ],
  "identity": [
    7983,
    8429,
    9081
  ],
  "bad_classes": [
    "None"
  ],
  "failures": {
    "None": 3
  },
  "reference": {
    "own_bats": [
      1298,
      2289
    ],
    "eo": [
      124,
      3747
    ],
    "oe": [
      109,
      4021
    ],
    "identity": [
      7320,
      7925,
      9081
    ]
  }
}
```

## Held-out hero row

Hero Wizard: 14 held-out s79-m05 video frames, no missing input frames. Same spell_dump live adapter path and mapping, conf .5 / IoU .6 / agnostic / 896×576; hero_row.py highest box IoU>=.3, correct means source_card Wizard. Fresh x1h reproduces 0/14 correct,9 Knight + 5 missed. h38 identifies 10/14 as Wizard and gets all 14 owners correct; two are still Knight, one MiniPekka and one Valkyrie. No new hero classes or identity changes.

```json
{
  "x1h": {
    "Wizard": {
      "n": 14,
      "frames_missing": 0,
      "matched": 9,
      "correct": 0,
      "owner_ok": 9,
      "classes": {
        "knight": 9,
        "(missed)": 5
      }
    }
  },
  "h38": {
    "Wizard": {
      "n": 14,
      "frames_missing": 0,
      "matched": 14,
      "correct": 10,
      "owner_ok": 14,
      "classes": {
        "wizard": 10,
        "knight": 2,
        "mini-pekka": 1,
        "valkyrie": 1
      }
    }
  }
}
```

## Own-unit rows versus x1h

| Slice | Class | x1h correct/truth | h38 correct/truth | x1h missed / wrong owner | h38 missed / wrong owner |
|---|---|---|---|---|---|
| raws80 | archer | 107/113 | 110/113 | 5 / 0 | 3 / 0 |
| raws80 | bat | 106/221 | 159/221 | 107 / 7 | 59 / 3 |
| raws80 | cannon | 92/92 | 92/92 | 0 / 0 | 0 / 0 |
| raws80 | mini-pekka | 38/42 | 36/42 | 4 / 0 | 4 / 0 |
| raws80 | valkyrie | 26/32 | 28/32 | 5 / 0 | 4 / 0 |
| raws81 | archer | 52/64 | 54/64 | 9 / 0 | 6 / 0 |
| raws81 | bat | 141/217 | 176/217 | 73 / 2 | 38 / 2 |
| raws81 | cannon | 8/8 | 8/8 | 0 / 0 | 0 / 0 |
| raws81 | electro-spirit | 1/39 | 19/39 | 36 / 1 | 19 / 1 |
| raws81 | hog-rider | 8/30 | 13/30 | 19 / 0 | 13 / 0 |
| raws81 | skeleton | 152/168 | 152/168 | 12 / 0 | 11 / 1 |
| raws83 | archer | 142/145 | 141/145 | 3 / 0 | 4 / 0 |
| raws83 | cannon | 41/42 | 41/42 | 1 / 0 | 1 / 0 |
| raws83 | electro-spirit | 1/31 | 20/31 | 28 / 2 | 9 / 2 |
| raws83 | hog-rider | 16/42 | 37/42 | 22 / 0 | 5 / 0 |
| raws83 | skeleton | 29/37 | 26/37 | 6 / 2 | 5 / 6 |
| raws83 | valkyrie | 7/12 | 10/12 | 3 / 2 | 0 / 1 |

RAWS83 has zero own-Bats truth; the mechanical Bats-gain verdict is inapplicable there. Its owner regressions still count: O→E is 7 versus 3 for x1h; Barbarian owner errors increase by 8 and Skeleton owner errors by 4. These are empirical regressions independent of the unavailable Bats-gain condition. Literal None/null truth identity rows in the pooled gate remain part of owner matching. Full own/enemy/both-team per-class counts, including old12 and HOGVID, are in the evidence JSON.

## Per-slice pooled results

| Slice | Verdict | h38 own Bats | Gain pp | E→O h38 / x1h | O→E h38 / x1h | Regressed classes |
|---|---|---|---|---|---|---|
| raws76 | PENDING re-test | 164/224 | 23.661 | 6 / 7 | 10 / 15 | mini-pekka |
| raws76b | QUALIFIES | 116/138 | 28.986 | 1 / 3 | 1 / 1 | none |
| raws76c | QUALIFIES | 203/299 | 17.057 | 3 / 9 | 28 / 40 | none |
| raws77 | PENDING re-test | 186/240 | 21.250 | 13 / 11 | 7 / 9 | skeleton |
| raws78 | PENDING re-test | 106/124 | 25.000 | 8 / 9 | 4 / 6 | None, witch |
| raws78b | PENDING re-test | 220/291 | 18.900 | 10 / 10 | 3 / 8 | valkyrie |
| raws78c | QUALIFIES | 138/170 | 18.235 | 10 / 19 | 0 / 0 | none |
| raws78d | PENDING re-test | 196/253 | 26.877 | 6 / 4 | 16 / 23 | none |
| raws79 | PENDING re-test | 121/141 | 10.638 | 7 / 17 | 2 / 0 | none |
| raws79b | QUALIFIES | 87/105 | 20.000 | 2 / 7 | 3 / 3 | none |
| raws79c | QUALIFIES | 92/122 | 26.230 | 9 / 19 | 0 / 2 | none |
| raws79d | QUALIFIES | 145/182 | 15.385 | 6 / 9 | 0 / 2 | none |
| raws80 | QUALIFIES | 161/221 | 24.887 | 2 / 13 | 1 / 2 | none |
| raws81 | PENDING re-test | 183/217 | 17.051 | 9 / 9 | 4 / 3 | none |
| raws83 | inapplicable (no own Bats) | 0/0 | 0.000 | 22 / 22 | 7 / 3 | barbarian, skeleton |
| hogvid | PENDING re-test | 132/175 | 25.714 | 14 / 15 | 3 / 1 | barbarian, bat |

## Reproduction and receipts

Scoring commands ran under nice 19 on 05 (small stored JSON only; no GPU work on05):

```bash
python3 /mpac/sdicks02/scratch/live-perc-r3/h38/score_h38.py
python3 /mpac/sdicks02/repos/clasher-live/live/perception/yolo/hero_row.py --truth h38/hero/truth.json --map /mpac/sdicks02/scratch/live-lead-share/katacr_to_clasher.json x1h=h38/hero/dump-x1h.jsonl h38=h38/hero/dump-h38.jsonl
```

All 16 candidate/reference slice truth arrays match exactly. All evaluator inputs and scorer hashes are in the evidence JSON. The paired full script source snapshots, exact argv, reviewer summaries, label counts, hashes, validation receipts and launch/postrun evidence are preserved there.
- `/mpac/sdicks02/scratch/live-perc-r3/pooled_gate.py` SHA256 `e6083dd5fe2f74834cca289e38410271608764a09bc1a12eb245a448659bd54b`.
- `/mpac/sdicks02/scratch/live-perc-r3/own_conf_report.py` SHA256 `a41724351441603fd52245283ba8df99ace3cbbdf21a3008695460c92859fa32`.
- `/mpac/sdicks02/scratch/live-perc-r3/enemy_conf_report.py` SHA256 `87a0e53ce0d63d26f3fc117f70f7e26c8d04581da09ca7525923e5d3f17bbcc3`.
- `/mpac/sdicks02/repos/clasher-live/live/perception/yolo/damage_recall.py` SHA256 `df21d5e3930440dd5de65cf22e36afa9bcef0a5c272de27ea1e8c1859cf70d85`.
- `/mpac/sdicks02/repos/clasher-live/live/perception/yolo/hero_row.py` SHA256 `f5898f89232ae7240751c81b1d8a2b1f492dd020a9486dc1a45ef10f66c41cf6`.
- `/mpac/sdicks02/scratch/live-lead-share/katacr_to_clasher.json` SHA256 `6548c95eb5b1dae16da77768c28557dc19c3dcc61d183e3a29eb1ca0c30361e8`.
- `/mpac/sdicks02/scratch/live-perc-r3/h38/hero/truth.json` SHA256 `47862b6ba9543b4c6af926986d817c5cd14acb2b2c2c1202a39ef5bee58abc16`.
