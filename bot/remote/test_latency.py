"""Local pipe/SSH fixtures only; no remote fleet connections or daemon discovery."""
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(HERE), *sys.path]):
        spec.loader.exec_module(module)
    return module


client = load("latency_client")
sampler = load("tailscaled_sampler")
responder = load("latency_responder")
measure = load("measure_payload")
with patch.object(sys, "path", [str(HERE), *sys.path]):
    context = load("network_context")


class ResponderTests(unittest.TestCase):
    def start(self, *args):
        process = subprocess.Popen([sys.executable, "-B", str(HERE / "latency_responder.py"), *args],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup, process)
        return process

    @staticmethod
    def cleanup(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=1)

    def test_flush_and_request_limit(self):
        process = self.start("--max-requests", "2")
        for i, size in enumerate((47281, 51200)):
            line = client.request_line(size, i, b"x" * 60000)
            process.stdin.write(line)
            process.stdin.flush()
            # exchange uses nonblocking deadlines; no test can hang on readline.
            import selectors
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(2), "response was not immediately flushed")
            response = json.loads(process.stdout.readline())
            self.assertEqual(response["id"], f"{i:08d}")
            self.assertGreaterEqual(response["server_send_ns"], response["server_receive_ns"])
            self.assertTrue(180 <= len(json.dumps(response["action"]).encode()) <= 250)
        self.assertEqual(process.wait(timeout=1), 0)

    def test_eof_and_invalid_input(self):
        for data, expected in ((b"", 0), (b"not-json\n", 2), (b"{}\n", 2),
                               (b"[]\n", 2), (b"{}", 2), (b"x" * (1024 * 1024 + 1), 2)):
            with self.subTest(data_size=len(data)):
                process = self.start()
                out, _ = process.communicate(data, timeout=2)
                self.assertEqual(process.returncode, expected)
                self.assertEqual(out, b"")

    def test_idle_and_partial_request_wall_limit(self):
        for partial in (b"", b'{"id":'):
            with self.subTest(partial=partial):
                process = self.start("--max-seconds", ".12")
                if partial:
                    process.stdin.write(partial)
                    process.stdin.flush()
                self.assertEqual(process.wait(timeout=1), 0)

    def test_backpressured_stdout_wall_limit(self):
        # File input fills stdout without any writer thread. Do not drain stdout
        # until the responder's wall-clock limit has exited the process.
        with tempfile.TemporaryFile() as source:
            source.write(b'{"id":"00000001","padding":""}\n' * 10000)
            source.seek(0)
            blocked = subprocess.Popen([sys.executable, "-B", str(HERE / "latency_responder.py"),
                                        "--max-seconds", ".15", "--max-requests", "10000"],
                                       stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                self.assertEqual(blocked.wait(timeout=1), 0)
            finally:
                self.cleanup(blocked)


class ClientTests(unittest.TestCase):
    def probe(self, command=None, count=2, hz=20, seconds=2, timeout=.5, stop_signal=lambda: False):
        with tempfile.TemporaryDirectory() as directory:
            return client.run_probe(command or [sys.executable, "-B", str(HERE / "latency_responder.py")],
                                    [47281, 5120, 51200], count, hz, seconds, timeout,
                                    Path(directory) / "STOP", subprocess.DEVNULL, stop_signal)

    def test_persistent_session_and_percentiles(self):
        result = self.probe()
        self.assertEqual(result["reason"], "complete")
        self.assertEqual(result["ssh_sessions_started"], 1)
        self.assertEqual(result["reconnect_count"], 0)
        self.assertEqual(result["timeouts"], 0)
        self.assertGreaterEqual(result["client_cpu_percent_one_core"], 0)
        self.assertEqual([g["request_bytes"] for g in result["payloads"]], [47281, 5120, 51200])
        for group in result["payloads"]:
            self.assertEqual(group["count"], 2)
            self.assertLessEqual(group["rtt_ms"]["p50"], group["rtt_ms"]["max"])
        self.assertEqual(client.percentiles(list(range(1, 101))),
                         {"p50": 50, "p90": 90, "p95": 95, "p99": 99, "max": 100})

    def test_timeout_aborts_without_reconnect(self):
        # Complete warmup, then consume a request but never answer it.
        command = [sys.executable, "-u", "-c",
                   "import sys,json,time; r=json.loads(sys.stdin.readline()); "
                   "print(json.dumps(dict(id=r['id'],action={},server_receive_ns=1,server_send_ns=2)),flush=True); "
                   "sys.stdin.readline(); time.sleep(10)"]
        result = self.probe(command, timeout=.08)
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["timeouts"], 1)
        self.assertEqual(result["payloads"][0]["timeouts"], 1)
        self.assertEqual(result["reconnect_count"], 0)
        self.assertLess(result["elapsed_s"], 1)

    def test_stop_while_reading_and_writing(self):
        for command in ([sys.executable, "-c", "import time;time.sleep(10)"],
                        [sys.executable, "-u", "-c", "import sys,time;sys.stdin.readline();time.sleep(10)"]):
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as directory:
                    stop = Path(directory) / "STOP"
                    # A subprocess creates STOP without touching any real process.
                    marker = subprocess.Popen([sys.executable, "-c",
                                               "import sys,time;from pathlib import Path;time.sleep(.12);Path(sys.argv[1]).touch()",
                                               str(stop)])
                    started = time.monotonic()
                    try:
                        result = client.run_probe(command, [51200], 2, 2, 5, 2, stop, subprocess.DEVNULL)
                    finally:
                        marker.wait(timeout=1)
                    self.assertEqual(result["reason"], "stop")
                    self.assertLess(time.monotonic() - started, .5)

    def test_existing_stop_launches_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            stop = Path(directory) / "STOP"
            stop.touch()
            with patch.object(client.subprocess, "Popen", side_effect=AssertionError("must not launch")):
                result = client.run_probe(["unused"], [5120], 1, 2, 1, 1, stop, subprocess.DEVNULL)
            self.assertEqual(result["reason"], "stop")
            self.assertEqual(result["ssh_sessions_started"], 0)

    def test_cli_stop_reaps_sampler_and_writes_summary_under_one_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Fake sampler subprocess, never runs pgrep/ps. Exercise main's real
            # child cleanup, resource accounting and output flow around STOP.
            (root / "tailscaled_sampler.py").write_text(
                "import sys,time,signal,json\nfrom pathlib import Path\n"
                "output=Path(sys.argv[sys.argv.index('--output')+1])\n"
                "def stop(*args):\n output.write_text(json.dumps(dict(samples=[{}],errors=[])));sys.exit(0)\n"
                "signal.signal(signal.SIGTERM,stop)\nwhile True: time.sleep(.01)\n")
            stop = root / "STOP"
            marker = subprocess.Popen([sys.executable, "-c",
                                       "import sys,time;from pathlib import Path;time.sleep(.12);Path(sys.argv[1]).touch()",
                                       str(stop)])
            argv = ["client", "--max-seconds", "5", "--output", str(root / "summary.json"),
                    "--stop-file", str(stop)]
            started = time.monotonic()
            try:
                with patch.object(client, "ROOT", root), patch.object(client, "__file__", str(root / "latency_client.py")), \
                        patch.object(sys, "platform", "darwin"), patch.object(sys, "argv", argv), \
                        patch.object(client.os, "nice", return_value=10), patch.object(client.signal, "signal"), \
                        patch.object(client, "ssh_command", return_value=[sys.executable, "-c", "import time;time.sleep(10)"]) as command_builder, \
                        patch.object(sys, "stdout", io.StringIO()) as stdout:
                    self.assertEqual(client.main(), 1)
                    self.assertIn("__RC=1", stdout.getvalue())
                    command_builder.assert_called_once_with("127x08", 5, 451)  # 150 per size + warmup
                self.assertLess(time.monotonic() - started, .5)
            finally:
                marker.wait(timeout=1)
            result = json.loads((root / "summary.json").read_text())
            self.assertEqual(result["reason"], "stop")
            self.assertTrue(result["sampler_ok"])
            self.assertGreaterEqual(result["total_local_cpu_percent_one_core"], result["client_cpu_percent_one_core"])

    def test_wall_limit_during_warmup(self):
        result = self.probe([sys.executable, "-c", "import time;time.sleep(10)"], seconds=.12)
        self.assertEqual(result["reason"], "max_seconds")
        self.assertLess(result["elapsed_s"], .5)

    def test_exact_payload_and_safe_transport(self):
        for size in (47281, 5120, 51200):
            line = client.request_line(size, 123, b"x" * 60000)
            self.assertEqual(len(line), size)
            self.assertEqual(json.loads(line)["id"], "00000123")
        with self.assertRaises(ValueError):
            client.ssh_command("127x05", 600, 901)
        command = client.ssh_command("127x08", 600, 901)
        for option in ("ControlMaster=no", "ControlPath=none", "StrictHostKeyChecking=yes", "Compression=no"):
            self.assertIn(option, command)

    def test_effective_ssh_config_clears_inherited_forwarding(self):
        # ssh -G only parses a synthetic config; no connection or listener.
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "ssh_config"
            config.write_text("Host *\n HostName 100.100.100.8\n"
                              " LocalForward 127.0.0.1:54321 127.0.0.1:80\n"
                              " RemoteForward 54322 127.0.0.1:80\n"
                              " DynamicForward 127.0.0.1:54323\n"
                              " ForwardAgent yes\n ForwardX11 yes\n Tunnel yes\n")
            for host in ("127x08", "127x04"):
                command = client.ssh_command(host, 1, 1)
                text = subprocess.check_output(["ssh", "-G", "-F", str(config), *command[1:-1]],
                                               text=True, stderr=subprocess.DEVNULL, timeout=2)
                fields = dict(line.split(None, 1) for line in text.splitlines() if " " in line)
                self.assertEqual(fields["clearallforwardings"], "yes")
                for key in ("forwardagent", "forwardx11"):
                    self.assertEqual(fields[key], "no")
                self.assertEqual(fields["tunnel"], "false")
                for key in ("localforward", "remoteforward", "dynamicforward"):
                    self.assertNotIn(key, fields)

    def test_hostname_only_known_hosts_stays_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host_key, user_key = root / "host_key", root / "user_key"
            for key in (host_key, user_key):
                subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
                               check=True, capture_output=True, timeout=2)
            server_config = root / "sshd_config"
            server_config.write_text(f"HostKey {host_key}\nAuthorizedKeysFile {user_key}.pub\n"
                                     "StrictModes no\nUsePAM no\nPasswordAuthentication no\n"
                                     "KbdInteractiveAuthentication no\nLogLevel ERROR\n")
            ssh_config = root / "ssh_config"
            # OpenSSH exempts loopback addresses from CheckHostIP. A UDP route
            # lookup discovers this machine's local interface without sending
            # any packet; the actual SSH fixture connects only to that interface.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
                route.connect(("192.0.2.1", 9))
                local_ip = route.getsockname()[0]
            ssh_config.write_text(f"Host 127x08\n HostName {local_ip}\n"
                                  " HostKeyAlias probe-fixture\n CheckHostIP yes\n")
            known_hosts = root / "known_hosts"
            public_key = " ".join(host_key.with_suffix(".pub").read_text().split()[:2])
            # Positive control must reproduce the old append, so an unsuccessful
            # connection or a fixture that bypasses IP checking cannot pass.
            for fixed in (False, True):
                with self.subTest(fixed=fixed), socket.socket() as listener:
                    listener.bind((local_ip, 0))
                    listener.listen(1)
                    listener.settimeout(2)
                    port = listener.getsockname()[1]
                    before = f"probe-fixture {public_key}\n".encode()
                    known_hosts.write_bytes(before)
                    options = client.ssh_command("127x08", 1, 1)[1:-1]
                    if not fixed:
                        index = options.index("CheckHostIP=no")
                        del options[index - 1:index + 1]
                    process = subprocess.Popen(
                        ["ssh", "-4", "-F", str(ssh_config), "-p", str(port), "-i", str(user_key),
                         "-o", "IdentitiesOnly=yes", "-o", f"UserKnownHostsFile={known_hosts}",
                         "-o", "GlobalKnownHostsFile=/dev/null", *options, "true"],
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    server = None
                    try:
                        connection, _ = listener.accept()
                        with connection:
                            # Inetd mode: only the test owns a transient local
                            # listener; sshd handles this one accepted connection.
                            server = subprocess.Popen(["/usr/sbin/sshd", "-i", "-e", "-f", str(server_config)],
                                                      stdin=connection, stdout=connection, stderr=subprocess.PIPE)
                        _, error = process.communicate(timeout=3)
                        self.assertEqual(process.returncode, 0, error.decode(errors="replace"))
                        server.communicate(timeout=2)
                        after = known_hosts.read_bytes()
                        if fixed:
                            self.assertEqual(after, before)
                        else:
                            self.assertNotEqual(after, before)
                            self.assertIn(f"[{local_ip}]:{port}".encode(), after)
                    finally:
                        for child in (process, server):
                            if child is not None:
                                if child.poll() is None:
                                    child.kill()
                                child.communicate(timeout=2)

    def test_stderr_flood_is_capped_and_aborts_before_and_after_warmup(self):
        for warmup in (False, True):
            with self.subTest(warmup=warmup), tempfile.TemporaryDirectory() as directory:
                source = "import os,sys,time,json; "
                if warmup:
                    source += ("r=json.loads(sys.stdin.readline()); "
                               "print(json.dumps(dict(id=r['id'],action={},server_receive_ns=1,server_send_ns=2)),flush=True); ")
                source += "os.write(2,b'x'*(8*1024*1024)); time.sleep(10)"
                sink = io.BytesIO()
                result = client.run_probe([sys.executable, "-u", "-c", source], [5120], 1, 2, 5, 2,
                                          Path(directory) / "STOP", sink)
                self.assertEqual(result["reason"], "error")
                self.assertTrue(result["stderr_limit_exceeded"])
                self.assertIn("stderr byte limit", result["error"])
                self.assertEqual(len(sink.getvalue()), 65536)
                self.assertLess(result["elapsed_s"], 1)

    def test_path_confinement(self):
        for module, function in ((client, client.confined), (sampler, sampler.output_path)):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "probe"
                root.mkdir()
                with patch.object(module, "ROOT", root):
                    self.assertEqual(function(str(root / "out.json")), root / "out.json")
                    with self.assertRaises(ValueError):
                        function(str(root / ".." / "outside"))
                    (root / "escape").symlink_to(Path(directory), target_is_directory=True)
                    with self.assertRaises(ValueError):
                        function(str(root / "escape" / "outside"))


class SamplerAndSizingTests(unittest.TestCase):
    def test_context_uses_config_address_and_refuses_proxy_route(self):
        self.assertEqual(context.tcp_target("hostname 100.101.102.103\nport 22\nproxycommand none\n"),
                         ("100.101.102.103", 22))
        for config in ("hostname 127x08\nport 22\n", "hostname 100.101.102.103\nproxycommand nc proxy\n",
                       "hostname 100.101.102.103\nproxyjump bastion\n"):
            with self.subTest(config=config), self.assertRaises(ValueError):
                context.tcp_target(config)

    def test_sampler_exact_process_reads_and_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            usual = {"cpu": {"mean_percent": 12, "max_percent": 17}}
            (root / "tailscaled-usual.json").write_text(json.dumps(usual))
            calls = []

            def process_read(argv, **kwargs):
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, "123\n" if argv[0] == "pgrep" else "14.5\n", "")

            argv = ["sampler", "--output", str(root / "during.json"), "--label", "during", "--max-seconds", ".06",
                    "--stop-file", str(root / "STOP"), "--usual-file", str(root / "tailscaled-usual.json")]
            with patch.object(sampler, "ROOT", root), patch.object(sys, "platform", "darwin"), \
                    patch.object(sys, "argv", argv), patch.object(sampler.os, "nice", return_value=10), \
                    patch.object(sampler.subprocess, "run", side_effect=process_read):
                self.assertEqual(sampler.main(), 0)
            result = json.loads((root / "during.json").read_text())
            self.assertEqual(calls, [["pgrep", "-x", "tailscaled"], ["ps", "-o", "%cpu=", "-p", "123"]])
            self.assertEqual(result["usual_cpu"], usual["cpu"])
            self.assertEqual(result["cpu"]["max_percent"], 14.5)
            self.assertFalse(result["max_above_17_percent"])

    def test_measurement_joins_wall_time_and_uses_trailing_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [{"n": i, "ts_ms": i * 10000, "units": "x" * i * 10} for i in range(20)]
            decisions = [{"n": i, "action": 1} for i in range(20)]
            (root / "frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            (root / "decisions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in decisions))
            result = measure.measure(root)
            self.assertEqual(result["selected_frame_n"], 18)
            self.assertEqual(result["history_row_count"], 3)
            self.assertEqual(result["realistic_bytes"], result["frame_p95_bytes"] + result["history_bytes_including_newlines"])


class SupervisionTests(unittest.TestCase):
    @staticmethod
    def wait_for(predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.01)
        raise AssertionError("local subprocess did not reach expected state")

    @staticmethod
    def exited(pid):
        # Inspect only PIDs recorded by our own fake processes. A dead orphan
        # guardian can briefly be a zombie awaiting the system reaper.
        read = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=.25)
        return read.returncode != 0 or not read.stdout.strip() or read.stdout.strip().startswith("Z")

    def bootstrap(self, directory, context_mode=False, flood=False):
        root = Path(directory)
        worker = ("import os,time,signal; from pathlib import Path; "
                  f"Path({str(root / 'ssh.pid')!r}).write_text(str(os.getpid())+' '+str(os.getppid())); "
                  "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                  + ("os.write(2,b'x'*(8*1024*1024)); " if flood else "") + "time.sleep(600)")
        (root / "tailscaled_sampler.py").write_text(
            "import os,time,sys,signal,json\nfrom pathlib import Path\n"
            "Path(__file__).with_suffix('.pid').write_text(str(os.getpid())+' '+str(os.getppid()))\n"
            "output=Path(sys.argv[sys.argv.index('--output')+1])\n"
            "def stop(*args):\n output.write_text(json.dumps(dict(samples=[{}],errors=[])));sys.exit(0)\n"
            "signal.signal(signal.SIGTERM,stop)\nwhile True: time.sleep(.01)\n")
        name = "network_context" if context_mode else "latency_client"
        code = (f"import sys;sys.path.insert(0,{str(HERE)!r});import {name} as app; "
                "import latency_client;from pathlib import Path;sys.platform='darwin'; "
                f"latency_client.ROOT=Path({directory!r}); "
                f"app.__file__={str(root / 'latency_client.py')!r}; "
                f"app.ssh_command=lambda *args:[sys.executable,'-u','-c',{worker!r}]+(['true'] if {context_mode!r} else []); "
                f"sys.argv=['app','--output',{str(root / 'summary.json')!r},'--stop-file',{str(root / 'STOP')!r}]; "
                "sys.exit(app.main())")
        # Context replaces its final SSH argument with true: preserve worker code
        # by giving its fake command a disposable final element above.
        process = subprocess.Popen([sys.executable, "-B", "-c", code],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup, process, root)
        self.wait_for(lambda: (root / "ssh.pid").exists())
        if not context_mode:
            self.wait_for(lambda: (root / "tailscaled_sampler.pid").exists())
        return process, root

    @staticmethod
    def cleanup(process, root):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=2)
        # Failure cleanup targets only exact fake PIDs created in this test.
        for file in root.glob("*.pid"):
            for pid in map(int, file.read_text().split()):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def assert_children_exit(self, root):
        for file in root.glob("*.pid"):
            child, guardian = map(int, file.read_text().split())
            self.wait_for(lambda: self.exited(child))
            self.wait_for(lambda: self.exited(guardian))
            # The guardian waited for the actual worker, so it is fully reaped.
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)

    def test_client_sigkill_and_ssh_disconnect_leave_no_workers(self):
        for signum in (signal.SIGKILL, signal.SIGHUP):
            with self.subTest(signal=signum), tempfile.TemporaryDirectory() as directory:
                process, root = self.bootstrap(directory)
                started = time.monotonic()
                process.send_signal(signum)
                process.wait(timeout=1)
                self.assert_children_exit(root)
                self.assertLess(time.monotonic() - started, 1)
                if signum == signal.SIGHUP:
                    self.assertEqual(json.loads((root / "summary.json").read_text())["reason"], "stop")

    def test_lifetime_pipe_disconnect_kills_and_reaps_owned_child(self):
        from probe_process import SupervisedProcess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = ("import os,signal,time;from pathlib import Path; "
                    "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                    f"Path({str(root / 'child')!r}).write_text(str(os.getpid()));time.sleep(600)")
            process = SupervisedProcess([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self.wait_for(lambda: (root / "child").exists())
                child = int((root / "child").read_text())
                process.stop()  # EOF only: no signal or explicit reap of worker.
                self.assertEqual(process.wait(timeout=.5), 137)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child, 0)
            finally:
                process.finish()

    def test_context_sigterm_reaps_stalled_ssh_and_exits_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            process, root = self.bootstrap(directory, context_mode=True)
            started = time.monotonic()
            process.terminate()
            self.assertEqual(process.wait(timeout=.5), 1)
            self.assert_children_exit(root)
            self.assertLess(time.monotonic() - started, .5)
            self.assertEqual(json.loads((root / "summary.json").read_text())["tcp"], {})

    def test_cli_stderr_file_stays_capped_during_eight_megabyte_flood(self):
        with tempfile.TemporaryDirectory() as directory:
            process, root = self.bootstrap(directory, flood=True)
            self.assertEqual(process.wait(timeout=1), 1)
            self.assert_children_exit(root)
            result = json.loads((root / "summary.json").read_text())
            self.assertTrue(result["stderr_limit_exceeded"])
            self.assertEqual(result["reason"], "error")
            self.assertEqual((root / "summary.ssh-stderr.txt").stat().st_size, 65536)


if __name__ == "__main__":
    unittest.main()
