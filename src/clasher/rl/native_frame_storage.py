"""Compact saved native frames without changing acquired public observations.

Only named cumulative event arrays are omitted. A null events value means not
stored, never an empty event history. Native envelope metadata and every other
field remain intact. Full parsed-frame and event hashes commit the omitted data;
those hashes cannot reconstruct it and are not hashes of unavailable wire bytes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TRACE_FIELDS = frozenset({
    'combatEvents', 'phaseRuntime', 'specialMovementRuntime',
    'actionMovementRuntime', 'characterStateRuntime', 'visibilityRuntime',
    'remainingRuntime',
})
STORAGE_KEY = 'storage_provenance'
SHA_PATTERN = r'^[0-9a-f]{64}$'


class OmittedEvents(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    count: int = Field(ge=0)
    json_bytes: int = Field(ge=2)
    json_sha256: str = Field(pattern=SHA_PATTERN)


class NativeFrameStorageRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal['native-public-compact-frame.v1'] = 'native-public-compact-frame.v1'
    full_frame_digest_encoding: Literal['compact-json-insertion-order-ascii-v1'] = 'compact-json-insertion-order-ascii-v1'
    retained_frame_digest_encoding: Literal['canonical-json-string-keys-ascii-v1'] = 'canonical-json-string-keys-ascii-v1'
    full_frame_json_sha256: str = Field(pattern=SHA_PATTERN)
    full_frame_json_bytes: int = Field(gt=0)
    retained_frame_json_sha256: str = Field(pattern=SHA_PATTERN)
    retained_frame_json_bytes: int = Field(gt=0)
    producer_source_sha256: str = Field(pattern=SHA_PATTERN)
    omitted_events: dict[str, OmittedEvents]
    native_wire_byte_digest_available: Literal[False] = False
    omitted_payload_recoverable_from_record: Literal[False] = False
    native_complete_flags_describe_source: Literal[True] = True


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def _canonical_bytes(value: Any) -> bytes:
    # Live level maps have integer keys; JSON-loaded maps have string keys.
    # Normalize through the JSON representation before canonical key sorting.
    normalized = json.loads(_json_bytes(value))
    return json.dumps(normalized, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_native_frame_storage(frame: dict) -> NativeFrameStorageRecord | None:
    """Validate a compact record; legacy full frames need no storage envelope."""
    if STORAGE_KEY not in frame:
        return None
    record = NativeFrameStorageRecord.model_validate(frame[STORAGE_KEY])
    payload = {key: value for key, value in frame.items() if key != STORAGE_KEY}
    if not isinstance(payload.get('rich'), dict) or payload['rich'].get('schema') != 'native-rich-telemetry.v3':
        raise ValueError('compact frame has an unsupported rich schema')
    if not set(record.omitted_events) <= TRACE_FIELDS:
        raise ValueError('compact frame omits an undeclared native trace')
    for field in record.omitted_events:
        envelope = payload['rich'].get(field)
        if not isinstance(envelope, dict) or 'events' not in envelope or envelope['events'] is not None:
            raise ValueError('omitted native events must remain explicitly unknown')
    retained = _canonical_bytes(payload)
    if len(retained) != record.retained_frame_json_bytes or _sha(retained) != record.retained_frame_json_sha256:
        raise ValueError('compact native frame retained payload checksum mismatch')
    return record


def _cached_events(event_cache, field, events):
    """Return a validated cache entry for exactly this events list, or None."""
    if event_cache is None or field not in event_cache:
        return None
    entry = event_cache[field]
    if (not isinstance(entry, dict) or entry.get('events') is not events
            or not isinstance(entry.get('event_bytes'), list)
            or len(entry['event_bytes']) != len(events)):
        raise ValueError('native event cache does not describe this frame')
    return entry


def _events_json_size(event_bytes: list[bytes]) -> int:
    # json.dumps(list, separators=(',', ':')) == b'[' + b','.join(items) + b']'.
    return 2 + sum(len(piece) for piece in event_bytes) + max(0, len(event_bytes) - 1)


def _full_frame_digest_cached(frame: dict, cached: dict) -> tuple[str, int, dict[str, str]]:
    """SHA-256 and size of ``_json_bytes(frame)`` without re-encoding cached events.

    Each cached events list is replaced by a unique sentinel string, the rest
    of the frame is encoded once, and the digest streams the pieces with the
    cached event encodings spliced back at each sentinel. Encoding a list with
    compact separators is ``[`` + ``,``.join(item encodings) + ``]``, so the
    streamed bytes equal the full encoding exactly. Each events list digest
    is recomputed from the same bytes; a cache-supplied digest must match it.
    """
    nonce = uuid.uuid4().hex
    sentinels = {field: f'\x00clasher-events-{nonce}-{field}\x00' for field in cached}
    rich = frame['rich']
    shallow = {**frame, 'rich': {
        key: ({**value, 'events': sentinels[key]} if key in cached else value)
        for key, value in rich.items()
    }}
    skeleton = _json_bytes(shallow)
    digest = hashlib.sha256()
    event_digests = {}
    size = 0
    cursor = 0
    # Splice in document order; every sentinel must occur exactly once.
    markers = sorted(
        ((skeleton.find(_json_bytes(sentinel)), field) for field, sentinel in sentinels.items()),
    )
    for position, field in markers:
        encoded = _json_bytes(sentinels[field])
        if position < cursor or skeleton.count(encoded) != 1:
            raise ValueError('native event cache sentinel is not unique in the frame encoding')
        head = skeleton[cursor:position]
        digest.update(head)
        size += len(head)
        pieces = cached[field]['event_bytes']
        if not all(type(piece) is bytes for piece in pieces):
            raise ValueError('native event cache holds a non-bytes encoding')
        joined = b','.join(pieces)
        events_digest = hashlib.sha256()
        for target in (digest, events_digest):
            target.update(b'[')
            target.update(joined)
            target.update(b']')
        event_digests[field] = events_digest.hexdigest()
        supplied = cached[field].get('json_sha256')
        if supplied is not None and supplied != event_digests[field]:
            raise ValueError('native event cache digest differs from its encodings')
        size += len(joined) + 2
        cursor = position + len(encoded)
    tail = skeleton[cursor:]
    digest.update(tail)
    size += len(tail)
    return digest.hexdigest(), size, event_digests


def compact_native_frame(frame: dict, *, event_cache: dict | None = None) -> dict:
    """Own a compact storage copy; leave the full in-memory native frame intact.

    ``event_cache`` (optional, e.g. from ``NativeRichTraceAccumulator.event_cache``)
    maps trace fields to ``{'events': <the frame's own list>, 'event_bytes':
    [compact JSON of each event], optional 'json_sha256': <digest of the list
    encoding>}``; each encoding must equal ``_json_bytes(event)``.
    It only avoids re-encoding events; the returned record is identical to the
    uncached result, which remains the default.
    """
    if STORAGE_KEY in frame:
        validate_native_frame_storage(frame)
        return copy.deepcopy(frame)
    rich = frame.get('rich')
    if not isinstance(rich, dict) or rich.get('schema') != 'native-rich-telemetry.v3':
        raise ValueError('cannot compact an unsupported native rich schema')
    if not isinstance(frame.get('ordinary'), dict) or not isinstance(frame.get('level_source'), dict):
        raise ValueError('compact native frame requires ordinary and level source records')
    cached = {}
    for field, value in rich.items():
        if field in TRACE_FIELDS and isinstance(value, dict) and isinstance(value.get('events'), list):
            entry = _cached_events(event_cache, field, value['events'])
            if entry is not None:
                cached[field] = entry
    event_digests = {}
    if cached:
        raw_sha, raw_size, event_digests = _full_frame_digest_cached(frame, cached)
    else:
        raw = _json_bytes(frame)
        raw_sha, raw_size = _sha(raw), len(raw)
        del raw
    retained_rich = {}
    omitted = {}
    for field, value in rich.items():
        if field in TRACE_FIELDS and isinstance(value, dict) and isinstance(value.get('events'), list):
            if field in cached:
                entry = cached[field]
                omitted[field] = OmittedEvents(count=len(value['events']),
                                               json_bytes=_events_json_size(entry['event_bytes']),
                                               json_sha256=event_digests[field])
            else:
                event_bytes = _json_bytes(value['events'])
                omitted[field] = OmittedEvents(count=len(value['events']), json_bytes=len(event_bytes),
                                               json_sha256=_sha(event_bytes))
            retained_rich[field] = {**value, 'events': None}
        else:
            # Keep unknown channels and all object-level runtime fields.
            retained_rich[field] = value
    payload = copy.deepcopy({**frame, 'rich': retained_rich})
    retained = _canonical_bytes(payload)
    record = NativeFrameStorageRecord(
        full_frame_json_sha256=raw_sha, full_frame_json_bytes=raw_size,
        retained_frame_json_sha256=_sha(retained), retained_frame_json_bytes=len(retained),
        producer_source_sha256=_sha(Path(__file__).read_bytes()), omitted_events=omitted,
    )
    payload[STORAGE_KEY] = record.model_dump(mode='json')
    return payload
