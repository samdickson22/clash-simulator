# Readiness development execution workflow

This adds a separate five-tick runner. No emulator was started, no native request was sent, and no actual game was run while implementing it. The tests include a synthetic six-tick scalar executor with native I/O forbidden. Fresh acceptance execution remains blocked.

## Implemented and checked

`src/clasher/rl/readiness_execution.py` pins capture/config/root-frame/catalog/source identities, enumerates condition × candidate × engine jobs, and holds repetition identity constant across repeat indices. It rejects undeclared subsets for coverage. `scripts/run_readiness_v2.py` provides `prepare`, `execute`, and `summarize-repetitions`.

Preparation reconstructs the candidate source from archived ordinary/rich/visible-level frames, rechecks public projection, preserves original controller recommendations, and records every root-generation failure. Execution rebuilds the same initial state and recorded prefix, applies the declared candidate at the root, and lets both styles react to their own branch observations every five ticks. Root-owner-relative style mapping works for both seats. The scalar root must retain the candidate's hand-slot/card identity; the native root must additionally reproduce the captured state and projected public packet. Illegal/rejected actions stop the run. Native scheduling receipts, one-tick command execution, elixir spending, terminal finalization and runtime attestations are checked. Partial outputs and failed claims remain on disk; outputs are never overwritten or automatically retried.

Identical-repetition studies can declare a small condition/candidate subset. The bounded example below is one root, one condition, one candidate, and two repetitions. Scalar-only produces two games; both engines produce four. This is a finite reproducibility check, not the full tactical coverage study.

Validation: 37 focused tests passed; Ruff passed; `readiness_execution.py` passed targeted mypy. Offline preparation succeeded against an actual existing development capture. The first preparation's JSON level-key conversion failure remains in `offline-preparation-check/`; its repair was validated in `offline-preparation-check-v2/`. Earlier prepared plans have stale source pins and are retained. The current runnable scalar plan is `scalar-repetition-plan-v2/execution-plan.json`.

## Execute the prepared scalar check

From `/Users/sam/Desktop/code/clasher`:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/run_readiness_v2.py execute \
  --plan reports/strategy_council_20260928/m0/readiness/scalar-repetition-plan-v2/execution-plan.json \
  --output reports/strategy_council_20260928/m0/readiness/scalar-repetition-run-v2 \
  --native-lock /tmp/clasher-readiness-v2.lock \
  --max-wall-seconds 600
```

The plan's source/input pins were verified after preparation. Any subsequent source change causes execution to fail closed. Re-prepare into a new directory after source changes; never alter the old plan:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/run_readiness_v2.py prepare \
  --roots reports/strategy_council_20260928/m0/readiness/opened-development-root-requests.json \
  --catalog /Users/sam/.cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv \
  --catalog-sha256 c59ef74273b721b861e6a499bc8869a6fc29ad07919884b79ebe859455d6eac5 \
  --attempt-id opened-root90-scalar-repetition-next \
  --purpose identical_repetition --repetitions 2 \
  --repetition-conditions balanced/pressure --repetition-roles immediate_play \
  --engines scalar \
  --output reports/strategy_council_20260928/m0/readiness/scalar-repetition-plan-next
```

The root request names this existing successful, explicitly development-role capture:

`artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_development_20260915/expanded-deck-development/forward-0`

It uses owner 0 at tick 90. Its two supported decks cover the original sixteen-card vocabulary. Its config, ruleset, initial state, accepted prefix, and recorded ordinary/rich/level frame are pinned. This does not reopen or relabel a v7 acceptance capture.

## Native counterpart, when the coordinator starts it

The runner requires an already available, paused, ready reference process and an explicit ADB path. It never boots, kills, installs, pauses or restarts the emulator. The lock is cooperative among readiness runners; the coordinator must also ensure no legacy collector is using the same reference. If the lock is occupied, execution fails immediately.

The saved emulator launch parameters are in `/Users/sam/.cache/clasher-native-reference/avd/clasher_reference_api35.avd/emu-launch-params.txt`: AVD `clasher_reference_api35`, port 5580, headless, no audio/snapshot/boot animation, SwiftShader, 3072 MB and two cores. SDK executables are under `/Users/sam/.cache/clasher-native-reference/android-sdk/`; the AVD directory is `/Users/sam/.cache/clasher-native-reference/avd`. The cached patched manifest declares launcher component `nullsroyale.rel.free/com.supercell.clashroyale.GameApp`. This is startup information read from disk, not a claim that the emulator or process is currently running.

After startup, forward the existing guest probe port using that SDK's ADB:

```sh
/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb \
  -s emulator-5580 forward tcp:26789 tcp:26789
```

Use `scripts/query_reference_probe.py --port 26789 --command status --output <new-status-file>` and the analogous `--command attest` query to capture readiness and attestation before preparation. Readiness must report `paused=true, ready=true`. The pinned historical attestation is:

`artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_acceptance_20260922_v7/native-attestation.json`

Its canonical JSON SHA-256 is `864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93`. This identifies the runtime only; using its hash does not reuse acceptance outcomes. The new run must match it live. `read_native_public_levels.py` independently verifies the expected libg/probe/content fingerprints.

Prepare the same study with `--engines scalar,reference`, `--native-attestation-sha256 864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93`, and a new attempt/output directory. Execute with the same arguments as the scalar command plus:

```sh
--adb /Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb \
--serial emulator-5580 --port 26789 --max-wall-seconds 7200
```

The 2-hour cap is a planning limit, not a throughput measurement. Each root-90 branch has at most 1,183 decision boundaries before terminal finalization. The existing capture stores 118 frames in 11.2 MB compressed; linear scaling suggests about 225 MB for two full-length native branches. Allow 1 GiB of free scratch for this four-game check. Scalar-only receipts omit native frame payloads and are much smaller. Actual native runtime and disk cost remain unmeasured on this runner; inspect the first run before a larger study.

Once a both-engine run completes, `summarize-repetitions` verifies claims and artifact hashes, recomputes the maximum within-identical-execution score/normalized-margin differences, and builds `MeasurementFloors`. Supply separately justified `--score-rounding-allowance`, `--margin-rounding-allowance`, and `--rounding-basis`; the runner does not invent these allowances. WDL spacing and scalar/reference disagreement are never used as measurement noise. Scalar-only output cannot establish the required both-engine floor.

## Contract and acceptance gaps

The reference builder enables visible body levels but currently omits own hand/next-card level arrays and confidence. Its packet wrapper reports schema 4; that number alone does not establish the extended actor contract. Runner receipts explicitly report `legacy_public_projection_valid=true` and `public_contract_valid=false` when those level channels are absent. They still provide genuine terminal repetition measurements, but emit `branch-ineligible.json` instead of an acceptance-compatible `Branch`. No own-card telemetry is inferred from the nominal level-11 configuration.

Fresh execution requires the future v2 capture/exposure ownership adapter and is deliberately rejected. The separate root-bank module supplies 32 prospective independent episode requests; existing archived 30-tick captures do not satisfy its five-tick causal root scan. Real root selection requires those declared episodes/capture frames, honest missing-root accounting, verified config-family binding, the extended public contract, stable source/config pins, and completed repetition/coverage evidence before freeze. The ordinary four-role coverage path always enumerates all four style conditions and both configured engines; the bounded noise subset is not a substitute.

Historical v7 runners, criteria, ledgers and source/evidence files remain unchanged by this work.

## Coordinator's completed scalar run

After the runner source stabilized, the coordinator executed the prepared two-game scalar study. `scalar-repetition-run-v2/complete.json` records successful completion. Both result files and their receipt hashes were inspected: each produced owner score 0, own remaining Crown HP 7,270, enemy remaining Crown HP 8,358, and winner 1. Both use the same execution SHA-256. Observed score and normalized-margin repeat differences are zero. Both report legal transport valid and the full public contract invalid, so their branch-ineligible receipts remain binding.

`scalar-study-observation.json` records the observed differences and result hashes. This is scalar-only development evidence. No reference repetition, both-engine noise floor, full public-contract certification, fresh acceptance result or training authorization follows from it. The native counterpart has not been started by this subtask.
