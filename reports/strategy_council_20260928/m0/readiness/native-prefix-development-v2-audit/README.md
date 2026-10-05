# Independent audit: native prefix captures, `m0-native-prefix-development-v2`

Scope: all 32 declared development families. The audit reads the recorded evidence
under `native-prefix-development-v2{,-remaining,-tail}/`, the ownership ledger
`readiness-v2.sqlite` (opened `mode=ro`), and the immutable runtime
`m0/runtime-snapshots/native-development-v1/`. It never calls adb or the emulator,
never writes the ledger, and writes only `results.json` in this directory.

## Reproduce

```
SNAP=reports/strategy_council_20260928/m0/runtime-snapshots/native-development-v1
CLASHER_ROOT=$SNAP PYTHONPATH=$SNAP/src:$SNAP/scripts $SNAP/.venv/bin/python -B \
  reports/strategy_council_20260928/m0/readiness/native-prefix-development-v2-audit/audit.py --negative-probes
```

This takes about 30 s for the audit plus about 60 s for the probes.

## What is recomputed

The audit recomputes each check from the raw evidence. It does not trust the
collector's summary flags.

- **Global:** the ledger attempt record equals `declaration.json`, and the ledger
  design SHA equals the recomputed declaration SHA. All 350 source pins and 38
  input pins in the snapshot are still intact. The audit also checks the manifest
  SHA, the canonical and file SHAs of the root bank, and the generator and catalog
  SHAs. The root bank is **regenerated from master seed 260928903** and matches
  exactly. The ledger has no seal, branch, exposure or admission rows.
- **Identity:** the ledger claim nonce and output path match `capture-receipt.json`
  (nonce, design, family, config and attestation). The ledger `captures` record is
  byte-equivalent to the receipt on disk. Rows in `batch-result.json` agree.
- **Artifacts:** the set of files equals the receipt's `artifact_hashes`, with no
  extra or missing files, and every SHA matches. The capture-binding input hashes,
  `root-frame.json` (identical to the last stored frame), `root_frame_sha256` and
  `root_sha256` are all recomputed.
- **Config and root request:** the canonical `plan.config` equals the declared config
  SHA and the declared config file, whose file SHA is also checked.
  `plan.root_request` equals the bank request and its declared SHA. The declared
  values are reserve 8, stop tick 3600, cadence 5 and start tick 90. The native
  initial decks match the manifest's ordered native card ids.
- **Cadence:** frame ticks, `packet-ticks.json` and `result.packet_ticks` are all
  equal to `range(90, root_tick+5, 5)`. Every compact-frame storage envelope
  validates, using the snapshot `native_frame_storage.py` SHA. No frame has ended
  or been finalized.
- **Session:** `native-read-session.json` has status `verified` and no failures.
  The expected, start and end attestations all equal the declared attestation.
  `reads_completed` equals the frame count. Every frame carries the same
  `session_id` and runtime identity, with `read_index` running 1..N in order.
- **Re-projection:** every stored frame is re-projected to both seats with the
  snapshot adapter, using own-play history rebuilt from the accepted-command log.
  All 5,452 recorded decision packet hashes match. Both `seat{0,1}-public.npz`
  archives are array-identical to the re-projected sequences.
- **Controllers and reserve:** the prefix controllers are replayed and every
  `ordinary_action` matches. The reserve rule is recomputed independently of
  `apply_prefix_owner_reserve`. For the root owner, the action is a wait whenever
  public elixir is below 8 or its confidence is 0; otherwise it is the ordinary
  action. The other seat always takes its ordinary action. The root owner never
  played a card with native `elixirRaw` below 8. All actions are legal under the
  public mask.
- **First-eligible selection:** an explicit per-tick scan uses `context_matches`,
  `generate_candidates` and a focal-token check. The first eligible tick equals the
  recorded root tick, and no earlier eligible tick exists. The snapshot's
  `select_root`, replayed on the re-projected packets, gives the same result as
  the recorded `RootSelection`: status, tick, packet, candidates, original
  recommendation and observed-packet count.
- **Transport:** each transport row's `before` equals the stored frame, and
  `validate_command_step` passes. Each action is decoded to a slot and position,
  and the native card id is checked against the HUD hand and the public token.
  From those, the audit rebuilds the submitted command string, the selected list,
  the commands and the receipts. Acceptance is recomputed from the transport
  before/after `elixirRaw` values. The rebuilt accepted-command records equal
  `accepted-commands.jsonl` and `result.commands`. Schedule sequences strictly
  increase, and each played card has left its hand slot.
- **Completion flags:** `game_complete` is false in the plan, result, receipt and
  batch results.
- **Producer source:** every `producer-source.zip` contains exactly the 350 pinned
  paths, all with matching SHAs, plus an `attempt-declaration.json` equal to
  `declaration.json`. Each episode copy equals its batch zip.

**Negative probes** (`--negative-probes`) apply 11 in-memory tampers each to
families 00 and 16: a dropped middle frame, a dropped root frame, a reserve
violation, an altered packet hash, an altered controller action, a removed accepted
command, a removed submission, an altered transport command, a selection moved
later, an unverified session, and `game_complete` set to true. All 22 are detected
by the semantic checks, not only by file hashes.

## Result

| Status | Families |
|---|---|
| selected, all checks pass (31) | 00–14, 16–31 |
| failed, correctly recorded as interrupted/incomplete (1) | 15 (`remaining/episode-11`, nonce `23c155ec…`) |
| no_eligible_root | none |

The audit found 0 discrepancies, and all global checks pass. Root ticks range from
95 to 1805 (median 380). Selected root owners split 15 to seat 0 and 16 to seat 1.
Every focal card has two selected roots except IceGolem, which has one because
family 15 (IceGolem, bridge_contact) was interrupted.

Family 15 is recorded as `failed` in the ledger and receipt, with prefix_complete
false, no selected family and no binding. It has no result, session receipt,
decisions or root frame. Its frames gzip is truncated after 124 decodable frames
(ticks 90–705, contiguous), and its transport gzip is truncated too. The
reconciliation receipt and `collector-failure.json` agree on the failure. It is not
listed as selected in any `batch-result.json`, and it was not retried.

## Notes, not failures

- The `-remaining` batch's `batch-result.json` requested 28 families but contains
  only 11 rows. The collector was interrupted during family 15, and families 16–31
  were later claimed under the separate `-tail` batch.
- The three batch `producer-source.zip` files have different SHAs (`e8374f5a`,
  `13d97f22`, `859852e3`) because of zip timestamps. All three contain identical
  pinned source bytes.
- Importing the snapshot's `clasher.battle` makes numba `njit(cache=True)`
  create or touch an empty `src/clasher/__pycache__/` directory in the snapshot,
  even with `-B`. The collector does the same. The directory is unpinned, and all
  source pins still verify.
- This is development-role evidence (`opened_development`). It shows that the
  generator is feasible under the declared rules. It is not fresh acceptance
  evidence or admission evidence.
