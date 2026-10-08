"""In-process adapter for the unmodified clasher.rl.eval/P16 protocol.

Only policy loading/stepping and reset event capture are substituted. Legacy
policies retain their native model, mask, recurrence and random seed behavior.
"""
from contextlib import contextmanager
from types import SimpleNamespace
import torch
from .paths import setup, COUNCIL
setup()
from .events import PublicRecorder
from .standalone import StandalonePlayer
from imitation.model import load_policy
from clasher.rl.contract_v5 import ContractV5ObservationBuilder


@contextmanager
def installed(checkpoint, reference, *, fixed_world=False):
    from clasher.rl import eval as ev
    from clasher.rl.selfplay_env import SelfPlayBattleEnv
    policy = load_policy(checkpoint)
    builder = ContractV5ObservationBuilder()
    costs = {n: float(builder.loader.get_card(n).mana_cost)
             for n in builder.loader.load_card_definitions()
             if builder.loader.get_card(n).mana_cost is not None}
    original_load, original_step, original_reset = ev.load_policy_checkpoint, ev._policy_step, SelfPlayBattleEnv.reset
    # The protocol environment and scripts keep the comparator's P16/v4 builder.
    # Only the imitation actor observes through the independent v5 builder.
    legacy = original_load(reference, device=torch.device('cpu'), decks_path=COUNCIL/'m0/data/roles_v2/training.json')
    facade = SimpleNamespace(builder=legacy.builder, checkpoint={'adapter': 'imitation-v5'},
        model=SimpleNamespace(config=legacy.model.config, initial_state=lambda *a, **k: (torch.zeros(1), torch.zeros(1))))
    from pathlib import Path
    expected = Path(checkpoint).resolve()
    with PublicRecorder(builder) as recorder:
        players = {}
        def reset(env, *a, **kw):
            if fixed_world and env.learner_player_id == 1 and kw.get('ordered_decks'):
                kw['ordered_decks'] = tuple(reversed(kw['ordered_decks']))
            result = original_reset(env, *a, **kw)
            recorder.bind(env.battle)
            players.clear()
            for seat in (0, 1):
                own = env.battle.players[seat]
                players[seat] = StandalonePlayer(policy, builder, costs, seat,
                    list(own.hand)+list(own.cycle_queue), int(kw['seed'])+271828+seat)
            return result
        def load(path, **kw):
            return facade if Path(path).resolve() == expected else original_load(path, **kw)
        def step(loaded, env, player_id, **kw):
            if loaded is not facade:
                return original_step(loaded, env, player_id, **kw)
            if kw['deterministic']:
                raise ValueError('gate (c) requires stochastic T=1')
            if env.decision_interval_ticks != 5:
                raise ValueError('gate (c) requires 5 ticks')
            packet = builder.build_public(env.battle, player_id)
            action, mask = players[player_id].decide(env.battle.tick, packet, recorder.public_events)
            return action, kw['state'], mask, None
        ev.load_policy_checkpoint, ev._policy_step, SelfPlayBattleEnv.reset = load, step, reset
        try:
            yield ev
        finally:
            ev.load_policy_checkpoint, ev._policy_step, SelfPlayBattleEnv.reset = original_load, original_step, original_reset


def main():
    import sys
    checkpoint = sys.argv[sys.argv.index('--checkpoint')+1]
    index = sys.argv.index('--reference-checkpoint')
    reference = sys.argv[index+1]
    del sys.argv[index:index+2]
    fixed = '--fixed-world' in sys.argv
    if fixed: sys.argv.remove('--fixed-world')
    with installed(checkpoint, reference, fixed_world=fixed) as ev:
        ev.main()


if __name__ == '__main__':
    main()
