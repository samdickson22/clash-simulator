//! Clone copies capabilities through immutable, fresh source prototypes.
use super::*;

impl BattleState {
    pub(super) fn clone_spell(&mut self,cast:&Cast,spell:&Spell) {
        let recipients:Vec<usize>=self.entities.iter().enumerate().filter_map(|(i,e)| {
            (e.alive && e.owner==cast.player as i32 && e.class=="Troop" && !e.is_clone
             && ((e.x-cast.x).powi(2)+(e.y-cast.y).powi(2)).sqrt()<=spell.radius+1e-9).then_some(i)
        }).collect();
        for i in recipients {
            let source=&self.entities[i];
            let Some(template)=&source.clone_template else {panic!("missing imported Clone prototype");};
            let mut child=(**template).clone();
            child.id=self.next_id as i32;self.next_id+=1;
            child.x=source.x;child.y=source.y;child.owner=source.owner;
            child.facing=(0,if source.owner==0 {1000} else {-1000});
            let (cx,cy)=cell(child.x,child.y);child.lane=self.config.lane_ids[(cy*36+cx) as usize];
            child.birth=self.tick;child.shield=if source.shield>0.0 {1.0} else {0.0};
            self.entities.push(child);
            // Batch B2 (Python CloneSpell.cast; RoyaleSim (MIT) spells.CLONE_OFFSET / CLONE_HOLD_*): hold both
            // max(500 ms, deploy left) and slide each 10 ticks along its fixed column-edge heading.
            let hold=self.entities[i].deploy.max(0.5);
            let copy=self.entities.len()-1;
            for (j,toward_enemy) in [(i,true),(copy,false)] {
                let (sx,sy)=Self::clone_slide_step(&self.entities[j],toward_enemy);
                self.entities[j].clone_slide=Some((sx,sy,10));
                self.slow_target(j,hold,(0.0,0.0,0.0));
            }
        }
    }
    fn clone_slide_step(e:&Entity,toward_enemy:bool)->(i64,i64) {
        let (x,y)=(units(e.x),units(e.y));
        let goal_x=x.div_euclid(500)*500+250;
        let row=if toward_enemy==(e.owner==0) {63} else {0};
        let (dx,dy)=(goal_x-x,row*500+250-y);
        let d=isqrt(dx*dx+dy*dy);
        if d==0 {return (0,0);}
        let (hx,hy)=(dx*256/d,dy*256/d);
        (hx*125/256,hy*125/256)
    }
    pub(super) fn advance_clone_slide(&mut self,i:usize) {
        let Some((sx,sy,left))=self.entities[i].clone_slide else {return;};
        let e=&mut self.entities[i];
        e.x=(units(e.x)+sx) as f64/1000.0;e.y=(units(e.y)+sy) as f64/1000.0;
        e.clone_slide=if left>1 {Some((sx,sy,left-1))} else {None};
        if left<=1 {
            // CLONE_SLIDE_ROUTE = client15535_dropped: plan afresh from the slide's end.
            e.route.clear();e.goal=None;
        }
    }
    pub(super) fn clone_payload(child:&mut Entity,source:&Entity) {
        if !source.is_clone {return;}
        child.is_clone=true;child.hp=1.0;child.stats.max_hp=1.0;
        child.clone_template=None;
        if child.shield>0.0 {child.shield=1.0;}
    }
}
