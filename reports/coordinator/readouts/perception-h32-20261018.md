# Perception h32 final evaluator readout

Written 2026-10-18T02:41:07Z; scored 2026-10-18T02:39:42.332973+00:00. Run root `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/h32`; evaluator files `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/<slice>/h32-e12-896.json`. Final12epoch CSV and ALL/FRESH markers observed. Weights last.pt SHA256`85150399b675a36552b237ef8e449a7890b2c90a5481e0956039c0f22bda1b71`.

Observed source code-tree SHA256`f718e5ce526c274c830cfa8093f294b9f5f3f1deec27dd066f0564582ca0995f` on 127x01 at2026-10-18T02:40:34Z; KataCR tree SHA256`2780695bff3c575c5cf956af5e72d9748f0249ad2466e7a459222306c653b4c6`. Tree hash=SHA256(compact JSON sorted [relativepath,fileSHA256] array), excluding .git/__pycache__. Launch records do not contain a Git commit pin; these are current archive-tree receipts, not proof of historical immutability. Local LIVE scoring definitions HEAD`feef63aabb5c54531409c70772d95faab79ec4db`; scorer file SHA256 receipts below.

ROUND1 scoring exactly: score>=.5, within1tile matching; pooled old12(raws76,76b,76c,77,78,78b,78c,78d,79,79b,79c,79d); own-Bats gain>=8percentagepoints vsx1h; E→O andO→E error counts no worse; no class exceeding reference errors+1. PENDING re-test only when all excesses<=4 and ownBats gain passes. Per-class correctness is truth-centred, different from pooled identity matching. Missing required coverage=unscorable, not failure. These deterministic counts have no preregistered CI. No inference/evaluation/training was launched. Raw scoring ran under nice19 on candidate hosts; x1h local existing evaluation JSON was passed in-memory to127x08 for scoring, then verdicts aggregated on127x08 under nice19.

## Old-deck pooled
```json
{
  "verdict": "unscorable",
  "missing": [
    "raws79d"
  ]
}
```

| Slice | Verdict | Own Bats correct/truth | E→O | O→E | Bad classes |
|---|---|---|---|---|---|
| raws76 | QUALIFIES | [167, 224] | [5, 269] | [4, 360] | [] |
| raws76b | PENDING re-test | [108, 138] | [2, 261] | [2, 426] | [] |
| raws76c | QUALIFIES | [230, 299] | [7, 343] | [22, 532] | [] |
| raws77 | QUALIFIES | [182, 240] | [9, 409] | [4, 417] | [] |
| raws78 | PENDING re-test | [108, 124] | [7, 635] | [2, 342] | ['None', 'witch'] |
| raws78b | PENDING re-test | [219, 291] | [11, 240] | [1, 443] | ['valkyrie'] |
| raws78c | QUALIFIES | [142, 170] | [10, 317] | [0, 329] | [] |
| raws78d | QUALIFIES | [187, 253] | [4, 400] | [16, 341] | [] |
| raws79 | PENDING re-test | [120, 141] | [10, 257] | [3, 314] | ['bat'] |
| raws79b | QUALIFIES | [88, 105] | [5, 161] | [2, 380] | [] |
| raws79c | PENDING re-test | [89, 122] | [18, 227] | [0, 195] | ['barbarian'] |
| raws79d | unscorable | unavailable | unavailable | unavailable | ['raws79d'] |
| raws80 | unscorable | unavailable | unavailable | unavailable | ['raws80'] |
| raws81 | unscorable | unavailable | unavailable | unavailable | ['raws81'] |
| raws81b | unscorable | unavailable | unavailable | unavailable |  |
| raws82 | unscorable | unavailable | unavailable | unavailable | ['raws82'] |
| raws83 | unscorable | unavailable | unavailable | unavailable | ['raws83'] |
| raws83b | unscorable | unavailable | unavailable | unavailable |  |
| raws84 | unscorable | unavailable | unavailable | unavailable |  |
| hogvid | PENDING re-test | [131, 175] | [14, 502] | [0, 465] | ['barbarian'] |

## New-deck own-unit rows
```json
{}
```

Each per-class row: n=truth bodies, ok=correctclass+owner, missed/owner_wrong counts as own_conf_report.py. Old pooled enemy troop total is available only when all12 slices exist. Hero row is unscorable: no candidate hero-row/spell_dump artifacts exist in inspected paths. Base-class training semantics remain required for hero Wizard/Knight/MiniPekka/MegaMinion/Musketeer; no separate hero class is scored as a new identity.

Decision implication: no action/deploy: the old pooled gate lacks raws79d, and raws80/new-deck evaluation coverage is absent. Existing FRESH marker covers its own launch slice list, not the full ROUND1 requirement. No new evaluations are started by the collector.

## Evaluation receipts
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/h32-e12-896.json`: 198frames; SHA256`9fe788fce3d9bfc9be06d3b35ebf0e3525194520999bb8019d56e84cffc0ba35`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/h32-e12-896.json`: 199frames; SHA256`b1a5c2e0555ea0c146220d80b691cbca170a11728c2dcb02c6f7e5a37e489e47`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/h32-e12-896.json`: 200frames; SHA256`83a608a3d079e6056637f567f3a0a0378b9c9c51049c8745cd61d93e703b6257`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/h32-e12-896.json`: 199frames; SHA256`1e2159058fae65c22a3c2667f4328b38258a0d9c22ba2e748f3fe9d98b2cfda0`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/h32-e12-896.json`: 196frames; SHA256`13ad30283870745b4c94ce1a9b26401e5164e92ef7f24ccdc986b2f1c27c20c5`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/h32-e12-896.json`: 199frames; SHA256`e1420a148e31e85fe37c682eedbec7f5c9d3c0e019dde72f83cdb742e91aa34a`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/h32-e12-896.json`: 200frames; SHA256`6029ffa23c484e83ae919507c7ad05b1c0aea2944e47f58f80b9852666cdfc7f`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/h32-e12-896.json`: 151frames; SHA256`17073cb29a8107322469f34463763831552760f8912b8d64d3a49f0fd0e31296`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/h32-e12-896.json`: 200frames; SHA256`2665af1f2d4cf95c9682f6a81d0b9ddf8108604868ac0b70652480e3ca10d64b`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/h32-e12-896.json`: 200frames; SHA256`d6f4e7dd8463ca6341ef6fd22c31174ec892fe9a3f56b96bfd83c82025af7efd`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/h32-e12-896.json`: 200frames; SHA256`2a3b75e64ffb4cb3a160101a098f2792509fca247767e730133a003acd839593`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/h32-e12-896.json`: 208frames; SHA256`aa4372246901cd564279a435e5e9bc0b55add6de4d2a0b75a3fd7d30b8354621`.

Scoring summary (all fields):
```json
{
  "old_pooled": {
    "verdict": "unscorable",
    "missing": [
      "raws79d"
    ]
  },
  "per_slice": {
    "raws76": {
      "verdict": "QUALIFIES",
      "own_bats": [
        167,
        224
      ],
      "gain_pp": 25.0,
      "eo": [
        5,
        269
      ],
      "oe": [
        4,
        360
      ],
      "identity": [
        601,
        633,
        703
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 275,
        "matched": 258,
        "cls_ok": 249,
        "own_ok": 247,
        "ok": 244,
        "missed": 17
      }
    },
    "raws76b": {
      "verdict": "PENDING re-test",
      "own_bats": [
        108,
        138
      ],
      "gain_pp": 23.188405797101453,
      "eo": [
        2,
        261
      ],
      "oe": [
        2,
        426
      ],
      "identity": [
        680,
        700,
        748
      ],
      "bad_classes": [],
      "failures": {
        "O\u2192E total": 1
      },
      "enemy": {
        "n": 284,
        "matched": 264,
        "cls_ok": 257,
        "own_ok": 259,
        "ok": 256,
        "missed": 20
      }
    },
    "raws76c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        230,
        299
      ],
      "gain_pp": 26.086956521739136,
      "eo": [
        7,
        343
      ],
      "oe": [
        22,
        532
      ],
      "identity": [
        818,
        886,
        943
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 340,
        "matched": 324,
        "cls_ok": 318,
        "own_ok": 315,
        "ok": 311,
        "missed": 16
      }
    },
    "raws77": {
      "verdict": "QUALIFIES",
      "own_bats": [
        182,
        240
      ],
      "gain_pp": 19.58333333333333,
      "eo": [
        9,
        409
      ],
      "oe": [
        4,
        417
      ],
      "identity": [
        762,
        835,
        899
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 403,
        "matched": 368,
        "cls_ok": 357,
        "own_ok": 359,
        "ok": 351,
        "missed": 35
      }
    },
    "raws78": {
      "verdict": "PENDING re-test",
      "own_bats": [
        108,
        124
      ],
      "gain_pp": 26.61290322580645,
      "eo": [
        7,
        635
      ],
      "oe": [
        2,
        342
      ],
      "identity": [
        927,
        993,
        1010
      ],
      "bad_classes": [
        "null",
        "witch"
      ],
      "failures": {
        "null": 2,
        "witch": 2
      },
      "enemy": {
        "n": 630,
        "matched": 594,
        "cls_ok": 590,
        "own_ok": 587,
        "ok": 586,
        "missed": 36
      }
    },
    "raws78b": {
      "verdict": "PENDING re-test",
      "own_bats": [
        219,
        291
      ],
      "gain_pp": 18.556701030927837,
      "eo": [
        11,
        240
      ],
      "oe": [
        1,
        443
      ],
      "identity": [
        670,
        686,
        772
      ],
      "bad_classes": [
        "valkyrie"
      ],
      "failures": {
        "valkyrie": 4,
        "E\u2192O total": 1
      },
      "enemy": {
        "n": 252,
        "matched": 243,
        "cls_ok": 230,
        "own_ok": 228,
        "ok": 225,
        "missed": 9
      }
    },
    "raws78c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        142,
        170
      ],
      "gain_pp": 20.588235294117652,
      "eo": [
        10,
        317
      ],
      "oe": [
        0,
        329
      ],
      "identity": [
        635,
        659,
        728
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 361,
        "matched": 318,
        "cls_ok": 317,
        "own_ok": 307,
        "ok": 307,
        "missed": 43
      }
    },
    "raws78d": {
      "verdict": "QUALIFIES",
      "own_bats": [
        187,
        253
      ],
      "gain_pp": 23.320158102766797,
      "eo": [
        4,
        400
      ],
      "oe": [
        16,
        341
      ],
      "identity": [
        693,
        757,
        816
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 418,
        "matched": 380,
        "cls_ok": 371,
        "own_ok": 377,
        "ok": 368,
        "missed": 38
      }
    },
    "raws79": {
      "verdict": "PENDING re-test",
      "own_bats": [
        120,
        141
      ],
      "gain_pp": 9.9290780141844,
      "eo": [
        10,
        257
      ],
      "oe": [
        3,
        314
      ],
      "identity": [
        558,
        574,
        613
      ],
      "bad_classes": [
        "bat"
      ],
      "failures": {
        "bat": 2,
        "O\u2192E total": 3
      },
      "enemy": {
        "n": 273,
        "matched": 258,
        "cls_ok": 254,
        "own_ok": 248,
        "ok": 245,
        "missed": 15
      }
    },
    "raws79b": {
      "verdict": "QUALIFIES",
      "own_bats": [
        88,
        105
      ],
      "gain_pp": 20.952380952380956,
      "eo": [
        5,
        161
      ],
      "oe": [
        2,
        380
      ],
      "identity": [
        507,
        548,
        561
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 157,
        "matched": 140,
        "cls_ok": 133,
        "own_ok": 135,
        "ok": 130,
        "missed": 17
      }
    },
    "raws79c": {
      "verdict": "PENDING re-test",
      "own_bats": [
        89,
        122
      ],
      "gain_pp": 23.77049180327869,
      "eo": [
        18,
        227
      ],
      "oe": [
        0,
        195
      ],
      "identity": [
        399,
        427,
        490
      ],
      "bad_classes": [
        "barbarian"
      ],
      "failures": {
        "barbarian": 2
      },
      "enemy": {
        "n": 247,
        "matched": 232,
        "cls_ok": 222,
        "own_ok": 209,
        "ok": 206,
        "missed": 15
      }
    },
    "raws79d": {
      "verdict": "unscorable",
      "missing": [
        "raws79d"
      ]
    },
    "raws80": {
      "verdict": "unscorable",
      "missing": [
        "raws80"
      ]
    },
    "raws81": {
      "verdict": "unscorable",
      "missing": [
        "raws81"
      ]
    },
    "raws81b": {
      "verdict": "unscorable",
      "reference_missing": [
        "raws81b"
      ]
    },
    "raws82": {
      "verdict": "unscorable",
      "missing": [
        "raws82"
      ]
    },
    "raws83": {
      "verdict": "unscorable",
      "missing": [
        "raws83"
      ]
    },
    "raws83b": {
      "verdict": "unscorable",
      "reference_missing": [
        "raws83b"
      ]
    },
    "raws84": {
      "verdict": "unscorable",
      "reference_missing": [
        "raws84"
      ]
    },
    "hogvid": {
      "verdict": "PENDING re-test",
      "own_bats": [
        131,
        175
      ],
      "gain_pp": 25.14285714285714,
      "eo": [
        14,
        502
      ],
      "oe": [
        0,
        465
      ],
      "identity": [
        870,
        990,
        1008
      ],
      "bad_classes": [
        "barbarian"
      ],
      "failures": {
        "barbarian": 2
      },
      "enemy": {
        "n": 480,
        "matched": 427,
        "cls_ok": 411,
        "own_ok": 413,
        "ok": 403,
        "missed": 53
      }
    }
  },
  "own_rows": {},
  "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
  "weights_sha256": "85150399b675a36552b237ef8e449a7890b2c90a5481e0956039c0f22bda1b71"
}
```
- `/mpac/sdicks02/scratch/live-perc-r3/pooled_gate.py` SHA256`e6083dd5fe2f74834cca289e38410271608764a09bc1a12eb245a448659bd54b`.
- `/mpac/sdicks02/scratch/live-perc-r3/own_conf_report.py` SHA256`a41724351441603fd52245283ba8df99ace3cbbdf21a3008695460c92859fa32`.
- `/mpac/sdicks02/scratch/live-perc-r3/enemy_conf_report.py` SHA256`87a0e53ce0d63d26f3fc117f70f7e26c8d04581da09ca7525923e5d3f17bbcc3`.
