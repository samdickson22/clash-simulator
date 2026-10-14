"""bot.search.run (HEADLINE-v1 cases, our engine, per-decision cost) plus the value-search diagnostics.

    python -m bot.value.run --out DIR --candidate K4SV-mlp1 --opponents R3a,v1 --games 300 --workers 40

Adds to each row's `search`: changed (fraction of searched decisions where phi alone would have
picked a different action from the same rollouts), mean phi_gap / v_gap (best - second), and
v_sane (fraction where the recomputed V argmax equals the action played).
"""
from bot.search import run as base

_summary = base.search_summary


def search_summary(player, timing):
    out = _summary(player, timing)
    ds = [d for d in getattr(player, 'decisions', []) if d and 'changed' in d]
    if ds:
        mean = lambda xs: sum(xs)/max(1, len(xs))
        out.update(changed=mean([d['changed'] for d in ds]),
                   phi_gap=mean([d['phi_gap'] for d in ds if 'phi_gap' in d]),
                   v_gap=mean([d['v_gap'] for d in ds if 'v_gap' in d]),
                   v_sane=mean([float(d['v_choice'] == d['action']) for d in ds]))
    return out


base.search_summary = search_summary

if __name__ == '__main__':
    base.main()
