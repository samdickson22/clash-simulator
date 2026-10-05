# Level extension (levels 10–12): runbook for after Tier A v4

Prepared on 2026-09-29 while `m0-tier-a-fresh-v4` was still using the emulators. Nothing here has run against a native reference. No ledger write, admission or native evidence exists yet.

This produces the evidence receipt that the pilot's mixed-level slot needs: `pilot/admissions/levels-10-12.json` in `pilot/v4-launch/post-admission-launch-plan.md` §4. The chain is: declare → native probes → scalar study → assemble → `readiness_admission.py extend-levels`. The pinned verifier (`clasher.rl.readiness_level_extension`, schema `readiness-level-extension-evidence-v2`) recomputes every accepted value from the raw files. No producer flag counts as evidence.

## What exists now

| Item | Path |
| --- | --- |
| Regenerated probe configs, bound to `daa58b28…` (v4 `gamedata.json`), from v4 `native-configs/configs/episode-00.json` | `prospective-configs/` (status `draft_missing_nominal_admission`) |
| Superseded drafts (bound to `3d99987c…`, never executed or declared), kept byte for byte | `superseded-draft-configs-3d99987c/` |
| Old/new manifest and per-config hashes. Only `rndSeed` differs. | `config-supersession.json` |
| Tools (workspace copies; step 1 freezes them) | `scripts/level_extension_common.py`, `collect_level_extension_probes.py`, `run_level_extension_scalar_study.py`, `build_level_extension_evidence.py`, `rehearse_level_extension_offline.py` |
| Dry test (scalar-backed fake native; 15 tests) | `tests/test_level_extension_tooling.py`, `tests/level_extension_fake_native.py` |

Config hashes. The file SHA-256 is in brackets.

- probe-0 (cards 10, Kings 10/12): `4a1e978f…` [`98781ed2…`]
- probe-1 (cards 10, Kings 12/10): `28e3cd09…` [`c87523c7…`]
- probe-2 (cards 12, Kings 12/10): `597415db…` [`e101f1b3…`]
- probe-3 (cards 12, Kings 10/12): `07398693…` [`67f59216…`]
- New manifest: `7b2adb98…`. Old manifest: `5f6aef63…`. Old probe files: `cd1fc483…`, `840b29b2…`, `16632996…`, `e0614d1e…`.

## Frozen design (fixed before any native outcome)

- **Native probes.** Four probes: uniform card and Princess level 10 or 12, with asymmetric Kings. Each probe is one verified-session "coverage game". Seat `p % 2` plays Knight, Musketeer, Dark Prince and Cannon in one lane. The other seat casts Fireball, Log and Zap on those troops once they cross into its half. Other cards cycle. Every action comes from the public action mask; no native state is forced. Frames are recorded every 5 ticks from tick 90, plus the tick-0 Crown frame, until all seven checks are observed and the ranking root is frozen. The cap is tick 3000.
- **Native rankings.** The verifier fixes the root owner at `p % 2`. The root is the first 5-tick boundary at or after tick 90 where both alternatives exist:
  - (0) the pressure controller's top play, which must deploy a building-targeting troop (Hog Rider);
  - (1) the defense controller's best play with another card.

  The root, its prefix and both alternatives are written to `ranking-root.json` before any branch runs. Each probe then runs 2 alternatives × 2 conditions (`balanced/pressure`, `defense/balanced`) for 200 ticks, on native and in scalar. That gives 32 branches.
- **Scalar mixed-level study.** Six declared cases (`CASES` in the study runner). Several card levels coexist in one seat, and some cases mix both seats. Crown levels are asymmetric per seat. Each case records Crown HP, body HP and spell damage as reported by the engine at every declared level. The root comes from balanced/balanced play using the same alternative rule, then two branches under `balanced/pressure`.
- **Level-aware controller views.** The pinned native adapter only projects level 11. For controller inputs, native frames go through a derived copy that keeps each body's HP fraction, after checking every body's native level against the plan. The views are then restored to the true visible levels. Raw frames are retained unchanged.

## Commands

Run everything from the snapshot, with the snapshot runtime, at low priority.

```sh
W=/Users/sam/Desktop/code/clasher
RC=$W/reports/strategy_council_20260928
SNAP=$RC/m0/runtime-snapshots/native-final-v4
ATT=$RC/m0/readiness/tier-a-fresh-v4
LEVEL=$RC/m0/level-extension
EVID=$RC/m0/level-extension-evidence-v1          # new; never under $LEVEL
LEDGER=$RC/readiness-v2.sqlite
ADB=/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb
CATALOG=/Users/sam/.cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv
CATALOG_SHA256=c59ef74273b721b861e6a499bc8869a6fc29ad07919884b79ebe859455d6eac5
ATTESTATION=$RC/m0/readiness/native-hostgpu-startup-20260928/attestation.json   # canonical sha 864227bf…
SERIAL=emulator-5580 PORT=26789
export CLASHER_ROOT=$SNAP PYTHONPATH=$SNAP/src:$SNAP/scripts PYTHONDONTWRITEBYTECODE=1 \
       OMP_NUM_THREADS=2 NUMBA_CACHE_DIR=$EVID/numba-cache
PY="nice -n 15 $SNAP/.venv/bin/python -B"
T=$EVID/tools
cd $SNAP
```

### 0. Preconditions (no writes)

```sh
pgrep -fl 'run_readiness_v2|collect_readiness_prefix|collect_level_extension' && echo "STOP: runner still active"
test -f $ATT/admission.json && $PY $SNAP/scripts/readiness_admission.py --ledger $LEDGER verify --admission $ATT/admission.json
$PY $SNAP/scripts/query_reference_probe.py --port $PORT --command status --output /tmp/le-status.json   # ready=true, paused=true
df -h $RC | tail -1          # well under 0.5 GB of output (full rich frames, gzip)
```

The emulator must be an already-running, owned, read-only host-GPU instance with attestation `864227bf…`. If the Tier A pool has been shut down, start one using the existing procedure (`$RC/m0/readiness/start_local_reference.py <new-output-dir> --gpu host --console-port 5580 --probe-port 26789 --read-only`) and check its `complete.json` first. The collector re-checks the attestation and ready/paused state before it writes anything. It takes the same device lock as the Tier A shard runner, so the two cannot overlap.

### 1. Freeze the tools (the receipt pins these copies)

The workspace copy of `run_readiness_v2.py` has already diverged from the snapshot. The tools always import the snapshot's helpers, and refuse to run if `CLASHER_ROOT` is unset.

```sh
mkdir -p $T $EVID/numba-cache
cp $W/scripts/{level_extension_common,collect_level_extension_probes,run_level_extension_scalar_study,build_level_extension_evidence,rehearse_level_extension_offline}.py $T/
chmod a-w $T/*.py && (cd $T && shasum -a 256 *.py > SHA256SUMS)
```

### 2. Offline rehearsal (optional, about 1 min, no emulator)

This uses the fake native, the real configs and a clearly synthetic base. Never pass its output to the ledger.

```sh
$PY $T/rehearse_level_extension_offline.py --configs-manifest $LEVEL/prospective-configs/manifest.json \
  --nominal-protocol-source $W/tests/test_training_readiness_v2.py --fake-native $W/tests/level_extension_fake_native.py \
  --decision-evidence $RC/m0/readiness/level-extension-implementation-decision.json \
  --catalog $CATALOG --catalog-sha256 $CATALOG_SHA256 --output /tmp/le-rehearsal-$(date +%s)
# expect {"native_failures": 0, "scalar_ranking_branches": 16, "adaptation_cases": 6, "scope": "independent_cards"}
```

### 3. Declare (binds the issued v4 admission; before any probe runs)

```sh
$PY $T/build_level_extension_evidence.py declare --configs-manifest $LEVEL/prospective-configs/manifest.json \
  --base-admission $ATT/admission.json --native-attestation $ATTESTATION --gamedata $SNAP/gamedata.json \
  --attempt-declaration $ATT/declaration.json --output $EVID/declaration
```

### 4. Native probes (the only emulator step, about 30–60 min on one emulator)

```sh
$PY $T/collect_level_extension_probes.py --declaration $EVID/declaration/declaration.json \
  --configs-manifest $LEVEL/prospective-configs/manifest.json --gamedata $SNAP/gamedata.json \
  --catalog $CATALOG --catalog-sha256 $CATALOG_SHA256 --adb $ADB --serial $SERIAL --port $PORT \
  --native-lock /tmp/clasher-readiness-v2-$SERIAL.lock --native-path fast --output $EVID/native \
  > $EVID/native.log 2>&1
```

Exit code 0 means all 4 probes and 16 native branches completed with unchanged sources. Per-probe status, coverage and failures are in `$EVID/native/collection-result.json`. The evidence consists of 4 coverage games of roughly 130–580 frames each, plus 16 branches of 40 frames. Tier A measured about 0.34–0.5 s per verified frame read.

### 5. Scalar study (no emulator, about 1 min)

```sh
$PY $T/run_level_extension_scalar_study.py rankings --declaration $EVID/declaration/declaration.json \
  --gamedata $SNAP/gamedata.json --catalog $CATALOG --catalog-sha256 $CATALOG_SHA256 \
  --native-run $EVID/native --output $EVID/scalar-rankings
$PY $T/run_level_extension_scalar_study.py adaptation --declaration $EVID/declaration/declaration.json \
  --gamedata $SNAP/gamedata.json --catalog $CATALOG --catalog-sha256 $CATALOG_SHA256 \
  --base-admission $ATT/admission.json --output $EVID/scalar-adaptation
```

### 6. Assemble and check locally

This binds the independent-card decision to the existing implementation decision. That is a coordinator application of the approved schedule. No new council endorsement is claimed.

```sh
$PY $T/build_level_extension_evidence.py assemble --declaration $EVID/declaration/declaration.json \
  --base-admission $ATT/admission.json --nominal-protocol $ATT/frozen-protocol.json --gamedata $SNAP/gamedata.json \
  --native-run $EVID/native --scalar-rankings $EVID/scalar-rankings --scalar-adaptation $EVID/scalar-adaptation \
  --independent-cards-decision-evidence $RC/m0/readiness/level-extension-implementation-decision.json \
  --output $EVID/assembled
python3 -m json.tool $EVID/assembled/local-verifier-check.json | head -60   # margins + verifier result/error
```

Before assembling, check that `frozen-protocol.json`'s `Protocol.sha256` equals `admission.json` `protocol_sha256`. Today it is `81b91eec…`, and the verifier enforces the match.

### 7. Issue the extension (coordinator; the only ledger write)

```sh
mkdir -p $RC/pilot/admissions
$PY $SNAP/scripts/readiness_admission.py --ledger $LEDGER extend-levels --base-admission $ATT/admission.json \
  --level-evidence $EVID/assembled/level-extension-receipt.json --output $RC/pilot/admissions/levels-10-12.json
$PY $SNAP/scripts/readiness_admission.py --ledger $LEDGER verify --admission $RC/pilot/admissions/levels-10-12.json
```

The expected output is `(10, 11, 12) independent_cards`. `native_level_scope` stays `uniform_cards_asymmetric_kings`, and native independent-card parity is never claimed. Then continue with `post-admission-launch-plan.md` §4 (`--phase mixed-league`).

## Failure policy

- Never retry, replace or delete a failed probe, branch or case. A failed run stays in `$EVID` as opened evidence.
- The verifier requires at least 2 of 4 probes with reference separation above 0.01, a regret of at most 0.05 in every probe, and at least 2 informative scalar cases. If a real run misses these, the receipt fails. Do not re-run in search of a pass. Any new attempt needs a new `$EVID` (for example `-v2`), a written reason and a design change declared before it runs.
- The collector fails closed when combat telemetry is incomplete or unattested, when a public action is illegal, when a command has no spend evidence, when a native level differs from the plan, or when the root does not replay.

## Known limits

- **Verifier gap.** The pinned verifier's Crown sum (`_crown_hp`) does not skip tower projectiles, which also carry `cardId -1`. Native ending frames are therefore Crown-body projections (`ending-frame.json`) that hash-link the retained raw frame (`ending-raw.json`). The assembler re-derives each projection from its raw frame. The verifier itself does not cross-check them. A workspace fix (skip `hp is None`) would not help this snapshot.
- **Dry-run informativeness.** On the fake, 2 to 4 of 4 probes were informative, with the probes paired by shared hands (0/2 and 1/3). The adaptation study had 5 of 6 informative cases. Native margins and regret are unknown until step 4.
- **Tick cap.** Native Log and Zap targeting may need retries (100-tick retry, tick-3000 cap). A long game could overflow the 1,024-event combat ring, in which case the collector stops with a failure.

## v3 delta (prepared 2026-09-30, not run)

Reason: `m0/level-extension-evidence-v3/reason.json`. Summary:

- **Fix A (Fireball).** Native names the caster's King Tower as a Fireball hit's `source`; the Fireball projectile is `immediateSource`. The v2 collector and the v7 verifier read `source.cardId` only, so none of the 20 Fireball casts counted (every cast hit a troop). The tools now attribute that shape (`level_extension_common.native_spell_attribution`). The same rule is in main `readiness_level_extension._spell_damage_attribution`.
- **Finding B (identical margins).** Not a bug. The native rows come from native frames, and Crown HP matched exactly in both engines in all 16 branch pairs. The assembler now rejects swapped or duplicated engine files (`check_ranking_provenance`).
- **Design change (required).** The native-final-v7 verifier cannot count native Fireball damage. It is pinned by the tier-a-fresh-v7 admission and is admission-bound for the pilot. v3 needs a snapshot carrying the fixed verifier and a base admission issued under it. Configs, plans, tick cap, root rule, roles, conditions and scalar cases stay unchanged. Under v7, v3 would fail again on Fireball: `m0/level-extension-v3-prep-rehearsal/v7-pinned-verifier` shows this offline.

Use the commands above with these changes:

```sh
SNAP=<runtime snapshot with the fixed verifier>      # native-final-v7 fails the precondition below
ATT=<tier A admission issued under $SNAP>
EVID=$RC/m0/level-extension-evidence-v3              # reason.json already present
# step 0, extra precondition (the pinned verifier must count King Tower-thrown Fireball):
$PY -c "import clasher.rl.readiness_level_extension as m; assert hasattr(m, '_spell_damage_attribution'), 'STOP: verifier cannot count native Fireball'"
# step 1 is unchanged (copy the five tools from $W/scripts). Expected SHA256SUMS:
#   level_extension_common.py bc2fd654…  build_level_extension_evidence.py a1d28509…
#   rehearse_level_extension_offline.py 8b1e42b5…  collect_level_extension_probes.py 748101920…  run_level_extension_scalar_study.py e59fb917…
# step 2 expected output now also lists probe status and the verifier error:
#   {"native_failures": 0, "scalar_ranking_branches": 16, "adaptation_cases": 6, "scope": "independent_cards",
#    "probe_status": ["coverage_complete", x4], "verifier_error": null}
```

Steps 3–7 use the same commands with the variables above. In step 4, `coverage.json` should show `spells_first_damage_attribution.Fireball == "king_tower_projectile"` and every probe as `coverage_complete`, well before tick 3000. In step 6, the assembler also fails if the native and scalar ranking files are swapped or duplicated.
