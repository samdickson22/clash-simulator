"""Actual common-loop/queue/native drain fixtures; source-only until fresh review.

The scripted facade supplies only native own HUD and a minimal reservation packet,
not a learned feature builder/Translator. It runs the production play_match,
RsimMatch.execute/refresh/hand_card and frozen CommandQueue against the pinned binary.
No Runtime, policy model, spell registry or cache is constructed. Existing real
Translator/controller integration remains mandatory in the same final suite.
"""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from bot.players import royalesim_match as match
from bot.players.base import Decision, WAIT
from . import terminal_probe as probe

JOB = Path('/mpac/sdicks02/jobs/clasher/bot-levels')


@dataclass(frozen=True)
class OwnView:
    """Minimal dataclass contract consumed by frozen CommandQueue.own_packet."""
    tick: int
    seat: int
    own: dict
    packet: object


@pytest.fixture(scope='module', autouse=True)
def native_paths():
    """Paths only; the facade never constructs a builder or any game-data object."""
    from bot.players.runtime import Runtime
    from .placement_probe import installed_identity, validate_identity
    paths = Runtime.__new__(Runtime)
    paths.root = Path(os.environ['CLASHER_BOT_RUNTIME']).resolve()
    paths.native_dir = paths.root/'native'
    paths._bootstrap_paths()
    validate_identity(installed_identity())


class ScriptedPlayer:
    name, deadline_seconds = 'terminal-fixture', None

    def __init__(self, commands=None):
        self.commands, self.polls, self.closed = commands or {}, [], False

    def start(self, ctx):
        self.ctx = ctx

    def act(self, view):
        assert view.tick < 6000, 'no actor may be polled during the pinned no-play phase'
        self.polls.append((view.tick, view.can_act))
        return Decision(action=self.commands.get(view.tick, WAIT), stats={})

    def close(self):
        self.closed = True


class ObservedBattle:
    """Record calls without changing native operations or consuming RNG."""

    def __init__(self, native):
        self.native, self.calls = native, []

    def __getattr__(self, name):
        return getattr(self.native, name)

    def step(self, commands, ticks):
        self.calls.append((json.loads(self.native.state_json())['tick'], list(commands), ticks))
        return self.native.step(commands, ticks)


def scripted_match(monkeypatch, *, start=5970, weaker=1, tie=False, crown_end=False, king_end=False, poison=False):
    """Real native match with a recorded-own-HUD facade; no policy/feature construction."""
    from bot.players.royalesim_adapter import our_card
    original = match.RsimMatch
    b, names = probe.scenario(start=start, weaker=weaker, tie=tie, crown_end=crown_end, king_end=king_end)
    m = original.__new__(original)
    m.b, m.client, m.names = ObservedBattle(b), '16.402', names
    m.decks = [list(probe.DECK), list(probe.DECK)]
    m.plays, m.events, m.public_events, m.command_results = {0: [], 1: []}, {0: [], 1: []}, [], []
    m.tr = SimpleNamespace(stats=Counter())
    m.own = {a: SimpleNamespace(mismatch=Counter(), play=lambda tick, card: None) for a in (0, 1)}
    m.refresh()
    m.command_phase = match.CommandPhase(m.b, m.state)
    saved = {}

    def information(seat):
        if poison:
            raise AssertionError('closed phase read a reservation HUD')
        me = m.state['players'][seat]
        hand = [our_card(names[c]) if c >= 0 else None for c in me['hand']]
        own = dict(hand=hand, elixir=me['elixir_milli']/1000., cycle=list(probe.DECK[4:]), refill=0)
        # Only CommandQueue.own_packet consumes these arrays. No feature model is queried.
        observation = SimpleNamespace(hand_ids=np.array([1, 2, 3, 4, 5]),
            hand_levels=np.full(5, 11), hand_level_confidence=np.ones(5), global_features=np.zeros(32))
        return OwnView(tick=m.tick, seat=seat, own=own,
            packet=SimpleNamespace(observation=observation, hand_id_confidence=np.ones(5)))

    def execute(commands):
        result = original.execute(m, commands)
        saved.update(blob=bytes(m.b.save()), state_hash=m.b.state_hash(), tick=m.tick)
        return result

    m.information, m.execute = information, execute
    if poison:
        def hand_card(*args):
            raise AssertionError('closed phase checked an overdue pending slot')
        m.hand_card = hand_card
    monkeypatch.setattr(match, 'RsimMatch', lambda *args, **kwargs: m)
    builder = SimpleNamespace(token_id=lambda card, **kwargs: probe.DECK.index(card)+1)
    rt = SimpleNamespace(R=SimpleNamespace(builder=builder, costs=dict.fromkeys(probe.DECK, 3)))
    return rt, m, saved


def play(rt, players, **kwargs):
    return match.play_match(rt, players, seed=1, decks=[list(probe.DECK)]*2,
                            vocab={'fixture': True}, client='16.402', verbose=True, **kwargs)


@pytest.mark.parametrize('client', ['16.402', '15.535.29'])
@pytest.mark.parametrize('weaker,tie', [(0, False), (1, False), (1, True)])
def test_pinned_api_boundary_and_actual_win_or_delayed_draw(client, weaker, tie):
    result = probe.boundary_case(client, weaker, tie=tie)
    assert result['passed'] and not result['at_closure']['game_over']
    assert result['final']['game_over']


@pytest.mark.parametrize('accepted_seat', [0, 1])
@pytest.mark.parametrize('tie', [False, True])
def test_last_accepted_late_pending_and_final_score_match_independent_native_drain(monkeypatch, accepted_seat, tie):
    rt, m, saved = scripted_match(monkeypatch, weaker=1-accepted_seat, tie=tie)
    action = 10*18+9
    players = {accepted_seat: ScriptedPlayer({5970: action}), 1-accepted_seat: ScriptedPlayer({5975: action})}
    result = play(rt, players)
    phase, pending = result['command_phase'], result['command_phase']['pending']
    assert phase['closed_tick'] == 6000 and phase['clock'] == dict(tick_ms=50, regular_ticks=3600, overtime_ticks=2400)
    assert pending[accepted_seat] == []
    assert pending[1-accepted_seat] == [dict(submitted=5975, due=6002, action=action, card='Knight', cost=3,
                                          status='not_dispatched', reason='command_phase_closed')]
    assert result['play_log'][accepted_seat] == [(5997, 'Knight', action, True)]
    assert result['play_log'][1-accepted_seat] == []
    assert result['command_sha256'] == hashlib.sha256(f'5997,{accepted_seat},{action},1;'.encode()).hexdigest()
    assert len(m.command_results) == len(m.public_events) == 1
    assert m.command_results[0]['tick'] == m.public_events[0]['tick'] == 5997
    assert m.command_results[0]['ok'] and m.public_events[0]['name'] == 'Knight'
    assert m.plays[accepted_seat] == [(5997, 'Knight')] and len(m.events[1-accepted_seat]) == 1
    for seat, player in players.items():
        assert player.closed and player.polls and max(t for t, _ in player.polls) == 5995
        ch = result['channels'][seat]
        assert ch['submitted'] == ch['executed']+ch['pending_at_end'] == 1 and ch['rejected'] == 0
        assert ch['pending_at_end'] == int(seat != accepted_seat)
        assert result['timing'][seat]['decisions'] == sum(can for _, can in player.polls)
    closed_calls = [c for c in m.b.calls if c[0] >= 6000]
    assert closed_calls and all(not commands and ticks == 5 for _, commands, ticks in closed_calls)
    assert saved['tick'] == 5997
    twin = probe.rsim_battle('16.402')
    twin.load(saved['blob'])
    assert twin.state_hash() == saved['state_hash'], 'reference must start at the exact post-last-accepted state'
    reference = probe.drain(twin)[-1]
    assert result['draw'] is tie and (result['winner'] is None if tie else result['winner'] == accepted_seat)
    actual = dict(tick=result['ticks'], game_over=result['terminal'], winner=2 if result['draw'] else result['winner'],
                  crowns=[result['crowns'][a] for a in (0, 1)], towers=[result['towers'][a] for a in (0, 1)])
    assert actual == reference and actual['tick'] > 6067
    assert result['state_hash'] == twin.state_hash()


def test_already_closed_with_overdue_pending_never_reads_hand_or_polls_and_does_not_spin(monkeypatch):
    from clasher.analysis.loss_review import delay_fixes
    rt, m, _ = scripted_match(monkeypatch, start=6010, poison=True)
    queue, created = delay_fixes.CommandQueue, []

    def with_pending(delay, capacity):
        ch = queue(delay, capacity)
        ch.pending.append(delay_fixes.Reservation(5975, 6002, 189, 'Knight', 3))
        ch.submitted = ch.peak = 1
        created.append(ch)
        return ch

    monkeypatch.setattr(delay_fixes, 'CommandQueue', with_pending)
    result = play(rt, {0: ScriptedPlayer(), 1: ScriptedPlayer()})
    assert result['terminal'] and result['ticks'] > 6067
    assert result['command_phase']['closed_tick'] == 6000
    assert result['command_phase']['observed_closed_tick'] == 6010
    assert result['command_sha256'] == hashlib.sha256(b'').hexdigest()
    assert not m.command_results and not m.public_events
    assert all(not commands and ticks == 5 for _, commands, ticks in m.b.calls)
    for seat in (0, 1):
        assert result['timing'][seat]['decisions'] == 0
        assert len(created[seat].pending) == result['channels'][seat]['pending_at_end'] == 1
        assert result['channels'][seat]['submitted'] == 1 and result['channels'][seat]['executed'] == 0
        assert result['channels'][seat]['rejected'] == 0
        assert result['command_phase']['pending'][seat][0]['due'] == 6002


@pytest.mark.parametrize('weaker', [0, 1])
@pytest.mark.parametrize('king', [False, True])
def test_preclosure_crown_or_king_end_has_no_extra_actions_or_physics(monkeypatch, weaker, king):
    rt, m, _ = scripted_match(monkeypatch, start=3595, weaker=weaker, crown_end=not king, king_end=king)
    players = {a: ScriptedPlayer({} if king else {3595: 189}) for a in (0, 1)}
    result = play(rt, players)
    assert result['terminal'] and result['winner'] == 1-weaker and result['ticks'] < 6000
    assert result['command_phase']['closed_tick'] is None and not m.command_results
    assert all(tick < result['ticks'] for tick, _, _ in m.b.calls)
    assert all(tick < result['ticks'] for p in players.values() for tick, _ in p.polls)
    assert all(p.closed for p in players.values())
    if king:
        assert m.b.calls and result['crowns'][1-weaker] == 3 and result['towers'][weaker][0] == 0
    else:
        assert result['ticks'] == 3600 and result['crowns'][1-weaker] == 1
        assert all(ch['pending_at_end'] == 1 and ch['executed'] == ch['rejected'] == 0
                   for ch in result['channels'].values())


def test_safeguard_is_nonterminal_not_an_early_draw_or_win(monkeypatch):
    from .run import row_issues
    rt, _, _ = scripted_match(monkeypatch)
    result = play(rt, {0: ScriptedPlayer(), 1: ScriptedPlayer()}, max_ticks=6000)
    assert result['ticks'] == 6000 and result['terminal'] is False
    assert row_issues(dict(result, failures={}, child_exit_code=0))['nonterminal'] == 1


def test_calibration_overrides_bound_once_and_public_boundary_not_hardcoded():
    overrides = {'match.REGULAR_TIME_S': '17', 'match.OVERTIME_S': '19'}
    calls = []
    def read():
        calls.append(True)
        return dict(overrides)
    b = SimpleNamespace(calibration_overrides=read)
    state = dict(tick=720, tick_ms=50, regular_ticks=340, overtime_ticks=380, overtime=True, game_over=False)
    phase = match.CommandPhase(b, state)
    overrides['match.REGULAR_TIME_S'] = '180'
    assert phase.closed(state) and not phase.closed(dict(state, tick=719)) and calls == [True]
    assert phase.receipt()['overrides']['match.REGULAR_TIME_S'] == 17


@pytest.mark.parametrize('rule', ['lowest_tower_hp_absolute', 'lowest_tower_hp_fraction', 'none_draw'])
def test_other_documented_tiebreaks_do_not_get_an_early_freeze(rule):
    b = SimpleNamespace(calibration_overrides=lambda: {'match.OVERTIME_TIEBREAK': json.dumps(rule)})
    state = dict(tick=6000, tick_ms=50, regular_ticks=3600, overtime_ticks=2400, overtime=True, game_over=False)
    assert not match.CommandPhase(b, state).closed(state)


@pytest.mark.parametrize('change', [dict(tick=True), dict(tick=-1), dict(tick_ms=100), dict(regular_ticks=1),
    dict(overtime_ticks=None), dict(overtime=1), dict(game_over=0), dict(overtime=True), dict(tick=6000)])
def test_bad_public_clock_fails_closed(change):
    state = dict(tick=100, tick_ms=50, regular_ticks=3600, overtime_ticks=2400, overtime=False, game_over=False)
    with pytest.raises(ValueError, match='public command-phase clock'):
        match.CommandPhase(SimpleNamespace(calibration_overrides=lambda: {}), dict(state, **change))


@pytest.mark.parametrize('overrides', [None, {'match.OVERTIME_TIEBREAK': '"unknown"'},
    {'match.BATTLE_END': '"overtime_end"'}, {'time.TICK_MS': 'true'}, {'match.OVERTIME_S': '0'},
    {'match.OVERTIME_S': 120}, {'match.OVERTIME_S': 'invalid JSON'}])
def test_bad_effective_rules_fail_actionably(overrides):
    state = dict(tick=100, tick_ms=50, regular_ticks=3600, overtime_ticks=2400, overtime=False, game_over=False)
    with pytest.raises(ValueError, match='unsupported RoyaleSim'):
        match.CommandPhase(SimpleNamespace(calibration_overrides=lambda: overrides), state)


def test_unknown_calibration_refuses_before_translator_or_player_start(monkeypatch):
    import royalesim as rs
    from bot.players import royalesim_translate
    ledger = json.loads(rs.EMBEDDED_CALIBRATION_JSON)
    ledger['match']['OVERTIME_TIEBREAK']['value'] = 'unknown'
    monkeypatch.setattr(rs, 'EMBEDDED_CALIBRATION_JSON', json.dumps(ledger))
    def forbidden(*args, **kwargs):
        raise AssertionError('unknown calibration reached a Translator/player')
    monkeypatch.setattr(royalesim_translate, 'Translator', forbidden)
    players = {a: SimpleNamespace(start=forbidden, act=forbidden, close=forbidden) for a in (0, 1)}
    with pytest.raises(ValueError, match='command-phase rules'):
        play(SimpleNamespace(R=None), players)


def test_probe_failure_retains_partial_evidence_and_cannot_overwrite(monkeypatch, tmp_path):
    path = tmp_path/'boundary.json'
    def fail(receipt):
        receipt['cases'] = [dict(observed='boundary contradiction', passed=False)]
        raise ValueError('native boundary contradiction')
    monkeypatch.setattr(probe, 'run', fail)
    assert probe.main(['--out', str(path)]) == 1
    raw = path.read_bytes()
    receipt = json.loads(raw)
    assert not receipt['passed'] and receipt['cases'][0]['observed'] == 'boundary contradiction'
    assert 'native boundary contradiction' in receipt['error'] and 'ValueError' in receipt['traceback']
    with pytest.raises(FileExistsError):
        probe.main(['--out', str(path)])
    assert path.read_bytes() == raw


def test_real_preclosure_rejection_remains_parent_and_report_failure(monkeypatch, tmp_path):
    from . import test_harness as harness
    from . import report, run
    rt, m, _ = scripted_match(monkeypatch)
    result = play(rt, {0: ScriptedPlayer({5970: 16*18+9}), 1: ScriptedPlayer()})
    assert result['terminal'] and len(m.command_results) == 1
    event = m.command_results[0]
    assert event['tick'] == 5997 and event['reason'] == 'WATER' and not event['ok']
    assert result['channels'][0]['rejected'] == 1
    # Registered protocol fixture with this real deck/seed/true L11 profile.
    case = dict(harness.gate_case(), decks=[list(probe.DECK), list(probe.DECK)],
                profile=dict(cards=[dict.fromkeys(probe.DECK, 11)]*2, towers=[11, 11]),
                view=dict(own_levels=dict.fromkeys(probe.DECK, 11), own_tower=11, opp_tower=11))
    monkeypatch.setattr(harness, 'gate_case', lambda: case)
    rows = harness.registered_report(tmp_path, cases=1)
    assert report.summarize(tmp_path)['quality_ok']
    path = rows/'A-00000.json'
    row = json.loads(path.read_text())
    row.update({k: v for k, v in result.items() if k != 'play_log'})
    row.update(failures={}, play_log=result['play_log'][0], command_events=m.command_results)
    run.write_json(path, row)
    assert run.row_issues(row, require_exit=False)['rejections'] == 1
    assert run.record_exit(path, case, 'A', {}, 123, 1 << 8)  # Parent marks failure; does not discard detail.
    preserved = json.loads(path.read_text())
    assert preserved['command_events'] == m.command_results and preserved['child_exit_code'] == 1
    summary = report.summarize(tmp_path)
    assert not summary['quality_ok'] and summary['arms']['A']['rejections'] == 1
    assert report.main([str(tmp_path)]) == 1


def test_immutable_R27_rows_and_all_sixteen_rejections_stay_failed():
    """Read the old experiment only; never invoke report.main or modify its receipt."""
    from . import report, run
    root = JOB/'pilot-r27'
    entries = [line.split('  ', 1) for line in (JOB/'pilot-r27-preserved-files.sha256').read_text().splitlines()]
    def verify():
        for expected, relative in entries:
            assert hashlib.sha256((root/relative).read_bytes()).hexdigest() == expected, relative
    verify()
    failures = []
    for arm, index in (('A', 10), ('A', 12), ('B', 0), ('B0', 13)):
        row = json.loads((root/'rows'/f'{arm}-{index:05d}.json').read_text())
        assert row['score'] == 1 and row['terminal'] and row['child_exit_code'] == 1
        assert run.row_issues(row)['rejections'] > 0 and run.row_issues(row)['child_failures'] == 1
        failures.extend(dict(arm=arm, index=index, **{k: e[k] for k in ('action', 'card', 'reason', 'seat', 'tick')})
                        for e in row['command_events'] if not e['ok'])
    expected = json.loads((JOB/'pilot-r27-stop-audit.json').read_text())['failures']['rejected_deployments']
    assert expected == len(failures) == 16 and all(e['reason'] == 'GAME_OVER' and e['tick'] >= 6000 for e in failures)
    summary = report.summarize(root)
    assert not summary['quality_ok'] and summary['coverage']['parent_exit_code'] == 143
    assert sum(a['rejections'] for a in summary['arms'].values()) == 16
    verify()
