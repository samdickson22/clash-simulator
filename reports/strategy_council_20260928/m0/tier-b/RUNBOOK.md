# Tier B runbook: learned-policy transfer check

Tier B runs after the pilot. It must run before continuing past the pilot and before any promotion (strategy.md, "Tier B: learned-policy transfer"). It uses the Tier A machinery for regret, measurement floors and automatic bias. The roots come from games played by the frozen candidate, and the frozen policy ranks the four candidate roles: immediate play, wait, alternate card and displaced placement. The Tier A native and scalar scripted controllers stay as the reacting continuations.

Tier B runs as two separate attempts that are reported separately:

| Block | Roots | Pass rule | Population reading |
|---|---|---|---|
| `representative` | 30, stratified by deck × phase × seat | At least 15 roots with consequential non-wait coverage. Zero material failures. No class reaching the 4-root repeated-harm count. No missing root or branch. Every above-floor event reviewed. | Yes. The bound is for 30 roots: 1 − 0.05^(1/30) ≈ 9.5%. **Never quote Tier A's 32-family 8.9% bound.** |
| `targeted_probe` | 24 by default: 4 each for lane choice, building pull, body block, charge blocking, Log pushback and shields | Can only be `blocked`, `inconclusive` or `no_block_found`. It never passes. | None |

Either block can block promotion. Every declared root stays in failure accounting. Ineligible, missing and failed roots are kept as declared failures. They make the block `inconclusive` and are never replaced.

Code:
- `src/clasher/rl/readiness_tier_b.py`: protocol, strata, policy ranking and evaluator.
- `readiness_tier_b_policy.py`: actor, scalar root bank and native prefix driver.
- `readiness_tier_b_probes.py`: probe rules and probe report.
- `readiness_tier_b_ledger.py`: `tier_b_*` tables and freshness shared with Tier A.
- CLIs: `scripts/tier_b_readiness.py` and `scripts/collect_tier_b_prefix.py`.
- Branches run through the unchanged `scripts/run_readiness_v2.py execute` with a `tier_b_transfer` plan.

## 0. Preconditions (all must hold before step 1)

1. **Tier A is admitted.** `require_admission(<ledger>, <tier-a admission.json>)` passes. Tier B takes its measurement floors, and the `tier_a_protocol_sha256` it binds, from the sealed Tier A protocol. The ledger checks this at declaration. If the native runtime or its attestation changes, the Tier A floors no longer apply: run a new identical-repetition study under a new prospective declaration.
2. **The pilot checkpoint is frozen.** Record its path and sha256 and never write to it again. It must be a public-contract-v4 checkpoint with confidence-aware inputs.
3. **A supported-decks JSON exists** whose card vocabulary is a subset of the 16 pilot cards. Use the pilot's training-decks file. `load_frozen_policy` rejects wider vocabularies because the scripted evaluation opponents require the 16-card scope.
4. **Execution is authorized.** Emulators and adb must be free, and the coordinator must authorize execution. Steps 1–3 are offline. Steps 4 and later write the real readiness-v2 ledger.
5. **A new runtime snapshot exists.** Tier B source pins cover every `src/clasher/**/*.py` plus the Tier A and Tier B scripts, so it must run from its own frozen copy. Never modify an existing snapshot.
   ```bash
   SNAPROOT=reports/strategy_council_20260928/m0/runtime-snapshots
   # Same arguments as native-final-v4 (see its snapshot.json); new output directory.
   python $SNAPROOT/create_snapshot.py --source . --gamedata <gamedata> \
     --gamedata-sha256 <sha> --roles <roles> --output $SNAPROOT/native-tier-b-v1
   ```
   Run every command below from the snapshot:
   ```bash
   SNAP=$SNAPROOT/native-tier-b-v1
   export PYTHONPATH=$SNAP/src:$SNAP/scripts OMP_NUM_THREADS=2
   ```

Shared variables (Tier A v4 values shown; confirm them before use):
```bash
LEDGER=reports/strategy_council_20260928/readiness-v2.sqlite
TIER_A_ID=m0-tier-a-fresh-v4
TIER_A_ADMISSION=<ledger-issued admission.json for $TIER_A_ID>
CKPT=<frozen pilot checkpoint>; DECKS=<pilot supported decks json>
OUT=reports/strategy_council_20260928/m0/tier-b/<attempt-dir>
ADB=/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb
CATALOG=/Users/sam/.cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv
CALIBRATION=$SNAP/calibration.receipt.json
NATIVE_ATTESTATION=<canonical sha of the native `attest` response, as in Tier A>
V7=/Users/sam/Desktop/code/clasher/artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_development_20260915/native-root-registry.sqlite
TEMPLATE=reports/calibration_development_20260915/deck-mix-development/mix0-reversed
TEMPLATE_PLAN_SHA=4c47d7839a9e5dd9fe49312949b3276b5bd332dd139225285ea4fb56bc591259
```

## 1. Scalar root banks (offline; CPU only)

Each root request comes from its own scalar game played by the frozen policy: one root per game.

- **Opponents** cycle over self-play and the balanced, pressure and defense scripts.
- **Window start.** The start tick is drawn uniformly inside the slot's phase. Native ticks: early is 90–1199, middle 1200–2399 and double elixir 2400–3599. Overtime is excluded by default; report this as a scope narrowing.
- **Window rule.** The window is 300 ticks, and the rule is the first root in that window where the policy's candidates are eligible.
- **Draws.** Each slot gets at most 3 scalar draws. Every rejected draw is recorded in the bank.
- **Incomplete banks.** If any slot has no eligible draw, the command writes `*.incomplete.json` and exits 1. An incomplete bank cannot be declared. Choose a new master seed and bank; never edit a bank.

```bash
nice -n 15 python $SNAP/scripts/tier_b_readiness.py generate-roots --checkpoint $CKPT \
  --decks $DECKS --master-seed <fresh integer> --block representative --output $OUT/rep/root-bank.json
nice -n 15 python $SNAP/scripts/tier_b_readiness.py generate-roots --checkpoint $CKPT \
  --decks $DECKS --master-seed <another fresh integer> --block targeted_probe \
  --probe-roots-per-kind 4 --output $OUT/probe/root-bank.json
```
Scalar previews show that eligible states are reachable. They are not roots and carry no outcomes.

## 2. Native configs (offline)

This step reuses the Tier A converter and exercised template:
```bash
python $SNAP/scripts/tier_b_readiness.py materialize-configs --bank $OUT/rep/root-bank.json \
  --template-capture $TEMPLATE --template-plan-sha256 $TEMPLATE_PLAN_SHA \
  --gamedata $SNAP/gamedata.json --gamedata-sha256 <sha> --output $OUT/rep/native-configs
```
Repeat for `probe`.

## 3. Freeze and declare (writes the ledger; before any capture)

```bash
python $SNAP/scripts/tier_b_readiness.py declare --ledger $LEDGER --attempt-id m0-tier-b-rep-v1 \
  --bank $OUT/rep/native-configs/root-bank.json --manifest $OUT/rep/native-configs/manifest.json \
  --checkpoint $CKPT --decks $DECKS --tier-a-ledger $LEDGER --tier-a-attempt-id $TIER_A_ID \
  --tier-a-admission $TIER_A_ADMISSION --native-attestation-sha256 $NATIVE_ATTESTATION \
  --catalog $CATALOG --calibration-receipt $CALIBRATION \
  --historical-registry $V7 --historical-registry $LEDGER
```
Repeat with `--attempt-id m0-tier-b-probe-v1`.

The declaration pins:
- all sources, including both Tier B scripts;
- the checkpoint, decks, Tier A admission, gamedata, catalog, calibration and converter manifest;
- the strata (deck/phase/seat/opponent/probe kind) and the frozen criteria.

Freshness is checked against v7 native roots, every Tier A attempt, the shared `fresh_identities` table and earlier Tier B attempts. Declared identities then block reuse by later Tier A attempts.

## 4. Native prefixes (emulator)

The frozen policy plays the root owner, and the opponent is the declared policy or script. Sampling runs at temperature one from the request's seeded generator.

- **Vocabulary bridge.** Native packets use the reference vocabulary and reach the policy through a bridge. The native adapter does not measure opponent history or seen cards, so those channels stay missing with zero confidence (see Limitations).
- **Claims.** Each claim is irreversible. Families can be split across emulators with repeated `--family-id` flags, but a claimed family is never re-run.

```bash
python $SNAP/scripts/collect_tier_b_prefix.py --registry $LEDGER --attempt-id m0-tier-b-rep-v1 \
  --manifest $OUT/rep/native-configs/manifest.json --catalog $CATALOG --decks $DECKS \
  --adb $ADB --serial emulator-5580 --port 26789 --output $OUT/rep/prefixes-e5580 \
  [--family-id tb<seed>-repr-00 ...]
```
Each selected capture also writes these files, which are pinned in its capture receipt:
- `policy-root.json`: the ranking record, with the original recommendation, wait log-probability and candidate log-probabilities.
- `policy-trace-public.npz` and `policy-trace-controls.npz`: the exact policy inputs and the sampled actions.

## 5. Recompute, then seal (before any branch outcome)

```bash
python $SNAP/scripts/tier_b_readiness.py verify-captures --ledger $LEDGER --attempt-id m0-tier-b-rep-v1 \
  --decks $DECKS --output $OUT/rep/policy-audit.json
python $SNAP/scripts/tier_b_readiness.py seal --ledger $LEDGER --attempt-id m0-tier-b-rep-v1 \
  --verification $OUT/rep/policy-audit.json --verification-sha256 $(shasum -a 256 $OUT/rep/policy-audit.json | cut -d' ' -f1) \
  --output $OUT/rep/frozen-protocol.json
```
`verify-captures` replays every selected root's policy trace. It checks each sampled prefix action and each candidate log-probability to within 1e-4, then recomputes the candidates and the original recommendation. Any drift stops the seal.

The seal records the families, the policy rankings and a `generation_failures` entry for every non-selected root. It refuses a protocol that hides a failure or changes strata, criteria or pins.

## 6. Branches (emulator + scalar)

```bash
python $SNAP/scripts/tier_b_readiness.py plan --ledger $LEDGER --attempt-id m0-tier-b-rep-v1 \
  --catalog $CATALOG --output $OUT/rep/plan
```
Then use the Tier A launchers (`readiness/tier-a-fresh-v4/run_native_shard*.sh` and `run_scalar.sh`) with these changes:
- `PLAN=$OUT/rep/plan/branch-plan.json` and `ATTEMPT_ID=m0-tier-b-rep-v1`
- new output directories and lock names

Keep these settings as in Tier A:
- `--native-path fast --native-render-off --native-branch-start replay`
- `--ownership-ledger $LEDGER --calibration-receipt $CALIBRATION`

For a `tier_b_transfer` plan, `run_readiness_v2.py` claims and records branches only in the `tier_b_*` tables. It rejects snapshot branch starts and non-default native read options, exactly as for fresh Tier A. Use `--unclaimed-only` to resume after an interruption: claimed failures are skipped, never retried.

## 7. Mechanism review, then evaluate once

Review every above-floor event: its `(family_id, candidate_role)` appears in the report's `above_floor_classes`. Write the verdicts as a JSON list of `MechanismReview` records. A review can add a block; it can never remove an automatic one. Evaluation opens the attempt irreversibly, so do the reviews first. In practice, run it once without reviews only if you accept an `inconclusive` result that you then preserve.

```bash
python $SNAP/scripts/tier_b_readiness.py evaluate --ledger $LEDGER --attempt-id m0-tier-b-rep-v1 \
  --calibration-receipt $CALIBRATION --report $OUT/rep/report.json --receipt $OUT/rep/receipt.json \
  [--reviews $OUT/rep/reviews.json]
```
For the probe attempt, the command also writes `report.probes.json`, a per-kind summary that never contains a population rate.

The receipt records the status and has `grants_scope: false`. Tier B gates promotion but grants no training or search scope.

## Interpretation and failure handling

- **Representative block.** `passed` requires all of the rules above. The quoted bound is the 30-root bound, and only for this protocol's narrow failure event. `inconclusive` (for example, fewer than 15 covered roots, a missing root or an unreviewed event) is retained as opened evidence. A new attempt needs a new bank, new seeds and a new attempt id.
- **Probe block.** `blocked` identifies a mechanic to repair or isolate before rewarding more of it (see strategy.md, "Scheduled follow-on work and decision rules"). `no_block_found` is not a clearance rate.
- **Reporting.** Report strata summaries (by deck, phase, seat, cell and opponent) and play-versus-wait coverage alongside the headline.
- **Opened attempts.** Never delete, retry or redirect a claim. Tier B roots can never enter training, and the ledger rejects `training` exposure.

## Known limitations to state with any result

- **Missing channels on native.** On native, the policy sees opponent history and seen cards as missing with zero confidence, which differs from the scalar training inputs. Visible identities outside the checkpoint vocabulary map to `<unknown>`; the count is in `policy-root.json`. These are declared transfer conditions, not repaired inputs.
- **Divergent games.** Native prefixes are closed-loop policy games. They diverge from the scalar preview games, which only locate phase-appropriate, policy-reachable eligible states.
- **Eligibility narrows scope.** Roots need two distinct affordable cards and a same-slot placement at least 2 tiles away; probe roots also need their probe's rule. Overtime is excluded by default.
- **Probe predicates** are public-geometry heuristics: token identity, side and canonical y. They select roots; they do not diagnose the mechanism. The mechanism review does that.

## Expected emulator time (from Tier A v4 measurements)

Tier A v4 measured about 250–290 s per native branch per emulator on 8 emulators, about 10 s per scalar branch and about 35 s per native prefix.

| Stage | Representative (30 roots) | Probes (24 roots) |
|---|---|---|
| Native branches (roots × 4 conditions × 4 candidates) | 480 → about 34–39 emulator-hours, **about 4.5–5 h wall on 8 emulators** | 384 → about 27–31 emulator-hours, **about 3.5–4 h wall** |
| Native prefixes | 30 → 20–45 min, one emulator (policy inference; later phases need longer prefixes) | 24 → 15–35 min |
| Scalar branches | 480 → about 80 CPU-min (concurrent) | 384 → about 65 CPU-min |

End to end, one Tier B run (both blocks) needs about 8–9 h of wall time on 8 emulators, plus about 1 h of offline scalar root generation. Roots that fail to capture reduce the branch count but leave the block inconclusive.
