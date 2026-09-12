import json
import sys
from pathlib import Path

import pytest
import run_scaling_comparison as runner


@pytest.mark.parametrize('memory_verified', [False, None])
def test_missing_memory_readiness_refuses_before_corpus_access(tmp_path,monkeypatch,memory_verified):
    root=Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    plan=root/'reports/hog26_scaling_frozen_plan_20260912.json'
    readiness=tmp_path/'readiness.json'
    readiness.write_text(json.dumps({'status':'passed','implementation':runner.source_pin(),
        'collection_plan_sha256':runner.sha(plan),'combined_games':1536,'memory_verified':memory_verified}))
    def forbidden(*args,**kwargs):
        raise AssertionError('corpus access before memory readiness')
    monkeypatch.setattr(runner,'load_combined_training',forbidden)
    monkeypatch.setattr(sys,'argv',['runner','--data',str(tmp_path/'absent'),'--plan',str(plan),
        '--preflight',str(root/'reports/hog26_scaling_preflight_pin_20260912.json'),
        '--comparison',str(root/'reports/hog26_scalar_pilot_comparison_plan_20260911.json'),
        '--output',str(tmp_path/'output'),'--model','globals','--readiness',str(readiness)])
    with pytest.raises(ValueError,match='scaling readiness'):
        runner.main()
    assert not (tmp_path/'output').exists()
