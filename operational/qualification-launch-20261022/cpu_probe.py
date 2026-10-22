"""CPU imports and optional full qualification audit. No Runtime or engine construction."""
import json
import os
from pathlib import Path
import sys


def main():
    assert os.environ['CUDA_VISIBLE_DEVICES'] == ''
    assert sys.version_info[:3] == (3, 12, 12)
    assert sys.base_prefix == os.environ['PYTHONHOME']
    assert all(os.environ[k] == '1' for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'))
    root = Path(sys.argv[1])
    sys.path.insert(0, str(root))  # The only driver import root. Workers use the reviewed CLI bootstrap.
    from bot.pretrain_v1 import rl_driver as D
    import torch
    import numpy
    assert str(torch.__version__) == '2.7.1+cu118' and numpy.__version__ == '2.3.5'
    assert Path(D.__file__).absolute() == root/'bot/pretrain_v1/rl_driver.py'
    assert D.source_digest() == sys.argv[2]
    result = dict(source_sha256=D.source_digest(), python=sys.version, torch=str(torch.__version__),
                  numpy=numpy.__version__, cuda_initialized=torch.cuda.is_initialized(), engine_constructed=False)
    if len(sys.argv) == 4:
        config = D.read_config(sys.argv[3])
        result['audit'] = D.audit(config, qualification=True)
        assert result['audit']['status'] == 'GO', result['audit']
    assert not torch.cuda.is_initialized()
    assert 'clasher_core' not in sys.modules and 'bot.players.runtime' not in sys.modules
    result['cuda_initialized'] = torch.cuda.is_initialized()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
