#!/bin/bash
# Local fault-injection tests for pf4-swap-preflight.sh (no host contact; scratch under /dev/shm). The remote body is
# extracted from the script and run with test constants substituted; the local part runs from a scratch copy with a
# fake ssh, a scratch LOG and a scratch SRC/NEW pin (the production log and files are never touched).
set -u
S=${1:-/mpac/sdicks02/k4s-runner/run-r1/end-staging/a4/pf4-swap-preflight.sh}
W=$(mktemp -d /dev/shm/pf4t-XXXXXX); FAILS=0; HN=$(hostname -s)
BODY=$(python3 - "$S" <<'PY'
import sys,re
s=open(sys.argv[1]).read(); m=re.search(r"REMOTE='(.*?\nfail 0)'", s, re.S); print(m.group(1))
PY
)
RC=$(command -v chmod); RM=$(command -v mkdir); RS=$(command -v sha256sum); RST=$(command -v stat); RMV=$(command -v mv); RCAT=$(command -v cat); RF=$(command -v find)
printf 'OLD preflight bytes\n' > $W/old; printf 'NEW preflight bytes r7\n' > $W/new; printf 'TAMPERED bytes\n' > $W/bad
OS=$($RS < $W/old | cut -c1-64); OZ=$($RST -c %s $W/old); NS=$($RS < $W/new | cut -c1-64); NZ=$($RST -c %s $W/new)
mk(){ $RC -R u+w $W/c 2>/dev/null; rm -rf $W/c $W/shim; $RM -p $W/c/tools $W/shim; cp $W/old $W/c/tools/k4s_end_preflight.py; $RC 0444 $W/c/tools/k4s_end_preflight.py; $RC a-w $W/c/tools; }
shim(){ printf '#!/bin/bash\n%s\n' "$2" > $W/shim/$1; $RC +x $W/shim/$1; }
body(){ local b=$BODY; b=${b//\'\"\'\$T\'\"\'/\'$1\'}; b=${b//\'\"\'\$H\'\"\'/\'${2:-$HN}\'}; b=${b//\'\"\'\$OLD_SHA\'\"\'/\'$OS\'}; b=${b//\'\"\'\$OLD_SIZE\'\"\'/\'$OZ\'}; b=${b//\'\"\'\$NEW_SHA\'\"\'/\'$NS\'}; b=${b//\'\"\'\$NEW_SIZE\'\"\'/\'$NZ\'}; printf '%s' "$b"; }
run(){ local t=$1 h=${2:-$HN} in=${3:-$W/new}; PATH=$W/shim:$PATH bash -c "$(body "$t" "$h")" < "$in" 2>/dev/null; }
tok(){ grep -E '^__RC=[0-9]+$' | tail -1 | cut -d= -f2; }
check(){ local name=$1 want=$2 got=$3 extra=${4:-ok}; if [ "$got" = "$want" ] && [ "$extra" = ok ]; then echo "PASS $name ($got)"; else echo "FAIL $name: want $want got $got $extra"; FAILS=$((FAILS+1)); fi; }
T=$W/c/tools; F=$T/k4s_end_preflight.py; N=$T/.k4s_end_preflight.py.pf4-new
state(){ local want=$1; local f=$($RS < $F | cut -c1-64); local fm=$($RST -c %a $F); local tm=$($RST -c %a $T); local nx=$([ -e $N ] && echo y || echo n)
  local wf=$([ "$want" = new ] && echo $NS || echo $OS); [ "$f" = "$wf" ] && [ "$fm" = 444 ] && [ "$tm" = 555 ] && [ "$nx" = n ] && echo ok || echo "file=${f:0:8} fmode=$fm tmode=$tm temp=$nx"; }
mk; check normal 0 "$(run $T | tok)" "$(state new)"
mk; check wrong-host 90 "$(run $T 127x99 | tok)" "$(state old)"
mk; ln -s $T $W/c/tlink; check tools-symlink 91 "$(run $W/c/tlink | tok)" "$(state old)"
mk; ln -s $W/c $W/calias; check symlinked-ancestor 92 "$(run $W/calias/tools | tok)" "$(state old)"
mk; $RC u+w $T; ln $F $W/c/hard; $RC a-w $T; check old-hardlink 93 "$(run $T | tok)"
mk; $RC u+w $T; rm $F; ln -s $W/old $F; $RC a-w $T; check old-symlink 93 "$(run $T | tok)"
mk; $RC u+w $T $F; printf 'OLD preflight bytez\n' > $F; $RC 0444 $F; $RC a-w $T; check old-wrong-sha 94 "$(run $T | tok)"
mk; shim stat "case \"\$*\" in *'%s'*) echo 1;; *) exec $RST \"\$@\";; esac"; check old-wrong-size 95 "$(run $T | tok)" "$(state old)"
mk; $RC u+w $T; touch $N; $RC a-w $T; check temp-exists 96 "$(run $T | tok)"
mk; $RC u+w $T; check tools-writable 97 "$(run $T | tok)"
mk; shim find 'exit 1'; check find-fails 84 "$(run $T | tok)" "$(state old)"
mk; shim chmod "case \"\$*\" in 'u+w -- '*) exit 1;; esac; exec $RC \"\$@\""; check chmod-uw-fails 70 "$(run $T | tok)" "$(state old)"
mk; shim cat "head -c 3; exit 1"; check cat-fails 71 "$(run $T | tok)" "$(state old)"
mk; check new-wrong-sha 74 "$(run $T $HN $W/bad | tok)" "$(state old)"
mk; shim sha256sum "case \"\$*\" in *pf4-new*) exit 1;; esac; exec $RS \"\$@\""; check new-sha-probe-fails 73 "$(run $T | tok)" "$(state old)"
mk; shim mv 'exit 1'; check mv-fails 76 "$(run $T | tok)" "$(state old)"
mk; shim cat "kill -TERM \$(ps -o ppid= -p \$PPID); exec $RCAT"; check term-during-write 87 "$(run $T | tok)" "$(state old)"
mk; shim cat "kill -HUP \$(ps -o ppid= -p \$PPID); exec $RCAT"; check hup-during-write 87 "$(run $T | tok)" "$(state old)"
mk; shim mv "kill -INT \$PPID; exec $RMV \"\$@\""; o=$(run $T); check int-after-mv 87 "$(echo "$o" | tok)" "$(state new)"
mk; shim chmod "case \"\$*\" in 'a-w -- '*/tools) exit 1;; esac; exec $RC \"\$@\""; o=$(run $T); check chmod-aw-tools-fails-restore-fails 88 "$(echo "$o" | tok)" "$(echo "$o" | grep -q '^__CAUSE=77$' && echo ok || echo nocause)"
mk; shim chmod "case \"\$*\" in 'a-w -- '*/tools) exit 1;; esac; exec $RC \"\$@\""; shim mkdir "exit 0"; o=$(env SHELLOPTS=braceexpand:errexit:hashall:interactive-comments:nounset PATH=$W/shim:$PATH bash -c "$(body $T)" < $W/new 2>/dev/null); check errexit-restore-fails 88 "$(echo "$o" | tok)"
mk; shim cat "kill -TERM \$(ps -o ppid= -p \$PPID); exec $RCAT"; o=$(env SHELLOPTS=braceexpand:errexit:hashall:interactive-comments:nounset PATH=$W/shim:$PATH bash -c "$(body $T)" < $W/new 2>/dev/null); check errexit-term-during-write 87 "$(echo "$o" | tok)" "$(state old)"
# local side (scratch copy: fake ssh, scratch LOG, SRC and NEW pins)
L=$W/local; $RM -p $L; cp "$S" $L/s.sh; cp $W/new $L/new.py
sed -i "s#/usr/bin/ssh #$L/ssh #; s#^LOG=.*#LOG=$L/log#; s#^SRC=.*#SRC=$L/new.py#; s#^NEW_SHA=__NEW_SHA__; NEW_SIZE=__NEW_SIZE__#NEW_SHA=$NS; NEW_SIZE=$NZ#; s#^NEW_SHA=[0-9a-f]*; NEW_SIZE=[0-9]*#NEW_SHA=$NS; NEW_SIZE=$NZ#" $L/s.sh; $RC +x $L/s.sh
fake(){ printf '#!/bin/bash\n%s\n' "$1" > $L/ssh; $RC +x $L/ssh; }
fake 'cat >/dev/null; echo __RC=0; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check local-ok 0 $?
fake 'cat > '"$L"'/stdin; printf "%s\n" "$@" > '"$L"'/argv; echo __RC=0; exit 0'; $L/s.sh 127x04 >/dev/null 2>&1; check local-stdin-is-new 0 $? "$(cmp -s $L/stdin $W/new && grep -q '^env -u BASH_ENV -u SHELLOPTS nice -n 19 /bin/bash -c ' $L/argv && echo ok || echo bad)"
fake 'echo "ssh: connect failed" >&2; exit 255'; $L/s.sh 127x03 >/dev/null 2>&1; check stale-log-ssh-fail 255 $?
for t in 256 999 007 x; do fake "cat >/dev/null; echo __RC=$t; exit 0"; $L/s.sh 127x03 >/dev/null 2>&1; check token-$t 255 $?; done
fake 'cat >/dev/null; echo __RC=0; echo __RC=0; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check two-tokens 255 $?
fake 'cat >/dev/null; echo __RC=94; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check remote-refusal-propagates 94 $?
printf 'changed\n' >> $L/new.py; rm -f $L/called; fake 'touch '"$L"'/called; cat >/dev/null; echo __RC=0; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check local-src-mismatch-refuses-before-login 2 $? "$([ ! -e $L/called ] && echo ok || echo ssh-called)"
$L/s.sh 127x99 >/dev/null 2>&1; check bad-host-arg 2 $?
$RC -R u+w $W; rm -rf $W
echo "FAILS=$FAILS"; exit $FAILS
