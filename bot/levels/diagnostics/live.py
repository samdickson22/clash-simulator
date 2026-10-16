"""Recorded-input LivePlayer facade around the real LiveSession translator.

The historical commands drive ONE conditional session (five acknowledged taps
and one explicitly unverified internal reservation). Two serial search
objects consume copies of its PublicView and never submit their own commands.
LivePlayer's start-time live belief replacement is retained; its fast model,
wall cutoff and error fallback are intentionally absent. Errors remain evidence.
"""
from __future__ import annotations

from collections import Counter
import copy
from dataclasses import replace
import json
import time
import traceback

from .protocol import (BASE, WAIT, action_details, command, command_kind, digest, in_window, plain,
                       root_tower_audit, tower_audit)


def recorded_session_class(base):
    """Actual LiveSession, with one documented untapped reservation exception.

    All confirmation/reconciliation behavior is UNCHANGED. Observe conditional
    HUD-inferred events without changing them; they are not tap acknowledgements
    or verified actual plays. Action233 alone never adds a public-play event.
    Observe object replacement, not the driver's flawed pending-length test.
    """
    class RecordedSession(base):
        _unverified_pending = None

        def _confirm_pending(self, record, poll):
            conditional = bool(self.ch.pending and self.ch.pending[0] is self._unverified_pending)
            count = len(record.get('events', ()))
            result = super()._confirm_pending(record, poll)
            if conditional:
                for event in record.get('events', ())[count:]:
                    row = dict(kind='conditional_hud_inference', n=self.player.frame['n'], tick=poll,
                        event=plain(event), verified_actual_play=False, acknowledged_tap=False,
                        evidence='unchanged LiveSession HUD inference conditional on unverified reservation233/170')
                    self.player.conditional_inferences.append(row)
                    self.player.sink(row)
            return result

        def _poll(self, record, poll, catch_up=False):
            before = tuple(self.ch.pending)
            decision = super()._poll(record, poll, catch_up)
            logged = self.player.decisions.get(self.player.frame['n']) if not catch_up else None
            if command_kind(logged) == 'unverified_internal_reservation':
                after = tuple(self.ch.pending)
                if (len(before) != 1 or before[0].action != 813 or before[0].card != 'Giant'
                        or before[0].submitted != 160 or len(after) != 1 or after[0] is before[0]
                        or after[0].action != 233 or after[0].submitted != 170 or decision.action != 233):
                    raise ValueError('unverified reservation contradicts expected Giant160 -> action233/170 replacement')
                self._unverified_pending = after[0]
                self.player.conditional_context = True
                self.player.sink(dict(kind='unverified_internal_reservation', n=self.player.frame['n'],
                    tick=poll, before=plain(before), after=plain(after),
                    evidence='logged action only; no tap/ack/play inferred from this action alone'))
            return decision
    return RecordedSession


def existing_configs(rt):
    """Parse existing cache bytes once; prohibit every exporter/receipt write."""
    import hashlib
    from bot.levels.configs import LevelConfigs, base_cards
    from bot.levels.profile import LIVE_DECK, OWN_LEVELS, OpponentEstimate
    lc = LevelConfigs(rt)
    support_raw = (lc.dir / 'supported.json').read_bytes()
    support = json.loads(support_raw)
    reference = hashlib.sha256(json.dumps(rt.R.config, sort_keys=True).encode()).hexdigest()
    if support.get('comparison') != 'native-json-v1' or support.get('reference_sha256') != reference:
        raise ValueError('existing supported receipt does not qualify this native JSON config')
    lc._supported = set(support['cards'])
    estimate = OpponentEstimate(rt)
    levels = {11, *(OWN_LEVELS[c] for c in LIVE_DECK), *(estimate(c) for c in base_cards(rt.R.config))}
    if not levels <= {4, 5, 6, 7, 9, 11}:
        raise ValueError(f'unreviewed required cache levels: {sorted(levels)}')
    manifest = {'supported': dict(path=str((lc.dir / 'supported.json').resolve()),
        raw_sha256=hashlib.sha256(support_raw).hexdigest(), canonical_sha256=digest(support)), 'levels': {}}
    for level in sorted(levels):
        path = lc.path(level)
        raw = path.read_bytes()  # No load() that could build on a missing file.
        data = json.loads(raw)
        missing = lc._supported - (set(data['cards']) | set(data.get('errors', {})))
        if data['level'] != level or missing:
            raise ValueError(f'incomplete existing export L{level}: {sorted(missing)}')
        lc.levels[level] = data
        manifest['levels'][str(level)] = dict(path=str(path.resolve()),
            raw_sha256=hashlib.sha256(raw).hexdigest(), canonical_sha256=digest(data),
            errors=data.get('errors', {}))
    good, bad = lc.check11()
    if set(good) != lc._supported or not lc._supported:
        raise ValueError(f'existing supported card set differs from parsed L11: {bad}')

    def load(level):
        if int(level) not in lc.levels:
            raise ValueError(f'unregistered level L{level}; diagnostic cannot export/read later')
        return lc.levels[int(level)]

    def refuse(*args, **kwargs):
        raise ValueError('offline diagnostic cannot build exports')

    lc.load, lc.build = load, refuse
    rt._level_configs = lc
    return lc, manifest


def native_physics(root):
    """Read the root actually built for search; never construct or sample another."""
    state = json.loads(root.snapshot())
    bodies = []
    for e in state['entities']:
        stats = e['stats']
        bodies.append(dict(id=e['id'], owner=e['owner'], name=stats['name'], kind=e['class'],
            x=e['x'], y=e['y'], hp=e['hp'], max_hp=stats['max_hp'], damage=stats.get('damage'),
            payload_key=stats.get('payload_key'), spell_name=e.get('spell_name'), alive=e['alive']))
    return dict(tick=state['tick'], bodies=bodies,
                towers=[b for b in bodies if b['name'] in ('Tower', 'KingTower') and b['kind'] != 'Projectile'])


def install_hooks(player, rt, arm, lc):
    """Call only AFTER actual search start reconstructed its core/native/config.

    Deliberately bypass levels.player and its RoyaleSim compatibility mask. These
    are the unmodified headline serial objects with root/leaf hooks only.
    """
    from bot.levels.profile import LIVE_DECK, OWN_LEVELS, OWN_TOWER, OPP_TOWER, OpponentEstimate
    from bot.levels.root import ExactLevelRoot, leaf_native
    if (player.native_threads, player.pool_size, player.roots) != (1, 0, 1):
        raise ValueError('diagnostic requires one serial native thread, no pool, one root')
    if hasattr(rt, '_placement'):
        raise ValueError('RoyaleSim placement installation is forbidden for LIVE replay')
    player.level_root = None
    if arm == 'B':
        player.level_root = ExactLevelRoot(rt, {c: OWN_LEVELS[c] for c in LIVE_DECK},
            OpponentEstimate(rt), OWN_TOWER, OPP_TOWER, lc=lc, force=True)
        root_fn = player.level_root.root
        player.p.core.native = leaf_native(rt, OWN_TOWER, OPP_TOWER)
    elif arm == 'A':
        root_fn = rt.R.root
    else:
        raise ValueError(arm)
    player._diagnostic_roots, player._diagnostic_candidates = [], None

    def root(info, opponent, rng):
        actual = root_fn(info, opponent, rng)  # Exactly one original RNG-consuming call.
        player._diagnostic_roots.append(native_physics(actual))
        return actual

    candidates_fn = player.p.core.candidates

    def candidates(packet, proposals=()):
        actions, mask = candidates_fn(packet, proposals)
        player._diagnostic_candidates = (list(actions), mask.copy())
        return actions, mask

    player.root_fn, player.p.core.candidates = root, candidates


class Shadow:
    """Independent deterministic search, read-only audit, fail-closed state rows."""
    def __init__(self, rt, arm, lc):
        from bot.eval.headline import make_player
        self.rt, self.arm, self.lc = rt, arm, lc
        self.player = make_player(rt, BASE)

    def start(self, ctx):
        from bot.live.player import live_belief_class
        self.player.start(ctx)
        belief = self.player.p.belief
        belief.__class__ = live_belief_class()
        belief.human_prior = self.rt.PRIOR
        install_hooks(self.player, self.rt, self.arm, self.lc)

    def act(self, view):
        from bot.search.lopp import FAILURES
        from bot.levels.scope import install
        player = self.player
        before = Counter(FAILURES)
        cpu0, wall0 = time.process_time(), time.monotonic()
        player._diagnostic_roots, player._diagnostic_candidates = [], None
        obs = view.info.packet.observation
        hand = list(view.info.own['hand'])
        elixir = float(view.info.own['elixir'])
        threats = [dict(token=int(t), x=float(f[0])*18, y=float(f[1])*32, hp_frac=float(f[9]))
                   for t, f in zip(obs.entity_ids[obs.entity_mask], obs.entity_features[obs.entity_mask])
                   if f[3] > .5 and f[1]*32 < 16
                   and player.rt.R.builder.token_names[int(t)] not in ('Tower', 'KingTower')]
        out = dict(view_sha256=digest(view), normalized_towers=plain(obs.global_features[8:14]),
                   hand=hand, elixir=elixir, cannon_available='Cannon' in hand,
                   cannon_affordable='Cannon' in hand and elixir >= float(self.rt.R.costs['Cannon']),
                   threats=threats)
        try:
            install(self.rt)
            out['effective_prior_before'] = digest(player.rt.PRIOR)
            if out['effective_prior_before'] != self.rt.levels_scope['restricted_sha256']:
                raise ValueError('constructed controller prior differs from scope')
            d = player.act(view)
            out['searched'] = d.stats is not None
            out['chosen'] = action_details(d.action, d.wait_ticks, hand)
            out['stats'] = plain(d.stats)
            out['effective_prior_after'] = digest(player.rt.PRIOR)
            install(self.rt)
            if out['effective_prior_after'] != out['effective_prior_before']:
                raise ValueError('controller prior changed during search')
            delta = Counter(FAILURES) - before
            out['failures'] = dict(delta)
            if delta or any((d.stats or {}).get(k) for k in ('native_failure', 'search_failures', 'error')):
                raise ValueError('native/search failure; fallback action cannot be accepted')
            out['root_tower_audits'] = [root_tower_audit(r, out['normalized_towers'], self.arm)
                                       for r in player._diagnostic_roots]
            if any(not t['consistent'] for audit in out['root_tower_audits'] for t in audit):
                raise ValueError('actual root tower HP/maxHP disagrees with unchanged public fractions/levels')
            chosen = out['chosen']
            out['cannon_home_defense'] = bool(chosen['card'] == 'Cannon' and chosen['row'] < 16 and threats)
            candidate_data = player._diagnostic_candidates
            if candidate_data is not None:
                actions, mask = candidate_data
                out['candidates'] = actions
                out['chosen_legal'] = d.action == WAIT or bool(mask[d.action])
                out['cannon_legal_tiles'] = sum(int(mask[i]) for slot, card in enumerate(hand)
                    if card == 'Cannon' for i in range(slot*576, (slot+1)*576))
                if not out['chosen_legal']:
                    raise ValueError('shadow chose a deployment rejected by its public mask')
        except BaseException as ex:
            if isinstance(ex, (KeyboardInterrupt, SystemExit)):
                raise
            out.update(error=repr(ex), traceback=traceback.format_exc(), failures=dict(Counter(FAILURES) - before))
        finally:
            root = player.level_root
            out.update(root_calls=len(player._diagnostic_roots), root_physics=player._diagnostic_roots,
                level_diagnostics=dict(stats=dict(getattr(root, 'stats', {})),
                    seat_configs={str(s): entry[2] for s, entry in getattr(root, '_cfg', {}).items()}),
                belief_rebuilds=getattr(player.p.belief, 'rebuilds', 0),
                cpu_s=time.process_time()-cpu0, wall_s=time.monotonic()-wall0)
        return out

    def close(self):
        if hasattr(self.player, 'p'):
            self.player.close()


class RecordedFacade:
    """LiveSession contract: recorded conditional command driver, shadows observe.

    Missing polls are explicit maintenance-only LiveSession catch-ups borrowing
    the current frame. They cannot become search opportunities. Recorded stats
    determine original search gating; no fast checkpoint is loaded/substituted.
    """
    def __init__(self, shadows, decisions, acks, sink):
        self.shadows, self.decisions, self.acks, self.sink = shadows, decisions, acks, sink
        self.rows, self.mismatches, self.seen = [], [], set()
        self.conditional_context, self.conditional_inferences = False, []
        self.frame, self.expected_poll = None, None

    def start(self, ctx):
        self.ctx = ctx
        for shadow in self.shadows.values():
            shadow.start(ctx)

    def act(self, view):
        from bot.players.base import Decision
        record = self.frame
        logged = self.decisions.get(record['n'])
        catch_up = view.tick != self.expected_poll
        if logged is not None and not catch_up:
            self.seen.add(record['n'])
            if logged['poll'] != view.tick:
                self.mismatches.append(dict(n=record['n'], kind='poll', recorded=logged['poll'], replay=view.tick))
        elif not catch_up:
            self.mismatches.append(dict(n=record['n'], tick=view.tick, kind='missing_recorded_poll'))
        action, wait = command(None if catch_up else logged, self.acks)
        stats = (logged or {}).get('stats') or {}
        searched = bool(stats.get('source') == 'search')
        if not catch_up and (action < WAIT or searched) and not view.can_act:
            self.mismatches.append(dict(n=record['n'], tick=view.tick, kind='recorded_command/search_blocked'))
        if (action < WAIT and command_kind(logged) == 'acknowledged_tap'
                and view.info.own['hand'][action // 576] != logged['card']):
            self.mismatches.append(dict(n=record['n'], tick=view.tick, kind='recorded_card_slot',
                recorded=logged['card'], replay=view.info.own['hand'][action // 576]))
            # Do not submit a different card under the same recorded slot.
            raise ValueError(f'recorded own command context diverged at frame {record["n"]}')
        opportunity = bool(not catch_up and logged and searched and in_window(record['clock_s'])
                           and view.tick % 10 == 0)
        before = digest(view)
        results = {}
        for arm, shadow in self.shadows.items():
            # Every D1 poll is serviced, including off-cadence/blocked polls.
            # Only recorded matched search opportunities permit a root/search.
            clone = replace(copy.deepcopy(view), can_act=bool(view.can_act and opportunity))
            results[arm] = shadow.act(clone)
            if digest(view) != before:
                raise ValueError('shadow mutated the common recorded public view')
        row = dict(n=record['n'], tick=view.tick, clock_s=record['clock_s'],
            expected_poll=self.expected_poll, catch_up=catch_up, opportunity=opportunity,
            common_can_act=view.can_act, recorded_search=searched, recorded_action=action,
            recorded_command_evidence=command_kind(None if catch_up else logged),
            conditional_reservation_context=self.conditional_context,
            conditional_hud_inferences=plain(self.conditional_inferences),
            common_pending=plain(view.pending), common_view_sha256=before,
            public_towers=tower_audit(record), arms=results)
        if results['A']['view_sha256'] != results['B']['view_sha256']:
            raise ValueError('A/B received different public decision views')
        self.rows.append(row)
        self.sink(row)
        return Decision(action, wait, dict(source='recorded-command', evidence=command_kind(logged)))

    def evidence(self):
        return dict(mismatches=self.mismatches, missing_decisions=sorted(set(self.decisions)-self.seen),
                    acknowledged_taps=sum(command_kind(r) == 'acknowledged_tap' for r in self.decisions.values()),
                    unverified_internal_reservations=sum(command_kind(r) == 'unverified_internal_reservation'
                                                        for r in self.decisions.values()),
                    conditional_hud_inferences=plain(self.conditional_inferences),
                    catch_up_polls=sum(r['catch_up'] for r in self.rows),
                    recorded_search_polls=sum(bool((r.get('stats') or {}).get('source') == 'search')
                                              for r in self.decisions.values()))

    def close(self):
        for shadow in self.shadows.values():
            shadow.close()
