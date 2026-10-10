"""Exercise X's frozen K wrapper on disjoint smoke seeds, using v1 as a stand-in."""
import argparse
import json
from pathlib import Path
import resource
import sys
import time
from imitation.exit_r1 import screen
from imitation.exit_r1.rows import sha, write_json
import k_stage3


def game_frame():
    frame = sys._getframe(1)
    while frame is not None:
        if frame.f_code.co_name == 'run_game' and 'wall0' in frame.f_locals:
            return frame
        frame = frame.f_back
    raise AssertionError('policy inference outside K run_game decision timer')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True)
    parser.add_argument('--index', type=int, choices=(0, 1), required=True)
    args = parser.parse_args()
    job = Path(args.job)
    screen.execution_guard(str(job/'REPORTING.STOP'))
    assert json.loads((job/'seed-audit.json').read_text())['passed']
    plan = json.loads((job/'stage3-wrapper-qualification-plan.json').read_text())
    assert sha(Path(k_stage3.__file__)) == plan['adapter_sha256']
    assert sha(Path(__file__)) == plan['qualifier_sha256']
    assert sha(job/'stage3-harness.json') == plan['harness_receipt_sha256']
    checkpoint = job/'inputs/main02.pt'
    assert sha(checkpoint) == plan['checkpoint_sha256']
    harness = json.loads((job/'stage3-harness.json').read_text())
    arm = 'init' if args.index == 0 else 'smoke-student'
    checks = dict(fallback_calls=0, proposal_calls=0, legal_proposals=0,
                  min_inference_offset_seconds=None, max_proposal_seconds=0.)
    original_load = k_stage3.load_student

    class CheckedPolicy:
        def __init__(self, delegate):
            self.delegate = delegate

        def __getattr__(self, name):
            return getattr(self.delegate, name)

        def check_context(self):
            frame = game_frame()
            elapsed = time.monotonic() - frame.f_locals['wall0']
            assert elapsed >= 0
            minimum = checks['min_inference_offset_seconds']
            checks['min_inference_offset_seconds'] = elapsed if minimum is None else min(minimum, elapsed)
            assert frame.f_locals['deadline_seconds'] == .2
            players = frame.f_locals['players']
            assert set(players) == {0, 1}
            for actor, player in players.items():
                core = player.core
                assert core.arm == 'W' and core.search_threads == 1 and core.coarse_horizon == 160
                if arm == 'init' or actor != args.index % 2:
                    assert core.coarse_order == () and core.refine_proposals == ()
            return frame

        def sample(self, *positional, **keyword):
            self.check_context()
            checks['fallback_calls'] += 1
            return self.delegate.sample(*positional, **keyword)

        def propose(self, *positional, **keyword):
            self.check_context()
            begin = time.monotonic()
            result = self.delegate.propose(*positional, **keyword)
            checks['max_proposal_seconds'] = max(checks['max_proposal_seconds'], time.monotonic()-begin)
            ids = [proposal['action'] for proposal in result]
            assert len(ids) == len(set(ids)) and all(0 <= action < 2304 for action in ids)
            caller = sys._getframe(1)
            assert caller.f_code.co_name == 'poll'
            assert all(caller.f_locals['self'].mask[action] for action in ids)
            checks['proposal_calls'] += 1
            checks['legal_proposals'] += len(ids)
            return result

    k_stage3.load_student = lambda path: CheckedPolicy(original_load(path))
    begin = time.monotonic()
    k_stage3.run_case(job, arm, args.index, 4503601527370496+args.index,
                     {'init': str(checkpoint), arm: str(checkpoint)}, harness)
    assert checks['fallback_calls'] > 0
    assert (checks['proposal_calls'] == 0) if arm == 'init' else (checks['proposal_calls'] > 0)
    case = job/'stage3/cases'/f'fallback-{arm}-{args.index:04d}.json'
    record = json.loads(case.read_text())
    assert record['terminal'] and record['seed'] == 4503601527370496+args.index
    usage = resource.getrusage(resource.RUSAGE_SELF)
    write_json(job/f'qualification-{args.index}.json', dict(
        passed=True, index=args.index, arm=arm, seed=record['seed'], terminal=True,
        case_sha256=sha(case), adapter_sha256=plan['adapter_sha256'], checks=checks,
        cpu_seconds=usage.ru_utime+usage.ru_stime, wall_seconds=time.monotonic()-begin,
        interpretation='Wrapper qualification only; v1 stands in for a future final-EMA survivor. No reporting result.'))


if __name__ == '__main__':
    main()
