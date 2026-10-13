#!/bin/bash
# r4 CHAIN steps after S10 (offline; fake hosts; real 05 inputs read-only). Each step logs rc to $CH/logs/steps.
S=/dev/shm/s3s9s10r4-scratch; CH=$(cat $S/CHAIN_DIR); L=$CH/logs; B=/jobs/clasher/k4s-end-r1
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
FB=$CH/hosts/127x03$B
ENVV="env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8"; NICE="nice -n 19 taskset -c 8-15"; RUN="$ENVV $NICE"
step() { name=$1; shift; "$@" > $L/$name.out 2> $L/$name.err; rc=$?; echo "$(date -u +%FT%TZ) $name rc=$rc" >> $L/steps; return $rc; }
P=$(env -i PATH=/usr/bin:/bin HOME=/nonexistent GIT_OPTIONAL_LOCKS=0 git -C /mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full rev-parse refs/remotes/origin/k4s-end-r1)
cd /tmp
# 1. S11 provision from the REAL repo-full (tip = P') to fake 03, one login
step s11-provision $RUN $PY -I -B $S/drivers/chain_drive.py s11 provision --host 127x03 --commit $P --record $CH/records/s11-provision --outside-end-window "r4 CHAIN fake host only" || exit 1
# 2. frozen identity on the staged tree, real native/corpus digests
RT=$FB/runtime-${P:0:12}; BD=$FB/bundles/end-ref-127x03-pf00
step frozen-identity $RUN $PY -I -B $S/drivers/frozen_identity_drive.py $RT $BD $FB/end-inputs-r1/clasher_core.abi3.so $FB/end-inputs-r1/K4-states.pkl
# 3. S5 run on fake 03 (staged tools/k4s_end_preflight.py, staged runtime/bundle/guard job/repository; stub native = deliberate stop before any backend)
mkdir -p $FB/stub-native $FB/preflight/preflight-127x03-l00 && printf 'STUB native (r4 CHAIN deliberate stop)\n' > $FB/stub-native/clasher_core.abi3.so
TS=$(sha256sum $BD/tiers-pins.json | cut -c1-64); EV=$(sha256sum $BD/k4s-end-evidence/end-evidence.json | cut -c1-64)
H=/mpac/sdicks02$B; HR=$H/runtime-${P:0:12}; HB=$H/bundles/end-ref-127x03-pf00
step s5-run $RUN $S/drivers/ns.sh 127x03 $PY -I -B $S/drivers/s5_drive.py run --bundle $HB --bundle-pins-sha256 $TS --runtime-root $HR --native $H/stub-native/clasher_core.abi3.so --corpus $H/end-inputs-r1/K4-states.pkl --corpus-inventory $HR/reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json --corpus-inventory-sha256 3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13 --k4s-manifest-sha256 74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357 --sd1-manifest-sha256 b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76 --end-evidence $HB/k4s-end-evidence/end-evidence.json --end-evidence-sha256 $EV --repository $H/repository --attempt-parent $H/attempts --out $H/preflight/preflight-127x03-l00/preflight-127x03-l00 --hold-seconds 120
# 4. X = P' + synthetic END-JOB on the scratch origin's k4s-end-r1 (plumbing, scratch only)
export GIT_CONFIG_NOSYSTEM=1 HOME=$CH/eq/home GIT_INDEX_FILE=$CH/eq/index GIT_AUTHOR_NAME=r4chain GIT_AUTHOR_EMAIL=r4@chain GIT_COMMITTER_NAME=r4chain GIT_COMMITTER_EMAIL=r4@chain
O=$CH/eq/origin.git
git -C $O read-tree $P && OID=$(git -C $O hash-object -w $CH/eq/END-JOB.synthetic.json) && git -C $O update-index --add --cacheinfo 100644,$OID,reports/explore/k4s-confirm/end/END-JOB.json && T=$(git -C $O write-tree) && X=$(git -C $O commit-tree $T -p $P -m "r4 CHAIN synthetic END-JOB (scratch only)") && git -C $O update-ref refs/heads/k4s-end-r1 $X $P || exit 1
unset GIT_INDEX_FILE; echo "X=$X" > $L/X
PATCH="S9:REPO_FULL:$CH/eq/repo-full;S9:ORIGIN_URL:file://$O;S9:CLONE_PROTOCOL:file"
# 5. S9 refresh-clone + equivalence on the scratch clone
step s9-refresh $ENVV CHAIN_PATCH="$PATCH" $NICE $PY -I -B $S/drivers/chain_drive.py s9 refresh-clone --commit $X --base-commit $P --record $CH/records/s9-refresh || exit 1
RTS=$(sha256sum $CH/runtime-${P:0:12}/runtime-manifest.json | cut -c1-64)
step s9-equivalence $ENVV CHAIN_PATCH="$PATCH" $NICE $PY -I -B $S/drivers/chain_drive.py s9 equivalence --out $CH/runtime-${P:0:12} --manifest-sha256 $RTS --end-job-commit $X --record $CH/records/s9-equiv || exit 1
ESHA=$(sha256sum $CH/records/s9-equiv/s9-equivalence.json | cut -c1-64); JSHA=$(sha256sum $CH/eq/END-JOB.synthetic.json | cut -c1-64)
# 6. S11 advance to X on fake 03, one login
step s11-advance $ENVV CHAIN_PATCH="$PATCH" $NICE $PY -I -B $S/drivers/chain_drive.py s11 advance --host 127x03 --from $P --commit $X --equivalence-record $CH/records/s9-equiv/s9-equivalence.json --equivalence-sha256 $ESHA --end-job-sha256 $JSHA --record $CH/records/s11-advance --outside-end-window "r4 CHAIN fake host only" || exit 1
# 7. frozen end_evidence / end_job / producer_registry / producer_claim on the ADVANCED fake-host repository (claim lands in the fake host only)
step frozen-job $RUN $PY -I -B $S/drivers/frozen_job_drive.py $RT $FB/repository $BD/k4s-end-evidence/end-evidence.json --claim
echo "$(date -u +%FT%TZ) chain_rest DONE" >> $L/steps
