"""Conformance-kit harness (bootstrap-r1). Run ONLY by k4s_bootstrap_kit.run_scenario in a fresh interpreter:

    python [-O] -B -I [-S] kit_harness.py SPEC.json

It installs read/open recorders BEFORE the entrypoint runs, runs the entrypoint exactly as given (never normalized),
and writes a JSON report. Recorders: os.open / os.read / os.pread / os.readv / os.preadv / os.fdopen and
builtins.open / io.open / io.open_code are wrapped; every descriptor is identified by fstat (st_dev, st_ino) and
compared with the WATCHED inodes the kit identified before the run (the canary, decoy and layer inodes). A watched
inode that is opened or read is recorded with the byte count (and, for the layer, the SHA-256 of the bytes read).
Opening a watched inode through io (FileIO reads cannot be wrapped) is itself recorded as consumption.

Modes:
  run_path  sys.argv = [entry] + argv; runpy.run_path(entry, run_name="__main__")
  import    importlib spec_from_file_location(module_name, entry); exec_module
  loader    the canonical shell loader program text, exec-ed as "-c" code with sys.argv = ["-c", LAYER, SHA, SIZE,
            "--"] + argv (the harness must run under -I -S, as the wrappers do)
Optional swap: when compile() is first called with a "<k4s-bootstrap " filename (the canonical bootstrap has hashed
the layer and is about to execute it), the decoy is renamed over the layer path, so a loader that re-opened or
re-imported by pathname after hashing would run the decoy.
"""
import builtins
import hashlib
import io
import json
import os
import sys


def main():
    with io.open(sys.argv[1], "r", encoding="utf-8") as handle:
        spec = json.load(handle)
    watched = {tuple(v): k for k, v in spec["watch"].items()}          # (dev, ino) -> label
    record = {"opens": {}, "bytes": {}, "events": [], "swapped": False}
    layer_hash = {}
    real = {"open": os.open, "read": os.read, "pread": os.pread, "readv": os.readv,
            "preadv": getattr(os, "preadv", None), "fdopen": os.fdopen, "bopen": builtins.open,
            "io_open": io.open, "open_code": io.open_code, "compile": builtins.compile, "fstat": os.fstat}

    def label_of(fd):
        try:
            st = real["fstat"](fd)
        except OSError:
            return None
        return watched.get((st.st_dev, st.st_ino))

    def note_open(label, how, what):
        record["opens"][label] = record["opens"].get(label, 0) + 1
        record["events"].append([how, label, str(what)[:300]])

    def note_bytes(label, how, data):
        record["bytes"][label] = record["bytes"].get(label, 0) + len(data)
        record["events"].append([how, label, len(data)])
        layer_hash.setdefault(label, hashlib.sha256()).update(data)

    def h_open(path, flags, *args, **kwargs):
        fd = real["open"](path, flags, *args, **kwargs)
        label = label_of(fd)
        if label is not None:
            note_open(label, "os.open", path)
        return fd

    def h_read(fd, n):
        data = real["read"](fd, n)
        label = label_of(fd)
        if label is not None:
            note_bytes(label, "os.read", data)
        return data

    def h_pread(fd, n, offset):
        data = real["pread"](fd, n, offset)
        label = label_of(fd)
        if label is not None:
            note_bytes(label, "os.pread", data)
        return data

    def h_readv(fd, buffers):
        n = real["readv"](fd, buffers)
        label = label_of(fd)
        if label is not None:
            note_bytes(label, "os.readv", b"?" * n)
        return n

    def h_preadv(fd, buffers, offset, *args):
        n = real["preadv"](fd, buffers, offset, *args)
        label = label_of(fd)
        if label is not None:
            note_bytes(label, "os.preadv", b"?" * n)
        return n

    def wrap_file(how, opener):
        def opened(file, *args, **kwargs):
            f = opener(file, *args, **kwargs)
            try:
                label = label_of(f.fileno())
            except (AttributeError, OSError, ValueError):
                label = None
            if label is not None:
                note_open(label, how, file)
                record["bytes"][label] = record["bytes"].get(label, 0) + 1     # io open counts as consumption
            return f
        return opened

    def h_compile(source, filename, *args, **kwargs):
        swap = spec.get("swap")
        if (swap and not record["swapped"] and isinstance(filename, str) and filename.startswith("<k4s-bootstrap ")):
            os.rename(swap["decoy"], swap["layer"])
            record["swapped"] = True
            record["events"].append(["swap", "decoy->layer", swap["layer"]])
        return real["compile"](source, filename, *args, **kwargs)

    os.open, os.read, os.pread, os.readv = h_open, h_read, h_pread, h_readv
    if real["preadv"] is not None:
        os.preadv = h_preadv
    os.fdopen = wrap_file("os.fdopen", real["fdopen"])
    builtins.open = wrap_file("builtins.open", real["bopen"])
    io.open = wrap_file("io.open", real["io_open"])
    io.open_code = wrap_file("io.open_code", real["open_code"])
    builtins.compile = h_compile

    outcome = {"kind": "returned"}
    try:
        if spec["mode"] == "run_path":
            import runpy
            sys.argv = [spec["entry"]] + spec["argv"]
            runpy.run_path(spec["entry"], run_name="__main__")
        elif spec["mode"] == "import":
            import importlib.util
            loaded = importlib.util.spec_from_file_location(spec["module_name"], spec["entry"])
            module = importlib.util.module_from_spec(loaded)
            sys.modules[spec["module_name"]] = module
            loaded.loader.exec_module(module)
        elif spec["mode"] == "loader":
            with real["io_open"](spec["loader_file"], "r", encoding="utf-8") as handle:
                code = handle.read()
            sys.argv = ["-c", spec["layer"], spec["sha256"], str(spec["size"]), "--"] + spec["argv"]
            exec(real["compile"](code, "<string>", "exec"), {"__name__": "__main__", "__builtins__": builtins})
        else:
            raise SystemExit("kit harness: unknown mode")
    except SystemExit as error:
        outcome = {"kind": "exit", "code": error.code if isinstance(error.code, int) or error.code is None
                   else str(error.code)}
    except BaseException as error:                                     # the refusal convention of the entrypoint
        outcome = {"kind": "exception", "type": type(error).__name__, "message": str(error)}
    finally:
        os.open, os.read, os.pread, os.readv = real["open"], real["read"], real["pread"], real["readv"]
        if real["preadv"] is not None:
            os.preadv = real["preadv"]
        os.fdopen, builtins.open, io.open, io.open_code = real["fdopen"], real["bopen"], real["io_open"], real["open_code"]
        builtins.compile = real["compile"]
    modules = []
    for name, module in list(sys.modules.items()):
        tag = getattr(module, "__k4s_bootstrap__", None) if module is not None else None
        if isinstance(tag, tuple):
            modules.append([name] + [str(t) if not isinstance(t, int) else t for t in tag])
    report = {"outcome": outcome, "opens": record["opens"], "bytes": record["bytes"], "events": record["events"][:200],
              "swapped": record["swapped"], "bootstrapped_modules": modules,
              "read_sha256": {k: v.hexdigest() for k, v in layer_hash.items()},
              "optimize": sys.flags.optimize, "version": list(sys.version_info[:3])}
    fd = real["open"](spec["report"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with real["fdopen"](fd, "w", encoding="utf-8") as handle:
        json.dump(report, handle)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (OSError, ValueError):
            pass
    os._exit(0)


if __name__ == "__main__":
    main()
