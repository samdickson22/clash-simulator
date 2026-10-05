# Current-client detector annotation queue canary

Date: 2026-08-17  
Source video: `hTG8dM4KtM4`  
Status: deterministic queue/export contract proven; no detector training run

## What was built

`scripts/build_current_client_annotation_queue.py` turns the existing current
YouTube neutral sequence into review work rather than pseudo-ground-truth:

1. It groups adjacent same-class/team boxes into deterministic video-local
   tracks. Boxes remain detector proposals and are explicitly marked non-labels.
2. It infers deck hints only from card identities repeatedly visible in the
   public dual HUD. A card seen fewer than five times is not a deck hint.
3. It ranks visually related choices from the stable current-client vocabulary.
   The 88 wholly missing classes receive first priority when their root card is
   supported by that player's HUD deck evidence.
4. Evolution bodies require an evolution-specific visual class. A base deck
   card alone can never suggest its evolution identity.
5. Root-family-only mappings remain unlabelled and the decision parser rejects
   attempts to accept them.
6. YOLO images/labels are emitted only for explicit accepted decisions.

The split unit is the complete source video: all frames, proposal tracks, and
both actor projections use `youtube:<video_id>`. The retained canary is forced
wholly to test. Future video IDs use the same versioned 80/10/10 SHA-256 split
contract as the detector-upgrade manifest.

## Canary result

- 2,872 proposal tracks were formed from the already-extracted 3,204 frames.
- A 12-item stratified review queue contains four missing-class proposals,
  three family-only proposals, three exact-class retention proposals, and two
  no-candidate proposals.
- Visual review accepted four boxes and rejected eight; none remain pending.
- Two accepted missing-class boxes are `troop_body:Recruit`.
- Two accepted retention boxes are `troop_body:GoblinBrawler`.
- Generic Skeleton proposals were rejected because pixels did not distinguish
  `SkeletonWarrior` from other skeleton bodies.
- Goblin Cage evolution-family and Flying Machine/DartBarrell-projectile hints
  were rejected because root-family agreement is not stable identity evidence.
- An old `barbarian` proposal was rejected after visual inspection and contrary
  team-deck evidence showed that the crowded sprite was likely a Royal Recruit.

Queue artifact:
`reports/current_client_annotation_queue_hTG8dM4KtM4_v1.json`  
SHA-256: `a97d6b3b227642b524a098e2ec13f88e15562a9834eeedb2ac11bcc3d1f174d8`

Review decisions:
`reports/current_client_annotation_decisions_hTG8dM4KtM4_v1.json`

## Visual audit

![Reviewed detector proposal queue](/Users/sam/Desktop/code/clasher/reports/current_client_annotation_queue_hTG8dM4KtM4_v1.jpg)

Yellow rectangles are the old detector's proposed sprite boxes. Each panel
shows the stable hint and final accepted/rejected state. I inspected the full
resolution source frames behind all 12 panels and additionally opened the
accepted Recruit and Goblin Brawler exports at full resolution. This caught the
incorrect Barbarian proposal that a class-name-only review would have accepted.

## YOLO-ready export

Accepted-only output:
`datasets/derived/current_client_annotation_queue_hTG8dM4KtM4_v1`

It contains four test images, four normalized YOLO label files, and an ordered
two-class `classes.json`. Rejected and pending proposals produce no image or
label. This canary is deliberately test-only and must not be used to train the
future detector.

## Validation

```bash
PYTHONPATH=src:. uv run python scripts/build_current_client_annotation_queue.py \
  --decisions reports/current_client_annotation_decisions_hTG8dM4KtM4_v1.json
PYTHONPATH=src:. uv run pytest -q tests/test_current_client_annotation_queue.py
uv run ruff check scripts/build_current_client_annotation_queue.py \
  tests/test_current_client_annotation_queue.py
uv run mypy scripts/build_current_client_annotation_queue.py
```

The tests enforce source-video split isolation, proposal/label separation,
family-only fail-closed behavior, explicit review counts, accepted-only export,
and normalized YOLO coordinates.
