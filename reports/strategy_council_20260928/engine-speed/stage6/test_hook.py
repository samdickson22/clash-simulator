"""Fisherman wind-up, moving-target flight, drag and imported continuations."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early

class Hook(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_building_self_pull_troop_drag_stun_and_live_states(self):
        for victim in ('Cannon','Giant'):
            cards=('Fisherman',victim,'Zap','Knight');cfg=config(cards)
            for seat in (0,1):
                for stun in (False,True):
                    with self.subTest(victim=victim,seat=seat,stun=stun):
                        b=initial(669533,cards=cards)
                        for owner,name,y in ((seat,'Fisherman',13.5 if seat==0 else 18.5),
                                             (1-seat,victim,(19.5 if seat==0 else 12.5) if victim=='Cannon' else (18.5 if seat==0 else 13.5))):
                            b.players[owner].elixir=10
                            self.assertTrue(b.deploy_card(owner,name,Position(13.5,y)))
                        actor=next(e for e in b.entities.values() if getattr(e.card_stats,'name',None)=='Fisherman')
                        mechanic=next(m for m in actor.mechanics if type(m).__name__=='FishermanHook')
                        r=clasher_core.BattleState(snapshot(b,cfg));seen=set();zapped=False
                        for _ in range(250):
                            if stun and not zapped and mechanic.state=='windup' and mechanic.windup_remaining_ms<=850:
                                b.players[1-seat].elixir=10;r=clasher_core.BattleState(snapshot(b,cfg))
                                pos=Position(actor.position.x,actor.position.y)
                                self.assertTrue(b.deploy_card(1-seat,'Zap',pos))
                                self.assertTrue(r.apply_action(1-seat,'Zap',pos.x,pos.y));zapped=True
                            b.step();r.step();self.same(b,r)
                            if mechanic.state not in seen:
                                seen.add(mechanic.state);self.continuation(b,cfg,100)
                        self.assertIn('windup',seen)
                        if not stun:self.assertTrue({'flight','drag'}<=seen,seen)
                        if stun:self.assertTrue(zapped)

    def test_hook_can_cancel_committed_bandit_travel(self):
        cards=('Fisherman','Assassin','Zap','Knight');cfg=config(cards)
        for seat in (0,1):
            b=initial(669534,cards=cards)
            for owner,name,y in ((seat,'Fisherman',13.5 if seat==0 else 18.5),(1-seat,'Assassin',19.5 if seat==0 else 12.5)):
                b.players[owner].elixir=10
                self.assertTrue(b.deploy_card(owner,name,Position(13.5,y)))
            fish=next(e for e in b.entities.values() if getattr(e.card_stats,'name',None)=='Fisherman')
            bandit=next(e for e in b.entities.values() if getattr(e.card_stats,'name',None)=='Assassin')
            mechanic=next(m for m in fish.mechanics if type(m).__name__=='FishermanHook')
            # Shorter synthetic anticipation places the hook arrival inside
            # the normal Bandit flight; live imports must retain this parameter.
            mechanic.hook_windup_ms=800
            r=clasher_core.BattleState(snapshot(b,cfg));caught=False
            for _ in range(180):
                was_dashing=bandit._bandit_dashing
                b.step();r.step();self.same(b,r)
                if was_dashing and bandit.forced_movement_active:
                    caught=True;self.assertFalse(bandit._bandit_dashing);self.continuation(b,cfg,100)
            self.assertTrue(caught)

    def test_saved_drag_continuation_preserves_blocked_preload(self):
        import cloudpickle,hashlib,json
        from pathlib import Path
        root=Path(__file__).resolve().parent/'hook-r33-root185.pkl'
        pins=json.loads(root.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(root.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((root.parent.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,old,_=cloudpickle.loads(root.read_bytes());cfg=config(tuple(old['cards']))
        self.assertTrue(b.entities[8]._attack_preload_blocked)
        self.continuation(b,cfg,180)

    def test_pending_weapon_reset_stays_deferred_during_new_hook_windup(self):
        import cloudpickle,hashlib,json
        from pathlib import Path
        root=Path(__file__).resolve().parent/'hook-clock-r34-root899.pkl'
        pins=json.loads(root.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(root.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((root.parent.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,old,_=cloudpickle.loads(root.read_bytes());cfg=config(tuple(old['cards']))
        actor=b.entities[11]
        self.assertNotEqual(actor.attack_cooldown,actor._ordinary_clock_projection)
        self.continuation(b,cfg,180)

if __name__=='__main__':unittest.main()
