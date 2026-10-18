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

MUMU = dict(kind='window', owner='MuMu Android Device', crop=[0, 28, 540, 960], size=[1080, 1920], fps=30,
            label='LADDER · MuMu')
GAME_INFO = dict(window_id=777, pid=9, bounds=[100.0, 40.0, 540.0, 988.0], content_rect=[0, 0, 540, 988], scale=2.0)
DIALOG_INFO = dict(window_id=1558, pid=33766, bounds=[300.0, 200.0, 600.0, 450.0], content_rect=[0, 0, 600, 450],
                   scale=2.0)


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
                        mock.patch.object(df.Pipeline, 'PIDS', self.d/'display/pipeline.json')]
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
            if len(cmd) > 1 and cmd[1] in ('info', 'windows'):   # subprocess.run(dispgrab info): the real fake script
                return real(cmd, *a, **kw)
            m = mock.MagicMock()
            m.args, m.pid, m.returncode = cmd, 4000 + len(procs), None
            m.poll.return_value = None
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

    def test_check_window_stop_gated(self):
        p = self.start_running()
        self.info.write_text(json.dumps(dict(GAME_INFO, window_id=778)))   # window changed -> restart wanted
        seq = iter([True, False, False, False])
        p.check_window(lambda: next(seq))
        p.grab.terminate.assert_not_called()

    def test_ffmpeg_only_kinds_ungated(self):
        p = self.pipe()
        p.kind, p.ff = 'card', mock.MagicMock()
        p.ff.poll.return_value = None
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


class SourceText(unittest.TestCase):
    def test_card_text_names_no_bluestacks(self):
        src = (HERE.parent/'display_feed.py').read_text()
        body = src[src.index('def _card_writer'):src.index('def ffargs')]
        self.assertNotIn('BlueStacks', body)
        self.assertNotIn("start_card('no BlueStacks", src)

    def test_main_window_source_skips_nulls_discovery(self):
        src = (HERE.parent/'display_feed.py').read_text()
        self.assertRegex(src, r"if k % 50 == 0 and \(drv_proc or pipe\.source is not None\):\s*\n\s*plan = None")


class MainExit(unittest.TestCase):
    def test_main_loop_exit_is_gated(self):
        src = (HERE.parent/'display_feed.py').read_text()
        body = src[src.index('def main():'):src.index("if __name__ == '__main__':")]
        self.assertNotIn('while not stop.is_set()', body)
        self.assertRegex(body, r"if stop\.is_set\(\) or \(a\.seconds and now - t0 > a\.seconds\):\s*\n\s*"
                               r"if exit_ready\(pipe, allowed\):\s*\n\s*break")
        self.assertIn('if not a.no_video and not exiting and not stop.is_set():', body)
        # the only stop on the way out is after the gated break, and is itself retried while gated
        self.assertEqual(body.count("pipe.stop("), 1)
        self.assertIn("while not pipe.stop('display_feed exiting'):", body)
        self.assertIn('pipe.allowed_fn = allowed', body)
        self.assertLess(body.index('exit_ready(pipe, allowed)'), body.index("pipe.stop('display_feed exiting')"))


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
