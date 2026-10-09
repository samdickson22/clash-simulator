# Owner review of the live SelectionClaims handoff

2026-10-09 02:16Z. Read-only review of the attached source pins. This is an API/evidence-contract review, not formal selection, decoder admission or Mac qualification. Live wrapper implementation remains with the coordinator's live-runtime worker. No worker source or pending Amendment12 orchestration package was edited.

## Verdict

The typed handoff is compatible with the intended final joint seal **with the requirements below**. The `selection_sha256` may bind the entire joint proof graph; the claims do not need to flatten every T6 proof, population, body-stage seal, dominance certificate, calibration input or amendment hash. `final_joint=True` is only the trusted verifier's result, never evidence by itself. No real final joint seal or trusted production callback exists yet, so formal startup must continue to refuse.

| Claim | Owner meaning |
|---|---|
| `final_joint` | Actual independently authenticated final T6+T7 seal, including completed validation-only calibration and all frozen followups; not a T7-only receipt or closure flag. |
| `checkpoint_sha256` | Exact bytes of the selected T7 checkpoint named by that joint seal. T6 control proof is bound by the joint seal, not substituted as the live checkpoint. |
| `cards`, `bodies` | Exact ordered checkpoint vocabularies, checked again against loaded checkpoint bytes. |
| `spells` | Fixed model/card-data routing under the sealed game-data source, not a tunable list. Must be a unique subset of `cards`. |
| `body_threshold` | The selected epoch's sealed body threshold, from the clock-free body-stage seal; finite numeric registered grid, no bool/default/config override. |
| `event_thresholds` | Complete measured-validation threshold configuration, including explicit `default` and admitted per-card overrides. |
| `calibration` | Exact immutable measured-validation isotonic/fallback configuration from the combined replay and declared minimum-support policy. |
| `selection_sha256` | Exact-byte SHA of the final joint seal supplied to the verifier. |
| `source_hashes` | Concrete resolved source/evidence paths and exact hashes that bind the actually loaded runtime and every selected adapter, plus the proof sources required by the verifier. |
| `decoder_admitted` | An admission result only for the exact decoder implementation/source set and execution-platform scope being launched; never a generic permission bit. |

## Required before formal startup

1. **No implicit event-threshold default.** `authenticate_selection` currently checks only that `event_thresholds` is a dict. `{}` passes that shape check, while `EventFusion` uses `thresholds.get('default', .5)` when a card has no override. Require explicit `default`, all values finite/non-bool on0.1..0.9, and keys contained in the exact card vocabulary plus `default`. Use the same semantics as frozen `threshold_options`, without importing a mutable ad-hoc source. The owner callback will also recompute threshold selection and exact-map equality against the final seal. Add tests for missing default, unknown card, bool/NaN and off-grid overrides.

2. **Bind decoder identity and platform scope.** The boolean and an arbitrary nonempty `source_hashes` dict do not themselves say which adapter was admitted. Either extend normalized claims/provenance with a typed decoder binding (implementation ID, actual source hashes, admission proof SHA, admitted device/backend scope), or make an equivalent immutable binding mandatory in the owner verifier and wrapper's startup checks. For the vectorized path the actual loaded `l1_v4.py`, `decoder_records_v4.py`, `vectorized_decoder_v4.py`, `vectorized_runtime_adapter_v4.py` and loading/adapter shim must match that binding. Admission on CPU/CUDA does not imply MPS parity or the Mac E4 gate. Current vectorized/lockstep candidates remain unadmitted. The default remains false.

3. **Pin trust outside the seal.** Recording the callback's source SHA after invocation is useful provenance; it does not authenticate that the callback was independently trusted. The deployment/launcher must pin the expected owner verifier module/function and its complete import/source closure before invocation. The seal, config JSON or calibration must not nominate their own verifier or modify this trust policy. The explicit CLI hook is acceptable as an operator trust choice only under that separately pinned deployment policy. This is not a request for a built-in permissive seal reader.

4. **Validate routing/calibration structure.** Check `spells` is a subset of cards and exactly matches sealed public card metadata. Calibration keys must be known cards/default; knots must have the runtime's supported pair shape, finite [0,1] values and correct monotone ordering. An empty calibration is not universally forbidden: its legitimacy depends on the frozen measured-support/fallback policy and must be independently justified by the owner verifier. Do not let malformed or absent selected calibration silently become raw-score operation. Preserve exact selected values rather than normalizing/re-fitting them in the wrapper.

5. **Keep runtime and raw-evaluation scopes distinct.** The current top-level CLI/runtime correctly restrict `decoder_diagnostic` to the mock actuator, and this review does not claim a real-tap bypass. Still, direct `V4Perception` construction permits the diagnostic branch and labels it `authenticated-final-joint`; ensure reports retain an explicit unadmitted-diagnostic label, not formal decoder qualification. Public tower reconciliation and geometry/template artifacts are separate live behavior and need their own artifact/config provenance. They must not silently change the frozen raw L1 evaluation output or be represented as a selected detector improvement.

## Owner verifier responsibilities

The final callback will return claims only after independently authenticating the frozen registration and Amendment12, shared producer/train/validation population, both formal fit/checkpoint identities, the already-verified unchanged T6 control evidence, full T7 body seal and all bound bindings, the suspension-free measured-dominance certificate and controlled-host replay provenance, all nine selected-epoch event cells, measured per-card/combined calibration and fixed-finalist replication. A model-selection seal does not establish Mac latency, overall L2 entry or other unmeasured gates. All referenced evidence and actual deployment source bindings must agree with the final joint seal's exact bytes.

The current `joint_selection_evidence_v4.py` still calls the pre-Amendment12 T7 capture selector and reruns T6; it is **not** this future live verifier. It must not be wired to the CLI as a shortcut. The owner will supply a new reviewed callback after the corrected evidence chain is complete. Until then: unset authenticator or non-final evidence means refusal.

## Validation scope

Read-only code review. Existing worker tests were inspected, not rerun here; no GPU, Mac, model, real selection or heldout access. The requested additional tests and live wrapper fixes belong to the live-runtime worker. The pending orchestration-review package and frozen draft/pins are unchanged.
