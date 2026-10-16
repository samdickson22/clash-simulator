"""Small deterministic fuzz gate; Runtime is built once for the whole module."""
import math

import pytest

from bot.live.multibody_fuzz import card_bodies, check, generate, ring

# births.py d5ba303a: quick seeds 0:30 achieved clean 2/30 (6.67%)
# and noisy 0/30. Allow one clean seed of margin; noisy has a zero floor.
# These are whole-scenario rates (every deployment matched, no extras).
# Full seeds 0:500 (generator with non-overlapping buildings): a5667ac9 clean 46/500 (9.2%), noisy 6/500 (1.2%);
# round 3 clean 90/500 (18.0%), noisy 12/500 (2.4%); invariant violations a/b/c/d: 0 on 200 seeds.
CLEAN_MIN = 3/30     # round 3: 18.0% of 500 clean seeds pass exactly (a5667ac9: 9.2%); noisy 2.4% (1.2%)
NOISY_MIN = 0.


@pytest.fixture(scope='module')
def cb():
    return card_bodies()


def test_generator_decks_cycle_and_board(cb):
    scene = generate(7, 'noisy')
    assert scene == generate(7, 'noisy')
    clean = generate(7, 'clean')
    assert clean['truth'] == scene['truth']
    assert clean['frames'] == scene['clean_frames']
    assert 1200 <= scene['params']['duration_ticks'] <= 2400
    assert all(b[0] - a[0] in (2, 3) for a, b in zip(scene['frames'], scene['frames'][1:]))
    for owner, deck in enumerate(scene['params']['decks']):
        assert len(deck) == len(set(deck)) == 8
        assert all(cb.main[c] for c in deck)
        assert any(cb.count[c] > 1 for c in deck)
        assert any(b[1] == 1 for c in deck for b, _ in cb.main[c])
        assert any(b[1] == 0 for c in deck for b, _ in cb.main[c])
        hand, queue = deck[:4], deck[4:]
        deployments = [d for d in scene['truth'] if d[0] == owner]
        last = {}
        for index, (_, card, tick, x, y) in enumerate(deployments):
            assert card in hand
            assert index - last.get(card, -5) >= 5
            last[card] = index
            hand[hand.index(card)] = queue.pop(0)
            queue.append(card)
            assert 0 <= x <= 18
            assert (15.5 <= y <= 28) if owner else (4 <= y <= 16.5)
            if index:
                assert 20 <= tick - deployments[index - 1][2] <= 82
            for previous in deployments[:index]:
                if tick - previous[2] <= 40:
                    assert math.hypot(x - previous[3], y - previous[4]) >= 2
    first_two = {i: [t for t, _ in scene['frames'] if t >= d[2]][:2]
                 for i, d in enumerate(scene['truth'])}
    for (tick, units), sources in zip(clean['frames'], clean['sources']):
        assert len(units) == len(sources)
        for u, origin in zip(units, sources):
            assert 0 <= u[2] <= 18 and 0 <= u[3] <= 32
            if len(u) == 6:
                assert u[5] == scene['truth'][origin][1]
                assert tick in first_two[origin]


def test_matching_does_not_greedily_steal_a_play(cb):
    from bot.live.multibody_fuzz import _match
    truth = [(0, 'Knight', 100, 5., 10.), (0, 'Knight', 100, 1., 10.)]
    plays = [(0, 'Knight', 3., 10., 101), (0, 'Knight', 8., 10., 102)]
    assert len(_match(truth, plays, cb)) == 2


@pytest.mark.parametrize('level,minimum', [('clean', CLEAN_MIN), ('noisy', NOISY_MIN)])
def test_fuzz_pass_rate_and_invariants(cb, level, minimum):
    results = [check(generate(seed, level), cb) for seed in range(30)]
    violations = [(seed, r['violations']) for seed, r in enumerate(results) if r['violations']]
    assert not violations, violations
    for invariant in 'abcd':
        assert all(r['invariant_checks'].get(invariant, 0) > 0 for r in results), invariant
    passed = sum(r['ok'] for r in results)
    rate = passed/len(results)
    print(f'{level}: {passed}/30 = {rate:.1%}, minimum={minimum:.1%}')
    assert rate >= minimum, (level, passed, [r['description'] for r in results if not r['ok']])


# REGRESSIONS: reduced from clean seeds 2, 3, and 12 after greedy shrinking;
# coordinates and ticks were then normalized and each failure rechecked.
# A champion dies after four intervening plays, then is legally redeployed: a new play (fixed in round 3: champion
# continuation needs a short gap and no cycle since the champion was played).
REGRESSIONS = ['ArcherQueen', 'Goblinstein', 'MightyMiner']


@pytest.mark.parametrize('champion', REGRESSIONS)
def test_minimized_regressions(cb, champion):
    # (owner, card, deployment tick, centre x/y, body death tick).
    deployments = [
        (1, champion, 100, 14., 27., 290),
        (1, 'Knight', 140, 4., 27., 220),
        (1, 'Archers', 180, 9., 27., 260),
        (1, 'MiniPekka', 220, 14., 28., 300),
        (1, 'Cannon', 260, 9., 22., 860),
        (1, champion, 300, 4., 27., 460),
    ]
    frames = [(tick, [
        (card, owner, bx, by - (0 if card == 'Cannon' else .04)*(tick - born), .95)
        for owner, card, born, x, y, dies in deployments if born <= tick < dies
        for bx, by in ring(cb.count[card], .5, x, y)
    ]) for tick in range(100, 381, 2)]
    result = check({'frames': frames, 'truth': [d[:5] for d in deployments]}, cb)
    assert not result['violations'], result['violations']
    assert result['ok'], result['description']
