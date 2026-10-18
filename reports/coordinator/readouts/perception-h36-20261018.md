# Perception h36 final evaluator readout

Written 2026-10-18T03:13:09Z; scored 2026-10-18T03:13:09.514553+00:00. Run root `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/h36`; evaluator files `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/<slice>/h36-e12-896.json`. Final12epoch CSV and ALL/FRESH markers observed. Weights last.pt SHA256`5afd3cfafccbc9a29bd5d320f4faca73debd3f51d9d98a0ae89283f22dc0aa2b`.

Observed source code-tree SHA256`f718e5ce526c274c830cfa8093f294b9f5f3f1deec27dd066f0564582ca0995f` on 127x01 at2026-10-18T02:40:34Z; KataCR tree SHA256`2780695bff3c575c5cf956af5e72d9748f0249ad2466e7a459222306c653b4c6`. Tree hash=SHA256(compact JSON sorted [relativepath,fileSHA256] array), excluding .git/__pycache__. Launch records do not contain a Git commit pin; these are current archive-tree receipts, not proof of historical immutability. Local LIVE scoring definitions HEAD`feef63aabb5c54531409c70772d95faab79ec4db`; scorer file SHA256 receipts below.

ROUND1 scoring exactly: score>=.5, within1tile matching; pooled old12(raws76,76b,76c,77,78,78b,78c,78d,79,79b,79c,79d); own-Bats gain>=8percentagepoints vsx1h; E→O andO→E error counts no worse; no class exceeding reference errors+1. PENDING re-test only when all excesses<=4 and ownBats gain passes. Per-class correctness is truth-centred, different from pooled identity matching. Missing required coverage=unscorable, not failure. These deterministic counts have no preregistered CI. No inference/evaluation/training was launched. Raw scoring ran under nice19 on candidate hosts; x1h local existing evaluation JSON was passed in-memory to127x08 for scoring, then verdicts aggregated on127x08 under nice19.

## Old-deck pooled
```json
{
  "verdict": "no",
  "own_bats": [
    1852,
    2289
  ],
  "gain_pp": 24.20270860637833,
  "eo": [
    107,
    3860
  ],
  "oe": [
    34,
    4501
  ],
  "identity": [
    8024,
    8471,
    9081
  ],
  "bad_classes": [
    "cannon",
    "hog-rider",
    "null",
    "skeleton-dragon"
  ],
  "failures": {
    "cannon": 2,
    "hog-rider": 5,
    "null": 10,
    "skeleton-dragon": 2
  },
  "enemy": {
    "n": 4009,
    "matched": 3733,
    "cls_ok": 3649,
    "own_ok": 3605,
    "ok": 3564,
    "missed": 276
  }
}
```

| Slice | Verdict | Own Bats correct/truth | E→O | O→E | Bad classes |
|---|---|---|---|---|---|
| raws76 | PENDING re-test | [179, 224] | [10, 270] | [3, 370] | ['mini-pekka', 'skeleton-dragon'] |
| raws76b | PENDING re-test | [116, 138] | [3, 263] | [1, 431] | ['hog-rider'] |
| raws76c | QUALIFIES | [236, 299] | [1, 337] | [10, 530] | [] |
| raws77 | no | [186, 240] | [19, 414] | [2, 419] | ['None', 'skeleton'] |
| raws78 | PENDING re-test | [111, 124] | [8, 632] | [1, 342] | ['None'] |
| raws78b | QUALIFIES | [223, 291] | [7, 234] | [3, 447] | [] |
| raws78c | QUALIFIES | [142, 170] | [9, 326] | [0, 329] | [] |
| raws78d | PENDING re-test | [199, 253] | [6, 401] | [11, 346] | ['barbarian'] |
| raws79 | PENDING re-test | [123, 141] | [12, 255] | [1, 312] | [] |
| raws79b | PENDING re-test | [92, 105] | [7, 157] | [1, 384] | ['None'] |
| raws79c | PENDING re-test | [96, 122] | [10, 224] | [1, 202] | ['barbarian'] |
| raws79d | no | [149, 182] | [15, 347] | [0, 389] | ['cannon'] |
| raws80 | PENDING re-test | [158, 221] | [10, 696] | [0, 422] | ['valkyrie'] |
| raws81 | PENDING re-test | [189, 217] | [9, 345] | [2, 442] | ['wizard'] |
| raws81b | unscorable | unavailable | unavailable | unavailable |  |
| raws82 | unscorable | unavailable | unavailable | unavailable | ['raws82'] |
| raws83 | no | [0, 0] | [32, 484] | [4, 283] | ['barbarian', 'skeleton'] |
| raws83b | unscorable | unavailable | unavailable | unavailable |  |
| raws84 | unscorable | unavailable | unavailable | unavailable |  |
| hogvid | PENDING re-test | [134, 175] | [16, 501] | [1, 468] | ['bat'] |

## New-deck own-unit rows
```json
{
  "raws81": {
    "bat": {
      "n": 217,
      "matched": 183,
      "cls_ok": 182,
      "own_ok": 181,
      "ok": 181,
      "missed": 34,
      "owner_wrong": 2
    },
    "skeleton": {
      "n": 168,
      "matched": 156,
      "cls_ok": 150,
      "own_ok": 155,
      "ok": 150,
      "missed": 12,
      "owner_wrong": 1
    },
    "archer": {
      "n": 64,
      "matched": 58,
      "cls_ok": 54,
      "own_ok": 58,
      "ok": 54,
      "missed": 6
    },
    "electro-spirit": {
      "n": 39,
      "missed": 20,
      "matched": 19,
      "cls_ok": 19,
      "own_ok": 19,
      "ok": 19
    },
    "hog-rider": {
      "n": 30,
      "matched": 19,
      "cls_ok": 16,
      "own_ok": 19,
      "ok": 16,
      "missed": 11
    },
    "valkyrie": null
  },
  "raws83": {
    "bat": null,
    "skeleton": {
      "n": 37,
      "matched": 32,
      "cls_ok": 30,
      "own_ok": 26,
      "ok": 26,
      "missed": 5,
      "owner_wrong": 6
    },
    "archer": {
      "n": 145,
      "missed": 3,
      "matched": 142,
      "cls_ok": 142,
      "own_ok": 142,
      "ok": 142
    },
    "electro-spirit": {
      "n": 31,
      "matched": 23,
      "cls_ok": 23,
      "own_ok": 23,
      "ok": 23,
      "missed": 8
    },
    "hog-rider": {
      "n": 42,
      "matched": 39,
      "cls_ok": 39,
      "own_ok": 39,
      "ok": 39,
      "missed": 3
    },
    "valkyrie": {
      "n": 12,
      "matched": 10,
      "cls_ok": 8,
      "own_ok": 9,
      "ok": 8,
      "owner_wrong": 1,
      "missed": 2
    }
  }
}
```

Each per-class row: n=truth bodies, ok=correctclass+owner, missed/owner_wrong counts as own_conf_report.py. Old pooled enemy troop total is available only when all12 slices exist. Hero row is unscorable: no candidate hero-row/spell_dump artifacts exist in inspected paths. Base-class training semantics remain required for hero Wizard/Knight/MiniPekka/MegaMinion/Musketeer; no separate hero class is scored as a new identity.

This run uses the h27 recipe plus HARD25 new-deck own units at .20; h35 seed21, h36 seed31. Hero forms are evaluated as base classes; dedicated candidate hero-row artifacts are absent.

Decision implication: raw-gate outcome is no. A single qualifying slice cannot replace pooled/per-class, current-deck, Mac parity and translator checks. No deployment is made; coordinator decides further work.

## Evaluation receipts
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/h36-e12-896.json`: 198frames; SHA256`63d3efb5e99c5832ccaa2b9ad96d87305d9d18711f697986a918a532c123eef7`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/h36-e12-896.json`: 199frames; SHA256`65769159b77c82c76282afb4ef78f70d85f2080399e2af104ecb62c864a5ef6a`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/h36-e12-896.json`: 200frames; SHA256`e96af4ec3266e051e47cf3fd7abf4e768b20d44dac289911d781e7743d62a5f5`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/h36-e12-896.json`: 199frames; SHA256`bea0fe9433e392fd01c9c28b53209b941e10543c708b5a2d00eab3a9927a9251`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/h36-e12-896.json`: 196frames; SHA256`94c14018e8db705c569f826b0c231f5572944b724722c32edc6f696ae7b3fb7f`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/h36-e12-896.json`: 199frames; SHA256`dc30be742e1b4d1a0ed6de5123bed2b2893f486d614f3c9ed77549ab68e579cb`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/h36-e12-896.json`: 200frames; SHA256`0baf22a16480be3be9426162d1e7d6d02634177adab5aa623a253c3783896fab`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/h36-e12-896.json`: 151frames; SHA256`dea20b046633b7e9c5181472cb50217a0c2087185c68561bfdc34de00ce48fcb`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/h36-e12-896.json`: 200frames; SHA256`406600a16b4a55b3dfae2c4d6f8112ce6afe470ab826e057177b4a7001dc3288`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/h36-e12-896.json`: 200frames; SHA256`7b3c6754f6679d6cbaef8cec2af56e977e40be1deba69db5a42aa2384eb6596b`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/h36-e12-896.json`: 200frames; SHA256`586d13194ea3a55b2081bf754c9b9b3a4c6a722bce3c110e0b58ff23f63fe7a2`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/h36-e12-896.json`: 200frames; SHA256`09a8f300b159af04b2ed4d1bcca89b3871fd732e2a083cf644eef1c757a3ae83`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/h36-e12-896.json`: 200frames; SHA256`a1733f71232458089fc595beff8bdcc5369c2723491cc0b7abd0782da70812bb`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws81/h36-e12-896.json`: 198frames; SHA256`ee89ebbaf03f27d4247dd047b94ca905b7c6651f541ee66bd1d36dc520fcd7ba`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws83/h36-e12-896.json`: 199frames; SHA256`74d70abe1900d2963f312c1fd7a102739d5d9634a3f503d73df5fc9b04afaa36`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/h36-e12-896.json`: 208frames; SHA256`6fb4bcd7149a6c8bd1cc90a53e0261eed6994eb5b84b00dcab68e38b8d2abf1f`.

Scoring summary (all fields):
```json
{
  "old_pooled": {
    "verdict": "no",
    "own_bats": [
      1852,
      2289
    ],
    "gain_pp": 24.20270860637833,
    "eo": [
      107,
      3860
    ],
    "oe": [
      34,
      4501
    ],
    "identity": [
      8024,
      8471,
      9081
    ],
    "bad_classes": [
      "cannon",
      "hog-rider",
      "null",
      "skeleton-dragon"
    ],
    "failures": {
      "cannon": 2,
      "hog-rider": 5,
      "null": 10,
      "skeleton-dragon": 2
    },
    "enemy": {
      "n": 4009,
      "matched": 3733,
      "cls_ok": 3649,
      "own_ok": 3605,
      "ok": 3564,
      "missed": 276
    }
  },
  "per_slice": {
    "raws76": {
      "verdict": "PENDING re-test",
      "own_bats": [
        179,
        224
      ],
      "gain_pp": 30.35714285714286,
      "eo": [
        10,
        270
      ],
      "oe": [
        3,
        370
      ],
      "identity": [
        610,
        645,
        703
      ],
      "bad_classes": [
        "mini-pekka",
        "skeleton-dragon"
      ],
      "failures": {
        "mini-pekka": 2,
        "skeleton-dragon": 2,
        "E\u2192O total": 3
      },
      "enemy": {
        "n": 275,
        "matched": 258,
        "cls_ok": 252,
        "own_ok": 243,
        "ok": 242,
        "missed": 17
      }
    },
    "raws76b": {
      "verdict": "PENDING re-test",
      "own_bats": [
        116,
        138
      ],
      "gain_pp": 28.985507246376805,
      "eo": [
        3,
        263
      ],
      "oe": [
        1,
        431
      ],
      "identity": [
        685,
        704,
        748
      ],
      "bad_classes": [
        "hog-rider"
      ],
      "failures": {
        "hog-rider": 2
      },
      "enemy": {
        "n": 284,
        "matched": 266,
        "cls_ok": 259,
        "own_ok": 261,
        "ok": 256,
        "missed": 18
      }
    },
    "raws76c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        236,
        299
      ],
      "gain_pp": 28.093645484949835,
      "eo": [
        1,
        337
      ],
      "oe": [
        10,
        530
      ],
      "identity": [
        834,
        878,
        943
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 340,
        "matched": 320,
        "cls_ok": 313,
        "own_ok": 314,
        "ok": 311,
        "missed": 20
      }
    },
    "raws77": {
      "verdict": "no",
      "own_bats": [
        186,
        240
      ],
      "gain_pp": 21.250000000000004,
      "eo": [
        19,
        414
      ],
      "oe": [
        2,
        419
      ],
      "identity": [
        763,
        842,
        899
      ],
      "bad_classes": [
        "null",
        "skeleton"
      ],
      "failures": {
        "null": 3,
        "skeleton": 3,
        "E\u2192O total": 8
      },
      "enemy": {
        "n": 403,
        "matched": 375,
        "cls_ok": 362,
        "own_ok": 358,
        "ok": 350,
        "missed": 28
      }
    },
    "raws78": {
      "verdict": "PENDING re-test",
      "own_bats": [
        111,
        124
      ],
      "gain_pp": 29.032258064516125,
      "eo": [
        8,
        632
      ],
      "oe": [
        1,
        342
      ],
      "identity": [
        924,
        988,
        1010
      ],
      "bad_classes": [
        "null"
      ],
      "failures": {
        "null": 4
      },
      "enemy": {
        "n": 630,
        "matched": 593,
        "cls_ok": 587,
        "own_ok": 584,
        "ok": 584,
        "missed": 37
      }
    },
    "raws78b": {
      "verdict": "QUALIFIES",
      "own_bats": [
        223,
        291
      ],
      "gain_pp": 19.931271477663238,
      "eo": [
        7,
        234
      ],
      "oe": [
        3,
        447
      ],
      "identity": [
        671,
        690,
        772
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 252,
        "matched": 240,
        "cls_ok": 229,
        "own_ok": 228,
        "ok": 226,
        "missed": 12
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
        9,
        326
      ],
      "oe": [
        0,
        329
      ],
      "identity": [
        640,
        669,
        728
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 361,
        "matched": 326,
        "cls_ok": 321,
        "own_ok": 317,
        "ok": 313,
        "missed": 35
      }
    },
    "raws78d": {
      "verdict": "PENDING re-test",
      "own_bats": [
        199,
        253
      ],
      "gain_pp": 28.06324110671937,
      "eo": [
        6,
        401
      ],
      "oe": [
        11,
        346
      ],
      "identity": [
        704,
        758,
        816
      ],
      "bad_classes": [
        "barbarian"
      ],
      "failures": {
        "barbarian": 2,
        "E\u2192O total": 2
      },
      "enemy": {
        "n": 418,
        "matched": 380,
        "cls_ok": 375,
        "own_ok": 374,
        "ok": 370,
        "missed": 38
      }
    },
    "raws79": {
      "verdict": "PENDING re-test",
      "own_bats": [
        123,
        141
      ],
      "gain_pp": 12.056737588652489,
      "eo": [
        12,
        255
      ],
      "oe": [
        1,
        312
      ],
      "identity": [
        550,
        568,
        613
      ],
      "bad_classes": [],
      "failures": {
        "O\u2192E total": 1
      },
      "enemy": {
        "n": 273,
        "matched": 256,
        "cls_ok": 251,
        "own_ok": 244,
        "ok": 239,
        "missed": 17
      }
    },
    "raws79b": {
      "verdict": "PENDING re-test",
      "own_bats": [
        92,
        105
      ],
      "gain_pp": 24.761904761904763,
      "eo": [
        7,
        157
      ],
      "oe": [
        1,
        384
      ],
      "identity": [
        510,
        555,
        561
      ],
      "bad_classes": [
        "null"
      ],
      "failures": {
        "null": 3
      },
      "enemy": {
        "n": 157,
        "matched": 139,
        "cls_ok": 132,
        "own_ok": 134,
        "ok": 129,
        "missed": 18
      }
    },
    "raws79c": {
      "verdict": "PENDING re-test",
      "own_bats": [
        96,
        122
      ],
      "gain_pp": 29.508196721311474,
      "eo": [
        10,
        224
      ],
      "oe": [
        1,
        202
      ],
      "identity": [
        414,
        433,
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
        "matched": 230,
        "cls_ok": 222,
        "own_ok": 215,
        "ok": 213,
        "missed": 17
      }
    },
    "raws79d": {
      "verdict": "no",
      "own_bats": [
        149,
        182
      ],
      "gain_pp": 17.582417582417577,
      "eo": [
        15,
        347
      ],
      "oe": [
        0,
        389
      ],
      "identity": [
        719,
        741,
        798
      ],
      "bad_classes": [
        "cannon"
      ],
      "failures": {
        "cannon": 2,
        "E\u2192O total": 6
      },
      "enemy": {
        "n": 369,
        "matched": 350,
        "cls_ok": 346,
        "own_ok": 333,
        "ok": 331,
        "missed": 19
      }
    },
    "raws80": {
      "verdict": "PENDING re-test",
      "own_bats": [
        158,
        221
      ],
      "gain_pp": 23.52941176470588,
      "eo": [
        10,
        696
      ],
      "oe": [
        0,
        422
      ],
      "identity": [
        1089,
        1130,
        1226
      ],
      "bad_classes": [
        "valkyrie"
      ],
      "failures": {
        "valkyrie": 3
      },
      "enemy": {
        "n": 726,
        "matched": 689,
        "cls_ok": 675,
        "own_ok": 678,
        "ok": 668,
        "missed": 37
      }
    },
    "raws81": {
      "verdict": "PENDING re-test",
      "own_bats": [
        189,
        217
      ],
      "gain_pp": 19.81566820276498,
      "eo": [
        9,
        345
      ],
      "oe": [
        2,
        442
      ],
      "identity": [
        750,
        799,
        911
      ],
      "bad_classes": [
        "wizard"
      ],
      "failures": {
        "wizard": 2
      },
      "enemy": {
        "n": 385,
        "matched": 329,
        "cls_ok": 316,
        "own_ok": 319,
        "ok": 309,
        "missed": 56
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
        32,
        484
      ],
      "oe": [
        4,
        283
      ],
      "identity": [
        727,
        777,
        846
      ],
      "bad_classes": [
        "barbarian",
        "skeleton"
      ],
      "failures": {
        "barbarian": 12,
        "skeleton": 3,
        "E\u2192O total": 10,
        "O\u2192E total": 1
      },
      "enemy": {
        "n": 537,
        "matched": 483,
        "cls_ok": 477,
        "own_ok": 450,
        "ok": 446,
        "missed": 54
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
        134,
        175
      ],
      "gain_pp": 26.85714285714285,
      "eo": [
        16,
        501
      ],
      "oe": [
        1,
        468
      ],
      "identity": [
        865,
        1001,
        1008
      ],
      "bad_classes": [
        "bat"
      ],
      "failures": {
        "bat": 3,
        "E\u2192O total": 1
      },
      "enemy": {
        "n": 480,
        "matched": 428,
        "cls_ok": 405,
        "own_ok": 412,
        "ok": 396,
        "missed": 52
      }
    }
  },
  "own_rows": {
    "raws81": {
      "bat": {
        "n": 217,
        "matched": 183,
        "cls_ok": 182,
        "own_ok": 181,
        "ok": 181,
        "missed": 34,
        "owner_wrong": 2
      },
      "skeleton": {
        "n": 168,
        "matched": 156,
        "cls_ok": 150,
        "own_ok": 155,
        "ok": 150,
        "missed": 12,
        "owner_wrong": 1
      },
      "archer": {
        "n": 64,
        "matched": 58,
        "cls_ok": 54,
        "own_ok": 58,
        "ok": 54,
        "missed": 6
      },
      "electro-spirit": {
        "n": 39,
        "missed": 20,
        "matched": 19,
        "cls_ok": 19,
        "own_ok": 19,
        "ok": 19
      },
      "hog-rider": {
        "n": 30,
        "matched": 19,
        "cls_ok": 16,
        "own_ok": 19,
        "ok": 16,
        "missed": 11
      },
      "valkyrie": null
    },
    "raws83": {
      "bat": null,
      "skeleton": {
        "n": 37,
        "matched": 32,
        "cls_ok": 30,
        "own_ok": 26,
        "ok": 26,
        "missed": 5,
        "owner_wrong": 6
      },
      "archer": {
        "n": 145,
        "missed": 3,
        "matched": 142,
        "cls_ok": 142,
        "own_ok": 142,
        "ok": 142
      },
      "electro-spirit": {
        "n": 31,
        "matched": 23,
        "cls_ok": 23,
        "own_ok": 23,
        "ok": 23,
        "missed": 8
      },
      "hog-rider": {
        "n": 42,
        "matched": 39,
        "cls_ok": 39,
        "own_ok": 39,
        "ok": 39,
        "missed": 3
      },
      "valkyrie": {
        "n": 12,
        "matched": 10,
        "cls_ok": 8,
        "own_ok": 9,
        "ok": 8,
        "owner_wrong": 1,
        "missed": 2
      }
    }
  },
  "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
  "weights_sha256": "5afd3cfafccbc9a29bd5d320f4faca73debd3f51d9d98a0ae89283f22dc0aa2b"
}
```
- `/mpac/sdicks02/scratch/live-perc-r3/pooled_gate.py` SHA256`e6083dd5fe2f74834cca289e38410271608764a09bc1a12eb245a448659bd54b`.
- `/mpac/sdicks02/scratch/live-perc-r3/own_conf_report.py` SHA256`a41724351441603fd52245283ba8df99ace3cbbdf21a3008695460c92859fa32`.
- `/mpac/sdicks02/scratch/live-perc-r3/enemy_conf_report.py` SHA256`87a0e53ce0d63d26f3fc117f70f7e26c8d04581da09ca7525923e5d3f17bbcc3`.

RAWS83 has zero own-Bats truth: its mechanical no verdict from the old Bats-gain gate is inapplicable; use per-class own-unit counts. None/null in bad_classes is the literal normalized truth-identity None category (owner matching includes it), not absence of class regressions or an unmatched prediction. Clarified 2026-10-18T03:13:12Z.

## Complete old12 per-class audit — h36

Computed 2026-10-18T03:46:41.519100+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 9/14 | -5 | False | 240/256 / 233/256 | 1315/1377 / 1311/1377 |
| baby-dragon | 2/2 | +0 | False | 111/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 18/19 | -1 | False | 522/607 / 519/607 | 0/0 / 0/0 |
| bat | 37/111 | -74 | False | 85/97 / 84/97 | 1841/2289 / 1295/2289 |
| battle-ram | 1/2 | -1 | False | 74/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 0/0 | +0 | False | 37/47 / 37/47 | 0/0 / 0/0 |
| cannon | 3/1 | +2 | True | 40/43 / 42/43 | 448/458 / 446/458 |
| giant | 1/1 | +0 | False | 18/18 / 17/18 | 74/82 / 74/82 |
| goblin-brawler | 1/0 | +1 | False | 29/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 0/0 | +0 | False | 16/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 0/0 | +0 | False | 47/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 6/1 | +5 | True | 125/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 100/100 / 97/100 | 0/0 / 0/0 |
| knight | 0/3 | -3 | False | 78/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 2/2 | +0 | False | 33/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 6/6 | +0 | False | 150/160 / 146/160 | 514/562 / 510/562 |
| minion | 7/11 | -4 | False | 125/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 7/21 | -14 | False | 71/88 / 56/88 | 0/0 / 0/0 |
| None | 15/5 | +10 | True | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 10/16 | -6 | False | 837/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 3/1 | +2 | True | 145/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 1/2 | -1 | False | 220/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 48/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 10/10 | +0 | False | 177/223 / 184/223 | 251/304 / 260/304 |
| witch | 1/1 | +0 | False | 66/74 / 59/74 | 0/0 / 0/0 |
| wizard | 1/4 | -3 | False | 64/76 / 57/76 | 0/0 / 0/0 |
