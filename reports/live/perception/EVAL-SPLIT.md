# Official-frame unit evaluation set: split and rules (the yardstick for every unit-perception candidate)

Owner: `live-perc-r3`. Written 2026-10-16. Not sealed: results are reported as soon as they exist. Its value depends on one rule:
**no frame from a held-out battle may be used for training, threshold tuning or model selection of a candidate that is
then reported on it** (round 3 picked epochs on this set; that is stated wherever its numbers appear).

## Held-out battles (evaluation only)

| arena | battle (05 path under `/mpac/sdicks02/scratch/live-loop/`) | labelled frames (excluded) | units | role |
|---|---|---:|---:|---|
| Goblin Stadium | `rec/ladder1-r1` | 3 | 2 | seen arena (its f255 was a round-3 training floor) |
| Goblin Stadium | `runs/live1/video` | 8 (1) | 30 | seen arena (f308/f312 were floors) |
| Goblin Stadium | `runs/live2/video` | 9 | 34 | seen arena (f604 was a floor) |
| Goblin Stadium | `runs/live3/video` | 11 | 33 | seen arena (f356 was a floor) |
| Goblin Stadium | `runs/live4/video` | 5 (2) | 21 | seen arena (live4 start frames were floors) |
| Goblin Stadium | `runs/live5/video` | 12 | 39 | no frame of this battle used anywhere |
| Training Camp | `rec/tc2-r1` | 26 (4) | 97 | **unseen arena** (never a floor) |
| Bone Pit | `runs/s1m01/video` | 25 | 76 | unseen in round 3; new-card held-out battle |
| Bone Pit | `runs/s2m01/video` | 11 (1) | 46 | new-card held-out battle |
| Bone Pit | `runs/s5m01/video` | 12 | 57 | new-card held-out battle |
| Bone Pit | `runs/s5m02/video` | 12 | 37 | |
| Bone Pit | `runs/s7/m04/video` (manifest run `s7-m04`) | 14 | 46 | new-card held-out battle (deck has Bomber, but none on the sampled frames) |
| Barbarian Bowl | `runs/s14/m02/video` + `runs/s15/m01/video` (runs `s14-m02`, `s15-m01`) | 42 (2) | 178 | Barbarian Bowl held-out battles (added 2026-10-16; Sol bb1/bb2, points + box_px) |
| Barbarian Bowl | `runs/s19/m01/video`, `runs/s19/m02/video` (runs `s19-m01`, `s19-m02`) | labelling (owner-net-opus / Sol) | — | **owner / enemy-building eval** (enemy Cannon at s19-m01 n326); held out 2026-10-16; 20+20 frames (half building frames, half uniform) labelled from scratch by Sol own1/own2: ids `BB-s19m01-<n>` / `BB-s19m02-<n>` in `labels-raw/`, points + box_px + per-unit `damaged` / `owner_cue`, sheets `label-s19/`. Owner hard examples are mined from s19-m03 onward only |
| **total (before s19)** | | **188 (10)** | **696** | |

**Empty official frames** (no units; decor false-positive test, 18): `rec/tc2-r1/000265,000270,000275,001180`;
`runs/live5/video/000280–000300` (5); `rec/ladder1-r1/000262,000275`; `runs/live1/video/000318`; `runs/live4/video/000350`;
`runs/s1m01/video/000236,000240,000245,000250,000255`.

**New-card / off-C56 truth** (Bone Pit, CARD LEAD names, `card` + `body`): GoblinCage 9 (body GoblinCage) + 3 (GoblinBrawler),
Tombstone 6 (body Skeleton; no standing Tombstone on sampled frames), SpearGoblins 4 (body SpearGoblin); no Bomber on sampled frames.
Relabel pass `nc-eval1`; "OOV:BarbarianHut" was the Goblin Hut (Battle Log decks), now `GoblinHut`.

**Training-eligible official data:** every other recording (incl. Barbarian Bowl s11-m01..m04, s12-m01..m04, s14-m01/m03/m04); in particular the 13 new-card manifest battles labelled in
`scratch/live-perc-r3/labels-nc-raw/` (live6, live7, live8, live11, s2-m02, s6-m01, s7-m01, s7-m02, s7-m03, s8-m01, s8-m02,
s8-m03, s8-m04). Matches recorded later are training-eligible unless added to the table above.

## Files (05, `/mpac/sdicks02/scratch/live-perc-r3/`; images never committed)

- `labels/<ID>.json`: verified full-frame labels (`finalize_labels.py` from `labels-raw/` + verifier exclusions/relabels).
  Unit = `{card, [body], owner: us|opp, x, y, conf, note}`. **Coordinates are tiles of the native arena**: x 0..18 from the
  arena's left, y 0..32 from its top (our king at (9, 29)); the point is the unit's ground position (feet; shadow for flyers),
  the same convention as the renderer truth. To get capture pixels: `live/loop/canvas.py` (`tile_to_android`, Android 1080×1920,
  then scale to the capture size).
- `label/index.json`: frame id → source JPEG (720×1280 capture or 1020×1816) + sheet.
- `empties.txt`: the 18 empty frames.
- Cards outside a model's vocabulary (`OOV:*`, `UNKNOWN`) are ignore regions for identity scoring and count for owner-only scoring.

## Metric (as `live/perception/r3/eval_official.py`)

Greedy score-ordered matching, same owner, **≤1 tile** between predicted and true ground point (≤1.5 reported too):
identity×owner P/R and owner-only P/R per arena (GS / TC / BP), false units per empty frame, per-card recall. A YOLO-style
detector is scored by converting each box to its ground point (bottom centre of the box, ~0.25 tile up for ground units; the box's
shadow point for flyers if available) and mapping to tiles with the inverse of `canvas.tile_to_android`.

Reference numbers (thr .5, this 148-frame set): round 1 (`export-final`) GS .833/.063, TC .176/.031, BP .806/.242;
ft-r5 final (`export-interim-r5e3`) GS .959/.440, TC 1.000/.485, BP .853/.388, BB .922/.476; 0 false units on empty frames (round 1: 1.0/frame on TC).
YOLO (sprite-level identity), thr .5: `yolo-v2m-e2` GS .950/.843, TC .976/.835, BP .851/.718, BB .907/.770; `yolo-v2l-e11` GS .946/.887,
TC .988/.856, BP .860/.752, BB .954/.809; 0 empty-frame false units.
