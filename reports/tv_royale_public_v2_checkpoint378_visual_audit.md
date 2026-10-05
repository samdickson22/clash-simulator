# TV Royale public-state v2 checkpoint visual audit (378 games)

Date: 2026-08-14

This is an intermediate collector-health audit, not the final 1,000-game
acceptance artifact and not authorization to start PFSP.

The contact-sheet builder read 378 completed games from arenas 12 through 31.
The output directory retains its pre-run `checkpoint377` name because the live
collector accepted one additional replay between the status read and the
builder's manifest read. The manifest itself is authoritative:

- `reports/tv_royale_public_v2_checkpoint377_contact_sheets/manifest.json`
- SHA-256 `e2a9d63fdd226cea2b436b42e64c2ebc9cf64fc37ff8979a71595916fbd4cadc`
- 20 arenas, four collection-time quantiles, early and late frames: eight
  sheets and 160 visually reviewed replay frames

Reviewed sheet hashes:

| Sheet | SHA-256 |
| --- | --- |
| `q00_early.jpg` | `e70a9bed67719296ba99b0176141f4f12eefe0bb232f90705eecfc0fdc3e8f0c` |
| `q00_late.jpg` | `1944b98a5a0146942d450d2da4df6b04f833fa8d19a6334ed6a52f5c50002aa9` |
| `q01_early.jpg` | `731fd4a05db1e79561850c123d5c46d6bb9a03403731b86d6a3f633c61fdb633` |
| `q01_late.jpg` | `0bc57f42928f595866f7f661bf2221ebb47c9338e10f701fef7eb43bf546acc3` |
| `q02_early.jpg` | `131dd3575380d1236e61faa1103a6e95533403cc9e899e66b6ee166f33991172` |
| `q02_late.jpg` | `ae1ed443648bf4aa43dc53a776c12f3b8fa0d027c8133d49064802917d054939` |
| `q03_early.jpg` | `2c2646c284fae1bc17f966f583f73897a88535e542722bfc64bed95b9cfef306` |
| `q03_late.jpg` | `ad25f5426fdbc1b52519229d7772063e52b77ea311b44c71efcf31dc75bcb21a` |

Visual result: pass for continued collection. The arena crop and 18-by-32 grid
remain aligned across every arena theme and both temporal phases. Entity boxes
remain on battlefield objects; tower HP, elixir, hand, timer, and deployment
overlays are consistently located; no systematic vertical/horizontal drift or
UI-region contamination is visible. Sparse and crowded battles are both
represented.

The drawn rectangles are object-detector image boxes. They are not treated as
simulator collision or deployment footprints; in particular, a Crown Tower's
visual bounding box is not interpreted as a 4-by-3 gameplay hitbox.

At the same checkpoint the live manifest was balanced at 18--20 accepted games
per arena. The first 377 games contained 11,361 retained decisions: 7,866
detected play events and 3,495 sampled no-ops. All 26 failures belonged to the
already-corrected early `CorpusMetadata` schema mismatch; no recent extraction
failure was observed.

The finalizer must independently rebuild and visually audit all eight sheets at
exactly 1,000 completed games. This checkpoint cannot satisfy that gate.
