"""Round 2: per-card unit recall and phantoms under a unit decode (plain threshold or UnitFilter), validation dump.
  python live/perception/r2/per_card_units.py DUMP_DIR OUT.json DECODE_JSON   (e.g. '{"hi":.5,"lo":.5}' or '{"hi":.5,"lo":.25,"nms":.6}')
"""
import json, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/'live/perception'))
from bot.live.real_replay import load_dump  # noqa: E402
from bot.live.empirical import _greedy  # noqa: E402
from unit_filter import UnitFilter  # noqa: E402


def main(dump, out, cfg):
    cfg = json.loads(cfg); tot, hit, fp = Counter(), Counter(), Counter(); frames = 0
    for f in sorted(Path(dump).glob('*.jsonl.gz')):
        _, rows = load_dump(f); flt = UnitFilter(**cfg)
        for r in rows:
            P_all = flt([u for u in r['units_lo'] if not u.get('effect') and not u.get('counted')])
            tr = r['truth']
            if tr.get('objects_stale'):
                continue
            frames += 1
            for owner in (0, 1):
                T = [u for u in tr['units'] if u['owner'] == owner]; P = [u for u in P_all if u['owner'] == owner]
                pairs = _greedy(P, T, 1.); used = {i for i, _, _ in pairs}
                for _, j, _ in pairs:
                    hit[T[j]['card']] += 1
                for t in T:
                    tot[t['card']] += 1
                for i, p in enumerate(P):
                    if i not in used:
                        fp[p['card']] += 1
    res = dict(decode=cfg, frames=frames, recall=sum(hit.values())/sum(tot.values()), fp_per_frame=sum(fp.values())/frames,
               per_card={c: dict(n=tot[c], recall=round(hit[c]/tot[c], 4), fp_per_1000_frames=round(1000*fp[c]/frames, 2)) for c in sorted(tot, key=lambda c: -tot[c])})
    Path(out).write_text(json.dumps(res, indent=1))
    print(json.dumps(dict(decode=cfg, recall=round(res['recall'], 4), fp_per_frame=round(res['fp_per_frame'], 4))))


if __name__ == '__main__':
    main(*sys.argv[1:4])
