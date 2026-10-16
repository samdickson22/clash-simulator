//! Mega Knight's fixed-duration leap retains the ground target plane.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Spec {
    minimum:f64, maximum:f64, windup:f64, speed:i64, airborne:i64, landing:i64,
    damage:f64, radius:f64, push:f64, spawn_damage:f64, spawn_radius:f64, spawn_push:f64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct State {
    pub phase:String, #[serde(default)] wait:i64, #[serde(default)] mark:i64, target:Option<i32>,
    #[serde(default)] seen:Option<i32>, #[serde(default)] blocked:bool, #[serde(default)] goal:Option<(i64,i64)>,
    consumed:bool, spawned:bool,
}
impl Entity {
    pub(super) fn cancel_leap_for_hook(&mut self) {
        if let Some(s)=&mut self.leap {
            s.phase="idle".into();s.wait=0;s.target=None;s.seen=None;s.blocked=false;s.goal=None;s.consumed=true;
        }
    }
    pub(super) fn leap_active(&self)->bool {
        self.leap.as_ref().is_some_and(|s|s.phase=="airborne" || s.phase=="landing" || s.consumed)
    }
    pub(super) fn leap_airborne(&self)->bool {
        self.leap.as_ref().is_some_and(|s|s.phase=="airborne")
    }
    /// An accepted displacement ends the stand (mega_knight.py `_cancel_charge`); the seen target is kept.
    pub(super) fn leap_cancel(&mut self) {
        if let Some(s)=&mut self.leap {
            if s.phase=="charging" { s.phase="idle".into();s.target=None;s.wait=0; }
        }
    }
}
impl BattleState {
    fn leap_slam(&mut self,i:usize,radius:f64,damage:f64,push:f64) {
        let a=&self.entities[i];let center=(a.x,a.y);
        let victims:Vec<usize>=self.entities.iter().enumerate().filter_map(|(j,e)| {
            (e.alive && e.owner!=a.owner && !e.above_surface() && !e.hidden && !e.spirit
             && !e.underground && !e.absent() && !e.dash_travel()
             && e.death_immunity.is_none() && (e.class=="Troop" || e.class=="Building")
             && Self::in_area(e,a.x,a.y,radius)).then_some(j)
        }).collect();
        for j in victims {
            self.damage(j,damage);self.radial_knockback(j,center,push,false,false,None);
        }
    }
    pub(super) fn leap_spawn(&mut self,i:usize) {
        let Some(spec)=self.entities[i].stats.leap.clone() else {return;};
        let Some(state)=&mut self.entities[i].leap else {return;};
        if state.spawned{return;} state.spawned=true;
        self.leap_slam(i,spec.spawn_radius,spec.spawn_damage,spec.spawn_push);
    }
    /// Combat component: the dash owns the frame from its entry to its end (mega_knight.py `_special_move_active`).
    pub(super) fn leap_combat(&mut self,i:usize)->bool {
        if self.entities[i].stats.leap.is_none() {return false;}
        let Some(s)=&mut self.entities[i].leap else {return false;};
        if s.consumed {s.consumed=false;return true;}
        s.phase=="airborne" || s.phase=="landing"
    }
    fn leap_step(&mut self,i:usize,spec:&Spec,state:&mut State) {
        let goal=state.goal.unwrap_or((units(self.entities[i].x),units(self.entities[i].y)));
        let ((x,y),arrived)=dash::dash_half_step((units(self.entities[i].x),units(self.entities[i].y)),goal,spec.speed);
        if arrived {state.goal=Some((x,y));}
        self.entities[i].x=x as f64/1000.0;self.entities[i].y=y as f64/1000.0;
        if self.tick!=state.mark+spec.airborne/50 {return;}
        self.entities[i].leap=Some(state.clone());
        self.leap_slam(i,spec.radius,spec.damage,spec.push);
        let e=&mut self.entities[i];
        if e.stats.ordinary && e.clock_projection_ms()!=e.stats.interval {e.clock_reseed=Some(e.stats.interval);}
        e.cooldown=e.stats.interval as f64/1000.0;
        let (x,y)=self.recover_ground(x,y);
        self.entities[i].x=x as f64/1000.0;self.entities[i].y=y as f64/1000.0;
        state.goal=Some((x,y));state.phase="landing".into();
    }
    /// Movement component (mega_knight.py `MegaKnightSlam.on_movement_tick`). True when the leap owns the frame.
    pub(super) fn leap_movement(&mut self,i:usize,external:(i64,i64))->bool {
        let Some(spec)=self.entities[i].stats.leap.clone() else {return false;};
        let Some(mut state)=self.entities[i].leap.take() else {return false;};
        let hold=|this:&mut Self,i:usize,state:State| {
            this.entities[i].leap=Some(state);this.entities[i].moving=false;this.apply_external(i,external);true
        };
        if state.phase=="airborne" {
            self.leap_step(i,&spec,&mut state);
            state.consumed=false;return hold(self,i,state);
        }
        if state.phase=="landing" {
            if self.tick>=state.mark+spec.airborne/50+4 {
                state.phase="idle".into();state.target=None;state.seen=None;state.blocked=false;state.goal=None;state.wait=0;
            }
            state.consumed=false;return hold(self,i,state);
        }
        if self.entities[i].stun>0.0 {self.entities[i].leap=Some(state);return false;}
        let target=self.entities[i].target.and_then(|id|self.index(id)).filter(|&j|self.entities[j].alive);
        let (windup,finish)=(self.entities[i].windup,self.entities[i].clock.finish!=0);
        if state.phase=="idle" {
            if let Some(j)=target.filter(|_|!windup && !finish) {
                let (a,b)=(&self.entities[i],&self.entities[j]);
                let (dx,dy)=(units(b.x)-units(a.x),units(b.y)-units(a.y));
                let d2=dx*dx+dy*dy;
                let near=units(spec.minimum)+units(a.stats.radius)+units(b.stats.radius);
                let reach=units(spec.maximum)+units(b.stats.radius);
                if state.seen!=Some(b.id) {state.seen=Some(b.id);state.blocked=d2<near*near;}
                if d2<=reach*reach && !state.blocked {
                    state.phase="charging".into();state.target=Some(b.id);
                    state.wait=((spec.windup as i64)/50).max(1)-1;
                    return hold(self,i,state);
                }
            }
        } else if state.phase=="charging"
            && (target.is_none() || target.map(|j|self.entities[j].id)!=state.seen || windup || finish)
        {
            state.phase="idle".into();state.target=None;state.wait=0;
        }
        if state.phase!="charging" {
            // A hook cancel's consumed frame (mega_knight.py `_special_move_consumed_tick`).
            if state.consumed {state.consumed=false;return hold(self,i,state);}
            self.entities[i].leap=Some(state);return false;
        }
        state.wait-=1;
        if state.wait>0 {return hold(self,i,state);}
        let j=target.unwrap();
        let (a,b)=(&self.entities[i],&self.entities[j]);
        let (ax,ay,tx,ty)=(units(a.x),units(a.y),units(b.x),units(b.y));
        let rr=units(a.stats.radius)+units(b.stats.radius);
        let (dx,dy)=(ax-tx,ay-ty);
        let n=isqrt(dx*dx+dy*dy);
        let (px,py)=if n==0 {(tx,ty)} else {(tx+dx*rr/n,ty+dy*rr/n)};
        state.goal=Some((px.div_euclid(500)*500+250,py.div_euclid(500)*500+250));
        state.mark=self.tick;state.wait=0;state.target=Some(b.id);state.phase="airborne".into();
        self.leap_step(i,&spec,&mut state);
        hold(self,i,state)
    }
}
