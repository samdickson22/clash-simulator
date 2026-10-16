"""568x896 KataCR arena-crop geometry (= the r3 YOLO input space).

Crop box in a 720x1280 official capture (r3 owner, from live/loop/canvas.py's calibrated mapping): x 42.2..674.2,
y 31.3..1019.3 -> 568x896. Tile grid = KataCR xyxy_grids (6, 64, 562, 864): 18x32 cells of 30.89x25 px.
"""
W, H = 568, 896
CROP_720 = (42.2, 31.3, 674.2, 1019.3)
GRID = (6, 64, 562, 864)
CELL_W, CELL_H = (GRID[2]-GRID[0])/18, (GRID[3]-GRID[1])/32

# (name, belong, bottom-centre cell x, y) as KataCR's towers_bottom_center_grid_position
TOWER_SLOTS = [('king-tower', 1, 9, 4.7), ('queen-tower', 1, 3.5, 7.7), ('queen-tower', 1, 14.5, 7.7),
               ('king-tower', 0, 9, 30.5), ('queen-tower', 0, 3.5, 26.7), ('queen-tower', 0, 14.5, 26.7)]


def cell2px(x, y):
    return GRID[0] + x*CELL_W, GRID[1] + y*CELL_H


def px2cell(x, y):
    return (x-GRID[0])/CELL_W, (y-GRID[1])/CELL_H
