"""Seeded, board-bounded perception scenarios for the LIVE births tracker.

Run with PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 nice -n 19 taskset -c 6-7
/mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m bot.live.multibody_fuzz
--seeds 0:500 --level both --out /tmp/multibody-fuzz.jsonl --minimize 3.

Only the cached CardBodies constructor loads Runtime. Scenario dictionaries are
JSON serializable; frames and truth also work as a minimal standalone scenario.
The simulation models perception and card cycle, not combat or elixir economy.
"""
from __future__ import annotations

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import random
import time

from bot.live.births import CardBodies, UnitTracker

TOWERS = {'left': True, 'right': True}
LEVELS = ('clean', 'noisy')


@lru_cache(maxsize=1)
def card_bodies():
    """One frozen runtime build per process (shared by generation and checking)."""
    from bot.players.runtime import Runtime
    return CardBodies(Runtime())


def ring(n, radius, x, y, phase=0.):
    if n == 1:
        return [(x, y)]
    return [(x + radius*math.cos(phase + 2*math.pi*k/n),
             y + radius*math.sin(phase + 2*math.pi*k/n)) for k in range(n)]


def _position(body, tick):
    age = tick - body['born']
    x = body['x'] + body['vx']*age
    y = body['y'] + body['vy']*age
    if body['jump'] and tick >= body['jump'][0]:
        x += body['jump'][1]
        y += body['jump'][2]
    return x, y


def generate(seed, level):
    """Return frames, deployment truth, parameters, and shrinkable body origins.

    Both levels use identical physical scenarios for a seed. Separate RNGs keep
    noise from changing decks, movement, lifetime, cycle, or frame cadence.
    Truth tuples are (owner, card, tick, formation_x, formation_y).
    """
    if level not in LEVELS:
        raise ValueError(f'unknown level: {level!r}')
    cb = card_bodies()
    rng, noise = random.Random(seed), random.Random(seed ^ 0xC1A5_4E2)
    cards = sorted(c for c, bodies in cb.main.items() if bodies and c not in cb.oov)
    buildings = [c for c in cards if any(b[1] == 1 for b, _ in cb.main[c])]
    multis = [c for c in cards if cb.count[c] > 1]
    duration = rng.randint(60*20, 120*20)
    ticks, tick = [], 0
    while tick <= duration + 80:  # close the last deployment's voting window
        ticks.append(tick)
        tick += rng.choice((2, 3))
    params = dict(seed=seed, level=level, duration_ticks=duration,
                  miss=noise.uniform(0., .2) if level == 'noisy' else 0.,
                  flip=noise.uniform(0., .4) if level == 'noisy' else 0.,
                  cross_flip=.01 if level == 'noisy' else 0.,
                  jitter=.1 if level == 'noisy' else 0., decks=[], cycles=[])
    truth, bodies = [], []

    def add(origin, label, x, y, born, dies, *, stationary=False, role='main', jump=None):
        # Equal-card bodies keep formation instead of stretching into a stream.
        # A stable name checksum gives cards different speeds across all seeds.
        speed = .03 + .05*(sum((i + 1)*ord(c) for i, c in enumerate(label)) % 101)/100
        bodies.append(dict(origin=origin, label=label, x=x, y=y, born=born, dies=dies,
                           vx=0. if stationary else rng.uniform(-.003, .003),
                           vy=0. if stationary else speed*(1 if truth[origin][0] == 0 else -1),
                           role=role, jump=jump, hinted=False))

    for owner in (0, 1):
        # At most one champion type in a real deck; never redeploy it while live.
        fixed = [rng.choice(buildings), rng.choice(multis)]
        pool = [c for c in cards if c not in fixed]
        rng.shuffle(pool)
        deck = list(dict.fromkeys(fixed))
        for c in pool:
            if c in cb.champions and any(d in cb.champions for d in deck):
                continue
            deck.append(c)
            if len(deck) == 8:
                break
        rng.shuffle(deck)
        params['decks'].append(list(deck))
        hand, queue = deck[:4], deck[4:]
        next_tick, previous = rng.randint(10, 40), []
        standing = []                      # (x, y, until) of this owner's buildings: 3x3 footprints never overlap
        champion_until = 0
        cycle = []
        for tick in ticks:
            if tick < next_tick or tick > duration:
                continue
            eligible = [i for i, c in enumerate(hand) if c not in cb.champions or tick >= champion_until]
            slot = rng.choice(eligible)
            card = hand[slot]
            hand[slot] = queue.pop(0)
            queue.append(card)
            cycle.append(card)
            n = cb.count[card]
            radius = min(2.3, .5 + .13*(n - 2)) if n > 1 else 0.
            for attempt in range(400):
                if attempt < 100:
                    x = min(17.5 - radius, max(.5 + radius, rng.choice((4.5, 9., 13.5)) + rng.uniform(-1., 1.)))
                else:                      # lanes crowded by buildings: anywhere across the board
                    x = rng.uniform(.5 + radius, 17.5 - radius)
                y = rng.uniform(max(15.5, 15.05 + radius), 28.) if owner else rng.uniform(4., 16.5)
                building = any(b[1] == 1 for b, _ in cb.main[card]) or cb.spawner(card)
                clear = 3.5 if building else 1.5   # a building needs its footprint; a troop is never inside one
                if all(tick - t > 40 or math.hypot(x - px, y - py) >= 2.
                       for t, px, py in previous) and \
                        all(tick >= until or math.hypot(x - bx, y - by) >= clear for bx, by, until in standing):
                    break
            else:
                raise AssertionError('could not separate deployments')
            previous.append((tick, x, y))
            origin = len(truth)
            truth.append((owner, card, tick, x, y))
            stationary = any(b[1] == 1 for b, _ in cb.main[card]) or cb.spawner(card)
            life = cb.lifetime.get(card, 600) if stationary else rng.randint(40, 240)
            if stationary:
                standing.append((x, y, tick + life))
            hinted = rng.random() < .2
            jump = None
            if card in cb.champions:
                champion_until = tick + life
                if life > 65 and rng.random() < .5:
                    when = tick + rng.randint(30, life - 20)
                    # A lateral ability relocation remains inside the board.
                    distance = rng.uniform(6., min(10., 16.8 - x if x < 9 else x - 1.2))
                    jump = (when, distance if x < 9 else -distance, 0.)
            for bx, by in ring(n, radius, x, y, rng.uniform(0., 2*math.pi)):
                add(origin, card, bx, by, tick, tick + life, stationary=stationary, jump=jump)
                bodies[-1]['hinted'] = hinted
            if cb.spawner(card):
                born = tick + rng.randint(60, 100)
                while born < tick + life:
                    labels = sorted(cb.families[cb.family_of(card)])
                    label = rng.choice(labels)
                    angle = rng.uniform(0., 2*math.pi)
                    add(origin, label, x + .9*math.cos(angle), y + .9*math.sin(angle),
                        born, born + rng.randint(40, 160), role='spawn')
                    born += rng.randint(60, 100)
            if card == 'Golem':
                parent = bodies[-1]
                dx, dy = _position(parent, tick + life)
                for offset in (-.7, .7):
                    add(origin, card, dx + offset, dy, tick + life,
                        tick + life + rng.randint(40, 120), role='child')
            next_tick = tick + rng.randint(20, 80)
        params['cycles'].append(cycle)

    # Sort deployment ids chronologically and remap the body's origin for slicing.
    order = sorted(range(len(truth)), key=lambda i: (truth[i][2], truth[i][0]))
    remap = {old: new for new, old in enumerate(order)}
    truth = [truth[i] for i in order]
    for b in bodies:
        b['origin'] = remap[b['origin']]
    frames, sources, clean_frames, clean_sources = [], [], [], []
    first_frames = {i: [t for t in ticks if t >= d[2]][:2] for i, d in enumerate(truth)}
    families = {c: sorted(cb.families[cb.family_of(c)] - {c}) for c in cards}
    cross = {c: [d for d in cards if cb.family_of(d) != cb.family_of(c)] for c in cards}
    for tick in ticks:
        units, origins, clean, clean_origins = [], [], [], []
        for b in bodies:
            if not b['born'] <= tick < b['dies']:
                continue
            x, y = _position(b, tick)
            if not .05 <= x <= 17.95 or not .05 <= y <= 31.95:
                continue  # walking off the arena ends visibility, never clamps movement
            origin, label = b['origin'], b['label']
            owner, card = truth[origin][:2]
            base = (label, owner, x, y, .95)
            if b['hinted'] and b['role'] == 'main' and tick in first_frames[origin]:
                base += (card,)
            clean.append(base)
            clean_origins.append(origin)
            if level == 'noisy':
                if noise.random() < params['miss']:
                    continue
                if noise.random() < params['cross_flip']:
                    label = noise.choice(cross[label])
                elif families[label] and noise.random() < params['flip']:
                    label = noise.choice(families[label])
                x += noise.gauss(0., params['jitter'])
                y += noise.gauss(0., params['jitter'])
            units.append((label, owner, x, y, *base[4:]))
            origins.append(origin)
        frames.append((tick, units))
        sources.append(origins)
        clean_frames.append((tick, clean))
        clean_sources.append(clean_origins)
    return dict(frames=frames, truth=truth, params=params, sources=sources,
                clean_frames=clean_frames, clean_sources=clean_sources)


def _match(truth, plays, cb):
    """Maximum-cardinality bipartite matching; nearest-first is only a tie break.

    A greedy nearest match can steal another deployment's only candidate.
    """
    edges = []
    for owner, card, tick, x, y in truth:
        candidates = [j for j, p in enumerate(plays) if p[0] == owner
                      and cb.family_of(p[1]) == cb.family_of(card)
                      and tick - 5 <= p[4] <= tick + 60
                      and math.hypot(p[2] - x, p[3] - y) <= 3.5]
        edges.append(sorted(candidates, key=lambda j: (
            plays[j][1] != card, abs(plays[j][4] - tick),
            math.hypot(plays[j][2] - x, plays[j][3] - y), j)))
    matched = {}

    def augment(i, visited):
        for j in edges[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in matched or augment(matched[j], visited):
                matched[j] = i
                return True
        return False

    for i in sorted(range(len(truth)), key=lambda i: (len(edges[i]), i)):
        augment(i, set())
    return matched


def _kind(cb, card):
    if cb.spawner(card):
        return 'spawner'
    if cb.death.get(card):
        return 'death-parent'
    if card in cb.champions:
        return 'champion'
    if any(b[1] == 1 for b, _ in cb.main.get(card, ())):
        return 'building'
    return 'multibody' if cb.count.get(card, 1) > 1 else 'singleton'


def check(scenario, cb):
    """Run a fresh tracker, match plays, and exercise invariants (a) through (d)."""
    return _check(scenario, cb, invariants=True)


def _check(scenario, cb, *, invariants):
    started = time.perf_counter()
    tracker, twin = UnitTracker(cb), UnitTracker(cb)
    plays, violations = [], []
    emitted_keys, emitted_ids = set(), set()
    checks = Counter()

    def violation(name, tick, detail):
        violations.append(dict(invariant=name, tick=tick, detail=detail))

    for frame, (tick, units) in enumerate(scenario['frames']):
        resolved = tracker.resolve(units, tick) if invariants else []
        if invariants and frame % 25 == 0:
            checks['b'] += 1
            saved = tracker.snapshot()
            twin.restore(saved)
            # Change observations, birth counter, history, and stats.
            perturbed = [(u[0], u[1], 17.5 - u[2], 31.5 - u[3], .99) for u in units]
            perturbed.append(('Knight', 0, 8., 8., .99, 'Knight'))
            tracker.update(tick + 20, perturbed, TOWERS, unknown=[('Building', 1, 9., 24.)])
            tracker.restore(saved)
            expected = twin.update(tick, units, TOWERS)
        else:
            expected = None
        output = tracker.update(tick, units, TOWERS)
        plays.extend(output[1])
        if invariants:
            checks['a'] += 1
            for index, identity in enumerate(resolved):
                if identity is not None and identity.id != tracker.last_tracks[index]:
                    violation('a', tick, f'unit {index}: resolve={identity.id}, assigned={tracker.last_tracks[index]}')
            if expected is not None and (output != expected or tracker.last_tracks != twin.last_tracks
                                         or tracker.stats != twin.stats):
                violation('b', tick, 'restored output, last_tracks, or stats differs from untouched twin')
            # Use emitted play events and cluster membership, not identity.state,
            # as the independent ledger for the identity contract.
            emitted_keys.update((p[0], p[1], p[4]) for p in output[1])
            for c in tracker.clusters:
                if (c['owner'], c['card'], c['t0']) in emitted_keys:
                    emitted_ids.update(c['members'])
            for p in tracker.played:
                if (p['owner'], p['card'], p['t0']) in emitted_keys:
                    emitted_ids.update(p['ids'])

    if invariants:
        tick = scenario['frames'][-1][0] if scenario['frames'] else 0
        retained = tracker.live + tracker.dead
        for t in retained:
            checks['c'] += 1
            identity = tracker.identity(t.id)
            if identity.state == 'played' and t.id not in emitted_ids:
                violation('c', tick, f'track {t.id} ({identity.card}) reports played without an emitted deployment')
        candidates = sorted({(t.owner, t.resolved) for t in retained
                             if t.id in emitted_ids and t.resolved is not None})
        for owner, card in candidates:
            checks['d'] += 1
            forgotten = UnitTracker(cb)
            forgotten.restore(tracker.snapshot())
            n = forgotten.forget_card(owner, card)
            second = forgotten.forget_card(owner, card)
            probes = [(t.label(), t.owner, t.x, t.y, .95) for t in retained]
            probes.extend(u for _, units in scenario['frames'][-5:] for u in units)
            after = forgotten.resolve(probes, tick)
            if n <= 0 or second != 0 or any(i is not None and i.owner == owner and i.card == card for i in after):
                violation('d', tick, f'forget({owner}, {card}): first={n}, second={second}, or card still resolves')

    truth = scenario['truth']
    matched = _match(truth, plays, cb)
    missing = sorted(set(range(len(truth))) - set(matched.values()))
    extra = sorted(set(range(len(plays))) - set(matched))
    failures = []
    for i in missing:
        owner, card, tick, x, y = truth[i]
        failures.append((tick, 'missed', owner, card, x, y, i))
    for j in extra:
        owner, card, x, y, tick = plays[j]
        failures.append((tick, 'extra', owner, card, x, y, j))
    first = min(failures, default=None)
    description, failure_class, context = '', None, None
    if first:
        tick, category, owner, card, x, y, index = first
        family = cb.family_of(card)
        failure_class = f'{category}/{_kind(cb, card)}/{family}'
        description = f'{failure_class}: owner={owner} card={card} tick={tick} at ({x:.2f}, {y:.2f})'
        context = dict(tick=tick, owner=owner, card=card, index=index,
                       truth=[d for d in truth if abs(d[2] - tick) <= 80],
                       plays=[p for p in plays if abs(p[4] - tick) <= 80],
                       frames=[(t, us) for t, us in scenario['frames'] if abs(t - tick) <= 5])
    elif violations:
        failure_class = 'invariant/' + violations[0]['invariant']
        description = failure_class + ': ' + violations[0]['detail']
        context = violations[0]
    return dict(true=len(truth), emitted=len(plays), matched=len(matched), missed=len(missing), extra=len(extra),
                wrong_card=sum(plays[j][1] != truth[i][1] for j, i in matched.items()),
                ok=not missing and not extra, description=description, failure_class=failure_class,
                context=context, violations=violations, invariant_counts=dict(Counter(v['invariant'] for v in violations)),
                invariant_checks=dict(checks), plays=plays, seconds=time.perf_counter() - started)


def _subset(scenario, keep):
    """Drop entire deployments, including all their production/death children."""
    order = sorted(keep)
    remap = {old: new for new, old in enumerate(order)}
    result = dict(scenario, truth=[scenario['truth'][i] for i in order])
    for frames_key, sources_key in (('frames', 'sources'), ('clean_frames', 'clean_sources')):
        result[frames_key], result[sources_key] = [], []
        for (tick, units), origins in zip(scenario[frames_key], scenario[sources_key]):
            selected = [(u, remap[o]) for u, o in zip(units, origins) if o in keep]
            result[frames_key].append((tick, [u for u, _ in selected]))
            result[sources_key].append([o for _, o in selected])
    return result


def _greedy(items, candidate, accept):
    """Chunk deletion followed by a greedy single-item deletion pass."""
    kept = list(items)
    width = max(1, len(kept)//2)
    while width:
        start = 0
        while start < len(kept):
            trial = kept[:start] + kept[start + width:]
            if accept(candidate(trial)):
                kept = trial
            else:
                start += width
        width //= 2
    return kept


def pytest_repro(scenario, name='minimized_births'):
    """Emit an explicit, independent of RNG pytest with expected deployments."""
    lines = [f'def test_{name}(cb):', '    from bot.live.multibody_fuzz import check', '    frames = []']
    frames, start = scenario['frames'], 0
    while start < len(frames):
        t0, units = frames[start]
        end, velocities = start + 1, []
        if end < len(frames):
            t1, following = frames[end]
            if len(units) == len(following) and all(u[:2] == v[:2] and u[4:] == v[4:]
                                                  for u, v in zip(units, following)):
                velocities = [((v[2] - u[2])/(t1 - t0), (v[3] - u[3])/(t1 - t0))
                              for u, v in zip(units, following)]
                end += 1
                while end < len(frames):
                    tick, current = frames[end]
                    if len(current) != len(units) or any(
                            u[:2] != v[:2] or u[4:] != v[4:]
                            or abs(u[2] + vx*(tick - t0) - v[2]) > 1e-9
                            or abs(u[3] + vy*(tick - t0) - v[3]) > 1e-9
                            for u, v, (vx, vy) in zip(units, current, velocities)):
                        break
                    end += 1
        if end - start >= 3:
            expressions = []
            for u, (vx, vy) in zip(units, velocities):
                x = repr(u[2]) if abs(vx) < 1e-14 else f'{u[2]!r} + {vx!r}*(t - {t0})'
                y = repr(u[3]) if abs(vy) < 1e-14 else f'{u[3]!r} + {vy!r}*(t - {t0})'
                expressions.append(f'({u[0]!r}, {u[1]}, {x}, {y}, ' + ', '.join(repr(v) for v in u[4:]) + ')')
            lines.append('    frames += [(t, [' + ', '.join(expressions) + '])')
            lines.append(f'               for t in {[t for t, _ in frames[start:end]]!r}]')
        else:
            end = start + 1
            lines.append(f'    frames.append({frames[start]!r})')
        start = end
    lines.extend([f'    expected = {scenario["truth"]!r}',
                  '    result = check({"frames": frames, "truth": expected}, cb)',
                  '    assert not result["violations"], result["violations"]',
                  '    assert result["ok"], result["description"]'])
    return '\n'.join(lines) + '\n'


def minimize(seed, level, cb):
    """Greedily remove deployments, noise, then frames; retain failure class.

    Slicing observed frames avoids regenerating different random draws when a
    deployment is dropped. The resulting fragment need not be a full game/deck.
    """
    scene = generate(seed, level)
    original = check(scene, cb)
    target = original['failure_class']
    if target is None:
        return dict(seed=seed, level=level, failure_class=None, scenario=scene, code='', attempts=0)
    attempts = 0

    def accept(candidate):
        nonlocal attempts
        attempts += 1
        # Dropping intervening plays must not turn a legal repeat into an
        # impossible cycle (and thereby invent a suppression failure).
        for owner in (0, 1):
            last = {}
            for index, deployment in enumerate(d for d in candidate['truth'] if d[0] == owner):
                card = deployment[1]
                if index - last.get(card, -5) < 5:
                    return False
                last[card] = index
        result = _check(candidate, cb, invariants=target.startswith('invariant/'))
        # Preserve the original event as well as its class. Otherwise trimming
        # observations of an earlier same-family deployment can manufacture a
        # different miss that happens to have the same description category.
        return (result['failure_class'] == target and result['context']['tick'] == original['context']['tick']
                and result['context'].get('owner') == original['context'].get('owner'))

    kept = _greedy(range(len(scene['truth'])), lambda ids: _subset(scene, set(ids)), accept)
    scene = _subset(scene, set(kept))
    if level == 'noisy':
        base = scene

        def with_noise(indices):
            noisy = set(indices)
            return dict(base, frames=[base['frames'][i] if i in noisy else base['clean_frames'][i]
                                      for i in range(len(base['frames']))],
                        sources=[base['sources'][i] if i in noisy else base['clean_sources'][i]
                                 for i in range(len(base['frames']))])
        # Often all noise can be removed at once; otherwise retain only the
        # noisy frames necessary for this class (including missed detections).
        if accept(with_noise([])):
            scene = with_noise([])
        else:
            changed = [i for i in range(len(base['frames'])) if base['frames'][i] != base['clean_frames'][i]]
            kept_noise = _greedy(changed, with_noise, accept)
            scene = with_noise(kept_noise)
    result = _check(scene, cb, invariants=target.startswith('invariant/'))
    centre = result['context']['tick']
    base = scene

    def with_frames(indices):
        return dict(base, **{key: [base[key][i] for i in indices]
                             for key in ('frames', 'sources', 'clean_frames', 'clean_sources')})
    window = [i for i, (tick, _) in enumerate(base['frames']) if centre - 80 <= tick <= centre + 100]
    if accept(with_frames(window)):
        scene = with_frames(window)
        base = scene
    # Never delete the observations around the failure: deleting every sighting
    # can manufacture a miss. Only trim context outside its confirmation window.
    protected = {i for i, (tick, _) in enumerate(base['frames']) if centre - 80 <= tick <= centre + 100}
    removable = [i for i in range(len(base['frames'])) if i not in protected]
    kept_frames = _greedy(removable, lambda ids: with_frames(sorted(protected | set(ids))), accept)
    scene = with_frames(sorted(protected | set(kept_frames)))
    result = check(scene, cb)
    return dict(seed=seed, level=level, failure_class=target, scenario=scene, result=result,
                attempts=attempts, code=pytest_repro(scene, f'fuzz_{level}_{seed}'))


def _seeds(value):
    if ':' in value:
        parts = [int(v) for v in value.split(':')]
        return range(*parts)
    return [int(v) for v in value.split(',')]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', default='0:500')
    parser.add_argument('--level', choices=(*LEVELS, 'both'), default='both')
    parser.add_argument('--out', required=True)
    parser.add_argument('--minimize', type=int, default=0, metavar='K')
    args = parser.parse_args(argv)
    cb = card_bodies()
    levels = LEVELS if args.level == 'both' else (args.level,)
    counts, classes, violations, totals = {}, Counter(), Counter(), Counter()
    representatives = {}
    source_hash = hashlib.sha256(Path(__file__).with_name('births.py').read_bytes()).hexdigest()
    with open(args.out, 'w') as output:
        for level in levels:
            counts[level] = Counter()
            for seed in _seeds(args.seeds):
                started = time.perf_counter()
                scenario = generate(seed, level)
                result = check(scenario, cb)
                result['seconds'] = time.perf_counter() - started
                row = dict(seed=seed, level=level, births_sha256=source_hash,
                           params=scenario['params'], **result)
                output.write(json.dumps(row, sort_keys=True) + '\n')
                output.flush()
                counts[level]['seeds'] += 1
                counts[level]['passed'] += result['ok']
                counts[level]['seconds'] += result['seconds']
                for key in ('true', 'emitted', 'matched', 'missed', 'extra', 'wrong_card'):
                    counts[level][key] += result[key]
                violations.update(result['invariant_counts'])
                totals.update(result['invariant_checks'])
                if result['failure_class']:
                    category = result['failure_class']
                    classes[category] += 1
                    representatives.setdefault(category, (seed, level))
                if counts[level]['seeds'] % 25 == 0:
                    n, passed = counts[level]['seeds'], counts[level]['passed']
                    print(f'{level}: {passed}/{n} pass ({passed/n:.1%}), '
                          f'{counts[level]["seconds"]/n:.3f} s/seed', flush=True)
    summary = dict(levels={level: dict(c, pass_rate=c['passed']/max(1, c['seeds']),
                                     seconds_per_seed=c['seconds']/max(1, c['seeds']))
                          for level, c in counts.items()},
                   failure_classes=dict(classes.most_common()), invariant_violations=dict(violations),
                   invariant_checks=dict(totals), births_sha256=source_hash)
    print(json.dumps(summary, indent=2), flush=True)
    for category, _ in classes.most_common(max(0, args.minimize)):
        seed, level = representatives[category]
        minimized = minimize(seed, level, cb)
        print(f'\n# {category}: seed={seed}, level={level}, '
              f'{minimized["attempts"]} shrink attempts\n{minimized["code"]}', flush=True)
    return summary


if __name__ == '__main__':
    main()
