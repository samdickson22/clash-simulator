"""Manifest of bot-played battles whose opponent deck had target non-C56 cards (labelling data for perception).

  python newcard_manifest.py --decks reports/live/loop/opponent-decks.jsonl --root /mpac/sdicks02/scratch/live-loop \
      --out reports/live/loop/newcard-manifest.jsonl

One row per battle (Battle Log inventory row with any target card): run, arena, the perception export that played it,
target cards, 05 paths (video/, frames.jsonl, perception.jsonl + whether live-logged or reconstructed), match length in
ticks, and crude `candidate_windows`. A window is a stretch where perception reported an OPPONENT unit whose identity is
not in that opponent's (C56 part of the) deck: an off-vocab troop shown as some C56 card (e.g. Spear Goblins read as
Goblins is not caught when the deck also has Goblins). Windows merge gaps < 2 s and are kept from 1 s. No names, no images.
"""
import argparse
import json
from pathlib import Path

TARGETS = ('SpearGoblins', 'Tombstone', 'Bomber', 'GoblinCage')


def find_dir(root, run):
    """05 location of a run: runs-all/<run> (logs), and the dir holding video/ (runs/<run>, runs/<sNmMM>, runs/<sN>/<mMM>)."""
    logs = root/'runs-all'/run
    cands = [root/'runs'/run, root/'runs'/run.replace('-', ''), logs]
    if '-m' in run:
        s, m = run.split('-', 1)
        cands.insert(0, root/'runs'/s/m)
    vid = next((c/'video' for c in cands if (c/'video').is_dir()), None)
    return logs if logs.is_dir() else None, vid


def windows(perc_path, opp_c56):
    rows = [json.loads(l) for l in open(perc_path)]
    hits = [r['tick'] for r in rows if any(u['owner'] == 1 and u.get('cls') not in opp_c56 and u.get('card') not in opp_c56
                                           for u in r.get('units', ()))]
    out, cur = [], None
    for t in hits:
        if cur and t - cur[1] <= 40:            # 2 s
            cur[1] = t
        else:
            if cur:
                out.append(cur)
            cur = [t, t]
    if cur:
        out.append(cur)
    return [[round(a), round(b)] for a, b in out if b - a >= 20]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--decks', required=True)
    ap.add_argument('--root', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    root = Path(a.root)
    rows = []
    for l in open(a.decks):
        r = json.loads(l)
        tg = sorted({c for c in r['opp_deck'] if c in TARGETS})
        if not tg or not r.get('run'):
            continue
        logs, vid = find_dir(root, r['run'])
        row = dict(run=r['run'], arena=r.get('arena'), result=r.get('result'), target_cards=tg,
                   opp_deck=r['opp_deck'], video_dir=str(vid) if vid else None,
                   frames=str(logs/'frames.jsonl') if logs and (logs/'frames.jsonl').exists() else None)
        if logs:
            cfg = json.loads((logs/'session-config.json').read_text()) if (logs/'session-config.json').exists() else {}
            row['perception_export'] = cfg.get('export_frame_sha256')
            row['perception_export_path'] = cfg.get('export')
            pj = logs/'perception.jsonl'
            if pj.exists():
                row['perception_jsonl'] = str(pj)
                row['perception_logged'] = cfg.get('logged', 'live')
                ticks = [json.loads(x)['tick'] for x in open(pj)]
                row['match_ticks'] = round(max(ticks)) if ticks else None
                opp_c56 = set(c for c in r['opp_deck'] if c not in TARGETS)
                row['candidate_windows'] = windows(pj, opp_c56)
            elif row['frames']:
                ticks = [json.loads(x).get('tick') for x in open(logs/'frames.jsonl')]
                ticks = [t for t in ticks if t is not None]
                row['match_ticks'] = round(max(ticks)) if ticks else None
        rows.append(row)
    with open(a.out, 'w') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')
    for row in rows:
        print(row['run'], row['target_cards'], 'video' if row['video_dir'] else 'NO-VIDEO',
              row.get('perception_logged'), row.get('match_ticks'), len(row.get('candidate_windows') or []), 'windows')


if __name__ == '__main__':
    main()
