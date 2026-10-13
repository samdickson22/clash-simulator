"""Fake frozen END modules for offline S5 tests. The monitor runs in a real spawned process and speaks the real
end_reference checkpoint protocol (fleet_reference.py:235-256); the guard data is synthetic.
``manifest["fake"]`` steers failures. The claim/measure entry points exist and raise if ever called."""
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

from helpers import sha

CALLS = []


class Forbidden(RuntimeError):
    pass


def forbidden(name):
    def call(*a, **k):
        CALLS.append(name)
        raise Forbidden(name + " must never be called by the preflight")
    return call


def guard_row(fake, ticks, sshd):
    return dict(passes=True, reason=None, rules="frozen-t1-op1-op2-op3-op4-op5-op6-v1",
                console={"positive": False}, memavailable_bytes=2 ** 40, foreign_compute=[], foreign_active=[],
                ssh_family_sample=dict(stop=False), ssh_family_blocks={},
                system_bus=dict(cpu_ticks=ticks, core_fraction=0.0001, interfered=False, retired=False),
                idle_services=dict(interfered=False, retired=False))


def reference_monitor(stop, phase, owned, clusters, output, cpu, bundle, manifest, channel):
    fake = manifest.get("fake", {})
    output = Path(output)
    blocks = output.parent / "guard-blocks.jsonl"
    start, ticks, n = time.monotonic(), 0, 0
    with output.open("x") as rows, blocks.open("x") as block_stream:
        while not stop.is_set():
            while channel.poll():
                request = channel.recv()
                reason = fake.get("reason_at_" + request["event"])
                g = guard_row(fake, ticks, 1)
                g.update(passes=reason is None, reason=reason)
                receipt = dict(request, utc=time.time(), reporting_guard=g)
                if request["event"] == "admit":
                    (output.parent / "guard-admission.json").write_text(json.dumps(receipt) + "\n")
                else:
                    if request["event"] == "end":
                        g["completed_block"] = dict(id=request["id"], seconds=0.5, ssh_family=dict(interfered=False),
                                                    system_bus=dict(core_fraction=0.0002, interfered=False),
                                                    idle_services=dict(interfered=False))
                    block_stream.write(json.dumps(receipt) + "\n"); block_stream.flush()
                channel.send(dict(request, reason=reason))
                if reason:
                    raise RuntimeError("guard: " + reason)
            n += 1
            # exact synthetic bus load: bus_percent % of one core since the monitor started (health-only)
            ticks = fake.get("bus_percent", 0) * os.sysconf("SC_CLK_TCK") / 100. * (time.monotonic() - start)
            if fake.get("side_file") and n == 3:
                Path(manifest["reference_load_profile"]["guard"]["job"], fake["side_file"]).write_text("{}\n")
            current = phase.value.decode()
            sshd = 1 + (1 if fake.get("login_during_hold") and current == "preflight-hold" and n % 7 == 0 else 0)
            row = dict(timestamp=time.monotonic(), utc=time.time(), phase=current,
                       processes=[dict(pid=i, name="sshd") for i in range(sshd)],
                       cpu_clock_mhz_by_processor={str(c): 3000.0 + c for c in range(8)},
                       reporting_guard=guard_row(fake, ticks, sshd))
            rows.write(json.dumps(row) + "\n"); rows.flush()
            time.sleep(fake.get("interval", 0.02))


class Backend:
    def __init__(self, fake, repository):
        self.k4s_rows = {"s%d" % i: i for i in range(6)}
        self.fake, self.repository, self.work = fake, repository, 0

    def k4s_work(self, row, **kw):
        self.work += 1
        if self.fake.get("claim_in_backend"):
            reg = Path(self.repository) / "reports/explore/k4s-confirm/end/registry/round-00/127x03"
            reg.mkdir(parents=True, exist_ok=True)
            (reg / "attempt-00.json").write_text("{}")
        time.sleep(0.01)

    def close(self):
        if self.fake.get("close_fails"):
            raise RuntimeError("backend close failed")


class Background:
    def __init__(self, fake, workers=2):
        self.fake = fake
        self.workers = [SimpleNamespace(pid=900001 + i) for i in range(workers)]
        self.check_external = None

    def __enter__(self):
        if self.fake.get("background_fails"):
            raise RuntimeError("Background reference load failed to become ready")
        return self

    def check(self):
        self.check_external()

    def __exit__(self, *exc):
        return False


def cleanup_steps(state, join_seconds=10):            # end_reference.py:252-279, verbatim logic
    errors = []

    def attempt(step):
        try:
            step()
        except BaseException as error:
            errors.append(error)
    if state.stop is not None:
        attempt(state.stop.set)
    monitor = state.monitor
    if monitor is not None and monitor.pid:
        def stop_monitor():
            monitor.join(join_seconds)
            if monitor.is_alive():
                monitor.terminate()
                monitor.join(join_seconds)
                raise RuntimeError("Reference census process had to be terminated")
        attempt(stop_monitor)
    for end in (state.channel, state.monitor_channel):
        if end is not None:
            attempt(end.close)
    if state.backend is not None:
        attempt(state.backend.close)
    if errors:
        raise errors[0]


class FleetTechnicalError(RuntimeError):
    def __init__(self, cause, detail):
        self.cause = cause
        super().__init__(detail)


def make(guard_job, fake=None, host="127x03", slot_count=3):
    """A Frozen-compatible object; its bundle manifest is what the test writes as the pinned tiers-pins.json."""
    fake = dict(fake or {})
    tmp = Path(guard_job).parent
    profile = dict(host=host, reference_slot=0, slot_count=slot_count, console_rule=False, warmup_seconds=300,
                   perception="none", plan="plan.json", end_evidence="end-evidence.json",
                   guard=dict(job=str(guard_job), freeze="FROZEN-T1.json", root="guard"))
    manifest = dict(profile="fleet-reference", reference_load_profile=profile, topology=dict(P=[0], E=[]),
                    files={}, runtime_files={}, fake=fake)
    calls = dict(end_job=0)

    def end_job(*a):
        calls["end_job"] += 1
        return {}

    def compare_mhz(reporting, census, cpus, slots):
        measured = [r for r in census if r["phase"] in ("reference-speed", "reference-deadlines")]
        ok = not fake.get("mhz_fails")
        return dict(passes=ok, absolute_relative_difference=0.01 if ok else 0.2, reference_rows=len(measured))

    def validate_blocks(rows, require_measurement=True):
        if not any(r["event"] == "end" for r in rows):
            raise FleetTechnicalError("validity_census", "Missing completed reference guard blocks")

    fleet_validity = SimpleNamespace(validate_census=lambda rows: None, validate_admission=lambda row: None,
                                     validate_blocks=validate_blocks)
    fleet_profile = SimpleNamespace(compare_mhz=compare_mhz)
    G = SimpleNamespace(
        evidence_spec=lambda *a: dict(spec=a),
        frozen_helpers=lambda spec, root: ({}, (SimpleNamespace(), fleet_profile, fleet_validity)),
        FrozenHooks=lambda: SimpleNamespace(host=lambda: dict(system="Linux", node=host, nice=10, sched_other=True)),
        k4s_reporting_profile=lambda bundle, m, spec, h, fe, fp: (
            profile, {}, ([0, 1], [[2, 3], [4, 5]][:slot_count - 1], 7), dict(sha256="e" * 64), [dict(slots=3)]),
        K4SFleetBackground=lambda *a: Background(fake, slot_count - 1))
    L = SimpleNamespace(sha=sha, MANIFEST_NAME="K4S-MAC-MANIFEST.json",
                        check_corpus=lambda a, b, inv, pub, ids: list(ids), claim_attempt=forbidden("claim_attempt"))
    P = SimpleNamespace(BLOCK=2, read_lines=lambda p: [json.loads(s) for s in Path(p).read_text().splitlines()],
                        pool_context=forbidden("pool_context"))
    E = SimpleNamespace(end_job=end_job, producer_claim=forbidden("producer_claim"))
    ER = SimpleNamespace(
        K4_CORPUS_SHA256="k" * 64, KERNEL_REL="sdefault.py", SCORER_REL="anchor_x.py", HERE=tmp,
        frozen_identity=lambda a, vb, ns: (manifest, dict(native_sha256=sha(a.native), measurement_files={}),
                                           dict(bundle_profile_host=host)),
        backend=lambda a: Backend(fake, a.repository), executing_sources=lambda files: True,
        cleanup_steps=cleanup_steps, measure=forbidden("measure"), run_attempt=forbidden("run_attempt"))
    F = SimpleNamespace(ER=ER, G=G, L=L, P=P, E=E, calls=calls, manifest=manifest,
                        bundle_tools=lambda: SimpleNamespace(NATIVE_SHA="n", validate_bundle=lambda *a, **k: manifest,
                                                             FleetTechnicalError=FleetTechnicalError),
                        guard_tools=lambda: SimpleNamespace(reference_monitor=reference_monitor,
                                                            cpu_counters=lambda: {},
                                                            validate_physical_cpus=lambda cpus: None,
                                                            validate_topology=lambda t, c, darwin: dict(P=[0], E=[])))
    return F
