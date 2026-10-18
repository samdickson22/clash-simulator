"""display_feed window source (stream-source.json kind 'window') + dispgrab gate rules. Linux-runnable, no capture:
fake dispgrab (info only), Popen recorded. Run: python -B -m unittest live/display/tests/test_display_feed_window.py"""
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix='dfwin-'))
os.environ['LL_LOOP_DIR'] = str(TMP/'loop')
os.environ.setdefault('CLASHER_DISPLAY_OFFSETS', str(TMP/'none.json'))
spec = importlib.util.spec_from_file_location('display_feed', HERE.parent/'display_feed.py')
df = importlib.util.module_from_spec(spec)
spec.loader.exec_module(df)
SWIFT = (HERE.parent/'dispgrab.swift').read_text()
REAL_CAPTURE_CLIENTS = df.capture_clients                # Base patches it; the parser tests use the real one

MUMU = dict(kind='window', owner='MuMu Android Device', crop=[0, 28, 540, 960], size=[1080, 1920], fps=30,
            label='LADDER · MuMu')
GAME_INFO = dict(window_id=777, pid=9, bounds=[100.0, 40.0, 540.0, 988.0], content_rect=[0, 0, 540, 988], scale=2.0)
DIALOG_INFO = dict(window_id=1558, pid=33766, bounds=[300.0, 200.0, 600.0, 450.0], content_rect=[0, 0, 600, 450],
                   scale=2.0)


def fake_proc(cmd=None, pid=4000, dies=True):
    """A Popen stand-in with a lifecycle: poll() None until terminate()/kill() (if dies), then the signal rc."""
    m = mock.MagicMock()
    m.args, m.pid, m.returncode = cmd, pid, None
    m.poll.return_value = None

    def die(rc):
        if dies:
            m.poll.return_value = m.returncode = rc

    def wait(timeout=None):
        if m.poll.return_value is None:
            raise df.subprocess.TimeoutExpired(cmd, timeout)
        return m.returncode
    m.terminate.side_effect = lambda: die(-15)
    m.kill.side_effect = lambda: die(-9)
    m.wait.side_effect = wait
    return m


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(dir=TMP))
        (self.d/'display').mkdir()
        self.src = self.d/'stream-source.json'
        self.info = self.d/'info.json'
        self.argv = self.d/'argv.log'
        grab = self.d/'dispgrab'
        grab.write_text(f'''#!{sys.executable}
import json, os, sys
open({str(self.argv)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')
if not os.path.exists({str(self.info)!r}):
    print('dispgrab error: no on-screen window', file=sys.stderr); sys.exit(3)
print(open({str(self.info)!r}).read())
''')
        grab.chmod(grab.stat().st_mode | stat.S_IXUSR)
        self.patches = [mock.patch.object(df, 'SOURCE_FILE', self.src), mock.patch.object(df, 'GRAB', str(grab)),
                        mock.patch.object(df, 'OUT', self.d/'display'), mock.patch.object(df, 'LOOP', self.d),
                        mock.patch.object(df, 'GATE_FILE', self.d/'display/capture-gate'),
                        mock.patch.object(df.Pipeline, 'PIDS', self.d/'display/pipeline.json'),
                        mock.patch.object(df, 'capture_clients', return_value=[]),
                        mock.patch.object(df, 'driver_running', return_value=False)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def write_src(self, d):
        self.src.write_text(json.dumps(d))

    def calls(self):
        try:
            return [json.loads(l) for l in self.argv.read_text().splitlines()]
        except OSError:
            return []


class WindowSourceConfig(Base):
    def test_absent_and_other_kinds(self):
        self.assertIsNone(df.window_source())
        self.write_src(dict(source='nulls', instances=[]))
        self.assertIsNone(df.window_source())

    def test_valid(self):
        self.write_src(dict(MUMU, title='Android'))
        s = df.window_source()
        self.assertEqual((s['owner'], s['title'], s['crop'], s['size'], s['fps']),
                         ('MuMu Android Device', 'Android', (0., 28., 540., 960.), (1080, 1920), 30))
        self.assertNotIn('error', s)
        self.assertEqual(df.window_args(s), ['--owner', 'MuMu Android Device', '--title', 'Android'])

    def test_invalid_is_error_not_fallback(self):
        for bad in (dict(kind='window'), dict(MUMU, crop=[0, 0, 0, 10]), dict(MUMU, size=[1081, 1920]),
                    dict(MUMU, fps=0), dict(MUMU, insets=[1, 2])):
            self.write_src(bad)
            s = df.window_source()
            self.assertIn('error', s, bad)
            self.assertEqual(df.window_args(s), [])
        self.src.write_text('{"kind": "window", ')
        self.assertIn('error', df.window_source())

    def test_fail_closed_malformed(self):
        for text in ('{"kind": "WINDOW", ', '[1, 2]', '"window"', '{"kind": "window", "owner": "M", "crop": [NaN, 0, 1, 1]}',
                     '{"kind": "window", "owner": "M", "size": [Infinity, 1920]}', '\udcff'):
            self.src.write_text(text, errors='surrogateescape') if text == '\udcff' else self.src.write_text(text)
            s = df.window_source()
            self.assertIsNotNone(s, text)
            self.assertIn('error', s, text)
            self.assertTrue(s['key'].startswith('error:'))

    def test_non_finite_and_overflow(self):
        for raw in ('{"kind": "window", "owner": "M", "size": [1e309, 1920]}',
                    '{"kind": "window", "owner": "M", "crop": [0, 0, 1e309, 960]}',
                    '{"kind": "window", "owner": "M", "size": [1%s, 1920]}' % ('0' * 400),
                    '{"kind": "window", "owner": "M", "size": [1080.5, 1920]}',
                    '{"kind": "window", "owner": "M", "insets": [-1e309, 0, 0, 0]}'):
            self.src.write_text(raw)
            self.assertIn('error', df.window_source(), raw[:70])

    def test_uppercase_kind_valid(self):
        self.write_src(dict(MUMU, kind='WINDOW'))
        s = df.window_source()
        self.assertNotIn('error', s)
        self.assertEqual(s['owner'], 'MuMu Android Device')

    def test_other_valid_kinds_default(self):
        self.write_src(dict(kind='nulls', instances=[dict(window='x')]))
        self.assertIsNone(df.window_source())
        self.write_src(dict(owner='MuMu Android Device'))      # no kind: not a window source
        self.assertIsNone(df.window_source())

    def test_nulls_plan_ignores_window_kind(self):
        self.write_src(dict(MUMU, label="null's"))
        with mock.patch.object(df, 'list_windows', side_effect=AssertionError('SCK query')):
            self.assertIsNone(df.source_plan())


class WindowCrop(Base):
    def src_of(self, **kw):
        self.write_src(dict(MUMU, **kw))
        return df.window_source()

    def test_explicit_crop_and_size(self):
        self.assertEqual(df.window_crop(self.src_of(), GAME_INFO), ((0., 28., 540., 960.), (1080, 1920)))

    def test_default_size_from_scale(self):
        s = self.src_of(size=None)
        self.assertEqual(df.window_crop(s, GAME_INFO)[1], (1080, 1920))

    def test_insets_fit(self):
        s = self.src_of(crop=None, insets=[28, 0, 0, 0])
        crop, _ = df.window_crop(s, GAME_INFO)
        self.assertEqual(crop, (0., 28., 540., 960.))

    def test_insets_fit_bottom_anchor(self):
        s = self.src_of(crop=None, anchor='bottom')
        self.assertEqual(df.window_crop(s, GAME_INFO), ((0., 28., 540., 960.), (1080, 1920)))
        self.write_src(dict(MUMU, anchor='middle'))
        self.assertIn('error', df.window_source())

    def test_landscape_dialog_rejected(self):
        with self.assertRaises(df.WrongWindow):
            df.window_crop(self.src_of(), DIALOG_INFO)
        self.assertTrue(issubclass(df.WrongWindow, df.NoWindow))     # -> status card

    def test_crop_outside_rejected(self):
        with self.assertRaises(df.WrongWindow):
            df.window_crop(self.src_of(crop=[0, 40, 540, 960]), GAME_INFO)


class PipelineStart(Base):
    def pipe(self):
        p = df.Pipeline(30, dict(desktop=['8000k'] * 3, phone=['1500k'] * 3), (540, 960))
        p.source = df.window_source()
        p.reaped = True
        p.drv = None                             # set by main(); only start_frames reads it
        return p

    def popen(self):
        procs = []
        real = df.subprocess.Popen

        def fake(cmd, *a, **kw):
            if cmd[0] == 'ps' or (len(cmd) > 1 and cmd[1] in ('info', 'windows')):   # real: the fake dispgrab
                return real(cmd, *a, **kw)                                       # script / ps (stale checks)
            m = fake_proc(cmd, 4000 + len(procs))
            procs.append(m)
            return m
        return procs, mock.patch.object(df.subprocess, 'Popen', side_effect=fake)

    def test_window_stream_command(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        procs, pm = self.popen()
        with pm:
            p.tick(lambda: True, 'display')
        grab = procs[0].args
        self.assertEqual(grab[1], 'stream')
        self.assertEqual(grab[grab.index('--owner') + 1], 'MuMu Android Device')
        self.assertNotIn('--title', grab)
        self.assertEqual(grab[grab.index('--crop') + 1], '0.0,28.0,540.0,960.0')
        self.assertEqual(grab[grab.index('--size') + 1], '1080,1920')
        self.assertEqual(grab[grab.index('--fps') + 1], '30')
        self.assertIn('--gate', grab)
        ff = procs[1].args
        self.assertEqual(ff[ff.index('-video_size') + 1], '1080x1920')
        self.assertEqual(self.calls()[0], ['info', '--owner', 'MuMu Android Device'])
        self.assertEqual(p.kind, 'display')
        state = self.d/'display/state.json'
        df.write_state(state, df.Driver(), p, time.monotonic())
        self.assertEqual(json.loads(state.read_text())['source'], 'LADDER · MuMu')

    def start_running(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        procs, pm = self.popen()
        with pm:
            p.tick(lambda: True, 'display')
        self.assertEqual(p.kind, 'display')
        return p

    def state_source(self, p):
        state = self.d/'display/state.json'
        df.write_state(state, df.Driver(), p, time.monotonic())
        return json.loads(state.read_text())['source']

    def test_pending_bad_source_keeps_running_label(self):
        p = self.start_running()
        self.src.write_text(json.dumps(dict(kind='window')))   # malformed while the capture runs (e.g. mid-battle)
        p.source = df.window_source()
        self.assertIn('error', p.source)
        self.assertEqual(self.state_source(p), 'LADDER · MuMu')  # no KeyError; the running source's label

    def test_pending_valid_source_does_not_relabel_early(self):
        p = self.start_running()
        self.write_src(dict(MUMU, label='OTHER'))
        p.source = df.window_source()
        self.assertEqual(self.state_source(p), 'LADDER · MuMu')

    def test_label_cleared_on_stop(self):
        p = self.start_running()
        p.stop('test')
        self.assertIsNone(p.src_label)
        self.assertIsNone(p.src_key)

    def test_exit_deferred_while_capture_in_battle(self):
        p = self.start_running()
        self.assertFalse(df.exit_ready(p, lambda: False))     # capture client + battle: no exit (no SCK stop)
        self.assertTrue(df.exit_ready(p, lambda: True))
        self.assertFalse(df.exit_ready(p, mock.Mock(side_effect=OSError)))   # unknown -> keep capture
        p.grab.poll.return_value = 0                           # capture child already gone: nothing to protect
        self.assertTrue(df.exit_ready(p, lambda: False))
        q = self.pipe()
        q.kind = 'card'
        self.assertTrue(df.exit_ready(q, lambda: False))

    def card_case(self, info):
        self.write_src(MUMU)
        if info:
            self.info.write_text(json.dumps(info))
        p = self.pipe()
        with mock.patch.object(p, 'start_card') as card, self.popen()[1]:
            p.tick(lambda: True, 'display')
        card.assert_called_once()
        self.assertIn('no source window', p.last_error)
        return p

    def test_absent_window_cards(self):
        self.card_case(None)

    def test_dialog_only_cards(self):
        p = self.card_case(DIALOG_INFO)
        self.assertIn('not portrait', p.last_error)

    def test_bad_config_cards_without_query(self):
        self.write_src(dict(kind='window'))
        p = self.pipe()
        with mock.patch.object(p, 'start_card') as card, self.popen()[1]:
            p.tick(lambda: True, 'display')
        card.assert_called_once()
        self.assertEqual(self.calls(), [])                         # no dispgrab (SCK) call at all

    def test_in_battle_no_capture_start(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        procs, pm = self.popen()
        with pm, mock.patch.object(p, 'start_frames') as frames:
            p.tick(lambda: False, 'display')
        frames.assert_called_once()
        self.assertEqual(self.calls(), [])
        self.assertFalse(any(c.args[1:2] == ['stream'] for c in procs))

    def test_source_change_restarts_only_between_battles(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        procs, pm = self.popen()
        with pm:
            p.tick(lambda: True, 'display')
        with mock.patch.object(p, 'frames_done', return_value=1):
            self.write_src(dict(MUMU, crop=[0, 20, 540, 960]))
            p.source = df.window_source()
            with mock.patch.object(p, 'stop') as stop:
                p.tick(lambda: False, 'display')                   # in a battle: never stopped
                stop.assert_not_called()
                p.tick(lambda: True, 'display')
                self.assertEqual(stop.call_args_list[0], mock.call('stream-source.json changed'))

    def test_legacy_default_unchanged(self):
        self.info.write_text(json.dumps(dict(GAME_INFO, bounds=[0, 0, 554.0, 960.0])))
        p = self.pipe()
        self.assertIsNone(p.source)
        procs, pm = self.popen()
        with pm:
            p.tick(lambda: True, 'display')
        grab = procs[0].args
        self.assertNotIn('--owner', grab)
        self.assertEqual(self.calls()[0], ['info'])
        self.assertEqual(grab[grab.index('--crop') + 1], ','.join(map(str, df.game_crop(dict(bounds=[0, 0, 554, 960])))))


class GatedSignals(PipelineStart):
    """Every capture-child signal re-reads 'allowed' fresh, after any blocking validation, right before it is sent."""
    def stale_setup(self):
        (self.d/'display/pipeline.json').write_text(json.dumps(dict(dispgrab=4242, ffmpeg=4243)))
        p = self.pipe()
        p.reaped = False
        return p

    def test_reap_defers_when_battle_starts_during_ps(self):
        p = self.stale_setup()
        battle = {'on': False}

        def ps(pid, exe):                        # the blocking identity check; a battle begins while it runs
            battle['on'] = True
            return f'{exe} stream --gate x'
        kills = []
        with mock.patch.object(df.Pipeline, 'stale_cmd', staticmethod(ps)), \
                mock.patch.object(df.os, 'kill', side_effect=lambda pid, sig: kills.append((pid, sig))):
            p.tick(lambda: not battle['on'], 'display')
        self.assertEqual(kills, [])                            # nothing signalled
        self.assertFalse(p.reaped)                             # cleanup still pending
        self.assertTrue((self.d/'display/pipeline.json').exists())
        self.assertIsNone(p.grab)                              # and nothing started meanwhile

    def test_reap_kill_escalation_regated(self):
        p = self.stale_setup()
        calls = {'n': 0}

        def allowed():                           # open for the TERM, battle by the KILL 2 s later
            calls['n'] += 1
            return calls['n'] <= 1
        sent = []

        def kill(pid, sig):
            if sig != 0:
                sent.append(sig)                 # signal 0 = alive probe: the child ignores TERM
        with mock.patch.object(df.Pipeline, 'stale_cmd', staticmethod(lambda pid, exe: f'{exe} stream x')), \
                mock.patch.object(df.os, 'kill', side_effect=kill), mock.patch.object(df.time, 'sleep'), \
                mock.patch.object(df.time, 'monotonic', side_effect=[0., 0., 3.] + [10.]*50):
            self.assertFalse(p.reap_stale(allowed))
        self.assertEqual(sent, [df.signal.SIGTERM])            # no SIGKILL in the battle

    def test_reap_completes_between_battles(self):
        p = self.stale_setup()
        alive = {4242, 4243}

        def kill(pid, sig):
            if sig == 0 and pid not in alive:
                raise ProcessLookupError
            if sig == df.signal.SIGTERM:
                alive.discard(pid)

        def ps(pid, exe):
            return f'{exe} stream x' if pid in alive else None
        with mock.patch.object(df.Pipeline, 'stale_cmd', staticmethod(ps)), mock.patch.object(df.os, 'kill', side_effect=kill):
            self.assertTrue(p.reap_stale(lambda: True))
        self.assertFalse((self.d/'display/pipeline.json').exists())

    def test_stop_defers_capture_signal_in_battle(self):
        p = self.start_running()
        grab, ff = p.grab, p.ff
        self.assertFalse(p.stop('test', lambda: False))
        grab.terminate.assert_not_called()
        ff.terminate.assert_not_called()
        self.assertIs(p.grab, grab)                            # state kept for the retry
        self.assertEqual(p.kind, 'display')

    def test_stop_kill_escalation_regated(self):
        p = self.start_running()
        grab = p.grab
        grab.terminate.side_effect = None        # ignores TERM
        grab.wait.side_effect = df.subprocess.TimeoutExpired('dispgrab', 2)
        answers = iter([True, True, False])      # TERM grab, TERM ffmpeg, then a battle before the KILL
        self.assertFalse(p.stop('test', lambda: next(answers)))
        grab.terminate.assert_called_once()
        grab.kill.assert_not_called()

    def test_stop_uses_tick_allowed_fn(self):
        p = self.start_running()
        p.allowed_fn = lambda: False
        self.assertFalse(p.stop('no explicit gate'))
        p.grab.terminate.assert_not_called()

    def test_switch_stop_rechecked_after_tick_start(self):
        p = self.start_running()
        seq = iter([True] + [False]*20)          # tick's own read says open, the fresh read before the signal: battle
        with mock.patch.object(p, 'frames_done', return_value=1):
            p.tick(lambda: next(seq), 'grid', ('x', [({'id': 1, 'bounds': [0, 0, 9, 16]}, 'a')]))
        p.grab.terminate.assert_not_called()
        self.assertEqual(p.kind, 'display')

    def cgwin(self, rows):
        f = self.d/'cgwin.json'
        f.write_text(json.dumps(rows))
        return mock.patch.dict(os.environ, CLASHER_DISPLAY_CGWIN=str(f))

    @staticmethod
    def cgrow(wid=777, bounds=(100.0, 40.0, 540.0, 988.0), owner='MuMu Android Device', layer=0):
        return dict(id=wid, owner=owner, title='', layer=layer, pid=9, bounds=list(bounds))

    def test_check_window_stop_gated(self):
        p = self.start_running()
        n = len(self.calls())
        with self.cgwin([self.cgrow(778)]):                                # window changed -> restart wanted
            seq = iter([False, False, False, False])
            p.win_check_t = 0.
            p.check_window(lambda: next(seq))
        p.grab.terminate.assert_not_called()
        self.assertEqual(len(self.calls()), n)                             # no dispgrab (SCK) query

    def test_check_window_no_sck_and_restarts_on_change(self):
        p = self.start_running()
        n = len(self.calls())
        grab = p.grab
        with self.cgwin([self.cgrow(777), self.cgrow(5, (0, 0, 300, 300), owner='Other')]):
            p.win_check_t = 0.
            p.check_window(lambda: True)
            grab.terminate.assert_not_called()                             # same id + size: nothing
            self.assertIn('window 777', p.window_probe)
        with self.cgwin([self.cgrow(777, (100.0, 40.0, 600.0, 988.0))]):   # resized: restart
            p.win_check_t = 0.
            p.check_window(lambda: True)
        grab.terminate.assert_called_once()
        self.assertIsNone(p.kind)
        self.assertEqual(len(self.calls()), n)

    def test_check_window_gone_after_grace(self):
        p = self.start_running()
        grab = p.grab
        with self.cgwin([self.cgrow(9, owner='Other')]):
            p.win_check_t = 0.
            p.check_window(lambda: True)
            grab.terminate.assert_not_called()                             # absent < WINDOW_GONE_S
            p.win_check_t, p.win_missing_t = 0., time.monotonic() - df.WINDOW_GONE_S - 1
            p.check_window(lambda: True)
        grab.terminate.assert_called_once()

    def test_check_window_cg_failure_no_fallback(self):
        p = self.start_running()
        n = len(self.calls())
        with mock.patch.object(df, 'cg_windows', side_effect=OSError('no CG')):
            p.win_check_t = 0.
            p.check_window(lambda: True)
        p.grab.terminate.assert_not_called()
        self.assertEqual(len(self.calls()), n)
        self.assertIn('unavailable', p.window_probe)

    def stats(self, *lines):
        with open(self.d/'display/dispgrab.log', 'a') as f:
            for t, age in lines:
                f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t)) +
                        f' dispgrab: stats 10s: captured 0.00 fps, emitted 30.00 fps, rejected 0, resyncs 0, '
                        f'write 0.10 ms/frame, last_capture_age {age:.1f} s\n')

    def test_stale_ignores_previous_capture_lines(self):
        now = time.time()
        self.stats((now - 1, 3265.0))                                      # the replaced capture's stale age
        p = self.start_running()
        self.assertIsNone(p.capture_stale(now))
        self.assertIsNone(p.capture_age())
        self.stats((now, 0.1))
        self.assertIsNone(p.capture_stale(now))
        self.assertEqual(p.capture_age(), 0.1)

    def test_stale_rules(self):
        p = self.start_running()
        now = time.time()
        self.assertIsNone(p.capture_stale(now + df.STATS_LATE_S - 1))      # first stats line not due yet
        self.assertIn('no dispgrab stats line', p.capture_stale(now + df.STATS_LATE_S + 1))
        self.stats((now + 10, 0.2))
        self.assertIsNone(p.capture_stale(now + 11))
        self.assertIn('no dispgrab stats line', p.capture_stale(now + 10 + df.STATS_LATE_S + 1))   # stopped
        self.stats((now + 20, df.STALE_S + 0.5))
        self.assertIn('no captured frame', p.capture_stale(now + 21))

    def test_stale_recovery_immediate_then_card_backoff(self):
        p = self.start_running()
        procs, pm = self.popen()
        with pm:
            with mock.patch.object(p, 'capture_stale', return_value='no captured frame for 9.0 s'):
                grab = p.grab
                p.tick(lambda: True, 'display')
            grab.terminate.assert_called_once()
            self.assertEqual(p.stale_restarts, 1)
            self.assertIsNone(p.kind)
            p.tick(lambda: True, 'display')                                # restarted at once (single client)
            self.assertEqual(p.kind, 'display')
            with mock.patch.object(p, 'capture_stale', return_value='no captured frame for 9.0 s'), \
                    mock.patch.object(p, 'start_card') as card:
                p.tick(lambda: True, 'display')
            self.assertEqual(p.stale_restarts, 2)
            card.assert_called_once()
            self.assertGreater(p.next_try, time.monotonic() + 3)

    def test_stale_deferred_in_battle(self):
        p = self.start_running()
        with mock.patch.object(p, 'capture_stale', return_value='no captured frame for 9.0 s'), \
                mock.patch.object(p, 'frames_done', return_value=1):
            p.tick(lambda: False, 'display')
        p.grab.terminate.assert_not_called()
        self.assertIn('deferred', p.last_stale)

    def test_no_dispgrab_call_beside_another_capture(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        procs, pm = self.popen()
        with pm, mock.patch.object(df, 'capture_clients', return_value=[4242]):
            p.tick(lambda: True, 'display')
        self.assertEqual(self.calls(), [])                                 # not even dispgrab info
        self.assertFalse(any(c.args[1:2] in (['stream'], ['grid']) for c in procs))   # no capture client
        self.assertFalse(any(str(c.args[0]) == df.GRAB for c in procs))    # no dispgrab process of any kind
        self.assertEqual(p.kind, 'card')                                   # only the ffmpeg status card publishes
        # (the card writer thread also runs /bin/date through the patched Popen when cv2 is present: count ffmpeg only)
        self.assertEqual(sum(1 for c in procs if str(c.args[0]) == df.FFMPEG), 1)
        self.assertIn('another dispgrab capture', p.last_error)
        with pm, mock.patch.object(df, 'capture_clients', return_value=None), self.cgwin([self.cgrow(777)]):
            p.next_try, p.card_t = 0., 0.                                  # retry due: card stopped, start refused
            p.tick(lambda: True, 'display')
        self.assertEqual(self.calls(), [])
        self.assertIn('pgrep', p.last_error)
        self.assertFalse(any(c.args[1:2] in (['stream'], ['grid']) for c in procs))
        self.assertFalse(any(str(c.args[0]) == df.GRAB for c in procs))
        self.assertEqual(p.kind, 'card')

    def test_card_leaves_via_cg_without_sck(self):
        self.write_src(MUMU)
        p = self.pipe()
        procs, pm = self.popen()
        with pm:
            p.start_card('no source window')
            p.card_t = 0.
            with self.cgwin([self.cgrow(9, owner='Other')]):
                p.tick(lambda: True, 'display')
            self.assertEqual(p.kind, 'card')
            self.assertEqual(self.calls(), [])
            self.info.write_text(json.dumps(GAME_INFO))
            card_ff = p.ff
            p.card_t = 0.
            with self.cgwin([self.cgrow(777)]):
                p.tick(lambda: True, 'display')
            card_ff.terminate.assert_called_once()                         # card stopped first, then the one info
            self.assertEqual(p.kind, 'display')
            self.assertEqual([c[0] for c in self.calls()], ['info'])

    def test_stop_unreaped_after_kill_keeps_state(self):
        p = self.start_running()
        grab = p.grab
        grab.terminate.side_effect = grab.kill.side_effect = None          # survives TERM and KILL
        t0 = time.monotonic()
        self.assertFalse(p.stop('test', lambda: True))
        self.assertLess(time.monotonic() - t0, 10)                         # bounded (was an unbounded wait)
        grab.kill.assert_called_once()
        self.assertIs(p.grab, grab)
        self.assertEqual(p.kind, 'display')
        self.assertIn('not reaped', p.last_error)
        procs, pm = self.popen()
        with pm, mock.patch.object(p, 'capture_stale', return_value='x'):
            p.next_try = 0.
            p.tick(lambda: True, 'display')                                # retries the stop, never a 2nd capture
        self.assertFalse(any(c.args[1:2] == ['stream'] for c in procs))
        self.assertIs(p.grab, grab)

    def test_recover_backoff_saturates(self):
        p = self.start_running()
        p.stale_restarts = 5000
        with mock.patch.object(p, 'start_card') as card:
            p.recover_stale('x', 100.)
        self.assertEqual(p.next_try, 160.)
        card.assert_called_once()

    def test_start_no_query_when_gate_closed_or_vision(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        procs, pm = self.popen()
        with pm:
            p.start(lambda: False)                                         # fresh gate closed: nothing queried
            self.assertEqual(self.calls(), [])
            self.assertTrue(p.deferred)
            with mock.patch.object(df, 'driver_running', return_value=True):
                with self.assertRaises(RuntimeError):
                    p.start(lambda: True)                                  # vision driver: no dispgrab info
            self.assertEqual(self.calls(), [])
            self.assertFalse(procs)

    def test_sck_block_cases(self):
        p = self.pipe()
        self.assertIsNone(p.sck_block(lambda: True))
        p.grab = fake_proc(pid=77)
        p.grab.poll.return_value = 0                                       # exited but not reaped by stop()
        self.assertIn('not reaped', p.sck_block(lambda: True))
        p.grab = None
        with mock.patch.object(p, 'stale_pids', return_value=[(55, 'x')]):
            self.assertIn('earlier capture child', p.sck_block(lambda: True))
        with mock.patch.object(df, 'capture_clients', return_value=None):
            self.assertIn('pgrep', p.sck_block(lambda: True))
        with mock.patch.object(df, 'capture_clients', return_value=[9]):
            self.assertIn('another dispgrab', p.sck_block(lambda: True))
        with mock.patch.object(df, 'driver_running', return_value=True):
            self.assertIn('vision', p.sck_block(lambda: True))
        self.assertIn('battle', p.sck_block(lambda: False))
        def broken():
            raise OSError('log read failed')
        self.assertIn('battle', p.sck_block(broken))

    def test_windows_query_blocked_by_live_grab_dead_ffmpeg(self):
        p = self.start_running()
        p.ff.poll.return_value = 1                                         # encoder died, capture alive
        self.assertFalse(p.running())
        self.write_src(dict(kind='nulls', instances=[dict(window='x')]))
        with mock.patch.object(df, 'cg_windows', side_effect=OSError('no CG')):
            with self.assertRaises(RuntimeError):
                df.source_plan(sck_guard=p.sck_block)
        self.assertEqual([c[0] for c in self.calls()], ['info'])           # only the start's info, no 'windows'

    def test_card_text(self):
        self.write_src(MUMU)
        p = self.pipe()
        self.assertEqual(p.card_text(p.source), ['Waiting for the', 'MuMu Android Device window'])
        p.card_why, p.stale_restarts, p.next_try = 'capture stalled; retry 3', 3, time.monotonic() + 8.4
        lines = p.card_text(p.source)
        self.assertEqual(lines[0], 'Video capture stalled')
        self.assertIn('attempt 3', lines[1])
        self.assertRegex(lines[2], r'retry in [78] s')
        p.card_why = 'no source window'
        p.source = dict(error='bad')
        self.assertEqual(p.card_text(p.source)[1], 'game window')

    def test_sck_block_vision_appears_during_gate(self):
        p = self.pipe()
        with mock.patch.object(df, 'driver_running', side_effect=[False, True]):
            self.assertIn('appeared', p.sck_block(lambda: True))
        with mock.patch.object(df, 'capture_clients', side_effect=[[], [321]]):
            self.assertIn('appeared', p.sck_block(lambda: True))

    def test_capture_clients_strict_parse(self):
        def run(stdout, rc=0):
            r = mock.Mock(returncode=rc, stdout=stdout)
            with mock.patch.object(df.subprocess, 'run', return_value=r):
                return REAL_CAPTURE_CLIENTS()
        self.assertEqual(run('123\n456\n'), [123, 456])
        self.assertEqual(run('', 1), [])
        self.assertIsNone(run('garbled'))
        self.assertIsNone(run(''))                                         # rc 0 with nothing = unknown
        self.assertIsNone(run('1\n'))
        self.assertIsNone(run('', 2))
        with mock.patch.object(df.subprocess, 'run', side_effect=OSError):
            self.assertIsNone(REAL_CAPTURE_CLIENTS())

    def test_stale_identity_unknown_fails_closed(self):
        def run(**kw):
            with mock.patch.object(df.subprocess, 'run', **kw):
                return df.Pipeline.stale_cmd(99, '/x/dispgrab')
        self.assertEqual(run(side_effect=df.subprocess.TimeoutExpired('ps', 3)), df.Pipeline.UNKNOWN)
        self.assertEqual(run(side_effect=OSError), df.Pipeline.UNKNOWN)
        self.assertEqual(run(return_value=mock.Mock(returncode=2, stdout='')), df.Pipeline.UNKNOWN)
        self.assertIsNone(run(return_value=mock.Mock(returncode=1, stdout='')))          # positively absent
        self.assertIsNone(run(return_value=mock.Mock(returncode=0, stdout='/bin/other')))   # pid reused
        self.assertEqual(run(return_value=mock.Mock(returncode=0, stdout='/x/dispgrab stream --crop 1')),
                         '/x/dispgrab stream --crop 1')
        p = self.pipe()
        p.PIDS.write_text(json.dumps(dict(dispgrab=4242)))
        with mock.patch.object(df.Pipeline, 'stale_cmd', staticmethod(lambda pid, exe: df.Pipeline.UNKNOWN)), \
                mock.patch.object(df.os, 'kill') as kill:
            self.assertFalse(p.reap_stale(lambda: True))
            self.assertIn('earlier capture child', p.sck_block(lambda: True))
        kill.assert_not_called()
        self.assertTrue(p.PIDS.exists())                                   # record kept

    def test_encoder_start_failure_keeps_capture_record(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        real = df.subprocess.Popen
        grabs = []

        def fake(cmd, *a, **kw):
            if cmd[0] == 'ps' or (len(cmd) > 1 and cmd[1] in ('info', 'windows')):
                return real(cmd, *a, **kw)
            if len(cmd) > 1 and cmd[1] == 'stream':
                g = fake_proc(cmd, 5151, dies=False)                       # survives TERM and KILL
                grabs.append(g)
                return g
            raise OSError('ffmpeg missing')
        with mock.patch.object(df.subprocess, 'Popen', side_effect=fake):
            with self.assertRaises(OSError):
                p.start(lambda: True)
        self.assertEqual(len(grabs), 1)
        self.assertIs(p.grab, grabs[0])                                    # not reaped: object kept
        self.assertEqual(json.loads(p.PIDS.read_text()).get('dispgrab'), 5151)   # identity recorded before ffmpeg
        self.assertIn('not reaped', p.sck_block(lambda: True))

    def test_card_kept_through_failed_retry(self):
        self.write_src(MUMU)
        p = self.pipe()
        procs, pm = self.popen()
        with pm, self.cgwin([self.cgrow(777)]):
            p.card_why = ''
            p.start_card('capture stalled; retry 2')
            p.next_try, p.card_t = 0., 0.
            card_ff = p.ff
            self.info.write_text(json.dumps(GAME_INFO))
            with mock.patch.object(df, 'capture_clients', return_value=None):   # retry due; the start fails
                p.tick(lambda: True, 'display')
            card_ff.terminate.assert_called_once()
            self.assertEqual(p.kind, 'card')                               # a publisher again, not nothing
            self.assertTrue(p.running())
            self.assertEqual(p.card_why, 'capture start failed')
            self.assertGreater(p.next_try, time.monotonic())
            self.assertEqual(p.card_text(p.source)[0], 'Video capture unavailable')
            self.assertFalse(any(c.args[1:2] == ['stream'] for c in procs))
            p.next_try, p.card_t = 0., 0.                                  # the guard passes again
            p.tick(lambda: True, 'display')
            self.assertEqual(p.kind, 'display')
            self.assertEqual(sum(1 for c in procs if c.args[1:2] == ['stream']), 1)

    def test_card_retry_then_early_capture_exit_restores_card(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        procs, pm = self.popen()
        streams = lambda: [c for c in procs if c.args[1:2] == ['stream']]
        ffs = lambda: [c for c in procs if str(c.args[0]) == df.FFMPEG]
        with pm, self.cgwin([self.cgrow(777)]):
            p.start_card('capture stalled; retry 2')
            p.next_try, p.card_t = 0., 0.
            p.tick(lambda: True, 'display')                                # retry due: card -> capture spawned OK
            self.assertEqual(p.kind, 'display')
            self.assertEqual(len(streams()), 1)
            grab = p.grab
            grab.poll.return_value = grab.returncode = 3                   # SCK start failed: dispgrab exit 3
            p.tick(lambda: True, 'display')
            self.assertEqual(p.kind, 'card')                               # visible card through the backoff
            self.assertTrue(p.running())
            self.assertEqual(sum(1 for c in ffs() if c.poll() is None), 1)  # exactly one live publisher (the card)
            self.assertEqual(len(streams()), 1)                            # no new SCK client
            self.assertGreater(p.next_try, time.monotonic())
            p.tick(lambda: True, 'display')                                # backoff not over: still the card
            self.assertEqual(p.kind, 'card')
            self.assertEqual(len(streams()), 1)
            p.next_try, p.card_t = 0., 0.
            p.tick(lambda: True, 'display')                                # retry: one new capture
            self.assertEqual(p.kind, 'display')
            self.assertEqual(len(streams()), 2)
            self.assertEqual(sum(1 for c in streams() if c.poll() is None), 1)

    def test_encoder_exit_tears_down_capture_before_card(self):
        p = self.start_running()
        grab, ff = p.grab, p.ff
        ff.poll.return_value = ff.returncode = 1                           # encoder died, capture still alive
        seen = []

        def card(why):
            seen.append((why, grab.poll(), p.grab, p.ff))
        with mock.patch.object(p, 'start_card', side_effect=card):
            p.tick(lambda: True, 'display')
        grab.terminate.assert_called_once()
        self.assertEqual(len(seen), 1)
        why, rc, g, f = seen[0]
        self.assertEqual(why, 'capture start failed')
        self.assertIsNotNone(rc)                                           # capture reaped before the card
        self.assertIsNone(g)
        self.assertIsNone(f)

    def test_no_card_when_early_exit_leaves_unreaped_capture(self):
        p = self.start_running()
        grab = p.grab
        grab.terminate.side_effect = grab.kill.side_effect = None          # capture survives TERM and KILL
        p.ff.poll.return_value = p.ff.returncode = 1
        procs, pm = self.popen()
        with pm, mock.patch.object(p, 'start_card') as card:
            p.tick(lambda: True, 'display')
            p.next_try = 0.
            p.tick(lambda: True, 'display')
        card.assert_not_called()
        self.assertIs(p.grab, grab)
        self.assertFalse(any(c.args[1:2] == ['stream'] for c in procs))

    def test_no_card_when_start_failure_leaves_unreaped_capture(self):
        self.write_src(MUMU)
        self.info.write_text(json.dumps(GAME_INFO))
        p = self.pipe()
        real = df.subprocess.Popen

        def fake(cmd, *a, **kw):
            if cmd[0] == 'ps' or (len(cmd) > 1 and cmd[1] in ('info', 'windows')):
                return real(cmd, *a, **kw)
            if len(cmd) > 1 and cmd[1] == 'stream':
                return fake_proc(cmd, 5152, dies=False)
            raise OSError('ffmpeg missing')
        with mock.patch.object(df.subprocess, 'Popen', side_effect=fake), mock.patch.object(p, 'start_card') as card:
            p.tick(lambda: True, 'display')
        card.assert_not_called()
        self.assertEqual(p.grab.pid, 5152)

    def test_nulls_plan_no_sck_while_capture(self):
        self.write_src(dict(kind='nulls', instances=[dict(window='x')]))
        with self.cgwin([dict(id=1, owner='A', title='', layer=0, bounds=[0, 0, 9, 16])]):
            with self.assertRaises(RuntimeError):
                df.source_plan(sck_guard=lambda: 'capture running')
        self.assertEqual(self.calls(), [])
        with self.cgwin([dict(id=1, owner='A', title='inst x', layer=0, bounds=[0, 0, 9, 16])]):
            self.assertEqual(df.source_plan(sck_guard=lambda: 'capture running')[1][0][0]['id'], 1)

    def test_ffmpeg_only_kinds_ungated(self):
        p = self.pipe()
        p.kind, p.ff = 'card', fake_proc()
        self.assertTrue(p.stop('card', lambda: False))        # no capture child: nothing to protect
        self.assertEqual(p.kind, None)


class DirectRunLayout(Base):
    def test_direct_session_root(self):
        r = self.d/'runs'/'memloop-s01'
        r.mkdir(parents=True)
        (r/'frames.jsonl').write_text(json.dumps(dict(n=1, state='battle', tick=3)) + '\n')
        drv = df.Driver()
        self.assertEqual(drv.find(), r)
        drv.follow(drv.find())
        self.assertEqual((drv.run, drv.match), ('memloop-s01', ''))


try:
    import cv2 as _cv2
    import numpy as _np
except ImportError:
    _cv2 = _np = None


@unittest.skipIf(_cv2 is None, 'needs cv2 + numpy (Mac venv, or a local uv venv)')
class CardRender(unittest.TestCase):
    """The visible status card: dark slate (not black), centred lines that fit, legible at the 540-wide phone rendition.
    CARD_PNG_DIR=dir also writes the rendered cards there for a visual check."""
    CASES = {'stalled': ['Video capture stalled', 'reconnecting, attempt 12', 'retry in 60 s', '23:41 PDT'],
             'nowindow': ['Waiting for the', 'MuMu Android Device window', '23:41 PDT']}

    def check(self, name, w, h):
        img = df.render_card(self.CASES[name], w, h)
        self.assertEqual(img.shape, (h, w, 3))
        bg = _np.array(df.CARD_BG, _np.uint8)
        self.assertGreater(int(bg.max()), 25)                              # not a black frame
        diff = _np.abs(img.astype(int) - bg).sum(axis=2) > 60              # text pixels
        ys, xs = _np.nonzero(diff)
        self.assertGreater(len(xs), 500)
        self.assertGreater(xs.min(), .04*w)                                # nothing clipped at the sides
        self.assertLess(xs.max(), .96*w)
        self.assertLess(abs((xs.min() + xs.max())/2 - w/2), .05*w)         # centred
        self.assertLess(abs((ys.min() + ys.max())/2 - h/2), .08*h)
        phone = _cv2.resize(img, (540, round(540*h/w)), interpolation=_cv2.INTER_AREA)
        rows = _np.nonzero((_np.abs(phone.astype(int) - bg).sum(axis=2) > 60).any(axis=1))[0]
        first = rows[_np.concatenate(([True], _np.diff(rows) > 1))]        # top of each text line
        self.assertGreaterEqual(len(first), len(self.CASES[name]))
        out = os.environ.get('CARD_PNG_DIR')
        if out:
            _cv2.imwrite(str(Path(out)/f'card-{name}-{w}x{h}.png'), img)
            _cv2.imwrite(str(Path(out)/f'card-{name}-{w}x{h}-phone540.png'), phone)
        return phone, rows

    def test_render_sizes(self):
        for name in self.CASES:
            for w, h in ((1034, 1838), (1044, 1856), (720, 1280)):
                phone, rows = self.check(name, w, h)
                band = _np.nonzero(_np.diff(rows) > 1)[0]
                line1 = rows[:band[0] + 1] if len(band) else rows
                self.assertGreaterEqual(len(line1), 14)                    # first line >= 14 px tall at 540 wide

    def test_card_writer_emits_nv12(self):
        p = df.Pipeline(30, dict(desktop=['8000k'] * 3, phone=['1500k'] * 3), (540, 960))
        p.size, p.card_why, p.stale_restarts, p.next_try = (1034, 1838), 'capture stalled; retry 2', 2, time.monotonic() + 4
        out = []
        ff = mock.MagicMock()
        ff.poll.side_effect = lambda: None if not out else 0               # one frame, then "exited"
        ff.stdin.write.side_effect = out.append
        p._card_writer(ff)
        self.assertEqual(len(out), 1)
        self.assertEqual(len(out[0]), 1034*1838*3//2)
        y = _np.frombuffer(out[0][:1034*1838], _np.uint8)
        self.assertGreater(int(_np.median(y)), 30)                         # luma of the slate, not black (16)


class SourceText(unittest.TestCase):
    def test_card_text_names_no_bluestacks(self):
        src = (HERE.parent/'display_feed.py').read_text()
        body = src[src.index('def _card_writer'):src.index('def ffargs')]
        self.assertNotIn('BlueStacks', body)
        self.assertNotIn("start_card('no BlueStacks", src)

    def test_sck_helpers_only_on_start_paths(self):
        src = (HERE.parent/'display_feed.py').read_text()
        body = src[src.index('def check_window'):src.index('def write_state')]
        self.assertNotIn('probe(', body)
        self.assertNotIn('grab_info', body)
        self.assertEqual(src.count('grab_info('), 2)                       # definition + probe()
        self.assertEqual(src.count('self.probe('), 2)                      # start() + window_present fallback
        self.assertEqual(src.count("[GRAB, 'windows']"), 1)                # list_windows only, after sck_guard
        tick = src[src.index('    def tick('):src.index('    def recover_stale(')]
        self.assertNotIn('probe(', tick)
        start = src[src.index('    def start(self, allowed):'):src.index('    def stop(')]
        self.assertLess(start.index('self.fresh_allowed(allowed)'), start.index('self.probe(allowed)'))
        probe = src[src.index('    def probe('):src.index('    def start(self, allowed):')]
        self.assertLess(probe.index('self.sole_client_ok(allowed_fn)'), probe.index('grab_info(src)'))
        lw = src[src.index('def list_windows('):src.index('def source_plan(')]
        self.assertLess(lw.index('sck_guard()'), lw.index("[GRAB, 'windows']"))

    def test_main_window_source_skips_nulls_discovery(self):
        src = (HERE.parent/'display_feed.py').read_text()
        self.assertRegex(src, r"if k % 50 == 0 and \(drv_proc or pipe\.source is not None\):\s*\n\s*plan = None")


class MainExit(unittest.TestCase):
    def test_main_loop_exit_is_gated(self):
        src = (HERE.parent/'display_feed.py').read_text()
        body = src[src.index('def main():'):src.index("if __name__ == '__main__':")]
        self.assertNotIn('while not stop.is_set()', body)
        self.assertRegex(body, r"if stop\.is_set\(\) or \(a\.seconds and now - t0 > a\.seconds\):\s*\n\s*"
                               r"if exit_ready\(pipe, allowed\.fresh\):\s*\n\s*break")
        self.assertIn('if not a.no_video and not exiting and not stop.is_set():', body)
        # the only stop on the way out is after the gated break, and is itself retried while gated
        self.assertEqual(body.count("pipe.stop("), 1)
        self.assertIn("while not pipe.stop('display_feed exiting'):", body)
        self.assertIn('pipe.allowed_fn = allowed', body)
        self.assertLess(body.index('exit_ready(pipe, allowed.fresh)'), body.index("pipe.stop('display_feed exiting')"))


class SwiftGate(unittest.TestCase):
    """dispgrab must never stop or start an SCK stream while the gate reads hold (source assertions)."""
    def loop(self):
        return SWIFT[SWIFT.index('// Supervise each SCK stream'):SWIFT.index('// --seconds ended')]

    def test_no_ungated_start(self):
        self.assertNotIn('gated: false', SWIFT)

    def test_held_checked_before_stop_and_restart(self):
        body = self.loop()
        i_held = body.index('if held() {')
        i_take = body.index('t.takeStop()')
        i_recheck = body.index('if held() { t.markStopped(why); continue }')
        i_stop = body.index('s.stopCapture()')
        i_start = body.index('try await startTile(')
        self.assertLess(i_held, i_take)
        self.assertLess(i_take, i_recheck)
        self.assertLess(i_recheck, i_stop)
        self.assertLess(i_stop, i_start)
        self.assertIn('if held() { deferred = true; break }', body[i_stop:i_start])
        self.assertIn('catch is Held { deferred = true; break }', body[i_start:])

    def test_no_fatal_exit_while_held(self):
        # a failed lookup may end past the 30 s deadline after the gate closed: re-check held() before the fatal exit
        body = self.loop()
        i_recheck = body.index('if !started && held() { deferred = true }')
        i_defer = body.index('if deferred { t.markStopped("restart deferred: gate hold"); continue }')
        i_fail = body.index('fail("no source window to restart on for 30 s", 3)')
        self.assertLess(i_recheck, i_defer)
        self.assertLess(i_defer, i_fail)
        self.assertEqual(body.count('fail('), 1)            # the only fatal exit in the supervise loop

    def startup(self):
        return SWIFT[SWIFT.index('        for t in tiles {\n            while true {'):SWIFT.index('// Supervise each SCK stream')]

    def test_startup_failure_defers_while_held(self):
        # grid: tile A streams, tile B's lookup fails after the gate closed -> no exit (it would stop A mid-battle)
        body = self.startup()
        i_catch = body.index('catch {')
        i_held = body.index('if held() && tiles.contains(where: { $0.stream != nil }) {')
        i_cont = body.index('continue', i_held)
        fails = [m.start() for m in re.finditer(r'fail\(', body)]
        self.assertEqual(len(fails), 3)                       # NoWindow, CropOutside, startCapture: all after the check
        self.assertTrue(i_catch < i_held < i_cont < min(fails))
        self.assertNotIn('catch is NoWindow', body)           # no catch clause that bypasses the held check

    def test_start_tile_never_exits(self):
        fn = SWIFT[SWIFT.index('func startTile'):SWIFT.index('func jsonStr')]
        self.assertNotIn('fail(', fn)                          # errors are thrown to the gated callers
        self.assertIn('throw CropOutside(', fn)

    def test_every_late_fail_is_gated(self):
        # each fail() reachable once a stream may run sits behind a held() wait/check
        emit = SWIFT[SWIFT.index('func emit('):SWIFT.index('struct NoWindow')]
        self.assertLess(emit.index('while held() { Thread.sleep(forTimeInterval: 0.5) }'), emit.index('fail("stdout closed", 0)'))
        tail = SWIFT[SWIFT.index('// --seconds ended'):]
        stop_loop = tail[tail.index('for t in tiles {'):tail.index('say("done")')]
        i_wait = stop_loop.index('while held() { try? await Task.sleep(nanoseconds: 500_000_000) }')
        i_stop = stop_loop.index('try? await t.stream?.stopCapture()')
        self.assertLess(i_wait, i_stop)                        # re-checked before EACH tile's stop (inside the loop)
        i_end = stop_loop.index('}', i_stop)
        self.assertIn('while held() { try? await Task.sleep(nanoseconds: 500_000_000) }', stop_loop[i_end:])  # + exit
        late = SWIFT[SWIFT.index('        for t in tiles {\n            while true {'):]
        self.assertEqual(len(re.findall(r'fail\(', late)), 4)  # 3 startup (gated) + 1 recovery (gated)

    def test_start_tile_rechecks_after_lookup(self):
        fn = SWIFT[SWIFT.index('func startTile'):SWIFT.index('func jsonStr')]
        self.assertLess(fn.index('findWindow('), fn.index('if gated && held() { throw Held() }'))
        self.assertLess(fn.index('if gated && held() { throw Held() }'), fn.index('startCapture()'))

    def test_no_window_query_while_held(self):
        self.assertRegex(self.loop(), r'if mono\(\) - lastCheck >= 10 && !held\(\) \{')

    def test_stop_capture_only_in_gated_paths(self):
        # supervise loop (gated above) and the final exit; nowhere else
        self.assertEqual(len(re.findall(r'stopCapture\(\)', SWIFT)), 2)


if __name__ == '__main__':
    unittest.main()
