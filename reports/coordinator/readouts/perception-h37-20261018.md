# Perception h37 final evaluator readout

Written 2026-10-18T02:41:07Z; scored 2026-10-18T02:39:42.332973+00:00. Run root `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/h37`; evaluator files `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/<slice>/h37-e12-896.json`. Final12epoch CSV and ALL/FRESH markers observed. Weights last.pt SHA256`c8fde87900d3b6f0780773f2e657cd27e99e746953abaf44b5f2921355da15b0`.

Observed source code-tree SHA256`9b198da10fc10d39210f5ded5f1238996a033985269dae8664c41d6c0ad49474` on 127x04 at2026-10-18T02:40:34Z; KataCR tree SHA256`2780695bff3c575c5cf956af5e72d9748f0249ad2466e7a459222306c653b4c6`. Tree hash=SHA256(compact JSON sorted [relativepath,fileSHA256] array), excluding .git/__pycache__. Launch records do not contain a Git commit pin; these are current archive-tree receipts, not proof of historical immutability. Local LIVE scoring definitions HEAD`feef63aabb5c54531409c70772d95faab79ec4db`; scorer file SHA256 receipts below.

ROUND1 scoring exactly: score>=.5, within1tile matching; pooled old12(raws76,76b,76c,77,78,78b,78c,78d,79,79b,79c,79d); own-Bats gain>=8percentagepoints vsx1h; E→O andO→E error counts no worse; no class exceeding reference errors+1. PENDING re-test only when all excesses<=4 and ownBats gain passes. Per-class correctness is truth-centred, different from pooled identity matching. Missing required coverage=unscorable, not failure. These deterministic counts have no preregistered CI. No inference/evaluation/training was launched. Raw scoring ran under nice19 on candidate hosts; x1h local existing evaluation JSON was passed in-memory to127x08 for scoring, then verdicts aggregated on127x08 under nice19.

## Old-deck pooled
```json
{
  "verdict": "no",
  "own_bats": [
    1860,
    2289
  ],
  "gain_pp": 24.55220620358235,
  "eo": [
    95,
    3848
  ],
  "oe": [
    39,
    4530
  ],
  "identity": [
    8043,
    8462,
    9081
  ],
  "bad_classes": [
    "baby-dragon",
    "giant",
    "hog-rider",
    "null"
  ],
  "failures": {
    "baby-dragon": 3,
    "giant": 3,
    "hog-rider": 2,
    "null": 5
  },
  "enemy": {
    "n": 4009,
    "matched": 3713,
    "cls_ok": 3633,
    "own_ok": 3600,
    "ok": 3558,
    "missed": 296
  }
}
```

| Slice | Verdict | Own Bats correct/truth | E→O | O→E | Bad classes |
|---|---|---|---|---|---|
| raws76 | QUALIFIES | [171, 224] | [4, 270] | [2, 360] | [] |
| raws76b | QUALIFIES | [112, 138] | [2, 262] | [1, 430] | [] |
| raws76c | PENDING re-test | [246, 299] | [6, 337] | [11, 540] | ['wizard'] |
| raws77 | PENDING re-test | [187, 240] | [13, 414] | [8, 427] | [] |
| raws78 | PENDING re-test | [105, 124] | [8, 631] | [2, 342] | ['None'] |
| raws78b | QUALIFIES | [228, 291] | [9, 231] | [1, 451] | [] |
| raws78c | PENDING re-test | [147, 170] | [15, 322] | [0, 333] | ['hog-rider'] |
| raws78d | PENDING re-test | [200, 253] | [5, 397] | [10, 348] | ['baby-dragon'] |
| raws79 | PENDING re-test | [125, 141] | [6, 258] | [3, 321] | ['giant'] |
| raws79b | PENDING re-test | [94, 105] | [7, 157] | [1, 387] | ['None'] |
| raws79c | QUALIFIES | [93, 122] | [10, 228] | [0, 200] | [] |
| raws79d | PENDING re-test | [152, 182] | [10, 341] | [0, 391] | [] |
| raws80 | QUALIFIES | [170, 221] | [6, 695] | [0, 438] | [] |
| raws81 | PENDING re-test | [191, 217] | [10, 342] | [2, 446] | [] |
| raws81b | unscorable | unavailable | unavailable | unavailable |  |
| raws82 | unscorable | unavailable | unavailable | unavailable | ['raws82'] |
| raws83 | no | [0, 0] | [18, 477] | [2, 283] | [] |
| raws83b | unscorable | unavailable | unavailable | unavailable |  |
| raws84 | unscorable | unavailable | unavailable | unavailable |  |
| hogvid | PENDING re-test | [136, 175] | [14, 500] | [1, 471] | ['barbarian'] |

## New-deck own-unit rows
```json
{
  "raws81": {
    "bat": {
      "n": 217,
      "matched": 185,
      "cls_ok": 184,
      "own_ok": 184,
      "ok": 184,
      "missed": 32,
      "owner_wrong": 1
    },
    "skeleton": {
      "n": 168,
      "matched": 160,
      "cls_ok": 155,
      "own_ok": 159,
      "ok": 154,
      "missed": 8,
      "owner_wrong": 1
    },
    "archer": {
      "n": 64,
      "matched": 56,
      "cls_ok": 52,
      "own_ok": 56,
      "ok": 52,
      "missed": 8
    },
    "electro-spirit": {
      "n": 39,
      "matched": 21,
      "cls_ok": 21,
      "own_ok": 21,
      "ok": 21,
      "missed": 18
    },
    "hog-rider": {
      "n": 30,
      "missed": 13,
      "matched": 17,
      "cls_ok": 15,
      "own_ok": 16,
      "ok": 15,
      "owner_wrong": 1
    },
    "valkyrie": null
  },
  "raws83": {
    "bat": null,
    "skeleton": {
      "n": 37,
      "matched": 31,
      "cls_ok": 29,
      "own_ok": 29,
      "ok": 28,
      "missed": 6,
      "owner_wrong": 2
    },
    "archer": {
      "n": 145,
      "matched": 143,
      "cls_ok": 143,
      "own_ok": 143,
      "ok": 143,
      "missed": 2
    },
    "electro-spirit": {
      "n": 31,
      "matched": 24,
      "cls_ok": 24,
      "own_ok": 24,
      "ok": 24,
      "missed": 7
    },
    "hog-rider": {
      "n": 42,
      "matched": 36,
      "cls_ok": 34,
      "own_ok": 36,
      "ok": 34,
      "missed": 6
    },
    "valkyrie": {
      "n": 12,
      "matched": 11,
      "cls_ok": 8,
      "own_ok": 9,
      "ok": 8,
      "owner_wrong": 2,
      "missed": 1
    }
  }
}
```

Each per-class row: n=truth bodies, ok=correctclass+owner, missed/owner_wrong counts as own_conf_report.py. Old pooled enemy troop total is available only when all12 slices exist. Hero row is unscorable: no candidate hero-row/spell_dump artifacts exist in inspected paths. Base-class training semantics remain required for hero Wizard/Knight/MiniPekka/MegaMinion/Musketeer; no separate hero class is scored as a new identity.

HARD26 was NOT loaded: `logs/chain.log` says `2026-10-18T00:45:45Z h37 HARD26: absent`. Thus this run is a seed65 replicate of the h34 recipe, not the planned hero/form-data intervention. No claim of HARD26/HARD27 improvement is valid.

Decision implication: no deploy; old pooled gate is no (None class+5; baby-dragon+3,giant+3,hog-rider+2), raws81 PENDING, current Valkyrie-deck raws83 no. raws80 QUALIFIES alone cannot override the complete gate.

## Evaluation receipts
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/h37-e12-896.json`: 198frames; SHA256`be7a4a7ce49d70157df5456d14dc9cbada94e86fe7b3a7b689fd2d8079c8b0d7`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/h37-e12-896.json`: 199frames; SHA256`c5de36bb1be7a73fe74459a00781cfaf08313df779c2d5a8bf1fdaabb1381490`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/h37-e12-896.json`: 200frames; SHA256`e718c811a7a406207cf17c1daeae626d72f423ec74ef3427a1ba19c962255204`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/h37-e12-896.json`: 199frames; SHA256`7c9b7182a6aef75a5f3b7cfb17588877a29bd5cde5526a46f76f3330f9ac8cec`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/h37-e12-896.json`: 196frames; SHA256`a0299da7c45b139b1adeca1be3439876aabe7f0cd2628d9cadef9e0a460bdc23`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/h37-e12-896.json`: 199frames; SHA256`5969c2a268ff0f02d0b67116d01b8cbe39fad742dc980784685f516eee7ebab7`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/h37-e12-896.json`: 200frames; SHA256`ce11a1770ef993b7312e1f9cf85a7771b7fc4d3f1f624ea06b8ed38576ee3b1d`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/h37-e12-896.json`: 151frames; SHA256`85598423c625ff0e05646a360ac3e8fc19a5d1fdfd70bbbd045bbee8f8bc134b`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/h37-e12-896.json`: 200frames; SHA256`62ac47d352454fbd9f113978ca88edd6516053b4a22984032d5149f9920ec0c9`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/h37-e12-896.json`: 200frames; SHA256`b72c1218c6d181399adb1fdfe691542b731fa8a36b86272581e5bcbed341fe1b`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/h37-e12-896.json`: 200frames; SHA256`d8339d030575988a8e16a0d819594f505d1cf4ed8977df311c24bce8657beb6f`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/h37-e12-896.json`: 200frames; SHA256`75045e8ad6f65424b8a27ef938ca7c69f47db55b2d9830788d414caa331d5cb2`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/h37-e12-896.json`: 200frames; SHA256`2012fa71ef2bb000c74f1ddb26d0e3ffe2923478ec0dcb59a61b286d921249d3`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws81/h37-e12-896.json`: 198frames; SHA256`5c935defe9e93694b88d4cc33b9a95f82e04b83146ad11e8e62f392eb17e0e85`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws83/h37-e12-896.json`: 199frames; SHA256`3d14295f741c0c9519656ec36fcaecf15565f985c5e389475bd12b348be4b27c`.
- `127x04:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/h37-e12-896.json`: 208frames; SHA256`9218f671516a3ac1eaf60d6f0bf7ec3d5fd1db688f5a1235152b7d5577a2286a`.

Scoring summary (all fields):
```json
{
  "old_pooled": {
    "verdict": "no",
    "own_bats": [
      1860,
      2289
    ],
    "gain_pp": 24.55220620358235,
    "eo": [
      95,
      3848
    ],
    "oe": [
      39,
      4530
    ],
    "identity": [
      8043,
      8462,
      9081
    ],
    "bad_classes": [
      "baby-dragon",
      "giant",
      "hog-rider",
      "null"
    ],
    "failures": {
      "baby-dragon": 3,
      "giant": 3,
      "hog-rider": 2,
      "null": 5
    },
    "enemy": {
      "n": 4009,
      "matched": 3713,
      "cls_ok": 3633,
      "own_ok": 3600,
      "ok": 3558,
      "missed": 296
    }
  },
  "per_slice": {
    "raws76": {
      "verdict": "QUALIFIES",
      "own_bats": [
        171,
        224
      ],
      "gain_pp": 26.785714285714278,
      "eo": [
        4,
        270
      ],
      "oe": [
        2,
        360
      ],
      "identity": [
        608,
        632,
        703
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 275,
        "matched": 257,
        "cls_ok": 249,
        "own_ok": 248,
        "ok": 246,
        "missed": 18
      }
    },
    "raws76b": {
      "verdict": "QUALIFIES",
      "own_bats": [
        112,
        138
      ],
      "gain_pp": 26.086956521739136,
      "eo": [
        2,
        262
      ],
      "oe": [
        1,
        430
      ],
      "identity": [
        683,
        701,
        748
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 284,
        "matched": 264,
        "cls_ok": 257,
        "own_ok": 260,
        "ok": 255,
        "missed": 20
      }
    },
    "raws76c": {
      "verdict": "PENDING re-test",
      "own_bats": [
        246,
        299
      ],
      "gain_pp": 31.438127090301005,
      "eo": [
        6,
        337
      ],
      "oe": [
        11,
        540
      ],
      "identity": [
        836,
        884,
        943
      ],
      "bad_classes": [
        "wizard"
      ],
      "failures": {
        "wizard": 2
      },
      "enemy": {
        "n": 340,
        "matched": 319,
        "cls_ok": 316,
        "own_ok": 311,
        "ok": 310,
        "missed": 21
      }
    },
    "raws77": {
      "verdict": "PENDING re-test",
      "own_bats": [
        187,
        240
      ],
      "gain_pp": 21.666666666666668,
      "eo": [
        13,
        414
      ],
      "oe": [
        8,
        427
      ],
      "identity": [
        775,
        848,
        899
      ],
      "bad_classes": [],
      "failures": {
        "E\u2192O total": 2
      },
      "enemy": {
        "n": 403,
        "matched": 373,
        "cls_ok": 364,
        "own_ok": 360,
        "ok": 356,
        "missed": 30
      }
    },
    "raws78": {
      "verdict": "PENDING re-test",
      "own_bats": [
        105,
        124
      ],
      "gain_pp": 24.193548387096776,
      "eo": [
        8,
        631
      ],
      "oe": [
        2,
        342
      ],
      "identity": [
        920,
        987,
        1010
      ],
      "bad_classes": [
        "null"
      ],
      "failures": {
        "null": 2
      },
      "enemy": {
        "n": 630,
        "matched": 592,
        "cls_ok": 587,
        "own_ok": 583,
        "ok": 582,
        "missed": 38
      }
    },
    "raws78b": {
      "verdict": "QUALIFIES",
      "own_bats": [
        228,
        291
      ],
      "gain_pp": 21.649484536082475,
      "eo": [
        9,
        231
      ],
      "oe": [
        1,
        451
      ],
      "identity": [
        669,
        688,
        772
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 252,
        "matched": 233,
        "cls_ok": 222,
        "own_ok": 222,
        "ok": 217,
        "missed": 19
      }
    },
    "raws78c": {
      "verdict": "PENDING re-test",
      "own_bats": [
        147,
        170
      ],
      "gain_pp": 23.529411764705888,
      "eo": [
        15,
        322
      ],
      "oe": [
        0,
        333
      ],
      "identity": [
        633,
        665,
        728
      ],
      "bad_classes": [
        "hog-rider"
      ],
      "failures": {
        "hog-rider": 2
      },
      "enemy": {
        "n": 361,
        "matched": 323,
        "cls_ok": 316,
        "own_ok": 307,
        "ok": 301,
        "missed": 38
      }
    },
    "raws78d": {
      "verdict": "PENDING re-test",
      "own_bats": [
        200,
        253
      ],
      "gain_pp": 28.458498023715418,
      "eo": [
        5,
        397
      ],
      "oe": [
        10,
        348
      ],
      "identity": [
        703,
        756,
        816
      ],
      "bad_classes": [
        "baby-dragon"
      ],
      "failures": {
        "baby-dragon": 2,
        "E\u2192O total": 1
      },
      "enemy": {
        "n": 418,
        "matched": 378,
        "cls_ok": 370,
        "own_ok": 372,
        "ok": 366,
        "missed": 40
      }
    },
    "raws79": {
      "verdict": "PENDING re-test",
      "own_bats": [
        125,
        141
      ],
      "gain_pp": 13.475177304964536,
      "eo": [
        6,
        258
      ],
      "oe": [
        3,
        321
      ],
      "identity": [
        566,
        580,
        613
      ],
      "bad_classes": [
        "giant"
      ],
      "failures": {
        "giant": 2,
        "O\u2192E total": 3
      },
      "enemy": {
        "n": 273,
        "matched": 259,
        "cls_ok": 255,
        "own_ok": 253,
        "ok": 249,
        "missed": 14
      }
    },
    "raws79b": {
      "verdict": "PENDING re-test",
      "own_bats": [
        94,
        105
      ],
      "gain_pp": 26.66666666666667,
      "eo": [
        7,
        157
      ],
      "oe": [
        1,
        387
      ],
      "identity": [
        516,
        552,
        561
      ],
      "bad_classes": [
        "null"
      ],
      "failures": {
        "null": 2
      },
      "enemy": {
        "n": 157,
        "matched": 141,
        "cls_ok": 135,
        "own_ok": 135,
        "ok": 131,
        "missed": 16
      }
    },
    "raws79c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        93,
        122
      ],
      "gain_pp": 27.04918032786885,
      "eo": [
        10,
        228
      ],
      "oe": [
        0,
        200
      ],
      "identity": [
        413,
        433,
        490
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 247,
        "matched": 231,
        "cls_ok": 222,
        "own_ok": 218,
        "ok": 214,
        "missed": 16
      }
    },
    "raws79d": {
      "verdict": "PENDING re-test",
      "own_bats": [
        152,
        182
      ],
      "gain_pp": 19.23076923076923,
      "eo": [
        10,
        341
      ],
      "oe": [
        0,
        391
      ],
      "identity": [
        721,
        736,
        798
      ],
      "bad_classes": [],
      "failures": {
        "E\u2192O total": 1
      },
      "enemy": {
        "n": 369,
        "matched": 343,
        "cls_ok": 340,
        "own_ok": 331,
        "ok": 331,
        "missed": 26
      }
    },
    "raws80": {
      "verdict": "QUALIFIES",
      "own_bats": [
        170,
        221
      ],
      "gain_pp": 28.95927601809955,
      "eo": [
        6,
        695
      ],
      "oe": [
        0,
        438
      ],
      "identity": [
        1106,
        1144,
        1226
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 726,
        "matched": 689,
        "cls_ok": 673,
        "own_ok": 681,
        "ok": 670,
        "missed": 37
      }
    },
    "raws81": {
      "verdict": "PENDING re-test",
      "own_bats": [
        191,
        217
      ],
      "gain_pp": 20.737327188940093,
      "eo": [
        10,
        342
      ],
      "oe": [
        2,
        446
      ],
      "identity": [
        747,
        803,
        911
      ],
      "bad_classes": [],
      "failures": {
        "E\u2192O total": 1
      },
      "enemy": {
        "n": 385,
        "matched": 325,
        "cls_ok": 310,
        "own_ok": 314,
        "ok": 301,
        "missed": 60
      }
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
      "verdict": "no",
      "own_bats": [
        0,
        0
      ],
      "gain_pp": 0.0,
      "eo": [
        18,
        477
      ],
      "oe": [
        2,
        283
      ],
      "identity": [
        735,
        765,
        846
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 537,
        "matched": 479,
        "cls_ok": 474,
        "own_ok": 459,
        "ok": 456,
        "missed": 58
      }
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
        136,
        175
      ],
      "gain_pp": 27.999999999999996,
      "eo": [
        14,
        500
      ],
      "oe": [
        1,
        471
      ],
      "identity": [
        872,
        999,
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
        "cls_ok": 410,
        "own_ok": 411,
        "ok": 400,
        "missed": 53
      }
    }
  },
  "own_rows": {
    "raws81": {
      "bat": {
        "n": 217,
        "matched": 185,
        "cls_ok": 184,
        "own_ok": 184,
        "ok": 184,
        "missed": 32,
        "owner_wrong": 1
      },
      "skeleton": {
        "n": 168,
        "matched": 160,
        "cls_ok": 155,
        "own_ok": 159,
        "ok": 154,
        "missed": 8,
        "owner_wrong": 1
      },
      "archer": {
        "n": 64,
        "matched": 56,
        "cls_ok": 52,
        "own_ok": 56,
        "ok": 52,
        "missed": 8
      },
      "electro-spirit": {
        "n": 39,
        "matched": 21,
        "cls_ok": 21,
        "own_ok": 21,
        "ok": 21,
        "missed": 18
      },
      "hog-rider": {
        "n": 30,
        "missed": 13,
        "matched": 17,
        "cls_ok": 15,
        "own_ok": 16,
        "ok": 15,
        "owner_wrong": 1
      },
      "valkyrie": null
    },
    "raws83": {
      "bat": null,
      "skeleton": {
        "n": 37,
        "matched": 31,
        "cls_ok": 29,
        "own_ok": 29,
        "ok": 28,
        "missed": 6,
        "owner_wrong": 2
      },
      "archer": {
        "n": 145,
        "matched": 143,
        "cls_ok": 143,
        "own_ok": 143,
        "ok": 143,
        "missed": 2
      },
      "electro-spirit": {
        "n": 31,
        "matched": 24,
        "cls_ok": 24,
        "own_ok": 24,
        "ok": 24,
        "missed": 7
      },
      "hog-rider": {
        "n": 42,
        "matched": 36,
        "cls_ok": 34,
        "own_ok": 36,
        "ok": 34,
        "missed": 6
      },
      "valkyrie": {
        "n": 12,
        "matched": 11,
        "cls_ok": 8,
        "own_ok": 9,
        "ok": 8,
        "owner_wrong": 2,
        "missed": 1
      }
    }
  },
  "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
  "weights_sha256": "c8fde87900d3b6f0780773f2e657cd27e99e746953abaf44b5f2921355da15b0"
}
```
- `/mpac/sdicks02/scratch/live-perc-r3/pooled_gate.py` SHA256`e6083dd5fe2f74834cca289e38410271608764a09bc1a12eb245a448659bd54b`.
- `/mpac/sdicks02/scratch/live-perc-r3/own_conf_report.py` SHA256`a41724351441603fd52245283ba8df99ace3cbbdf21a3008695460c92859fa32`.
- `/mpac/sdicks02/scratch/live-perc-r3/enemy_conf_report.py` SHA256`87a0e53ce0d63d26f3fc117f70f7e26c8d04581da09ca7525923e5d3f17bbcc3`.

## RAWS83 gate applicability clarification

Added 2026-10-18T03:09:55Z. RAWS83 has zero own-Bats truth. The unmodified pooled_gate script mechanically prints no because the required +8pp Bats gain cannot be computed; this is not an empirical failure of the Valkyrie deck. Use its own-unit per-class rows and owner-error counts. The old12 pooled failure remains valid and sufficient for the no-deploy implication.

## Complete old12 per-class audit — h37

Computed 2026-10-18T03:46:41.519100+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 5/14 | -9 | False | 242/256 / 233/256 | 1329/1377 / 1311/1377 |
| baby-dragon | 5/2 | +3 | True | 105/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 11/19 | -8 | False | 525/607 / 519/607 | 0/0 / 0/0 |
| bat | 40/111 | -71 | False | 80/97 / 84/97 | 1848/2289 / 1295/2289 |
| battle-ram | 1/2 | -1 | False | 74/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 1/0 | +1 | False | 35/47 / 37/47 | 0/0 / 0/0 |
| cannon | 0/1 | -1 | False | 43/43 / 42/43 | 449/458 / 446/458 |
| giant | 4/1 | +3 | True | 18/18 / 17/18 | 67/82 / 74/82 |
| goblin-brawler | 0/0 | +0 | False | 30/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 0/0 | +0 | False | 16/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 0/0 | +0 | False | 47/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 3/1 | +2 | True | 116/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 100/100 / 97/100 | 0/0 / 0/0 |
| knight | 1/3 | -2 | False | 77/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 3/2 | +1 | False | 32/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 6/6 | +0 | False | 148/160 / 146/160 | 515/562 / 510/562 |
| minion | 6/11 | -5 | False | 127/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 12/21 | -9 | False | 65/88 / 56/88 | 0/0 / 0/0 |
| None | 10/5 | +5 | True | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 8/16 | -8 | False | 840/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 0/1 | -1 | False | 148/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 2/2 | +0 | False | 224/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 48/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 10/10 | +0 | False | 186/223 / 184/223 | 259/304 / 260/304 |
| witch | 2/1 | +1 | False | 65/74 / 59/74 | 0/0 / 0/0 |
| wizard | 4/4 | +0 | False | 61/76 / 57/76 | 0/0 / 0/0 |
