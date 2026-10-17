"""Local pipes only: never invokes SSH, contacts a host, or discovers real processes."""
import importlib.util
import io
import json
from pathlib import Path
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
            argv = ["client", "--count", "1", "--max-seconds", "5", "--output", str(root / "summary.json"),
                    "--stop-file", str(stop)]
            started = time.monotonic()
            try:
                with patch.object(client, "ROOT", root), patch.object(client, "__file__", str(root / "latency_client.py")), \
                        patch.object(sys, "platform", "darwin"), patch.object(sys, "argv", argv), \
                        patch.object(client.os, "nice", return_value=10), patch.object(client.signal, "signal"), \
                        patch.object(client, "ssh_command", return_value=[sys.executable, "-c", "import time;time.sleep(10)"]), \
                        patch.object(sys, "stdout", io.StringIO()) as stdout:
                    self.assertEqual(client.main(), 1)
                    self.assertIn("__RC=1", stdout.getvalue())
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


if __name__ == "__main__":
    unittest.main()
