"""Opt-in Stage6 action metadata using unchanged Python/native C56 scoring.

The default controllers and admitted extension keep their original scope.
This development adapter only accepts cards covered by incremental core gates.
"""
import copy
import json

import clasher_core
from c56_controller import CARDS, STYLES, metadata
from clasher.dynamic_spells import create_spell_from_json
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent

EARLY = ('SpearGoblins', 'GoblinCage', 'Bomber', 'Tombstone', 'Barbarians',
         'BattleRam', 'MegaMinion', 'Witch', 'Pekka', 'GiantSkeleton',
         'SkeletonDragons', 'Mortar', 'DartBarrell', 'SkeletonWarriors',
         'RoyalGiant', 'ThreeMusketeers', 'RoyalRecruits',
         'Snowball', 'Freeze', 'BattleHealer',
         'Hunter', 'ElectroWizard', 'IceWizard', 'AxeMan',
         'GiantBuffer', 'GoblinDemolisher', 'RamRider', 'GoblinGiant', 'Monk',
         'Ronin', 'MergeMaiden_Normal', 'LittlePrince', 'GoblinMachine')
BLOCKED_CONTROLLER_CARDS = frozenset({'ThreeMusketeers'})
CONTROLLER_CARDS = tuple(c for c in EARLY if c not in BLOCKED_CONTROLLER_CARDS)


def resources(cards=CONTROLLER_CARDS):
    if set(cards) & BLOCKED_CONTROLLER_CARDS:
        raise ValueError('Python controller crashes on visible ThreeMusketeers; see python-issues.json')
    if not set(cards) <= set(CONTROLLER_CARDS):
        raise ValueError('card outside the Stage6 qualified development roster')
    builder = ContractV5ObservationBuilder()
    bots = {style: PublicScriptedOpponent(builder, style=style, card_scope='c56')
            for style in STYLES}
    for name in cards:
        stats = copy.copy(builder.loader.get_card(name))
        if stats is None or stats.level != 11:
            raise ValueError('Stage6 controller requires level11 base cards')
        token = builder.token_id(name, namespace='card_action')
        for bot in bots.values():
            bot.cards[token] = (name, stats)
            if str(stats.card_type).lower() == 'spell':
                bot.spells[name] = create_spell_from_json(stats._raw_entry, level=11)
    meta = metadata(builder, bot=bots['balanced'], action_cards=(*CARDS,*cards))
    return builder, meta, clasher_core.NativeScripts(json.dumps(meta)), bots
