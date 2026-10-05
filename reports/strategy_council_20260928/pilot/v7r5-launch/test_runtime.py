"""Run existing tests against v6 modules, using workspace cwd for test fixtures."""
import os
import sys
from pathlib import Path


def main():
    import clasher.rl.train_recurrent
    import clasher.rl.imitation
    import clasher.rl.parallel_rollout
    import clasher.rl.tbptt
    runtime = Path(os.environ['CLASHER_ROOT'])
    for module in (clasher.rl.train_recurrent, clasher.rl.imitation, clasher.rl.parallel_rollout, clasher.rl.tbptt):
        assert Path(module.__file__).is_relative_to(runtime)
        print('runtime import:', module.__file__, flush=True)
    os.chdir('/Users/sam/Desktop/code/clasher')
    import pytest
    return pytest.main(['-q', '-p', 'no:cacheprovider',
        'tests/test_recurrent_tbptt.py', 'tests/test_council_ppo_contract.py',
        'tests/test_pilot_learner_inference.py', 'tests/test_council_rollout_transport.py',
        'tests/test_train_resume_rng.py'])

if __name__ == '__main__':
    sys.exit(main())
