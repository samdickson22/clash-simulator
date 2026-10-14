#!/bin/bash
# Local fault-injection tests for ro1-results-r2.sh (SOL-REVIEW-RO1-r1 #1-#3). No host contact; scratch under /dev/shm.
set -u
S=${1:-/mpac/sdicks02/k4s-runner/run-r1/end-staging/a4/ro1-results-r2.sh}
W=$(mktemp -d /dev/shm/ro1t2-XXXXXX); FAILS=0; HN=$(hostname -s)
BODY=$(python3 - "$S" <<'PY'
import sys,re
s=open(sys.argv[1]).read(); m=re.search(r"REMOTE='(.*?\nfail 0)'", s, re.S); print(m.group(1))
PY
)
REAL_CHMOD=$(command -v chmod); REAL_MKDIR=$(command -v mkdir); REAL_FIND=$(command -v find); REAL_LS=$(command -v ls); REAL_STAT=$(command -v stat)
mk(){ $REAL_CHMOD -R u+w $W/c 2>/dev/null; rm -rf $W/c $W/shim; $REAL_MKDIR -p $W/c/es $W/shim; }
shim(){ printf '#!/bin/bash\n%s\n' "$2" > $W/shim/$1; $REAL_CHMOD +x $W/shim/$1; }
body(){ local b=${BODY//\'\"\'\$P\'\"\'/\'$1\'}; printf '%s' "${b//\'\"\'\$H\'\"\'/\'$2\'}"; }
run(){ PATH=$W/shim:$PATH bash -c "$(body "$1" "${2:-$HN}")" 2>/dev/null; }
mode(){ $REAL_STAT -c %a "$1" 2>/dev/null || echo none; }
check(){ local name=$1 want=$2 got=$3 extra=${4:-ok}; if [ "$got" = "$want" ] && [ "$extra" = ok ]; then echo "PASS $name ($got)"; else echo "FAIL $name: want $want got $got $extra"; FAILS=$((FAILS+1)); fi; }
tok(){ grep -E '^__RC=[0-9]+$' | tail -1 | cut -d= -f2; }
P=$W/c/es
mk; $REAL_CHMOD a-w $P; o=$(run $P); check normal 0 "$(echo "$o" | tok)" "$([ "$(mode $P)" = 555 ] && [ "$(mode $P/results)" = 555 ] && [ -z "$($REAL_LS -A $P/results)" ] && echo ok || echo badmodes)"
o=$(run $P); check results-exists 93 "$(echo "$o" | tok)"
mk; $REAL_CHMOD a-w $P; check wrong-host 90 "$(run $P 127x99 | tok)"
mk; $REAL_MKDIR $W/c/real; ln -s $W/c/real $W/c/link; $REAL_CHMOD a-w $W/c/real; check symlink-leaf 91 "$(run $W/c/link | tok)"
mk; $REAL_MKDIR -p $W/c/a/es; ln -s $W/c/a $W/c/alias; $REAL_CHMOD a-w $W/c/a/es; check symlinked-ancestor 92 "$(run $W/c/alias/es | tok)"
mk; check writable-parent 94 "$(run $P | tok)"
mk; ln -s /tmp $P/results; $REAL_CHMOD a-w $P; check results-symlink 93 "$(run $P | tok)"
# #3 probe failures
mk; $REAL_CHMOD a-w $P; shim find 'exit 1'; check pre-find-fails 84 "$(run $P | tok)" "$([ ! -e $P/results ] && echo ok || echo created)"
mk; $REAL_CHMOD a-w $P; shim find "if [ \$# -gt 6 ]; then exit 1; fi; exec $REAL_FIND \"\$@\""; o=$(run $P); check post-find-fails 82 "$(echo "$o" | tok)" "$([ "$(mode $P)" = 555 ] && echo ok || echo parent-$(mode $P))"
mk; $REAL_CHMOD a-w $P; shim ls 'exit 2'; o=$(run $P); check ls-fails 83 "$(echo "$o" | tok)" "$([ "$(mode $P)" = 555 ] && echo ok || echo parent-$(mode $P))"
mk; $REAL_CHMOD a-w $P; shim stat 'exit 1'; check stat-fails 81 "$(run $P | tok)" "$([ ! -e $P/results ] && echo ok || echo created)"
# #1 chmod failures and signals
mk; $REAL_CHMOD a-w $P; shim chmod "case \"\$*\" in *'a-w -- '*/results) exit 1;; esac; exec $REAL_CHMOD \"\$@\""; o=$(run $P); check chmod-results-fails 97 "$(echo "$o" | tok)" "$([ "$(mode $P)" = 555 ] && echo ok || echo parent-$(mode $P))"
mk; $REAL_CHMOD a-w $P; shim chmod "case \"\$*\" in 'a-w -- $P') exit 1;; esac; exec $REAL_CHMOD \"\$@\""; o=$(run $P); check chmod-parent-fails-restore-fails 88 "$(echo "$o" | tok)" "$(echo "$o" | grep -q '^__CAUSE=98$' && echo ok || echo nocause)"
mk; $REAL_CHMOD a-w $P; shim chmod "case \"\$*\" in 'u+w -- $P') $REAL_CHMOD u+w -- $P; exit 1;; esac; exec $REAL_CHMOD \"\$@\""; o=$(run $P); check chmod-uw-fails 95 "$(echo "$o" | tok)" "$([ "$(mode $P)" = 555 ] && echo ok || echo parent-$(mode $P))"
mk; $REAL_CHMOD a-w $P; shim mkdir 'exit 1'; o=$(run $P); check mkdir-fails 96 "$(echo "$o" | tok)" "$([ "$(mode $P)" = 555 ] && echo ok || echo parent-$(mode $P))"
mk; $REAL_CHMOD a-w $P; shim mkdir "kill -TERM \$PPID; exec $REAL_MKDIR \"\$@\""; o=$(run $P); check term-after-enabling-writes 87 "$(echo "$o" | tok)" "$([ "$(mode $P)" = 555 ] && echo ok || echo parent-$(mode $P))"
for sig in INT HUP; do mk; $REAL_CHMOD a-w $P; shim mkdir "kill -$sig \$PPID; exec $REAL_MKDIR \"\$@\""; o=$(run $P); check $sig-after-enabling-writes 87 "$(echo "$o" | tok)" "$([ "$(mode $P)" = 555 ] && echo ok || echo parent-$(mode $P))"; done
# #2 local token parsing: a scratch copy with ssh and LOG replaced (the production log is never touched)
L=$W/local; $REAL_MKDIR -p $L; cp "$S" $L/s.sh; sed -i "s#/usr/bin/ssh #$L/ssh #; s#^LOG=.*#LOG=$L/log#" $L/s.sh; $REAL_CHMOD +x $L/s.sh
fake(){ printf '#!/bin/bash\n%s\n' "$1" > $L/ssh; $REAL_CHMOD +x $L/ssh; }
fake 'echo BEFORE x; echo __RC=0; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check token-ok 0 $?
fake 'echo "ssh: connect to host 127x03 port 22: Connection refused" >&2; exit 255'; $L/s.sh 127x03 >/dev/null 2>&1; check stale-log-token-ssh-fail 255 $? "$(grep -c '^__RC=0$' $L/log | grep -q '^[1-9]' && echo ok || echo nostale)"
fake 'echo __RC=0x; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check malformed-token 255 $?
fake 'echo __RC=0; echo __RC=0; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check two-tokens 255 $?
fake 'echo "  __RC=0"; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check unanchored-token 255 $?
fake 'echo __RC=97; exit 0'; $L/s.sh 127x03 >/dev/null 2>&1; check remote-refusal-propagates 97 $?
fake 'echo __RC=0; exit 1'; $L/s.sh 127x03 >/dev/null 2>&1; check token-with-ssh-nonzero 255 $?
$REAL_CHMOD -R u+w $W; rm -rf $W
echo "FAILS=$FAILS"; exit $FAILS
