"""P1: recorded train pixels or a directly consumed emulator screenshot RPC."""
import hashlib
import json
from pathlib import Path
import time
from .contracts import Frame


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def admit_replay(match, split_path):
    """Supervisor-only admission. Read no labels; discard all hidden metadata.

    The split is checked BEFORE opening media. Only public timing fields leave
    this function. Own deck is declared pre-match information, never opponent's.
    """
    match = Path(match)
    receipt = json.loads((match/'receipt.json').read_text())
    members = {r['seed']: r for r in json.loads(Path(split_path).read_text())['matches']}
    member = members.get(receipt['seed'])
    if receipt.get('split') != 'train' or not member or member['split'] != 'train':
        raise ValueError('Runtime development replays require frozen train membership')
    if member['decks'] != receipt['decks']:
        raise ValueError('Receipt disagrees with frozen registration')
    hashes = {name: sha256(match/name) for name in ('video.mp4', 'frames.jsonl')}
    if any(receipt['files'][name] != value for name, value in hashes.items()):
        raise ValueError('Replay media/timing checksum mismatch')
    rows = []
    with (match/'frames.jsonl').open() as stream:
        for line in stream:
            row = json.loads(line)
            rows.append({k: row[k] for k in ('seq', 'produced_mono', 'received_at', 'media_pts')})
    if any(b['seq'] != a['seq']+1 or b['produced_mono'] <= a['produced_mono']
           for a, b in zip(rows, rows[1:])):
        raise ValueError('Noncausal or incomplete replay timing')
    return dict(episode=receipt['episode'], video=str(match/'video.mp4'), rows=rows,
                own_deck=member['decks'][1], render_backend=receipt['render_backend'],
                split='train', split_sha256=sha256(split_path), hashes=hashes)


def sanitize(image):
    import cv2
    from clasher.vision.l1 import public_pixels
    if image.shape == (1140, 540, 3):
        import numpy as np
        from clasher.vision.l1 import ARENA, CLOCK, OWN_HUD
        # Phase A video is already sanitized/downscaled. Reapply the same
        # allowlist without an unnecessary 2x upsample/downsample round trip.
        safe = np.zeros_like(image)
        for x1, y1, x2, y2 in (ARENA, CLOCK, OWN_HUD):
            safe[y1:y2, x1:x2] = image[y1:y2, x1:x2]
        return safe
    if image.shape != (2280, 1080, 3):
        raise ValueError('Unexpected replay/screenshot geometry')
    return public_pixels(image)


def replay_frames(source, stop, log, limit=0):
    import cv2
    cv2.setNumThreads(1)
    video = cv2.VideoCapture(source['video'])
    video.set(cv2.CAP_PROP_N_THREADS, 1) if hasattr(cv2, 'CAP_PROP_N_THREADS') else None
    origin = time.monotonic()+.1
    rows = source['rows'][:limit or None]
    first = rows[0]['produced_mono']
    try:
        for row in rows:
            produced = origin+row['produced_mono']-first
            delivery = max(0., row['received_at']-row['produced_mono'])
            if stop.wait(max(0., produced+delivery-time.monotonic())):
                break
            received = time.monotonic()
            start = time.monotonic()
            ok, image = video.read()
            if not ok:
                raise ValueError('Video ended before its frame ledger')
            pixels = sanitize(image)
            now = time.monotonic()
            log('capture', (received-produced)*1000, sequence=row['seq'])
            log('decode', (now-start)*1000, sequence=row['seq'])
            yield Frame(source['episode'], row['seq'], produced, received,
                        (row['produced_mono']-first)*1000, pixels)
    finally:
        video.release()


def grpc_frames(config, stop, log):
    """Consume RPC directly: existing latest-only ScreenStream would lose frames.

    Connects to an already owned emulator; never launches one or changes its
    network settings. Unix production epoch is anchored to host monotonic time.
    """
    import cv2
    import grpc
    import numpy as np
    from .loading import module
    pb = module('clasher_live_capture_pb', Path(config['proto_dir'])/'emulator_controller_pb2.py')
    settings = dict(line.strip().split('=', 1) for line in Path(config['discovery']).read_text().splitlines()
                    if '=' in line and not line.lstrip().startswith('#'))
    if int(settings['grpc.port']) != config['port'] or not settings.get('grpc.token'):
        raise ValueError('Emulator ownership discovery mismatch')
    channel = grpc.insecure_channel(f"127.0.0.1:{config['port']}",
                                   options=[('grpc.max_receive_message_length', 16*1024*1024)])
    call = channel.unary_stream('/android.emulation.control.EmulatorController/streamScreenshot',
                                request_serializer=pb.ImageFormat.SerializeToString,
                                response_deserializer=pb.Image.FromString)
    rpc = call(pb.ImageFormat(format=pb.ImageFormat.RGB888, width=1080, height=2280),
               metadata=(('authorization', 'Bearer '+settings['grpc.token']),))
    offset = time.monotonic()-time.time()
    first = None
    sequence = 0
    next_due = None
    fps = config.get('capture_fps', 20)
    if not 20 <= fps <= 30:
        rpc.cancel()
        channel.close()
        raise ValueError('Live capture target must be 20..30 FPS')
    try:
        for message in rpc:
            if stop.is_set():
                break
            received = time.monotonic()
            produced = message.timestampUs/1e6+offset
            if not 0 <= received-produced <= 10:
                raise ValueError('gRPC production timestamp is not a current epoch timestamp')
            if next_due is not None and produced < next_due:
                continue
            if next_due is None or produced-next_due > 1/fps:
                next_due = produced+1/fps
            else:
                next_due += 1/fps
            seq = sequence
            sequence += 1
            if (message.format.width, message.format.height) != (1080, 2280):
                raise ValueError('Unexpected screenshot dimensions')
            first = produced if first is None else first
            start = time.monotonic()
            rgb = np.frombuffer(message.image, np.uint8).reshape(2280, 1080, 3)
            pixels = sanitize(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
            log('capture', (received-produced)*1000, sequence=seq)
            log('decode', (time.monotonic()-start)*1000, sequence=seq)
            yield Frame(config['episode'], seq, produced, received, (produced-first)*1000, pixels)
    finally:
        rpc.cancel()
        channel.close()
