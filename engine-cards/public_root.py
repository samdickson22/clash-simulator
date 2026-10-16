"""Compatible public v5 template defaults and attachment reconstruction.

Only static configuration and reconstructed public rows enter these helpers.
The v5 contract has no engine IDs or Three Musketeers rank channel: neither is
recovered here. See reports/cards/runtime/B1-PUBLIC-ROOT.md for approximations.
"""
from __future__ import annotations

import copy
import math

THREE_MEMBER = 'ThreeMusketeer_Rework_Character_1'
THREE_LOAD_MS = 700
GG_PARENT = 'GoblinGiant'
GG_RIDER = 'SpearGoblinGiant'
# A public heading is the end-of-tick heading, whereas attachments were placed
# using the start-of-tick heading. Allow any point on the static attachment arc
# within this radial tolerance; prefer the current-heading geometry below.
GG_POSITION_TOLERANCE = 0.25


def install_three_templates(config, builder, templates, projectile):
    """Explicit canonical rank-1 body and actual shot; never first-demo-wins.

    Called only for configs containing the B1 rework. The canonical mechanical
    name/selector and 700ms load remain intact. Other template keys are untouched.
    """
    formations = config['cards']['ThreeMusketeers']['units']
    bodies = [e for e in formations[0] if e['class'] == 'Troop' and e['stats']['name'] == THREE_MEMBER]
    if len(bodies) != 1 or bodies[0]['stats']['load'] != THREE_LOAD_MS or not bodies[0]['stats'].get('attack_select'):
        raise ValueError('invalid canonical public ThreeMusketeers body')
    if projectile['class'] != 'Projectile' or projectile['stats']['name'] != THREE_MEMBER:
        raise ValueError('invalid actual public ThreeMusketeers projectile')
    for kind, ns, value in (('Troop', 'troop_body', bodies[0]), ('Projectile', 'projectile', projectile)):
        token = builder.token_id('ThreeMusketeers', namespace=ns)
        if token <= 1:
            raise ValueError(f'no existing ThreeMusketeers public token in {ns}')
        if not any(nspace == ns and names and names[0] == 'ThreeMusketeers'
                   for nspace, names in value.get('public_identity', ())):
            raise ValueError(f'canonical ThreeMusketeers {kind} lacks explicit public alias')
        templates[token, kind] = copy.deepcopy(value)


class PublicGraphError(ValueError):
    """Observed attached riders cannot form a coherent bounded public graph."""

    def __init__(self, report):
        self.report = report
        super().__init__(f'unsupported public GoblinGiant attachment graph: {report}')


def _public_order(e):
    # IDs below are NEW row IDs, used only to break otherwise indistinguishable
    # public ties. They never enter geometry or pretend to remap engine IDs.
    return (e['owner'], e['x'], e['y'], *e['facing'], e['id'])


def rider_offset(parent, rank):
    """Known static attachment geometry evaluated at a reconstructed heading."""
    from clasher.logic_math import logic_vector_angle, logic_cos, logic_sin
    spec = parent['stats']['riders']
    n = int(spec['number'])
    angle = 180 + int(spec['shift']) + (n - 1 - rank) * int(spec['max_angle']) // n
    angle += logic_vector_angle(*parent['facing'])
    return logic_cos(angle, spec['radius']) / 1000., logic_sin(angle, spec['radius']) / 1000.


def repair_public_graph(entities):
    """Discard stale demo links; match only observed GG riders to observed GGs.

    Each (parent, rank) slot has capacity one. Deterministic augmenting matching
    maximizes admitted riders, preferring the public-heading slot distance.
    Coincident graphs and changed headings remain documented approximations.
    Missing/remote/over-capacity parents are rejected, never invented. A missing
    rider row is allowed and stays missing. Ordinary released SpearGoblins and
    projectile carriers are never attached.
    """
    parents = sorted((e for e in entities if e['class'] == 'Troop' and e['stats']['name'] == GG_PARENT), key=_public_order)
    riders = sorted((e for e in entities if e['class'] == 'Troop' and e['stats']['name'] == GG_RIDER), key=_public_order)
    report = dict(parents=len(parents), riders=len(riders), matched=0, ambiguous=0, unsupported=[])
    # Generic legacy shot prototypes can themselves inherit a rider body's
    # stale mount/rank. A shot is never an attachment, even on a rider-only row.
    for e in entities:
        if e['stats']['name'] in (GG_PARENT, GG_RIDER):
            e.pop('mount', None)
            e.pop('rider_rank', None)
    if not parents and not riders:
        return report
    ids = [e['id'] for e in entities]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate reconstructed public entity IDs')
    slots = []
    for p in parents:
        spec = p['stats'].get('riders')
        # This is deliberately the two-rider Goblin Giant policy, not a generic
        # guessed attachment mechanism for arbitrary future carrier types.
        if not spec or int(spec['number']) != 2 or int(spec['radius']) <= 0:
            raise ValueError('invalid public GoblinGiant static attachment geometry')
        for rank in range(2):
            dx, dy = rider_offset(p, rank)
            slots.append((p, rank, p['x'] + dx, p['y'] + dy))
    preferences = []
    for r in riders:
        edges = []
        for i, (p, rank, x, y) in enumerate(slots):
            radius = p['stats']['riders']['radius'] / 1000.
            center = math.hypot(r['x'] - p['x'], r['y'] - p['y'])
            if r['owner'] != p['owner'] or abs(center - radius) > GG_POSITION_TOLERANCE:
                continue
            edges.append(((r['x'] - x)**2 + (r['y'] - y)**2, _public_order(p), rank, i))
        edges.sort()
        preferences.append([edge[-1] for edge in edges])
        if len({slots[edge[-1]][0]['id'] for edge in edges}) > 1:
            report['ambiguous'] += 1
    assigned = {}

    def attach(r, visited):
        for s in preferences[r]:
            if s in visited:
                continue
            visited.add(s)
            if s not in assigned or attach(assigned[s], visited):
                assigned[s] = r
                return True
        return False

    # Process constrained rows first. Reverse public order on equal constraints
    # lets the augmenting displacement give earlier public rows their best slot.
    for r in sorted(range(len(riders)), key=lambda i: (len(preferences[i]), -i)):
        if not attach(r, set()):
            report['unsupported'].append(riders[r]['id'])
    report['matched'] = len(assigned)
    if report['unsupported']:
        raise PublicGraphError(report)
    for s, r in assigned.items():
        parent, rank, _, _ = slots[s]
        riders[r].update(mount=parent['id'], rider_rank=rank)
    return report
