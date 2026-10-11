"""X4S2 qualification: every guard-population card resolves to a known card_action token in the
runtime builder (shared by v1 and R3a features), has a loader card definition, and round-trips
through card_name_for_token_id. No unknown-card fallback is allowed. Exploration, NEVER ADOPTABLE."""
import json, subprocess, sys
from pathlib import Path
import run


def main():
    run.initialize()
    cfg = json.loads((Path(run.__file__).parent/'plan.json').read_text())
    b = run.R.builder
    unknown = b.token_id(None)
    defs = b.loader.load_card_definitions()
    G = cfg['populations']['G']
    cards = sorted({c for d in G['own_decks']+G['opponent_decks'] for c in d})
    rows = []
    for c in cards:
        tid = b.token_id(c, namespace='card_action')
        rows.append(dict(card=c, token=int(tid), roundtrip=b.card_name_for_token_id(tid), defined=c in defs))
        assert tid != unknown and rows[-1]['defined'], rows[-1]
    out = dict(utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(), cards=rows,
               unknown_token=int(unknown), label='X4S2 exploration, NEVER ADOPTABLE')
    Path(sys.argv[1]).write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps([(r['card'], r['token'], r['roundtrip']) for r in rows]))


if __name__ == '__main__':
    main()
