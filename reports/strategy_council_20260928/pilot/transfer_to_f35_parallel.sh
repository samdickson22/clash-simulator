#!/bin/bash
# Parallel copy of the Clasher project to f35 (copy only; nothing deleted on the Mac). Re-run to resume.
set -u
SRC=/Users/sam/Desktop/code/clasher
DST=sdicks02@f35:/data2/sdicks02/repos/clasher/
P=${P:-8}
LOG=$SRC/reports/strategy_council_20260928/pilot/logs/transfer-to-f35-parallel.log
RS=/opt/homebrew/bin/rsync
SSH="ssh -T -o BatchMode=yes -o Compression=no -c aes128-gcm@openssh.com"
EX=(--exclude=/.venv/ --exclude=target/ --exclude='*.so' --exclude='*.dylib' --exclude=__pycache__/ --exclude=node_modules/ --exclude=.DS_Store)
cd $SRC
CH=$(mktemp)
{ find . -mindepth 1 -maxdepth 1 ! -name reports ! -name artifacts ! -name datasets ! -name .venv
  find reports -mindepth 1 -maxdepth 1 ! -name strategy_council_20260928
  find reports/strategy_council_20260928 -mindepth 1 -maxdepth 1 ! -name m0
  find reports/strategy_council_20260928/m0 -mindepth 1 -maxdepth 2
  find artifacts -mindepth 1 -maxdepth 4
  find datasets -mindepth 1 -maxdepth 2
} | sed 's|^\./||' | awk -F/ '{print NF"\t"$0}' | sort -rn | cut -f2 > $CH.all
# keep only chunks not nested inside another listed chunk
python3 - "$CH.all" > $CH <<'PY'
import sys
paths=[l.rstrip('\n') for l in open(sys.argv[1]) if l.strip()]
s=set(paths); out=[]
for p in paths:
    parts=p.split('/')
    if any('/'.join(parts[:i]) in s for i in range(1,len(parts))): continue
    out.append(p)
print('\n'.join(out))
PY
echo "$(date -u +%FT%TZ) start: $(wc -l < $CH) chunks, P=$P" >> $LOG
cat $CH | xargs -P $P -I{} $RS -aR --partial "${EX[@]}" -e "$SSH" --rsync-path=/usr/bin/rsync "./{}" $DST >> $LOG 2>&1
echo "$(date -u +%FT%TZ) parallel phase exit $?" >> $LOG
$RS -a --partial "${EX[@]}" -e "$SSH" --rsync-path=/usr/bin/rsync $SRC/ $DST >> $LOG 2>&1
echo "$(date -u +%FT%TZ) final sweep exit $?" >> $LOG
$RS -a --partial -e "$SSH" --rsync-path=/usr/bin/rsync --exclude='cp312cy/' --exclude='cp314/' --exclude='pypy/' --exclude='cy_base/' --exclude='cy_proto/' --exclude='cy_proto_c56/' --exclude='stage0-cython/' /Users/sam/.cache/clasher-engine-speed/ sdicks02@f35:/data2/sdicks02/repos/clasher-local-data/clasher-engine-speed/ >> $LOG 2>&1
echo "$(date -u +%FT%TZ) DONE" >> $LOG
