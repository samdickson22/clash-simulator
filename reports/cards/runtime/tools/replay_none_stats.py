"""Replay BOT LEAD game 2000024 without writing or sealing training shards.
Run from an isolated copy of BOT LEAD's repo-98f4e2b36313 with patched runtime.py.
The original ranking module must fail first; the patched module must finish the game.
"""
import argparse
import json
from pathlib import Path
import sys
import traceback
import types


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--baseline-script', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.repo))
    from bot.players.runtime import Runtime
    rt = Runtime(verify=True)
    from bot.fullpool.models import install
    install(rt, 'v1=/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/main02-fp.pt,R3a=/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/R3a-fp.pt')
    from bot.fullpool.banks import case, select
    from bot.exit.generate import make_any
    from bot.exit.label import LabelingPlayer
    from bot.players.ours import play_match
    from clasher.rl import c56_scripted
    spec = 'fullpool:11433651:freq=b53b02a1fde4'
    select(rt, spec)
    game = case(rt, 2000024, 2613058991490864, spec)
    student = 'student:/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/rl5-v10-fp.pt@0.5375'
    old = types.ModuleType('clasher.rl._none_stats_baseline')
    old.__package__ = 'clasher.rl'
    exec(compile(args.baseline_script.read_text(), str(args.baseline_script), 'exec'), old.__dict__)
    fixed = c56_scripted.ranked_actions
    out = dict(game=2000024, case=game, student=student, teacher='K4C-r16', beta=0.,
               opponent='self', no_sealing=True, runtime=str(rt.root), fullpool_policies=rt.fullpool_policies)
    for arm, fn in [('original', old.ranked_actions), ('patched', fixed)]:
        c56_scripted.ranked_actions = fn
        players = {s: LabelingPlayer(rt, make_any(rt, student), make_any(rt, 'K4C-r16'), beta=0.) for s in (0, 1)}
        try:
            result = play_match(rt, players, seed=game['seed'], decks=game['decks'])
            out[arm] = dict(result=result, counts={s: p.counts for s, p in players.items()},
                            rows_in_memory={s: len(p.rows) for s, p in players.items()})
        except BaseException as ex:
            out[arm] = dict(error=f'{type(ex).__name__}: {ex}', trace=traceback.format_exc())
        args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
        print(arm, out[arm].get('error', 'completed'), flush=True)
    c56_scripted.ranked_actions = fixed
    assert 'float()' in out['original'].get('error', '') and 'building_damage' in out['original']['trace'], out['original']
    assert 'error' not in out['patched'] and out['patched']['result']['terminal'], out['patched']


if __name__ == '__main__':
    main()
