#!/usr/bin/env bash
# K4S runner r1: one frozen-T1 replacement cycle (coordinator Option A afe83faa + standing policy P2 adc12f36).
# Health/process metadata only; never opens a game outcome. Each subcommand is run and checked by hand, in order:
#   round.sh stop      PREVNS PREVPHASE            # owned STOP on both hosts, wait supervisor exits, 0 owned groups
#   round.sh drain     PREVNS PREVPHASE            # wait every listed block ACK-returned, STOP-COPY, copier exit+revoked
#   round.sh inventory N "NS1:PH1 NS2:PH2 ..."     # phase-meta copy, hub view, frozen replace.py -> replacement-rN.json
#   round.sh stage     N                           # fresh namespace k4s-confirm-replacement-rN + fresh qualification (detached)
#   round.sh finalize  N                           # qualification PASS, runtime==smoke runtime, carry-over, 03 idle pin, auth, barrier
#   round.sh launch    N                           # copiers then frozen launch.sh (via launch_phase.sh)
set -euo pipefail
L=/mpac/sdicks02/k4s-runner/run-r1
W=/mpac/sdicks02/repos/clasher-k4s-run
K=$W/reports/explore/k4s-confirm
declare -A ROOT=([127x03]=/mpac/sdicks02/jobs/clasher [127x04]=/mpac/sdicks02/jobs-k4s)
declare -A CORE=([127x03]=62 [127x04]=63)
HOSTS=(127x03 127x04)
cmd=${1:?}; shift
valid_ns(){ [[ "$1" =~ ^k4s-confirm-(reporting-r1|replacement-r[0-9]+)$ ]]; }
valid_ph(){ [[ "$1" =~ ^(reporting|replacement-r[0-9]+)$ ]]; }

case $cmd in
stop)
  NS=$1; PH=$2; valid_ns $NS; valid_ph $PH
  for H in "${HOSTS[@]}"; do J=${ROOT[$H]}/$NS
    ssh -o BatchMode=yes $H "test -e $J/$PH/launch.json && date -u +%FT%T.%3NZ > $J.STOP && echo $H STOP \$(cat $J.STOP)"
  done
  for H in "${HOSTS[@]}"; do J=${ROOT[$H]}/$NS
    ssh -o BatchMode=yes $H "S=\$(grep -o '\"supervisor_pid\": *[0-9]*' $J/$PH/launch.json | grep -o '[0-9]*\$'); for i in \$(seq 1 300); do kill -0 \$S 2>/dev/null || break; sleep 1; done; kill -0 \$S 2>/dev/null && { echo $H SUPERVISOR STILL ALIVE; exit 3; }; python3 -c \"import json;e=json.load(open('$J/$PH/supervisor-exit.json'));print('$H exit',e['utc'],e['reason'],'completed',len(e['completed']),'failed',len(e['failed']),'unstarted',len(e['unstarted']))\"; echo $H owned_groups \$(ps -eo pgid=,args= | grep -E '$J(/| |\$)' | grep -v -e grep -e 'echo ' | wc -l)"
  done ;;
drain)
  NS=$1; PH=$2; valid_ns $NS; valid_ph $PH
  for H in "${HOSTS[@]}"; do J=${ROOT[$H]}/$NS
    n=$(ssh -o BatchMode=yes $H "find $J/$PH -mindepth 2 -maxdepth 2 -name complete.json | wc -l")
    for i in $(seq 1 90); do
      ok=$(python3 -c "import json;h=json.load(open('$J/copy-health-$H.json'));print(1 if h.get('listed')==$n and h.get('ack_returned')==$n and not h.get('pending_return') else 0)")
      [ "$ok" = 1 ] && break; sleep 10
    done
    [ "$ok" = 1 ] || { echo "$H: ACKs not all returned ($n complete)"; exit 3; }
    P=$(python3 -c "import json;print(json.load(open('$J/owned-copier-admission.json'))['identity']['pid'])")
    date -u +%FT%TZ > $J/STOP-COPY
    for i in $(seq 1 120); do kill -0 $P 2>/dev/null || break; sleep 1; done
    kill -0 $P 2>/dev/null && { echo "$H copier $P still alive"; exit 3; }
    rm -f $J/STOP-COPY
    python3 -c "import json;h=json.load(open('$J/copy-health-$H.json'));r=json.load(open('$J/owned-copier-admission.json'));print('$H copier',$P,'acked',h['ack_returned'],'of',$n,'revoked',h.get('revoked'),'hub receipt active',r['active']);assert h.get('revoked') is True and r['active'] is False and not h.get('lifecycle_error')"
    ssh -o BatchMode=yes $H "grep -q '\"active\": false' $J/owned-copier-admission.json && echo $H source receipt inactive"
  done ;;
inventory)
  N=$1; PHASES=$2; [[ "$N" =~ ^[0-9]+$ ]]
  OUT=$L/dispatch/replacement-r$N.json; test ! -e $OUT
  SRC=()
  for np in $PHASES; do NS=${np%%:*}; PH=${np#*:}; valid_ns $NS; valid_ph $PH
    for H in "${HOSTS[@]}"; do J=${ROOT[$H]}/$NS; M=$L/phase-meta/$H-$NS-$PH; mkdir -p $M
      rsync -a --include='launch.json' --include='supervisor-exit.json' --include='stop-reason.json' --include='pids/***' --include='descriptors/***' --include='exits/***' --exclude='*' $H:$J/$PH/ $M/
      test -s $M/supervisor-exit.json; SRC+=($M)
    done
  done
  # hub view over every acknowledged hub block of every phase so far (ids are unique across phases)
  V=$L/hub-view/r$N; test ! -e $V; mkdir -p $V
  for H in "${HOSTS[@]}"; do for d in ${ROOT[$H]}/k4s-confirm-*/hub-blocks/{reporting,replacement-r*}/*/; do
    [ -e "$d/hub-ack.json" ] || continue; b=$(basename $d); test ! -e $V/$b || { echo "duplicate hub id $b"; exit 3; }; ln -s ${d%/} $V/$b
  done; done
  DIS=($L/dispatch/reporting-dispatch.json $(ls $L/dispatch/replacement-r*.json 2>/dev/null))
  (cd $K && nice -n 19 /bin/python3 -B replace.py --source-phases "${SRC[@]}" --dispatches "${DIS[@]}" --hub $V --ledger $L/ledger/blind-ledger.json --dispatch-out $OUT --hosts 127x03 127x04 --stop-file $L/ledger/STOP-replace)
  python3 - "$OUT" "$V" <<'EOF'
import json,sys,collections,glob,os
sys.path.insert(0,'/mpac/sdicks02/repos/clasher-k4s-run/reports/explore/k4s-confirm')
from schedule import canonical
L='/mpac/sdicks02/k4s-runner/run-r1';d=json.load(open(sys.argv[1]));rows=d['blocks']
for r in rows:canonical(r)
ev=json.load(open(L+'/ledger/blind-ledger.json'))['events']
counted={os.path.basename(p) for p in glob.glob(sys.argv[2]+'/*')}
logical=collections.Counter()
for b in counted:
 c=json.load(open(os.path.join(sys.argv[2],b,'complete.json')))['descriptor'];logical[c.get('replaces') or c['id']]+=1
for r in rows:logical[r['replaces'] or r['id']]+=1
want={f'primary-{i:04d}' for i in range(3000)}|{f'guard-{i:04d}' for i in range(900)}
kmax=collections.defaultdict(int)
for e in ev:
 rr=e['replacement'];kmax[rr['population']]=max(kmax[rr['population']],rr['replacement_k'])
print('rows',len(rows),'hosts',dict(collections.Counter(r['host'] for r in rows)),'games',sum(len(r['order']) for r in rows),'never_started',len(d['never_started_redispatched']))
print('ledger events',len(ev),dict(collections.Counter(e['lost']['population'] for e in ev)),'max k',dict(kmax))
print('counted',len(counted),'coverage exact',set(logical)==want and all(v==1 for v in logical.values()))
assert set(logical)==want and all(v==1 for v in logical.values())
EOF
  sha256sum $OUT $L/ledger/blind-ledger.json ;;
stage)
  N=$1; [[ "$N" =~ ^[0-9]+$ ]]; NS=k4s-confirm-replacement-r$N
  for H in "${HOSTS[@]}"; do B=${ROOT[$H]}; J=$B/$NS; S=$B/k4s-confirm-r1-stage
    EXTRA=""; [ $H = 127x04 ] && EXTRA="--base /mpac/sdicks02/jobs-k4s/k4s-prep-20261011/base-s1 --inherited-pin /mpac/sdicks02/jobs-k4s/k4s-prep-20261011/base-s1/s1-runtime-pin-r2.json"
    (cd $W && bash $K/export_staging_extras.sh $J /mpac/sdicks02/k4s-runner/stage/extras-$H-repl-r$N.tar >/dev/null)
    scp -q /mpac/sdicks02/k4s-runner/stage/extras-$H-repl-r$N.tar $H:$S/extras-repl-r$N.tar
    ssh -o BatchMode=yes $H "rm -rf $S/overlay-src; test ! -e $J && EXTRAS_TAR=$S/extras-repl-r$N.tar bash $S/stage_host.sh $J $S $EXTRA && cd $J/repo && sha256sum --quiet -c $S/frozen-overlay.sha256 && echo $H OVERLAY-OK && P=reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md && mkdir -p \$(dirname \$P) && cp $S/PREREG-K4S-DRAFT-r3.md \$P && test \$(sha256sum \$P | cut -c1-8) = 9650972d && bash reports/explore/k4s-confirm/detach.sh $J/qualification-driver.log $J/qualification-driver-pid.json env K4S_JOB=$J OWNED_STOP=$J.STOP NICE=10 bash reports/explore/k4s-confirm/run_qualification.sh"
  done ;;
finalize)
  N=$1; [[ "$N" =~ ^[0-9]+$ ]]; NS=k4s-confirm-replacement-r$N; DSP=$L/dispatch/replacement-r$N.json; test -s $DSP
  for H in "${HOSTS[@]}"; do B=${ROOT[$H]}; J=$B/$NS; SM=$B/k4s-confirm-r1
    ssh -o BatchMode=yes $H "test -e $J/QUALIFICATION-FINISHED"
    scp -q $H:$J/qualification-$H.json $L/receipts/replacement-r$N-qualification-$H.json
    ssh -o BatchMode=yes $H "python3 - <<'EOF'
import json
a=json.load(open('$J/runtime-pin.json'));b=json.load(open('$SM/runtime-pin.json'))
same={k:a[k]==b[k] for k in ('files','native_source','inputs','inherited_runtime_pin_sha256','plan_sha256')}
q=json.load(open('$J/qualification-$H.json'))
print('$H runtime==smoke',same,'qual',q['verdict'],q['utc'],sum(map(bool,q['checks'].values())),'/',len(q['checks']))
assert all(same.values()) and q['verdict']=='PASS' and all(q['checks'].values())
EOF
test ! -e $J/FROZEN-K4S.json && cp -a $SM/FROZEN-K4S.json $SM/SMOKE-PASS $SM/smoke-admission.json $J/ && test \$(sha256sum $J/FROZEN-K4S.json | cut -c1-8) = 416f6e51"
    scp -q $DSP $H:$J/replacement-r$N.json
    if [ $H = 127x03 ]; then ssh -o BatchMode=yes $H "cd $J/repo && K4S_JOB=$J nice -n 19 bash reports/explore/k4s-confirm/runtime.sh reports/explore/k4s-confirm/idle_services.py --job $J >/dev/null && python3 -c \"import json,sys;s=json.load(open('$J/idle-services.json'))['services'][0]['service'];print('03 idle pin',s['pid'],s['start_ticks']);sys.exit(0 if s['start_ticks']==139691386 and s['cmdline_sha256'].startswith('16152ceb') else 1)\""; fi
  done
  python3 - $N <<'EOF'
import json,hashlib,sys
N=sys.argv[1];L='/mpac/sdicks02/k4s-runner/run-r1'
def h(p):return hashlib.sha256(open(p,'rb').read()).hexdigest()
a=json.load(open(L+'/receipts/REPORTING-AUTHORIZATION.json'))
a['reporting_jobs']={'127x03':f'/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r{N}','127x04':f'/mpac/sdicks02/jobs-k4s/k4s-confirm-replacement-r{N}'}
a['phase']=f'replacement-r{N}';a['dispatch_path']=f'reports/explore/k4s-confirm/run-r1/dispatch/replacement-r{N}.json';a['dispatch_sha256']=h(f'{L}/dispatch/replacement-r{N}.json')
a['reporting_jobs_note']=dict(ruling='coordinator Option A (COORDINATOR.md afe83faa) + standing policy P2 (adc12f36): frozen replace.py rounds',original_dispatch_sha256='78335dc40094b404848088e55c287a536034e739c56789aa6f46af9a9b8af5b2',ledger_sha256=h(L+'/ledger/blind-ledger.json'))
json.dump(a,open(f'{L}/receipts/REPORTING-AUTHORIZATION-v-replacement-r{N}.json','w'),indent=2);print('auth',h(f'{L}/receipts/REPORTING-AUTHORIZATION-v-replacement-r{N}.json'))
EOF
  for H in "${HOSTS[@]}"; do J=${ROOT[$H]}/$NS
    scp -q $L/receipts/REPORTING-AUTHORIZATION-v-replacement-r$N.json $H:$J/REPORTING-AUTHORIZATION.json
    ssh -o BatchMode=yes $H "cd $J/repo && K4S_JOB=$J nice -n 19 bash reports/explore/k4s-confirm/runtime.sh -c \"from barrier import reporting_release;from pathlib import Path;m=reporting_release(Path('$J/repo'),Path('$J/FROZEN-K4S.json'),Path('$J/REPORTING-AUTHORIZATION.json'));print('$H BARRIER PASS',len(m['files']))\" && test ! -e $J/owned-supervisor-admission.json && echo $H fresh-slot who=\$(who | wc -l)"
  done ;;
launch)
  N=$1; [[ "$N" =~ ^[0-9]+$ ]]
  for H in "${HOSTS[@]}"; do K4S_JOBNAME=k4s-confirm-replacement-r$N bash $L/tools/launch_phase.sh $H replacement-r$N $L/dispatch/replacement-r$N.json ${CORE[$H]}; done ;;
*) echo "unknown subcommand" >&2; exit 2 ;;
esac
