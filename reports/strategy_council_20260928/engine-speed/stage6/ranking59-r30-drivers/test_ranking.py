"""Native heuristic rankings preserve public C56 choices and candidate order."""
import unittest

import clasher_core
from c56_controller import CARDS, verify
from controller import CONTROLLER_CARDS as EARLY, resources
from differential import Position, config, initial, snapshot


class Ranking(unittest.TestCase):
    def test_deployed_new_bodies_and_spawn_areas(self):
        builder,_,scripts,bots=resources();cfg=config(tuple(dict.fromkeys((*CARDS,*EARLY))))
        for card in EARLY:
            for seat in (0,1):
                with self.subTest(card=card,seat=seat):
                    b=initial(cards=(card,'Knight','Archers','Giant'))
                    b.players[seat].elixir=10
                    self.assertTrue(b.deploy_card(seat,card,Position(8.5,10.5 if seat==0 else 21.5)))
                    for _ in range(25):b.step()
                    r=clasher_core.BattleState(snapshot(b,cfg))
                    result=verify(b,r,builder,scripts,bots,seat)
                    self.assertTrue(result['ok'],result)

    def test_all_declared_cards_both_seats_and_three_styles(self):
        builder, _, scripts, bots = resources()
        cfg = config(tuple(dict.fromkeys((*CARDS, *EARLY))))
        for card in (*CARDS, *EARLY):
            b = initial(cards=tuple(dict.fromkeys((card, 'Knight', 'Archers', 'Giant', 'Musketeer'))))
            r = clasher_core.BattleState(snapshot(b, cfg))
            for seat in (0, 1):
                with self.subTest(card=card, seat=seat):
                    self.assertTrue(verify(b,r,builder,scripts,bots,seat)['ok'])
                    packet = builder.build_public(b,seat)
                    for style, bot in bots.items():
                        expected = bot._ranked_actions(packet,all_plays=True)
                        actual = scripts.ranked_actions(r,seat,style)
                        self.assertEqual([d.action_id for d in expected[:4]], [a for a,_ in actual[:4]])
                        self.assertEqual(scripts.select_action(r,seat,style),actual[0][0])

    def test_rejects_invalid_seat_and_style(self):
        _,_,scripts,_=resources()
        b=initial();r=clasher_core.BattleState(snapshot(b,config()))
        for seat,style in ((2,'balanced'),(0,'unknown')):
            with self.assertRaises(ValueError):scripts.ranked_actions(r,seat,style)

    def test_reference_controller_blocker_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'Python controller crashes'):
            resources(('ThreeMusketeers',))


if __name__=='__main__':unittest.main()
