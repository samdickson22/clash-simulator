# Executed command audit

Run roots on127x04: R01=`/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-main-20261016-01`, R02=same prefix ending`-02`. All source edits/commits in `/mpac/sdicks02/repos/clasher-cards-b1`, branchcards/b1. No writes to source/runtime roots outside B1; remote run roots are owned scratch artifacts. `PROGRESS.md` supplies UTC times, exact PIDs and failures; launcher receipts supply actual script/binary/input hashes.

## Git/source

```
git branch cards/b1-before-main-20261016 1dab5bce4a550eb4a99e21558d62ab231db84b5a
git merge --no-commit --no-ff ae3f6b0c579c5c817630b92a64089917c6623704
git add engine-cards/src/lib.rs engine-cards/differential.py
git add engine-cards/src/c56.rs engine-cards/py/src/clasher/entities.py
git add reports/cards/b1/main-integration
/mpac/sdicks02/cc/tools/bin/clasher-secret-scan
git diff --cached --check ae3f6b0c579c5c817630b92a64089917c6623704
git commit -m "Merge fixed main into B1 and reconcile synchronous container spawning"
```

Merge5c8afc2d7 retained all automatically staged fixed-main changes. The first diffcheck flagged one newly copied review blank line plus8 inherited main patch lines; non-fail-fast command grouping incorrectly continued. The immediate follow-up stripped the new report blank-line whitespace, used`set -e`, explicit staging of that report and PROGRESS, secret-scan and both staged/against-main diffchecks, then commit6cf7dbcfd. The inherited main patch is unchanged; B1's against-main delta is clean. History is preserved.

## Staging/identity

Exclusive mkdir of each fresh run's tree/tools/root and owned output directories; read-only mirror links to old`/mpac/sdicks02/jobs/clasher/cards/b1/rt` excluding src/engine-rs/gamedata, with those three links pointing at the fresh source snapshot. Source transfer:

```
rsync -a --exclude target --exclude __pycache__ --exclude '*.pyc' engine-cards/ 127x04:R/tree/
```

R is replaced by the exact R01/R02 above, no delete. Tools copied with scp from scoped reviewed files, unchanged B1/BatchA probes/scenarios and fidelity comparator. Pools and stats specification copied read-only from08 `cards/{b1,batchA}/fid` via`/tmp/b1-main-stage-20261016-01`, never staged into git. Current source manifest path prefix engine-cards/→tree/. Original506 manifest paths prefixed with absolute original04 tree; failed initial relative-path manifest retained in R01 and corrected before any job launched. Local Python3.8 lacks str.removeprefix; compatible slicing corrected the local preparation exception before SSH mutation.

R02 copies actual successful R01 build.done/test.done/regressions.json and unchanged native file, with explicit build-origin/test-origin and native-origin receipts. It makes no claim that those phases executed in02. Native copied checksum was initially relative to R02; after affected completed, preserved native-staged-relative.sha256, emitted native-absolute.sha256 and restored native.sha256's original absolute-path format. The hash column remains6737; no binary/source substitution. Exact path normalization:

```
cp native.sha256 native-staged-relative.sha256
sha256sum "$A/out/clasher_core.abi3.so" > native-absolute.sha256
test "$(cut -d' ' -f1 native-staged-relative.sha256)" = "$(cut -d' ' -f1 native-absolute.sha256)"
cp native-absolute.sha256 native.sha256
```

All506 current/original source files, tool manifests and native checksum verified before/after every successful phase. All17 gate helper/root/pinned-native expected identities derived from original accepted receipts and verified before gate; all5 pinned JSONL checksums and original compare match. Old inputs/receipts were not rewritten.

## Jobs

Each launch is this exact form with A=R01/R02, phase literal below, exclusive launch log and recorded `$!`:

```
set -o noclobber
PYTHONOPTIMIZE=0 NUMBA_DISABLE_JIT=1 setsid /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4 nice -n 15 bash "$A/tools/review_jobs.sh" "$A" "$phase" > "$A/$phase-launch.log" 2>&1 </dev/null &
pid=$!
printf '%s\n' "$pid" > "$A/$phase-launch.pid"
```

R01 build3593124→success3593595; test3686350→success3687187; affected3989610→88/94 failure (two assertion assumptions). R02 affected385528→success38620494/94; supplemental1134711→success11354314/4; reference1451252→success145165739 pairs; gate1634216 launched only after all actual prerequisites, currently pending. Supplemental substitutes script`$A/supplemental/supplemental_jobs.sh`; reference substitutes`$A/tools/reference_jobs.sh`. Both retain identical approved lease/flock/group-drain/env controls. Exact old phase PIDs and receipt/output identities checked absent/complete before each next phase; no pgrep/pkill and no duplicate gate.

Build: offline cargo+1.97.1, release, extension-module+gil-release, -j4, target only R01/out/target. Tests single process. Gate uses3 fixture workers plus coordinator≤4, then four sequential root shards; unchanged exact validator requires577 identical fixtures/chains,429 reference parity,0 errors,600 roots300full/300cut,12games/1800selections. Roots/templates/scripts and model inputs remain read-only; all Python jobs use JIT/bytecode off and single-thread libraries. Native clone/reload comparison is exact over all serialized fields; cross-engine raw representation limitations remain disclosed.
