# Native public v4 serialization

`public_reference_builder(..., public_contract_version=4)` now enables the five own-card level fields. Its default remains v3 for historical callers. The native adapter writes unmeasured hand/next-card levels as int64 zero and their confidence as float32 zero. Existing body-label evidence remains frame-bound and reaches the entity-level channels. `native_public_level_coverage(builder, public)` reports observed versus visible body, tower, hand and next-card counts separately from schema validity.

Unknown values are valid v4 inputs. The recorded Mirror fixture produces a structurally valid v4 archive and model input with 4/4 measured troop-body levels, 0/6 measured tower levels, 0/4 measured own-hand levels and 0/1 measured next-card level. Its public mask still permits legal plays. This fixture's tower levels are unknown because its evidence did not claim them; the general body reader supports Crown Tower body readings when they are included.

Existing evidence does not establish an own-hand/next-card level reader:

- `scripts/read_native_public_levels.py` reads native object-vector bodies with validated HP-component layouts and backlinks, then reads the body level field and keys the result by native object ID. It does not read own hand or visible-next levels.
- `NativePublicLevelEvidence` accepts only native body-ID level/confidence mappings tied to snapshot tick, generation and state epoch.
- `tests/fixtures/native_public_mirror_levels_15_535_86.json` records hand entries with `cardId`, `cardParameter`, `commandCardId`, `cost`, `deckSlot` and `handIndex`. Its visible-next entry contains `cardId` and `deckSlot`. Neither entry has a declared level reading. No interpretation of `cardParameter` as a level is established by these sources.

Consequently this change does not infer level 11 from the nominal scope, infer levels from HP, reinterpret opaque fields, or trust newly injected HUD `level` keys. An observed own-card level claim still needs a declared, calibrated source bound to the correct owner, frame and visible card slots. That missing calibration is reported as an evidence limitation, not a malformed-packet error.

Validation: `python -m pytest -q tests/test_native_public_v4.py tests/test_native_public_levels.py tests/test_native_public_observation.py tests/test_public_reference_checks.py` completed with **83 passed in 1.93s**, including four new tests. The new cases cover both perspectives, v6 archive/model round trips, honest unknowns, body confidence below one, legal-mask behavior and legacy builder compatibility. Focused diff check passed.

No native calls, emulator work, native reader/probe edits, fitting or reference collection occurred. The readiness owner is separately wiring v4 opt-in and separating structural validity from measured-channel coverage in the new runner.
