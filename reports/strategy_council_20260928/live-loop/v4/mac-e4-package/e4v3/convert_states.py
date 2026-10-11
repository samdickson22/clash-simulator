#!/usr/bin/env python3
"""One-time states.pkl -> states-rows.{bin,json} conversion (TIERS Amendment 3).

Reads the reviewed fixture, either the assembled states.pkl (SHA-checked before
it executes) or T1's public states plus the separate golden125, assembled as
T1's END preparation did (public + golden). Each row is written, in the original
order, as pickle.dumps(row, protocol=5).

Those bytes are NOT reproducible across processes: torch's legacy storage
serialization (Tensor -> torch.storage._load_from_bytes) keys each storage by
str(storage._cdata), a memory address. Row identity is therefore established
by an address-independent canonical digest of the row's object graph (types,
values, float bits, array/tensor dtype-shape-stride-bytes, in-row aliasing),
computed for the original object and again for the object unpickled from disk.
Raw-byte SHA-256 pins every stored row against later change. Never writes beside
its inputs; never overwrites.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import platform
import struct
import sys
import time
import types

from state_rows import CONTAINER, INDEX, PROTOCOL, SCHEMA

CONVERTER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
STATE_ROWS_SHA256 = hashlib.sha256((Path(__file__).parent / "state_rows.py").read_bytes()).hexdigest()
IMMUTABLE = (str, bytes, int, float, bool, complex, type(None), tuple, frozenset, type,
             types.BuiltinFunctionType, types.FunctionType, types.ModuleType)


def file_sha(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 22), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


class HashWriter:
    def __init__(self):
        self.digest, self.size = hashlib.sha256(), 0

    def write(self, data):
        view = memoryview(data)  # protocol 5 passes large buffers as PickleBuffer
        self.digest.update(view)
        self.size += view.nbytes
        return view.nbytes


def load_pickle(path, expected):
    digest, size = file_sha(path)
    if digest != expected:
        raise ValueError("Pin mismatch: " + str(path))
    with Path(path).open("rb") as stream:  # executes only after the SHA matched
        return pickle.load(stream), dict(path=str(path), sha256=digest, bytes=size)


def _name(obj):
    return (getattr(obj, "__module__", None) or "?") + "." + (getattr(obj, "__qualname__", None) or getattr(obj, "__name__", "?"))


def canonical_digest(obj, stats=None):
    """SHA-256 of an address-independent encoding of obj's object graph.

    Covers types, values, float bits, in-graph object aliasing, and the backing
    buffer of every NumPy array/torch tensor (which arrays are views of, or share
    storage with, which others, at which offsets/strides). ``stats`` (a dict) is
    incremented with arrays/tensors and those sharing a buffer seen earlier.
    """
    digest = hashlib.sha256()
    memo = {("stats",): stats if stats is not None else {}}
    _canonical(obj, digest.update, memo, [])
    return digest.hexdigest()


def _buffer_root(x):
    """The object that owns an array's memory (following ndarray/memoryview bases)."""
    np = sys.modules.get("numpy")
    root = x
    while True:
        base = root.base if np is not None and isinstance(root, np.ndarray) else (
            root.obj if isinstance(root, memoryview) else None)
        if base is None:
            return root
        root = base


def _same_buffer_structure(a, b, pa, pb, path, seen):
    """Arrays/tensors must share backing memory exactly where the originals did."""
    ra, rb = _buffer_root(a), _buffer_root(b)
    key = ("buffer", id(ra))
    if key in seen:
        previous, origin_a, origin_b = seen[key][1]
        if previous is not rb or pa - origin_a != pb - origin_b:
            raise ValueError(path + ": backing buffer sharing differs")
        return
    if ("buffer-b", id(rb)) in seen:
        raise ValueError(path + ": backing buffer sharing differs")
    seen[key] = (ra, (rb, pa, pb))
    seen[("buffer-b", id(rb))] = (rb, ra)


def _buffer(x, pointer, out, memo, keep):
    """Number each backing buffer once; later sharers are emitted as references."""
    root = _buffer_root(x)
    key = ("buffer", id(root))
    stats = memo[("stats",)]
    stats["arrays"] = stats.get("arrays", 0) + 1
    if key in memo:
        stats["sharing_buffer"] = stats.get("sharing_buffer", 0) + 1
        index, origin = memo[key]
        out(b"^%d,%d;" % (index, pointer - origin))
        return False
    keep.append(root)
    memo[key] = (memo.setdefault(("buffers",), 0), pointer)
    memo[("buffers",)] += 1
    out(b"^new;")
    return True


def _canonical(x, out, memo, keep):
    kind = type(x)
    if x is None or kind is bool:
        out(b"N" if x is None else b"T" if x else b"F")
        return
    if kind is int:
        text = str(x).encode()
        out(b"i%d:" % len(text) + text)
        return
    if kind is float:
        out(b"f" + struct.pack("<d", x))
        return
    if kind is str:
        text = x.encode("utf-8", "surrogatepass")
        out(b"s%d:" % len(text) + text)
        return
    if kind is bytes:
        out(b"b%d:" % len(x) + x)
        return
    if id(x) in memo:  # in-row aliasing is part of the identity
        out(b"@%d;" % memo[id(x)])
        return
    memo[id(x)] = len(memo)
    keep.append(x)  # temporaries stay alive: ids are never recycled
    np, torch = sys.modules.get("numpy"), sys.modules.get("torch")
    if isinstance(x, (type, types.FunctionType, types.BuiltinFunctionType, types.ModuleType)):
        text = _name(x).encode()
        out(b"G%d:" % len(text) + text)
    elif np is not None and kind is np.ndarray and not x.dtype.hasobject:
        head = repr((x.dtype.str, x.dtype.descr, x.shape, x.strides, bool(x.flags.writeable))).encode()
        out(b"A%d:" % len(head) + head)
        _buffer(x, x.__array_interface__["data"][0], out, memo, keep)
        data = x.tobytes(order="A")
        out(b"%d:" % len(data) + data)
    elif np is not None and kind is np.ndarray:
        out(b"O" + repr((x.dtype.str, x.shape)).encode())
        _canonical(x.ravel(order="K").tolist(), out, memo, keep)
    elif np is not None and isinstance(x, np.generic):
        head, data = x.dtype.str.encode(), x.tobytes()
        out(b"S%d:" % len(head) + head + b"%d:" % len(data) + data)
    elif torch is not None and isinstance(x, torch.Tensor):
        t = x.detach()
        head = repr((_name(kind), str(t.dtype), tuple(t.shape), tuple(t.stride()), t.storage_offset(),
                     x.requires_grad, str(t.device), str(t.layout))).encode()
        out(b"X%d:" % len(head) + head)
        storage = t.untyped_storage()
        key = ("storage", storage.data_ptr(), storage.nbytes())
        stats = memo[("stats",)]
        stats["arrays"] = stats.get("arrays", 0) + 1
        if key in memo:  # tensors sharing one storage stay sharing it
            stats["sharing_buffer"] = stats.get("sharing_buffer", 0) + 1
            out(b"^%d;" % memo[key])
        else:
            keep.append(storage)
            memo[key] = memo.setdefault(("storages",), 0)
            memo[("storages",)] += 1
            data = bytes(storage.cpu())
            out(b"^new;%d:" % len(data) + data)
        _canonical(getattr(x, "__dict__", {}), out, memo, keep)
    elif kind is list or kind is tuple:
        out(b"L%d:" % len(x) if kind is list else b"U%d:" % len(x))
        for item in x:
            _canonical(item, out, memo, keep)
    elif kind is dict:
        out(b"D%d:" % len(x))
        for key, value in x.items():
            _canonical(key, out, memo, keep)
            _canonical(value, out, memo, keep)
    elif kind is set or kind is frozenset:
        out(b"E%d:" % len(x) if kind is set else b"Z%d:" % len(x))
        for item in sorted(x, key=canonical_digest):  # hash-seed independent
            _canonical(item, out, memo, keep)
    else:
        reduced = x.__reduce_ex__(PROTOCOL)
        if isinstance(reduced, str):
            text = (_name(kind) + "/" + reduced).encode()
            out(b"G%d:" % len(text) + text)
            return
        reduced = list(reduced) + [None] * (6 - len(reduced))
        out(b"R")
        _canonical(reduced[0], out, memo, keep)
        _canonical(reduced[1], out, memo, keep)
        _canonical(reduced[2], out, memo, keep)
        _canonical(None if reduced[3] is None else list(reduced[3]), out, memo, keep)
        _canonical(None if reduced[4] is None else list(reduced[4]), out, memo, keep)


def deep_equal(a, b, path="row", seen=None):
    """Exact structural equality: same types, keys/order, values, float bits, array bytes."""
    seen = {} if seen is None else seen
    if type(a) is not type(b):
        raise ValueError(path + ": type " + type(a).__name__ + " != " + type(b).__name__)
    if id(a) in seen:
        if seen[id(a)][1] is not b:
            raise ValueError(path + ": aliasing differs")
        return
    if isinstance(a, float):
        if a.hex() != b.hex() and not (math.isnan(a) and math.isnan(b)):
            raise ValueError(path + ": float")
        return
    if isinstance(a, (str, bytes, int, bool, type(None), complex)):
        if a != b:
            raise ValueError(path + ": value")
        return
    seen[id(a)] = (a, b)  # keeps temporaries alive: no id reuse
    np = sys.modules.get("numpy")  # arrays exist only if numpy is already imported
    if np is not None and isinstance(a, np.ndarray):
        if a.dtype != b.dtype or a.shape != b.shape or a.dtype.hasobject:
            if a.dtype != b.dtype or a.shape != b.shape:
                raise ValueError(path + ": array dtype/shape")
            for i, (x, y) in enumerate(zip(a.ravel().tolist(), b.ravel().tolist())):
                deep_equal(x, y, path + "[" + str(i) + "]", seen)
            return
        if a.tobytes(order="C") != b.tobytes(order="C") or a.strides != b.strides or a.flags.writeable != b.flags.writeable:
            raise ValueError(path + ": array bytes/flags")
        _same_buffer_structure(a, b, a.__array_interface__["data"][0], b.__array_interface__["data"][0], path, seen)
        return
    if np is not None and isinstance(a, np.generic):
        if a.tobytes() != b.tobytes():
            raise ValueError(path + ": numpy scalar")
        return
    torch = sys.modules.get("torch")
    if torch is not None and isinstance(a, torch.Tensor):
        if canonical_digest(a) != canonical_digest(b):  # never the address-keyed storage pickle
            raise ValueError(path + ": tensor")
        sa, sb = a.untyped_storage(), b.untyped_storage()
        key = ("storage", sa.data_ptr())
        if key in seen:
            if seen[key][1] != sb.data_ptr():
                raise ValueError(path + ": tensor storage sharing differs")
        elif ("storage-b", sb.data_ptr()) in seen:
            raise ValueError(path + ": tensor storage sharing differs")
        else:
            seen[key], seen[("storage-b", sb.data_ptr())] = (sa, sb.data_ptr()), (sb, None)
        return
    if isinstance(a, dict):
        if list(a) != list(b):
            raise ValueError(path + ": dict keys/order")
        for key in a:
            deep_equal(a[key], b[key], path + "[" + repr(key)[:40] + "]", seen)
        if type(a) is dict:
            return
    elif isinstance(a, (list, tuple)):
        if len(a) != len(b):
            raise ValueError(path + ": length")
        for i, (x, y) in enumerate(zip(a, b)):
            deep_equal(x, y, path + "[" + str(i) + "]", seen)
        if type(a) in (list, tuple):
            return
    elif isinstance(a, (set, frozenset)):
        if pickle.dumps(sorted(map(repr, a))) != pickle.dumps(sorted(map(repr, b))):
            raise ValueError(path + ": set")
        return
    if isinstance(a, IMMUTABLE):
        if a is not b:
            raise ValueError(path + ": global object")
        return
    # Any other object: compare exactly what pickle preserves of it.
    ra, rb = a.__reduce_ex__(PROTOCOL), b.__reduce_ex__(PROTOCOL)
    if isinstance(ra, str) or isinstance(rb, str):
        if ra != rb:
            raise ValueError(path + ": global")
        return
    if len(ra) != len(rb) or ra[0] is not rb[0]:
        raise ValueError(path + ": reconstructor")
    for i, (x, y) in enumerate(zip(ra[1:], rb[1:])):
        if i in (2, 3) and x is not None and not isinstance(x, (list, tuple, dict)):
            x, y = list(x), list(y)  # list/dict item iterators
        deep_equal(x, y, path + "<reduce" + str(i + 1) + ">", seen)


def mutable_memo(pickler):
    return {key: obj for key, (_, obj) in pickler.memo.copy().items() if not isinstance(obj, IMMUTABLE)
            and type(obj).__name__ != "dtype" and not type(obj).__name__.endswith("DType")}


def fingerprint(entries):
    """One digest for the ordered fixture: ids and canonical row digests, in order."""
    return hashlib.sha256("".join(e["id"] + " " + e["canonical_sha256"] + "\n" for e in entries).encode()).hexdigest()


def write_state_rows(rows, output, source_sha256, source_bytes, source_verified, expect_fingerprint=None, final_check=None):
    """Write states-rows.{bin,json} for ``rows`` into the existing ``output``; verify from disk.

    ``source_verified`` may be True only when ``rows`` were unpickled from the file whose
    SHA-256 was checked to be ``source_sha256``; backends refuse any other index. The
    index is first written unverified; it is atomically replaced by the verified index
    only after every disk check and ``final_check()`` succeed, so a failed or
    interrupted conversion never leaves an admissible index.
    """
    output = Path(output)
    ids = [str(r["id"]) for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate fixed-state IDs")
    entries, owners, shared, keepalive, buffers = [], {}, {}, [], {}
    offset = 0
    with (output / CONTAINER).open("xb") as stream:
        for index, row in enumerate(rows):
            chunks = []
            class Sink:
                def write(self, data):
                    chunks.append(bytes(data))
                    return memoryview(data).nbytes
            pickler = pickle.Pickler(Sink(), protocol=PROTOCOL)
            pickler.dump(row)
            data = b"".join(chunks)
            memo = mutable_memo(pickler)
            keepalive.append(memo)  # pickling temporaries must not recycle ids across rows
            for key, obj in memo.items():
                if key in owners and owners[key] != index:
                    shared.setdefault(_name(type(obj)), set()).add(ids[index])
                owners.setdefault(key, index)
            stream.write(data)
            entries.append(dict(id=ids[index], offset=offset, length=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                canonical_sha256=canonical_digest(row, buffers)))
            offset += len(data)
        stream.flush()
        os.fsync(stream.fileno())
    del owners, keepalive
    if expect_fingerprint is not None and fingerprint(entries) != expect_fingerprint:
        raise ValueError("Ordered canonical fingerprint differs from the expected fixture: " + fingerprint(entries))
    container_sha, container_bytes = file_sha(output / CONTAINER)
    index = dict(schema=SCHEMA, pickle_protocol=PROTOCOL,
                 row_bytes="pickle.dumps(row, protocol=5); torch storage keys make these bytes process-specific",
                 canonical_sha256="convert_states.canonical_digest: address-independent object-graph digest",
                 fixture_canonical_fingerprint=fingerprint(entries),
                 source=dict(file="states.pkl", sha256=source_sha256, bytes=source_bytes, rows=len(rows),
                             verified=False),
                 container=dict(file=CONTAINER, sha256=container_sha, bytes=container_bytes),
                 rows=entries)
    with (output / INDEX).open("x") as stream:
        stream.write(json.dumps(index, sort_keys=True, indent=1) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    index_sha, _ = file_sha(output / INDEX)
    # Independent verification from disk, through the backend's own loader.
    from state_rows import StateRows
    store = StateRows(output, {"states.pkl": source_sha256, INDEX: index_sha, CONTAINER: container_sha},
                      require_verified_source=False)
    if store.ids != ids:
        raise ValueError("Order/identity differs")
    load_seconds = []
    try:
        for position, (identity, original) in enumerate(zip(store.ids, rows)):
            start = time.monotonic()
            loaded = store.load(identity)
            load_seconds.append(time.monotonic() - start)
            if canonical_digest(loaded) != entries[position]["canonical_sha256"]:
                raise ValueError("Unpickled state differs from the original: " + identity)
            deep_equal(original, loaded, identity)
            del loaded
    finally:
        store.close()
    if final_check is not None:
        final_check()
    if source_verified:
        index["source"]["verified"] = True
        staged = output / (INDEX + ".verified")
        with staged.open("x") as stream:
            stream.write(json.dumps(index, sort_keys=True, indent=1) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, output / INDEX)
        directory = os.open(output, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        index_sha, _ = file_sha(output / INDEX)
        StateRows(output, {"states.pkl": source_sha256, INDEX: index_sha, CONTAINER: container_sha}).close()
    lengths = sorted(e["length"] for e in entries)
    load_seconds.sort()
    return dict(index=dict(file=INDEX, sha256=index_sha),
        container=dict(file=CONTAINER, sha256=container_sha, bytes=container_bytes),
        fixture_canonical_fingerprint=index["fixture_canonical_fingerprint"],
        verification=dict(rows=len(rows), per_row_sha256=len(rows), canonical_digest_equal=len(rows),
            deep_structural_equal=len(rows), order_and_identity_equal=True,
            cross_row_shared_mutable_objects={k: len(v) for k, v in sorted(shared.items())},
            arrays_and_tensors=buffers.get("arrays", 0), sharing_a_backing_buffer=buffers.get("sharing_buffer", 0),
            source_verified=bool(source_verified)),
        row_bytes=dict(min=lengths[0], median=lengths[len(lengths)//2], max=lengths[-1]),
        load_seconds=dict(median=load_seconds[len(load_seconds)//2], p99=load_seconds[int(.99*(len(load_seconds)-1))],
                          max=load_seconds[-1], total=sum(load_seconds)))


def check_inventory(path, expected, rows):
    """T1's selected-state inventory: same ids per tier; its byte SHAs are reported, not re-derivable."""
    digest, _ = file_sha(path)
    if digest != expected:
        raise ValueError("Pin mismatch: corpus inventory")
    receipt = json.loads(Path(path).read_text())
    by_tier = {}
    for row in rows:
        if "tier" in row and "strata" in row:
            by_tier.setdefault(row["tier"], []).append(str(row["id"]))
    shas, ordered = {}, True
    for tier, value in receipt["tiers"].items():
        listed = [str(v["id"]) for v in value["state_inventory"]]
        if sorted(listed) != sorted(by_tier.get(tier, ())) or len(set(listed)) != len(listed):
            raise ValueError("Public rows differ from T1's selected-state inventory: " + tier)
        ordered = ordered and listed == by_tier[tier]
        shas.update({str(v["id"]): v["sha256"] for v in value["state_inventory"]})
    if set(by_tier) != set(receipt["tiers"]):
        raise ValueError("Public tiers differ from T1's selected-state inventory")
    reproduced = sum(shas[str(r["id"])] == hashlib.sha256(pickle.dumps(r, protocol=PROTOCOL)).hexdigest()
                     for r in rows if str(r["id"]) in shas)
    return dict(path=str(path), sha256=digest, ids_equal=True, inventory_order_equal=ordered, states=len(shas),
                byte_sha_reproduced=reproduced)


def convert(args):
    started = time.monotonic()
    if args.output.exists():
        raise FileExistsError(args.output)
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 100000))
    sys.path[:0] = [str(p) for p in args.extra_path or ()]
    from tier_backend import setup_imports
    setup_imports(args.runtime_root, args.native)
    inputs = []
    if args.states:
        rows, receipt = load_pickle(args.states, args.states_sha256)
        inputs.append(dict(receipt, role="assembled", rows=len(rows)))
        byte_identity = "states.pkl SHA verified before unpickling"
    else:
        public, receipt = load_pickle(args.public, args.public_sha256)
        inputs.append(dict(receipt, role="public", rows=len(public)))
        golden, receipt = load_pickle(args.golden, args.golden_sha256)
        inputs.append(dict(receipt, role="golden", rows=len(golden)))
        if len(public) != args.public_rows or len(golden) != args.golden_rows:
            raise ValueError("Unexpected public/golden row counts")
        for item, part in zip(inputs, (public, golden)):
            writer = HashWriter()
            pickle.dump(part, writer, protocol=5)
            item["redump_byte_identical"] = writer.digest.hexdigest() == item["sha256"]
        rows = public + golden  # T1 END-assemble-preflight-01-r1.py order
        del public, golden
        byte_identity = ("declared only: a re-dump cannot reproduce " + args.assembled_sha256 +
                         " (address-keyed torch storages); compare fixture_canonical_fingerprint with a --states run")
    writer = HashWriter()
    pickle.dump(rows, writer, protocol=5)
    assembled = dict(sha256=args.assembled_sha256, byte_identity=byte_identity,
                     redump_sha256=writer.digest.hexdigest(), redump_bytes=writer.size)
    inventory = check_inventory(args.inventory, args.inventory_sha256, rows) if args.inventory else None
    args.output.mkdir(parents=True)
    after = []
    def inputs_unchanged():
        after.extend(dict(item, sha256_after=file_sha(item["path"])[0]) for item in inputs)
        if any(item["sha256_after"] != item["sha256"] for item in after):
            raise ValueError("An input changed during conversion")
    result = write_state_rows(rows, args.output, args.assembled_sha256,
                              inputs[0]["bytes"] if args.states else args.assembled_bytes,
                              source_verified=bool(args.states), expect_fingerprint=args.expect_fingerprint,
                              final_check=inputs_unchanged)
    import numpy
    import torch
    receipt = dict(schema="clasher.e4v3.state-rows-conversion.v1", status="PASS",
        utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        host=platform.node(), python=platform.python_implementation() + platform.python_version(),
        numpy=numpy.__version__, torch=torch.__version__,
        nice=os.getpriority(os.PRIO_PROCESS, 0), cpus=sorted(os.sched_getaffinity(0)),
        converter_sha256=CONVERTER_SHA256, state_rows_sha256=STATE_ROWS_SHA256,
        inputs=after, assembled=assembled, corpus_inventory=inventory,
        rows=len(rows), output=dict(directory=str(args.output), **{k: result[k] for k in ("index", "container")}),
        fixture_canonical_fingerprint=result["fixture_canonical_fingerprint"],
        verification=result["verification"], row_bytes=result["row_bytes"], load_seconds=result["load_seconds"],
        maxrss_bytes=__import__("resource").getrusage(__import__("resource").RUSAGE_SELF).ru_maxrss*1024,
        seconds=time.monotonic()-started, outcomes_read=False, timing=False, inputs_modified=False)
    with (args.output / "conversion-receipt.json").open("x") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--extra-path", type=Path, action="append", help="inherited import directory, as T1 qualified")
    parser.add_argument("--states", type=Path, help="assembled states.pkl")
    parser.add_argument("--states-sha256")
    parser.add_argument("--public", type=Path)
    parser.add_argument("--public-sha256")
    parser.add_argument("--public-rows", type=int, default=1200)
    parser.add_argument("--golden", type=Path)
    parser.add_argument("--golden-sha256")
    parser.add_argument("--golden-rows", type=int, default=125)
    parser.add_argument("--assembled-sha256", required=True)
    parser.add_argument("--assembled-bytes", type=int, help="declared states.pkl size (with --public/--golden)")
    parser.add_argument("--expect-fingerprint", help="required ordered canonical fingerprint (e.g. from the 05 reconstruction)")
    parser.add_argument("--inventory", type=Path, help="T1 corpora.json with per-state SHA inventory")
    parser.add_argument("--inventory-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.states) == bool(args.public or args.golden):
        raise ValueError("Give either --states or --public with --golden")
    if args.states and args.states_sha256 != args.assembled_sha256:
        raise ValueError("Assembled input must be the pinned states.pkl")
    if not args.states and args.assembled_bytes is None:
        raise ValueError("--public/--golden needs the declared --assembled-bytes")
    convert(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
