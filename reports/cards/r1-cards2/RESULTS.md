# r1-cards2 / live16402b — final build and gate receipts

**PASS.** Final dev roots are assembled on 127x08 from engine `878d5f459d58112527e9c3e76c804f27e5d7c0a3` with native `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`. Runtime/evaluator snapshot: `d6c347ac1ce4ce8382745ba2d9a7fd31dcf830de` plus the two final native-pin overrides. The assembler fixes are f97b2052e and a71a7643a, both committed/pushed as explicitly requested; 11 unit tests and credential-pattern scans passed. No engine logic edits, release or sealing by this worker. Final pin edits and this report are for the lead to commit.

## Final artifacts

| Artifact | Value |
|---|---|
| r1-cards2 root | `127x08:/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards2-dev/` |
| live16402b root | `127x08:/mpac/sdicks02/jobs/clasher/cards/runtime/live16402b-dev/` |
| Native SHA256, both roots | `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1` |
| r1-cards2 gamedata SHA256 | `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65` |
| live16402b gamedata SHA256 | `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb` — same as live16402 |
| Engine overlay manifest SHA256 | `b98ea61c5dd438f26bfbdd42bdf51efbabe289a26964922b69730eff7b02aad3` |
| Engine overlay | 473 files; 9 changed from frozen r1; 0 base-only source files |
| Balance overlay | 79 applied slots; original RoyaleSim/calibration input hashes retained |
| `CARDS-RUNTIME-RECEIPT.json` | `87d4cf225ebdaf39a00650080246a5b01d42c8ac54e702005aab0a2b1e50439c` |
| `LIVE16402-RECEIPT.json` | `81f5ccb3e054449cd64788161514ef2f302481f28b1167a1594c6542f08d4204` |

Final native was **copied from the Batch A owner's build**, with its full SHA verified on both 04 and 08. The explicit source export is 878d5f459. Earlier fresh builds on 08 reproduced 1923619e and 5f07238c byte for byte using the existing build recipe capped at cargo `-j8`; their receipts remain historical. Final roots were reassembled with the fixed assemblers at 2026-10-16T03:38:24–32Z, using copies rather than hardlinks. The source/hash audit verified every installed overlay against that exact export, both natives, all four balance inputs, and seven runtime code files: [artifact receipt](receipts/artifacts-de11f124.json).

[BUILD-RECEIPT.json](BUILD-RECEIPT.json) holds the final input/code hashes and resolved pins. Raw assembler receipts retain their legacy `pins=r1-cards1` / `pins=live16402` labels; Runtime selection uses the actual r1-cards2/live16402b entries below, verified by the two final smokes. Value-bearing overlay details remain in scratch runtime roots.

The worktree advanced during measurement to 99b26b995 (legacy `base_cut=None` compatibility and the existing live16402 flag). Those changes were preserved. The measured runtime snapshot is the lead-specified d6c347ac1; selected new-pin dictionaries match the worktree. The 99b change preserves the explicit `base_cut=True` call used by these fc K4L checks.

## Gate table

Fresh final-candidate checks and the carried 5f07238c measurements are labeled separately. The lead explicitly requested carrying the completed scope/no-crash/sanity evidence while replacing the native/runtime, then rerunning smoke, HEADLINE and live totality.

| Gate | Measurement build | Coverage / outcome | Failures |
|---|---|---|---|
| Runtime verify smoke | **de11f124 / d6 snapshot** | **2/2 PASS**; full scope, 121 playable cards, 142 bodies, 350 templates; config entries 237 / 238 | 0 |
| K4L HEADLINE command SHA vs r1-total | **de11f124 / d6 snapshot** | **12/12 identical**, cases 0–5 × R3a/v1; winner/ticks/towers/score also identical | 0 errors; all 24 arm rows terminal |
| live16402b totality | **de11f124 / d6 snapshot** | **4 × 6,707 probes** | **0 panics**; scrub modes 0 failures |
| Scope root parity vs r1-total | Carried **5f07238c** | **600/600 identical**: 300 full + 300 cut, exact sampled key sets; all fields except config SHA agree | 0 differing IDs |
| r1-cards2 non-C56 no-crash | Carried **5f07238c** | **6/6 terminal**, D1–D4/M1 vs random + D1 vs R3a; 599 roots / 592 with non-C56 opponent cards; new-card entities in every game | 0 crashes/panics/errors/native/search/root/fast failures |
| LIVE K4L mixed decks | Carried **5f07238c** | **33/33 terminal**, D1–D4/M1 vs random/R3a ×3 + X1/random ×3; 3,588 roots / 3,228 non-C56 | 0 crashes/panics/errors/native/search/root/fast failures |
| Fast mixed decks | Carried **5f07238c** | **36/36 terminal**, D1–D4/M1/X1 × random/R3a ×3 | 0 crashes/panics/errors/native/search/root/fast failures |
| K4L sanity eval vs current pin | Carried **5f07238c** | **400/400 terminal**, exact cases 0–199 × R3a/v1 | 0 errors |

Final HEADLINE completed 03:47:03Z and final totality 03:49:38Z. Final baseline ran on 04 and full arm on 08, each with two workers under an 8-slot lease. Scope roots and all match gates used the existing tools unchanged; the wrappers supply the requested roots/pins. All arms used `PYTHONHASHSEED=0`. The scope snapshot before d6 already included the R.bots widening; [GLUE-5F07238C.json](GLUE-5F07238C.json) identifies that measured code. LIVE wall-clock results are no-crash measurements; search/default source counts remain in raw logs.

The Batch A owner's separate **native de11f124 run-4 C56 gate is PASS**: 577/577 fixtures and Rust-only chains byte-identical, full/cut roots 300+300 identical (compare SHA `5371b33164a52d7ee9fe242e155ac873cc11a2e7e1fa40e4de52032c9aba8744`). See [Batch A RESULTS §6](../batchA/RESULTS.md); that run was not duplicated here.

## Final totality detail

| Configuration | Mode | Probes | Panics | Failing cuts |
|---|---|---:|---:|---:|
| Recorded-root config | Plain | 6,707 | 0 | 68 |
| Recorded-root config | Scrub | 6,707 | 0 | 0 |
| Final live Runtime config | Plain | 6,707 | 0 | 67 |
| Final live Runtime config | Scrub | 6,707 | 0 | 0 |

Every plain-mode failure is `ValueError: unsupported card absent from imported pilot configuration` (244/243 failed probes respectively), the deliberate malformed-hand condition. Both scrubbed modes have zero failures.

## Sanity eval (carried)

HEADLINE-v1, C56 X-decks, base 1455777415631152. Candidate K4L-R-gs-rw-fc; current arm is hl2 K4L-R-gs on 04 `jobs/clasher/bot-lopp2/base/bot-lopp-hl2`, restricted to cases 0–199. The filtered reference SHA is `627b198537b7be0341a536622049293e76636b02040cc31126358304d0a78e77`; fresh r1-total short-gate command streams replay its first six cases/opponent 12/12 exactly.

| K4L vs | live16402b mean (W-D-L) | Current pin | Paired difference [95% CI] |
|---|---|---|---|
| R3a | 0.810 (162-0-38) | 0.830 (166-0-34) | -0.0200 [-0.0800, +0.0450] |
| v1 | 0.920 (184-0-16) | 0.950 (190-0-10) | -0.0300 [-0.0750, +0.0150] |
| Pooled | 0.865 (346-0-54) | 0.890 (356-0-44) | -0.0250 [-0.0625, +0.0150] |

Bootstrap: 4,000 draws, seed 0, sorted (opponent,index) pairs; pooled resamples 400 paired game differences. Individual mean-score CIs are in [eval receipt](receipts/eval-5f07238c.json). Each paired interval includes zero. This measures sim sanity. The full eval was completed on 5f07238c/pre-d6 and retained per the lead's instruction. Cases were split into disjoint 0–99 (04) / 100–199 (08), preserving the initial 47 completed cases; exact 400-key coverage was audited.

## PIN_SETS lines

Only the two new entries' native SHA and their source comment were changed by this final update. Other worktree entries equal current HEAD; the r1-cards1 gamedata pin and later existing-live16402 flag change are the runtime owner's work.

```python
# BASE_GAMEDATA = '892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65'
**{'r1-cards2': dict(PINS, native_sha256='de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1',
                     card_scope='full', fc_side_cut=True, gamedata_sha256=BASE_GAMEDATA)},
**{'live16402b': dict(PINS, native_sha256='de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1',
                     card_scope='full', fc_side_cut=True,
                     gamedata_sha256='a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb',
                     tournament_crown_from_gamedata=('Fireball', 'Poison'))},
```

Select on 08:

```bash
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards2-dev
export CLASHER_BOT_RUNTIME_PINS=r1-cards2
export CLASHER_ROOT="$CLASHER_BOT_RUNTIME"
export CLASHER_EVAL_RUNTIME_ROOT="$CLASHER_BOT_RUNTIME"
export CLASHER_DELAY_NATIVE_DIR="$CLASHER_BOT_RUNTIME/native"
```

For live16402b, use this complete selection instead:

```bash
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/cards/runtime/live16402b-dev
export CLASHER_BOT_RUNTIME_PINS=live16402b
export CLASHER_ROOT="$CLASHER_BOT_RUNTIME"
export CLASHER_EVAL_RUNTIME_ROOT="$CLASHER_BOT_RUNTIME"
export CLASHER_DELAY_NATIVE_DIR="$CLASHER_BOT_RUNTIME/native"
```

## Evidence and restart notes

Final scratch: `08:/mpac/sdicks02/jobs/clasher/cards/r1-cards2/final/` (native copy, exact source export, repo snapshot, final logs, full HEADLINE, smokes, totality); baseline HEADLINE is in the same path on 04. Local collected evidence: `/mpac/sdicks02/jobs/clasher/cards/r1-cards2/evidence-de11f124/`. Carried outputs remain under the parent job's `gate/`, eval ranges under `gate/hl-live16402b-{0-99,100-199}/` on their respective hosts; collected/combined data under `evidence-5f07238c/`.

All summary receipts are in [receipts/](receipts/), with exact input SHA256s. [CURRENT-ARM-RECEIPT.json](CURRENT-ARM-RECEIPT.json) records the hl2 reference. [PROGRESS.md](PROGRESS.md) includes stage times, recorded PIDs and the one interrupted preliminary smoke during lease right-sizing; the subsequently completed smoke/check sequence is the final one. [DRY-RUN-RESULTS.md](DRY-RUN-RESULTS.md) is the superseded 1923619e history and is not a passing gate receipt.

Runs used only 08/04, setsid, cpu_job.sh leases ≤8, and nice. Frozen clasher-bot-runtime was read only. All task jobs are complete. No card stat tables were added to git; only aggregate results, identifiers and hashes are recorded here.
