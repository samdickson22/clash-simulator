#!/bin/bash
CH=/tmp/k4s-r4chainb-H1qWfE; D=/dev/shm/s3s9s10r4-scratch/drivers-b; L=$CH/logs; B=/mpac/sdicks02/k4s-runner/run-r1/end-prep; ES=/mpac/sdicks02/k4s-runner/run-r1/end-staging
PY=/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python
ENVV="env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8"; NICE="nice -n 19 taskset -c 8-15"; RUN="$ENVV $NICE"
step() { name=$1; shift; "$@" > $L/$name.out 2> $L/$name.err; rc=$?; echo "$(date -u +%FT%TZ) $name rc=$rc" >> $L/steps; return $rc; }
sha() { sha256sum "$1" | cut -c1-64; }
P=$(env -i PATH=/usr/bin:/bin HOME=/nonexistent GIT_OPTIONAL_LOCKS=0 git -C $B/repo-full rev-parse refs/remotes/origin/k4s-end-r1)
RT=$CH/runtime-${P:0:12}; RTS=$(sha $RT/runtime-manifest.json)
cd /tmp
# 1. RC-6 declaration from the real runtime + 3 real bundles; the real r4 S7 validate_roots
ARGS=""; for n in 127x03:pf00 127x03:rd00-a00 127x04:pf00; do h=${n%%:*}; k=${n#*:}; BD=$CH/bundles/end-ref-$h-$k; ARGS="$ARGS --declare-bundle $h $BD $(sha $BD/tiers-pins.json) $(sha $BD/assembly-receipt.json)"; done
mkdir -p $CH/end-launch
step declare-roots $RUN $PY -I -B $D/chain_drive.py s10 --declare-roots --commit $P --runtime-manifest-for-checks $RT --runtime-manifest-sha256 $RTS $ARGS --out $CH/end-launch/ROOTS-DECLARATION.json || exit 1
ROOTS=$(sha $CH/end-launch/ROOTS-DECLARATION.json)
# 2. bundle headers for S7 build-argv (STAGING_BUNDLES), then drop the big 03-rd00-a00 and 04-pf00 bundles
for n in end-ref-127x03-pf00 end-ref-127x03-rd00-a00 end-ref-127x04-pf00; do mkdir -p $CH/staging-bundles/$n; for f in tiers-pins.json tiers-pins.sha256 assembly-receipt.json; do cp $CH/bundles/$n/$f $CH/staging-bundles/$n/; done; done
for n in end-ref-127x03-rd00-a00 end-ref-127x04-pf00; do chmod -R u+w $CH/bundles/$n && rm -rf $CH/bundles/$n; done
# 3. S10 -> fake 03 with the s5s6s7-r4 tools
BD=$CH/bundles/end-ref-127x03-pf00; GJ=$ES/guard-jobs/guard-127x03-pf00
step s10-03 $RUN $PY -I -B $D/chain_drive.py s10 --host 127x03 --create-base --runtime $RT --runtime-manifest-sha256 $RTS --bundle $BD $(sha $BD/tiers-pins.json) $(sha $BD/assembly-receipt.json) --guard-job $GJ --guard-job-name k4s-end-guard-r1-pf00 --guard-manifest-sha256 $(sha $GJ/guard-job-manifest.json) --tools-source $B/s5s6s7-r4 --end-inputs --record $CH/records/s10-03 --outside-end-window "r4 CHAIN-b fake host only" || exit 1
# 4. S11 provision from the real repo-full
step s11-provision $RUN $PY -I -B $D/chain_drive.py s11 provision --host 127x03 --commit $P --record $CH/records/s11-provision --outside-end-window "r4 CHAIN-b fake host only" || exit 1
# 5. the r4 S7 build-argv (U5) for preflight-127x03-l00 with S10's declared end-inputs paths
H=/mpac/sdicks02/jobs/clasher/k4s-end-r1
step s7-build-argv $RUN $PY -I -B $D/gate_drive.py build-argv --host 127x03 --kind preflight --attempt preflight-127x03-l00 --roots-sha256 $ROOTS --bundle end-ref-127x03-pf00 --compare-bundle end-ref-127x03-rd00-a00 --native $H/end-inputs-r1/clasher_core.abi3.so --corpus $H/end-inputs-r1/K4-states.pkl --hold-seconds 120 || exit 1
# 6. the r4 S5 run with EXACTLY the built argv's options, except --native -> a stub (deliberate stop before any backend);
#    compare bundle on the fake host = its 3 header files (SIMULATED, S5 reads only these); job dir made by hand (S7's)
FB=$CH/hosts/127x03$H; mkdir -p $FB/stub-native $FB/preflight/preflight-127x03-l00 && printf 'STUB native (r4 CHAIN-b deliberate stop)\n' > $FB/stub-native/clasher_core.abi3.so
chmod u+w $FB/bundles; mkdir $FB/bundles/end-ref-127x03-rd00-a00 && cp $CH/staging-bundles/end-ref-127x03-rd00-a00/* $FB/bundles/end-ref-127x03-rd00-a00/
TAIL=$(python3 -c "
import json; a=json.load(open('$CH/end-launch/127x03/preflight-127x03-l00/launch-argv.json'))
t=a[a.index('run'):]; t[t.index('--native')+1]='$H/stub-native/clasher_core.abi3.so'; print(' '.join(t))")
echo "$TAIL" > $L/s5-args
step s5-run $RUN $D/ns.sh 127x03 $PY -I -B $D/s5_drive.py $TAIL
# 7. frozen identity on the staged tree with the REAL native/corpus
step frozen-identity $RUN $PY -I -B $D/frozen_identity_drive.py $FB/runtime-${P:0:12} $FB/bundles/end-ref-127x03-pf00 $FB/end-inputs-r1/clasher_core.abi3.so $FB/end-inputs-r1/K4-states.pkl
# 8. X = P' + the s5s6s7-r4 builder's END-JOB on a scratch origin; refresh -> equivalence -> S11 advance; frozen end_job/claim
mkdir -p $CH/eq/home && cd $CH/eq && export GIT_CONFIG_NOSYSTEM=1 HOME=$CH/eq/home GIT_OPTIONAL_LOCKS=0
nice -n 19 git clone -q --mirror --no-hardlinks $B/repo-full origin.git && nice -n 19 cp -a $B/repo-full repo-full && git -C origin.git update-ref refs/heads/k4s-end-r1 $P && git -C repo-full config remote.origin.url file://$CH/eq/origin.git || exit 1
JOB=$B/s5s6s7-r4/builder-proof/END-JOB.json; O=$CH/eq/origin.git
GIT_INDEX_FILE=$CH/eq/index git -C $O read-tree $P && OID=$(git -C $O hash-object -w $JOB) && GIT_INDEX_FILE=$CH/eq/index git -C $O update-index --add --cacheinfo 100644,$OID,reports/explore/k4s-confirm/end/END-JOB.json && T=$(GIT_INDEX_FILE=$CH/eq/index git -C $O write-tree) && X=$(GIT_AUTHOR_NAME=r4b GIT_AUTHOR_EMAIL=r4b@chain GIT_COMMITTER_NAME=r4b GIT_COMMITTER_EMAIL=r4b@chain git -C $O commit-tree $T -p $P -m "r4 CHAIN-b: s5s6s7-r4 builder END-JOB (scratch only)") && git -C $O update-ref refs/heads/k4s-end-r1 $X $P || exit 1
echo "X=$X" > $L/X; cd /tmp
PATCH="S9:REPO_FULL:$CH/eq/repo-full;S9:ORIGIN_URL:file://$O;S9:CLONE_PROTOCOL:file"
step s9-refresh $ENVV CHAIN_PATCH="$PATCH" $NICE $PY -I -B $D/chain_drive.py s9 refresh-clone --commit $X --base-commit $P --record $CH/records/s9-refresh || exit 1
step s9-equivalence $ENVV CHAIN_PATCH="$PATCH" $NICE $PY -I -B $D/chain_drive.py s9 equivalence --out $RT --manifest-sha256 $RTS --end-job-commit $X --record $CH/records/s9-equiv || exit 1
step s11-advance $ENVV CHAIN_PATCH="$PATCH" $NICE $PY -I -B $D/chain_drive.py s11 advance --host 127x03 --from $P --commit $X --equivalence-record $CH/records/s9-equiv/s9-equivalence.json --equivalence-sha256 $(sha $CH/records/s9-equiv/s9-equivalence.json) --end-job-sha256 $(sha $JOB) --record $CH/records/s11-advance --outside-end-window "r4 CHAIN-b fake host only" || exit 1
step frozen-job $RUN $PY -I -B $D/frozen_job_drive.py $FB/runtime-${P:0:12} $FB/repository $FB/bundles/end-ref-127x03-pf00/k4s-end-evidence/end-evidence.json --claim
echo "$(date -u +%FT%TZ) partB DONE" >> $L/steps
