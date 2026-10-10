# E4-v3 response to T1 review round 2 (draft)

Candidate `aefc607a`, plus fleet-only GC/census sealing and typed-profile checks; source review:
`reports/explore/t1/REVIEW-T1-DELTA-REDUCER-20261010T1403Z.md`.
This response requests independent review and does not freeze or qualify inputs.

| Finding | Implemented response | Evidence |
|---|---|---|
| F1 host/priority admission | Fleet workers derive host, nice and scheduler from the pinned reporting plan. The separate nice19 smoke worker rejects fleet inputs. | Dynamic-host/priority tests; full fleet worker loop test |
| F2 reporting load | Reference slot plus **every** other normal/console reporting slot, all rotating the four complete own-tier corpora. No fleet perception worker. | 11/8-slot mask tests; each background tier consumes all 300 states; reporting/reference 1Hz MHz retained |
| F3 raw pooling | Medians over all raw hosts × repeats, geometric mean speed ratios, one-pass ±5% host exclusion, remaining raw observations repooled. Deadline numerators/counts and per-state distributions retained. | Raw-vs-host-median counterexample; host exclusion; missing/duplicate repeat failures; sealed complete CLI pooling and tamper rejection |
| F4 public rows | Exactly T1 ba3dc8b0's 20 fields and three stratum fields. Production requires pre-poll D1/history. Private suspended generators and `belief_resume` rejected. Schedule timestamps live in registration, with row tick binding. | Every missing field and extra hidden/resume/elixir/tick field rejected; stratum bins checked |
| F5 replay setup | Physical info/pending/posterior/D1 snapshot cloning happens before packet entry; `replay_setup_seconds` retained. D1 validation happens after elapsed wall is recorded. | Revised full Linux loaded calibration/smoke |
| F6 CPU S wrapper | Actual frozen `CachedPolicy(student, threshold)`; capture its existing forward tensors and format agreement diagnostics after the timer. | Revised full Linux loaded calibration/smoke; same source adapter on reference and measurement |

Every fleet host must pass native golden125 and belief/posterior/ledger/sample/RNG
125×ON/OFF before timing. Pooling rechecks those receipts, code/policy/native/spec
pins, corpus identity and complete raw cohorts; mismatches from an excluded host
also drop ALL tiers. Pooling records C6 local gate/near-tie exceptions with
>=99.5% joint agreement; logits alone need not be bit-identical. A sealed CLI
integration check proves conditional policy exceptions cannot hide common native
score drift. The fleet census stops before parsing/sealing, and parent-slot
GC events carry actual packet-entry deadlines. Capture-health counts and selected-state SHA inventory are
required pinned inputs, retained in host/Mac receipts.

Items still requiring scientific review: clearing suspended private preparation
in both deadline replays; the coordinator's reference-at-reporting-END placement
and its exclusion timeline versus PREREG §6.1; the explicit <=5% mean physical MHz
comparison gate. Linux smoke uses the historical golden batch and reduced counts;
it establishes implementation behavior, not fleet reporting or Mac feasibility.
The first receipt covers `deef4076`; the revised receipt identifies its own source
pins. No Mac or reporting host was accessed by this worker; 03 is vacated.

Revised Linux05 receipt: `receipts/linux05-20261010-r2/`; handoff SHA
`4e3db13a47a3d6a918662f75dc75af4d5c6cb6746f580592879d2f5ebecf372d`.
The full pipeline adapter from `aefc607a` was separately recalibrated under the
same 3-core light load and ran all measurement phases. EXACT native125 and
belief125×ON/OFF, CPU agreement32/32, ~20 FPS TRAIN perception and all four
smoke deadline/GC gates passed. Source hashes and conservative distributions
remain explicit; later fleet-only changes are unit/integration tested, not
executed on reporting hosts. 44 tests pass. Nothing is frozen by this receipt.
