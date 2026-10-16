"""Offline s27-m02 replay. SOURCE ONLY until independent review authorizes use.

One Runtime, one process, one recorded command channel, independent serial A/B.
Every output directory is fresh: no mixed-source resume or overwritten evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib import metadata
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback

from .protocol import (BASE, SCOPE_SHA256, command_kind, digest, file_sha, load_inputs,
                       opportunity_roster, plain, summary)

REPO = Path(__file__).resolve().parents[3]
JOB = Path('/mpac/sdicks02/jobs/clasher/bot-levels')
ENV = JOB / 'dev/env.sh'
AUDIT = Path(__file__).with_name('audit')
AUDIT_SHA256 = {
    'drive.py.txt': '0772fe4b5b6a9b1bb69a07ebbd9d9531efd773c36812820f00c31ba035545c3e',
    'towers.py.txt': '58033f080ecafe1f80d45e43c287253cd0ebd5010f04de695f3cad060edbfdf4',
    'provenance.json': '253a261ca1d7f3bdda4f86aa8bff75805ea801da8f2426f9ddd5c6d8ef895b29',
}


def hashes(paths):
    return {str(p.resolve()): file_sha(p) for p in sorted(set(paths)) if p.is_file()}


def audit_sources():
    """Portable, exact R18 writer audit; these text snapshots are never imported."""
    raw = {name: (AUDIT / name).read_bytes() for name in AUDIT_SHA256}
    for name, expected in AUDIT_SHA256.items():
        if hashlib.sha256(raw[name]).hexdigest() != expected:
            raise ValueError(f'portable audit bytes changed: {name}')
    manifest = json.loads(raw['provenance.json'])
    expected = {k: v for k, v in AUDIT_SHA256.items() if k != 'provenance.json'}
    if {k: v['sha256'] for k, v in manifest['files'].items()} != expected:
        raise ValueError('portable audit manifest does not bind the reviewed sources')
    return {str((AUDIT / name).resolve()): expected for name, expected in AUDIT_SHA256.items()}


def sources():
    # Primary source files are read and bound, never edited. New diagnostics
    # live below a package the primary runner's immediate *.py glob ignores.
    paths = list((REPO / 'bot').rglob('*.py')) + list((REPO / 'reports/explore/x4s').glob('*.py'))
    required = [ENV, REPO / 'bot/players/royalesim_vocab.json']
    if any(not p.is_file() for p in required):
        raise ValueError('missing source provenance input')
    return dict(hashes(paths + required), **audit_sources())


def serving_root(root):
    """The evaluation path resolver must serve the same authorized runtime."""
    selected = Path(os.environ.get('CLASHER_EVAL_RUNTIME_ROOT', root)).resolve()
    if selected != root.resolve():
        raise ValueError('CLASHER_EVAL_RUNTIME_ROOT must resolve to the authorized own runtime copy')
    return selected


def runtime_content(root):
    """Referenced source/native/checkpoints/catalog; no export or noise outputs."""
    root = serving_root(root)
    native = Path(os.environ.get('CLASHER_DELAY_NATIVE_DIR', root / 'native'))
    prior = root / 'reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json'
    pool = Path(os.environ.get('CLASHER_LOPP_MODELS', '/mpac/sdicks02/jobs/clasher/bot-lopp-models')) / 'pool.npz'
    required = [root / 'main02.pt', root / 'R3a.pt',
                Path(os.environ.get('CLASHER_ROOT', root)) / 'gamedata.json', prior, pool,
                native / 'clasher_core.abi3.so', Path(sys.executable),
                root / 'src/clasher/rl/contract_v5_tokens.json']
    if any(not p.is_file() for p in required):
        raise ValueError(f'missing referenced runtime files: {[str(p) for p in required if not p.is_file()]}')
    return hashes(required + list(root.rglob('*.py')) + list(native.glob('*.so')))


def environment():
    prefixes = ('BOT_', 'CLASHER_', 'PYTHON', 'OMP_', 'MKL_', 'OPENBLAS_', 'RAYON_', 'NUMPY_', 'CUDA_')
    return {k: v for k, v in sorted(os.environ.items()) if k.startswith(prefixes) or k == 'LEVELS_RUNTIME'}


def guard(out):
    """A reviewed invocation remains CPU-only on the authorized own-copy host."""
    if socket.gethostname().split('.')[0] != '127x01':
        raise ValueError('offline diagnostic is restricted to 127x01')
    if os.environ.get('PYTHONHASHSEED') != '0' or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('require startup PYTHONHASHSEED=0 and disabled CUDA')
    if any(os.environ.get(k) != '1' for k in
           ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'RAYON_NUM_THREADS')):
        raise ValueError('require reviewed single-thread CPU environment')
    if os.environ.get('CLASHER_BOT_RUNTIME_PINS') != 'live16402b-r2':
        raise ValueError('requires the live16402b-r2 own runtime copy')
    expected = (JOB / 'runtime/live16402b-r2').resolve()
    serving_root(expected)
    if Path(os.environ.get('CLASHER_BOT_RUNTIME', '')).resolve() != expected:
        raise ValueError('requires the 01 own runtime copy; frozen runtimes are read-only')
    if (Path(os.environ.get('CLASHER_ROOT', expected)).resolve() != expected
            or Path(os.environ.get('CLASHER_DELAY_NATIVE_DIR', expected / 'native')).resolve() != expected / 'native'):
        raise ValueError('game/native overrides must resolve inside the authorized own runtime copy')
    if os.environ.get('CLASHER_LEVELS_PLACEMENT_PROOF'):
        raise ValueError('do not inherit RoyaleSim placement environment into this LIVE diagnostic')
    if JOB.resolve() not in out.resolve().parents or out.resolve() == (JOB / 's27-m02').resolve():
        raise ValueError('output must be a fresh diagnostic job directory, separate from inputs/runtime')
    if (JOB / 'runtime').resolve() in out.resolve().parents or (JOB / 's27-m02').resolve() in out.resolve().parents:
        raise ValueError('cannot write into runtime or read-only input directories')


def write(path, value):
    path.write_text(json.dumps(plain(value), indent=2, sort_keys=True, allow_nan=False) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs', type=Path, default=JOB / 's27-m02')
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args(argv)
    guard(args.out)
    data, input_hashes, decisions, acks, anchor = load_inputs(args.inputs)
    cfg = data['session-config']
    roster = opportunity_roster(data['perception'], decisions.values())
    source_baseline = sources()  # Missing/changed audit bytes cannot reserve an output name.
    receipt = dict(protocol='s27-recorded-world-v1', time=datetime.now(timezone.utc).isoformat(),
        host=socket.gethostname(), pid=os.getpid(), args=vars(args), inputs=input_hashes, base=BASE,
        python=sys.version, source_sha256=source_baseline, environment_before_runtime=environment(),
        expected_opportunities=roster,
        recorded_config=cfg, input_session=data['session'],
        normalization='Unchanged recorded hp_frac for BOTH arms; live tower OCR already uses actual L6 maxima.',
        driver='One LiveSession: five acknowledged taps plus unverified internal reservation233/170; unchanged HUD confirmation is explicitly conditional, never a sixth acknowledged tap/verified actual play.',
        fast_model='Recorded Mac rl5-v10 is not loaded; recorded actions/gating drive, unbounded shadows use no fast cutoff.',
        limitations=['Conditional supported-card prior; not literal original command reproduction.',
                     'Frame234/action233 is an UNVERIFIED INTERNAL RESERVATION; original logs contain no tap/ack.',
                     'Recorded future world: no outcome, win-rate or causal counterfactual.',
                     'Public OCR rounding/early maximum-inference errors retained and exposed.',
                     'Missing polls use explicitly labelled LiveSession maintenance only; never searched.'])
    args.out.mkdir(parents=True, exist_ok=False)
    write(args.out / 'launch.json', receipt)
    facade, session = None, None
    failed = None
    rows_path = args.out / 'states.jsonl'
    with rows_path.open('x', buffering=1) as stream:
        def sink(row):
            stream.write(json.dumps(plain(row), sort_keys=True, allow_nan=False) + '\n')

        try:
            root = Path(os.environ['CLASHER_BOT_RUNTIME']).resolve()
            runtime_before = runtime_content(root)
            from bot.players.runtime import Runtime
            from bot.levels.scope import install
            rt = Runtime()
            install(rt)  # Before players, pollers, cache setup or acceptance.
            if any(rt.levels_scope.get(k) != v for k, v in SCOPE_SHA256.items()):
                raise ValueError('runtime prior differs from the accepted fixed conditional population')
            if runtime_content(root) != runtime_before or sources() != receipt['source_sha256']:
                raise ValueError('runtime/source changed during construction')
            from .live import RecordedFacade, Shadow, existing_configs, recorded_session_class
            from bot.levels.profile import LIVE_DECK, OWN_LEVELS, OWN_TOWER, OPP_TOWER
            from bot.live.translate import LiveSession, LiveTranslator
            from bot.search.lopp import _MODELS
            if set(cfg['deck']) != set(LIVE_DECK):
                raise ValueError('recorded own deck differs from fixed public account profile')
            lc, cache_manifest = existing_configs(rt)
            receipt.update(runtime_files=runtime_before, runtime_path=str(rt.root), pins=rt.pins,
                environment=environment(), levels_scope=rt.levels_scope, effective_prior_sha256=digest(rt.PRIOR),
                cache=cache_manifest, own_levels={c: OWN_LEVELS[c] for c in LIVE_DECK},
                own_tower=OWN_TOWER, opponent_tower=OPP_TOWER,
                packages={name: metadata.version(name) for name in ('numpy', 'torch')})
            facade = RecordedFacade({a: Shadow(rt, a, lc) for a in ('A', 'B')}, decisions, acks, sink)
            tr = LiveTranslator(rt, cfg['deck'], unknown_card=cfg['translator']['unknown_card'],
                               plays_from=cfg['translator']['plays_from'])
            def static_identity():
                return digest(dict(config=rt.R.config, meta=rt.R.meta, templates=rt.R.templates,
                                   tokens=rt.R.builder.token_names, costs=rt.R.costs, vocab=tr.vocab))
            static_before = static_identity()
            receipt['public_static_loaded_sha256'] = static_before
            receipt['loaded_tokens_sha256'] = digest(rt.R.builder.token_names)
            scfg = cfg['session']
            session = recorded_session_class(LiveSession)(rt, facade, cfg['deck'], seed=scfg['seed'],
                command_delay=scfg['command_delay'], expire=scfg['expire'], translator=tr)
            tr.clock.anchor(0, anchor['ts_ms'])
            model_digest = None
            for record in data['perception']:
                facade.frame = record
                # The driver's log adds fractional metadata tick AFTER producing
                # rec. Real LiveSession derives a rounded tick using its anchor.
                # Keeping/flooring the metadata would misplace n207: 99.60 ->100.
                rec = {k: v for k, v in record.items() if k not in ('n', 'tick', 'ts_ms', 'logged')}
                facade.expected_poll = int(round((record['timestamp_ms']-anchor['ts_ms'])/50)) // 5 * 5
                # Logged elixir already includes the ORIGINAL pending floor.
                # Do not silently refloor it to a divergent replay queue.
                if rec['elixir'] < sum(c.cost for c in session.ch.pending):
                    raise ValueError(f'recorded elixir/pending mismatch at frame {record["n"]}')
                session.step(rec)
                if facade.rows and facade.rows[-1]['n'] == record['n']:
                    logged = decisions.get(record['n'])
                    if logged is not None and session.log[-1]['action'] != logged['action']:
                        facade.mismatches.append(dict(n=record['n'], kind='session_action',
                            recorded=logged['action'], replay=session.log[-1]['action']))
                if model_digest is None and _MODELS:
                    model_digest = digest({k: vars(v) for k, v in _MODELS.items()})
            install(rt)
            if digest({k: vars(v) for k, v in _MODELS.items()}) != model_digest:
                raise ValueError('loaded learned weights/static columns changed during replay')
            if static_identity() != static_before:
                raise ValueError('common runtime config/meta/templates/public statics changed during replay')
            receipt['learned_model_loaded_sha256'] = model_digest
            receipt['loaded_dependency_sha256'] = hashes([Path(m.__file__) for m in sys.modules.values()
                if getattr(m, '__file__', None) and Path(m.__file__).suffix in ('.py', '.so')])
            if (runtime_content(root) != runtime_before or sources() != receipt['source_sha256']
                    or any(file_sha(Path(v['path'])) != v['raw_sha256']
                           for v in [cache_manifest['supported'], *cache_manifest['levels'].values()])):
                raise ValueError('runtime/source/cache changed during replay')
        except BaseException as ex:
            failed = dict(error=repr(ex), traceback=traceback.format_exc(),
                          n=facade.frame['n'] if facade and facade.frame else None,
                          expected_poll=facade.expected_poll if facade else None)
            sink(dict(kind='run_error', **failed))
        finally:
            if facade:
                try:
                    facade.close()
                except BaseException as ex:
                    close_error = dict(error=repr(ex), traceback=traceback.format_exc(), kind='close_error')
                    sink(close_error)
                    failed = failed or close_error
    driver = facade.evidence() if facade else dict(mismatches=[], missing_decisions=sorted(decisions),
        acknowledged_taps=len(acks), unverified_internal_reservations=sum(
            command_kind(r) == 'unverified_internal_reservation' for r in decisions.values()),
        conditional_hud_inferences=[], catch_up_polls=0)
    report = summary(facade.rows if facade else [], driver, dict(session.tr.stats) if session else {}, roster, failed)
    receipt.update(finished=datetime.now(timezone.utc).isoformat(), report_sha256=digest(report),
                   states_sha256=file_sha(rows_path), fatal_error=failed)
    write(args.out / 'report.json', report)
    write(args.out / 'receipt.json', receipt)
    text = (f"s27-m02 recorded-world diagnostic: {'PASS checks' if report['pass_checks'] else 'FAIL checks'}\n\n"
            f"Expected {report['expected']}; attempted {report['attempted']}; successful {report['successful']}; "
            f"failed {report['failed']}; unvisited {report['unvisited']}. "
            f"action differences {report.get('action_differences', 0)}.\n\n"
            "Conditional reconstruction: five acknowledged taps plus UNVERIFIED INTERNAL RESERVATION233/170; any unchanged HUD-inferred play is conditional, never an acknowledged tap/verified actual play.\n\n"
            "Diagnostic only: no causal or outcome claim. Full failures, Cannon examples and root HP are in JSON.\n")
    (args.out / 'report.md').write_text(text)
    print(text, end='')
    return 0 if report['pass_checks'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
