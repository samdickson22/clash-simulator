"""Character rolling births and short homing windows on retained live roots."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early


class ProjectileExtensions(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_bowler_rolling_birth_hit_push_and_import_both_seats(self):
        cards=('Bowler','Knight','Minions','Giant');cfg=config(cards)
        for seat in (0,1):
            with self.subTest(seat=seat):
                b=initial(669400,cards=cards);sign=1 if seat==0 else -1;y=10 if seat==0 else 22
                b._spawn_unit_at_position(Position(9,y),seat,b.card_loader.get_card('Bowler'),deploy_delay_override=0,snap_to_valid=False)
                target=b.next_entity_id
                b._spawn_unit_at_position(Position(9.5,y+sign*5),1-seat,b.card_loader.get_card('Knight'),deploy_delay_override=0,snap_to_valid=False)
                r=clasher_core.BattleState(snapshot(b,cfg));shot=push=False
                for _ in range(160):
                    b.step();r.step();self.same(b,r)
                    rolls=[e for e in b.entities.values() if type(e).__name__=='RollingProjectile']
                    if rolls and not shot:
                        shot=True;self.assertEqual(rolls[0].time_alive,0.05);self.continuation(b,cfg,100)
                    victim=b.entities.get(target)
                    if victim and victim._knockback_target is not None:
                        push=True;self.continuation(b,cfg,100);break
                self.assertTrue(shot);self.assertTrue(push)

    def test_magic_archer_temporary_homing_live_import_both_seats(self):
        cards=('EliteArcher','Giant','Knight','Minions');cfg=config(cards)
        for seat in (0,1):
            with self.subTest(seat=seat):
                b=initial(669401,cards=cards);sign=1 if seat==0 else -1;y=10 if seat==0 else 22
                b._spawn_unit_at_position(Position(9,y),seat,b.card_loader.get_card('EliteArcher'),deploy_delay_override=0,snap_to_valid=False)
                b._spawn_unit_at_position(Position(9.5,y+sign*7),1-seat,b.card_loader.get_card('Giant'),deploy_delay_override=0,snap_to_valid=False)
                r=clasher_core.BattleState(snapshot(b,cfg));window=False
                for _ in range(100):
                    b.step();r.step();self.same(b,r)
                    if any(getattr(e,'_temporary_homing_remaining_ms',0)>0 for e in b.entities.values()):
                        window=True;self.continuation(b,cfg,100);break
                self.assertTrue(window)

    def test_magic_archer_enlarged_launch_hit_is_synchronous(self):
        cards=('EliteArcher','Knight','Giant','Minions');cfg=config(cards)
        for seat in (0,1):
            with self.subTest(seat=seat):
                b=initial(669402,cards=cards);sign=1 if seat==0 else -1;y=10 if seat==0 else 22
                b._spawn_unit_at_position(Position(9,y),seat,b.card_loader.get_card('EliteArcher'),deploy_delay_override=0,snap_to_valid=False)
                target=b.next_entity_id
                b._spawn_unit_at_position(Position(9,y+sign*1.5),1-seat,b.card_loader.get_card('Knight'),deploy_delay_override=0,snap_to_valid=False)
                r=clasher_core.BattleState(snapshot(b,cfg));born=False
                for _ in range(80):
                    next_id=b.next_entity_id;hp=b.entities[target].hitpoints
                    b.step();r.step();self.same(b,r)
                    shots=[e for e in b.entities.values() if e.id>=next_id and getattr(e,'source_name','')=='EliteArcher']
                    if shots:
                        born=True;self.assertTrue(shots[0].start_collision_resolved)
                        self.assertLess(b.entities[target].hitpoints,hp)
                        self.continuation(b,cfg,100);break
                self.assertTrue(born)


if __name__=='__main__':unittest.main()
