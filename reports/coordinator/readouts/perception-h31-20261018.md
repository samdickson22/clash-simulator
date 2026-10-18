# Perception h31 final evaluator readout

Written 2026-10-18T02:41:07Z; scored 2026-10-18T02:39:42.332973+00:00. Run root `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/h31`; evaluator files `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/<slice>/h31-e12-896.json`. Final12epoch CSV and ALL/FRESH markers observed. Weights last.pt SHA256`c9f7bb8123705517335976d31b4b3114ef20d38c9cf68868ed85df7830c2db2d`.

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
| raws76 | QUALIFIES | [166, 224] | [5, 269] | [4, 360] | [] |
| raws76b | QUALIFIES | [107, 138] | [2, 263] | [1, 423] | [] |
| raws76c | QUALIFIES | [222, 299] | [5, 341] | [19, 523] | [] |
| raws77 | PENDING re-test | [183, 240] | [10, 409] | [8, 423] | ['baby-dragon', 'mega-minion'] |
| raws78 | PENDING re-test | [103, 124] | [10, 641] | [3, 337] | [] |
| raws78b | QUALIFIES | [215, 291] | [5, 235] | [2, 441] | [] |
| raws78c | QUALIFIES | [140, 170] | [17, 324] | [0, 327] | [] |
| raws78d | QUALIFIES | [193, 253] | [3, 398] | [10, 342] | [] |
| raws79 | PENDING re-test | [122, 141] | [12, 258] | [4, 315] | ['bat', 'giant'] |
| raws79b | no | [86, 105] | [14, 171] | [2, 378] | ['None'] |
| raws79c | QUALIFIES | [86, 122] | [10, 228] | [0, 191] | [] |
| raws79d | unscorable | unavailable | unavailable | unavailable | ['raws79d'] |
| raws80 | unscorable | unavailable | unavailable | unavailable | ['raws80'] |
| raws81 | unscorable | unavailable | unavailable | unavailable | ['raws81'] |
| raws81b | unscorable | unavailable | unavailable | unavailable |  |
| raws82 | unscorable | unavailable | unavailable | unavailable | ['raws82'] |
| raws83 | unscorable | unavailable | unavailable | unavailable | ['raws83'] |
| raws83b | unscorable | unavailable | unavailable | unavailable |  |
| raws84 | unscorable | unavailable | unavailable | unavailable |  |
| hogvid | PENDING re-test | [137, 175] | [13, 511] | [0, 470] | ['None'] |

## New-deck own-unit rows
```json
{}
```

Each per-class row: n=truth bodies, ok=correctclass+owner, missed/owner_wrong counts as own_conf_report.py. Old pooled enemy troop total is available only when all12 slices exist. Hero row is unscorable: no candidate hero-row/spell_dump artifacts exist in inspected paths. Base-class training semantics remain required for hero Wizard/Knight/MiniPekka/MegaMinion/Musketeer; no separate hero class is scored as a new identity.

Decision implication: no action/deploy: the old pooled gate lacks raws79d, and raws80/new-deck evaluation coverage is absent. Existing FRESH marker covers its own launch slice list, not the full ROUND1 requirement. No new evaluations are started by the collector.

## Evaluation receipts
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/h31-e12-896.json`: 198frames; SHA256`a1138c901fd4404f15ab2c2f6361076a3c3e9d5cf232d5d021cda3c7c5b73384`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/h31-e12-896.json`: 199frames; SHA256`f869083dd0108b9dc9104a4396545fcaf1af3bbd3149e1f1b321e4e7ae9b684f`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/h31-e12-896.json`: 200frames; SHA256`f5e6fbca327269bcffcc65797dec4c7cb47a7643ae4a0a217d7e10beeb8e0812`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/h31-e12-896.json`: 199frames; SHA256`22c2aa96ddca73d1f7fbc206aeeb924f123185a3827b91ee5bf79209545a71f3`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/h31-e12-896.json`: 196frames; SHA256`889cfede5557de0a2ab8ed45299bf5def1a8e94649132918993b8c32859727de`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/h31-e12-896.json`: 199frames; SHA256`09217a58a9119b0ddfa6831cf53f7e36bb4cb41a06064923611d8ff7fca5fe05`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/h31-e12-896.json`: 200frames; SHA256`7c7b9c0d52ebb70db8dbb850f4f4812e5ebd784a0d3af471a627ceda2c923151`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/h31-e12-896.json`: 151frames; SHA256`5a5b17840c4b679905a7adcfc152ff7bc888b746ca6cded316b5f4138442e213`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/h31-e12-896.json`: 200frames; SHA256`12baff52c5c36c380a549acd66e70d2b9cef1f2a6503a77e22054c330f1bce44`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/h31-e12-896.json`: 200frames; SHA256`d273f9e6f8d7ed426a3f7c08d4835d61c8eb1f175c5dbf60578753a12dd5730d`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/h31-e12-896.json`: 200frames; SHA256`d9ef17a240f1cbda70f36478a965c265c044af98bfe8e9a614bba52d2250bae7`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/h31-e12-896.json`: 208frames; SHA256`5507d0ddb9a15143e78b9f069aaec9978674d24da0f5525c5d1c117e3c0d151a`.

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
        166,
        224
      ],
      "gain_pp": 24.55357142857143,
      "eo": [
        5,
        269
      ],
      "oe": [
        4,
        360
      ],
      "identity": [
        603,
        631,
        703
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 275,
        "matched": 259,
        "cls_ok": 248,
        "own_ok": 246,
        "ok": 245,
        "missed": 16
      }
    },
    "raws76b": {
      "verdict": "QUALIFIES",
      "own_bats": [
        107,
        138
      ],
      "gain_pp": 22.463768115942027,
      "eo": [
        2,
        263
      ],
      "oe": [
        1,
        423
      ],
      "identity": [
        679,
        698,
        748
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 284,
        "matched": 265,
        "cls_ok": 260,
        "own_ok": 261,
        "ok": 258,
        "missed": 19
      }
    },
    "raws76c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        222,
        299
      ],
      "gain_pp": 23.41137123745819,
      "eo": [
        5,
        341
      ],
      "oe": [
        19,
        523
      ],
      "identity": [
        816,
        877,
        943
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 340,
        "matched": 324,
        "cls_ok": 318,
        "own_ok": 315,
        "ok": 313,
        "missed": 16
      }
    },
    "raws77": {
      "verdict": "PENDING re-test",
      "own_bats": [
        183,
        240
      ],
      "gain_pp": 19.999999999999996,
      "eo": [
        10,
        409
      ],
      "oe": [
        8,
        423
      ],
      "identity": [
        762,
        842,
        899
      ],
      "bad_classes": [
        "baby-dragon",
        "mega-minion"
      ],
      "failures": {
        "baby-dragon": 2,
        "mega-minion": 2
      },
      "enemy": {
        "n": 403,
        "matched": 368,
        "cls_ok": 358,
        "own_ok": 357,
        "ok": 351,
        "missed": 35
      }
    },
    "raws78": {
      "verdict": "PENDING re-test",
      "own_bats": [
        103,
        124
      ],
      "gain_pp": 22.580645161290324,
      "eo": [
        10,
        641
      ],
      "oe": [
        3,
        337
      ],
      "identity": [
        915,
        991,
        1010
      ],
      "bad_classes": [],
      "failures": {
        "E\u2192O total": 1
      },
      "enemy": {
        "n": 630,
        "matched": 595,
        "cls_ok": 589,
        "own_ok": 585,
        "ok": 582,
        "missed": 35
      }
    },
    "raws78b": {
      "verdict": "QUALIFIES",
      "own_bats": [
        215,
        291
      ],
      "gain_pp": 17.182130584192446,
      "eo": [
        5,
        235
      ],
      "oe": [
        2,
        441
      ],
      "identity": [
        664,
        686,
        772
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 252,
        "matched": 240,
        "cls_ok": 228,
        "own_ok": 232,
        "ok": 225,
        "missed": 12
      }
    },
    "raws78c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        140,
        170
      ],
      "gain_pp": 19.41176470588235,
      "eo": [
        17,
        324
      ],
      "oe": [
        0,
        327
      ],
      "identity": [
        628,
        663,
        728
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 361,
        "matched": 324,
        "cls_ok": 320,
        "own_ok": 307,
        "ok": 303,
        "missed": 37
      }
    },
    "raws78d": {
      "verdict": "QUALIFIES",
      "own_bats": [
        193,
        253
      ],
      "gain_pp": 25.69169960474309,
      "eo": [
        3,
        398
      ],
      "oe": [
        10,
        342
      ],
      "identity": [
        702,
        754,
        816
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 418,
        "missed": 39,
        "matched": 379,
        "cls_ok": 372,
        "own_ok": 376,
        "ok": 370
      }
    },
    "raws79": {
      "verdict": "PENDING re-test",
      "own_bats": [
        122,
        141
      ],
      "gain_pp": 11.34751773049646,
      "eo": [
        12,
        258
      ],
      "oe": [
        4,
        315
      ],
      "identity": [
        557,
        575,
        613
      ],
      "bad_classes": [
        "bat",
        "giant"
      ],
      "failures": {
        "bat": 2,
        "giant": 2,
        "O\u2192E total": 4
      },
      "enemy": {
        "n": 273,
        "matched": 259,
        "cls_ok": 255,
        "own_ok": 248,
        "ok": 244,
        "missed": 14
      }
    },
    "raws79b": {
      "verdict": "no",
      "own_bats": [
        86,
        105
      ],
      "gain_pp": 19.047619047619047,
      "eo": [
        14,
        171
      ],
      "oe": [
        2,
        378
      ],
      "identity": [
        503,
        561,
        561
      ],
      "bad_classes": [
        "null"
      ],
      "failures": {
        "null": 8,
        "E\u2192O total": 7
      },
      "enemy": {
        "n": 157,
        "matched": 139,
        "cls_ok": 133,
        "own_ok": 133,
        "ok": 128,
        "missed": 18
      }
    },
    "raws79c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        86,
        122
      ],
      "gain_pp": 21.311475409836067,
      "eo": [
        10,
        228
      ],
      "oe": [
        0,
        191
      ],
      "identity": [
        406,
        426,
        490
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 247,
        "matched": 231,
        "cls_ok": 225,
        "own_ok": 218,
        "ok": 215,
        "missed": 16
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
        137,
        175
      ],
      "gain_pp": 28.571428571428566,
      "eo": [
        13,
        511
      ],
      "oe": [
        0,
        470
      ],
      "identity": [
        880,
        1007,
        1008
      ],
      "bad_classes": [
        "null"
      ],
      "failures": {
        "null": 2
      },
      "enemy": {
        "n": 480,
        "matched": 433,
        "cls_ok": 417,
        "own_ok": 420,
        "ok": 409,
        "missed": 47
      }
    }
  },
  "own_rows": {},
  "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
  "weights_sha256": "c9f7bb8123705517335976d31b4b3114ef20d38c9cf68868ed85df7830c2db2d"
}
```
- `/mpac/sdicks02/scratch/live-perc-r3/pooled_gate.py` SHA256`e6083dd5fe2f74834cca289e38410271608764a09bc1a12eb245a448659bd54b`.
- `/mpac/sdicks02/scratch/live-perc-r3/own_conf_report.py` SHA256`a41724351441603fd52245283ba8df99ace3cbbdf21a3008695460c92859fa32`.
- `/mpac/sdicks02/scratch/live-perc-r3/enemy_conf_report.py` SHA256`87a0e53ce0d63d26f3fc117f70f7e26c8d04581da09ca7525923e5d3f17bbcc3`.
