"""Reconstruct cumulative native rich telemetry from Phase B delta responses.

The Phase B probe (``observe-rich-since`` / ``observe-atomic-levels`` with
cursors) transmits, for each of the seven cumulative hook-telemetry rings, only
the events at or after the caller's acknowledged sequence. It marks each such
envelope with ``deltaSinceSequence`` and ``deltaTransmitFromSequence``
immediately before ``events``. Without cursors the probe answers exactly as the
pinned probe does.

``NativeRichTraceAccumulator.apply`` rebuilds the envelope the full (cursor-free)
command would have returned for the same frame: the two delta keys are removed,
``transmitFromSequence`` (where the ring has one) is restored to
``oldestRetainedSequence``, and ``events`` becomes the retained held events plus
the transmitted ones. Key order, values and event objects are identical, so the
rebuilt rich dict serializes to the same bytes as the full response parsed by
``json.loads``. This rests on three probe properties, each checked where it can
be: ring sequences are process-global and never reset; a published event's JSON
is a pure function of its immutable ring record; a full response always carries
exactly the sequences ``range(oldestRetainedSequence, nextSequence)``.

Any inconsistency (a sequence gap, a cursor the probe did not echo, a transmit
start that differs from the rule, an epoch change without a full retransmit, a
sequence regression) raises ``RichTraceDeltaError`` and invalidates the
accumulator. There is no fallback that could silently drop or duplicate events.
"""

from __future__ import annotations

import json
from typing import Any

TRACE_ORDER = (
    "combatEvents",
    "phaseRuntime",
    "specialMovementRuntime",
    "actionMovementRuntime",
    "characterStateRuntime",
    "visibilityRuntime",
    "remainingRuntime",
)
# Rings whose envelopes carry transmitFromSequence (the generic EpochRing
# envelopes of the other three do not).
TRANSMIT_FIELD_TRACES = frozenset(
    {"combatEvents", "phaseRuntime", "visibilityRuntime", "remainingRuntime"}
)
DELTA_KEYS = ("deltaSinceSequence", "deltaTransmitFromSequence")
RICH_SCHEMA = "native-rich-telemetry.v3"
RICH_SINCE_COMMAND = "observe-rich-since"
ATOMIC_LEVELS_COMMAND = "observe-atomic-levels"


class RichTraceDeltaError(ValueError):
    """A delta response cannot be reconstructed into the cumulative envelope."""


def _json_bytes(value: Any) -> bytes:
    # Same encoding as native_frame_storage._json_bytes.
    return json.dumps(
        value, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _uint(value) -> bool:
    return type(value) is int and value >= 0


class _Channel:
    __slots__ = ("event_bytes", "events", "identity", "next")

    def __init__(self):
        self.identity = None
        self.events: list = []
        self.event_bytes: list[bytes] = []
        self.next = 0


class NativeRichTraceAccumulator:
    """Per-branch cumulative trace state for one probe telemetry epoch stream.

    Create one per branch (or per verified session). ``command()`` returns the
    probe command carrying the current cursors; pass the response's rich
    object to ``apply()``. The first command carries zero cursors, which the
    probe answers with a full retransmit.
    """

    def __init__(self):
        self._channels = {field: _Channel() for field in TRACE_ORDER}
        self._state = "open"
        self._failure = None
        self.frames = 0
        self.transmitted_events = 0
        self.reconstructed_events = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def receipt(self) -> dict:
        return {
            "schema": "native-rich-trace-delta.v1",
            "status": self._state,
            "failure": self._failure,
            "frames": self.frames,
            "transmitted_events": self.transmitted_events,
            "reconstructed_events": self.reconstructed_events,
            "cursors": self.cursors(),
        }

    def cursors(self) -> list[int]:
        return [self._channels[field].next for field in TRACE_ORDER]

    def command(self, base: str = RICH_SINCE_COMMAND) -> str:
        if base not in (RICH_SINCE_COMMAND, ATOMIC_LEVELS_COMMAND):
            raise ValueError("unknown delta command")
        if self._state != "open":
            raise RichTraceDeltaError("rich trace accumulator was invalidated")
        return base + " " + " ".join(str(c) for c in self.cursors())

    def _fail(self, message: str):
        self._state = "failed"
        self._failure = message
        raise RichTraceDeltaError(message)

    def apply(self, rich: dict) -> dict:
        """Validate one delta rich response; return the reconstructed full one."""
        if self._state != "open":
            raise RichTraceDeltaError("rich trace accumulator was invalidated")
        try:
            return self._apply(rich)
        except RichTraceDeltaError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            self._fail(f"malformed rich delta response: {type(error).__name__}: {error}")

    def _apply(self, rich: dict) -> dict:
        if (
            not isinstance(rich, dict)
            or rich.get("ok") is not True
            or rich.get("schema") != RICH_SCHEMA
        ):
            self._fail("rich delta response is not a successful native-rich-telemetry.v3 object")
        updates = {}
        rebuilt_envelopes = {}
        for field in TRACE_ORDER:
            envelope = rich.get(field)
            if not isinstance(envelope, dict) or not isinstance(envelope.get("events"), list):
                self._fail(f"{field}: missing trace envelope")
            channel = self._channels[field]
            since, transmit = (envelope.get(key) for key in DELTA_KEYS)
            if not _uint(since) or not _uint(transmit):
                self._fail(f"{field}: response is not a delta envelope")
            if since != channel.next:
                self._fail(f"{field}: probe cursor {since} differs from acknowledged {channel.next}")
            keys = list(envelope)
            events_at = keys.index("events")
            if keys[events_at - 2 : events_at] != list(DELTA_KEYS):
                self._fail(f"{field}: delta keys are not immediately before events")
            first = envelope.get("epochFirstSequence")
            oldest = envelope.get("oldestRetainedSequence")
            upcoming = envelope.get("nextSequence")
            generation, epoch = envelope.get("generation"), envelope.get("stateEpoch")
            if not all(_uint(v) for v in (first, oldest, upcoming, generation, epoch)):
                self._fail(f"{field}: invalid sequence bounds")
            if not first <= oldest <= upcoming:
                self._fail(f"{field}: inconsistent sequence bounds")
            if since > upcoming:
                self._fail(f"{field}: sequence regression (cursor {since} beyond next {upcoming})")
            expected_from = since if oldest <= since <= upcoming else oldest
            if transmit != expected_from:
                self._fail(f"{field}: transmit start {transmit} differs from rule {expected_from}")
            if field in TRANSMIT_FIELD_TRACES:
                if envelope.get("transmitFromSequence") != expected_from:
                    self._fail(f"{field}: transmitFromSequence differs from delta start")
            elif "transmitFromSequence" in envelope:
                self._fail(f"{field}: unexpected transmitFromSequence")
            identity = (generation, epoch, first)
            if channel.identity != identity and expected_from != oldest:
                self._fail(f"{field}: telemetry epoch changed without a full retransmit")
            new_events = envelope["events"]
            if len(new_events) != upcoming - expected_from:
                self._fail(
                    f"{field}: sequence gap ({len(new_events)} events for "
                    f"[{expected_from}, {upcoming}))"
                )
            for offset, event in enumerate(new_events):
                if not isinstance(event, dict) or event.get("sequence") != expected_from + offset:
                    self._fail(f"{field}: event sequence gap or reorder at {expected_from + offset}")
            # Retained events the probe did not retransmit: [oldest, expected_from).
            # An empty range (full retransmit, including after more than a
            # ring's capacity of new events) needs no held events.
            if expected_from == oldest:
                held, held_bytes = [], []
            elif channel.identity == identity and channel.events:
                held_first = channel.events[0]["sequence"]
                start, end = oldest - held_first, expected_from - held_first
                if start < 0 or end > len(channel.events):
                    self._fail(f"{field}: held events do not cover [{oldest}, {expected_from})")
                held = channel.events[start:end]
                held_bytes = channel.event_bytes[start:end]
            else:
                self._fail(f"{field}: held events do not cover [{oldest}, {expected_from})")
            if len(held) != expected_from - oldest or (
                held and held[0]["sequence"] != oldest
            ):
                self._fail(f"{field}: held events do not cover [{oldest}, {expected_from})")
            events = held + new_events
            event_bytes = held_bytes + [_json_bytes(event) for event in new_events]
            rebuilt = {}
            for key, value in envelope.items():
                if key in DELTA_KEYS:
                    continue
                if key == "transmitFromSequence":
                    value = oldest
                elif key == "events":
                    value = events
                rebuilt[key] = value
            rebuilt_envelopes[field] = rebuilt
            updates[field] = (identity, events, event_bytes, upcoming, len(new_events))
        for key, value in rich.items():
            if key not in rebuilt_envelopes and isinstance(value, dict) and any(
                k in value for k in DELTA_KEYS
            ):
                self._fail(f"{key}: unexpected delta keys outside the declared traces")
        # Commit only after every channel validated.
        for field, (identity, events, event_bytes, upcoming, transmitted) in updates.items():
            channel = self._channels[field]
            channel.identity, channel.events, channel.event_bytes, channel.next = (
                identity, events, event_bytes, upcoming)
            self.transmitted_events += transmitted
            self.reconstructed_events += len(events)
        self.frames += 1
        return {key: rebuilt_envelopes.get(key, value) for key, value in rich.items()}

    def event_cache(self, rich: dict) -> dict:
        """Serialized-event cache for ``compact_native_frame`` on ``rich``.

        Valid only for the rich dict most recently returned by ``apply``; each
        entry is checked against that dict's event list identity.
        """
        cache = {}
        for field in TRACE_ORDER:
            channel = self._channels[field]
            if rich.get(field, {}).get("events") is not channel.events:
                raise RichTraceDeltaError("event cache requested for a different rich frame")
            # compact_native_frame recomputes every digest from these bytes.
            cache[field] = {"events": channel.events, "event_bytes": channel.event_bytes}
        return cache
