# Human-data feasibility inventory

This read-only pass found enough existing material to justify the agreed one-day audit. It did not establish 20 clean chronological public-v4 sequences with disjoint training/evaluation roles. Zero sequences were newly certified here. That is a certification count, not a claim that none can be recovered. No extraction, annotation, reconstruction, fitting, or source mutation ran.

## Existing material

| Source | Live inventory or historical evidence | Current interpretation |
|---|---|---|
| `datasets/katacr_hog26_human_v1.npz` | Live: 383,670 rows, 347 contiguous episodes, 17,331 plays, 366,339 waits | Legacy camera-derived corpus. It lacks source replay/frame arrays and all new level/confidence/history/lifecycle fields. |
| `datasets/human_safety_fullhuman_tvtrain_seed1043701.npz` | Live: 596,905 rows, 794 contiguous episodes, 27,067 plays, 29 abilities | Mixed rehearsal, not 794 human episodes. Manifest composition is 347 KataCR episodes/383,589 rows, 299 behavior-teacher episodes/210,000 rows, and 148 TV human-train episodes/3,316 rows. |
| `datasets/tv_royale_human_chronological_expanded_v2.npz` | Live: 3,768 rows, 182 contiguous episodes, 2,076 plays. Episode lengths 4–61 rows, median 16. | Sparse legacy sequences. The merged archive lacks source replay/frame arrays, confidence, levels, and public-v4 lifecycle/history. |
| `datasets/tv_royale_replay_disjoint_{train,holdout}_seed1043201.npz` | Live: 148 train replay IDs/3,316 rows and 37 holdout replay IDs/824 rows; zero replay-ID overlap. Source frames strictly increase within each episode. | Useful chronological and role provenance. No actor-ID array or public-v4 level/confidence contract. Legacy legal-label checks pass but do not establish HUD accuracy, forms, or temporal alignment. |
| Newer causal YouTube pipeline | Historical latest manifest: 58 replay groups, 116 actor episodes, 156,304 rows, 1,411 supervised plays and 114,278 supervised waits. Its rebuilt corpus and public sidecar paths are currently absent. | The 58 source manifests and their neutral, two-actor overlay, and offline-target artifacts remain present. All 58 manifest hashes match the historical audit. Reusable source material exists despite missing aggregate tensor files. |
| IL_Replay first 5,000 matches | Existing compatibility audit: 2 base-only sides among 10,000 sides; zero two-sided base/level-11 candidate matches; all 365,362 placement forms unknown; zero of 18,913 abilities authoritatively attributed. | Action/deck analysis only. No state/action reconstruction was attempted here. These are convenience-sample counts. |

The council's earlier inventory description of the 794-episode file as camera/human data needs correction. The original merge manifest explicitly identifies its 210,000 simulator-teacher rows. Both the merge and its source corpora must retain their separate provenance.

## Why the legacy corpus is not already clean

`reports/katacr_hog26_human_v1_manifest.json` explicitly says the importer fills live entities with neutral full health, maps evolution labels to base-card equivalents, and treats no-op frames as forced no-op context. It records 49,733 evolution-hand rows and 307,933 unknown-entity rows. The source groups include 221 `fast_hog_2.6` and 126 `golem_ai` files; group names alone do not establish human identity or skill.

`src/clasher/rl/katacr_replay.py::_action` sets the expert target's mask bit true after constructing the nominal mask. Thus an accepted label in this archive is not independent legality evidence. The TV placement converter instead rejects labels outside its computed mask, but that legacy mask still requires a new-contract audit.

Unknown levels may remain unknown with zero confidence; this is not a requirement to guess exact levels. The missing pieces are trustworthy observation/missingness records, retained form identity, causal masks, and evidence linking actions to the observed frame.

## Stronger candidate source for the one-day audit

Start from `reports/tv_royale_youtube_clocked_rotate_20260826/deck_closed_causal_corpus_audit_58games.json` and the per-match records listed in `causal-source-inventory.json`.

Its historical counts include 44 contract-passed replay groups, 406 targets called `full_actor_ready`, and 42 contract-passed groups with at least one such target. The current source artifacts exist for all 58 matches. This inventory verified manifest hashes and file presence, not every source artifact hash or image annotation.

The old `full_actor_ready` calculation requires target-in-mask, valid public clock, and complete own HUD. It does not by itself test new level/missingness fields, form/ruleset identity, independent visual action confirmation, complete-match coverage, or held-out role assignment. Its broader `ready_for_fresh_causal_bc` label is an old contract result, not new admission.

Six source videos exist at the recorded local path or the direct local equivalent of the old remote workspace path: `8YuZLtVvugY`, `Jlt7dX6BbVg`, `QnAT-wQKFS0`, `AI2eN0wMlXs`, `XHAA7lLNK8o`, and `R7hF_l6Ls-U`. Together their manifests claim 46 full-actor-ready targets. The other 52 videos were not found by those exact path checks; alternative archives were not exhaustively searched. These six are a practical starting point for visual review, but 46 targets are not 46 independent matches or already-clean sequences.

The manifests declare 10 Hz detector/event sampling and 5 Hz actor trajectories. Review the source presentation timestamps around each candidate rather than assuming the actor row locates the action to one 10 Hz frame. The historical causal builder resets recurrence across unaligned public plays and cadence gaps, which must stay explicit.

Both player overlays join the same neutral match, and the audit groups by source-video SHA-256. That is useful grouping information. This pass found no frozen training/development/acceptance assignment for the newer 58-group corpus; grouping alone is not a role split. All these replays have also been used in historical development, so they cannot become fresh policy acceptance evidence merely through new filenames.

## Bounded next audit

Use the surviving candidate artifacts to locate short chronological windows around HUD-confirmed plays in the six available videos. Verify identity/form, visible state alignment, legal masks, missingness, and original coordinates. Preserve failures and unknown fields. Group complete matches and both perspectives before assigning prospective human-observation training and evaluation roles. Cross-check duplicate uploads before treating video hashes as independent matches.

If at least 20 windows meet the declared contract, record them as a feasibility result and a possible small observation-evaluation/prior dataset. Do not infer broad training sufficiency. If fewer qualify, retain the review as evaluation diagnostics and state which missing source or observation fields prevented qualification. Bulk extraction is unnecessary for this initial audit.

`archive-inventory.json` contains live archive fields and counts. `manifest-evidence.json` pins the read manifests and records aggregate artifact availability. `causal-source-inventory.json` lists all 58 source manifest hashes, artifact presence, historical target counts, and exact video-path checks. The two `inspect_*.py` scripts reproduce this inventory without building labels.
