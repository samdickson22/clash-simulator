# r1-cards2 / live16402b — provisional dry run

Exploration tier. **Long gates ON HOLD at the lead's request.** Batch A native `1923619e…` has a newly reported native≠Python bug in Freeze inheritance on death spawns. The lead will supply the replacement commit and native SHA. The builds below are preparation receipts, not approval or gate passes. No engine logic changes, release, sealing or commits.

## Builds

Worktree `cards/lead` at `ab241882502ce102af7df59c90c6fd5126d3dc0e`. Engine export: `9eed63029db98d6f99db16c1701a964a0c741fd2`; `git diff 9eed63029 HEAD -- engine-cards` was empty. Both assemblers ran on 08, completed 2026-10-16T02:23:10Z.

| Artifact | Receipt |
|---|---|
| r1-cards2 dev root | `127x08:/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards2-dev/` |
| live16402b dev root | `127x08:/mpac/sdicks02/jobs/clasher/cards/runtime/live16402b-dev/` (scratch copy on 04) |
| Fresh native rebuild from 9eed63029 | `1923619e996684122571cae05688e085163328b3cf6334dd3bad1a2d8e53aae8` — exact match to 04 `batchA/out/clasher_core.abi3.so`; `batchA/gout` absent |
| Base gamedata | `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65` |
| Overlay gamedata | `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb` — unchanged from live16402 |
| Engine overlay manifest | `870eb15b5253baa3afbf96f9fffbdaf6a6873e4bfda1744dc4d74f6e7538579c` (473 files, 9 changed from r1) |
| CARDS-RUNTIME-RECEIPT.json | `24aa81935740aefb9f36d85e8ef77dafe24070a4e72f28c5bafdb080cecc40ad` |
| LIVE16402-RECEIPT.json | `884601c5cd49bbe4170ba75d9cc18648d41011006cf087507cba6858ba53d14a` |

The native rebuilt in 34.78 seconds using a scratch copy of `08:/mpac/sdicks02/jobs/clasher/cards/build.sh SRC OUT`, changing only cargo `-j 16` to `-j 8`. The build ran with `setsid`, `cpu_job.sh 8`, and nice 15. This reproduces the original native byte for byte while respecting the requested concurrency cap. Native output: `08:/mpac/sdicks02/jobs/clasher/cards/r1-cards2/native-rebuild/`.

`build_runtime.py --tree source-9eed63029 --native native-rebuild/clasher_core.abi3.so` overlays the exact committed `engine-cards/py/src`, top-level Python glue, and native onto a copy of frozen r1. The assembler's receipt has legacy `pins='r1-cards1'` and `built_here=false` because the rebuild was a separate step passed via `--native`; actual selection uses the new entries below. `build_live16402.py` likewise retains legacy `pins='live16402'` in its receipt. Runtime selection is explicit and checked by the smoke.

The overlay applied the same 79 slots. Its RoyaleSim and calibration input hashes are recorded in [BUILD-DRY-RUN.json](BUILD-DRY-RUN.json); value-bearing overlay details remain in scratch runtime roots, outside git.

## Gate status

| Pin / gate | Required coverage | Status |
|---|---|---|
| r1-cards2 scope roots vs r1-total | 300 C56 roots × full/cut, exact parity | **HELD**. Old candidate partial output invalidated. |
| r1-cards2 HEADLINE command SHA vs r1-total | K4L-R-gs-rw-fc-p2, cases 0–5 × R3a/v1 | **HELD**, not started. |
| r1-cards2 non-C56 no-crash | D1–D4/M1, 0 failures, new-card units in roots | **HELD**, not started. |
| live16402b totality | Root/runtime config × plain/scrub, 0 panics | **HELD**, not started. |
| live16402b LIVE K4L + fast tier | 33 LIVE + 36 fast mixed-deck games, 0 failures | **HELD**, not started. |
| live16402b sanity eval | K4L-R-gs-rw-fc, 200 cases × R3a/v1 vs hl2 current-pin arm | **HELD**. Old eval stopped before any result rows. |
| Both dev roots, Runtime verify smoke | Pin verification, resource construction, full card scope | **PASS**: both verify=True, 121 playable cards, 350 templates; no gameplay gate. |

Root gate PGID `3260029` on 08 and eval PGID `2871656` on 04 launched before the hold instruction. Both were stopped by TERM to the recorded process groups and verified absent using `ps`; no pgrep/pkill. Baseline roots had 600 records and candidate roots 56, so no comparison is claimed. Eval had 0 output rows. Superseded data: each host's `jobs/clasher/cards/r1-cards2/gate-superseded-1923619e/`, cancellation files and superseded logs. `LONG-GATES-ON-HOLD` in both job dirs prevents accidental gate/eval relaunch. No long jobs remain active.

Smoke completed 2026-10-16T02:26:58Z on 08, PGID `3291403`, exit 0. r1-cards2: 237 config entries (including Mirror payloads), build 45.6 s. live16402b: 238 config entries, build 46.0 s. Both had 121 metadata cards, 142 metadata bodies and 350 templates. The known RamRider base/full metadata conflict remains the documented full-wins choice. Only counts and hashes are retained in the git receipt; full smoke output stays in scratch. An independent dictionary comparison verified every preexisting PIN_SETS entry unchanged.

## Provisional PIN_SETS lines

Only these two entries were added to `bot/players/runtime.py`; other entries are untouched. Both retain `r1-cards1`'s `fc_side_cut=True`. The native SHA below must be replaced after the lead supplies the fixed build.

```python
**{'r1-cards2': dict(PINS, native_sha256='1923619e996684122571cae05688e085163328b3cf6334dd3bad1a2d8e53aae8',
                     card_scope='full', fc_side_cut=True)},
**{'live16402b': dict(PINS, native_sha256='1923619e996684122571cae05688e085163328b3cf6334dd3bad1a2d8e53aae8',
                     card_scope='full', fc_side_cut=True,
                     gamedata_sha256='a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb',
                     tournament_crown_from_gamedata=('Fireball', 'Poison'))},
```

Dry-run selection on 08 (these provisional builds are superseded):

```bash
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards2-dev
export CLASHER_BOT_RUNTIME_PINS=r1-cards2
export CLASHER_DELAY_NATIVE_DIR="$CLASHER_BOT_RUNTIME/native"
# For the provisional live overlay:
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/cards/runtime/live16402b-dev
export CLASHER_BOT_RUNTIME_PINS=live16402b
export CLASHER_DELAY_NATIVE_DIR="$CLASHER_BOT_RUNTIME/native"
```

## Ready for replacement

Mechanical launcher: [tools/run.sh](tools/run.sh), copied into each job's `repo/`. Build accepts `CARD_SOURCE_TREE` and `CARD_NATIVE_SHA256` for the lead's replacement; it rebuilds on 08 and checks the full native SHA and overlay gamedata SHA. The two pins must be updated and synced with that SHA. Clear the hold marker only after the replacement arrives. All stages run through explicit launches; nothing auto-restarts.

Existing gate tools and invocation semantics are retained. The roots and HEADLINE wrappers compare the actual r1-total root/native against the new full-scope root, avoiding the old wrappers' hardcoded r1-cards1 native/pin assumptions. Root comparison ignores config text hashes only. All arms use hash seed 0. The new eval uses the existing hl2 cases 0–199 current-pin arm documented in live16402 RESULTS. Match gates use the existing D1–D4/M1/X1 harness unchanged. Record complete expected case sets and zero failures before claiming any pass.
