# L1-v4 Phase A collection preregistration

This registration freezes the data acquisition population and technical gates. It does not register T7 model selection or L2 strength claims. `frozen-manifest.json` records UTC epoch, source hashes, configuration hashes, and this document's hash. That content manifest identifies this dirty checkout.

The question is whether the pinned offline renderer can deliver a portable 20 FPS corpus with scheduled execution boundaries and verified storage. The design's perception and strength thresholds remain unchanged. No model is trained by this job.

Phase A collects 24 hours of active emulator wall time, excluding setup, pauses, transfer and trailing paused cue windows. A deterministic list of up to 2,400 matches permits duration-based stopping despite early native terminals. It interleaves eight train, one validation and one heldout match. Each seed and unordered eight-card deck is unique across Phase A. The split is frozen in `split.json` before any Phase A frame or training. The three infrastructure smoke seeds are separate and excluded. The seed audit scans prior L1 and L2 manifests and schedules before admission.

The roster is P16 plus C56. Both seats use the existing C56 public scripts with balanced, pressure and defense styles rotated. Card selection favors the least-used card-side within each match. Thirty percent of placements are drawn from legal script actions for that card. Ten percent of turns schedule the two seats within 0.5 seconds. Ordinary paired commands have a 12-tick separation. Five percent of turns are explicit negative windows. Scripts target crowds and defend around buildings through their existing scores. Phase starts rotate through ticks 340, 1200, 2400, 3600, 4200, 4800 and 5200. Native terminal or tick 5980 ends capture, with 700 ms of trailing frames. Champion ability coverage is recorded separately and must be reported if absent.

The sole acquisition arm uses the attested private renderer, host GPU backend, one owned 3 GiB/two-core emulator and dedicated adb server 5042. All host workers run at nice 10 with one encoder thread. Another project's VM and Stage 6 jobs remain running. Collection does not claim a quiet-host latency benchmark. No official client or game network is used. IPv4 and IPv6 UID REJECT rules, serial, PID, read-only AVD, backend and attestation are checked before and after each match.

Primary technical endpoints are the share of complete matches at nominal 20 FPS, exact execution ticks for all accepted plays, and hub verification for every admitted match. Nominal 20 FPS permits a 1% timestamp sampling tolerance, meaning at least 19.8 measured FPS per match. At least 95% of Phase A matches must pass; all three smoke matches must pass. Execution labels require a succeeded schedule receipt with `queuedAtTick == executeTick - 1`, followed by hand/cost corroboration. Enqueue acknowledgements alone never count. Screenshot timing brackets remain empirical, not a compositor guarantee. Rejected commands are retained as negatives. Rates, gaps, native versus wall seconds, per-card-side counts, heldout matches and opponent-event coverage are descriptive completeness checks. Heldout must include at least 20 matches and 1,500 opponent events; failing coverage does not authorize outcome-based recollection or a new split.

Only infrastructure failures may trigger a rerun with the same seed. Preserve incomplete attempts under the capped buffer and log the incident in T1-PROGRESS.md. No completed receipt is overwritten. There is no outcome-based stopping, heldout adaptation or tuning after Phase A begins. Phase B requires the coordinator's later decision. The maximum hub footprint is 40 GB. Collection pauses if a completed transfer cannot be verified, if the Mac buffer including retained labels approaches 6,000,000,000 bytes, or if free disk approaches 15 GiB. Each new match reserves 400 MiB; encoding keeps the same 400 MiB reserve every second. Before finalization, the collector checks a conservative byte bound for the complete remaining object rewrite, rich labels, frames, HUD and receipt.

Completed matches go only to `127x02:/mpac/sdicks02/repos/clasher-v4-data`. The hub recomputes every SHA256 before finalizing the directory. Local deletion follows an exact hash acknowledgement and local immutability check. Receipts, compact labels and transfer manifests remain local. Native truth files supply training/evaluation labels only. The actuator imports no native truth module.

Before Phase A, three smoke matches must pass the endpoints, the v3 converter must round-trip a sample's selected frame labels and all deployment labels, and negative checksum/storage tests must pass. Results report all gates, accepted/rejected counts, bytes, elapsed emulator hours, coverage and deviations. A running phase is reported as running, never complete. Resume commands and owned process IDs are written to T1-PROGRESS.md.

The pinned ordinary observation does not expose validated deployment-state or sprite-visibility flags. The collector samples coherent rich object metadata when new bodies appear, at most once per native second. Body names join by native object ID and the frozen native data catalog, so children do not inherit their summoner's class. Missing identities remain null with a separate card-derived hint. Deployment and visibility flags are populated only from a rich snapshot at the same tick; otherwise they remain null with explicit provenance. No exact sprite visibility, body boxes or compositor fence is claimed. Champion abilities use a coherent rich observation, a named available ability, the scheduled boundary, and cooldown/charge plus elixir corroboration. The immutable ordinary and rich receipts remain evaluator-only evidence.

Pre-smoke source amendment, 2026-10-07: the persistent input channel is now a separate pixel-only module. The evaluator keeps a thin ownership adapter. RPC serialization and tap coordinates are unchanged. No collection frame or Phase A match existed at this amendment. The earlier source registration remains immutable on the hub; the replacement source manifest is frozen and verified before smoke.

Pre-smoke source amendment, 2026-10-07: the v3 converter also accepts a directory of finalized matches and commits a combined v3 manifest after all conversions. A two-match codec/label round-trip test passed. Collection, splits, timing thresholds and stopping rules are unchanged. No smoke or Phase A frame existed at this amendment.

Pre-smoke label audit, 2026-10-07: `command_tick` is taken from the probe's `registeredAtTick`, not the earlier observation used by the script. `before_tick` separately anchors the affordability/regeneration corroboration. Accepted events must agree with the final schedule receipt's registration tick. This correction precedes every collected match.

Pre-smoke schedule audit, 2026-10-07: both side choices are computed before a shared scheduling anchor. A forced pair uses adjacent execution ticks, independent of script computation time, and waits until both sides have an affordable legal action. Ordinary paired turns retain a twelve-tick separation. No collection match preceded this audit.

Pre-smoke actuator unit audit, 2026-10-07: a cost-one play must still show a positive elixir drop. The cost ±1 tolerance does not make a zero-spend slot change an acceptance. A regression test covers this boundary. This actuator change does not affect collector inputs or labels; the complete source bundle is resealed before smoke.

Pre-smoke terminal audit, 2026-10-07: commands still pending when the native match ends are recorded as negative examples with null `exec_tick` and an explicit terminal reason. They are not lost plays or infrastructure failures. Accepted commands must have reached their receipt's execution tick. A regression test ends a native-shaped fixture with both seats' commands pending and verifies two retained negatives and an atomic match receipt.


## Pre-smoke amendment, 2026-10-07: hub recovery, timing and coverage

Before any smoke or Phase A match, adopt the coordinator decision in
`../../amendments/2026-10-07-t2-actuation-timing.md` (including its addendum).
The destination is now `127x01:/mpac/sdicks02/repos/clasher-v4-data/matches/`.
This is an operational destination change; acquisition labels and match schema are unchanged.
Old registration bundles on 127x02 are unreachable. Re-register the preserved producer
sources and the new content manifest under the new hub's `registration/` directory.
Do not write to the hub's recovered source checkout.

Phase A now stops when the frozen heldout split contains at least 1,500 accepted
opponent events AND at least 20 matches, or at the 36 active emulator-hour cap.
Only receipt counts are inspected; no label content, model output, or outcome enters
the stopping rule. The frozen seed/deck memberships and 80/10/10 split are unchanged
(split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258).
The collector reserves its existing 380-second maximum match duration before starting
another complete match, so it may stop at the cap up to 380 seconds early rather than
exceed 36 hours. Coverage shortfall is reported; it does not authorize more collection.
Historical split metadata still says 24 hours and 127x02; `collection-config.json`
is the prospective operational override, avoiding a change to split identity.

Phase A requires a readable JSON `127x01:/mpac/sdicks02/jobs/clasher/hub-ready.json`
and at least one checksum-verified smoke match on 127x01, in addition to all existing
three-smoke admission gates. The 15 GiB disk floor and 6 GB buffer cap are unchanged.

Source deviation before smoke: the prior collector hard-coded its hub and duration,
so minimal source edits were necessary to load the operational config, enforce the
count/cap stop, and check hub readiness. The backend-relative actuator timing change
also changes a hashed source file. Therefore archive the prior freeze locally and
refreeze before smoke. No APK, hook, command age, attestation, collector label schema,
threshold or frozen population is changed. T2 failure does not block T1's independent
scheduled-receipt collector; it continues to block production actuator qualification.


## Pre-Phase-A infrastructure amendment, 2026-10-07 23:51Z

The first smoke attempt shipped `v4-smoke-0` (19.994 FPS, 21 exact-tick plays)
to 127x01, then smoke seed 1975100001 failed at tick 2630 with `unsupported visible
body identity`. Ordinary native objects keep the parent spell card ID: the spawned
Barbarian was projected as BarbLog. This is an adapter failure, not a match outcome.
The collector-only repair maps a spell with exactly one hitpoint-bearing payload
to that payload's existing C56 body stats (BarbLog→Barbarian, GoblinBarrel→Goblin,
RoyalDelivery→DeliveryRecruit). Unknown/ambiguous payloads still fail. No common
engine, APK, hook, player, label schema, data thresholds or split membership changes.

Preserve the successful old match on the hub and archive its local receipt and
converter check under `data/smoke-attempts/pre-body-repair-20261007/`. Preserve the
incomplete second match in the capped buffer. Archive the old source manifest and
refreeze before rerunning all three original smoke seeds with `-bodyrepair1`
attempt IDs. This ensures admission uses one producer freeze and overwrites no
completed receipt. Phase A has collected no matches and remains gated on all three
new smoke passes plus hub-ready.json. The coordinator's 23:50:59Z whole-repo
checksum window has ended; this source repair is later than that hub source snapshot.
Only the new producer registration bundle is sent to v4-data, never a hub source resync.
