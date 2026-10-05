"""Replay complete recorded games; truth is read only by this offline test."""
import argparse
import json
from pathlib import Path
import numpy as np

from derived_public_state import DerivedPublicState
from public_planner import Resources, observe
from support import Context, TRAIN_DECKS, cl_eval, maybe_silence_stdio
from clasher.rl.public_action_mask import PublicActionMaskInput

HERE=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',type=int,required=True);args=ap.parse_args()
    ctx=Context(); resources=Resources(ctx); prior=json.loads(TRAIN_DECKS.read_text())
    paths=sorted(p for p in (HERE/'superseded-v2/games').glob('*/*.json')
                 if json.loads(p.read_text())['spec']['game']<4)
    assert len(paths)==24
    results=[]
    for path in paths[args.worker::3]:
        record=json.loads(path.read_text());spec=record['spec'];seat=record['candidate_player'];other=1-seat
        env=ctx.envs(spec['role'],spec['seed'])[seat]
        decks=cl_eval._sample_paired_ordered_decks(*ctx.pools(spec['role']),matchup_seed=record['matchup_seed'])
        with maybe_silence_stdio(True):env.reset(seed=record['matchup_seed'],ordered_decks=decks if seat==0 else decks[::-1])
        belief=DerivedPublicState(prior,resources.costs)
        trace={row[0]:row[1] for row in record['trace']}
        n=elixir_errors=hand_known=hand_errors=cycle_known=cycle_errors=next_known=next_errors=0
        max_elixir_error=0.
        while True:
            info=observe(env,seat);belief.update(info.tick,info.history);derived=belief.derived()
            truth=env.battle.players[other]
            error=abs(belief.elixir_units/10000-truth.elixir)
            max_elixir_error=max(max_elixir_error,error);elixir_errors+=int(error>1e-8);n+=1
            if derived['hand'] is not None:
                hand_known+=1
                hand_errors+=int(sorted(derived['hand'],key=lambda x:x or '')!=sorted(truth.hand,key=lambda x:x or ''))
            if derived['cycle'] is not None:
                cycle_known+=1;cycle_errors+=int(tuple(truth.cycle_queue)!=derived['cycle'])
            if derived['next_card'] is not None:
                next_known+=1;next_errors+=int(truth.cycle_queue[0]!=derived['next_card'])
            for i,known in enumerate(derived['hand_slots_known']):
                if known: assert truth.hand[i]==derived['hand_slots'][i]
            for i,known in enumerate(derived['cycle_positions_known']):
                if known: assert truth.cycle_queue[i]==derived['cycle_positions'][i]
            own_mask=resources.mask_builder.build(PublicActionMaskInput.from_confidence_observation(info.packet))
            packet=observe(env,other).packet
            other_mask=resources.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
            action=trace.get(info.tick,resources.no_op)
            opponent=ctx.bot(spec['opponent']).select_action(packet)
            with maybe_silence_stdio(True):
                _,done,_=env.step({seat:action,other:opponent},pre_action_masks={seat:own_mask,other:other_mask})
            if done:break
        b=env.battle
        outcome='draw' if b.winner is None else 'win' if b.winner==seat else 'loss'
        hps=lambda s:[getattr(b.players[s],f'{name}_tower_hp') for name in ('left','right','king')]
        assert (b.tick,outcome,hps(seat),hps(other))==(record['ticks'],record['outcome'],record['candidate_tower_hp'],record['opponent_tower_hp'])
        result=dict(id=record['id'],decisions=n,ticks=b.tick,elixir_errors=elixir_errors,
            max_elixir_error=max_elixir_error,hand_determined=hand_known,hand_errors=hand_errors,
            cycle_determined=cycle_known,cycle_errors=cycle_errors,next_determined=next_known,next_errors=next_errors,
            full_recorded_game_parity=True,estimate_fallbacks=0)
        assert elixir_errors==hand_errors==cycle_errors==next_errors==0,result
        results.append(result)
        (HERE/'results'/f'derived-audit-{args.worker}.json').write_text(json.dumps(results,indent=2)+'\n')
        print(result,flush=True)


if __name__=='__main__':main()
