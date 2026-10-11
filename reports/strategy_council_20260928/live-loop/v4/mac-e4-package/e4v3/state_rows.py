"""TIERS Amendment 3 state storage: the pinned states.pkl rows, one state at a time.

convert_states.py writes, for the SAME ordered rows that pickle.loads(states.pkl)
returns, each row's canonical bytes pickle.dumps(row, protocol=5) (the per-state
SHA that T1's corpus inventory already uses) into states-rows.bin, and their
offsets and SHA-256 into states-rows.json. The index binds to the pinned
states.pkl SHA; both new files are pinned by the bundle manifest.

A backend never holds the corpus. ``by_id`` unpickles one state on a miss and
drops the previously cached state. Every caller looks a state up before its
decision timer starts (prepare_work, or the argument of work()); the lookup that
measure_tiers/fleet_reference repeat after packet entry is a plain dict hit.
"""
import hashlib
import json
import os
from pathlib import Path
import pickle

SCHEMA = "clasher.e4v3.state-rows.v1"
INDEX = "states-rows.json"
CONTAINER = "states-rows.bin"
PROTOCOL = 5


class StateRows:
    def __init__(self, bundle, files, require_verified_source=True):
        bundle = Path(bundle)
        for name in ("states.pkl", INDEX, CONTAINER):
            if name not in files:
                raise ValueError("Required input is not pinned: " + name)
        data = (bundle / INDEX).read_bytes()
        if hashlib.sha256(data).hexdigest() != files[INDEX]:
            raise ValueError("Pin mismatch: " + INDEX)
        index = json.loads(data)
        if index.get("schema") != SCHEMA or index.get("pickle_protocol") != PROTOCOL:
            raise ValueError("Unsupported state index")
        if index["source"]["file"] != "states.pkl" or index["source"]["sha256"] != files["states.pkl"]:
            raise ValueError("State index is not derived from the pinned states.pkl")
        if require_verified_source and index["source"].get("verified") is not True:
            raise ValueError("State index was not converted from the SHA-verified states.pkl")
        if index["container"]["file"] != CONTAINER or index["container"]["sha256"] != files[CONTAINER]:
            raise ValueError("State index names a different container")
        entries = index["rows"]
        if len(entries) != index["source"]["rows"]:
            raise ValueError("State index row count differs from states.pkl")
        position = 0
        for entry in entries:
            if entry["offset"] != position or entry["length"] <= 0:
                raise ValueError("Non-contiguous state index")
            position += entry["length"]
        if position != index["container"]["bytes"]:
            raise ValueError("State index length differs from its container")
        self.ids = [entry["id"] for entry in entries]
        self.entries = {entry["id"]: entry for entry in entries}
        if len(self.entries) != len(entries):
            raise ValueError("Duplicate fixed-state IDs")
        self.descriptor = os.open(bundle / CONTAINER, os.O_RDONLY)
        if os.fstat(self.descriptor).st_size != position:
            os.close(self.descriptor)
            raise ValueError("State container size differs from its index")

    def load(self, identity):
        """One pinned state's canonical bytes, SHA-checked BEFORE they execute."""
        entry = self.entries[identity]
        data = os.pread(self.descriptor, entry["length"], entry["offset"])
        if len(data) != entry["length"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Pin mismatch: state " + identity)
        row = pickle.loads(data)
        if str(row["id"]) != identity:
            raise ValueError("State index identity differs from its row")
        return row

    def close(self):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None


class Rows:
    """The ordered fixture, as pickle.loads(states.pkl) returned it; streamed."""
    def __init__(self, store):
        self.store = store

    def __len__(self):
        return len(self.store.ids)

    def __iter__(self):
        for identity in self.store.ids:
            yield self.store.load(identity)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self.store.load(identity) for identity in self.store.ids[index]]
        return self.store.load(self.store.ids[index])


class ById(dict):
    """A hit is the built-in dict lookup; a miss loads that state, evicting the last."""
    def __init__(self, store):
        super().__init__()
        self.store = store

    def __missing__(self, identity):
        if identity not in self.store.entries:
            raise KeyError(identity)
        row = self.store.load(identity)
        self.clear()
        self[identity] = row
        return row
