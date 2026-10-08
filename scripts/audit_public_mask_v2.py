"""Read-only recorded-action replay audit; writes only the requested new receipt.

Run through fleet_run.sh on a home CPU host. The oracle is the scalar engine's
exact pre-deployment guards (DiscreteTileActionSpace fast mask). All 2,304
placement bits are compared, including false negatives. No-op is an always
available policy wait, not a deploy_card command; abilities are reported apart.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import replace
import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import time

import numpy as np

from clasher.entities import Building
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder, ContractV5ObservationBuilder
from clasher.rl.public_action_mask import PublicActionMaskInput


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Audit:
    def __init__(self, output, limit, *, native_every=0):
        self.output, self.limit = Path(output), limit
        self.builder = ContractV5ObservationBuilder()
        self.v1 = ContractV5ActionMaskBuilder(self.builder)
        self.v2 = ContractV5ActionMaskBuilder(self.builder, mask_version=2)
        self.space = DiscreteTileActionSpace(mask_version=2)
        self.counts = Counter()
        self.cards = defaultdict(Counter)
        self.situations = defaultdict(Counter)
        self.scopes = defaultdict(Counter)
        self.scope = 'gate'
        self.raw_plays = {}
        self.examples = []
        self.games = []
        self.oracle_cache = {}
        self.mask_cache = {}
        self.native_every = native_every
        self.started = time.time()
        if native_every:
            import clasher_core
            from c56_controller import CARDS, metadata
            from differential import config
            self.core, self.cfg = clasher_core, config(CARDS)
            self.native = clasher_core.NativeScripts(json.dumps(metadata(self.builder, mask_version=2)))

    def observe(self, b, seat, action=2304, *, source="human"):
        if self.counts['states'] >= self.limit:
            return
        packet = self.builder.build_public(b, seat)
        request = PublicActionMaskInput.from_confidence_observation(packet)
        # Oracle-only cache: every engine input to PLACEMENT legality, including
        # full precision coordinates and exact affordability. Never fed to v2.
        buildings = tuple((e.id, e.position.x, e.position.y, e.card_stats.collision_radius)
                          for e in b.entities.values() if e.is_alive and isinstance(e, Building))
        payloads = tuple((e.id, e.position.x, e.position.y, e.deployment_collision_radius)
                        for e in b.entities.values() if e.is_alive and getattr(e, 'blocks_deployment', False))
        p = b.players[seat]
        plays = [b.resolve_card_play(seat, name) if name else None for name in p.hand[:4]]
        hand = tuple(None if play is None else (name, play[0], play[1].level,
                     p.can_play_card(name, play[1])) for name, play in zip(p.hand[:4], plays))
        placement_cache = tuple((size, mask.tobytes()) for size, mask in
                                sorted(b._building_placement_blocked_masks.items()))
        key = (seat, b.game_over, hand, buildings, payloads, placement_cache,
               tuple((p.left_tower_hp > 0, p.right_tower_hp > 0, p.king_tower_hp > 0) for p in b.players))
        exact = self.oracle_cache.get(key)
        if exact is None:
            exact = self.space.legal_action_mask(b, seat, fast_path=True)[:2304].copy()
            # Independently check every new oracle geometry against deploy's
            # scalar guards. This catches omissions in the optimized mask itself.
            scalar = self.space.legal_action_mask(b, seat, fast_path=False)[:2304]
            self.counts['oracle_fast_scalar_mismatch_bits'] += int((exact != scalar).sum())
            exact = scalar.copy()
            self.oracle_cache[key] = exact
            self.counts['engine_guard_masks_computed'] += 1
        # Public cache is independently keyed on public arrays; include all
        # fields to avoid assuming away a missing occupancy input.
        public_key = (request.entity_ids.tobytes(), request.entity_features.tobytes(),
                      request.entity_mask.tobytes(), request.hand_ids.tobytes(),
                      request.global_features.tobytes(), request.own_last_play,
                      request.terminal, request.board_rotated)
        cached = self.mask_cache.get(public_key)
        if cached is None:
            cached = (self.v1.build(request)[:2304], self.v2.build(request)[:2304])
            if len(self.mask_cache) > 4000:
                self.mask_cache.clear()
            self.mask_cache[public_key] = cached
        old, new = cached
        fp1, fp2, fn2 = old & ~exact, new & ~exact, exact & ~new
        if (fp2|fn2).any():
            # Diagnostic ONLY: explain information-theoretic residuals by
            # revealing hidden blockers to a counterfactual copy. This result
            # is never counted as the public mask or supplied to an actor.
            hidden = [e for e in b.entities.values() if e.is_alive and isinstance(e,Building)
                      and not self.builder._actor_visible(e,seat)]
            explained = np.zeros(2304,dtype=np.bool_)
            if hidden:
                rows=[self.builder._entity_row(e,seat) for e in hidden]
                counterfactual=replace(request,
                    entity_ids=np.concatenate([request.entity_ids,np.array([r[0] for r in rows])]),
                    entity_features=np.concatenate([request.entity_features,np.stack([r[1] for r in rows])]),
                    entity_mask=np.concatenate([request.entity_mask,np.ones(len(rows),dtype=np.bool_)]),
                    entity_id_confidence=np.concatenate([request.entity_id_confidence,np.ones(len(rows))]))
                revealed=self.v2.build(counterfactual)[:2304]
                explained=(fp2|fn2)&(revealed==exact)
            self.counts['residual_hidden_building_bits']+=int(explained.sum())
            self.counts['residual_unclassified_bits']+=int(((fp2|fn2)&~explained).sum())
        self.counts.update(states=1, placement_bits=2304, v1_legal=int(old.sum()),
                           v1_false_positive=int(fp1.sum()), v2_legal=int(new.sum()),
                           v2_false_positive=int(fp2.sum()), v2_false_negative=int(fn2.sum()),
                           states_v1_false_positive=int(fp1.any()), states_v2_mismatch=int((fp2|fn2).any()))
        situation = 'payload' if payloads else ('non_crown_building' if len(buildings)>6 else 'ordinary')
        self.situations[situation].update(states=1, v1_legal=int(old.sum()), v1_false_positive=int(fp1.sum()),
                                         v2_false_positive=int(fp2.sum()), v2_false_negative=int(fn2.sum()))
        self.scopes[self.scope].update(states=1, v1_legal=int(old.sum()), v1_false_positive=int(fp1.sum()),
                                      v2_false_positive=int(fp2.sum()), v2_false_negative=int(fn2.sum()))
        for slot, name in enumerate(p.hand[:4]):
            if name:
                sl = slice(slot*576, (slot+1)*576)
                self.cards[name].update(slot_states=1, v1_legal=int(old[sl].sum()),
                    v1_false_positive=int(fp1[sl].sum()), v2_false_positive=int(fp2[sl].sum()),
                    v2_false_negative=int(fn2[sl].sum()))
        if 0 <= action < 2304:
            card = p.hand[action//576]
            for target in (self.counts, self.cards[card]):
                target.update({source+'_actions':1, source+'_v1_legal':int(old[action]),
                               source+'_v1_legal_engine_rejected':int(fp1[action]),
                               source+'_v2_legal_engine_rejected':int(fp2[action])})
        # Original human coordinates, before the frozen replayer's adjacent-tile
        # projection. Quantize exactly as its discrete action encoder does.
        for play in self.raw_plays.get(b.tick, ()):
            if play.card not in p.hand:
                self.counts['raw_human_card_not_in_hand'] += 1
                continue
            from clasher.rl.human_replay_demonstrations import world_tile
            x,y=world_tile(play.x_millitiles,play.y_millitiles)
            raw=self.space.encode_action(p.hand.index(play.card),x,y,seat)
            for target in (self.counts,self.cards[play.card]):
                target.update(raw_human_actions=1,raw_human_v1_legal=int(old[raw]),
                              raw_human_v1_legal_engine_rejected=int(fp1[raw]),
                              raw_human_v2_legal_engine_rejected=int(fp2[raw]))
        if (fp2|fn2).any() and len(self.examples)<30:
            bad = np.flatnonzero(fp2|fn2)[:8]
            self.examples.append(dict(tick=b.tick, seat=seat, hand=list(p.hand),
                actions=bad.tolist(), v2=new[bad].tolist(), engine=exact[bad].tolist(),
                buildings=buildings, payloads=payloads,
                public_buildings=self.v2._placement_v2.board(request).buildings))
        if self.native_every and self.counts['states'] % self.native_every == 0:
            from differential import snapshot
            if all(name is None or name in self.cfg['cards'] for name in p.hand):
                try:
                    native = np.asarray(self.native.public_mask(self.core.BattleState(snapshot(b, self.cfg)),seat))[:2304]
                    self.counts.update(native_states=1,native_python_mismatch_bits=int((native!=new).sum()))
                except (ValueError, KeyError) as e:
                    self.counts['native_out_of_scope'] += 1
                    if len(self.examples)<30:
                        self.examples.append(dict(native_error=str(e),tick=b.tick))
        if len(self.oracle_cache)>20000:
            self.oracle_cache.clear()

    def save(self):
        value = dict(schema='clasher.mask-v2-audit.v1', counts=dict(self.counts),
            per_card=dict(self.cards), per_situation=dict(self.situations), examples=self.examples,
            per_scope=dict(self.scopes),
            games=self.games, elapsed_seconds=time.time()-self.started,
            oracle='scalar engine pre-deployment guards; full 2304 placement bits; exact-input memo',
            source_files={str(p):sha(p) for p in (Path(__file__),
                Path(sys.modules[ContractV5ActionMaskBuilder.__module__].__file__),
                Path(sys.modules['clasher.rl.public_placement_v2'].__file__))})
        self.output.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.output.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(self.output)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--states',type=int,default=100000)
    ap.add_argument('--payloads',type=Path)
    ap.add_argument('--slug-map-dir',type=Path)
    ap.add_argument('--shard',type=int,default=0)
    ap.add_argument('--gate',type=Path)
    ap.add_argument('--native-every',type=int,default=0)
    args=ap.parse_args()
    audit=Audit(args.output,args.states,native_every=args.native_every)
    if args.gate:
        from stage2_matches import battle
        record=json.loads(args.gate.read_text())
        b=battle(record,audit.builder.loader)
        by_tick=defaultdict(list)
        for a in record['actions']:by_tick[a[0]].append(a)
        for tick in range(record.get('ticks',6101)+1):
            if b.game_over:break
            for _,seat,action,expected in by_tick.get(b.tick,[]):
                audit.observe(b,seat,action,source='model' if seat==record['seat'] else 'script')
                actual=bool(audit.space.apply_action(b,seat,action))
                audit.counts['recorded_actions']+=1
                audit.counts['recorded_acceptance_divergences']+=actual!=expected
            b.step()
        audit.games.append(dict(source=str(args.gate),sha256=sha(args.gate),ticks=b.tick))
    else:
        from clasher.rl.human_replay_demonstrations import parse_il_replay_record
        from clasher.rl.human_replay_v5 import reconstruct_perspective_v5, ReconstructionConfigV5
        sys.path.insert(0,str(args.slug_map_dir))
        from card_map import SLUG_TO_GAMEDATA
        source=args.payloads/f'shard-{args.shard:03d}.jsonl.gz'
        with gzip.open(source,'rt') as stream:
            for index,line in enumerate(stream):
                if audit.counts['states']>=args.states:break
                try:
                    match=parse_il_replay_record(json.loads(line),SLUG_TO_GAMEDATA)
                    from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
                    from clasher.rl.c56_scripted import C56_ADDED_CARDS
                    audit.scope = ('C56' if all(c in SUPPORTED_CARDS|C56_ADDED_CARDS
                                    for deck in match.decks for c in deck) else 'S122-extension')
                    audit.raw_plays=defaultdict(list)
                    for play in match.plays:
                        if play.player==index%2:
                            audit.raw_plays[play.tick//5*5].append(play)
                    # Each source match contributes one alternating seat, avoiding
                    # duplicated perspectives of the same underlying recording.
                    with contextlib.redirect_stdout(io.StringIO()):
                        game=reconstruct_perspective_v5(match,index%2,audit.builder,
                            config=ReconstructionConfigV5(tower_clamp=True),
                            row_observer=audit.observe)
                    audit.games.append(dict(record=index,seat=index%2,rows=len(game.controls['expert_actions']),
                                            summary=game.summary))
                except (ValueError, KeyError) as e:
                    audit.games.append(dict(record=index,error=str(e)))
                audit.save()
                print(json.dumps(dict(record=index,counts=audit.counts)),flush=True)
        audit.games.append(dict(source=str(source),sha256=sha(source)))
    audit.save()


if __name__=='__main__':main()
