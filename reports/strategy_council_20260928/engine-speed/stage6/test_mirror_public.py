"""Mirror mask and candidate scoring use only accepted own public history."""
import copy
import json
import unittest

import clasher_core
from c56_controller import CARDS, metadata, verify
from controller import CONTROLLER_CARDS, resources
from clasher.dynamic_spells import create_spell_from_json
from differential import Position, config, initial, snapshot


class MirrorPublic(unittest.TestCase):
    def test_resolved_mask_and_static_script_scores_before_and_after_mirror(self):
        builder, _, _, bots = resources()
        stats = copy.copy(builder.loader.get_card('Mirror'))
        token = builder.token_id('Mirror', namespace='card_action')
        for bot in bots.values():
            bot.cards[token] = ('Mirror', stats)
            bot.spells['Mirror'] = create_spell_from_json(stats._raw_entry, level=11)
        meta = metadata(builder, bot=bots['balanced'],
                        action_cards=(*CARDS, *CONTROLLER_CARDS, 'Mirror'))
        scripts = clasher_core.NativeScripts(json.dumps(meta))
        for card in ('Knight', 'Cannon', 'GoblinDrill', 'Fireball', 'Rage', 'Clone', 'ElixirGolem'):
            cards = (card, 'Mirror', 'Zap', 'Archers')
            cfg = config(cards)
            for seat in (0, 1):
                with self.subTest(card=card, seat=seat):
                    b = initial(669552, cards=cards)
                    b.players[seat].elixir = 10
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    self.assertTrue(verify(b, r, builder, scripts, bots, seat)['ok'])
                    pos = Position(13.5, 13.5 if seat == 0 else 18.5)
                    self.assertTrue(b.deploy_card(seat, card, pos))
                    for _ in range(30): b.step()
                    b.players[seat].elixir = 10
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    result = verify(b, r, builder, scripts, bots, seat)
                    self.assertTrue(result['ok'], result)
                    expected = b.resolve_card_play(seat, 'Mirror') is not None
                    self.assertEqual(b.deploy_card(seat, 'Mirror', Position(4.5, pos.y)), expected)
                    for _ in range(30): b.step()
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    result = verify(b, r, builder, scripts, bots, seat)
                    self.assertTrue(result['ok'], result)
