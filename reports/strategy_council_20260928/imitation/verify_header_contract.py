"""Independently verify global headers using the frozen authoritative writer.

The bulk adapter compares every fresh perspective summary and all row arrays.
This closes its template reuse check by deriving the non-perspective header
from an actual fresh demonstration, not from any original archive's header.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from replay_sidecars import DATA, pins, initialize, sha, write
import replay_sidecars as replay
from clasher.rl import human_replay_v5 as v5
from clasher.rl.human_replay_demonstrations import parse_il_replay_record

V3_SHA = 'af205b0bc8614ff8a2ac794c7af0708f8822fe29681fccf6fd8ba7eaebe7ba82'
V3B_SHA = '1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493'
REUSE_FIELDS = ('reused_v2_episode_ids', 'v2_sha256')
EXEMPT_FIELDS = [f'extra.{name}' for name in REUSE_FIELDS] + ['extra.runtime_sha256']


def check_extra(extra, expected):
    """Only the explicitly accepted provenance fields may differ."""
    assert expected['runtime_sha256'] == V3B_SHA
    assert extra['runtime_sha256'] in (V3_SHA, V3B_SHA), extra
    actual = {k:v for k,v in extra.items() if k not in REUSE_FIELDS}
    actual['runtime_sha256'] = V3B_SHA
    assert actual == expected, (extra, expected)


def main(out):
    before=pins();initialize()
    index,side=replay.ex.perspective_list(0,'s117')[0]
    record=next(r for i,r in enumerate(replay.cb.read_payloads(0)) if i==index)
    match=parse_il_replay_record(record,replay.cb.slug_map())
    seat=('team','opponent').index(side)
    game=v5.reconstruct_perspective_v5(match,seat,replay.BUILDER,episode_id=index*2+seat,
                                     config=v5.ReconstructionConfigV5(tower_clamp=True))
    writer=v5.HumanReplayShardWriterV5();writer.add(game)
    path=out/'header-authority.npz';path.parent.mkdir(parents=True,exist_ok=True)
    header=writer.write(path)
    common={k:v for k,v in header.items() if k not in ('rows','perspectives','extra')}
    checked=0;historical=[]
    for source in sorted((DATA/'recon/engine-v3').glob('*/shard-*.npz')):
        with np.load(source,allow_pickle=False) as z:old=json.loads(z['header_json'].item())
        assert {k:v for k,v in old.items() if k not in ('rows','perspectives','extra')}==common,str(source)
        extra=old['extra'];phase=source.parent.name;shard,number=(int(source.stem.split('-')[i]) for i in (1,3))
        expected=dict(source_shard=shard,part=number,phase=phase,extraction='v3',runtime_sha256=before['runtime']['sha256'])
        check_extra(extra, expected)
        if extra['runtime_sha256'] == V3_SHA:
            historical.append(dict(unit=str(source.relative_to(DATA/'recon/engine-v3')),original=extra['runtime_sha256'],replay=expected['runtime_sha256']))
        checked+=1
    assert checked==1767 and len(historical)==270 and pins()==before
    reproduced=[]
    for item in historical:
        receipt=out/'units'/Path(item['unit']).with_suffix('.json')
        if receipt.exists():
            value=json.loads(receipt.read_text())
            assert value['arrays_equal']==31 and value['summary_equal'] and not any(value['violations'])
            reproduced.append(item['unit'])
    rule=dict(authority='COORDINATOR.md 2026-10-08 03:40 UTC',
        non_header_arrays='Every array equal in dtype, shape and C-order values.',
        header_and_summary='Every common field equal except the explicitly listed provenance fields; any other difference fails.',
        exempt_fields=EXEMPT_FIELDS, runtime_sha256_original_allowed=[V3_SHA,V3B_SHA],
        runtime_sha256_executed=V3B_SHA, original_headers='Preserved unchanged.',
        rows_and_perspectives='Compared in full by the frozen bulk writer, including every perspective summary; these are not exemptions.')
    write(out/'header-contract-audit.json',dict(passed=True,units=checked,common_header=common,rule=rule,
          historical_runtime_provenance=historical,historical_unit_ids=[v['unit'] for v in historical],requires_decision=False,
          determinism_evidence=dict(statement='Successful v3b reproduction of all arrays of the 270 v3-era units is additional determinism evidence.',
              verified_unit_ids=reproduced,verified_units=len(reproduced),expected_units=270,
              qualification='T2 PASS additionally requires all 1767 bulk replay receipts and artifact checksums.'),
          authoritative_example_sha256=sha(path),runtime=before['runtime'],extractor_sha256=before['extractor_sha256']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();main(args.out)
