"""Lossless uint8 block cache. Contains no truth or heldout admission path.

Model-resolution BGR arena/HUD plus sanitized source pixels preserve pre-resize
JPEG augmentation exactly. Zstd-compressed XOR blocks are random-access shards;
no video decoding is performed by the reader. Completed match dirs are immutable.
"""
import ctypes
import ctypes.util
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import numpy as np

ARENA = (832,448,3)
HUD = (64,448,3)
RAW = (1140,540,3)
PIXEL_BYTES = int(np.prod(ARENA)+np.prod(HUD))
SCHEMA = 'clasher.v4.lossless-pixels.v1'


@lru_cache(maxsize=1)
def library():
    z=ctypes.CDLL(ctypes.util.find_library('zstd') or 'libzstd.so.1')
    for name, args in {
        'ZSTD_compressBound':[ctypes.c_size_t],
        'ZSTD_compress':[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int],
        'ZSTD_decompress':[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t],
        'ZSTD_isError':[ctypes.c_size_t],
    }.items():
        fn=getattr(z,name);fn.argtypes=args;fn.restype=ctypes.c_size_t
    return z


def compress(array):
    z=library();n=array.nbytes;bound=z.ZSTD_compressBound(n);dst=ctypes.create_string_buffer(bound)
    size=z.ZSTD_compress(dst,bound,array.ctypes.data,n,3)
    if z.ZSTD_isError(size):raise ValueError('Zstd compression failure')
    return dst.raw[:size]


def decompress(blob,shape):
    z=library();dst=np.empty(shape,np.uint8)
    size=z.ZSTD_decompress(dst.ctypes.data,dst.nbytes,blob,len(blob))
    if z.ZSTD_isError(size) or size!=dst.nbytes:raise ValueError('Corrupt Zstd cache block')
    # Axis-0 accumulate has poor cache locality for megapixel frames.
    for i in range(1,len(dst)):np.bitwise_xor(dst[i],dst[i-1],out=dst[i])
    return dst


def encode(frames):
    x=np.stack(frames)
    x[1:]=np.bitwise_xor(x[1:],x[:-1])
    return compress(x)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()


class PixelCache:
    def __init__(self,root,receipts,verify=True):
        self.root=Path(root);self.index={};self.files={}
        for r in receipts:
            if r['split'] not in ('train','validation'):raise ValueError('Heldout cache forbidden')
            folder=self.root/r['episode'];idx=json.loads((folder/'index.json').read_text())
            if idx['schema']!=SCHEMA or idx['video_sha256']!=r['files']['video.mp4'] or idx['frames']!=r['frames']:
                raise ValueError('Cache identity mismatch')
            if idx['receipt_sha256']!=r['receipt_sha256']:raise ValueError('Cache receipt mismatch')
            if not idx['equality']['pass'] or idx['equality']['checked']<int(np.ceil(.01*r['frames'])):
                raise ValueError('Cache equality check missing')
            if idx['opencv']!=__import__('cv2').__version__:raise ValueError('OpenCV cache ABI mismatch')
            for name,digest in idx['sha256'].items():
                if verify and sha(folder/name)!=digest:raise ValueError('Cache SHA256 mismatch')
                self.files[r['episode'],name]=folder/name
            self.index[r['episode']]=idx

    def get(self,episode,indices,raw=False):
        idx=self.index[episode];name='raw.zst' if raw else 'pixels.zst';width=int(np.prod(RAW)) if raw else PIXEL_BYTES
        blocks={};out=[]
        for i in indices:
            if not 0<=i<idx['frames']:raise IndexError(i)
            key=i//idx['block_size']
            if key not in blocks:
                block=idx['blocks'][key];offset,size=block[name]
                with self.files[episode,name].open('rb') as f:
                    f.seek(offset);blob=f.read(size)
                blocks[key]=decompress(blob,(block['count'],width))
            row=blocks[key][i%idx['block_size']]
            if raw:out.append(row.reshape(RAW).copy())
            else:out.append((row[:int(np.prod(ARENA))].reshape(ARENA).copy(),row[int(np.prod(ARENA)):].reshape(HUD).copy()))
        return out
