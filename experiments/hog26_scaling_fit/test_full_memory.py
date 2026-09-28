import sys
from pathlib import Path

import check_full_memory
import numpy as np
import pytest


def test_incomplete_data_refused_without_arrays_or_output(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[2]
    def forbidden(*args,**kwargs):
        raise AssertionError('partial corpus array access')
    monkeypatch.setattr(np,'load',forbidden)
    monkeypatch.setattr(sys,'argv',['memory','--data',str(tmp_path/'missing'),
        '--plan',str(root/'reports/hog26_scaling_frozen_plan_20260912.json'),
        '--preflight',str(root/'reports/hog26_scaling_preflight_pin_20260912.json'),
        '--output',str(tmp_path/'report.json'),'--phase','neural'])
    with pytest.raises(ValueError,match='extension incomplete'):
        check_full_memory.main()
    assert not (tmp_path/'report.json').exists()
