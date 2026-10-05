# TV Royale pipeline follow-up — 2026-08-18

## Outcome

This follow-up converts the H200/GH200 profiling findings into production code
and closes two bounded gates:

1. a real, visually inspected HUD identity holdout for PIL versus native tensor
   preprocessing; and
2. compact actor overlays that reconstruct exactly from the neutral state.

Replay-disjoint HUD promotion remains blocked because the second permitted
high-resolution YouTube replay could not be acquired from the public CDN.

## Real HUD identity holdout

`scripts/build_tv_royale_hud_identity_holdout.py` selects reviewed plays with
exactly one changing hand slot. Slot selection uses only the transition count;
the independent manual identity label is attached afterward. Every real crop is
kept in the replay-level test split.

- 27 manually identified play events.
- 81 strictly pre-play crops at -1,100, -800, and -500 ms.
- 11 card classes.
- Both spectator HUD orientations and multiple hand slots represented.
- Manifest SHA-256:
  `09e538a3587da6bd04ab19d5067eccc2830719369acb30c7bc52daf81af36ad1`.
- Visually inspected contact sheet SHA-256:
  `9d0329613aae08bcb76f928df91f971afa119cc95f7a29925140561355c4281a`.

The contact sheet shows correctly bounded card portraits, costs, selected/evo
frames, and no arena-entity substitution.

`scripts/evaluate_tv_royale_hud_identity_holdout.py` produced diagnostic report
SHA-256 `811eb67d423a8775cbb5c51e7732c645a06ce0ed28af9ebc686328f2895f4b79`:

| Backend | Candidate accuracy | Valid precision | Valid row recall | Event valid precision/recall |
|---|---:|---:|---:|---:|
| PIL | 81/81 | 77/77 | 95.06% | 27/27, 27/27 |
| Batched PIL | 81/81 | 77/77 | 95.06% | 27/27, 27/27 |
| Tensor | 81/81 | 74/74 | 91.36% | 27/27, 27/27 |

Batched PIL is exact to the historical PIL path. Tensor preprocessing preserves
every reviewed identity and event, but rejects three additional borderline
frames. It remains diagnostic until an untouched replay reproduces the
precision/recall gates.

## Replay-disjoint acquisition attempt

The May 15, 2026 replay `i4WTQPAh0_E` exposes an exact public 1182x2560,
60-fps, video-only VP9 format with declared size 138,690,318 bytes. The
acquisition script now supports:

- bounded YoutubeExplode;
- pinned yt-dlp exact-format acquisition; and
- yt-dlp-resolved single-request HTTPS acquisition without persisting the
  signed media URL.

All paths require public/video-only media, an exact size below 500 MiB, no
cookies/account/token, HTTPS googlevideo confinement, full decode, contiguous
10-Hz frame hashes, and atomic publication.

For this replay, YoutubeExplode returned VideoUnavailable; yt-dlp range
transfers stopped with HTTP 403 after about 35 MiB; a standard resume and a
single continuous request also returned 403. All owned partials were cleaned.
No replay-disjoint crop labels were fabricated.

## Policy-facing entity hygiene

HP bars, level text, tower bars, elixir UI, emotes, and evolution icons are now
retained only as detector support proposals. They are used for HP association
where relevant but are not serialized as policy-facing arena entities.

On the accepted 3,204-frame match:

- 52,252/89,013 serialized detector rows were support/UI primitives;
- filtering them changed 0/6,408 actor masks; and
- before/after mask SHA-256 remained
  `f05955dc361f20d6cb8781d65885b5565c26a31ec782d757a8ce39210ef87175`.

## Compact actor overlays

The mask builder now supports `--actor-storage compact`. A compact row contains
only:

- `snapshot_id` and `actor_id`;
- own HUD;
- label-independent public action mask; and
- label-validity flags.

Shared public state, timestamps, split identity, and match identity are stored
once in the neutral sequence and reconstructed by exact `snapshot_id` join.
The CUDA launcher selects compact storage.

One-match evidence:

- full actor artifacts: 7,982,755 compressed bytes;
- compact overlays: 910,377 bytes;
- savings: 7,072,378 bytes / 88.60%;
- 3,204 exact mask recomputations, zero mismatches;
- 3,204 poisoned-label counterfactuals, zero mask changes; and
- independent verifier status: passed, failed gates empty.

Verifier report SHA-256:
`78d0ae2b4be27db1806e05cfa43e6d4f33e4c3035d91c12d7356da622646e59c`.

## Validation

- HUD holdout builder/evaluator: 4 focused tests passed.
- Acquisition backend: 3 focused tests passed.
- Compact mask builder/verifier/launcher: 13 focused tests passed.
- Extractor/launcher support suite: 15 focused tests passed.
- Ruff clean on all changed source/test files.
- Mypy clean when changed scripts are checked as their normal individual
  modules.

## Next gate

Acquire at least one untouched high-resolution replay through an approved,
stable public transport or owner-provided file. Run the same unique-transition
holdout builder and require:

- tensor candidate accuracy 100%;
- event-level valid precision and recall 100%;
- no card-family leakage across replay splits; and
- current-client variant coverage.

Only then should tensor HUD preprocessing replace batched PIL for bulk GH200
extraction.
