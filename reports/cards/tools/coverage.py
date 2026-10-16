"""Build reports/cards/COVERAGE.md from the probe/fidelity/translator inputs (missing inputs show as '?').

python3 reports/cards/tools/coverage.py [--python probe-python.json] [--native probe-native.json]
    [--fidelity reports/cards/fidelity/results.jsonl] [--seen opponent-decks.jsonl] > reports/cards/COVERAGE.md
"""
import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pool import ladder_pool, ROOT

C56 = frozenset((
    'AngryBarbarians', 'Archer', 'ArcherQueen', 'Arrows', 'BabyDragon', 'Balloon', 'BarbLog', 'Bats',
    'Berserker', 'BlowdartGoblin', 'BombTower', 'Cannon', 'DarkPrince', 'Earthquake', 'ElectroSpirit',
    'FireSpirits', 'Fireball', 'Firecracker', 'FirespiritHut', 'Ghost', 'Giant', 'GoblinBarrel',
    'GoblinGang', 'GoblinHut', 'Goblins', 'Goblinstein', 'Golem', 'HogRider', 'IceGolemite', 'IceSpirits',
    'InfernoTower', 'Knight', 'Lightning', 'Log', 'MightyMiner', 'Miner', 'MiniPekka', 'MinionHorde',
    'Minions', 'Musketeer', 'Poison', 'Prince', 'Princess', 'Rascals', 'Rocket', 'RoyalDelivery',
    'RoyalHogs', 'SkeletonArmy', 'Skeletons', 'Tesla', 'Tornado', 'Valkyrie', 'Wallbreakers', 'Wizard',
    'Xbow', 'Zap'))

# Batch plan: live priority first, then arena order, then shared mechanics; champions last.
BATCH = {}
for b, names in {
    'A': 'GoblinCage SpearGoblins Bomber Tombstone Barbarians BattleRam MegaMinion BarbarianHut Mortar DartBarrell '
         'Witch Pekka SkeletonWarriors SkeletonDragons',
    'B': 'RoyalGiant ThreeMusketeers RoyalRecruits GiantSkeleton BattleHealer Freeze Snowball Vines SkeletonBalloon '
         'GoblinGiant GiantBuffer Hunter MiniSparkys',
    'C': 'ZapMachine InfernoDragon ElectroWizard RamRider MegaKnight IceWizard ElectroDragon Phoenix GoblinDemolisher '
         'LavaHound Bowler Assassin EliteArcher ElectroGiant SuspiciousBush RageBarbarian AxeMan DarkWitch '
         'ElixirGolem Ronin MovingCannon Fisherman WitchMother GoblinMachine',
    'D': 'Graveyard Heal Rage GoblinCurse Mirror Clone DarkMagic MergeMaiden GoblinDrill',
    'E': 'Elixir_Collector',
    'F': 'SkeletonKing GoldenKnight BossBandit Monk LittlePrince',
}.items():
    for n in names.split():
        BATCH[n.replace('_', ' ')] = b


def load_json(path, default):
    try:
        p = Path(path)
        if p.suffix == '.jsonl':
            return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def configured_scope():
    """Read the committed opt-in scope without constructing a runtime."""
    tree = ast.parse((ROOT / 'bot/cards/scope.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EXTRA_CARDS' for t in node.targets):
            return set(ast.literal_eval(node.value)) | C56
    raise ValueError('EXTRA_CARDS scope declaration not found')


def configured_proxies():
    """Read constant mapping metadata without importing a runtime-version module."""
    class DictKeywords(ast.NodeTransformer):
        def visit_Call(self, node):
            if not (isinstance(node.func, ast.Name) and node.func.id == 'dict'
                    and not node.args and all(k.arg is not None for k in node.keywords)):
                raise ValueError('Nonconstant proxy metadata call')
            return ast.Dict(keys=[ast.Constant(k.arg) for k in node.keywords],
                            values=[self.visit(k.value) for k in node.keywords])
    tree = ast.parse((ROOT / 'bot/cards/proxy_table.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NAMED' for t in node.targets):
            return ast.literal_eval(DictKeywords().visit(node.value))
    raise ValueError('NAMED proxy declaration not found')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--python', default='/mpac/sdicks02/jobs/clasher/cards/probe-python.json')
    ap.add_argument('--native', default='/mpac/sdicks02/jobs/clasher/cards/probe-native.json')
    ap.add_argument('--fidelity', default=str(ROOT / 'reports/cards/fidelity/results.jsonl'))
    ap.add_argument('--scope', default=str(ROOT / 'reports/cards/runtime/scope.json'))
    ap.add_argument('--status', default=str(ROOT / 'reports/cards/coverage-status.json'))
    ap.add_argument('--seen', default='/mpac/sdicks02/jobs/clasher/cards/opponent-decks.jsonl')  # git show origin/main:reports/live/loop/opponent-decks.jsonl
    a = ap.parse_args()
    py = {r['card']: r for r in load_json(a.python, [])}
    nat = {r['card']: r for r in load_json(a.native, [])}
    fid = {}
    for r in load_json(a.fidelity, []):
        if 'card' in r and 'verdict' in r and str(r.get('table')) == '160402':
            fid.setdefault(r['card'], {})[r['scenario']] = r['verdict']
    scope_input = load_json(a.scope, None)
    scope = set(scope_input['cards']) if scope_input is not None else configured_scope()
    status = load_json(a.status, {})
    streams = {name: (stream, entry['status']) for stream, entry in status.get('streams', {}).items()
               for name in entry['cards']}
    seen = Counter()
    for row in load_json(a.seen, []):
        for c in row.get('opponent_deck') or row.get('opp_deck') or []:
            seen[c] += 1
    named = configured_proxies()

    rows = []
    for c in sorted(ladder_pool(), key=lambda c: (c['name'] not in C56, BATCH.get(c['name'], 'Z'), c['arena'] or 99, c['name'])):
        n = c['name']
        p = py.get(n, {})
        r = nat.get(n, {})
        if n in C56:
            engine = 'C56'
        elif not r:
            engine = '?'
        elif r.get('native') == 'ok' and r.get('first_mismatch') is None:
            engine = 'digest=py'
        else:
            engine = f"diff@{r.get('first_mismatch')}" if r.get('native') == 'ok' else 'native err'
        py_status = 'probe ok' if p.get('python') == 'ok' else p.get('python', '?')
        if n == 'MergeMaiden' and p.get('deployed') and not p.get('spawned'):
            py_status = 'empty deployment'
            if engine == 'digest=py':
                engine = 'empty-deploy digest only'
        checks = fid.get(n, {})
        test = 'C56 gates' if n in C56 else (f"{sum(v == 'PASS' for v in checks.values())}/{len(checks)} baseline" if checks else '-')
        mapping = named.get(n)
        if n in ('Mirror', 'Clone') and mapping:
            stub = 'dynamic copied-body stub'
        elif mapping and mapping.get('bodies') == 0 and not mapping.get('body_map'):
            stub = 'spell/effect stub'
        else:
            stub = ('proxy ' + mapping['proxy_card']) if mapping and mapping.get('proxy_card') else ('body/effect stub' if mapping else 'no named stub')
        trans = 'C56' if n in C56 else (f'full-scope; {stub}' if n in scope else f'excluded action; {stub}')
        perc = 'C56 source vocab' if n in C56 else 'LIVE owner; unverified here'
        stream, progress = streams.get(n, ('C56', 'pinned baseline') if n in C56 else ('C2', 'specs; mechanics pending'))
        rows.append(f"| {c['display']} | `{n}` | {c['kind']} | {c['cost']} | {c['arena']} | {BATCH.get(n, '' if n in C56 else '?')} "
                    f"| {py_status} | {engine} | {test} | {stream}: {progress} | {trans} | {perc} | {seen.get(n, seen.get(c['display'], 0))} |")
    total = len(rows)
    missing = sum(1 for c in ladder_pool() if c['name'] not in C56)
    print('# Card coverage (generated by reports/cards/tools/coverage.py; do not edit by hand)\n')
    print(f'Pool: {total} ladder cards (gamedata.json, visible, no tower troops). C56: {total - missing}; outside C56: {missing}. '
          f'Configured full scope: {sum(c["name"] in scope for c in ladder_pool())}/{total}.\n')
    print('Columns: **py** = initial Python deployment probe; **engine** = native 681b5f2c vs Python 900-tick lockstep digest '
          '(digest equality does not establish full-state equivalence); **fidelity** = all recorded initial RoyaleSim 16.402 scenarios, '
          'before later batches; **workstream** = current acceptance ledger; **translator** = configured full-scope and mapping stubs, '
          'with active LIVE use owned separately; **perception** = LIVE LEAD domain; **seen** = opponent decks containing it '
          '(Battle Log inventory).\n')
    print('A successful deployment probe alone does not certify mechanics or action support. Spirit Empress (MergeMaiden) '
          'is excluded from the full runtime action scope because its action token is unknown. No candidate batch or r3 root '
          'is marked accepted by a source commit or review alone.\n')
    print('Kind, cost and arena are unmodified gamedata labels; balance-overlay values and live detections are tracked separately.\n')
    ledger = Path(a.status)
    try:
        ledger_label = ledger.relative_to(ROOT)
    except ValueError:
        ledger_label = ledger
    print(f'Acceptance ledger: `{ledger_label}` (as of {status.get("updated_utc", "unknown")}); live job details: `reports/cards/PROGRESS.md`.\n')
    print('Batches: A live priority (arenas 1–6 + seen live), B arenas 7–10, C remaining troops, D spells + drill, '
          'E elixir collector, F champions (abilities) last.\n')
    print('| card | name | kind | cost | arena | batch | py | engine | fidelity | workstream | translator | perception | seen |')
    print('|---|---|---|---:|---:|---|---|---|---|---|---|---|---:|')
    print('\n'.join(rows))


if __name__ == '__main__':
    main()
