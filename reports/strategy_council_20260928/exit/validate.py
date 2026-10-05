"""Checks for candidate gradients, stored histories and public planner isolation."""
from common import *
from fit import candidate_ce,student_kl,target_rows
from clasher.rl.imitation import load_corpus,_sequence_batch_inputs,_council_imitation_state,_imitation_evaluation_batches

class HiddenDenied:
    def __init__(self,p):self.p=p
    def __getattr__(self,key):
        if key in ('hand','deck','cycle_queue','elixir','next_card_refill_cooldown_ms','card_levels'):raise AssertionError(key)
        return getattr(self.p,key)
class RngDenied:
    def __getattr__(self,key):raise AssertionError('true RNG '+key)

def main():
    verify();ctx=Context();r=Resources(ctx);prior=json.loads(TRAIN_DECKS.read_text())
    checks={}
    for seat in (0,1):
        env,_=reset(ctx,'training',991113,seat)
        a=PublicPlanner(r,prior,seed=123,policy=True);action,mask=a.decide(observe(env,seat),0)
        original=env.battle.players[1-seat];rng=env.battle.rng
        env.battle.players[1-seat]=HiddenDenied(original);env.battle.rng=RngDenied()
        b=PublicPlanner(r,prior,seed=123,policy=True);action2,mask2=b.decide(observe(env,seat),0)
        assert action==action2 and a.last==b.last and np.array_equal(mask,mask2)
        env.battle.players[1-seat]=original;env.battle.rng=rng
    checks['public_denied_read_seats']=2
    probe=torch.randn(1,6,requires_grad=True)
    ce=candidate_ce(probe,torch.tensor([[1,3]]),torch.tensor([2]),torch.tensor([[.4,.6]]));ce.sum().backward()
    assert torch.equal(probe.grad[0,[0,2,4,5]],torch.zeros(4))
    assert abs(float(student_kl(probe,probe).sum()))<1e-7
    checks['candidate_gradient_and_kl']=True
    for path in sorted((HERE/'smoke').glob('game-*.npz')):
        _,a=load_corpus(path);rows,ids,scores,counts=target_rows(path)
        assert a['episode_starts'][0] and a['terminal_status'][-1]==1
        with np.load(path) as raw:
            assert np.array_equal(a['previous_actions'][1:],raw['submitted_actions'])
            assert np.all(raw['submitted_actions'][~a['expert_action_supervision_valid'][:-1]]==r.no_op)
        cache={}
        with torch.no_grad():
            for selected,_,output in _imitation_evaluation_batches(ctx.loaded.model,a,rows,batch_size=128,device=DEVICE,trim_entity_padding=True):
                for row,logits in zip(selected,output.joint_logits[:,0]):cache[int(row)]=logits
            chosen=int(rows[len(rows)//2]);chunk=np.arange(chosen,min(chosen+4,len(a['episode_ids'])))[None]
            state=_council_imitation_state(ctx.loaded.model,a,chunk,device=DEVICE,episode_offsets={int(a['episode_ids'][0]):0})
            inputs=_sequence_batch_inputs(a,chunk,DEVICE,trim_entity_padding=True,reset_memory=False)
            output=ctx.loaded.model(inputs,state).joint_logits[0,0]
            assert torch.allclose(output,cache[chosen],atol=1e-4,rtol=1e-5)
        checks[path.name]=dict(decisions=len(a['episode_ids'])-1,labels=len(rows),prefix_logit_max_delta=float((output-cache[chosen]).abs().max()))
    assert len(list((HERE/'smoke').glob('game-*.npz')))==2
    from evaluate import search_game
    for role in ('holdout','hog26'):
        records = [search_game({'initial':ctx,'student':ctx},{'initial':r,'student':r},
            dict(which='student',role=role,mode='h2h',style='search',game=g,seed=991117)) for g in (0,1)]
        assert sum(rec['score'] for rec in records)==1.
        assert records[0]['world_decks']==records[1]['world_decks']
        assert records[0]['ticks']==records[1]['ticks']
        checks['h2h_identical_policy_'+role]=dict(scores=[rec['score'] for rec in records],ticks=records[0]['ticks'])
    write_json(HERE/'validation.json',checks);log(checks)
if __name__=='__main__':main()
