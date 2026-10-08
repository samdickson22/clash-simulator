"""Read-only mmap contract. T3's adapter can map field names in manifest.json.

manifest: schema='clasher.imitation.model-store.v1', role, rows, arrays (field ->
relative .npy), optional row_table (structured .npy), metadata (perspective JSON),
assets (.npz), hashes, wait_keep_probability (1 for C56, .5 for pre-thinned S122).
All arrays are mmap, never NPZ/object/pickle payloads. Target/metadata are kept
separate from the whitelisted public feature adapter.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import Dataset
from .features import build_row, collate_features
from .losses import intent_target


LABELS = {"action": "expert_actions", "supervised": "expert_action_supervision_valid",
          "weight": "weights", "intent_card": "intent_card", "intent_bin": "intent_bin",
          "intent_observed": "intent_observed", "intent_valid": "intent_valid"}
D1_KEYS = ("own_deck", "own_queue", "opp_hand_known", "opp_next_card", "opp_queue",
           "opp_history", "own_history", "opp_abilities", "opp_elixir", "opp_refill_remaining",
           "own_refill_remaining", "opp_cards_revealed", "elixir_exact")
PACKET_KEYS = ("hand_ids", "hand_levels", "opponent_seen_card_ids", "global_features", "champion_button")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class PackedStore(Dataset):
    def __init__(self, directory, role, assets=None):
        self.root = Path(directory).resolve()
        self.manifest_path = self.root / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text())
        if role not in ("train", "dev") or self.manifest["role"] != role:
            raise ValueError("T4 opens train or dev only, with exact role match")
        self.t3 = "schema" not in self.manifest and "perspectives" in self.manifest
        if self.t3:
            self._load_t3(role, assets)
            return
        if self.manifest["schema"] != "clasher.imitation.model-store.v1":
            raise ValueError("T3 store schema needs an explicit adapter; never guess field semantics")
        self.role = role
        self.arrays = {name: np.load(self.path(path), mmap_mode="r", allow_pickle=False)
                       for name, path in self.manifest["arrays"].items()}
        if "row_table" in self.manifest:
            table = np.load(self.path(self.manifest["row_table"]), mmap_mode="r", allow_pickle=False)
            self.arrays.update({name: table[name] for name in table.dtype.names})
        self.assets_path = self.path(self.manifest["assets"])
        self.assets = np.load(self.assets_path, allow_pickle=False)
        self.costs = self.assets["costs"]
        self.metadata = json.loads(self.path(self.manifest["metadata"]).read_text()) if "metadata" in self.manifest else {}
        self.wait_keep_probability = float(self.manifest.get("wait_keep_probability", 1))
        if self.role == "dev" and self.wait_keep_probability != 1:
            raise ValueError("dev must retain all waits")
        if self.wait_keep_probability not in (.5, 1.):
            raise ValueError("unsupported wait pre-thinning")
        for key in (*LABELS.values(), "perspective_ids", "row_ids", *PACKET_KEYS, *D1_KEYS):
            if key not in self.arrays or len(self.arrays[key]) != len(self):
                raise ValueError(f"missing/wrong-length array {key}")
        self.hashes = {**self.manifest.get("hashes", {}), "store_manifest": sha256(self.manifest_path),
                       "assets": sha256(self.assets_path)}

    def _load_t3(self, role, assets):
        """Exact adapter for reports/.../imitation/build_store.py, without imports.

        Parent access is restricted to the shared public mask and manifests.
        No other role is opened; no data or manifest is modified.
        """
        parent = self.root.parent
        root_manifest = json.loads((parent/"manifest.json").read_text())
        if root_manifest.get("schema") != "clasher.imitation.packed.v1" or not root_manifest.get("passed"):
            raise ValueError("T3 packed store is not qualified")
        if root_manifest["role_manifests"][role] != sha256(self.manifest_path):
            raise ValueError("T3 role manifest hash mismatch")
        if assets is None:
            raise ValueError("T3 store requires --assets built with its frozen v5 runtime")
        self.role = role
        self.arrays = {name: np.load(self.path(name+".npy"), mmap_mode="r", allow_pickle=False)
                       for name in self.manifest["arrays"]}
        self.arrays["mask_table"] = np.load(parent/"mask_table.npy", mmap_mode="r", allow_pickle=False)
        self.mask_bitorder = "big"  # np.packbits/unpackbits default in the frozen corpus.
        self.assets_path = Path(assets).resolve()
        self.assets = np.load(self.assets_path, allow_pickle=False)
        asset_info = json.loads(Path(str(self.assets_path)+".json").read_text())
        if asset_info["asset_sha256"] != sha256(self.assets_path):
            raise ValueError("static asset hash mismatch")
        self.costs = self.assets["costs"]
        self.metadata = {}
        self.wait_keep_probability = 1.
        # Source row identity survives role packing and epoch reshuffles.
        self.arrays["row_ids"] = (self.arrays["source_unit"].astype(np.int64) << 32) | self.arrays["source_row"].astype(np.int64)
        self.arrays["perspective_ids"] = self.arrays["episode_ids"]
        self.hashes = {"tokens": asset_info["token_sha256"], "assets": asset_info["asset_sha256"],
                       "roles": root_manifest["role_file_sha256"], "eval_spec": root_manifest["eval_spec_sha256"],
                       "sidecar_manifest": root_manifest["sidecar_manifest_sha256"],
                       "store_manifest": sha256(parent/"manifest.json"), "role_manifest": sha256(self.manifest_path)}
        self.perspectives = self.manifest["perspectives"]

    def path(self, relative):
        p = (self.root / relative).resolve()
        if not p.is_relative_to(self.root) or any(part in ("audit", "eval", "eval_ood") for part in p.relative_to(self.root).parts):
            raise ValueError("store reference escapes role or enters protected/audit data")
        return p

    def __len__(self):
        return int(self.manifest["rows"])

    def column(self, name):
        return self.arrays[name]

    def __getitem__(self, i):
        a = self.arrays
        p = {key: a[key][i] for key in PACKET_KEYS}
        if "action_mask" in a:
            p["action_mask"] = a["action_mask"][i]
        else:
            p["action_mask"] = np.unpackbits(a["mask_table"][a["mask_index"][i]], bitorder=getattr(self, "mask_bitorder", "little"))[:2306].astype(bool)
        offset, end = a["entity_offsets"][i:i+2]
        for name in ("ids", "levels", "features"):
            p["entity_"+name] = a["flat_entity_"+name][offset:end]
        p["entity_mask"] = np.ones(end-offset, bool)
        if self.t3:
            keys = tuple(k for k in D1_KEYS if k not in ("opp_history", "own_history", "opp_abilities"))
            keys += ("opp_recent_play_ids", "opp_recent_play_features", "own_recent_play_ids", "own_recent_play_features", "opp_ability_ids", "opp_ability_ages")
            d1 = {key: a[key][i] for key in keys}
        else:
            d1 = {key: a[key][i] for key in D1_KEYS}
        row = build_row(p, d1, self.costs)
        if self.t3:
            observed = not bool(a["intent_censored"][i])
            hazard_bin, _ = intent_target(float(a["intent_delay_ticks"][i])/20, observed)
            y = {key: a[name][i] for key, name in LABELS.items() if not key.startswith("intent_")}
            y.update(intent_card=a["intent_deck_index"][i], intent_bin=hazard_bin,
                     intent_observed=observed, intent_valid=True)
        else:
            y = {key: a[name][i] for key, name in LABELS.items()}
        # On disk, intent_card indexes the supplied own_deck. The model's eight
        # auxiliary classes index sorted token IDs, independent of deck storage order.
        if int(y["intent_card"]) >= 0:
            if int(y["intent_card"]) >= 8:
                raise ValueError("intent deck index outside [0,8)")
            token = d1["own_deck"][int(y["intent_card"])]
            y["intent_card"] = np.searchsorted(np.sort(d1["own_deck"]), token)
        action = int(y["action"])
        if y["supervised"] and (not 0 <= action < 2306 or not p["action_mask"][action]):
            raise ValueError(f"illegal supervised label at row {i}")
        if not 0 <= int(y["intent_bin"]) <= 12 or not np.isfinite(y["weight"]) or y["weight"] < 0:
            raise ValueError(f"invalid target/weight at row {i}")
        y.update(row_id=a["row_ids"][i], perspective=a["perspective_ids"][i], index=i)
        return row, y


def collate(rows):
    features, targets = zip(*rows)
    return collate_features(features), {key: torch.from_numpy(np.asarray([y[key] for y in targets])) for key in targets[0]}


def hash64(values):
    """SplitMix64; overflow is part of the definition, independent of processes."""
    x = np.asarray(values, np.uint64).copy()
    with np.errstate(over="ignore"):
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xbf58476d1ce4e5b9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94d049bb133111eb)
    return x ^ (x >> np.uint64(31))


def epoch_indices(store, epoch, seed, subset_fraction=1.):
    ids = store.column("row_ids").astype(np.uint64)
    # Perspective subsampling preserves complete trajectories for the 2% shakedown.
    perspective_hash = hash64(store.column("perspective_ids"))
    subset = (perspective_hash >> np.uint64(11)).astype(np.float64) / 2**53 < subset_fraction
    wait = store.column("expert_actions") == 2304
    p = .25 / store.wait_keep_probability
    threshold = int(p*2**32)
    sampled = (hash64(ids ^ np.uint64(seed) ^ np.uint64((epoch+1)*0x9e3779b9)) >> np.uint64(32)) < threshold
    keep = store.column("expert_action_supervision_valid").astype(bool) & subset & (~wait | sampled)
    ix = np.flatnonzero(keep)
    np.random.default_rng(np.random.SeedSequence([seed, epoch])).shuffle(ix)
    return ix
