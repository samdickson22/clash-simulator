"""Coordinator-approved derived-cache boundaries (2026-10-08 07:22 UTC)."""
from pathlib import Path
import shutil
import socket

MAX_BYTES = 300_000_000_000
MIN_FREE_BYTES = 200_000_000_000
HOME_HOSTS = {'127x01', '127x03', '127x04', '127x08'}
LEASE_HOSTS = {'127x11', '127x13', '127x14', '127x16', '127x18'}


def approved_root(host=None):
    host = host or socket.gethostname().split('.')[0]
    if host in HOME_HOSTS:
        return Path('/mpac/sdicks02/repos/clasher-v4-cache')
    if host in LEASE_HOSTS:
        return Path('/mpac/sdicks02/repos/clasher-lease/data/v4-cache')
    raise ValueError('Host not approved for derived caches')


def validate_root(path):
    root = approved_root()
    if Path(path).resolve() != root:
        raise ValueError(f'Use approved derived-cache root: {root}')
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < MIN_FREE_BYTES:
        raise RuntimeError('Less than 200 GB free on /mpac')
    return root


def used_bytes(root):
    # Includes partial/retained attempts, metadata and nested legacy caches.
    return sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())


def require_growth(root, growth, *, budget=MAX_BYTES):
    if not 0 < budget <= MAX_BYTES or growth < 0:
        raise ValueError('Invalid derived-cache budget')
    if used_bytes(root) + growth > budget:
        raise RuntimeError('Derived-cache host budget would be exceeded')
    if shutil.disk_usage(root).free - growth < MIN_FREE_BYTES:
        raise RuntimeError('Derived-cache growth would cross 200 GB free-space floor')
