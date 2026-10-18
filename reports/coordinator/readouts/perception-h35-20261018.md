# Perception h35 final evaluator readout

Written 2026-10-18T03:09:27Z; scored 2026-10-18T03:09:27.600270+00:00. Run root `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/h35`; evaluator files `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/<slice>/h35-e12-896.json`. Final12epoch CSV and ALL/FRESH markers observed. Weights last.pt SHA256`d178330bb585b05a0bb0af8aa1825e311f9d29b25fd229912d5c492305a7e061`.

Observed source code-tree SHA256`f718e5ce526c274c830cfa8093f294b9f5f3f1deec27dd066f0564582ca0995f` on 127x01 at2026-10-18T02:40:34Z; KataCR tree SHA256`2780695bff3c575c5cf956af5e72d9748f0249ad2466e7a459222306c653b4c6`. Tree hash=SHA256(compact JSON sorted [relativepath,fileSHA256] array), excluding .git/__pycache__. Launch records do not contain a Git commit pin; these are current archive-tree receipts, not proof of historical immutability. Local LIVE scoring definitions HEAD`feef63aabb5c54531409c70772d95faab79ec4db`; scorer file SHA256 receipts below.

ROUND1 scoring exactly: score>=.5, within1tile matching; pooled old12(raws76,76b,76c,77,78,78b,78c,78d,79,79b,79c,79d); own-Bats gain>=8percentagepoints vsx1h; E→O andO→E error counts no worse; no class exceeding reference errors+1. PENDING re-test only when all excesses<=4 and ownBats gain passes. Per-class correctness is truth-centred, different from pooled identity matching. Missing required coverage=unscorable, not failure. These deterministic counts have no preregistered CI. No inference/evaluation/training was launched. Raw scoring ran under nice19 on candidate hosts; x1h local existing evaluation JSON was passed in-memory to127x08 for scoring, then verdicts aggregated on127x08 under nice19.

## Old-deck pooled
```json
{
  "verdict": "no",
  "own_bats": [
    1828,
    2289
  ],
  "gain_pp": 23.154215814766268,
  "eo": [
    88,
    3886
  ],
  "oe": [
    33,
    4483
  ],
  "identity": [
    8038,
    8476,
    9081
  ],
  "bad_classes": [
    "null"
  ],
  "failures": {
    "null": 7
  },
  "enemy": {
    "n": 4009,
    "matched": 3742,
    "cls_ok": 3662,
    "own_ok": 3633,
    "ok": 3591,
    "missed": 267
  }
}
```

| Slice | Verdict | Own Bats correct/truth | E→O | O→E | Bad classes |
|---|---|---|---|---|---|
| raws76 | QUALIFIES | [170, 224] | [5, 273] | [3, 359] | [] |
| raws76b | QUALIFIES | [114, 138] | [1, 262] | [0, 432] | [] |
| raws76c | QUALIFIES | [233, 299] | [6, 337] | [10, 529] | [] |
| raws77 | PENDING re-test | [186, 240] | [13, 415] | [3, 419] | ['None'] |
| raws78 | PENDING re-test | [106, 124] | [6, 633] | [3, 339] | ['None'] |
| raws78b | QUALIFIES | [226, 291] | [7, 236] | [3, 449] | [] |
| raws78c | QUALIFIES | [145, 170] | [11, 327] | [0, 332] | [] |
| raws78d | QUALIFIES | [197, 253] | [4, 408] | [8, 346] | [] |
| raws79 | PENDING re-test | [123, 141] | [7, 262] | [1, 314] | [] |
| raws79b | PENDING re-test | [91, 105] | [8, 165] | [1, 383] | [] |
| raws79c | QUALIFIES | [92, 122] | [9, 224] | [1, 197] | [] |
| raws79d | PENDING re-test | [145, 182] | [11, 344] | [0, 384] | [] |
| raws80 | QUALIFIES | [170, 221] | [3, 702] | [0, 440] | [] |
| raws81 | QUALIFIES | [186, 217] | [9, 337] | [0, 434] | [] |
| raws81b | unscorable | unavailable | unavailable | unavailable |  |
| raws82 | unscorable | unavailable | unavailable | unavailable | ['raws82'] |
| raws83 | no | [0, 0] | [18, 479] | [2, 274] | [] |
| raws83b | unscorable | unavailable | unavailable | unavailable |  |
| raws84 | unscorable | unavailable | unavailable | unavailable |  |
| hogvid | PENDING re-test | [136, 175] | [19, 506] | [2, 470] | ['barbarian', 'bat', 'mini-pekka'] |

## New-deck own-unit rows
```json
{
  "raws81": {
    "bat": {
      "n": 217,
      "matched": 180,
      "cls_ok": 179,
      "own_ok": 179,
      "ok": 179,
      "missed": 37,
      "owner_wrong": 1
    },
    "skeleton": {
      "n": 168,
      "matched": 157,
      "cls_ok": 152,
      "own_ok": 156,
      "ok": 152,
      "missed": 11,
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
      "matched": 17,
      "cls_ok": 17,
      "own_ok": 17,
      "ok": 17,
      "missed": 22
    },
    "hog-rider": {
      "n": 30,
      "matched": 16,
      "cls_ok": 15,
      "own_ok": 16,
      "ok": 15,
      "missed": 14
    },
    "valkyrie": null
  },
  "raws83": {
    "bat": null,
    "skeleton": {
      "n": 37,
      "matched": 31,
      "cls_ok": 29,
      "own_ok": 28,
      "ok": 28,
      "missed": 6,
      "owner_wrong": 3
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
      "matched": 21,
      "cls_ok": 21,
      "own_ok": 20,
      "ok": 20,
      "missed": 10,
      "owner_wrong": 1
    },
    "hog-rider": {
      "n": 42,
      "matched": 30,
      "cls_ok": 29,
      "own_ok": 30,
      "ok": 29,
      "missed": 12
    },
    "valkyrie": {
      "n": 12,
      "matched": 11,
      "cls_ok": 9,
      "own_ok": 10,
      "ok": 9,
      "owner_wrong": 1,
      "missed": 1
    }
  }
}
```

Each per-class row: n=truth bodies, ok=correctclass+owner, missed/owner_wrong counts as own_conf_report.py. Old pooled enemy troop total is available only when all12 slices exist. Hero row is unscorable: no candidate hero-row/spell_dump artifacts exist in inspected paths. Base-class training semantics remain required for hero Wizard/Knight/MiniPekka/MegaMinion/Musketeer; no separate hero class is scored as a new identity.

This run uses the h27 recipe plus HARD25 new-deck own units at .20; h35 seed21, h36 seed31. Hero forms are evaluated as base classes; dedicated candidate hero-row artifacts are absent.

Decision implication: raw-gate outcome is no. A single qualifying slice cannot replace pooled/per-class, current-deck, Mac parity and translator checks. No deployment is made; coordinator decides further work.

## Evaluation receipts
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/h35-e12-896.json`: 198frames; SHA256`ad246c39006b394d64f4cf38168bae1fa120db4ff8a457d503b8dcac39994171`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/h35-e12-896.json`: 199frames; SHA256`5d381804b0a1b94bf3f73a4eabf12969bae9a1c87d24482887512a2669fddf91`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/h35-e12-896.json`: 200frames; SHA256`08acd3bfa5bb959ea8113d9c21ccebf4caa6979bf404ab8415005b2bf7e7c467`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/h35-e12-896.json`: 199frames; SHA256`d039cbd422af0bcd005825f5e08242b8c4e8d6803731dbaee28e6953685b0cc5`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/h35-e12-896.json`: 196frames; SHA256`b41a13bc35514bc6ba6ace015f011ab7428590b66b92f48ff43cf541ffa592eb`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/h35-e12-896.json`: 199frames; SHA256`e050c6130c6eeb954c0e2a100afc4f0bbd07893be80446813276fe5411a0b0ef`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/h35-e12-896.json`: 200frames; SHA256`b7855ef9ef118f8f50ea2bf6c4e80147a6d5d3c2603bf8b8c9f9e90140c91521`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/h35-e12-896.json`: 151frames; SHA256`2ee67e9a58f9201cf919dbfd3646d20a006f8f65da9d22b90a4082d7bdfa8698`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/h35-e12-896.json`: 200frames; SHA256`dc7142d260fa1af5d6a1acafe5943d95b6d96acb923f18ab2203b9aceb904392`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/h35-e12-896.json`: 200frames; SHA256`432b96696f5939f65b921ac5d344bfcb7095c445c1371311062726c57a802e83`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/h35-e12-896.json`: 200frames; SHA256`d3d69b0aa2b5640ed87ff33f14032ce74a20e2695bf977a1f28c4644add9304c`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/h35-e12-896.json`: 200frames; SHA256`3459e655edc70a4f026806a1ea866a0b6fd50c8d182ffa24e315d89256394c45`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/h35-e12-896.json`: 200frames; SHA256`b26a243b5f276df8f3e56434d05bcd06093ca63667b6c11a93e03fd1e49508ea`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws81/h35-e12-896.json`: 198frames; SHA256`64f47a7b117cf03255115e4a8604acc7fcced3435a802eb6c8eb80cab6400ebb`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws83/h35-e12-896.json`: 199frames; SHA256`db91a99ab2f2f1b6900550753614ce9e5eaf2fe263c212f98bf19f5beac9805f`.
- `127x01:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/h35-e12-896.json`: 208frames; SHA256`75538829369dd4e1a5b0b42e73b3344e0ae724a5285a6272bf2adbe8f6fc467c`.

Scoring summary (all fields):
```json
{
  "old_pooled": {
    "verdict": "no",
    "own_bats": [
      1828,
      2289
    ],
    "gain_pp": 23.154215814766268,
    "eo": [
      88,
      3886
    ],
    "oe": [
      33,
      4483
    ],
    "identity": [
      8038,
      8476,
      9081
    ],
    "bad_classes": [
      "null"
    ],
    "failures": {
      "null": 7
    },
    "enemy": {
      "n": 4009,
      "matched": 3742,
      "cls_ok": 3662,
      "own_ok": 3633,
      "ok": 3591,
      "missed": 267
    }
  },
  "per_slice": {
    "raws76": {
      "verdict": "QUALIFIES",
      "own_bats": [
        170,
        224
      ],
      "gain_pp": 26.339285714285708,
      "eo": [
        5,
        273
      ],
      "oe": [
        3,
        359
      ],
      "identity": [
        607,
        638,
        703
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 275,
        "matched": 261,
        "cls_ok": 254,
        "own_ok": 251,
        "ok": 250,
        "missed": 14
      }
    },
    "raws76b": {
      "verdict": "QUALIFIES",
      "own_bats": [
        114,
        138
      ],
      "gain_pp": 27.536231884057973,
      "eo": [
        1,
        262
      ],
      "oe": [
        0,
        432
      ],
      "identity": [
        688,
        703,
        748
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 284,
        "matched": 264,
        "cls_ok": 259,
        "own_ok": 260,
        "ok": 258,
        "missed": 20
      }
    },
    "raws76c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        233,
        299
      ],
      "gain_pp": 27.090301003344486,
      "eo": [
        6,
        337
      ],
      "oe": [
        10,
        529
      ],
      "identity": [
        828,
        881,
        943
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 340,
        "matched": 320,
        "cls_ok": 317,
        "own_ok": 312,
        "ok": 311,
        "missed": 20
      }
    },
    "raws77": {
      "verdict": "PENDING re-test",
      "own_bats": [
        186,
        240
      ],
      "gain_pp": 21.250000000000004,
      "eo": [
        13,
        415
      ],
      "oe": [
        3,
        419
      ],
      "identity": [
        769,
        841,
        899
      ],
      "bad_classes": [
        "null"
      ],
      "failures": {
        "null": 4,
        "E\u2192O total": 2
      },
      "enemy": {
        "n": 403,
        "matched": 369,
        "cls_ok": 361,
        "own_ok": 361,
        "ok": 355,
        "missed": 34
      }
    },
    "raws78": {
      "verdict": "PENDING re-test",
      "own_bats": [
        106,
        124
      ],
      "gain_pp": 25.0,
      "eo": [
        6,
        633
      ],
      "oe": [
        3,
        339
      ],
      "identity": [
        915,
        986,
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
        "cls_ok": 585,
        "own_ok": 585,
        "ok": 582,
        "missed": 38
      }
    },
    "raws78b": {
      "verdict": "QUALIFIES",
      "own_bats": [
        226,
        291
      ],
      "gain_pp": 20.96219931271478,
      "eo": [
        7,
        236
      ],
      "oe": [
        3,
        449
      ],
      "identity": [
        676,
        693,
        772
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 252,
        "matched": 241,
        "cls_ok": 228,
        "own_ok": 229,
        "ok": 224,
        "missed": 11
      }
    },
    "raws78c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        145,
        170
      ],
      "gain_pp": 22.352941176470587,
      "eo": [
        11,
        327
      ],
      "oe": [
        0,
        332
      ],
      "identity": [
        645,
        673,
        728
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 361,
        "matched": 328,
        "cls_ok": 324,
        "own_ok": 316,
        "ok": 313,
        "missed": 33
      }
    },
    "raws78d": {
      "verdict": "QUALIFIES",
      "own_bats": [
        197,
        253
      ],
      "gain_pp": 27.27272727272727,
      "eo": [
        4,
        408
      ],
      "oe": [
        8,
        346
      ],
      "identity": [
        713,
        766,
        816
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 418,
        "matched": 388,
        "cls_ok": 378,
        "own_ok": 383,
        "ok": 375,
        "missed": 30
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
        7,
        262
      ],
      "oe": [
        1,
        314
      ],
      "identity": [
        564,
        577,
        613
      ],
      "bad_classes": [],
      "failures": {
        "O\u2192E total": 1
      },
      "enemy": {
        "n": 273,
        "matched": 263,
        "cls_ok": 258,
        "own_ok": 256,
        "ok": 251,
        "missed": 10
      }
    },
    "raws79b": {
      "verdict": "PENDING re-test",
      "own_bats": [
        91,
        105
      ],
      "gain_pp": 23.809523809523814,
      "eo": [
        8,
        165
      ],
      "oe": [
        1,
        383
      ],
      "identity": [
        509,
        558,
        561
      ],
      "bad_classes": [],
      "failures": {
        "E\u2192O total": 1
      },
      "enemy": {
        "n": 157,
        "matched": 140,
        "cls_ok": 133,
        "own_ok": 132,
        "ok": 128,
        "missed": 17
      }
    },
    "raws79c": {
      "verdict": "QUALIFIES",
      "own_bats": [
        92,
        122
      ],
      "gain_pp": 26.22950819672131,
      "eo": [
        9,
        224
      ],
      "oe": [
        1,
        197
      ],
      "identity": [
        409,
        425,
        490
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 247,
        "matched": 230,
        "cls_ok": 222,
        "own_ok": 216,
        "ok": 213,
        "missed": 17
      }
    },
    "raws79d": {
      "verdict": "PENDING re-test",
      "own_bats": [
        145,
        182
      ],
      "gain_pp": 15.384615384615374,
      "eo": [
        11,
        344
      ],
      "oe": [
        0,
        384
      ],
      "identity": [
        715,
        735,
        798
      ],
      "bad_classes": [],
      "failures": {
        "E\u2192O total": 2
      },
      "enemy": {
        "n": 369,
        "matched": 346,
        "cls_ok": 343,
        "own_ok": 332,
        "ok": 331,
        "missed": 23
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
        3,
        702
      ],
      "oe": [
        0,
        440
      ],
      "identity": [
        1113,
        1153,
        1226
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 726,
        "matched": 692,
        "cls_ok": 673,
        "own_ok": 688,
        "ok": 672,
        "missed": 34
      }
    },
    "raws81": {
      "verdict": "QUALIFIES",
      "own_bats": [
        186,
        217
      ],
      "gain_pp": 18.433179723502302,
      "eo": [
        9,
        337
      ],
      "oe": [
        0,
        434
      ],
      "identity": [
        740,
        785,
        911
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 385,
        "matched": 321,
        "cls_ok": 309,
        "own_ok": 312,
        "ok": 304,
        "missed": 64
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
        479
      ],
      "oe": [
        2,
        274
      ],
      "identity": [
        729,
        759,
        846
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 537,
        "matched": 478,
        "cls_ok": 473,
        "own_ok": 459,
        "ok": 457,
        "missed": 59
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
        19,
        506
      ],
      "oe": [
        2,
        470
      ],
      "identity": [
        870,
        1000,
        1008
      ],
      "bad_classes": [
        "barbarian",
        "bat",
        "mini-pekka"
      ],
      "failures": {
        "barbarian": 3,
        "bat": 3,
        "mini-pekka": 2,
        "E\u2192O total": 4,
        "O\u2192E total": 1
      },
      "enemy": {
        "n": 480,
        "matched": 430,
        "cls_ok": 414,
        "own_ok": 410,
        "ok": 401,
        "missed": 50
      }
    }
  },
  "own_rows": {
    "raws81": {
      "bat": {
        "n": 217,
        "matched": 180,
        "cls_ok": 179,
        "own_ok": 179,
        "ok": 179,
        "missed": 37,
        "owner_wrong": 1
      },
      "skeleton": {
        "n": 168,
        "matched": 157,
        "cls_ok": 152,
        "own_ok": 156,
        "ok": 152,
        "missed": 11,
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
        "matched": 17,
        "cls_ok": 17,
        "own_ok": 17,
        "ok": 17,
        "missed": 22
      },
      "hog-rider": {
        "n": 30,
        "matched": 16,
        "cls_ok": 15,
        "own_ok": 16,
        "ok": 15,
        "missed": 14
      },
      "valkyrie": null
    },
    "raws83": {
      "bat": null,
      "skeleton": {
        "n": 37,
        "matched": 31,
        "cls_ok": 29,
        "own_ok": 28,
        "ok": 28,
        "missed": 6,
        "owner_wrong": 3
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
        "matched": 21,
        "cls_ok": 21,
        "own_ok": 20,
        "ok": 20,
        "missed": 10,
        "owner_wrong": 1
      },
      "hog-rider": {
        "n": 42,
        "matched": 30,
        "cls_ok": 29,
        "own_ok": 30,
        "ok": 29,
        "missed": 12
      },
      "valkyrie": {
        "n": 12,
        "matched": 11,
        "cls_ok": 9,
        "own_ok": 10,
        "ok": 9,
        "owner_wrong": 1,
        "missed": 1
      }
    }
  },
  "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
  "weights_sha256": "d178330bb585b05a0bb0af8aa1825e311f9d29b25fd229912d5c492305a7e061"
}
```
- `/mpac/sdicks02/scratch/live-perc-r3/pooled_gate.py` SHA256`e6083dd5fe2f74834cca289e38410271608764a09bc1a12eb245a448659bd54b`.
- `/mpac/sdicks02/scratch/live-perc-r3/own_conf_report.py` SHA256`a41724351441603fd52245283ba8df99ace3cbbdf21a3008695460c92859fa32`.
- `/mpac/sdicks02/scratch/live-perc-r3/enemy_conf_report.py` SHA256`87a0e53ce0d63d26f3fc117f70f7e26c8d04581da09ca7525923e5d3f17bbcc3`.

## RAWS83 gate applicability clarification

Added 2026-10-18T03:09:55Z. RAWS83 has zero own-Bats truth. The unmodified pooled_gate script mechanically prints no because the required +8pp Bats gain cannot be computed; this is not an empirical failure of the Valkyrie deck. Use its own-unit per-class rows and owner-error counts. The old12 pooled failure remains valid and sufficient for the no-deploy implication.

## Complete old12 per-class audit — h35

Computed 2026-10-18T03:46:41.519100+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 8/14 | -6 | False | 243/256 / 233/256 | 1321/1377 / 1311/1377 |
| baby-dragon | 3/2 | +1 | False | 111/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 17/19 | -2 | False | 522/607 / 519/607 | 0/0 / 0/0 |
| bat | 36/111 | -75 | False | 83/97 / 84/97 | 1818/2289 / 1295/2289 |
| battle-ram | 1/2 | -1 | False | 73/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 0/0 | +0 | False | 37/47 / 37/47 | 0/0 / 0/0 |
| cannon | 1/1 | +0 | False | 42/43 / 42/43 | 449/458 / 446/458 |
| giant | 0/1 | -1 | False | 17/18 / 17/18 | 73/82 / 74/82 |
| goblin-brawler | 0/0 | +0 | False | 32/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 0/0 | +0 | False | 16/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 0/0 | +0 | False | 46/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 0/1 | -1 | False | 138/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 100/100 / 97/100 | 0/0 / 0/0 |
| knight | 1/3 | -2 | False | 77/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 2/2 | +0 | False | 32/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 4/6 | -2 | False | 150/160 / 146/160 | 513/562 / 510/562 |
| minion | 5/11 | -6 | False | 127/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 10/21 | -11 | False | 68/88 / 56/88 | 0/0 / 0/0 |
| None | 12/5 | +7 | True | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 9/16 | -7 | False | 838/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 1/1 | +0 | False | 147/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 1/2 | -1 | False | 226/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 48/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 5/10 | -5 | False | 183/223 / 184/223 | 254/304 / 260/304 |
| witch | 2/1 | +1 | False | 65/74 / 59/74 | 0/0 / 0/0 |
| wizard | 3/4 | -1 | False | 64/76 / 57/76 | 0/0 / 0/0 |
