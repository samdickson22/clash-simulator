"""Read-only fixture support; no simulator, policy, exporters or receipt writers.

These gates bind the existing approved pilot cache; they never repair/regenerate it.
Production config/root/scaling and the independent LIVE diagnostic stay unchanged.
"""
from __future__ import annotations

import hashlib
import json
from numbers import Integral

from .configs import CACHE, LevelConfigs, base_cards

# Prior clean native/s27 receipts, not values inferred from the failed pytest cache.
PILOT_CACHE = dict(
    reference_sha256='193b6615e3a1b7c13da664243e8d70050a35e5531ef12d2bbe1a92390e97865e',
    cards=121,
    supported=('e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc',
               'b97c2a61edd7fedc37182320a143673012f34e5b35e34effd69eb99d1aded8e7'),
    levels={
        11: ('1a36f377d55be3ea34e20225aa17eb92bead8e148b216b5b1346f0e7d04c8a94',
             '0700072fb0c81682de7e419363f3cee19cb2518ce49ece2332149ffc093828f9'),
        4: ('bd77caea134e469c89dc1d25d60f30474a404feef6b529d26b0e307a8f3a7d95',
            '314a6eaf17947386d889f04edc7ea7a7080aad703e4e6dc20a52ac8f26c7ee1c'),
        5: ('e88a6e04183f449754775b7f9d999c2ca3982601cb6f35dbbc1aec28d1555dfe',
            '38dc346eeaccbb14a625eb65cf055bb5fdaae7e069dc69ded2c90f17519caafd'),
        6: ('ad4b725b180cb2aa0abf50c13cf378ba2a954233eac43080b248f2f40146dcbb',
            '6dc6240cede22c916cd519a372b73f49265caf633f854ffdb382d48cc19d1398'),
        7: ('8fc9633bbd50906d7f95575b7c93ba6a39e540aec2997f67c2d50b8a1477b6f3',
            'af59897ecc32c11b40d5b67746f4a58bd85516f47e756498029b1663fddd8c84'),
        9: ('88a2472e54b090853bd18016cdafda642aafa1fd00f03ca6e7fa20f3edd638b2',
            '825ce4dc7b1fb58bce9b345df5dbaf325b5a9207b4738db310b6050f17a5eb0e'),
    })


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def units(path):
    field = path.rsplit('.', 1)[-1]
    if field == 'crown_tower_damage':
        return 'hitpoints per crown-tower hit; no conversion'
    if field in ('damage', 'max_hp', 'hp'):
        return 'hitpoints; no conversion'
    if field.endswith('_ms'):
        return 'milliseconds; no conversion'
    return 'native JSON value; no rescaling, quantization or tolerance'


def differences(old, new, path='config'):
    """All JSON field/type differences; only JSON's tuple-to-list representation is normalized."""
    old, new = json.loads(json.dumps(old)), json.loads(json.dumps(new))
    result = []

    def walk(a, b, where):
        if type(a) is type(b) is dict:
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    result.append(dict(path=f'{where}.{key}', old=a.get(key), new=b.get(key),
                                       old_present=key in a, new_present=key in b, units=units(f'{where}.{key}')))
                else:
                    walk(a[key], b[key], f'{where}.{key}')
        elif type(a) is type(b) is list and len(a) == len(b):
            for index, (left, right) in enumerate(zip(a, b)):
                walk(left, right, f'{where}[{index}]')
        elif type(a) is not type(b) or a != b:
            result.append(dict(path=where, old=a, new=b, old_type=type(a).__name__,
                               new_type=type(b).__name__, units=units(where)))
    walk(old, new, path)
    return result


def candidate_allowed(action, mask):
    """Planner timed waits have no tile-mask index; only their public WAIT bit authorizes them."""
    from bot.search.players import TIMED_WAITS
    if len(mask) != 2306:
        raise ValueError('fixture expects the 2306-entry public mask')
    if isinstance(action, bool) or not isinstance(action, Integral):
        return False
    if action in TIMED_WAITS:
        return bool(mask[2304])
    return 0 <= action < 2306 and bool(mask[action])


def normalized_spells(rt, lc):
    """Independent prior export/arithmetic anchors, recorded before real roots or decisions."""
    anchors = {
        'Fireball': dict(damage=688.0, crown_tower_damage=159.0,
                         crown_tower_damage_multiplier=0.22999999999999998, level=11,
                         radius=2.5, travel_speed=11.999999999999998, knockback_distance=1.0),
        'Poison': dict(damage=92.0, crown_tower_damage=21.0,
                       crown_tower_damage_multiplier=0.21999999999999997, level=11),
    }
    observed, fields = {}, []
    for card, expected in anchors.items():
        spell = rt.R.config['cards'][card]['spell']
        observed[card] = {field: spell.get(field) for field in expected}
        fields.extend(differences(expected, observed[card], f'normalized.L11.{card}'))
    if 4 in lc.levels:
        entry = lc.load(4)['cards']['Fireball']['card']
        expected = dict(damage=357.0, crown_tower_damage=83.0,
                        crown_tower_damage_multiplier=0.22999999999999998, level=4)
        observed['L4.Fireball'] = {field: entry['spell'].get(field) for field in expected}
        fields.extend(differences(expected, observed['L4.Fireball'], 'export.L4.Fireball'))
        carrier_damage = [[unit['stats']['damage'] for unit in entry['units'][seat]] for seat in (0, 1)]
        observed['L4.Fireball.carrier_damage'] = carrier_damage
        fields.extend(differences([[357.0], [357.0]], carrier_damage, 'export.L4.Fireball.carrier_damage'))
    if fields:
        raise ValueError('normalized spell anchors differ; no tolerance/repair permitted: ' + json.dumps(fields, sort_keys=True))
    return observed


class FrozenLevelConfigs(LevelConfigs):
    """Parse pre-existing bytes once, verify the complete L11 model, then allow registered memory reads only."""

    def __init__(self, rt, levels, *, cache=CACHE, expected=PILOT_CACHE):
        super().__init__(rt, cache=cache)
        requested = {11, *(int(level) for level in levels)}
        if not requested <= set(expected['levels']):
            raise ValueError(f'unregistered fixture levels: {sorted(requested - set(expected["levels"]))}')
        paths = {'supported': self.dir/'supported.json', **{str(n): self.path(n) for n in sorted(requested)}}
        missing = [str(p) for p in paths.values() if not p.is_file()]
        if missing:
            raise ValueError(f'missing existing fixture cache artifacts; no build/write permitted: {missing}')
        self._raw = {key: path.read_bytes() for key, path in paths.items()}
        self._data = {key: json.loads(raw) for key, raw in self._raw.items()}
        self._paths = paths
        self._registered = frozenset(requested)
        self._inventory = sorted(p.name for p in self.dir.iterdir())
        self._reference = sha(json.dumps(self.R.config, sort_keys=True).encode())
        self.levels = {int(key): data for key, data in self._data.items() if key != 'supported'}
        self._supported = frozenset(self._data['supported']['cards'])
        self.manifest = {key: dict(path=str(paths[key].resolve()), raw_sha256=sha(raw),
                                  canonical_sha256=sha(canonical(self._data[key]))) for key, raw in self._raw.items()}
        errors = []
        expected_cards = set(base_cards(self.R.config))
        support = self._data['supported']
        if (support.get('comparison') != 'native-json-v1' or support.get('unsupported') != {}
                or len(support['cards']) != len(self._supported) or self._supported != expected_cards
                or len(expected_cards) != expected['cards']):
            errors.append(dict(kind='supported set/comparison mismatch', cached=support, expected_cards=sorted(expected_cards)))
        if self._reference != expected['reference_sha256'] or support.get('reference_sha256') != self._reference:
            errors.append(dict(kind='runtime/support reference mismatch', runtime=self._reference,
                               cached=support.get('reference_sha256'), expected=expected['reference_sha256']))
        for key, item in self.manifest.items():
            raw_expected, canonical_expected = expected['supported'] if key == 'supported' else expected['levels'][int(key)]
            if (item['raw_sha256'], item['canonical_sha256']) != (raw_expected, canonical_expected):
                errors.append(dict(kind='cache bytes differ', path=item['path'], observed=item,
                                   expected_raw_sha256=raw_expected, expected_canonical_sha256=canonical_expected))
        for level, data in self.levels.items():
            cards, failed = set(data['cards']), set(data.get('errors', {}))
            if type(data.get('level')) is not int or data['level'] != level or cards & failed or cards | failed != expected_cards:
                errors.append(dict(kind='incomplete/overlapping export', level=level,
                                   missing=sorted(expected_cards - (cards | failed)), extra=sorted((cards | failed) - expected_cards)))
        good, bad = self.check11()  # Our load() never reads/builds; this cannot call supported().
        if set(good) != self._supported or bad:
            errors.append(dict(kind='L11 check11 mismatch', supported=sorted(self._supported), good=good, bad=bad))
        # Always include exact export->runtime fields if the reference or L11 check fails.
        if errors:
            fields = []
            for card, entry in self.levels[11]['cards'].items():
                fields.extend(differences(entry['card'], self.R.config['cards'].get(card), f'cards.{card}'))
                for table, rows in entry['tables'].items():
                    for key, value in rows.items():
                        fields.extend(differences(value, self.R.config.get(table, {}).get(key), f'{table}.{key}'))
            raise ValueError('read-only fixture cache validation failed: ' + json.dumps(dict(errors=errors, fields=fields), sort_keys=True))
        self.verify()

    def load(self, level):
        level = int(level)
        if level not in self._registered:
            raise ValueError(f'unregistered fixture L{level}; no future disk read/export permitted')
        return self.levels[level]

    def supported(self):
        return self._supported

    def build(self, *args, **kwargs):
        raise ValueError('read-only fixture cache cannot build exports or write receipts')

    def verify(self):
        if set(self.levels) != self._registered:
            raise ValueError('fixture registered memory levels changed')
        if sorted(p.name for p in self.dir.iterdir()) != self._inventory:
            raise ValueError('fixture cache directory entries changed; preserve unexpected artifacts')
        reference = sha(json.dumps(self.R.config, sort_keys=True).encode())
        if reference != self._reference:
            raise ValueError(f'fixture runtime config changed: {self._reference} -> {reference}')
        for key, path in self._paths.items():
            raw = path.read_bytes()
            if sha(raw) != self.manifest[key]['raw_sha256']:
                raise ValueError(f'fixture cache raw bytes changed: {path}; {self.manifest[key]["raw_sha256"]} -> {sha(raw)}')
            data = self._data['supported'] if key == 'supported' else self.load(int(key))
            if sha(canonical(data)) != self.manifest[key]['canonical_sha256']:
                raise ValueError('fixture parsed cache changed: ' + json.dumps(differences(json.loads(self._raw[key]), data, key)))
