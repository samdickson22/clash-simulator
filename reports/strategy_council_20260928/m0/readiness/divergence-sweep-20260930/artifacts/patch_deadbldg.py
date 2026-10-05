"""Candidate B: a building killed earlier in this tick (still in the pre-combat avoidance grid) remains a
static avoidance obstacle for this tick's movement scans."""
from clasher.entities import Troop, Building
_ou=Troop._update_native_avoidance
def u(self,bs):
    grid=getattr(bs,'_native_avoidance_grid',None)
    dead=[]
    if grid is not None:
        for e in list(bs.entities.values()):
            if isinstance(e,Building) and not e.is_alive:
                dead.append(e); e.is_alive=True
    try: return _ou(self,bs)
    finally:
        for e in dead: e.is_alive=False
Troop._update_native_avoidance=u
