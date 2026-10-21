"""Level-specific native configs without a Rust change (exploration; reports/bot/levels/DESIGN.md).

The native engine already resolves every secondary payload by a QUALIFIED key: entity stats carry
`payload_key` = 'level<L>:<name>' for L != 11 (engine-rs/mirror_snapshot.payload_key, written by
differential.entity), and lib.rs/spawn.rs/c56.rs/champions.rs look death_children, death_areas, death_objects,
production_children, spawn_areas, spirit_areas, ability_bombs and chain templates up by `stats.key()` (payload_key,
else name); spell carriers look their spell up by `spell_name`. Mirror uses exactly this for its level-12 copies.
So a planner config with per-seat levels is a pure config transform:

1. export(card, L): differential.config((card,), level=L) on the runtime's own Python engine (same gamedata and
   overlays as R.config; level 11 reproduces R.config exactly, checked per card by `check11`).
2. qualify: spell_name values naming the exported card -> 'level<L>:<card>'; side-table keys -> 'level<L>:<key>'.
3. mixed(level_of): cards[c].units[seat] (and .spawns[seat]) <- the level-L formation of that seat; the level-L card
   (spell, chain) and side tables are added under qualified keys. Level-11 entries are untouched, so a profile with
   every level 11 gives R.config itself (byte-identical JSON).
Limits (documented): direct-cast spells (no carrier units, e.g. Zap; the cast looks cards[<name>].spell up by its
plain name) are shared by both seats: they take the level of the seat holding the card in the root (ours if both);
Mirror keeps its fixed level-12 payloads; cards whose level-11 export differs from R.config keep level 11
(`unsupported`). Static NativeScripts metadata (scripted-opponent scores) stays level 11, except the leaf's crown
tower maxima (root.py).
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import sys
from importlib.machinery import PathFinder
from importlib.util import resolve_name
from pathlib import Path

SIDE = ('death_areas', 'death_objects', 'death_children', 'spirit_areas', 'production_children', 'spawn_areas',
        'ability_bombs', 'bomb_children', 'create_areas', 'hit_areas')
CACHE = Path(os.environ.get('CLASHER_LEVELS_CACHE', '/mpac/sdicks02/jobs/clasher/bot-levels/level-configs'))


def qkey(name, level):
    return name if int(level) == 11 else f'level{int(level)}:{name}'


def base_cards(cfg):
    """Ordinary card names (not Mirror's or our qualified copies)."""
    return sorted(n for n in cfg['cards'] if not n.startswith('level'))


def _same_json(a, b):
    """Compare the native payload representation (disk JSON turns tuples into lists)."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _export(card, level):
    from differential import config
    out = config((card,), level=level, mirror_templates=False)
    return dict(card=out['cards'][card], tables={t: out[t] for t in SIDE if out.get(t)})


def _qualify(entry, card, level):
    """In place: spell carriers of `card` name the level-L spell; side tables keyed by qualified names."""
    def walk(v):
        if isinstance(v, dict):
            if v.get('spell_name') == card:
                v['spell_name'] = qkey(card, level)
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(entry['card'])
    for table in entry['tables'].values():
        walk(table)
    entry['tables'] = {t: {qkey(k, level): v for k, v in rows.items()} for t, rows in entry['tables'].items()}
    return entry


def _runtime_export_identity(rt):
    """Bind exports to their effective Python engine, glue, receipts and data.

    Hash sources as well as release manifests: this also covers development
    overlays, stale receipts and modules imported from outside rt.root. The
    conservative root-wide scan includes lazy snapshot/engine-speed helpers.
    Called once when constructing the runtime's shared LevelConfigs, not per root.
    """
    root = getattr(rt, 'root', None)
    if root is None:
        exporter = getattr(sys.modules.get('differential'), '__file__', None)
        package = getattr(sys.modules.get('clasher'), '__path__', ())
        if exporter:
            root = Path(exporter).resolve().parent
            if root.name in ('engine-rs', 'engine-cards'):
                root = root.parent
        elif package:
            root = Path(next(iter(package))).resolve().parent
            if root.name == 'src':
                root = root.parent
        else:  # synthetic resources with no loaded engine/exporter
            return dict(manifests={}, source_sha256=None, gamedata_sha256=None)
    root = Path(root).resolve()
    manifests = {}
    for name in ('RECEIPT.json', 'CARDS-RUNTIME-RECEIPT.json'):
        path = root / name
        if path.exists():
            receipt = json.loads(path.read_text())
            for field in ('content_manifest_sha256', 'overlay_manifest_sha256'):
                if receipt.get(field):
                    manifests[f'{name}:{field}'] = receipt[field]

    files, helpers, selected = {}, [], {}

    def location(path, outside):
        path = Path(path).resolve()
        return path.relative_to(root).as_posix() if path.is_relative_to(root) else outside

    def sources(directory, label):
        directory = Path(directory).resolve()
        for path in directory.rglob('*.py'):
            relative = path.relative_to(directory)
            files.setdefault(path.resolve(), f'{label}/{relative.as_posix()}')

    # Include every runtime helper, even one lazily imported only at L16/L17.
    sources(root, 'runtime')
    for name in ('clasher', 'differential'):
        module = sys.modules.get(name)
        spec = None if module is not None else PathFinder.find_spec(name)
        package = getattr(module, '__path__', None) if module is not None else \
            getattr(spec, 'submodule_search_locations', None)
        origin = getattr(module, '__file__', None) if module is not None else getattr(spec, 'origin', None)
        if package:
            selected[name] = [location(directory, f'imported/{name}/{index}')
                              for index, directory in enumerate(package)]
            for index, directory in enumerate(package):
                sources(directory, f'imported/{name}/{index}')
        elif origin:
            selected[name] = location(origin, f'imported/{name}')
            # All glue siblings, including snapshot helpers beside differential.
            sources(Path(origin).parent, f'imported/{name}')

        if origin and Path(origin).suffix == '.py':
            helpers.append((name, Path(origin).resolve()))

    # Walk only the exporter/package entry points, not unrelated glue tests or
    # RL modules whose proposer imports can legitimately differ from the warmer.
    # Every engine/glue source remains content-hashed above.
    # Resolve static helper imports without executing them. This includes a
    # snapshot helper shadowed elsewhere on sys.path, or lazily used at L16.
    seen = set()
    while helpers:
        module_name, path = helpers.pop()
        if path in seen:
            continue
        seen.add(path)
        package_name = module_name if path.name == '__init__.py' else module_name.rpartition('.')[0]
        try:
            tree = ast.parse(path.read_bytes())
        except SyntaxError:  # unexecuted legacy scripts are still content-hashed
            continue
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                name = node.module or ''
                if node.level:
                    if not package_name:
                        continue
                    try:
                        name = resolve_name('.' * node.level + name, package_name)
                    except ImportError:
                        continue
                names.append(name)
                names.extend(f'{name}.{alias.name}' for alias in node.names if alias.name != '*')
        for name in names:
            if name.split('.')[0] in sys.stdlib_module_names:
                continue
            module = sys.modules.get(name)
            origin = getattr(module, '__file__', None)
            if module is None:
                search = None
                spec = None
                parts = name.split('.')
                for index in range(len(parts)):
                    prefix = '.'.join(parts[:index + 1])
                    parent = sys.modules.get(prefix)
                    if parent is not None:
                        search = getattr(parent, '__path__', None)
                        origin = getattr(parent, '__file__', None)
                        spec = getattr(parent, '__spec__', None)
                        if index == len(parts) - 1:
                            break
                        if search is None:
                            spec = None
                            origin = None
                            break
                        continue
                    spec = PathFinder.find_spec(prefix, search)
                    if spec is None:
                        break
                    search = spec.submodule_search_locations
                    if search is None and index < len(parts) - 1:
                        spec = None
                        break
                if parent is None:
                    origin = getattr(spec, 'origin', None)
            if not origin or not origin.endswith('.py'):
                continue
            dependency = Path(origin).resolve()
            if 'site-packages' in dependency.parts or 'dist-packages' in dependency.parts:
                continue
            files.setdefault(dependency, f'helper/{name}')
            selected[name] = files[dependency]
            helpers.append((name, dependency))

    digest = hashlib.sha256(json.dumps(selected, sort_keys=True).encode())
    for path, label in sorted(files.items(), key=lambda item: item[1]):
        digest.update(label.encode() + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    gamedata = rt.pins.get('gamedata_sha256')
    if gamedata is None:
        paths = sys.modules.get('clasher.paths')
        if paths is not None and hasattr(paths, 'gamedata_path'):
            path = paths.gamedata_path(must_exist=True)
        else:
            path = Path(os.environ.get('CLASHER_ROOT', root)) / 'gamedata.json'
        gamedata = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return dict(manifests=manifests, source_sha256=digest.hexdigest(), gamedata_sha256=gamedata)


class LevelConfigs:
    """Per-level card exports of one runtime, cached on disk (one JSON per level, keyed by the runtime pins)."""

    def __init__(self, rt, cache=CACHE):
        self.rt, self.R = rt, rt.R
        pins = rt.pins
        # Python/config changes can share native/data pins. Never reuse a
        # pre-B1 export missing healer pulses or rework member templates.
        config_hash = hashlib.sha256(json.dumps(self.R.config, sort_keys=True).encode()).hexdigest()
        # Pin the export/qualification and match-level engine patches as well as
        # the immutable runtime. New export code must never reuse old physics.
        source = hashlib.sha256()
        for name in ('configs.py', 'match.py', 'root.py'):
            source.update(name.encode())
            source.update(Path(__file__).with_name(name).read_bytes())
        self.export_code_sha256 = source.hexdigest()
        self.runtime_export_identity = _runtime_export_identity(rt)
        self.runtime_export_sha256 = hashlib.sha256(json.dumps(
            self.runtime_export_identity, sort_keys=True).encode()).hexdigest()
        tag = hashlib.sha256(json.dumps([os.environ.get('CLASHER_BOT_RUNTIME_PINS', 'r1'), pins.get('native_sha256'),
                                         pins.get('gamedata_sha256'), config_hash,
                                         self.export_code_sha256, self.runtime_export_sha256]).encode()).hexdigest()[:16]
        self.dir = Path(cache) / tag
        self.levels = {}
        self._mixed = {}

    def path(self, level):
        return self.dir / f'L{int(level)}.json'

    def build(self, level, cards=None):
        """Export every ordinary card at `level` (errors recorded, not raised) and cache it."""
        level = int(level)
        out = dict(level=level, cards={}, errors={})
        for card in cards or base_cards(self.R.config):
            try:
                out['cards'][card] = _export(card, level)
            except Exception as ex:   # e.g. dynamic_spells rejects unreconciled non-11 data
                out['errors'][card] = repr(ex)[:300]
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path(level).with_suffix('.tmp')
        tmp.write_text(json.dumps(out))
        tmp.replace(self.path(level))
        return out

    def check11(self):
        """Cards whose level-11 export reproduces R.config exactly (card entry and its side-table rows)."""
        data = self.load(11)
        good, bad = [], {}
        for card, e in data['cards'].items():
            same = _same_json(e['card'], self.R.config['cards'].get(card)) and all(
                _same_json(self.R.config.get(t, {}).get(k), v)
                for t, rows in e['tables'].items() for k, v in rows.items())
            if same:
                good.append(card)
            else:
                bad[card] = 'level-11 export differs from R.config'
        bad.update(data['errors'])
        return sorted(set(good)), bad

    def load(self, level):
        level = int(level)
        if level not in self.levels:
            p = self.path(level)
            self.levels[level] = json.loads(p.read_text()) if p.exists() else self.build(level)
        return self.levels[level]

    def supported(self):
        if not hasattr(self, '_supported'):
            p = self.dir / 'supported.json'
            cached = json.loads(p.read_text()) if p.exists() else {}
            reference = hashlib.sha256(json.dumps(self.R.config, sort_keys=True).encode()).hexdigest()
            if cached.get('comparison') == 'native-json-v1' and cached.get('reference_sha256') == reference:
                self._supported = set(cached['cards'])
            else:
                good, bad = self.check11()
                self.dir.mkdir(parents=True, exist_ok=True)
                tmp = p.with_name(f'.supported.{os.getpid()}.tmp')
                tmp.write_text(json.dumps(dict(cards=good, unsupported=bad, comparison='native-json-v1',
                                                reference_sha256=reference), indent=1))
                tmp.replace(p)
                self._supported = set(good)
        return self._supported

    def entry(self, card, level):
        """Qualified level-L export of `card` (deep copy, cached), or None if unavailable."""
        key = (card, int(level))
        if key not in self._mixed:
            data = self.load(level)
            e = data['cards'].get(card)
            self._mixed[key] = None if e is None or card not in self.supported() else \
                _qualify(copy.deepcopy(e), card, level)
        return self._mixed[key]

    def mixed(self, level_of, holders=None):
        """The planner config for per-seat levels. level_of(seat, card) -> int. holders: {card: seat} for direct-cast
        spells held by one seat (see module docstring); default: seat 0 wins ties. Returns (config, report)."""
        R = self.R
        cfg = dict(R.config)
        cards = dict(cfg['cards'])
        tables = {t: dict(cfg[t]) for t in SIDE if isinstance(cfg.get(t), dict)}
        report = dict(changed=0, unsupported=[], direct=[])
        for card in base_cards(R.config):
            levels = [int(level_of(seat, card)) for seat in (0, 1)]
            if levels == [11, 11]:
                continue
            new = dict(cards[card])
            units, spawns = list(new.get('units') or [[], []]), list(new.get('spawns') or [[], []])
            direct = new.get('spell') is not None and not any(new.get('units') or [[], []])
            for seat, level in enumerate(levels):
                if level == 11:
                    continue
                e = self.entry(card, level)
                if e is None:
                    report['unsupported'].append((card, level))
                    continue
                units[seat] = e['card']['units'][seat]
                if 'spawns' in new:
                    spawns[seat] = e['card']['spawns'][seat]
                cards[qkey(card, level)] = e['card']
                for t, rows in e['tables'].items():
                    tables.setdefault(t, {}).update(rows)
            if 'units' in new:
                new['units'] = units
            if 'spawns' in new:
                new['spawns'] = spawns
            if direct:
                seat = (holders or {}).get(card, 0)
                e = self.entry(card, levels[seat]) if levels[seat] != 11 else None
                if e is not None:
                    new['spell'] = e['card']['spell']
                report['direct'].append((card, levels))
            cards[card] = new
            report['changed'] += 1
        cfg['cards'] = cards
        cfg.update(tables)
        return cfg, report


class CutConfig:
    """fc for a level config: lopp_fast.config_need + fc_cut.mirror_need + fc_cut.SideCut, plus the qualified card
    keys the kept cards reference (a carrier's 'level<L>:Fireball' spell, a 'level<L>:ElectroDragon' chain), so the
    cut root resolves every lookup the uncut root does. Keyed text cache as lopp_fast._ConfigJson."""

    def __init__(self, cfg):
        from bot.cards.fc_cut import SideCut, strings
        self.cfg = cfg
        self.full = json.dumps(cfg)
        self.side = SideCut(cfg)
        self.cards_text = {n: json.dumps(n) + ':' + json.dumps(v) for n, v in cfg['cards'].items()}
        qualified = {n for n in cfg['cards'] if n.startswith('level')}
        self.refs = {n: frozenset(strings(v) & qualified) for n, v in cfg['cards'].items()}
        from bot.search.lopp_fast import _CutTexts
        self._cut = _CutTexts()

    def text(self, players, entities, pending):
        from bot.cards.fc_cut import mirror_need, strings
        from bot.search.lopp_fast import config_need
        cards = config_need(players, entities, pending, self.cfg['cards'])
        if cards is None:
            return self.full
        cards = set(mirror_need(cards, players, self.cfg['cards']))
        todo = list(cards)
        while todo:
            for r in self.refs[todo.pop()]:
                if r not in cards:
                    cards.add(r)
                    todo.append(r)
        cards = tuple(sorted(cards))
        kept, gated = self.side.keep(cards, strings([players, list(entities), list(pending)]))
        key = (cards, kept, gated)
        if key not in self._cut:
            self._cut[key] = ('{' + self.side.other(kept, gated) + ',"cards":{' +
                              ','.join(self.cards_text[n] for n in cards) + '}}')
        return self._cut[key]


def main():
    import argparse
    import sys
    import time
    ap = argparse.ArgumentParser(description='build the per-level export cache of this runtime')
    ap.add_argument('--levels', default='11,3,4,5,6,7,8,9')
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from bot.players.runtime import Runtime
    rt = Runtime()
    lc = LevelConfigs(rt)
    for level in map(int, a.levels.split(',')):
        t = time.process_time()
        out = lc.build(level)
        print(f'L{level}: {len(out["cards"])} cards, {len(out["errors"])} errors {sorted(out["errors"])[:12]}, '
              f'{time.process_time()-t:.0f} s CPU', flush=True)
    good, bad = lc.check11()
    print(f'level-11 export == R.config: {len(good)} cards; unsupported {len(bad)}: {dict(list(bad.items())[:20])}')
    print('cache', lc.dir)


if __name__ == '__main__':
    main()
