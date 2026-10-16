#!/usr/bin/env bash
# On a host, in a staged tree: everything G1/K1 need, end to end on real inputs, before any big launch.
#   ROOT=<root> [PINS=live16402] [OWN=full|c56] bot/fullpool/run/preflight.sh OUT
# 1 root receipt + native sha; 2 meta tokens under PINS vs the r1-cards1 dump the K4L nets were extended with;
# 3 extended checkpoint receipts; 4 one G1 game (generate, K4C-r16 teacher) and one K1 game (lopp_record).
set -uo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
OUT=${1:?OUT}; mkdir -p "$OUT"; fail=0
echo "preflight $(date -u +%FT%TZ) tree $(cat STAGED-REV 2>/dev/null) root $ROOT pins $PINS own $OWN decks $DECKS"
ls "$ROOT"/*RECEIPT*.json 2>/dev/null && sha256sum "$ROOT"/*RECEIPT*.json; sha256sum "$ROOT/native/clasher_core.abi3.so"
nice -n 15 $PY -B -m bot.fullpool.extend meta-tokens --out "$OUT/meta.json" > "$OUT/meta.log" 2>&1 || { echo "FAIL meta-tokens"; fail=1; }
$PY - "$OUT/meta.json" "$J/meta/r1-cards1-meta.json" <<'PYEOF' || fail=1
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
tok = {k for k in a if k in b and a[k]['token'] != b[k]['token']}
print(f'meta: {len(a)} cards; token diffs vs r1-cards1 dump: {sorted(tok)}; only here: {sorted(set(a) - set(b))}; missing: {sorted(set(b) - set(a))}')
if tok or set(b) - set(a):
    print('FAIL meta tokens differ: re-extend the K4L nets (bot.fullpool.extend lopp --meta <this meta.json>)'); sys.exit(1)
PYEOF
$PY - "$EXT" <<'PYEOF' || fail=1
import sys
from bot.fullpool.models import verified
pins = dict(main02='d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed',
            R3a='37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85',
            **{'rl5-v10': 'e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19'})
for name, pin in pins.items():
    verified(f'{sys.argv[1]}/{name}-fp.pt', pin); print('ok', name)
PYEOF
nice -n 15 $PY -B -m bot.exit.generate --out "$OUT/g1" --student "$STUDENT" --teacher K4C-r16 --pool R3a --games 1 \
  --workers 1 --start 99000000 --base "$TRAIN_BASE" --decks "$DECKS" > "$OUT/g1.log" 2>&1 || fail=1
nice -n 15 $PY -B -m bot.search.lopp_record --out "$OUT/k1" --candidate K4C-r16 --opponents "$STUDENT" --games 1 \
  --workers 1 --start 99000 --base $((TRAIN_BASE + 50000000)) --decks "$DECKS" > "$OUT/k1.log" 2>&1 || fail=1
$PY - "$OUT" <<'PYEOF' || fail=1
import json, sys
from pathlib import Path
out = Path(sys.argv[1]); bad = 0
for arm in ('g1', 'k1'):
    rows = [json.loads(l) for p in sorted((out / arm).glob('games-*.jsonl')) for l in p.read_text().splitlines() if l.strip()]
    errs = [r for r in rows if 'error' in r]
    print(arm, 'games', len(rows), 'errors', len(errs), [r['error'][:300] for r in errs][:2],
          {k: rows[0].get(k) for k in ('shards', 'rec_rows', 'rec_errors', 'belief_rebuilds') if rows and k in rows[0]})
    bad += len(errs) or not rows
sys.exit(1 if bad else 0)
PYEOF
[ $? -eq 0 ] || fail=1
echo "PREFLIGHT $([ $fail = 0 ] && echo PASS || echo FAIL) $(date -u +%FT%TZ)"
exit $fail
