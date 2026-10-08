"""Combine completed audit receipts; refuse incomplete or duplicate samples."""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def literals(path, variable):
    tree=ast.parse(Path(path).read_text())
    for node in tree.body:
        target=(node.target if isinstance(node,ast.AnnAssign) else
                node.targets[0] if isinstance(node,ast.Assign) else None)
        if isinstance(target,ast.Name) and target.id==variable:
            value=node.value.args[0] if isinstance(node.value,ast.Call) else node.value
            return ast.literal_eval(value)
    raise ValueError(variable)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('receipts',nargs='+',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--minimum-states',type=int,default=100000)
    args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    aliases=literals(root/'src/clasher/card_aliases.py','CARD_NAME_ALIASES')
    canonical=lambda name: aliases.get(name,name)
    cards=literals(root/'src/clasher/rl/public_scripted_opponent.py','SUPPORTED_CARDS')
    cards |= literals(root/'src/clasher/rl/c56_scripted.py','C56_ADDED_CARDS')
    c56={canonical(c) for c in cards}
    counts=Counter(); per_card=defaultdict(Counter); situations=defaultdict(Counter)
    scopes=Counter(); seen=set(); files={}
    for path in args.receipts:
        raw=path.read_bytes();r=json.loads(raw)
        counts.update(r['counts'])
        for name,v in r['per_card'].items():per_card[canonical(name)].update(v)
        # These bins intentionally describe the measured count predicate, not
        # an inferred presence/absence of non-Crown buildings after tower deaths.
        names={'payload':'payload_present','non_crown_building':'no_payload_more_than_6_live_buildings',
               'ordinary':'no_payload_at_most_6_live_buildings'}
        for name,v in r['per_situation'].items():situations[names[name]].update(v)
        remaining=r['counts']['states']
        for game in r['games']:
            if 'error' in game:
                raise ValueError(f"unqualified reconstruction error: {game}")
            if 'summary' not in game:continue
            summary=game['summary'];key=(summary['match_id'],game['seat'])
            if key in seen:raise ValueError(f'duplicate recorded perspective: {key}')
            seen.add(key)
            observed=min(remaining,game['rows']-int(summary['terminal_context_row']))
            remaining-=observed
            scope=('C56' if all(canonical(c) in c56 for c in summary['own_deck']+summary['opponent_deck'])
                   else 'S122-extension')
            scopes[scope]+=observed
        if remaining:raise ValueError(f'row provenance mismatch in {path}: {remaining}')
        files[str(path)]=hashlib.sha256(raw).hexdigest()
    if counts['states']<args.minimum_states:raise ValueError('incomplete audit')
    def ratio(n,d):return counts[n]/counts[d] if counts[d] else None
    value=dict(schema='clasher.mask-v2-summary.v1',counts=counts,per_card=per_card,
        per_situation=situations,recorded_scope_states=scopes,unique_recorded_perspectives=len(seen),
        rates=dict(v1_false_positive_per_legal_bit=ratio('v1_false_positive','v1_legal'),
                   v2_false_positive_per_legal_bit=ratio('v2_false_positive','v2_legal'),
                   states_with_v1_false_positive=ratio('states_v1_false_positive','states'),
                   states_with_v2_mismatch=ratio('states_v2_mismatch','states'),
                   raw_human_v1_legal_engine_rejected=ratio('raw_human_v1_legal_engine_rejected','raw_human_v1_legal')),
        assertions=dict(at_least_100k_states=counts['states']>=100000,
            all_residuals_classified=counts['residual_unclassified_bits']==0,
            optimized_simulator_matches_scalar=counts['oracle_fast_scalar_mismatch_bits']==0,
            sampled_rust_python_parity=counts['native_python_mismatch_bits']==0),
        scope='Current-engine replay of source recordings, one alternating perspective per match; retained decision states only. Raw human coordinates and projected labels are separate. No-op/abilities excluded from placement-bit equality.',
        residual='Hidden building counterfactual is audit-only and is never used as the public mask.',
        receipts=files)
    args.output.write_text(json.dumps(value,indent=2)+'\n')


if __name__=='__main__':main()
