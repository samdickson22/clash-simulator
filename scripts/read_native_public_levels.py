"""Read public level-label values from the pinned, paused offline reference."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

from smoke_reference_battle import request

EXPECTED = {
    'libg_sha256': '110aa2b5cac391c498645e072b0d88729428c2c2845e7e2737ca8ee979059783',
    'probe_sha256': '2ea5e10dff5cfe763218d07ec17acdb4be1379eac51d6b4f827d887edc3c645c',
    'content_fingerprint_sha256': 'e0cb2fb9eb2fdd0df1afcb00df3e3ba61cf25aa8b24e39c17cc391d952a4e339',
}


def read_levels(adb: Path, *, port=26789, serial='emulator-5580', batched=False):
    attestation = request(port, 'attest')['attestation']
    if any(attestation.get(k) != v for k, v in EXPECTED.items()):
        raise ValueError('unverified native build')
    status = request(port, 'status')
    if not status['paused'] or not status['ready']:
        raise ValueError('reference must be ready and paused')
    before = request(port, 'observe')
    if before['truncated'] or before['returned'] != before['count']:
        raise ValueError('incomplete ordinary snapshot')
    pid = int(subprocess.check_output([str(adb), '-s', serial, 'shell', 'pidof', 'nullsroyale.rel.free']))
    recoveries = []

    def memory(address, size):
        if not 0 < address < 1 << 56 or not 0 < size <= 4096:
            raise ValueError('invalid bounded memory request')
        data = subprocess.check_output([str(adb), '-s', serial, 'exec-out',
            f'dd if=/proc/{pid}/mem bs=1 skip={address} count={size} 2>/dev/null'])
        if len(data) < size:
            # Retry the identical bounded read once, only in the same paused
            # process/frame. Discard the partial bytes rather than combining
            # responses or replaying the match to obtain replacement evidence.
            current = request(port, 'status')
            if (
                not current['paused'] or not current['ready']
                or current['manager'] != status['manager']
                or request(port, 'observe') != before
                or int(subprocess.check_output([
                    str(adb), '-s', serial, 'shell', 'pidof', 'nullsroyale.rel.free',
                ])) != pid
            ):
                raise ValueError('native frame or process changed after short memory read')
            received = len(data)
            data = subprocess.check_output([str(adb), '-s', serial, 'exec-out',
                f'dd if=/proc/{pid}/mem bs=1 skip={address} count={size} 2>/dev/null'])
            if len(data) == size:
                recoveries.append({
                    'kind': 'short-single-retry', 'address': hex(address),
                    'expected_bytes': size, 'received_bytes': received,
                })
        if len(data) != size:
            raise ValueError(
                f'invalid native memory read length: address={address:#x}, '
                f'expected={size}, actual={len(data)}'
            )
        return data

    def memory_many(ranges):
        if len(ranges) > 128 or sum(size for _, size in ranges) > 65536:
            raise ValueError('oversized native memory batch')
        for address, size in ranges:
            if not 0 < address < 1 << 56 or not 0 < size <= 4096 or address + size > 1 << 56:
                raise ValueError('invalid bounded memory request')
        if not ranges:
            return []
        if not batched:
            return [memory(address, size) for address, size in ranges]
        # Only validated integer addresses and byte counts enter this script.
        commands = [f'dd if=/proc/{pid}/mem bs=1 skip={address} count={size} 2>/dev/null'
                    for address, size in ranges]
        data = subprocess.check_output([str(adb), '-s', serial, 'exec-out', '\n'.join(commands)])
        expected_size = sum(size for _, size in ranges)
        if len(data) != expected_size:
            if len(data) > expected_size:
                raise ValueError(
                    f'oversized native memory response: expected={expected_size}, actual={len(data)}'
                )
            # Recover only transport truncation within the same paused frame.
            # Discard the entire batch; never splice partial and retried bytes.
            if request(port, 'observe') != before:
                raise ValueError('native frame changed after short memory batch')
            chunks = [memory(address, size) for address, size in ranges]
            recoveries.append({
                'kind': 'short-batch-serial-fallback',
                'ranges': len(ranges), 'expected_bytes': expected_size,
                'received_bytes': len(data),
            })
            return chunks
        chunks, offset = [], 0
        for _, size in ranges:
            chunks.append(data[offset:offset + size])
            offset += size
        return chunks

    def pointer(address):
        return struct.unpack('<Q', memory(address, 8))[0]

    manager = int(status['manager'], 16)
    world = pointer(manager + 0xa8)
    king = pointer(world + 0xe0)
    object_manager = pointer(king + 0x10)
    vector = pointer(object_manager + 8)
    capacity, count = struct.unpack('<ii', memory(object_manager + 0x10, 8))
    if not 0 < count <= min(capacity, 128) or count != before['count']:
        raise ValueError('invalid native object vector')
    pointers = struct.unpack(f'<{count}Q', memory(vector, count * 8))
    expected = {o['nativeObjectId']: o for o in before['objects']}
    if len(expected) != count:
        raise ValueError('duplicate ordinary object ID')
    seen, levels, bodies = set(), {}, []
    headers = memory_many([(address, 0xb0) for address in pointers])
    for address, header in zip(pointers, headers, strict=True):
        identity = struct.unpack_from('<I', header, 8)[0]
        obj = expected.get(identity)
        if obj is None or identity in seen:
            raise ValueError('object identity mismatch')
        seen.add(identity)
        owner = struct.unpack_from('<i', header, 0x78)[0]
        card = struct.unpack_from('<i', header, 0xac)[0]
        if owner != obj['owner'] or card != obj['cardId']:
            raise ValueError('native body metadata mismatch')
        if obj['hp'] is None:
            continue
        # Only a validated HP component establishes a character/body layout.
        components = struct.unpack_from('<Q', header, 0x18)[0]
        component_count = struct.unpack_from('<i', header, 0x20)[0]
        if not 3 <= component_count <= 64:
            raise ValueError('missing body component inventory')
        bodies.append((address, identity, components))
    hp_components = [struct.unpack('<Q', data)[0] for data in memory_many(
        [(components + 16, 8) for _, _, components in bodies]
    )]
    backlinks = memory_many([(component + 8, 8) for component in hp_components])
    for (address, _, _), backlink in zip(bodies, backlinks, strict=True):
        if struct.unpack('<Q', backlink)[0] != address:
            raise ValueError('HP component owner backlink mismatch')
    # Read level fields only after every body layout/backlink has validated.
    values = memory_many([(address + 0x120, 4) for address, _, _ in bodies])
    for (_, identity, _), raw in zip(bodies, values, strict=True):
        value = struct.unpack('<i', raw)[0] + 1
        if not 1 <= value <= 127:
            raise ValueError('native public level out of range')
        levels[identity] = value
    after = request(port, 'observe')
    final_status = request(port, 'status')
    if after != before or not final_status['paused'] or final_status['manager'] != status['manager']:
        raise ValueError('native frame changed during read')
    return {'ordinary': before, 'levels': levels, 'attestation': attestation,
            'reader_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'transport': 'batched-adb' if batched else 'serial-adb',
            'transport_recoveries': recoveries,
            'scope': 'Exact native level-label reference, not pixel OCR; no HP-derived levels.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--batched', action='store_true', help='Experimental batched transport; requires live parity validation')
    args = parser.parse_args()
    result = read_levels(args.adb, batched=args.batched)
    with args.output.open('x') as f:
        f.write(json.dumps(result, indent=2) + '\n')
    print(result['ordinary']['tick'], result['levels'])


if __name__ == '__main__':
    main()
