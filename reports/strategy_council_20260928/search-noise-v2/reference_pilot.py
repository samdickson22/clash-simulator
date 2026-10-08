"""Timing-only slow-reference pilot for the r2 affordability optimization gate.

Reconstruct the documented unoptimized operations without changing elt.py:
clone before checking spend, advance the exact ledger frame by frame, and
attempt all latent missed plays instead of skipping impossible repairs.
Uses the original pilot seed, cell and seat; never prints or retains outcomes.
"""
import bootstrap
import inspect
import textwrap
import elt
from worker import main

def reference_apply(state, event):
    out = elt.clone(state)
    try:
        out.advance(event.tick)
        cost = out.costs.get(event.name) if event.kind == 'card' else event.amount
        if event.kind != 'collector' and (cost is None or out.elixir + 1e-9 < cost):
            return None
        out.update(event.tick, out.events + [event])
    except (ValueError, KeyError, IndexError):
        return None
    return out

source = textwrap.dedent(inspect.getsource(elt.ELT.observe))
source = '\n'.join(line for line in source.splitlines()
                   if not line.lstrip().startswith(('affordable =', 'in_deck =')))
old = 'if not accepted and affordable and in_deck and self.missed_rate > 0 and candidate.q < 1:'
assert source.count(old) == 1
source = source.replace(old, 'if not accepted and self.missed_rate > 0 and candidate.q < 1:')
namespace = dict(vars(elt))
namespace['apply'] = reference_apply
exec(compile(source, '<r2-slow-reference-observe>', 'exec'), namespace)
elt.ELT.observe = namespace['observe']
main(['--pilot', '--index', '61', '--workers', '1'])
