"""Canonical-name scalar scenario algorithm; collection requires separate authority."""

import hashlib
import json
import random
from dataclasses import dataclass

VERSION = "clasher.scalar-canonical-opening.v1"
STREAMS = ("opening", "battle", "action-order", "opponent")


def encode(value):
    """UTF-8 JSON, sorted object keys, no spaces, ASCII escaping, no NaN."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def _cards(values, canonical_names):
    result = tuple(values)
    if (len(result) != 8 or len(set(result)) != 8
            or any(type(name) is not str or name not in canonical_names for name in result)):
        raise ValueError("template must contain eight distinct prevalidated canonical names")
    return result


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    cluster_id: str
    ordinal: int
    relative_decks: tuple[tuple[str, ...], tuple[str, ...]]
    stream_seeds: tuple[tuple[str, int], ...]
    attempts: int

    def world_decks(self, learner_seat):
        if type(learner_seat) is not int or learner_seat not in (0, 1):
            raise ValueError("learner seat must be zero or one")
        return self.relative_decks if learner_seat == 0 else self.relative_decks[::-1]


class CanonicalOpeningSchedule:
    def __init__(self, *, campaign_seed, role, deck_name, opponent_style,
                 learner_template, opponent_template, canonical_names, episodes):
        if type(campaign_seed) is not int or campaign_seed < 0:
            raise ValueError("campaign seed must be a nonnegative integer")
        if type(episodes) is not int or not 1 <= episodes <= 100000:
            raise ValueError("invalid fixed episode budget")
        if any(type(x) is not str or not x for x in (role, deck_name, opponent_style)):
            raise ValueError("role, deck name, and style must be explicit")
        canonical_names = tuple(canonical_names)
        if (not canonical_names or any(type(name) is not str or not name for name in canonical_names)
                or len(set(canonical_names)) != len(canonical_names)):
            raise ValueError("canonical inventory must contain distinct nonempty names")
        canonical_names = tuple(sorted(canonical_names))
        templates = (_cards(learner_template, canonical_names),
                     _cards(opponent_template, canonical_names))
        # Canonical-name membership is setup-supplied, never guessed from aliases.
        authority = {"version": VERSION, "campaign_seed": str(campaign_seed),
                          "role": role, "deck_name": deck_name,
                          "opponent_style": opponent_style,
                          "relative_templates": templates, "episodes": episodes,
                          "canonical_names": canonical_names}
        self._authority_json = encode(authority)
        self.scenarios = []
        seen_deals = set()
        for ordinal in range(episodes):
            base = {k: v for k, v in self.authority.items() if k != "episodes"}
            base["ordinal"] = ordinal
            stream_seeds = tuple((stream, int(digest({"domain": "stream-seed", "stream": stream,
                                                      "scenario": base}), 16)) for stream in STREAMS)
            opening_seed = dict(stream_seeds)["opening"]
            for attempt in range(1000):
                # Retry is a new substream, not a perturbation of battle/opponent RNG.
                attempt_seed = int(digest({"domain": "opening-attempt", "version": VERSION,
                                           "opening_seed": str(opening_seed), "attempt": attempt}), 16)
                rng = random.Random(attempt_seed)
                decks = []
                for template in templates:
                    indices = list(range(8))
                    rng.shuffle(indices)
                    decks.append(tuple(template[i] for i in indices))
                relative = tuple(decks)
                # Cluster by matchup + relative deal, excluding ordinal/seed/role.
                cluster_id = digest({"domain": "relative-deal-cluster", "version": VERSION,
                                     "deck_name": deck_name, "opponent_style": opponent_style,
                                     "relative_decks": relative})
                if cluster_id not in seen_deals:
                    seen_deals.add(cluster_id)
                    break
            else:
                raise ValueError("could not construct distinct retained relative deals")
            scenario_id = digest({"domain": "scenario-identity", "scenario": base,
                                  "relative_decks": relative,
                                  "stream_seeds": [(key, str(seed)) for key, seed in stream_seeds],
                                  "attempt": attempt})
            self.scenarios.append(Scenario(scenario_id, cluster_id, ordinal, relative,
                                            stream_seeds, attempt + 1))
        self.scenarios = tuple(self.scenarios)

    @property
    def authority(self):
        """Independent JSON value; callers cannot mutate the stored authority."""
        return json.loads(self._authority_json)

    def metadata(self):
        result = {"authority": self.authority, "authority_sha256": digest(self.authority),
                "scenarios": [{"scenario_id": s.scenario_id, "cluster_id": s.cluster_id,
                               "ordinal": s.ordinal, "relative_decks": s.relative_decks,
                               "stream_seeds": {k: str(v) for k, v in s.stream_seeds},
                               "attempts": s.attempts} for s in self.scenarios],
                "pairing": "same-relative-deal-and-streams-across-seats",
                "repeats": "same-scenario-and-cluster; determinism-only",
                "rng_algorithm": "CPython random.Random MT19937; shuffle/randbelow version pinned externally"}

        return json.loads(encode(result))
