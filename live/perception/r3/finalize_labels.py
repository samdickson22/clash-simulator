"""Round 3: verified label set = helper labels + verifier exclusions (camera not on the battle grid).

  python finalize_labels.py RAW_DIR OUT_DIR
"""
import json
import sys
from pathlib import Path

VERIFIER_EXCLUDE = {  # id -> reason (checked by the round-3 owner)
    'TC-tc2-000260': 'intro camera (zoomed out): grid does not apply',
    'TC-tc2-000870': 'game-end camera shift',
    'TC-tc2-001560': 'game-end camera shift',
    'TC-tc2-001590': 'game-end camera shift (0.5-2 tiles off)',
    'GS-live1-000803': 'end-of-game screen (crown banner, view shifted)',
    'GS-live4-000370': 'translucent placement preview on the bridge (ambiguous truth)',
}

VERIFIER_RELABEL = {  # (id, card, x, y) -> new card; cross-helper reconciliation
}
# Battle Log decks (newcard-manifest) list GoblinHut and no Barbarian Hut for these battles; the "barbarian" seen at s1m01-752 is a
# spear goblin from the hut (nc-eval1). So every OOV:BarbarianHut there is the Goblin Hut (an earlier verifier relabel was wrong).
DECK_RELABEL = {('BP-s1m01', 'OOV:BarbarianHut'): 'GoblinHut', ('BP-s2m01', 'OOV:BarbarianHut'): 'GoblinHut',
                ('BP-s5m01', 'OOV:BarbarianHut'): 'GoblinHut'}

raw, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
n = dict(frames=0, excluded=0, units=0)
for f in sorted(raw.glob('*.json')):
    d = json.loads(f.read_text())
    if d['id'] in VERIFIER_EXCLUDE:
        d['exclude'] = True; d['exclude_reason'] = 'verifier: '+VERIFIER_EXCLUDE[d['id']]
    for u in d['units']:
        new = VERIFIER_RELABEL.get((d['id'], u['card'], u['x'], u['y'])) or DECK_RELABEL.get((d['id'].rsplit('-', 1)[0], u['card']))
        if new:
            u['note'] = (u.get('note', '')+f" [verifier: relabelled {u['card']} -> {new}]").strip(); u['card'] = new
    n['frames'] += 1; n['excluded'] += bool(d.get('exclude'))
    n['units'] += 0 if d.get('exclude') else len(d['units'])
    (out/f.name).write_text(json.dumps(d, indent=1))
print(json.dumps(n))
