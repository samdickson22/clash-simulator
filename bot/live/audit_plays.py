"""Offline opponent-play audit through the deployed LiveSession/LiveTranslator.

    python -m bot.live.audit_plays RUN [RUN ...] --births old.py --births bot/live/births.py --json out.json

No perception recomputation, policy inference, game, or network. Logged perception
already contains the driver's HUD/clock overrides and own-event deduplication.
The logged metadata tick is deliberately removed, as in loop/hand_audit.py.
Reported plays are accepted public events; raw births candidates are also in JSON.
Comparison matches the multiset (card, tick, x, y), positions rounded to 6 decimals;
a timing/position change therefore appears in both trackers' differences.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import contextmanager
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
import textwrap
import time

REPO = Path(__file__).resolve().parents[2]
RUNS_ROOT = Path('/mpac/sdicks02/scratch/live-loop/runs-all')
DEFAULT_BIRTHS = Path(__file__).with_name('births.py')
LEGACY = ('legacy C56/drop adapter: trim spawn hint; omit unknown; CardBodies.oov=set(); '
          'use deployed tree ClockTracker')


def jsonl(path, *, optional=False):
    if optional and not path.exists():
        return []
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def load_decks():
    """Read the committed battle log, never a dirty local copy; entirely local git."""
    result = subprocess.run(
        ['git', '-C', str(REPO), 'show', 'origin/main:reports/live/loop/opponent-decks.jsonl'],
        check=True, capture_output=True, text=True)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    return {row['run'].replace('-', ''): row for row in rows}


@contextmanager
def births_module(path):
    """Install the exact source as bot.live.births BEFORE importing the translator.

    Compile bytes directly to avoid stale .pyc files when comparing copied sources.
    Restore the previous module/package attribute so library/test callers are safe.
    """
    import bot.live as package
    name = 'bot.live.births'
    previous = sys.modules.get(name)
    old_attr = getattr(package, 'births', None)
    source = path.read_bytes()
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    package.births = module
    try:
        exec(compile(source, str(path), 'exec'), module.__dict__)
        legacy = 'unknown' not in inspect.signature(module.UnitTracker.update).parameters
        if legacy:
            original_cards, original_tracker = module.CardBodies, module.UnitTracker
            # d9fc2843d strictly unpacks 4 fields; the later clock-fix commit
            # accepts an optional fifth score. Preserve scores where supported.
            update_ast = ast.parse(textwrap.dedent(inspect.getsource(original_tracker.update)))
            fields = next((len(node.target.elts) for node in ast.walk(update_ast)
                           if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple)
                           and isinstance(node.iter, ast.Name) and node.iter.id == 'units'), 5)

            class LegacyCards(original_cards):
                def __init__(self, *args, **kw):
                    super().__init__(*args, **kw)
                    self.oov = set()

            class LegacyTracker(original_tracker):
                def update(self, tick, units, tower_alive, unknown=()):
                    if unknown:
                        raise ValueError('legacy tracker cannot handle unknown units')
                    return super().update(tick, [u[:fields] for u in units], tower_alive)

            module.CardBodies, module.UnitTracker = LegacyCards, LegacyTracker
            # Original LIVE glue's clock has an `anchor` DATA field, not the
            # driver's anchor method. Keep deployed timing for tracker comparisons.
            clock_spec = importlib.util.spec_from_file_location('_audit_deployed_births', DEFAULT_BIRTHS)
            deployed = importlib.util.module_from_spec(clock_spec)
            exec(compile(DEFAULT_BIRTHS.read_bytes(), str(DEFAULT_BIRTHS), 'exec'), deployed.__dict__)
            module.ClockTracker = deployed.ClockTracker
        yield dict(path=str(path), sha256=hashlib.sha256(source).hexdigest(),
                   adapter=f'{LEGACY}; unit_fields={fields}' if legacy else None)
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        if old_attr is None:
            delattr(package, 'births')
        else:
            package.births = old_attr


class ReplayPlayer:
    """Replay only logged submissions; no live player, models, or search loaded."""
    def __init__(self, actions):
        self.actions = actions

    def start(self, ctx):
        pass

    def act(self, view):
        from bot.players.base import Decision, WAIT
        return Decision(self.actions.get(int(view.tick), WAIT) if view.can_act else WAIT)

    def close(self):
        pass


def battles(records, events):
    """Driver match_start/end (including false HUD matches) define fresh sessions."""
    starts = [e for e in events if e.get('ev') == 'match_start']
    if not starts:
        return [(None, records)]
    out = []
    for i, start in enumerate(starts):
        lo = start['ts_ms']
        hi = starts[i + 1]['ts_ms'] if i + 1 < len(starts) else float('inf')
        ends = [e['ts_ms'] for e in events if e.get('ev') in ('match_end', 'false_match')
                and lo <= e.get('ts_ms', -1) < hi]
        hi = min(ends, default=hi)
        rows = [r for r in records if lo <= r.get('timestamp_ms', r.get('ts_ms', -1)) < hi]
        out.append((lo, rows))
    return out


def replay_battle(rt, cfg, records, events, decisions, anchor, deck, adapter):
    # The import must remain here: births_module is already active.
    from bot.live.translate import LiveSession, LiveTranslator
    tr_kw, sess_kw = dict(cfg.get('translator') or {}), dict(cfg.get('session') or {})
    if tr_kw.pop('cls', 'bot.live.translate.LiveTranslator') != 'bot.live.translate.LiveTranslator':
        raise ValueError('unsupported translator class in session-config.json')
    if sess_kw.pop('cls', 'bot.live.translate.LiveSession') != 'bot.live.translate.LiveSession':
        raise ValueError('unsupported session class in session-config.json')
    if adapter and tr_kw.get('unknown_card', 'drop') != 'drop':
        raise ValueError('legacy births supports C56/drop only; refusing non-drop config')
    if tr_kw.get('plays_from', 'births') != 'births':
        raise ValueError('audit requires plays_from=births')
    tr = LiveTranslator(rt, cfg['deck'], **tr_kw)
    indices = {r['n'] for r in records if 'n' in r}
    submitted = [d for d in decisions if d.get('submitted') and
                 ('n' not in d or d['n'] in indices)]
    player = ReplayPlayer({int(d['poll']): int(d['action']) for d in submitted})
    sess = LiveSession(rt, player, cfg['deck'], translator=tr, **sess_kw)
    if anchor is not None:
        tr.clock.anchor(0, anchor)
    pauses = [e for e in events if e.get('ev') in ('paused_by_user', 'resumed_by_user')]
    paused, skipped, errors = False, 0, []
    pause_i = 0
    for row in records:
        ts = row.get('timestamp_ms', row.get('ts_ms', -1))
        while pause_i < len(pauses) and pauses[pause_i]['ts_ms'] <= ts:
            paused = pauses[pause_i]['ev'] == 'paused_by_user'
            pause_i += 1
        if paused:
            skipped += 1
            continue
        rec = {k: v for k, v in row.items() if k not in ('n', 'logged', 'tick', 'ts_ms')}
        try:
            sess.step(rec)
        except Exception as ex:  # drive.py logs errors and keeps feeding frames too
            errors.append(dict(n=row.get('n'), error=f'{type(ex).__name__}: {ex}'))
    c56 = set(json.loads((REPO / 'bot/fidelity/c56_native_ids.json').read_text()))

    def play(tick, card, x, y, **extra):
        return dict(tick=int(tick), seconds=int(tick) * .05, card=card,
                    x=float(x), y=float(y), off_deck=None if deck is None else card not in deck,
                    c56=card in c56, **extra)

    plays = [play(e['tick'], e.get('true_id', e['name']), e['x'], e['y'], public_card=e['name'])
             for e in tr.public_events if e['seat'] == 1 and e['kind'] == 'card']
    derived = [play(t, c, x, y) for o, c, x, y, t in tr.derived_plays if o == 1]
    sess.close()
    return dict(plays=plays, derived_plays=derived, per_card=dict(sorted(Counter(p['card'] for p in plays).items())),
                total_plays=len(plays), off_deck=None if deck is None else sum(p['off_deck'] for p in plays),
                off_deck_c56=None if deck is None else sum(p['off_deck'] and p['c56'] for p in plays),
                translator_stats=dict(sorted(tr.stats.items())), tracker_stats=dict(sorted(tr.tracker.stats.items())),
                records=len(records), paused_records=skipped, polls=len(sess.log), errors=errors,
                effective_replay_config=dict(translator=dict(tr_kw, cls='bot.live.translate.LiveTranslator',
                    unknown_card=tr.unknown_card, plays_from=tr.plays_from, card_level=tr.card_level),
                    session=dict(cls='bot.live.translate.LiveSession', seed=sess.seed,
                                 command_delay=sess.command_delay, expire=sess.expire),
                    clock_anchor_ms=anchor, logged_tick='removed (driver metadata)',
                    actions='logged submitted actions; WAIT otherwise',
                    own_events='already deduplicated by deployed driver', adapter=adapter))


def play_key(play):
    return play['card'], play['tick'], round(play['x'], 6), round(play['y'], 6)


def compare(results):
    counts = [Counter(play_key(p) for p in r['plays']) for r in results]
    out = []
    for i, result in enumerate(results):
        others = Counter()
        for j, count in enumerate(counts):
            if i != j:
                others |= count
        remaining = counts[i] - others
        unique = []
        for p in result['plays']:
            key = play_key(p)
            if remaining[key]:
                unique.append(p)
                remaining[key] -= 1
        out.append(dict(tracker=result['tracker'], total_plays=result['total_plays'],
                        off_deck=result['off_deck'], off_deck_c56=result['off_deck_c56'], only_here=unique))
    return out


def audit(runs, paths=None, *, runs_root=RUNS_ROOT, decks=None, rt=None):
    from bot.players.runtime import Runtime
    rt = rt or Runtime()
    decks = load_decks() if decks is None else decks
    inputs, output = [], dict(schema='clasher.live.audit-plays.v1', trackers=[], runs=[])
    for run in runs:
        directory = Path(runs_root) / run
        cfg = json.loads((directory / 'session-config.json').read_text())
        events = jsonl(directory / 'events.jsonl', optional=True)
        decisions = jsonl(directory / 'decisions.jsonl', optional=True)
        rows = jsonl(directory / 'perception.jsonl')
        deck_row = decks.get(Path(run).name.replace('-', ''))
        deck = deck_row.get('opp_deck') if deck_row else None
        split = battles(rows, events)
        inputs.append((cfg, events, decisions, deck, split))
        output['runs'].append(dict(run=run, path=str(directory.resolve()), opponent_deck=deck,
            deck_source='origin/main:reports/live/loop/opponent-decks.jsonl' if deck is not None else None,
            warnings=([] if deck is not None else ['No battle-log deck; off-deck is unknown.']) +
                     ([] if decisions else ['No decisions.jsonl submissions; replay player always WAITs.']) +
                     ([] if any(e.get('ev') == 'match_start' for e in events) else
                      ['No match_start event; one unanchored session using recorded clock/phase.']),
            battles=[dict(battle=i + 1, trackers=[]) for i in range(len(split))]))
    for i, path in enumerate(paths or [DEFAULT_BIRTHS]):
        path = Path(path).resolve()
        with births_module(path) as metadata:
            metadata['id'] = f'b{i}'
            output['trackers'].append(metadata)
            for run_out, (cfg, events, decisions, deck, split) in zip(output['runs'], inputs):
                for battle, (anchor, rows) in zip(run_out['battles'], split):
                    start = time.monotonic()
                    result = replay_battle(rt, cfg, rows, events, decisions, anchor, deck, metadata['adapter'])
                    result.update(tracker=metadata['id'], replay_seconds=round(time.monotonic() - start, 3))
                    battle['trackers'].append(result)
    for run in output['runs']:
        for battle in run['battles']:
            battle['comparison'] = compare(battle['trackers']) if len(output['trackers']) > 1 else []
    return output


def print_plays(plays, out):
    print('  tick  seconds card                      x       y  off-deck', file=out)
    for p in plays:
        flag = '?' if p['off_deck'] is None else 'YES' if p['off_deck'] else 'no'
        print(f"{p['tick']:6d} {p['seconds']:8.2f} {p['card']:<23} {p['x']:7.2f} {p['y']:7.2f}  {flag}", file=out)


def print_report(report, out=None):
    out = out or sys.stdout
    for t in report['trackers']:
        print(f"{t['id']} {t['path']} sha256={t['sha256']} adapter={t['adapter'] or 'none'}", file=out)
    print('Plays = accepted opponent public events; raw derived candidates are in JSON. Off-deck ? = no deck.', file=out)
    for run in report['runs']:
        print(f"\nRUN {run['run']} deck={run['opponent_deck']}", file=out)
        for warning in run['warnings']:
            print(f'WARNING: {warning}', file=out)
        for battle in run['battles']:
            for result in battle['trackers']:
                print(f"Battle {battle['battle']} {result['tracker']}", file=out)
                print_plays(result['plays'], out)
                print('Per-card:', json.dumps(result['per_card'], sort_keys=True), file=out)
                print(f"SUMMARY {run['run']} battle={battle['battle']} {result['tracker']} "
                      f"plays={result['total_plays']} off-deck={result['off_deck']} "
                      f"off-deck-C56={result['off_deck_c56']} derived={len(result['derived_plays'])} "
                      f"errors={len(result['errors'])} seconds={result['replay_seconds']}", file=out)
                print('Effective replay config:', json.dumps(result['effective_replay_config'], sort_keys=True), file=out)
                print('Translator stats:', json.dumps(result['translator_stats'], sort_keys=True), file=out)
                print('Tracker stats:', json.dumps(result['tracker_stats'], sort_keys=True), file=out)
                if result['errors']:
                    print('ERRORS:', json.dumps(result['errors']), file=out)
            if battle['comparison']:
                print('COMPARISON battle', battle['battle'], '|', ' | '.join(
                    f"{r['tracker']}: plays={r['total_plays']} off-deck={r['off_deck']} "
                    f"off-deck-C56={r['off_deck_c56']} only-here={len(r['only_here'])}"
                    for r in battle['comparison']), file=out)
                print('Only-here uses exact card/tick and x/y rounded to 6 decimals (multiset).', file=out)
                for r in battle['comparison']:
                    print(f"Only {r['tracker']}:", file=out)
                    print_plays(r['only_here'], out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+')
    parser.add_argument('--births', action='append', type=Path)
    parser.add_argument('--runs-root', type=Path, default=RUNS_ROOT)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args(argv)
    report = audit(args.runs, args.births, runs_root=args.runs_root)
    print_report(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + '\n')
    return int(any(r['errors'] for run in report['runs'] for b in run['battles'] for r in b['trackers']))


if __name__ == '__main__':
    raise SystemExit(main())
