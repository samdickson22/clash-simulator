"""Render markdown tables for RESULTS.md from eval_val metrics.json and eval_events events.json files.

  python make_tables.py --frame NAME=metrics.json ... --events NAME=events.json ...
"""
import argparse
import json


def frame_rows(name, m):
    h, e, t, u = m['hand'], m['elixir'], m['towers'], m['units']
    best = lambda k, r: max(u[k][r].items(), key=lambda kv: kv[1]['f1'])
    idb, idr = best('identity_x_owner', 'r=1.0'); owb, owr = best('owner_only_all_visible', 'r=1.0')
    q = u['identity_x_owner']['r=0.25'][idb]; oq = u['owner_only_all_visible']['r=0.25'][owb]
    pt = t['per_tower']
    tw = lambda k: pt.get(k, {}).get('hp_mae_when_alive', float('nan'))
    return dict(name=name, frames=m['frames'], hand_slot=h['mean_4slots'], hand_next=h['next'], hand_all4=h['all4'],
                hand_steady=h.get('steady_state_slot_acc'), elixir_mae=e['mae'], elixir_int=e['exact_integer_acc'],
                elixir_steady=e.get('steady_state_integer_acc'), tower_mae=t['hp_mae_all_with_destroyed_as_0']['0.5'],
                tower_alive=t['alive_acc']['0.5'], king_mae=(tw('own_king_center')+tw('opp_king_center'))/2,
                princess_mae=sum(tw(k) for k in ('own_princess_left', 'own_princess_right', 'opp_princess_left', 'opp_princess_right'))/4,
                id_th=idb, id_p=idr['precision'], id_r=idr['recall'], id_f1=idr['f1'], id_q=(q['precision'], q['recall'], q['f1']),
                ow_th=owb, ow_p=owr['precision'], ow_r=owr['recall'], ow_f1=owr['f1'], ow_q=(oq['precision'], oq['recall'], oq['f1']),
                id05=u['identity_x_owner']['r=1.0']['0.5'], dist=u['mean_match_distance_tiles@0.5'])


def main():
    p = argparse.ArgumentParser(); p.add_argument('--frame', nargs='*', default=[]); p.add_argument('--events', nargs='*', default=[])
    a = p.parse_args()
    if a.frame:
        rows = [frame_rows(*x.split('=', 1)[0:1], json.load(open(x.split('=', 1)[1]))) for x in a.frame]
        print('| metric | ' + ' | '.join(r['name'] for r in rows)+' |'); print('|---|'+'---:|'*len(rows))
        fmt = lambda v: f'{v:.4f}' if isinstance(v, float) else str(v)
        for label, key in [('frames', 'frames'), ('hand acc / slot (4 slots)', 'hand_slot'), ('next-card acc', 'hand_next'),
                           ('all 4 slots correct', 'hand_all4'), ('hand acc / slot, steady state', 'hand_steady'),
                           ('elixir MAE', 'elixir_mae'), ('elixir exact integer', 'elixir_int'), ('elixir integer, steady state', 'elixir_steady'),
                           ('tower HP MAE (all, destroyed = 0)', 'tower_mae'), ('tower alive/destroyed acc', 'tower_alive'),
                           ('king tower HP MAE (alive)', 'king_mae'), ('princess tower HP MAE (alive)', 'princess_mae')]:
            print(f'| {label} | '+' | '.join(fmt(r[key]) for r in rows)+' |')
        for label, f in [('units id×owner ≤1 tile: best-F1 threshold', lambda r: r['id_th']),
                         ('  P / R / F1', lambda r: f"{r['id_p']:.3f} / {r['id_r']:.3f} / {r['id_f1']:.3f}"),
                         ('  same threshold, ≤¼ tile P / R / F1', lambda r: '%.3f / %.3f / %.3f' % r['id_q']),
                         ('  at score 0.5, ≤1 tile P / R / F1', lambda r: f"{r['id05']['precision']:.3f} / {r['id05']['recall']:.3f} / {r['id05']['f1']:.3f}"),
                         ('units owner-only ≤1 tile: threshold', lambda r: r['ow_th']),
                         ('  P / R / F1', lambda r: f"{r['ow_p']:.3f} / {r['ow_r']:.3f} / {r['ow_f1']:.3f}"),
                         ('  ≤¼ tile P / R / F1', lambda r: '%.3f / %.3f / %.3f' % r['ow_q']),
                         ('mean match distance (tiles, score 0.5)', lambda r: f"{r['dist']:.3f}")]:
            print(f'| {label} | '+' | '.join(str(f(r)) for r in rows)+' |')
    for x in a.events:
        name, path = x.split('=', 1); m = json.load(open(path))
        print(f'\n**{name}** ({m["matches"]} matches, {m["frames"]} processed frames at ~{m["approx_fps"]} FPS, {m["truth_events"]} events)\n')
        print('| fusion | thr | W | all P/R | opp P/R | opp spell P/R | opp troop+bldg P/R | own P/R | placement median / p90 / ≤1 tile | latency median |')
        print('|---|---|---|---|---|---|---|---|---|---|')
        for fus, key in (('tracker', 'tracker_metrics'), ('EventFusion', 'metrics')):
            if key not in m:
                continue
            for W in ('W=500ms', 'W=1000ms'):
                for th, v in m[key][W].items():
                    pr = lambda g: f"{v[g]['precision']:.3f}/{v[g]['recall']:.3f}"
                    print(f"| {fus} | {th} | {W[2:]} | {pr('all')} | {pr('opp')} | {pr('opp_spell')} | {pr('opp_troop_building')} | {pr('own')} | "
                          f"{v['all']['placement_median_tiles']} / {v['all']['placement_p90_tiles']} / {v['all']['within_1_tile']} | {v['all']['latency_median_ms']} |")


if __name__ == '__main__':
    main()
