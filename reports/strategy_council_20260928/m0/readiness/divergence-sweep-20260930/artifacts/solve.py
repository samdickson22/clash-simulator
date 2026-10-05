import sys; sys.path.insert(0,'/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/native-final-v6/src')
from clasher.kinematics import normalized_vector_logic_units as nv, movement_component_vector_logic_units as mv
from clasher.pathfinding import _cell_center
# usage: solve.py x y speed tx ty avs [extx exty] [extra points name:x:y,...]
x,y,sp,tx,ty=map(int,sys.argv[1:6]); avs=[int(a) for a in sys.argv[6].split(',')]
ex,ey=(int(sys.argv[7]),int(sys.argv[8])) if len(sys.argv)>8 else (0,0)
def rot(mx,my,a,m):
    if a==0: return (mx,my)
    r=256-abs(a); rx=(r*mx>>8)+(a*my>>8); ry=(r*my>>8)+(-mx*a>>8); return nv(rx,ry,m)
pts={}
cx0,cy0=int(x/500),int(y/500)
for cx in range(cx0-8,cx0+9):
    for cy in range(cy0-8,cy0+9):
        c=_cell_center((cx,cy)); pts[(cx,cy)]=(round(c.x*1000),round(c.y*1000))
if len(sys.argv)>9:
    for s in sys.argv[9].split(','):
        n,a,b=s.split(':'); pts[n]=(int(a),int(b))
out=[]
for k,(px,py) in pts.items():
    d=((px-x)**2+(py-y)**2)**.5
    m=min(sp,max(1,int(d)))
    v=mv(px-x,py-y,m)
    for a in avs:
        r=rot(v[0],v[1],a,m)
        if (r[0]+ex,r[1]+ey)==(tx,ty): out.append((k,a,v))
print(out)
