# Five-tick native root-prefix collector

Implemented `scripts/collect_readiness_prefix.py` and `src/clasher/rl/readiness_prefix.py`. The CLI consumes a previously declared attempt from the readiness-v2 ownership ledger and the concrete native-config manifest. It does not create an attempt or start an emulator.

Before configuration, it verifies the declaration's source/input pins, root-bank and episode identities, config bytes and canonical hashes, gamedata, projectile catalog, generator and native attestation. The source freeze must include all Python files in `src/clasher` plus the collector and concrete native helper scripts. It archives those exact bytes and the declaration, then claims each episode before creating its episode directory or sending `configure`. Every episode receives the source archive. The ledger prevents retrying or redirecting an existing family claim.

Immediately after configuration, the collector enters `VerifiedNativeReadSession`. The session checks full attestation on entry and close and validates PID, process start time, manager, configuration and content identity on every read. It reads body levels afresh without caching body pointers or values. `native-read-session.json` is attached only after the context exits. A close verification failure turns an internally selected root into a failed capture under the original claim, so no successful receipt can precede closing verification.

After validating the native initial ordered decks, collection advances to native tick 90 and reads public observations every five ticks. Each recorded frame includes ordinary, rich and independently read visible-level data with strict projection checks for both seats. The two declared public prefix controllers act from the same pre-command boundary. After ordinary action selection, the collector applies the shared `apply_prefix_owner_reserve` helper. New v2 requests reserve eight elixir for the root owner during prefix exploration and use their declared 3600-tick window. Legacy requests retain reserve zero and their original window. Decisions record both the ordinary action and whether the reserve changed it. The helper does not change root candidate rankings, branch continuations or root eligibility. The balanced root controller selects the first root meeting the existing causal context and focal-candidate eligibility rule. The generator stops before submitting prefix actions at a selected root.

The CLI requests public contract v4. Native own-hand and next-card levels remain zero with zero confidence where the native adapter cannot observe them. A nominal level-11 configuration does not turn those unknown measurements into known values.

The collector retains both public packet sequences, native frames, observation ticks, decisions, submissions, accepted commands and transport rows. Each transport row stores exact submitted command strings, raw scheduler acknowledgements and before/after tick, epoch, hand and elixir snapshots. Failed scheduling or missing acceptance ends that prefix without a fallback action. Public history changes only after acceptance evidence. Initial and selected root frames permit deterministic prefix replay from the same config and accepted command schedule.

Missing or ineligible roots remain failures for their original requests. The CLI processes only the explicitly requested declared families, or all declared families by default. It does not substitute new roots. Failed post-claim captures enter the same append-only ownership ledger, including failures caused by source drift. All results explicitly set `game_complete=false`; no prefix is a full-game outcome or Tier A acceptance result.

A selected receipt binds the actual root tick, ordinary/rich/level frame hash, public packet hash, four candidate roles, config and original controller recommendation. The capture's evidence role comes from the immutable attempt declaration. There is no CLI option to relabel development work as fresh acceptance.

To execute after source freeze and an authorized reference startup:

```sh
.venv/bin/python scripts/collect_readiness_prefix.py \
  --registry /absolute/path/to/readiness-v2.sqlite \
  --attempt-id DECLARED_ATTEMPT \
  --manifest /absolute/path/to/native-configs/manifest.json \
  --catalog tests/fixtures/native_projectiles_15_535_86.csv \
  --catalog-sha256 DECLARED_CATALOG_SHA256 \
  --adb /absolute/path/to/adb \
  --output /absolute/path/to/new-prefix-batch
```

`--family-id` can select a bounded subset for a declared development run. Each selected family remains claim-once. This command was not executed against a native runtime in this implementation task.

Current validation in `session-reserve-tests.log` has 11 passing tests using offline native doubles. `tests.log` retains the earlier broader check. It covers claim ordering, causal stopping, five-tick cadence, missing/ineligible roots, rejected commands, source drift, replay evidence and transport snapshots. Concrete CLI tests use the real SQLite declaration/claim/capture API with fake native transport. They exercise selected and failed receipts, a failed session close after root selection, and prove that a second collection request cannot configure the same episode again. The short-window CLI fixture explicitly uses a legacy v1 bank without relaxing production v2 validation. Those tests exposed a read-only SQLite URI bug, which the ledger owner fixed. Targeted mypy and Ruff also pass. These tests do not establish live native transport acceptance, runtime performance or gameplay fidelity.
