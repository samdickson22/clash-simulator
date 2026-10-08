#!/bin/bash
# GUARD (127x05 coordinator, 2026-10-08): the fleet hub 127x01 is now the authority for fleet trees.
# A push without --update overwrote sealed S1/Stage 6 files on 2026-10-08 01:39Z. Refuse unless explicitly authorized.
if [ "${CLASHER_FLEET_PUSH_AUTHORIZED:-}" != "127x05-coordinator" ]; then echo "refused: fleet push needs CLASHER_FLEET_PUSH_AUTHORIZED=127x05-coordinator (see COORDINATOR.md 2026-10-08)" >&2; exit 3; fi
# Copy the Clasher project from the Mac mini to the fleet hub (copy only; nothing deleted on the Mac). Re-run to resume.
# Tailscale on the fleet is userspace (~10-30 MB/s per node), so chunks run P-way in parallel.
set -u
HUB=${HUB:-127x02}
SRC=/Users/sam/Desktop/code/clasher
DST=$HUB:/mpac/sdicks02/repos/clasher/
P=${P:-6}
LOG=${LOG:-$SRC/reports/strategy_council_20260928/pilot/logs/transfer-to-fleet-$HUB.log}
RS=/opt/homebrew/bin/rsync
SSH="ssh -T -o BatchMode=yes -o Compression=no -o ControlMaster=no -c aes128-gcm@openssh.com"
EX=(--exclude=/.venv/ --exclude=target/ --exclude='*.so' --exclude='*.dylib' --exclude=__pycache__/ --exclude=node_modules/ --exclude=.DS_Store)
cd $SRC
CH=$(mktemp)
# code and run data first; bulky evidence (artifacts/) last
{ find . -mindepth 1 -maxdepth 1 ! -name reports ! -name artifacts ! -name datasets ! -name .venv
  find reports -mindepth 1 -maxdepth 1 ! -name strategy_council_20260928
  find reports/strategy_council_20260928 -mindepth 1 -maxdepth 1 ! -name m0
  find reports/strategy_council_20260928/m0 -mindepth 1 -maxdepth 2
  find datasets -mindepth 1 -maxdepth 2
} | sed 's|^\./||' > $CH.all
# keep only chunks not nested inside another listed chunk
python3 - "$CH.all" > $CH <<'PY2'
import sys
paths=[l.rstrip('\n') for l in open(sys.argv[1]) if l.strip()]
s=set(paths)
print('\n'.join(p for p in paths if not any('/'.join(p.split('/')[:i]) in s for i in range(1,p.count('/')+1))))
PY2
echo "$(date -u +%FT%TZ) start: $(wc -l < $CH) chunks, P=$P, hub=$HUB" >> $LOG
tr '\n' '\0' < $CH | xargs -0 -P $P -I{} $RS -aRz --partial "${EX[@]}" -e "$SSH" "./{}" $DST >> $LOG 2>&1
echo "$(date -u +%FT%TZ) parallel phase exit $?" >> $LOG
$RS -a --partial -e "$SSH" /Users/sam/.cache/clasher-engine-speed /Users/sam/.cache/clasher-native-reference/decoded-logic-1e505767 $HUB:/mpac/sdicks02/repos/clasher-local-data/ >> $LOG 2>&1
echo "$(date -u +%FT%TZ) local-data exit $?" >> $LOG
$RS -az --partial "${EX[@]}" -e "$SSH" $SRC/ $DST >> $LOG 2>&1
echo "$(date -u +%FT%TZ) final sweep exit $?" >> $LOG
$RS -an --itemize-changes "${EX[@]}" -e "$SSH" $SRC/ $DST > $LOG.verify 2>&1
echo "$(date -u +%FT%TZ) verify: $(grep -c '^[<>c.*]' $LOG.verify) differing entries" >> $LOG
echo "$(date -u +%FT%TZ) DONE" >> $LOG
