//! Clone copies capabilities through immutable, fresh source prototypes.
use super::*;

impl BattleState {
    pub(super) fn clone_spell(&mut self,cast:&Cast,spell:&Spell) {
        let recipients:Vec<usize>=self.entities.iter().enumerate().filter_map(|(i,e)| {
            (e.alive && e.owner==cast.player as i32 && e.class=="Troop" && !e.is_clone && e.mount.is_none()
             && ((e.x-cast.x).powi(2)+(e.y-cast.y).powi(2)).sqrt()<=spell.radius+1e-9).then_some(i)
        }).collect();
        for i in recipients {
            let source=&self.entities[i];
            let Some(template)=&source.clone_template else {panic!("missing imported Clone prototype");};
            let mut child=(**template).clone();
            let attached=std::mem::take(&mut child.clone_children);
            let origin=(child.x,child.y);
            let mut ids=BTreeMap::new();
            ids.insert(child.id,self.next_id as i32);
            child.id=self.next_id as i32;self.next_id+=1;
            child.x=source.x;child.y=source.y;child.owner=source.owner;
            child.facing=(0,if source.owner==0 {1000} else {-1000});
            let (cx,cy)=cell(child.x,child.y);child.lane=self.config.lane_ids[(cy*36+cx) as usize];
            child.birth=self.tick;child.shield=if source.shield>0.0 {1.0} else {0.0};
            let (x,y,owner)=(child.x,child.y,child.owner);
            self.entities.push(child);
            for body in &attached {
                ids.insert(body.id,self.next_id as i32);self.next_id+=1;
            }
            for mut body in attached {
                body.id=ids[&body.id];
                body.mount=body.mount.map(|id| ids[&id]);
                // riders.py creates each attachment in integer logic units;
                // subtracting/adding tile floats changes the serialized bits.
                body.x=(units(x)+units(body.x)-units(origin.0)) as f64/1000.0;
                body.y=(units(y)+units(body.y)-units(origin.1)) as f64/1000.0;
                body.owner=owner;body.facing=(0,if owner==0 {1000} else {-1000});
                let (cx,cy)=cell(body.x,body.y);body.lane=self.config.lane_ids[(cy*36+cx) as usize];
                body.birth=self.tick;
                self.entities.push(body);
            }
        }
    }
    pub(super) fn clone_payload(child:&mut Entity,source:&Entity) {
        if !source.is_clone {return;}
        child.is_clone=true;child.hp=1.0;child.stats.max_hp=1.0;
        child.clone_template=None;
        if child.shield>0.0 {child.shield=1.0;}
    }
}
