# Perception label-volume final

Written 2026-10-18T04:06:49Z; final score command UTC2026-10-18T04:06:39.869359+00:00; LIVE definition HEAD`feef63aabb5c54531409c70772d95faab79ec4db`. All six12epoch runs and their existing evaluator ALL/FRESH markers are complete on127x08. Data dose nominal0/100/300frames at seeds13/23, fixed x1h recipe, initv11b, lr1e-4,12epochs, VOL list weight.15. Actual list sizes:99 and291frames; the99line set is a verified subset of291lines.

Existing ROUND1 gate exactly: score>=.5, nearest matching within1tile, own-Bats recall at least x1h+8pp, E→O/O→E owner-error counts no worse, no class with combined owner errors greater than x1h+1. PENDING re-test permits excesses<=4 while Bats gain passes; it is not QUALIFIES. Old12 pooled includes raws76..79d as in ROUND1. The label-volume pre-check also predeclared its unseen5slice row raws79/79b/79c/79d/80, shown separately. Fixed-dataset counts have no registered CI.

## Old12 pooled gate

| Run | Verdict | Own Bats | E→O | O→E | Bad classes | Enemy correct class+owner |
|---|---|---|---|---|---|---|
| vol0s13 | no | 1298/2289 (56.7%) | 124/3747 (3.3%) | 109/4021 (2.7%) | none | 3410/4009 |
| vol0s23 | no | 1371/2289 (59.9%) | 118/3745 (3.2%) | 116/4110 (2.8%) | baby-dragon, bat, hog-rider, skeleton, witch | 3426/4009 |
| vol1s13 | no | 1691/2289 (73.9%) | 137/3784 (3.6%) | 65/4371 (1.5%) | goblin-brawler, mega-minion, mini-pekka, skeleton, spear-goblin, valkyrie, witch | 3443/4009 |
| vol1s23 | PENDING re-test | 1584/2289 (69.2%) | 110/3753 (2.9%) | 71/4261 (1.7%) | giant, hog-rider, musketeer, None, skeleton, witch | 3438/4009 |
| vol3s13 | no | 1708/2289 (74.6%) | 131/3771 (3.5%) | 54/4390 (1.2%) | barbarian, hog-rider, mega-minion, musketeer, skeleton, skeleton-dragon | 3445/4009 |
| vol3s23 | PENDING re-test | 1640/2289 (71.6%) | 96/3751 (2.6%) | 73/4303 (1.7%) | mini-pekka, skeleton | 3443/4009 |

## Predeclared unseen5slice row

| Run | Verdict | Own Bats | E→O | O→E | Bad classes | RAWS80 alone | HOGVID |
|---|---|---|---|---|---|---|
| vol0s13 | no | 455/771 (59.0%) | 65/1647 (3.9%) | 9/1552 (0.6%) | none | no | no |
| vol0s23 | no | 460/771 (59.7%) | 61/1653 (3.7%) | 17/1572 (1.1%) | barbarian, bat, None | no | no |
| vol1s13 | no | 573/771 (74.3%) | 67/1661 (4.0%) | 6/1665 (0.4%) | goblin-brawler, None, valkyrie | PENDING re-test | PENDING re-test |
| vol1s23 | PENDING re-test | 535/771 (69.4%) | 45/1647 (2.7%) | 9/1630 (0.6%) | None | QUALIFIES | PENDING re-test |
| vol3s13 | PENDING re-test | 578/771 (75.0%) | 63/1648 (3.8%) | 6/1679 (0.4%) | musketeer, valkyrie | PENDING re-test | no |
| vol3s23 | PENDING re-test | 553/771 (71.7%) | 44/1644 (2.7%) | 10/1643 (0.6%) | giant | QUALIFIES | PENDING re-test |

Old12 qualifiers:[]; unseen5 qualifiers:[]. Controlvol0s13 matches x1h counts. These comparisons describe these two fixed seeds; no unregistered dose-effect significance test or new selection was added.

## Per-class, new-deck and hero coverage

All six runs lack the required new-deck RAWS81/83 evaluations and candidate hero-row/spell_dump artifacts. They are unscorable on those rows; missing coverage is not a failed gate. Hero forms use their base card identity; no separate hero head or hero classes are introduced. None/null in bad_classes is the literal normalized missing truth-identity category, still included in owner-error gating. No complete deployment gate, Mac raw parity or translator verification is established; no action/deploy.

Source-code tree receipts on the host holding raw evaluation data:
```json
{
  "utc": "2026-10-18T04:06:43.894239+00:00",
  "lists": {
    "hard-ownervol100.txt": {
      "path": "/mpac/sdicks02/jobs/clasher/live-yolo-20261016/lists/hard-ownervol100.txt",
      "sha256": "50dc102403772699db260f5431a087a707be810f565918a2432d6546b35835a9",
      "lines": 99,
      "unique_lines": 99
    },
    "hard-ownervol300.txt": {
      "path": "/mpac/sdicks02/jobs/clasher/live-yolo-20261016/lists/hard-ownervol300.txt",
      "sha256": "a2e83ab623055fb23cecc03008910a256cedc89da805cf7c3f2299cefc991293",
      "lines": 291,
      "unique_lines": 291
    }
  },
  "scripts": {
    "vol0s13": {
      "path": "/mpac/sdicks02/jobs/clasher/live-yolo-20261016/run-vol0s13.sh",
      "sha256": "4e121c643407699d18f2bb1eac43ccb12dd4896015757dc232c4597ee0c2a869",
      "fresh": true,
      "all": true
    },
    "vol0s23": {
      "path": "/mpac/sdicks02/jobs/clasher/live-yolo-20261016/run-vol0s23.sh",
      "sha256": "0907b3e4615269cfaf98a2413da36a781cda78125ec3dda593a52d43b6627ac1",
      "fresh": true,
      "all": true
    },
    "vol1s13": {
      "path": "/mpac/sdicks02/jobs/clasher/live-yolo-20261016/run-vol1s13.sh",
      "sha256": "9849d796337b602e38c9805bc5ed164076f0534cc34946a92778a3ddd21b6467",
      "fresh": true,
      "all": true
    },
    "vol1s23": {
      "path": "/mpac/sdicks02/jobs/clasher/live-yolo-20261016/run-vol1s23.sh",
      "sha256": "8068a401ab2bb2401088140b58d0433ce882972a7088501a398a513fffa414c3",
      "fresh": true,
      "all": true
    },
    "vol3s13": {
      "path": "/mpac/sdicks02/jobs/clasher/live-yolo-20261016/run-vol3s13.sh",
      "sha256": "10dea2e0340c6f210ef80dbf3ac29717b48230fc204cc88c30058f8118ecaff2",
      "fresh": true,
      "all": true
    },
    "vol3s23": {
      "path": "/mpac/sdicks02/jobs/clasher/live-yolo-20261016/run-vol3s23.sh",
      "sha256": "5ce2bc1179f43b7c82ba5d1df004b591326b63727183dec4d7c425ae6aebb9e0",
      "fresh": true,
      "all": true
    }
  },
  "trees": {
    "code": {
      "files": 88,
      "sha256": "9c1e3f5217e1973affdf5f47e082cf7163699a51f50186c5085bbb81e025744b"
    },
    "katacr-src": {
      "files": 176,
      "sha256": "2780695bff3c575c5cf956af5e72d9748f0249ad2466e7a459222306c653b4c6"
    }
  },
  "list100_lines_subset300": true
}
```

These are observed archive-tree digests, SHA256 of compact JSON sorted(relativepath,fileSHA256) pairs, excluding .git/__pycache__. The launch scripts did not store a Git commit pin, so historical source immutability is not asserted. All scoring was pure stored-output processing on127x08 under nice19; no inference/evaluation/training job was started.

## All scoring fields (per-slice, owner errors, class rows)
```json
{
  "vol0s13": {
    "old_pooled": {
      "verdict": "no",
      "own_bats": [
        1298,
        2289
      ],
      "gain_pp": 0.0,
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
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 4009,
        "matched": 3626,
        "cls_ok": 3518,
        "own_ok": 3487,
        "ok": 3410,
        "missed": 383
      }
    },
    "per_slice": {
      "raws76": {
        "verdict": "no",
        "own_bats": [
          111,
          224
        ],
        "gain_pp": 0.0,
        "eo": [
          7,
          266
        ],
        "oe": [
          15,
          316
        ],
        "identity": [
          544,
          590,
          703
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 275,
          "matched": 255,
          "cls_ok": 247,
          "own_ok": 246,
          "ok": 240,
          "missed": 20
        }
      },
      "raws76b": {
        "verdict": "no",
        "own_bats": [
          76,
          138
        ],
        "gain_pp": 0.0,
        "eo": [
          3,
          259
        ],
        "oe": [
          1,
          394
        ],
        "identity": [
          638,
          666,
          748
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 284,
          "matched": 260,
          "cls_ok": 248,
          "own_ok": 256,
          "ok": 246,
          "missed": 24
        }
      },
      "raws76c": {
        "verdict": "no",
        "own_bats": [
          152,
          299
        ],
        "gain_pp": 0.0,
        "eo": [
          9,
          331
        ],
        "oe": [
          40,
          474
        ],
        "identity": [
          733,
          820,
          943
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 340,
          "matched": 315,
          "cls_ok": 306,
          "own_ok": 303,
          "ok": 297,
          "missed": 25
        }
      },
      "raws77": {
        "verdict": "no",
        "own_bats": [
          135,
          240
        ],
        "gain_pp": 0.0,
        "eo": [
          11,
          400
        ],
        "oe": [
          9,
          375
        ],
        "identity": [
          699,
          790,
          899
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 403,
          "matched": 358,
          "cls_ok": 344,
          "own_ok": 348,
          "ok": 338,
          "missed": 45
        }
      },
      "raws78": {
        "verdict": "no",
        "own_bats": [
          75,
          124
        ],
        "gain_pp": 0.0,
        "eo": [
          9,
          620
        ],
        "oe": [
          6,
          310
        ],
        "identity": [
          873,
          944,
          1010
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 630,
          "missed": 48,
          "matched": 582,
          "cls_ok": 576,
          "own_ok": 573,
          "ok": 569
        }
      },
      "raws78b": {
        "verdict": "no",
        "own_bats": [
          165,
          291
        ],
        "gain_pp": 0.0,
        "eo": [
          10,
          233
        ],
        "oe": [
          8,
          394
        ],
        "identity": [
          607,
          638,
          772
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 252,
          "matched": 235,
          "cls_ok": 224,
          "own_ok": 223,
          "ok": 218,
          "missed": 17
        }
      },
      "raws78c": {
        "verdict": "no",
        "own_bats": [
          107,
          170
        ],
        "gain_pp": 0.0,
        "eo": [
          19,
          314
        ],
        "oe": [
          0,
          293
        ],
        "identity": [
          576,
          624,
          728
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 361,
          "matched": 315,
          "cls_ok": 303,
          "own_ok": 295,
          "ok": 284,
          "missed": 46
        }
      },
      "raws78d": {
        "verdict": "no",
        "own_bats": [
          128,
          253
        ],
        "gain_pp": 0.0,
        "eo": [
          4,
          367
        ],
        "oe": [
          23,
          287
        ],
        "identity": [
          597,
          667,
          816
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 418,
          "missed": 70,
          "matched": 348,
          "cls_ok": 338,
          "own_ok": 344,
          "ok": 335
        }
      },
      "raws79": {
        "verdict": "no",
        "own_bats": [
          106,
          141
        ],
        "gain_pp": 0.0,
        "eo": [
          17,
          259
        ],
        "oe": [
          0,
          297
        ],
        "identity": [
          537,
          563,
          613
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 273,
          "matched": 260,
          "cls_ok": 256,
          "own_ok": 242,
          "ok": 240,
          "missed": 13
        }
      },
      "raws79b": {
        "verdict": "no",
        "own_bats": [
          66,
          105
        ],
        "gain_pp": 0.0,
        "eo": [
          7,
          145
        ],
        "oe": [
          3,
          356
        ],
        "identity": [
          480,
          519,
          561
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 157,
          "matched": 138,
          "cls_ok": 134,
          "own_ok": 132,
          "ok": 129,
          "missed": 19
        }
      },
      "raws79c": {
        "verdict": "no",
        "own_bats": [
          60,
          122
        ],
        "gain_pp": 0.0,
        "eo": [
          19,
          223
        ],
        "oe": [
          2,
          167
        ],
        "identity": [
          366,
          401,
          490
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 247,
          "matched": 227,
          "cls_ok": 218,
          "own_ok": 205,
          "ok": 201,
          "missed": 20
        }
      },
      "raws79d": {
        "verdict": "no",
        "own_bats": [
          117,
          182
        ],
        "gain_pp": 0.0,
        "eo": [
          9,
          330
        ],
        "oe": [
          2,
          358
        ],
        "identity": [
          670,
          703,
          798
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 369,
          "matched": 333,
          "cls_ok": 324,
          "own_ok": 320,
          "ok": 313,
          "missed": 36
        }
      },
      "raws80": {
        "verdict": "no",
        "own_bats": [
          106,
          221
        ],
        "gain_pp": 0.0,
        "eo": [
          13,
          690
        ],
        "oe": [
          2,
          374
        ],
        "identity": [
          1026,
          1081,
          1226
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 726,
          "matched": 684,
          "cls_ok": 667,
          "own_ok": 669,
          "ok": 656,
          "missed": 42
        }
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
        "verdict": "no",
        "own_bats": [
          87,
          175
        ],
        "gain_pp": 0.0,
        "eo": [
          15,
          454
        ],
        "oe": [
          1,
          415
        ],
        "identity": [
          764,
          903,
          1008
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 480,
          "matched": 385,
          "cls_ok": 358,
          "own_ok": 371,
          "ok": 347,
          "missed": 95
        }
      }
    },
    "own_rows": {},
    "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
    "weights_sha256": "f68eef5f11bd10c247f231684fe35d1ce64b3f94b1f96f0b908060a622b39338",
    "fresh5_pooled": {
      "verdict": "no",
      "own_bats": [
        455,
        771
      ],
      "gain_pp": 0.0,
      "eo": [
        65,
        1647
      ],
      "oe": [
        9,
        1552
      ],
      "identity": [
        3079,
        3267,
        3688
      ],
      "bad_classes": [],
      "failures": {},
      "enemy": {
        "n": 1772,
        "matched": 1642,
        "cls_ok": 1599,
        "own_ok": 1568,
        "ok": 1539,
        "missed": 130
      }
    }
  },
  "vol0s23": {
    "old_pooled": {
      "verdict": "no",
      "own_bats": [
        1371,
        2289
      ],
      "gain_pp": 3.1891655744866743,
      "eo": [
        118,
        3745
      ],
      "oe": [
        116,
        4110
      ],
      "identity": [
        7416,
        8023,
        9081
      ],
      "bad_classes": [
        "baby-dragon",
        "bat",
        "hog-rider",
        "skeleton",
        "witch"
      ],
      "failures": {
        "baby-dragon": 2,
        "bat": 7,
        "hog-rider": 3,
        "skeleton": 4,
        "witch": 2,
        "O\u2192E total": 7
      },
      "enemy": {
        "n": 4009,
        "matched": 3630,
        "cls_ok": 3526,
        "own_ok": 3496,
        "ok": 3426,
        "missed": 379
      }
    },
    "per_slice": {
      "raws76": {
        "verdict": "no",
        "own_bats": [
          125,
          224
        ],
        "gain_pp": 6.25,
        "eo": [
          3,
          268
        ],
        "oe": [
          18,
          333
        ],
        "identity": [
          565,
          610,
          703
        ],
        "bad_classes": [
          "bat",
          "mini-pekka"
        ],
        "failures": {
          "bat": 2,
          "mini-pekka": 2,
          "O\u2192E total": 3
        },
        "enemy": {
          "n": 275,
          "matched": 257,
          "cls_ok": 251,
          "own_ok": 252,
          "ok": 249,
          "missed": 18
        }
      },
      "raws76b": {
        "verdict": "no",
        "own_bats": [
          84,
          138
        ],
        "gain_pp": 5.797101449275366,
        "eo": [
          3,
          256
        ],
        "oe": [
          3,
          403
        ],
        "identity": [
          642,
          674,
          748
        ],
        "bad_classes": [
          "bat"
        ],
        "failures": {
          "bat": 2,
          "O\u2192E total": 2
        },
        "enemy": {
          "n": 284,
          "matched": 258,
          "cls_ok": 246,
          "own_ok": 253,
          "ok": 243,
          "missed": 26
        }
      },
      "raws76c": {
        "verdict": "no",
        "own_bats": [
          151,
          299
        ],
        "gain_pp": -0.33444816053511683,
        "eo": [
          2,
          331
        ],
        "oe": [
          40,
          473
        ],
        "identity": [
          741,
          818,
          943
        ],
        "bad_classes": [
          "bat"
        ],
        "failures": {
          "bat": 2
        },
        "enemy": {
          "n": 340,
          "matched": 317,
          "cls_ok": 310,
          "own_ok": 311,
          "ok": 308,
          "missed": 23
        }
      },
      "raws77": {
        "verdict": "no",
        "own_bats": [
          149,
          240
        ],
        "gain_pp": 5.833333333333335,
        "eo": [
          13,
          396
        ],
        "oe": [
          8,
          384
        ],
        "identity": [
          711,
          795,
          899
        ],
        "bad_classes": [
          "skeleton"
        ],
        "failures": {
          "skeleton": 3,
          "E\u2192O total": 2
        },
        "enemy": {
          "n": 403,
          "matched": 359,
          "cls_ok": 348,
          "own_ok": 343,
          "ok": 336,
          "missed": 44
        }
      },
      "raws78": {
        "verdict": "PENDING re-test",
        "own_bats": [
          87,
          124
        ],
        "gain_pp": 9.677419354838712,
        "eo": [
          10,
          621
        ],
        "oe": [
          3,
          324
        ],
        "identity": [
          890,
          965,
          1010
        ],
        "bad_classes": [
          "witch"
        ],
        "failures": {
          "witch": 2,
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 630,
          "missed": 42,
          "matched": 588,
          "cls_ok": 576,
          "own_ok": 577,
          "ok": 571
        }
      },
      "raws78b": {
        "verdict": "no",
        "own_bats": [
          164,
          291
        ],
        "gain_pp": -0.3436426116838476,
        "eo": [
          7,
          232
        ],
        "oe": [
          9,
          394
        ],
        "identity": [
          608,
          638,
          772
        ],
        "bad_classes": [],
        "failures": {
          "O\u2192E total": 1
        },
        "enemy": {
          "n": 252,
          "matched": 233,
          "cls_ok": 228,
          "own_ok": 224,
          "ok": 221,
          "missed": 19
        }
      },
      "raws78c": {
        "verdict": "no",
        "own_bats": [
          117,
          170
        ],
        "gain_pp": 5.882352941176472,
        "eo": [
          19,
          305
        ],
        "oe": [
          1,
          307
        ],
        "identity": [
          580,
          631,
          728
        ],
        "bad_classes": [],
        "failures": {
          "O\u2192E total": 1
        },
        "enemy": {
          "n": 361,
          "matched": 306,
          "cls_ok": 293,
          "own_ok": 287,
          "ok": 275,
          "missed": 55
        }
      },
      "raws78d": {
        "verdict": "no",
        "own_bats": [
          138,
          253
        ],
        "gain_pp": 3.9525691699604737,
        "eo": [
          10,
          378
        ],
        "oe": [
          24,
          302
        ],
        "identity": [
          613,
          695,
          816
        ],
        "bad_classes": [
          "hog-rider"
        ],
        "failures": {
          "hog-rider": 2,
          "E\u2192O total": 6,
          "O\u2192E total": 1
        },
        "enemy": {
          "n": 418,
          "missed": 62,
          "matched": 356,
          "cls_ok": 342,
          "own_ok": 347,
          "ok": 336
        }
      },
      "raws79": {
        "verdict": "no",
        "own_bats": [
          108,
          141
        ],
        "gain_pp": 1.4184397163120588,
        "eo": [
          15,
          257
        ],
        "oe": [
          3,
          301
        ],
        "identity": [
          537,
          565,
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
          "cls_ok": 252,
          "own_ok": 242,
          "ok": 238,
          "missed": 15
        }
      },
      "raws79b": {
        "verdict": "no",
        "own_bats": [
          67,
          105
        ],
        "gain_pp": 0.952380952380949,
        "eo": [
          9,
          147
        ],
        "oe": [
          3,
          360
        ],
        "identity": [
          483,
          522,
          561
        ],
        "bad_classes": [
          "null"
        ],
        "failures": {
          "null": 3,
          "E\u2192O total": 2
        },
        "enemy": {
          "n": 157,
          "matched": 137,
          "cls_ok": 133,
          "own_ok": 132,
          "ok": 129,
          "missed": 20
        }
      },
      "raws79c": {
        "verdict": "no",
        "own_bats": [
          66,
          122
        ],
        "gain_pp": 4.918032786885251,
        "eo": [
          16,
          223
        ],
        "oe": [
          2,
          173
        ],
        "identity": [
          376,
          406,
          490
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 247,
          "matched": 226,
          "cls_ok": 220,
          "own_ok": 208,
          "ok": 205,
          "missed": 21
        }
      },
      "raws79d": {
        "verdict": "no",
        "own_bats": [
          115,
          182
        ],
        "gain_pp": -1.098901098901106,
        "eo": [
          11,
          331
        ],
        "oe": [
          2,
          356
        ],
        "identity": [
          670,
          704,
          798
        ],
        "bad_classes": [
          "barbarian",
          "bat"
        ],
        "failures": {
          "barbarian": 2,
          "bat": 2,
          "E\u2192O total": 2
        },
        "enemy": {
          "n": 369,
          "matched": 335,
          "cls_ok": 327,
          "own_ok": 320,
          "ok": 315,
          "missed": 34
        }
      },
      "raws80": {
        "verdict": "no",
        "own_bats": [
          104,
          221
        ],
        "gain_pp": -0.9049773755656132,
        "eo": [
          10,
          695
        ],
        "oe": [
          7,
          382
        ],
        "identity": [
          1038,
          1095,
          1226
        ],
        "bad_classes": [
          "bat"
        ],
        "failures": {
          "bat": 5,
          "O\u2192E total": 5
        },
        "enemy": {
          "n": 726,
          "matched": 690,
          "cls_ok": 673,
          "own_ok": 678,
          "ok": 665,
          "missed": 36
        }
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
        "verdict": "no",
        "own_bats": [
          94,
          175
        ],
        "gain_pp": 3.9999999999999982,
        "eo": [
          12,
          441
        ],
        "oe": [
          1,
          428
        ],
        "identity": [
          770,
          899,
          1008
        ],
        "bad_classes": [
          "mini-pekka"
        ],
        "failures": {
          "mini-pekka": 2
        },
        "enemy": {
          "n": 480,
          "missed": 104,
          "matched": 376,
          "cls_ok": 356,
          "own_ok": 361,
          "ok": 347
        }
      }
    },
    "own_rows": {},
    "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
    "weights_sha256": "e29970837cc12f2dff7b7556c8880af3240bdfb3e1bb28c2988906395995d08e",
    "fresh5_pooled": {
      "verdict": "no",
      "own_bats": [
        460,
        771
      ],
      "gain_pp": 0.6485084306095956,
      "eo": [
        61,
        1653
      ],
      "oe": [
        17,
        1572
      ],
      "identity": [
        3104,
        3292,
        3688
      ],
      "bad_classes": [
        "barbarian",
        "bat",
        "null"
      ],
      "failures": {
        "barbarian": 3,
        "bat": 9,
        "null": 3,
        "O\u2192E total": 8
      },
      "enemy": {
        "n": 1772,
        "matched": 1646,
        "cls_ok": 1605,
        "own_ok": 1580,
        "ok": 1552,
        "missed": 126
      }
    }
  },
  "vol1s13": {
    "old_pooled": {
      "verdict": "no",
      "own_bats": [
        1691,
        2289
      ],
      "gain_pp": 17.169069462647446,
      "eo": [
        137,
        3784
      ],
      "oe": [
        65,
        4371
      ],
      "identity": [
        7750,
        8302,
        9081
      ],
      "bad_classes": [
        "goblin-brawler",
        "mega-minion",
        "mini-pekka",
        "skeleton",
        "spear-goblin",
        "valkyrie",
        "witch"
      ],
      "failures": {
        "goblin-brawler": 2,
        "mega-minion": 2,
        "mini-pekka": 2,
        "skeleton": 7,
        "spear-goblin": 3,
        "valkyrie": 7,
        "witch": 2,
        "E\u2192O total": 13
      },
      "enemy": {
        "n": 4009,
        "matched": 3663,
        "cls_ok": 3556,
        "own_ok": 3504,
        "ok": 3443,
        "missed": 346
      }
    },
    "per_slice": {
      "raws76": {
        "verdict": "PENDING re-test",
        "own_bats": [
          162,
          224
        ],
        "gain_pp": 22.76785714285714,
        "eo": [
          8,
          273
        ],
        "oe": [
          8,
          359
        ],
        "identity": [
          602,
          640,
          703
        ],
        "bad_classes": [
          "skeleton"
        ],
        "failures": {
          "skeleton": 2,
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 275,
          "matched": 262,
          "cls_ok": 255,
          "own_ok": 250,
          "ok": 249,
          "missed": 13
        }
      },
      "raws76b": {
        "verdict": "PENDING re-test",
        "own_bats": [
          107,
          138
        ],
        "gain_pp": 22.463768115942027,
        "eo": [
          4,
          263
        ],
        "oe": [
          1,
          424
        ],
        "identity": [
          676,
          697,
          748
        ],
        "bad_classes": [],
        "failures": {
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 284,
          "matched": 266,
          "cls_ok": 255,
          "own_ok": 259,
          "ok": 253,
          "missed": 18
        }
      },
      "raws76c": {
        "verdict": "QUALIFIES",
        "own_bats": [
          198,
          299
        ],
        "gain_pp": 15.384615384615385,
        "eo": [
          7,
          335
        ],
        "oe": [
          20,
          501
        ],
        "identity": [
          783,
          846,
          943
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 340,
          "matched": 316,
          "cls_ok": 309,
          "own_ok": 306,
          "ok": 302,
          "missed": 24
        }
      },
      "raws77": {
        "verdict": "no",
        "own_bats": [
          167,
          240
        ],
        "gain_pp": 13.33333333333333,
        "eo": [
          16,
          405
        ],
        "oe": [
          6,
          404
        ],
        "identity": [
          736,
          823,
          899
        ],
        "bad_classes": [
          "mega-minion",
          "skeleton"
        ],
        "failures": {
          "mega-minion": 2,
          "skeleton": 3,
          "E\u2192O total": 5
        },
        "enemy": {
          "n": 403,
          "matched": 364,
          "cls_ok": 351,
          "own_ok": 348,
          "ok": 340,
          "missed": 39
        }
      },
      "raws78": {
        "verdict": "PENDING re-test",
        "own_bats": [
          101,
          124
        ],
        "gain_pp": 20.967741935483875,
        "eo": [
          11,
          617
        ],
        "oe": [
          3,
          335
        ],
        "identity": [
          895,
          969,
          1010
        ],
        "bad_classes": [
          "witch"
        ],
        "failures": {
          "witch": 2,
          "E\u2192O total": 2
        },
        "enemy": {
          "n": 630,
          "missed": 50,
          "matched": 580,
          "cls_ok": 571,
          "own_ok": 567,
          "ok": 564
        }
      },
      "raws78b": {
        "verdict": "PENDING re-test",
        "own_bats": [
          208,
          291
        ],
        "gain_pp": 14.7766323024055,
        "eo": [
          12,
          232
        ],
        "oe": [
          7,
          435
        ],
        "identity": [
          649,
          681,
          772
        ],
        "bad_classes": [
          "mini-pekka",
          "valkyrie"
        ],
        "failures": {
          "mini-pekka": 2,
          "valkyrie": 3,
          "E\u2192O total": 2
        },
        "enemy": {
          "n": 252,
          "matched": 236,
          "cls_ok": 225,
          "own_ok": 220,
          "ok": 217,
          "missed": 16
        }
      },
      "raws78c": {
        "verdict": "PENDING re-test",
        "own_bats": [
          136,
          170
        ],
        "gain_pp": 17.05882352941177,
        "eo": [
          21,
          318
        ],
        "oe": [
          0,
          320
        ],
        "identity": [
          609,
          656,
          728
        ],
        "bad_classes": [
          "spear-goblin"
        ],
        "failures": {
          "spear-goblin": 2,
          "E\u2192O total": 2
        },
        "enemy": {
          "n": 361,
          "matched": 319,
          "cls_ok": 309,
          "own_ok": 297,
          "ok": 289,
          "missed": 42
        }
      },
      "raws78d": {
        "verdict": "QUALIFIES",
        "own_bats": [
          189,
          253
        ],
        "gain_pp": 24.110671936758898,
        "eo": [
          3,
          375
        ],
        "oe": [
          14,
          343
        ],
        "identity": [
          670,
          731,
          816
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 418,
          "missed": 63,
          "matched": 355,
          "cls_ok": 344,
          "own_ok": 351,
          "ok": 342
        }
      },
      "raws79": {
        "verdict": "PENDING re-test",
        "own_bats": [
          119,
          141
        ],
        "gain_pp": 9.219858156028371,
        "eo": [
          19,
          261
        ],
        "oe": [
          3,
          311
        ],
        "identity": [
          548,
          578,
          613
        ],
        "bad_classes": [
          "bat",
          "goblin-brawler"
        ],
        "failures": {
          "bat": 2,
          "goblin-brawler": 2,
          "E\u2192O total": 2,
          "O\u2192E total": 3
        },
        "enemy": {
          "n": 273,
          "matched": 262,
          "cls_ok": 255,
          "own_ok": 243,
          "ok": 238,
          "missed": 11
        }
      },
      "raws79b": {
        "verdict": "PENDING re-test",
        "own_bats": [
          78,
          105
        ],
        "gain_pp": 11.428571428571432,
        "eo": [
          8,
          144
        ],
        "oe": [
          2,
          369
        ],
        "identity": [
          490,
          528,
          561
        ],
        "bad_classes": [
          "null"
        ],
        "failures": {
          "null": 2,
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 157,
          "matched": 135,
          "cls_ok": 130,
          "own_ok": 129,
          "ok": 124,
          "missed": 22
        }
      },
      "raws79c": {
        "verdict": "QUALIFIES",
        "own_bats": [
          81,
          122
        ],
        "gain_pp": 17.213114754098356,
        "eo": [
          19,
          226
        ],
        "oe": [
          1,
          187
        ],
        "identity": [
          388,
          421,
          490
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 247,
          "matched": 231,
          "cls_ok": 221,
          "own_ok": 208,
          "ok": 203,
          "missed": 16
        }
      },
      "raws79d": {
        "verdict": "QUALIFIES",
        "own_bats": [
          145,
          182
        ],
        "gain_pp": 15.384615384615374,
        "eo": [
          9,
          335
        ],
        "oe": [
          0,
          383
        ],
        "identity": [
          704,
          732,
          798
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 369,
          "matched": 337,
          "cls_ok": 331,
          "own_ok": 326,
          "ok": 322,
          "missed": 32
        }
      },
      "raws80": {
        "verdict": "PENDING re-test",
        "own_bats": [
          150,
          221
        ],
        "gain_pp": 19.90950226244344,
        "eo": [
          12,
          695
        ],
        "oe": [
          0,
          415
        ],
        "identity": [
          1080,
          1125,
          1226
        ],
        "bad_classes": [
          "valkyrie"
        ],
        "failures": {
          "valkyrie": 2
        },
        "enemy": {
          "n": 726,
          "matched": 688,
          "cls_ok": 673,
          "own_ok": 674,
          "ok": 663,
          "missed": 38
        }
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
          124,
          175
        ],
        "gain_pp": 21.142857142857135,
        "eo": [
          18,
          476
        ],
        "oe": [
          1,
          454
        ],
        "identity": [
          829,
          960,
          1008
        ],
        "bad_classes": [],
        "failures": {
          "E\u2192O total": 3
        },
        "enemy": {
          "n": 480,
          "matched": 407,
          "cls_ok": 383,
          "own_ok": 385,
          "ok": 371,
          "missed": 73
        }
      }
    },
    "own_rows": {},
    "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
    "weights_sha256": "1a3487fed0cf2945fdb446e589d1c02397d227247ba3ff18fc3ce0560c7cd6c8",
    "fresh5_pooled": {
      "verdict": "no",
      "own_bats": [
        573,
        771
      ],
      "gain_pp": 15.304798962386512,
      "eo": [
        67,
        1661
      ],
      "oe": [
        6,
        1665
      ],
      "identity": [
        3210,
        3384,
        3688
      ],
      "bad_classes": [
        "goblin-brawler",
        "null",
        "valkyrie"
      ],
      "failures": {
        "goblin-brawler": 2,
        "null": 2,
        "valkyrie": 5,
        "E\u2192O total": 2
      },
      "enemy": {
        "n": 1772,
        "matched": 1653,
        "cls_ok": 1610,
        "own_ok": 1580,
        "ok": 1550,
        "missed": 119
      }
    }
  },
  "vol1s23": {
    "old_pooled": {
      "verdict": "PENDING re-test",
      "own_bats": [
        1584,
        2289
      ],
      "gain_pp": 12.494539100043689,
      "eo": [
        110,
        3753
      ],
      "oe": [
        71,
        4261
      ],
      "identity": [
        7623,
        8167,
        9081
      ],
      "bad_classes": [
        "giant",
        "hog-rider",
        "musketeer",
        "null",
        "skeleton",
        "witch"
      ],
      "failures": {
        "giant": 2,
        "hog-rider": 2,
        "musketeer": 2,
        "null": 2,
        "skeleton": 4,
        "witch": 2
      },
      "enemy": {
        "n": 4009,
        "matched": 3625,
        "cls_ok": 3528,
        "own_ok": 3498,
        "ok": 3438,
        "missed": 384
      }
    },
    "per_slice": {
      "raws76": {
        "verdict": "PENDING re-test",
        "own_bats": [
          144,
          224
        ],
        "gain_pp": 14.732142857142861,
        "eo": [
          8,
          270
        ],
        "oe": [
          9,
          339
        ],
        "identity": [
          573,
          618,
          703
        ],
        "bad_classes": [
          "mini-pekka"
        ],
        "failures": {
          "mini-pekka": 2,
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 275,
          "matched": 256,
          "cls_ok": 249,
          "own_ok": 245,
          "ok": 243,
          "missed": 19
        }
      },
      "raws76b": {
        "verdict": "PENDING re-test",
        "own_bats": [
          101,
          138
        ],
        "gain_pp": 18.11594202898551,
        "eo": [
          4,
          256
        ],
        "oe": [
          2,
          418
        ],
        "identity": [
          661,
          689,
          748
        ],
        "bad_classes": [],
        "failures": {
          "E\u2192O total": 1,
          "O\u2192E total": 1
        },
        "enemy": {
          "n": 284,
          "matched": 258,
          "cls_ok": 249,
          "own_ok": 252,
          "ok": 245,
          "missed": 26
        }
      },
      "raws76c": {
        "verdict": "QUALIFIES",
        "own_bats": [
          193,
          299
        ],
        "gain_pp": 13.712374581939802,
        "eo": [
          6,
          328
        ],
        "oe": [
          22,
          496
        ],
        "identity": [
          773,
          837,
          943
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 340,
          "matched": 311,
          "cls_ok": 305,
          "own_ok": 303,
          "ok": 299,
          "missed": 29
        }
      },
      "raws77": {
        "verdict": "PENDING re-test",
        "own_bats": [
          161,
          240
        ],
        "gain_pp": 10.833333333333329,
        "eo": [
          13,
          403
        ],
        "oe": [
          6,
          394
        ],
        "identity": [
          728,
          810,
          899
        ],
        "bad_classes": [
          "skeleton"
        ],
        "failures": {
          "skeleton": 4,
          "E\u2192O total": 2
        },
        "enemy": {
          "n": 403,
          "matched": 360,
          "cls_ok": 351,
          "own_ok": 345,
          "ok": 342,
          "missed": 43
        }
      },
      "raws78": {
        "verdict": "PENDING re-test",
        "own_bats": [
          97,
          124
        ],
        "gain_pp": 17.741935483870964,
        "eo": [
          9,
          623
        ],
        "oe": [
          6,
          337
        ],
        "identity": [
          900,
          975,
          1010
        ],
        "bad_classes": [
          "witch"
        ],
        "failures": {
          "witch": 2
        },
        "enemy": {
          "n": 630,
          "missed": 44,
          "matched": 586,
          "cls_ok": 579,
          "own_ok": 578,
          "ok": 573
        }
      },
      "raws78b": {
        "verdict": "QUALIFIES",
        "own_bats": [
          192,
          291
        ],
        "gain_pp": 9.278350515463918,
        "eo": [
          7,
          231
        ],
        "oe": [
          5,
          416
        ],
        "identity": [
          634,
          662,
          772
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 252,
          "matched": 233,
          "cls_ok": 224,
          "own_ok": 224,
          "ok": 221,
          "missed": 19
        }
      },
      "raws78c": {
        "verdict": "no",
        "own_bats": [
          128,
          170
        ],
        "gain_pp": 12.352941176470589,
        "eo": [
          24,
          312
        ],
        "oe": [
          0,
          312
        ],
        "identity": [
          594,
          643,
          728
        ],
        "bad_classes": [
          "hog-rider",
          "skeleton"
        ],
        "failures": {
          "hog-rider": 3,
          "skeleton": 2,
          "E\u2192O total": 5
        },
        "enemy": {
          "n": 361,
          "matched": 313,
          "cls_ok": 303,
          "own_ok": 289,
          "ok": 282,
          "missed": 48
        }
      },
      "raws78d": {
        "verdict": "QUALIFIES",
        "own_bats": [
          173,
          253
        ],
        "gain_pp": 17.786561264822144,
        "eo": [
          3,
          375
        ],
        "oe": [
          13,
          323
        ],
        "identity": [
          650,
          710,
          816
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 418,
          "missed": 62,
          "matched": 356,
          "cls_ok": 345,
          "own_ok": 351,
          "ok": 342
        }
      },
      "raws79": {
        "verdict": "no",
        "own_bats": [
          113,
          141
        ],
        "gain_pp": 4.964539007092206,
        "eo": [
          13,
          256
        ],
        "oe": [
          2,
          305
        ],
        "identity": [
          545,
          568,
          613
        ],
        "bad_classes": [],
        "failures": {
          "O\u2192E total": 2
        },
        "enemy": {
          "n": 273,
          "matched": 257,
          "cls_ok": 252,
          "own_ok": 243,
          "ok": 240,
          "missed": 16
        }
      },
      "raws79b": {
        "verdict": "no",
        "own_bats": [
          74,
          105
        ],
        "gain_pp": 7.619047619047626,
        "eo": [
          5,
          148
        ],
        "oe": [
          3,
          367
        ],
        "identity": [
          489,
          530,
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
          "matched": 136,
          "cls_ok": 129,
          "own_ok": 133,
          "ok": 127,
          "missed": 21
        }
      },
      "raws79c": {
        "verdict": "QUALIFIES",
        "own_bats": [
          75,
          122
        ],
        "gain_pp": 12.295081967213118,
        "eo": [
          11,
          220
        ],
        "oe": [
          2,
          182
        ],
        "identity": [
          386,
          409,
          490
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 247,
          "matched": 227,
          "cls_ok": 217,
          "own_ok": 211,
          "ok": 206,
          "missed": 20
        }
      },
      "raws79d": {
        "verdict": "QUALIFIES",
        "own_bats": [
          133,
          182
        ],
        "gain_pp": 8.791208791208781,
        "eo": [
          7,
          331
        ],
        "oe": [
          1,
          372
        ],
        "identity": [
          690,
          716,
          798
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 369,
          "matched": 332,
          "cls_ok": 325,
          "own_ok": 324,
          "ok": 318,
          "missed": 37
        }
      },
      "raws80": {
        "verdict": "QUALIFIES",
        "own_bats": [
          140,
          221
        ],
        "gain_pp": 15.38461538461538,
        "eo": [
          9,
          692
        ],
        "oe": [
          1,
          404
        ],
        "identity": [
          1065,
          1117,
          1226
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 726,
          "matched": 686,
          "cls_ok": 669,
          "own_ok": 674,
          "ok": 660,
          "missed": 40
        }
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
          115,
          175
        ],
        "gain_pp": 15.999999999999998,
        "eo": [
          18,
          479
        ],
        "oe": [
          2,
          449
        ],
        "identity": [
          822,
          955,
          1008
        ],
        "bad_classes": [
          "hog-rider"
        ],
        "failures": {
          "hog-rider": 3,
          "E\u2192O total": 3,
          "O\u2192E total": 1
        },
        "enemy": {
          "n": 480,
          "matched": 415,
          "cls_ok": 390,
          "own_ok": 393,
          "ok": 377,
          "missed": 65
        }
      }
    },
    "own_rows": {},
    "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
    "weights_sha256": "179bcf409a4bbcd1219ad3a3fdf9ac234d2b13feba1713faf039379fa0b1a09b",
    "fresh5_pooled": {
      "verdict": "PENDING re-test",
      "own_bats": [
        535,
        771
      ],
      "gain_pp": 10.376134889753564,
      "eo": [
        45,
        1647
      ],
      "oe": [
        9,
        1630
      ],
      "identity": [
        3175,
        3340,
        3688
      ],
      "bad_classes": [
        "null"
      ],
      "failures": {
        "null": 2
      },
      "enemy": {
        "n": 1772,
        "matched": 1638,
        "cls_ok": 1592,
        "own_ok": 1585,
        "ok": 1551,
        "missed": 134
      }
    }
  },
  "vol3s13": {
    "old_pooled": {
      "verdict": "no",
      "own_bats": [
        1708,
        2289
      ],
      "gain_pp": 17.911751856705983,
      "eo": [
        131,
        3771
      ],
      "oe": [
        54,
        4390
      ],
      "identity": [
        7776,
        8316,
        9081
      ],
      "bad_classes": [
        "barbarian",
        "hog-rider",
        "mega-minion",
        "musketeer",
        "skeleton",
        "skeleton-dragon"
      ],
      "failures": {
        "barbarian": 2,
        "hog-rider": 2,
        "mega-minion": 2,
        "musketeer": 2,
        "skeleton": 5,
        "skeleton-dragon": 4,
        "E\u2192O total": 7
      },
      "enemy": {
        "n": 4009,
        "matched": 3662,
        "cls_ok": 3557,
        "own_ok": 3505,
        "ok": 3445,
        "missed": 347
      }
    },
    "per_slice": {
      "raws76": {
        "verdict": "PENDING re-test",
        "own_bats": [
          171,
          224
        ],
        "gain_pp": 26.785714285714278,
        "eo": [
          10,
          271
        ],
        "oe": [
          6,
          365
        ],
        "identity": [
          603,
          645,
          703
        ],
        "bad_classes": [
          "skeleton-dragon"
        ],
        "failures": {
          "skeleton-dragon": 3,
          "E\u2192O total": 3
        },
        "enemy": {
          "n": 275,
          "matched": 257,
          "cls_ok": 249,
          "own_ok": 244,
          "ok": 241,
          "missed": 18
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
          1,
          257
        ],
        "oe": [
          1,
          425
        ],
        "identity": [
          675,
          697,
          748
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 284,
          "matched": 262,
          "cls_ok": 253,
          "own_ok": 257,
          "ok": 252,
          "missed": 22
        }
      },
      "raws76c": {
        "verdict": "PENDING re-test",
        "own_bats": [
          207,
          299
        ],
        "gain_pp": 18.394648829431436,
        "eo": [
          10,
          335
        ],
        "oe": [
          17,
          506
        ],
        "identity": [
          793,
          851,
          943
        ],
        "bad_classes": [
          "barbarian"
        ],
        "failures": {
          "barbarian": 2,
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 340,
          "matched": 317,
          "cls_ok": 313,
          "own_ok": 306,
          "ok": 305,
          "missed": 23
        }
      },
      "raws77": {
        "verdict": "PENDING re-test",
        "own_bats": [
          170,
          240
        ],
        "gain_pp": 14.583333333333337,
        "eo": [
          14,
          397
        ],
        "oe": [
          5,
          409
        ],
        "identity": [
          737,
          816,
          899
        ],
        "bad_classes": [
          "baby-dragon",
          "mega-minion",
          "skeleton"
        ],
        "failures": {
          "baby-dragon": 2,
          "mega-minion": 2,
          "skeleton": 4,
          "E\u2192O total": 3
        },
        "enemy": {
          "n": 403,
          "matched": 363,
          "cls_ok": 348,
          "own_ok": 345,
          "ok": 336,
          "missed": 40
        }
      },
      "raws78": {
        "verdict": "no",
        "own_bats": [
          99,
          124
        ],
        "gain_pp": 19.354838709677413,
        "eo": [
          14,
          622
        ],
        "oe": [
          3,
          337
        ],
        "identity": [
          900,
          981,
          1010
        ],
        "bad_classes": [
          "null",
          "skeleton"
        ],
        "failures": {
          "null": 2,
          "skeleton": 2,
          "E\u2192O total": 5
        },
        "enemy": {
          "n": 630,
          "missed": 44,
          "matched": 586,
          "cls_ok": 578,
          "own_ok": 572,
          "ok": 568
        }
      },
      "raws78b": {
        "verdict": "PENDING re-test",
        "own_bats": [
          211,
          291
        ],
        "gain_pp": 15.807560137457044,
        "eo": [
          10,
          232
        ],
        "oe": [
          4,
          433
        ],
        "identity": [
          649,
          675,
          772
        ],
        "bad_classes": [
          "valkyrie"
        ],
        "failures": {
          "valkyrie": 2
        },
        "enemy": {
          "n": 252,
          "matched": 236,
          "cls_ok": 225,
          "own_ok": 221,
          "ok": 218,
          "missed": 16
        }
      },
      "raws78c": {
        "verdict": "QUALIFIES",
        "own_bats": [
          133,
          170
        ],
        "gain_pp": 15.294117647058824,
        "eo": [
          17,
          314
        ],
        "oe": [
          0,
          322
        ],
        "identity": [
          610,
          656,
          728
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 361,
          "matched": 315,
          "cls_ok": 306,
          "own_ok": 298,
          "ok": 290,
          "missed": 46
        }
      },
      "raws78d": {
        "verdict": "PENDING re-test",
        "own_bats": [
          180,
          253
        ],
        "gain_pp": 20.55335968379447,
        "eo": [
          5,
          383
        ],
        "oe": [
          12,
          327
        ],
        "identity": [
          661,
          725,
          816
        ],
        "bad_classes": [
          "hog-rider"
        ],
        "failures": {
          "hog-rider": 2,
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 418,
          "missed": 55,
          "matched": 363,
          "cls_ok": 348,
          "own_ok": 356,
          "ok": 346
        }
      },
      "raws79": {
        "verdict": "no",
        "own_bats": [
          117,
          141
        ],
        "gain_pp": 7.801418439716312,
        "eo": [
          10,
          257
        ],
        "oe": [
          1,
          310
        ],
        "identity": [
          554,
          573,
          613
        ],
        "bad_classes": [],
        "failures": {
          "O\u2192E total": 1
        },
        "enemy": {
          "n": 273,
          "matched": 258,
          "cls_ok": 255,
          "own_ok": 248,
          "ok": 245,
          "missed": 15
        }
      },
      "raws79b": {
        "verdict": "PENDING re-test",
        "own_bats": [
          82,
          105
        ],
        "gain_pp": 15.238095238095239,
        "eo": [
          8,
          145
        ],
        "oe": [
          1,
          373
        ],
        "identity": [
          498,
          534,
          561
        ],
        "bad_classes": [],
        "failures": {
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 157,
          "matched": 140,
          "cls_ok": 132,
          "own_ok": 132,
          "ok": 127,
          "missed": 17
        }
      },
      "raws79c": {
        "verdict": "PENDING re-test",
        "own_bats": [
          90,
          122
        ],
        "gain_pp": 24.590163934426236,
        "eo": [
          21,
          222
        ],
        "oe": [
          3,
          200
        ],
        "identity": [
          393,
          432,
          490
        ],
        "bad_classes": [
          "musketeer"
        ],
        "failures": {
          "musketeer": 3,
          "E\u2192O total": 2,
          "O\u2192E total": 1
        },
        "enemy": {
          "n": 247,
          "matched": 226,
          "cls_ok": 216,
          "own_ok": 201,
          "ok": 195,
          "missed": 21
        }
      },
      "raws79d": {
        "verdict": "PENDING re-test",
        "own_bats": [
          141,
          182
        ],
        "gain_pp": 13.186813186813184,
        "eo": [
          11,
          336
        ],
        "oe": [
          1,
          383
        ],
        "identity": [
          703,
          731,
          798
        ],
        "bad_classes": [],
        "failures": {
          "E\u2192O total": 2
        },
        "enemy": {
          "n": 369,
          "matched": 339,
          "cls_ok": 334,
          "own_ok": 325,
          "ok": 322,
          "missed": 30
        }
      },
      "raws80": {
        "verdict": "PENDING re-test",
        "own_bats": [
          148,
          221
        ],
        "gain_pp": 19.00452488687782,
        "eo": [
          13,
          688
        ],
        "oe": [
          0,
          413
        ],
        "identity": [
          1068,
          1114,
          1226
        ],
        "bad_classes": [
          "valkyrie"
        ],
        "failures": {
          "valkyrie": 2
        },
        "enemy": {
          "n": 726,
          "matched": 682,
          "cls_ok": 666,
          "own_ok": 668,
          "ok": 656,
          "missed": 44
        }
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
        "verdict": "no",
        "own_bats": [
          125,
          175
        ],
        "gain_pp": 21.714285714285715,
        "eo": [
          20,
          486
        ],
        "oe": [
          0,
          451
        ],
        "identity": [
          829,
          968,
          1008
        ],
        "bad_classes": [
          "barbarian",
          "hog-rider",
          "mini-pekka"
        ],
        "failures": {
          "barbarian": 2,
          "hog-rider": 3,
          "mini-pekka": 2,
          "E\u2192O total": 5
        },
        "enemy": {
          "n": 480,
          "matched": 417,
          "cls_ok": 388,
          "own_ok": 394,
          "ok": 375,
          "missed": 63
        }
      }
    },
    "own_rows": {},
    "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
    "weights_sha256": "7a32aac6e2ac8ccf2a3456dbab4ed7a42a55dd52d665a511fe57453125d076b7",
    "fresh5_pooled": {
      "verdict": "PENDING re-test",
      "own_bats": [
        578,
        771
      ],
      "gain_pp": 15.953307392996107,
      "eo": [
        63,
        1648
      ],
      "oe": [
        6,
        1679
      ],
      "identity": [
        3216,
        3384,
        3688
      ],
      "bad_classes": [
        "musketeer",
        "valkyrie"
      ],
      "failures": {
        "musketeer": 3,
        "valkyrie": 3
      },
      "enemy": {
        "n": 1772,
        "matched": 1645,
        "cls_ok": 1603,
        "own_ok": 1574,
        "ok": 1545,
        "missed": 127
      }
    }
  },
  "vol3s23": {
    "old_pooled": {
      "verdict": "PENDING re-test",
      "own_bats": [
        1640,
        2289
      ],
      "gain_pp": 14.941022280471817,
      "eo": [
        96,
        3751
      ],
      "oe": [
        73,
        4303
      ],
      "identity": [
        7672,
        8183,
        9081
      ],
      "bad_classes": [
        "mini-pekka",
        "skeleton"
      ],
      "failures": {
        "mini-pekka": 2,
        "skeleton": 2
      },
      "enemy": {
        "n": 4009,
        "matched": 3628,
        "cls_ok": 3525,
        "own_ok": 3508,
        "ok": 3443,
        "missed": 381
      }
    },
    "per_slice": {
      "raws76": {
        "verdict": "PENDING re-test",
        "own_bats": [
          156,
          224
        ],
        "gain_pp": 20.089285714285708,
        "eo": [
          5,
          266
        ],
        "oe": [
          10,
          354
        ],
        "identity": [
          588,
          627,
          703
        ],
        "bad_classes": [
          "mini-pekka"
        ],
        "failures": {
          "mini-pekka": 2
        },
        "enemy": {
          "n": 275,
          "matched": 251,
          "cls_ok": 246,
          "own_ok": 243,
          "ok": 242,
          "missed": 24
        }
      },
      "raws76b": {
        "verdict": "QUALIFIES",
        "own_bats": [
          102,
          138
        ],
        "gain_pp": 18.840579710144922,
        "eo": [
          2,
          256
        ],
        "oe": [
          1,
          413
        ],
        "identity": [
          656,
          683,
          748
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 284,
          "matched": 258,
          "cls_ok": 246,
          "own_ok": 253,
          "ok": 244,
          "missed": 26
        }
      },
      "raws76c": {
        "verdict": "QUALIFIES",
        "own_bats": [
          195,
          299
        ],
        "gain_pp": 14.381270903010035,
        "eo": [
          8,
          336
        ],
        "oe": [
          26,
          502
        ],
        "identity": [
          782,
          851,
          943
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 340,
          "matched": 319,
          "cls_ok": 313,
          "own_ok": 308,
          "ok": 305,
          "missed": 21
        }
      },
      "raws77": {
        "verdict": "PENDING re-test",
        "own_bats": [
          171,
          240
        ],
        "gain_pp": 15.000000000000002,
        "eo": [
          9,
          401
        ],
        "oe": [
          5,
          408
        ],
        "identity": [
          734,
          818,
          899
        ],
        "bad_classes": [
          "skeleton"
        ],
        "failures": {
          "skeleton": 2
        },
        "enemy": {
          "n": 403,
          "matched": 356,
          "cls_ok": 344,
          "own_ok": 346,
          "ok": 337,
          "missed": 47
        }
      },
      "raws78": {
        "verdict": "PENDING re-test",
        "own_bats": [
          96,
          124
        ],
        "gain_pp": 16.935483870967737,
        "eo": [
          12,
          624
        ],
        "oe": [
          3,
          330
        ],
        "identity": [
          896,
          971,
          1010
        ],
        "bad_classes": [],
        "failures": {
          "E\u2192O total": 3
        },
        "enemy": {
          "n": 630,
          "missed": 45,
          "matched": 585,
          "cls_ok": 578,
          "own_ok": 571,
          "ok": 568
        }
      },
      "raws78b": {
        "verdict": "QUALIFIES",
        "own_bats": [
          204,
          291
        ],
        "gain_pp": 13.4020618556701,
        "eo": [
          7,
          230
        ],
        "oe": [
          7,
          423
        ],
        "identity": [
          639,
          662,
          772
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 252,
          "matched": 233,
          "cls_ok": 222,
          "own_ok": 223,
          "ok": 219,
          "missed": 19
        }
      },
      "raws78c": {
        "verdict": "QUALIFIES",
        "own_bats": [
          131,
          170
        ],
        "gain_pp": 14.117647058823534,
        "eo": [
          11,
          309
        ],
        "oe": [
          0,
          313
        ],
        "identity": [
          600,
          640,
          728
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 361,
          "matched": 309,
          "cls_ok": 298,
          "own_ok": 298,
          "ok": 287,
          "missed": 52
        }
      },
      "raws78d": {
        "verdict": "PENDING re-test",
        "own_bats": [
          175,
          253
        ],
        "gain_pp": 18.577075098814234,
        "eo": [
          6,
          373
        ],
        "oe": [
          12,
          324
        ],
        "identity": [
          651,
          706,
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
          "missed": 63,
          "matched": 355,
          "cls_ok": 344,
          "own_ok": 348,
          "ok": 340
        }
      },
      "raws79": {
        "verdict": "PENDING re-test",
        "own_bats": [
          119,
          141
        ],
        "gain_pp": 9.219858156028371,
        "eo": [
          7,
          255
        ],
        "oe": [
          3,
          306
        ],
        "identity": [
          548,
          567,
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
          "matched": 256,
          "cls_ok": 252,
          "own_ok": 249,
          "ok": 245,
          "missed": 17
        }
      },
      "raws79b": {
        "verdict": "PENDING re-test",
        "own_bats": [
          80,
          105
        ],
        "gain_pp": 13.33333333333333,
        "eo": [
          10,
          144
        ],
        "oe": [
          3,
          373
        ],
        "identity": [
          492,
          528,
          561
        ],
        "bad_classes": [],
        "failures": {
          "E\u2192O total": 3
        },
        "enemy": {
          "n": 157,
          "matched": 141,
          "cls_ok": 133,
          "own_ok": 130,
          "ok": 125,
          "missed": 16
        }
      },
      "raws79c": {
        "verdict": "QUALIFIES",
        "own_bats": [
          77,
          122
        ],
        "gain_pp": 13.934426229508201,
        "eo": [
          9,
          222
        ],
        "oe": [
          2,
          183
        ],
        "identity": [
          391,
          410,
          490
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 247,
          "matched": 228,
          "cls_ok": 219,
          "own_ok": 214,
          "ok": 211,
          "missed": 19
        }
      },
      "raws79d": {
        "verdict": "PENDING re-test",
        "own_bats": [
          134,
          182
        ],
        "gain_pp": 9.340659340659341,
        "eo": [
          10,
          335
        ],
        "oe": [
          1,
          374
        ],
        "identity": [
          695,
          720,
          798
        ],
        "bad_classes": [
          "bat"
        ],
        "failures": {
          "bat": 2,
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 369,
          "matched": 337,
          "cls_ok": 330,
          "own_ok": 325,
          "ok": 320,
          "missed": 32
        }
      },
      "raws80": {
        "verdict": "QUALIFIES",
        "own_bats": [
          143,
          221
        ],
        "gain_pp": 16.742081447963802,
        "eo": [
          8,
          688
        ],
        "oe": [
          1,
          407
        ],
        "identity": [
          1068,
          1107,
          1226
        ],
        "bad_classes": [],
        "failures": {},
        "enemy": {
          "n": 726,
          "matched": 683,
          "cls_ok": 668,
          "own_ok": 673,
          "ok": 660,
          "missed": 43
        }
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
          119,
          175
        ],
        "gain_pp": 18.28571428571429,
        "eo": [
          16,
          480
        ],
        "oe": [
          1,
          450
        ],
        "identity": [
          830,
          958,
          1008
        ],
        "bad_classes": [
          "mini-pekka"
        ],
        "failures": {
          "mini-pekka": 2,
          "E\u2192O total": 1
        },
        "enemy": {
          "n": 480,
          "matched": 411,
          "cls_ok": 389,
          "own_ok": 391,
          "ok": 379,
          "missed": 69
        }
      }
    },
    "own_rows": {},
    "hero_row": "unscorable: no candidate spell_dump/hero_row artifacts found",
    "weights_sha256": "91c79efcaa74ef7b273f9244411c26630519776dbbd8fbc6dd7e18330dd92309",
    "fresh5_pooled": {
      "verdict": "PENDING re-test",
      "own_bats": [
        553,
        771
      ],
      "gain_pp": 12.710765239948119,
      "eo": [
        44,
        1644
      ],
      "oe": [
        10,
        1643
      ],
      "identity": [
        3194,
        3332,
        3688
      ],
      "bad_classes": [
        "giant"
      ],
      "failures": {
        "giant": 2,
        "O\u2192E total": 1
      },
      "enemy": {
        "n": 1772,
        "matched": 1645,
        "cls_ok": 1602,
        "own_ok": 1591,
        "ok": 1561,
        "missed": 127
      }
    }
  }
}
```

## Exact evaluation artifacts
- `127x08:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/vol0s13/weights/last.pt` SHA256`f68eef5f11bd10c247f231684fe35d1ce64b3f94b1f96f0b908060a622b39338`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/vol0s13-e12-896.json`: 198frames, SHA256`a7f63499797204f288513e5168441109509abbf17767a2d34b71e16a888abc57`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/vol0s13-e12-896.json`: 199frames, SHA256`06e3772f846466a755b06bb4eb50b138a4ec3832422e302ec9b0313eea4024f2`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/vol0s13-e12-896.json`: 200frames, SHA256`518ac0053afc72ef3cf6a78f3baeec3d1ea4de523501ec444042a4f29ec65e71`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/vol0s13-e12-896.json`: 199frames, SHA256`a3b8180006bfb72373800dd9ed5792b54b94f349f30112c6d1610221d715c8b5`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/vol0s13-e12-896.json`: 196frames, SHA256`4cc2d48328edcc99e72582cf43ae6b1b5f1f64c7999d60a70637cf2060a9d383`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/vol0s13-e12-896.json`: 199frames, SHA256`c1cc7b69ea56d2a9c4eb4768b7d370a501c03ad64b4bfdc1d202b4f8eadb80a2`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/vol0s13-e12-896.json`: 200frames, SHA256`a748e2e64041ec76c64c60f861e9a6f24a3a07c322a5e9251e7baec807286eb1`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/vol0s13-e12-896.json`: 151frames, SHA256`d82d9e8fdb7c8f4ebd72cdbf6da18bb94b729a635d5185a88e77a151cc23e8a7`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/vol0s13-e12-896.json`: 200frames, SHA256`5fd2b24564f3434db7853275259e4e18f3dfc0853d3a1bce8cf5060f1541d7c8`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/vol0s13-e12-896.json`: 200frames, SHA256`3a0ab09e97f170252736df0f50f8047b934ee8912cdfacbef3331647b17524e4`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/vol0s13-e12-896.json`: 200frames, SHA256`64cc7d6d80614272b01a028d30587b993de7ce9f429bd63da8d63b07c908ceea`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/vol0s13-e12-896.json`: 200frames, SHA256`77fecece80df3092086025c7247bcba00166ff6a33756c04bc1c2c44fc1f3e54`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/vol0s13-e12-896.json`: 200frames, SHA256`595d55c5bfb38d3f86c42a671cff8d5f634ea2654b0061dc279f4bc891bf0f69`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/vol0s13-e12-896.json`: 208frames, SHA256`2e6e0acab1ccdacc12280dcf9627ec3ee4d19c470c743050ae47c8e540268346`.
- `127x08:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/vol0s23/weights/last.pt` SHA256`e29970837cc12f2dff7b7556c8880af3240bdfb3e1bb28c2988906395995d08e`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/vol0s23-e12-896.json`: 198frames, SHA256`f406132088e8f95c7702e10922e15081dd4cd3cfe0da2150be2440e479296222`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/vol0s23-e12-896.json`: 199frames, SHA256`1b176dec801f2c91b7da7353e0a07907a0c132e4b012639dac5fc1cba0ba96dd`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/vol0s23-e12-896.json`: 200frames, SHA256`74d33c582244a106e9d5e01862b7d96e6eb0315db9a7afb72dbbdbb967203f5b`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/vol0s23-e12-896.json`: 199frames, SHA256`b1a532a530f3e3a02297f97fe364fc977a0f57631f3fc6a89abaa812495be1a8`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/vol0s23-e12-896.json`: 196frames, SHA256`d399b1983a80b88764c1f25e19f052abe7f8fa3da6fbb91ebe910e34c6b1d509`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/vol0s23-e12-896.json`: 199frames, SHA256`ecb75c64341fd504037da4a294b90592b43329981c8bea54dfc3abbb687732b2`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/vol0s23-e12-896.json`: 200frames, SHA256`93ed4eccdc575fafa4536c471f9a7fa9d4cee6e45a7ae0522b69c6a9a521ecf0`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/vol0s23-e12-896.json`: 151frames, SHA256`1140085d0d52d6430036256b7afeafdd652b7d055ff80acbabd840ef2772f894`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/vol0s23-e12-896.json`: 200frames, SHA256`c0a6aa3112d04e2d65c9f11c3228e5df3aa144f003649c483b8d545e6364aa5c`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/vol0s23-e12-896.json`: 200frames, SHA256`5c49d62a5958446df98e1d733930e52d54b0cd6da12597ee9d4eb2becf2b18e2`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/vol0s23-e12-896.json`: 200frames, SHA256`c434144911c0beb82727f82a44fc45fb7e17297d72177e72ca22906de367bafd`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/vol0s23-e12-896.json`: 200frames, SHA256`2930472c4d516786c38605100f3a70acd51a50dcb9eaa0c33afd637f097d7048`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/vol0s23-e12-896.json`: 200frames, SHA256`e2d6ff74e0c9b9955a52d90d91b5485649bfb2268a4a1ad870b60633ea945dc8`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/vol0s23-e12-896.json`: 208frames, SHA256`c7c5536fa98660f9f9ebff82ee5a3a71b54e8df9170626d1e49529a687170faa`.
- `127x08:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/vol1s13/weights/last.pt` SHA256`1a3487fed0cf2945fdb446e589d1c02397d227247ba3ff18fc3ce0560c7cd6c8`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/vol1s13-e12-896.json`: 198frames, SHA256`1fa875472b705320189337993aa7f5aa639df16d6937fa0e7072d9d18ceb5536`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/vol1s13-e12-896.json`: 199frames, SHA256`8e9c9692714eee0aac042e1346903074ecbdfb22b91511de710d3ff4cefd2e5d`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/vol1s13-e12-896.json`: 200frames, SHA256`874e40486347dace48a138596bac243cc76be97021ab5907a68101c2069a483e`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/vol1s13-e12-896.json`: 199frames, SHA256`0d9de7a5d745127b1b113b17ba3a1da61edf577e8973422b1d2762a7f062b82d`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/vol1s13-e12-896.json`: 196frames, SHA256`18e5ea91fa0ff1cc9f63f6c13fb9f02c97e4da2357ac5d48d08fd3bed5535ee7`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/vol1s13-e12-896.json`: 199frames, SHA256`213f5ae5a205dec946534839e8c999cacdb9aff4a00015b8f0a5d832aef4dcd6`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/vol1s13-e12-896.json`: 200frames, SHA256`e6e968493344ac9c57744e191385c7e686c69254a24107a0e2a765528be2c975`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/vol1s13-e12-896.json`: 151frames, SHA256`27e4b7165b7e42edf1e6505de3e8883ca5fbbacf6edb934634ad461098bb3470`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/vol1s13-e12-896.json`: 200frames, SHA256`2284bec33eda718fe8b2c50c1376bf94e84220ebfe0999eae43b05e0b8f28f39`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/vol1s13-e12-896.json`: 200frames, SHA256`80ca22c99649931f28492a18094b6d71729d928150444767b94ccf01dc5e36b6`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/vol1s13-e12-896.json`: 200frames, SHA256`a400aef88a23d8946d217e44591e73ccc33e0502d70bb8474a12cdf1c74c0304`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/vol1s13-e12-896.json`: 200frames, SHA256`bce3f7d616c801682fa436d40b5faf400796c9ec00324c04d9741612f382745c`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/vol1s13-e12-896.json`: 200frames, SHA256`a4938e64ea7637c79abccf4fd0cecf85ccd117330758015f3f04d9efe4f7f45a`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/vol1s13-e12-896.json`: 208frames, SHA256`3f36a8f62220bf95710a23bd1e54599407652c7a3f99712e79abc2a87bee6aff`.
- `127x08:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/vol1s23/weights/last.pt` SHA256`179bcf409a4bbcd1219ad3a3fdf9ac234d2b13feba1713faf039379fa0b1a09b`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/vol1s23-e12-896.json`: 198frames, SHA256`d402d2a3232b79a760d72112cb0996bb5a25115cb84cd0d31d8985d7402237ce`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/vol1s23-e12-896.json`: 199frames, SHA256`917602b5bf8443582957ff256b1f9929f3862eda6ceb3a78dd84564cb07b823a`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/vol1s23-e12-896.json`: 200frames, SHA256`bf57b022b353f6812a732d6335d46f1346cec55365b1f84f6abbadae6bef3e1e`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/vol1s23-e12-896.json`: 199frames, SHA256`6e20da36c7c660dc566b7d49e2c0579b8bb2565cca57624f1180d2c65f04f5d5`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/vol1s23-e12-896.json`: 196frames, SHA256`af19deb57d229094da594725f2c943e505c1fafcd21e4bf44da0c0017a0413d1`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/vol1s23-e12-896.json`: 199frames, SHA256`50d67cf56308d513a5ee1e40376827e97f1561794b2dc13aaeae85715e25ed55`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/vol1s23-e12-896.json`: 200frames, SHA256`c7b9715f537156d551365fe0b1713d35245ccbc419dbd82e05e6b86881b3ad66`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/vol1s23-e12-896.json`: 151frames, SHA256`66012a6bdf7e52379f013212fa8303f3a463acd32b09ca6886983e935504d6da`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/vol1s23-e12-896.json`: 200frames, SHA256`0f46961da68d59fc5c8417d25247d15b6ed4c8d9598be58e7d183f8653194699`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/vol1s23-e12-896.json`: 200frames, SHA256`b4131ca687895033cb8bf84e6c2c16fba1bbf738529203785d5575948a99cffa`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/vol1s23-e12-896.json`: 200frames, SHA256`d9692c007783b3c9140b12bd49f14dfd0d123aa28dd9278a0f636e5ec795b935`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/vol1s23-e12-896.json`: 200frames, SHA256`2493893cb17bf5133cdd03983c990fc9b90e1e73cc8dbd963306a71147867c54`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/vol1s23-e12-896.json`: 200frames, SHA256`cdd09efeeab902f432c9d70ac45d4068bf774f0b1ae212ee4de02f30619a9fe9`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/vol1s23-e12-896.json`: 208frames, SHA256`48087465ca9d6471bb5b6c5c9150bd450b42788bfce473c92bc3ced3cfeaf162`.
- `127x08:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/vol3s13/weights/last.pt` SHA256`7a32aac6e2ac8ccf2a3456dbab4ed7a42a55dd52d665a511fe57453125d076b7`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/vol3s13-e12-896.json`: 198frames, SHA256`8700e0aff9575acbb7f5cc199b9e2296a2f32203ff07cb06b4f5ad0c2c5966f2`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/vol3s13-e12-896.json`: 199frames, SHA256`0e2b4500a19608a3f6841647f43eef72afd935c3fa7aa1dda2026e1c2d8ed4e3`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/vol3s13-e12-896.json`: 200frames, SHA256`a25fb817ae68ce35c445c96c071074256049d60306c4ced991758bcb044460c5`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/vol3s13-e12-896.json`: 199frames, SHA256`e5b4d46afe07c537abf054d01f203ec0df74c2613900ea6d3c1277b1ea035d55`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/vol3s13-e12-896.json`: 196frames, SHA256`b8c137741ebbb94d1654c0e2fba2d74eb5a7ef06f969f72ab2fe2140506a5f4b`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/vol3s13-e12-896.json`: 199frames, SHA256`fcdeb08790d07cdd265e7561fe6fa76755121ffe3da39d61ad311f006a78bad5`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/vol3s13-e12-896.json`: 200frames, SHA256`af75be33628b69818332aac107e837cda053ecf3c3d08a8c94678476dc9e0117`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/vol3s13-e12-896.json`: 151frames, SHA256`085fd3968420b0304392f570cb51edf5b14d70dde47670a6a0f375882c3658b0`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/vol3s13-e12-896.json`: 200frames, SHA256`8da1ea9290287b19eadf68120f6e5f51344ce70f63dcb8198ccd47a3a017b1fa`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/vol3s13-e12-896.json`: 200frames, SHA256`d53f5d199cc20c0e55345d7520be551faa61308bd40885cf645d9e1c77722a88`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/vol3s13-e12-896.json`: 200frames, SHA256`506a602eef71526bc9c693129a7af7611f56a8ea720563d997e2b52b6e084657`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/vol3s13-e12-896.json`: 200frames, SHA256`97e9326286058bc7c2a3b80a0a22ad66ce93f82403e1a815aa95b74691c84afe`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/vol3s13-e12-896.json`: 200frames, SHA256`1ec4a96f5ad309f5c451f4d618cca8fe2fd82f7edbb421e4efd45f2c3849357b`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/vol3s13-e12-896.json`: 208frames, SHA256`ccd15de59bee996ce22232d672b8e2a8b83a1a2614dfd8b5121079b6bb30b4ea`.
- `127x08:/mpac/sdicks02/jobs/clasher/live-yolo-20261016/runs/vol3s23/weights/last.pt` SHA256`91c79efcaa74ef7b273f9244411c26630519776dbbd8fbc6dd7e18330dd92309`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76/vol3s23-e12-896.json`: 198frames, SHA256`a936ddaf5bec8c29192879d2220104a6e8c3b0073aec26448add867855ac8a5d`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76b/vol3s23-e12-896.json`: 199frames, SHA256`438e9d003e6c3b4aebd46121c93dd666a106ecc6c8ea19e28bb735302721969c`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws76c/vol3s23-e12-896.json`: 200frames, SHA256`493d32c89eebca296f225ae372fbc2fab273040f17674d947eabf882f9c5a07b`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws77/vol3s23-e12-896.json`: 199frames, SHA256`64ca9af0a414e3e59d20d5ad1d80d6c5f6a67677c214754e6747f4971fc77e09`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78/vol3s23-e12-896.json`: 196frames, SHA256`f63ac2c24c1c1e02eeffae79c3a3811a26d1d6197dcb1ad62ee3e43a408804ad`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78b/vol3s23-e12-896.json`: 199frames, SHA256`d514e77ee85e7a746dee981f45b1e341ea53f902a84a06c5947c3d32e8e870c5`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78c/vol3s23-e12-896.json`: 200frames, SHA256`0315a62395ff8eb4c5e5d4db20f338f34b8795913f04e26c7b0c37a91db28b6c`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws78d/vol3s23-e12-896.json`: 151frames, SHA256`fc7bb9c134625ab9723dcf19e12dc579272cdf9d051e3da785f90929cec57b28`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79/vol3s23-e12-896.json`: 200frames, SHA256`af4819163095d5609348a6c887a58b75dbf5562b3a88b6264b3a7298cea47650`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79b/vol3s23-e12-896.json`: 200frames, SHA256`e545062631c7689576871dd5a03abb63772201bb6f4f1ce8d75bae3ddae420c7`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79c/vol3s23-e12-896.json`: 200frames, SHA256`bc544fd28799bd20b8d7c862128decff8160ccca71c5679de2c8ad0601ace1e1`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws79d/vol3s23-e12-896.json`: 200frames, SHA256`504fa31e3a47283e343645a2b975d63726f3607dd2379416b66456d8992d2457`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/raws80/vol3s23-e12-896.json`: 200frames, SHA256`988fce86760e0bd2c8e4d57bc250d533545092b68b32afef101d6c75cac5be1c`.
  - `/mpac/sdicks02/jobs/clasher/live-yolo-20261016/evals/hogvid/vol3s23-e12-896.json`: 208frames, SHA256`17eb79f94bc628814d852b4ee115e628cc3f5e5121f157e435fcc1d73631b875`.
- `/tmp/clasher-results-collector/collect_perception.py` SHA256`91a1056771aadea23f8153f338e3ea8ab2dc1626aff0e8b5895dabf785fde295`.
- `/tmp/clasher-results-collector/collect_baseline.py` SHA256`c5fe919a1e521d031de5dead911cf6a5c873d87982fe51322a6b4a35048d8990`.
- `/tmp/clasher-results-collector/score_perception.py` SHA256`c2f026a7c8586905e0e9629cb3642d60ec7c77a5e445e00bd2d5e7b515ac118a`.

## Complete old12 per-class audit — vol0s13

Computed 2026-10-18T04:06:51.833805+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 14/14 | +0 | False | 233/256 / 233/256 | 1311/1377 / 1311/1377 |
| baby-dragon | 2/2 | +0 | False | 93/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 19/19 | +0 | False | 519/607 / 519/607 | 0/0 / 0/0 |
| bat | 111/111 | +0 | False | 84/97 / 84/97 | 1295/2289 / 1295/2289 |
| battle-ram | 2/2 | +0 | False | 72/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 0/0 | +0 | False | 37/47 / 37/47 | 0/0 / 0/0 |
| cannon | 1/1 | +0 | False | 42/43 / 42/43 | 446/458 / 446/458 |
| giant | 1/1 | +0 | False | 17/18 / 17/18 | 74/82 / 74/82 |
| goblin-brawler | 0/0 | +0 | False | 31/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 0/0 | +0 | False | 16/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 0/0 | +0 | False | 48/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 1/1 | +0 | False | 54/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 97/100 / 97/100 | 0/0 / 0/0 |
| knight | 3/3 | +0 | False | 75/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 2/2 | +0 | False | 32/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 6/6 | +0 | False | 146/160 / 146/160 | 510/562 / 510/562 |
| minion | 11/11 | +0 | False | 124/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 21/21 | +0 | False | 56/88 / 56/88 | 0/0 / 0/0 |
| None | 5/5 | +0 | False | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 16/16 | +0 | False | 813/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 1/1 | +0 | False | 144/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 2/2 | +0 | False | 223/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 48/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 10/10 | +0 | False | 184/223 / 184/223 | 260/304 / 260/304 |
| witch | 1/1 | +0 | False | 59/74 / 59/74 | 0/0 / 0/0 |
| wizard | 4/4 | +0 | False | 57/76 / 57/76 | 0/0 / 0/0 |

## Complete old12 per-class audit — vol0s23

Computed 2026-10-18T04:06:51.833805+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 10/14 | -4 | False | 237/256 / 233/256 | 1318/1377 / 1311/1377 |
| baby-dragon | 4/2 | +2 | True | 91/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 14/19 | -5 | False | 528/607 / 519/607 | 0/0 / 0/0 |
| bat | 118/111 | +7 | True | 82/97 / 84/97 | 1364/2289 / 1295/2289 |
| battle-ram | 0/2 | -2 | False | 73/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 0/0 | +0 | False | 38/47 / 37/47 | 0/0 / 0/0 |
| cannon | 1/1 | +0 | False | 41/43 / 42/43 | 447/458 / 446/458 |
| giant | 1/1 | +0 | False | 18/18 / 17/18 | 74/82 / 74/82 |
| goblin-brawler | 0/0 | +0 | False | 31/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 0/0 | +0 | False | 16/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 0/0 | +0 | False | 49/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 4/1 | +3 | True | 47/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 100/100 / 97/100 | 0/0 / 0/0 |
| knight | 2/3 | -1 | False | 76/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 3/2 | +1 | False | 32/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 7/6 | +1 | False | 147/160 / 146/160 | 514/562 / 510/562 |
| minion | 8/11 | -3 | False | 125/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 19/21 | -2 | False | 55/88 / 56/88 | 0/0 / 0/0 |
| None | 6/5 | +1 | False | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 20/16 | +4 | True | 819/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 1/1 | +0 | False | 146/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 2/2 | +0 | False | 224/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 47/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 10/10 | +0 | False | 184/223 / 184/223 | 255/304 / 260/304 |
| witch | 3/1 | +2 | True | 55/74 / 59/74 | 0/0 / 0/0 |
| wizard | 1/4 | -3 | False | 59/76 / 57/76 | 0/0 / 0/0 |

## Complete old12 per-class audit — vol1s13

Computed 2026-10-18T04:06:51.833805+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 11/14 | -3 | False | 236/256 / 233/256 | 1309/1377 / 1311/1377 |
| baby-dragon | 2/2 | +0 | False | 97/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 11/19 | -8 | False | 531/607 / 519/607 | 0/0 / 0/0 |
| bat | 69/111 | -42 | False | 82/97 / 84/97 | 1681/2289 / 1295/2289 |
| battle-ram | 3/2 | +1 | False | 68/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 0/0 | +0 | False | 35/47 / 37/47 | 0/0 / 0/0 |
| cannon | 0/1 | -1 | False | 43/43 / 42/43 | 448/458 / 446/458 |
| giant | 1/1 | +0 | False | 17/18 / 17/18 | 74/82 / 74/82 |
| goblin-brawler | 2/0 | +2 | True | 29/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 1/0 | +1 | False | 15/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 0/0 | +0 | False | 48/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 1/1 | +0 | False | 82/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 100/100 / 97/100 | 0/0 / 0/0 |
| knight | 2/3 | -1 | False | 75/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 4/2 | +2 | True | 31/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 8/6 | +2 | True | 146/160 / 146/160 | 512/562 / 510/562 |
| minion | 10/11 | -1 | False | 122/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 20/21 | -1 | False | 59/88 / 56/88 | 0/0 / 0/0 |
| None | 6/5 | +1 | False | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 23/16 | +7 | True | 813/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 2/1 | +1 | False | 146/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 5/2 | +3 | True | 222/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 48/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 17/10 | +7 | True | 180/223 / 184/223 | 260/304 / 260/304 |
| witch | 3/1 | +2 | True | 55/74 / 59/74 | 0/0 / 0/0 |
| wizard | 1/4 | -3 | False | 57/76 / 57/76 | 0/0 / 0/0 |

## Complete old12 per-class audit — vol1s23

Computed 2026-10-18T04:06:51.833805+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 11/14 | -3 | False | 236/256 / 233/256 | 1310/1377 / 1311/1377 |
| baby-dragon | 1/2 | -1 | False | 95/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 9/19 | -10 | False | 523/607 / 519/607 | 0/0 / 0/0 |
| bat | 71/111 | -40 | False | 84/97 / 84/97 | 1576/2289 / 1295/2289 |
| battle-ram | 1/2 | -1 | False | 70/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 0/0 | +0 | False | 38/47 / 37/47 | 0/0 / 0/0 |
| cannon | 0/1 | -1 | False | 43/43 / 42/43 | 447/458 / 446/458 |
| giant | 3/1 | +2 | True | 17/18 / 17/18 | 68/82 / 74/82 |
| goblin-brawler | 1/0 | +1 | False | 28/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 0/0 | +0 | False | 16/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 1/0 | +1 | False | 47/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 3/1 | +2 | True | 66/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 99/100 / 97/100 | 0/0 / 0/0 |
| knight | 1/3 | -2 | False | 77/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 2/2 | +0 | False | 33/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 5/6 | -1 | False | 148/160 / 146/160 | 509/562 / 510/562 |
| minion | 6/11 | -5 | False | 127/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 23/21 | +2 | True | 56/88 / 56/88 | 0/0 / 0/0 |
| None | 7/5 | +2 | True | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 20/16 | +4 | True | 816/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 2/1 | +1 | False | 145/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 3/2 | +1 | False | 222/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 47/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 7/10 | -3 | False | 182/223 / 184/223 | 259/304 / 260/304 |
| witch | 3/1 | +2 | True | 59/74 / 59/74 | 0/0 / 0/0 |
| wizard | 1/4 | -3 | False | 58/76 / 57/76 | 0/0 / 0/0 |

## Complete old12 per-class audit — vol3s13

Computed 2026-10-18T04:06:51.833805+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 6/14 | -8 | False | 243/256 / 233/256 | 1320/1377 / 1311/1377 |
| baby-dragon | 3/2 | +1 | False | 97/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 21/19 | +2 | True | 517/607 / 519/607 | 0/0 / 0/0 |
| bat | 58/111 | -53 | False | 84/97 / 84/97 | 1702/2289 / 1295/2289 |
| battle-ram | 1/2 | -1 | False | 72/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 0/0 | +0 | False | 35/47 / 37/47 | 0/0 / 0/0 |
| cannon | 2/1 | +1 | False | 41/43 / 42/43 | 448/458 / 446/458 |
| giant | 1/1 | +0 | False | 17/18 / 17/18 | 72/82 / 74/82 |
| goblin-brawler | 1/0 | +1 | False | 29/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 0/0 | +0 | False | 16/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 0/0 | +0 | False | 49/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 3/1 | +2 | True | 82/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 99/100 / 97/100 | 0/0 / 0/0 |
| knight | 2/3 | -1 | False | 76/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 4/2 | +2 | True | 31/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 5/6 | -1 | False | 148/160 / 146/160 | 515/562 / 510/562 |
| minion | 9/11 | -2 | False | 125/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 23/21 | +2 | True | 49/88 / 56/88 | 0/0 / 0/0 |
| None | 6/5 | +1 | False | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 21/16 | +5 | True | 820/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 5/1 | +4 | True | 142/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 1/2 | -1 | False | 223/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 47/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 10/10 | +0 | False | 180/223 / 184/223 | 257/304 / 260/304 |
| witch | 1/1 | +0 | False | 59/74 / 59/74 | 0/0 / 0/0 |
| wizard | 2/4 | -2 | False | 58/76 / 57/76 | 0/0 / 0/0 |

## Complete old12 per-class audit — vol3s23

Computed 2026-10-18T04:06:51.833805+00:00 on127x08 under nice19 from stored-output counters. Owner errors use pooled_gate prediction-centred matching, both directions combined; class-correct counts use own_conf_report/enemy_conf_report truth-centred matching. None is normalized missing truth identity and remains in the fixed owner-error rule.

| Class | Owner errors candidate/reference | Excess | Bad (>+1) | Enemy correct/truth candidate/reference | Own correct/truth candidate/reference |
|---|---|---:|---|---|---|
| archer | 7/14 | -7 | False | 241/256 / 233/256 | 1297/1377 / 1311/1377 |
| baby-dragon | 2/2 | +0 | False | 93/127 / 93/127 | 0/0 / 0/0 |
| barbarian | 17/19 | -2 | False | 526/607 / 519/607 | 0/0 / 0/0 |
| bat | 74/111 | -37 | False | 82/97 / 84/97 | 1632/2289 / 1295/2289 |
| battle-ram | 1/2 | -1 | False | 71/78 / 72/78 | 0/0 / 0/0 |
| bomb-tower | 0/0 | +0 | False | 106/106 / 106/106 | 0/0 / 0/0 |
| bomber | 1/0 | +1 | False | 36/47 / 37/47 | 0/0 / 0/0 |
| cannon | 0/1 | -1 | False | 43/43 / 42/43 | 447/458 / 446/458 |
| giant | 2/1 | +1 | False | 17/18 / 17/18 | 69/82 / 74/82 |
| goblin-brawler | 0/0 | +0 | False | 31/33 / 31/33 | 0/0 / 0/0 |
| goblin-cage | 0/0 | +0 | False | 16/16 / 16/16 | 0/0 / 0/0 |
| goblin-hut | 0/0 | +0 | False | 48/50 / 48/50 | 0/0 / 0/0 |
| hog-rider | 0/1 | -1 | False | 65/177 / 54/177 | 0/0 / 0/0 |
| ice-golem | 0/0 | +0 | False | 0/1 / 0/1 | 0/0 / 0/0 |
| inferno-tower | 0/0 | +0 | False | 95/100 / 97/100 | 0/0 / 0/0 |
| knight | 3/3 | +0 | False | 75/78 / 75/78 | 0/0 / 0/0 |
| mega-minion | 2/2 | +0 | False | 32/35 / 32/35 | 0/0 / 0/0 |
| mini-pekka | 8/6 | +2 | True | 145/160 / 146/160 | 513/562 / 510/562 |
| minion | 6/11 | -5 | False | 125/139 / 124/139 | 0/0 / 0/0 |
| musketeer | 10/21 | -11 | False | 67/88 / 56/88 | 0/0 / 0/0 |
| None | 4/5 | -1 | False | 0/0 / 0/0 | 0/0 / 0/0 |
| skeleton | 18/16 | +2 | True | 817/933 / 813/933 | 0/0 / 0/0 |
| skeleton-dragon | 0/1 | -1 | False | 146/149 / 144/149 | 0/0 / 0/0 |
| spear-goblin | 1/2 | -1 | False | 222/250 / 223/250 | 0/0 / 0/0 |
| tombstone | 0/0 | +0 | False | 48/48 / 48/48 | 0/0 / 0/0 |
| valkyrie | 11/10 | +1 | False | 178/223 / 184/223 | 252/304 / 260/304 |
| witch | 1/1 | +0 | False | 59/74 / 59/74 | 0/0 / 0/0 |
| wizard | 1/4 | -3 | False | 59/76 / 57/76 | 0/0 / 0/0 |
