"""Excluded-game capture construction after the honest decision timer."""
import copy
import numpy as np
from corpus import stratum

def capture_proposals(cached, action_mask, d1):
    # poll() populated this cache inside WINDOW. Reading it is not inference.
    assert cached.cache is not None and cached.cache[0] is d1
    assert np.array_equal(cached.cache[1], action_mask)
    return list(cached.cache[2])

def capture_row(p, R, info, reserved_packet, policy, cached, capture_before, arm, seed):
    core=copy.copy(p.core);core.rng=np.random.default_rng()
    core.rng.bit_generator.state=copy.deepcopy(capture_before['candidate_rng_state'])
    core.info=info;core.costs=R.costs;core.pending=capture_before['pending']
    core.opponent_elixir=policy.opponent_elixir
    proposals=() if cached is None else capture_proposals(cached, policy.mask, policy.player.last_d1)
    corpus_candidates,corpus_mask=core.candidates(reserved_packet,[v['action'] for v in proposals])
    if len([a for a in corpus_candidates if a!=2305])>1:
        posterior=copy.deepcopy(capture_before['belief_before'])
        posterior.update(info.tick,info.events,deadline=None)
        sample_rng=np.random.default_rng();sample_rng.bit_generator.state=copy.deepcopy(capture_before['belief_rng_state'])
        opponent=posterior.sample(sample_rng,deadline=None)
        root_rng_state=copy.deepcopy(sample_rng.bit_generator.state)
        root=R.root(info,opponent,sample_rng)
        elixir=float(info.own['elixir']);legal=int(np.count_nonzero(corpus_mask[:2304]))
        return dict(capture_before,id=f"{arm}/{seed}/{info.tick}",tier=arm.split('-')[0],seed=seed,info=copy.deepcopy(info),reserved_packet=copy.deepcopy(reserved_packet),opponent_elixir=core.opponent_elixir,d1=copy.deepcopy(policy.player.last_d1),root_rng_state=root_rng_state,root=root.snapshot(),root_digest=root.digest(),opponent=copy.deepcopy(opponent),strata=dict(elixir=elixir,legal_play_count=legal,bins=list(stratum(elixir,legal))))
    return None
