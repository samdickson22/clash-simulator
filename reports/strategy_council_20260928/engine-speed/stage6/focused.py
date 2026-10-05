"""Pinned, resumable focused gates using the unmodified Stage 2 comparator."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback

import clasher_core
from differential import CARDS, config
from stage2 import fingerprint, focused_case


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cards', nargs='+', required=True)
    p.add_argument('--cases', type=int, default=8)
    p.add_argument('--ticks', type=int, default=2200)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    pins = dict(source=fingerprint(), native=hashlib.sha256(
        Path(clasher_core.__file__).read_bytes()).hexdigest(),
        driver=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    declaration = dict(pins=pins, cards=args.cards, cases=args.cases, ticks=args.ticks)
    out = dict(**declaration, results={})
    if args.output.exists():
        old = json.loads(args.output.read_text())
        assert all(old[k] == v for k, v in declaration.items()), 'changed pins; use a fresh receipt'
        out = old
    for card in args.cards:
        for case in range(args.cases):
            key = f'{card}-{case}'
            if out['results'].get(key, {}).get('ok'):
                continue
            try:
                cfg = config(tuple(dict.fromkeys((*CARDS, card))))
                result = focused_case(card, case, cfg, ticks=args.ticks)
            except Exception:
                result = dict(ok=False, kind='exception', traceback=traceback.format_exc())
            out['results'][key] = result
            assert fingerprint() == pins['source'], 'source changed during gate'
            assert hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest() == pins['native']
            tmp = args.output.with_suffix('.tmp')
            tmp.write_text(json.dumps(out, indent=2) + '\n')
            tmp.replace(args.output)
            print(key, {k: v for k, v in result.items()
                        if k not in ('python', 'rust', 'field_diff', 'actions')}, flush=True)
            if not result['ok']:
                raise SystemExit(1)
    print('PASS', len(out['results']), flush=True)


if __name__ == '__main__':
    main()
