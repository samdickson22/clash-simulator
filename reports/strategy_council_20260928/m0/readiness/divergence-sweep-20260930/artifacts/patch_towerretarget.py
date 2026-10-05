"""Candidate T: a Crown Tower retargeting to a replacement already inside engagement reach keeps its hit timeline
(native f5c92c ordinary retarget preservation, which scalar applies only to ordinary-clock entities)."""
from clasher.entities import Entity
_o=Entity._note_combat_target
def _note_combat_target(self,target,*,preserve_hit=False):
    prev=getattr(self,'_last_combat_target_id',None)
    if (target is not None and prev is not None and prev!=target.id and self._ordinary_clock is None
        and getattr(getattr(self,'card_stats',None),'name',None) in ('Tower','KingTower')
        and self.is_within_attack_engagement_reach(target)):
        preserve_hit=True
    return _o(self,target,preserve_hit=preserve_hit)
Entity._note_combat_target=_note_combat_target
