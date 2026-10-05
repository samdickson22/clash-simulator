# Compact native frame storage

Implemented `native_frame_storage.compact_native_frame()` and its validator. All **1,406 native frames** from the two completed v6 reference repetitions passed an offline full-versus-compact replay. Both seats' packet hashes matched the archived hashes, giving 2,812 matching owner packets per format. Legal masks, calibration checks and coverage, recorded action legality and command-transport inputs also matched. Source and input pins stayed unchanged during the 114-second audit.

The two compressed decision streams shrank from **159.75 MB to 11.47 MB**, a **92.8% reduction**. Their expanded JSON shrank from 8.89 GB to 90.54 MB. The audit streamed gzip; it did not create expanded source files or alter historical evidence.

| Scope | Original compressed | Compact compressed |
| --- | ---: | ---: |
| Reference repetition 0, 703 frames | 79.85 MB | 5.73 MB |
| Reference repetition 1, 703 frames | 79.90 MB | 5.74 MB |
| 512 branches using the larger observed branch, plus one full last-decision snapshot each | 40.99 GB | 3.02 GB |

The 3.02 GB estimate leaves substantial room within roughly 37 GB free space. It excludes prefix captures, command-transport journals, source archives, checkpoints and unrelated files. These two repetitions cover one opened root and continuation, so the estimate is not a worst-case bound for other games. Each retained full last-decision snapshot is about 160 KB compressed. It is explicitly not labelled terminal because the final decision precedes match finalization.

## Retained data and omitted traces

The implementation keeps every ordinary observation and level-source field unchanged. It also retains every rich object, player, capability, provenance field, unknown field and trace-envelope metadata field. Only the `events` lists inside seven named global cumulative streams become `null`: combat, phase, special movement, action movement, character state, visibility and remaining-runtime telemetry. Per-object runtime fields remain intact.

`null` means not stored, not an empty history. The storage envelope records each omitted list's original count, serialized size and SHA-256. It also records the full parsed-frame SHA-256/size, a checksum of the retained frame, the producer source hash and the digest encodings. Native completeness flags describe the original source; the storage envelope explicitly marks the omitted payload as unrecoverable from the record.

These commitments hash the full parsed JSON payload and omitted event arrays. They are not hashes of original socket bytes, which the existing request API does not expose. Hashes preserve commitments, not a backup of omitted diagnostics. Full cumulative-trace analysis requires a separately retained full snapshot or source capture.

## Consumer audit

| Consumer | Required data | Preservation |
| --- | --- | --- |
| `native_public_observation.join_rich_snapshot/project` | Rich schema/epoch/coverage metadata and full object records | Unchanged |
| `public_reference_checks.check_reference_entities` | Ordinary state, rich object IDs/data IDs and level evidence | Unchanged |
| `native_public_calibration.audit_native_frame` | Ordinary/rich objects, level source, public serialization, masks and coordinates | All 1,406 frames passed both formats |
| `readiness_transport` and `native_command_checks` | Ordinary tick/epoch, hands, resources and action/receipt records | Inputs unchanged; positive and negative transport fixtures retain the same outcome |
| `run_readiness_v2.public_views` and prefix projection | The same projection and calibration fields | Storage validator integrated; public packets unchanged |
| Public projection/boundary audit scripts, route inspection and timed-defense inspection | Rich object records and required headers | All retained |
| Global cumulative-event analyzers | The omitted event arrays | Unsupported by compact records; arrays are explicitly unknown rather than empty |

The calibration owner integrated storage validation and source pinning. Readiness and prefix owners integrated compaction at persistence boundaries. Readiness admission replay also binds the recorded compactor source hash to producer provenance. Native observation requests and five-tick decisions remain unchanged.

## Verification and provenance

Focused storage/calibration tests: **25 passed**, including ownership of copies, unknown fields, JSON round trips, malformed metadata, payload corruption and transport pass/fail preservation.

Reproduce the complete offline audit with:

```sh
.venv/bin/python scripts/verify_native_frame_compaction.py \
  --run-directory reports/strategy_council_20260928/m0/readiness/paired-repetition-run-v6 \
  --output /tmp/native-frame-compaction-audit-new
```

The durable [receipt](receipt.json) binds both original streams, their original results/configuration/data, all compact derivatives, the ordered full-frame commitments and 125 audit source files. `audit-source.zip` preserves those exact source bytes. Each job folder contains its compact decision stream and one full last-decision snapshot.

This is a storage-equivalence receipt, not a new calibration or admission receipt. V6 did not retain independent command-acceptance journals; this audit proves unchanged transport inputs and fixture behavior, not fresh execution acceptance. There were no native calls, probe/API changes, gameplay fitting or bandwidth measurements. The full rich response is still acquired from the native endpoint.
