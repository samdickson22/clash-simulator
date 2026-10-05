# Current-client detector upgrade data contract

Date: 2026-08-17  
Status: data preparation complete; large detector training deliberately not run

## Result

The old KataCR detector is not a 494-class detector. The stable policy vocabulary
contains 494 tokens, but only 315 are arena-visible detector targets; 177 are
card actions handled by the HUD identity head and two are reserved tokens.

Of the 315 arena targets:

| Relationship to the April-2024 KataCR labels | Tokens | Safe use |
|---|---:|---|
| Exact canonical or explicit visual alias | 84 | May bootstrap a detector label |
| Same root-card family only | 143 | Manual-review candidate only; never auto-label |
| No existing visual class | 88 | Requires new current-client arena annotation |

The 88 wholly missing classes comprise 41 troop bodies, five building bodies,
22 projectiles, and 20 area effects. The machine-readable manifest enumerates
all 231 missing or family-only tokens, rather than collapsing spawned bodies,
evolutions, projectiles, and effects into their root card. High-priority ordinary
current-client gaps include `troop_body:Goblinstein`,
`troop_body:Goblinstein_doctor`, `troop_body:GoblinDemolisher`,
`troop_body:GoblinMachine`, `troop_body:BossBandit`,
`troop_body:SuspiciousBush`, the two Merge Maiden forms, and their distinct
projectiles/effects. Event-only Super forms remain represented but should not
displace ordinary ladder classes in sampling.

Artifact:
`reports/current_client_detector_upgrade_manifest_v1.json`  
SHA-256: `fa5a8faf38a5dd74c6e20dd7a1e8111f455e08ea7e16bd0baf38f9949b93f6a4`

## Local evidence already available

- KataCR label authority: 155 labels, of which 141 are non-UI labels; pinned
  revision `36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8`.
- Human-segmented Clash Royale arena crops: 4,654 images across 154 class
  directories, pinned revision `31b4151fedb1b914e99c3c122c16dca61cb2b905`.
- Deterministically mapped, unambiguous old-class crops: 2,679. Ambiguous or
  family-only crops are retained for review but cannot become automatic labels.
- Newer CS541 card-face templates: 161 files, pinned revision
  `08aafd87cb3707b779804918cc65f4ae430d37ab`; 102 map unambiguously to a stable
  card action. These are valid only for the HUD card head, never for an arena
  body detector.
- Current YouTube canary: 3,204 frames and 25,801 typed detector observations.
  The entire `hTG8dM4KtM4` video is forced to the test split.

No local source supplies authoritative current in-arena sprites for every new
body. Card faces are not a substitute. Missing classes must be mined from the
permissioned current YouTube videos and human-confirmed, with detector-assisted
boxes used only as proposals.

## Leakage-safe split contract

The split key is SHA-256 over a versioned source-group ID. Thresholds are
80% train, 10% validation, and 10% test.

- One YouTube video ID, all its frames, and both actor projections stay together.
- A segmented crop sequence is grouped by visual class and filename prefix with
  only the terminal frame number removed.
- Every synthetic augmentation and placement stays with its foreground crop
  source group.
- The sole current-video canary is held out wholesale until multiple current
  videos exist.
- Offline temporal labels are never policy inputs.
- Root-family matches are not automatic labels.

The deterministic synthetic plan assigns the 4,654 old crops to 3,921 training,
515 validation, and 218 test assets. It uses a procedural arena grid rather than
held-out real-video backgrounds and is intended only for geometry/old-class
retention. It is not evidence of current-client visual coverage.

## Visual coordinate audit

![Six-frame detector alignment audit](/Users/sam/Desktop/code/clasher/reports/current_client_detector_upgrade_alignment_contact_sheet_v1.jpg)

Contact sheet SHA-256:
`88ea7632b84162abab814410cd8dabea9ef6db2f932375bb0be067f5297a3b9c`.

I visually inspected all six panels. The blue/yellow rectangles are detector
sprite boxes, not gameplay hitboxes. Green dots are the inverse-projected 18x32
world centers and land at the sprite-box centers in every inspected panel,
including both arena halves. Towers, troops, and area effects use the same
coordinate transform. The sheet also exposes semantic crowding and occasional
old-detector mistakes; therefore it proves coordinate/label plumbing alignment,
not the correctness of every pseudo-label.

## Reproduction and gates

```bash
PYTHONPATH=src:. uv run python scripts/build_current_client_detector_upgrade_manifest.py
PYTHONPATH=src:. uv run pytest -q tests/test_current_client_detector_upgrade_manifest_v1.py
uv run ruff check scripts/build_current_client_detector_upgrade_manifest.py \
  tests/test_current_client_detector_upgrade_manifest_v1.py
```

Two consecutive manifest builds produced identical manifest and contact-sheet
hashes. The focused test checks complete contiguous token coverage, typed Royal
Giant/Goblinstein/Boss Bandit examples, family-only fail-closed behavior,
source-group split isolation, HUD/arena asset separation, and authority hashes.

## Next H100 work

Before full-channel extraction, annotate a class-balanced current-video canary
covering the missing ordinary cards and variants, fine-tune the detector with
old-class rehearsal, and accept it only on entire-video held-out splits. Report
per-stable-key precision/recall, team accuracy, box-center world-coordinate
error, false-positive rate on crowded frames, and old-class retention. A fast
detector that aliases evolutions or spawned forms to a root card fails the gate.

## Hero-variant HUD addendum

The current-client graph contains 14 typed `card_action:*_hero` variants. They
are runtime-visible HUD card variants even though the stable graph manifest's
`runtime_observable` field is false: that field describes standalone entity
observability, not whether a card action can appear in a hand. All 14 therefore
need distinct HUD review/template coverage.

No exact packaged hero template exists for any of the 14. The 14 ordinary base
templates are retained only as family hints and cannot label a hero variant.
One exact video reference is now accepted for the reviewed held-out sequence;
the other 13 remain missing, and no current-video reference is training-eligible.
Current data names the same summoned body or projectile for every base/hero
pair, so this is HUD-only unless future video proves a distinct arena sprite.

The retained current video provides one strong unresolved identity hypothesis:
`card_action:BarbLog_hero` (token 100). Nineteen repeated player-0 frames show a
glowing cost-2 single-Barbarian portrait that is visually distinct from both the
local Barbarian Barrel template and 15 repeated player-1 base BarbLog portraits.
The exact source-video sequence proves its slot kind: at 30.8 seconds the
portrait is visible in bottom `Next`, and by 31.4 seconds it has cycled
into an ordinary four-card hand slot after the preceding play. It is therefore
a normal cycling card variant, not a temporary ability-control button.

The subsequent play uniquely resolves the identity for this reviewed sequence.
At 37.1 seconds the portrait is still in hand and public elixir displays 4. At
37.2 seconds the slot is empty/replaced and elixir displays 2. A friendly rolling
Barbarian Barrel is visibly present on the left lane at 37.4–37.5 seconds. The
official current client contains exactly three cost-2 hero variants: BarbLog
deploys `BarbLogProjectile`, Goblins directly summons four `Goblin_Stab` bodies,
and Ice Golem directly summons `IceGolemite`. Only `card_action:BarbLog_hero`
matches the distinct portrait, cost, cycle, and deployment mechanics.

The exact identity is therefore accepted for this reviewed held-out sequence.
It is not a root-family auto-label, does not generalize automatically to other
video crops, and creates no new arena class because it uses the existing
BarbLog projectile/body mechanics.

Hero manifest:
`reports/current_client_hero_variant_hud_manifest_v1.json`  
SHA-256: `89e05015df007da57045388b287add246c0a0d878631cc5fc77bcf087cf7e3b5`

![Hero variant visual comparison](/Users/sam/Desktop/code/clasher/reports/current_client_hero_variant_hud_contact_sheet_v1.jpg)

The comparison sheet SHA-256 is
`1cdd9c42b5d9c16edf7568e6b5ef2a0d5c103bbd15cf8f1a6c46ce25da0e5e95`.

Deployment evidence:
`reports/barblog_hero_deployment_evidence_v1.json`  
SHA-256: `4b1cf6977fc19ff69e9ddf7f92346372ed7229501b20a9286a53722bf98e03aa`

![BarbLog hero deployment sequence](/Users/sam/Desktop/code/clasher/reports/barblog_hero_deployment_sequence_v1.jpg)
