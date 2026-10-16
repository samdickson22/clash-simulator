"""Exact G1 game 5000110; memory-only labels, no sealing/shard writes."""
import argparse
import json
from pathlib import Path
import sys
import traceback


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--expect-error',action='store_true')
    a=ap.parse_args()
    sys.path.insert(0,str(a.repo))
    from bot.players.runtime import Runtime
    rt=Runtime(verify=True)
    from bot.fullpool.models import install
    install(rt,'v1=/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/main02-fp.pt,R3a=/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/R3a-fp.pt')
    from bot.fullpool.banks import case,select
    from bot.exit.generate import make_any
    from bot.exit.label import LabelingPlayer
    from bot.players.ours import play_match
    spec='fullpool:11433651:freq=b53b02a1fde4'
    select(rt,spec)
    game=case(rt,5000110,2613058991490864,spec)
    student='student:/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/rl5-v10-fp.pt@0.5375'
    opp=['R3a','v1','self'][5000110%3]
    def labeller():return LabelingPlayer(rt,make_any(rt,student),make_any(rt,'K4C-r16'),beta=0.)
    players={game['seat']:labeller()}
    players[1-game['seat']]=labeller() if opp=='self' else make_any(rt,opp)
    out=dict(game=5000110,case=game,student=student,teacher='K4C-r16',beta=0.,opponent=opp,
             no_sealing=True,runtime=str(rt.root),fullpool_policies=rt.fullpool_policies)
    out['template_keys']={f'{token}/{kind}':rt.R.builder.token_names[token] for token,kind in rt.R.templates}
    try:
        out['result']=play_match(rt,players,seed=game['seed'],decks=game['decks'])
        out['counts']={s:p.counts for s,p in players.items() if hasattr(p,'rows')}
        out['rows_in_memory']={s:len(p.rows) for s,p in players.items() if hasattr(p,'rows')}
    except BaseException as e:
        out.update(error=f'{type(e).__name__}: {e}',trace=traceback.format_exc())
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(out.get('error',out.get('result')),flush=True)
    if a.expect_error:assert 'BarbarianRageDamage/AreaEffect' in out.get('error',''),out
    else:assert 'error' not in out and out['result']['terminal'],out


if __name__=='__main__':main()
