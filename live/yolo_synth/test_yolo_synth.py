"""Tests for the YOLO synthetic-frame compositor (tiny synthetic bank; no scratch data needed).

  python -m pytest live/yolo_synth/test_yolo_synth.py -q      (or: python live/yolo_synth/test_yolo_synth.py)
"""
import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compose as C  # noqa: E402
import geometry as G  # noqa: E402

CLASSES = HERE/'classes.json'


def _names():
    return {x['name']: x for x in json.loads(CLASSES.read_text())['names']}


def _sprite(path, w, h, bgr):
    im = np.zeros((h, w, 4), np.uint8)
    im[..., :3] = bgr
    im[..., 3] = 255
    cv2.imwrite(str(path), im)


def make_bank(root):
    root = Path(root)
    (root/'bgs').mkdir(parents=True)
    (root/'sprites').mkdir()
    cv2.imwrite(str(root/'bgs/kcr-a.png'), np.full((G.H, G.W, 3), 90, np.uint8))
    bgs = [dict(id='kcr-a', file='kcr-a.png', kind='katacr', arena='katacr', towers=[])]
    (root/'bgs.json').write_text(json.dumps(bgs))
    rows = []
    for name, belong, w, h, col in (('knight', 1, 30, 40, (0, 0, 220)), ('minion', 0, 26, 30, (220, 0, 0)),
                                     ('king-tower', 0, 80, 90, (50, 50, 50)), ('king-tower', 1, 80, 90, (60, 60, 60)),
                                     ('queen-tower', 0, 60, 70, (70, 70, 70)), ('queen-tower', 1, 60, 70, (80, 80, 80)),
                                     ('bar', 0, 36, 8, (255, 200, 0)), ('bar', 1, 36, 8, (0, 0, 255)),
                                     ('bar-level', 0, 12, 12, (255, 255, 0)), ('bar-level', 1, 12, 12, (0, 0, 200))):
        f = f'sprites/{name}_{belong}_{len(rows)}.png'
        _sprite(root/f, w, h, col)
        rows.append(dict(file=f, name=name, belong=belong, src='test', scale=1.0))
    (root/'sprites.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return C.Bank(root, CLASSES)


def test_crop_maps_tile_grid_onto_katacr_grid():
    # r3 crop box: tile (0,0) and (18,32) of live/loop/canvas.py land on KataCR xyxy_grids (6,64)-(562,864)
    S, T = 1.806, (51.5, -275.5)
    TA, TB, TC, TD = 28.545, 12.09, 22.895, 237.18
    x0, y0, x1, y1 = G.CROP_720
    for tx, ty, ex, ey in ((0, 0, 6, 64), (18, 32, 562, 864)):
        ax, ay = (S*(TB+TA*tx)+T[0])*720/1080, (S*(TD+TC*ty)+T[1])*1280/1920
        cx, cy = (ax-x0)*G.W/(x1-x0), (ay-y0)*G.H/(y1-y0)
        assert abs(cx-ex) < 1.5 and abs(cy-ey) < 1.5, (tx, ty, cx, cy)


def test_classes_json_ids_and_names():
    doc = json.loads(CLASSES.read_text())
    names = doc['names']
    assert [x['idx'] for x in names] == list(range(len(names)))
    assert names[0]['name'] == 'king-tower' and names[155]['name'] == 'unknown'
    by = {x['name']: x for x in names}
    for n in ('spear-goblin', 'tombstone', 'bomber', 'goblin-cage', 'goblin-brawler', 'skeleton'):
        assert by[n]['labelled']
    for n in ('bar', 'bar-level', 'clock', 'elixir', 'emote', 'text', 'tower-bar'):
        assert not by[n]['labelled']
    assert all(c['id'] == 2*by[c['name']]['idx']+c['team'] for c in doc['classes'])


def test_yolo_lines_format():
    s = C.yolo_lines([(25, 1, 10, 20, 40, 60)])
    idx, cx, cy, w, h, b = s.split()
    assert idx == '25' and b == '1'
    assert abs(float(cx)*G.W-25) < 1e-3 and abs(float(cy)*G.H-40) < 1e-3
    assert abs(float(w)*G.W-30) < 1e-3 and abs(float(h)*G.H-40) < 1e-3


def test_team_swap_red_blue():
    im = np.zeros((2, 2, 4), np.uint8); im[..., 3] = 255
    im[0, 0, :3] = (0, 0, 230)      # red (BGR)
    im[0, 1, :3] = (230, 0, 0)      # blue
    im[1, 0, :3] = (40, 160, 40)    # green: untouched
    out = C.team_swap(im)
    assert out[0, 0, 0] > 150 and out[0, 0, 2] < 80        # red -> blue
    assert out[0, 1, 2] > 150 and out[0, 1, 0] < 80        # blue -> red
    assert np.abs(out[1, 0, :3].astype(int)-im[1, 0, :3]).max() < 8


def test_frames_deterministic_and_labels_consistent():
    names = _names()
    with tempfile.TemporaryDirectory() as d:
        bank = make_bank(d)
        comp = C.Composer(bank, dict(p_official=0, n_units=((1., 10, 20),), p_damaged=1.0, p_dim=0, p_noise=0, p_items=0))
        a = comp.frame(np.random.default_rng(7))
        b = comp.frame(np.random.default_rng(7))
        assert np.array_equal(a[0], b[0]) and a[1] == b[1]
        img, labels, meta = a
        assert img.shape == (G.H, G.W, 3) and img.dtype == np.uint8
        assert len(labels) == len(meta['units']) > 0
        labelled = {names[n]['idx'] for n in ('knight', 'minion', 'king-tower', 'queen-tower')}
        for (idx, belong, x1, y1, x2, y2), u in zip(labels, meta['units']):
            assert idx in labelled                                  # bars / badges never labelled
            assert names[u['name']]['idx'] == idx and u['belong'] == belong
            assert 0 <= x1 < x2 <= G.W and 0 <= y1 < y2 <= G.H
        assert meta['damaged'] > 0
        # team of synthesised (swapped) knights is the requested one; real ones keep their cut-out team
        for u in meta['units']:
            if u['name'] == 'knight' and not u['swap']:
                assert u['belong'] == 1


def test_hidden_unit_dropped_and_boxes_are_visible_part():
    with tempfile.TemporaryDirectory() as d:
        bank = make_bank(d)
        comp = C.Composer(bank, dict(p_official=0, n_units=((1., 0, 0),), p_dim=0, p_noise=0, p_items=0, p_tower_bar=0,
                                     gain=(1, 1), bias=(0, 0), sat=(1, 1), hue=(0, 0), p_resample=0, p_blur=0))
        rng = np.random.default_rng(0)
        # hand-built layers: a small knight fully behind a big minion -> dropped; a partly covered one -> visible box
        kn = bank.sprites['knight'][1][0]['img']; mi = np.zeros((60, 60, 4), np.uint8); mi[..., 3] = 255
        idx_k, idx_m = bank.names['knight']['idx'], bank.names['minion']['idx']
        layers = [C.Layer(kn, 100, 100, (1, 140), (idx_k, 1), 0, dict(name='knight', belong=1)),
                  C.Layer(mi, 90, 90, (2, 150), (idx_m, 0), 1, dict(name='minion', belong=0)),
                  C.Layer(kn, 300, 300, (1, 340), (idx_k, 1), 2, dict(name='knight', belong=1)),
                  C.Layer(mi[:20, :60], 290, 280, (2, 330), None, 3, dict(name='bar'))]
        img, ids = C.Composer._render(np.zeros((G.H, G.W, 3), np.uint8), layers)
        assert (ids == 0).sum() == 0                                 # fully hidden
        ys, xs = np.nonzero(ids == 2)
        assert ys.min() == 300 and ys.max() == 339 and xs.min() == 300   # rows 300.. visible (cover ends at y=300)
        _ = rng


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
