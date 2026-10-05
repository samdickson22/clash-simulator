"""Resource-effect observer test; production amounts never come from balances."""
from pathlib import Path
import numpy as np
from clasher.battle import BattleState
from clasher.cards.elixir_collector import ElixirProduction
from clasher.data import CardDataLoader
from clasher.arena import Position
from clasher.rl.contract_v5 import champion_ability_cost
from stage2_matches import battle
from derived_public_state import DerivedPublicState, PublicEvent
from test_derived import assert_truth
from qualify import write

cards=['Elixir Collector','Heal','Knight','ArcherQueen','Skeletons','IceSpirit','Fireball','Log']
loader=CardDataLoader();costs={n:float(loader.get_card(n).mana_cost) for n in cards}
b=battle(dict(seed=880300,decks=[cards,cards[4:]+cards[:4]]),loader)
trackers=[DerivedPublicState(dict(decks=[dict(cards=cards)]),costs) for _ in (0,1)]
events=[[],[]];original=ElixirProduction._give
counts=dict(collector=0,ability=0,Heal=0,checks=0,hand_determined=0,cycle_determined=0)

def visible_production(entity,amount):
    # This is the public production/death animation event. The observer records
    # its announced amount and timestamp, never the hidden recipient balance.
    if entity.battle_state is b and amount>0 and not b.game_over:
        events[entity.player_id].append(PublicEvent(b.tick,'collector','Elixir Collector',amount));counts['collector']+=1
    original(entity,amount)

ElixirProduction._give=staticmethod(visible_production)
try:
    while not b.game_over:
        if b.tick%40==0:
            for seat in (0,1):
                if b.can_activate_champion_ability(seat):
                    assert b.activate_champion_ability(seat)
                    events[seat].append(PublicEvent(b.tick,'ability','ArcherQueen',champion_ability_cost('ArcherQueen',loader=loader)));counts['ability']+=1
                hand=b.players[seat].hand
                for name in sorted((n for n in hand if n),key=lambda n:(n!='Elixir Collector',hand.index(n))):
                    y=9.5 if seat==0 else 22.5
                    if name in ('Fireball','Log'):y=22.5 if seat==0 else 9.5
                    if b.deploy_card(seat,name,Position(4.5,y)):
                        events[seat].append(PublicEvent(b.tick,'card',name));counts['Heal']+=int(name=='Heal');break
        for seat in (0,1):
            trackers[seat].update(b.tick,events[seat]);h,c=assert_truth(trackers[seat],b,seat)
            counts['checks']+=1;counts['hand_determined']+=h;counts['cycle_determined']+=c
        b.step()
    for seat in (0,1):
        trackers[seat].update(b.tick,events[seat]);assert_truth(trackers[seat],b,seat)
finally:
    ElixirProduction._give=staticmethod(original)
assert counts['collector']>0 and counts['Heal']>0 and counts['ability']>0,counts
write(Path(__file__).resolve().parent/'collector.json',dict(complete=True,ticks=b.tick,elixir_error=0,**counts))
print(counts)
