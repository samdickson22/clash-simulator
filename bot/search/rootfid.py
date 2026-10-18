"""Root fidelity (token RF, default off): the planner root keeps public timing and target facts.

LP1 (reports/bot/lag-projection/RESULTS.md) found the v5 root rebuild (fair_player.Resources.root) resets what the
packet columns cannot carry: a Goblin Barrel in flight is rebuilt aiming at (0, 0); an in-flight spell carrier
(Fireball, Arrows) aims one tile ahead of itself; deploying bodies are already deployed; stunned bodies move;
spawner buildings restart their first wave. The diagnostic argmax changed on 8/20 rebuilt roots.

FidelityRoot.root(info, opponent, rng) is LevelRoot's payload (bot/live/levels.py; byte-identical to R.root at
all levels 11) with one patch per body, read from info.extras (royalesim_translate.PublicInformation; keyed by the
packet row's kind, own flag, x, y). Every field is public: an observer reads it off the screen (flight arc and
landing, deploy clock, stun effect, spawn timing from the building's appearance) or from the client's public unit
data (LIVE memory route). Nothing hidden (hands, elixir, RNG) is read. A body without an extra keeps the old default.
- Projectile / SpawnProjectile with 'aim': aim = the carrier's actual destination (absolute tiles);
  SpawnProjectile with 'flown': effect_age = flown ticks x 0.05 s (its impact-delay clock).
- Troop / Building: deploy = remaining deploy ticks x 0.05 s; stun = remaining stun ticks x 0.05 s;
  age = 50 ms x ticks since its deploy clock reached 0 (native age counts deployed ticks only; 0 while deploying).
- Building with a spawner: the production clock the native spawner (engine-rs spawn.rs) would have after
  (live + 1) x 50 ms of running (it also runs on the deploy-end tick): waves done, the current wave's pending units,
  elapsed ms. Idle gating, stuns and rage on the spawner are not replayed (documented approximation; phase only).
  A body first seen already deployed counts from its first sight (its earlier age is unknown).
Without extras (an Information with no `extras`, e.g. the live translator before it fills them) this is R.root.
"""
from __future__ import annotations

from bot.live.levels import LevelRoot, Levels

TICK_S = 0.05


def production_state(spec, active_ms):
    """Native spawner State after active_ms of an always-active clock (engine-rs spawn.rs production loop)."""
    interval, intra, count = float(spec['interval']), float(spec.get('intra') or 0.), max(1, int(spec.get('count') or 1))
    first = spec.get('first')
    first = interval if first is None else float(first)
    maximum = int(spec.get('maximum', -1))
    state = dict(elapsed=0., waves=0, pending=0, unit_elapsed=0., wave_spawned=0)
    t = max(0., float(active_ms))
    if t < first:
        state['elapsed'] = t
        return state
    t -= first
    burst = intra*(count-1) if intra > 0 and count > 1 else 0.
    period = burst + interval
    k = int(t // period) if period > 0 else 0
    r = t - k*period
    if burst and r < burst:                      # inside wave k: units 0..j spawned, the rest pending
        j = int(r // intra)
        state.update(waves=k, wave_spawned=j+1, pending=count-1-j, unit_elapsed=r-j*intra)
    else:
        state.update(waves=k+1, elapsed=r-burst)
    if maximum != -1 and state['waves'] >= maximum:
        state.update(waves=maximum, pending=0, wave_spawned=0, elapsed=0., unit_elapsed=0.)
    return state


def make_patch(extras_of):
    """patch(e, template, row, info) for LevelRoot; extras_of(info) -> {extra_key: extra} or None."""
    from bot.players.royalesim_translate import extra_key
    counts = {}

    def patch(e, template, row, info):
        extras = extras_of(info)
        if not extras:
            return
        x = extras.get(extra_key(row))
        if not x:
            counts['unmatched'] = counts.get('unmatched', 0) + 1
            return
        cls = e['class']
        if cls in ('Projectile', 'SpawnProjectile'):
            if x.get('aim') is not None:
                e['aim'] = [float(x['aim'][0]), float(x['aim'][1])]
                counts['aim'] = counts.get('aim', 0) + 1
            if cls == 'SpawnProjectile' and x.get('flown') is not None:
                e['effect_age'] = round(int(x['flown'])*TICK_S, 6)
        if cls in ('Troop', 'Building'):
            deploying = x.get('deploy', 0) > 0
            if deploying:
                e['deploy'] = round(int(x['deploy'])*TICK_S, 6)
                counts['deploy'] = counts.get('deploy', 0) + 1
            if x.get('stun', 0) > 0:
                e['stun'] = round(int(x['stun'])*TICK_S, 6)
                counts['stun'] = counts.get('stun', 0) + 1
            live = None if deploying else x.get('live')
            if deploying or live is not None:
                # engine-rs lib.rs: age += 50 only on ticks that start deployed; production also runs on the tick
                # the deploy clock reaches 0. live = ticks since that tick.
                e['age'] = 0 if deploying else int(live)*50
                spec = e['stats'].get('spawner')
                if cls == 'Building' and spec and e.get('production') is not None:
                    active = 0. if deploying else (int(live)+1)*50.
                    e['production'] = dict(e['production'], **production_state(spec, active))
                    counts['production'] = counts.get('production', 0) + 1
    patch.counts = counts
    return patch


class FidelityRoot:
    """root_fn for the search tiers (bot/search/players.py, bot/live/player.py): R.root plus the public extras."""

    def __init__(self, R, levels=None, *, ignore_extras=False):
        self.R, self.ignore_extras = R, ignore_extras
        self.patch = make_patch(lambda info: None if ignore_extras else getattr(info, 'extras', None))
        self.lr = LevelRoot(R, levels or Levels(), patch=self.patch)

    @property
    def counts(self):
        return self.patch.counts

    def root(self, info, opponent, rng):
        if (self.ignore_extras or not getattr(info, 'extras', None)) and self.lr.levels.trivial():
            return self.R.root(info, opponent, rng)
        import clasher_core
        return clasher_core.BattleState(self.lr.payload(info, opponent, rng))
