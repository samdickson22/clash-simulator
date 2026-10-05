//! Mega Knight's fixed-duration leap retains the ground target plane.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Spec {
    minimum:f64, maximum:f64, windup:f64, speed:i64, airborne:i64, landing:i64,
    damage:f64, radius:f64, push:f64, spawn_damage:f64, spawn_radius:f64, spawn_push:f64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct State {
    pub phase:String, progress:f64, duration:f64, target:Option<i32>,
    origin:(f64,f64), destination:Option<(f64,f64)>, consumed:bool, spawned:bool,
}
impl Entity {
    pub(super) fn cancel_leap_for_hook(&mut self) {
        if let Some(s)=&mut self.leap {
            s.phase="idle".into();s.progress=0.0;s.target=None;s.destination=None;s.duration=0.0;s.consumed=true;
        }
    }
    pub(super) fn leap_active(&self)->bool {
        self.leap.as_ref().is_some_and(|s|s.phase!="idle" || s.consumed)
    }
    pub(super) fn leap_airborne(&self)->bool {
        self.leap.as_ref().is_some_and(|s|s.phase=="airborne")
    }
    pub(super) fn leap_cancel(&mut self) {
        if let Some(s)=&mut self.leap {
            if s.phase=="charging" {
                s.phase="idle".into();s.progress=0.0;s.target=None;s.destination=None;s.duration=0.0;s.consumed=true;
            }
        }
    }
}
impl BattleState {
    fn leap_band(&self,i:usize,j:usize,spec:&Spec)->bool {
        let a=&self.entities[i];let b=&self.entities[j];
        let (dx,dy)=(units(a.x-b.x),units(a.y-b.y));
        let square=(dx*dx+dy*dy-b.stats.distance_discount.round_ties_even() as i64).max(0);
        let inner=units(spec.minimum)+units(a.stats.radius)+units(b.stats.radius);
        let outer=units(spec.maximum)+units(b.stats.radius);
        square>=inner*inner && square<=outer*outer
    }
    fn leap_slam(&mut self,i:usize,radius:f64,damage:f64,push:f64) {
        let a=&self.entities[i];let center=(a.x,a.y);
        let victims:Vec<usize>=self.entities.iter().enumerate().filter_map(|(j,e)| {
            (e.alive && e.owner!=a.owner && !e.above_surface() && !e.hidden && !e.spirit
             && !e.underground && e.stagger<=1e-9 && !e.dash_travel()
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
    pub(super) fn leap_combat(&mut self,i:usize,grid:&[Vec<usize>])->bool {
        let Some(spec)=self.entities[i].stats.leap.clone() else {return false;};
        let Some(mut state)=self.entities[i].leap.take() else {return false;};
        let mut active=false;
        if state.consumed {state.consumed=false;active=true;}
        else if state.phase=="airborne" || state.phase=="landing" {active=true;}
        else if state.phase=="charging" {
            if self.entities[i].stun<=0.0 {
                let target=self.target(i,grid).and_then(|id|self.index(id));
                if let Some(j)=target {self.entities[i].target=Some(self.entities[j].id);}
                if let Some(j)=target.filter(|&j|self.leap_band(i,j,&spec)) {
                    self.entities[i].target=Some(self.entities[j].id);state.target=self.entities[i].target;
                    state.progress+=self.entities[i].attack_work() as f64;
                    if state.progress+1e-9>=spec.windup {
                        let a=&self.entities[i];let b=&self.entities[j];
                        let (dx,dy)=(units(b.x)-units(a.x),units(b.y)-units(a.y));
                        let length=(isqrt(dx*dx+dy*dy)-units(a.stats.range+b.stats.radius)).max(0);
                        let (mx,my)=norm(dx,dy,length);
                        state.origin=(a.x,a.y);state.destination=Some(((units(a.x)+mx) as f64/1000.0,(units(a.y)+my) as f64/1000.0));
                        state.duration=if spec.airborne>0 {spec.airborne as f64} else {(length as f64/spec.speed.max(1) as f64*50.0).max(1.0)};
                        state.progress=0.0;state.phase="airborne".into();
                    }
                } else {
                    state.phase="idle".into();state.progress=0.0;state.target=None;state.destination=None;state.duration=0.0;
                }
            }
            active=true;
        } else if self.entities[i].stun<=0.0 {
            if let Some(j)=self.entities[i].target.and_then(|id|self.index(id)).filter(|&j|self.entities[j].alive && self.leap_band(i,j,&spec)) {
                state.phase="charging".into();state.progress=0.0;state.target=Some(self.entities[j].id);active=true;
            }
        }
        self.entities[i].leap=Some(state);active
    }
    pub(super) fn leap_movement(&mut self,i:usize,external:(i64,i64))->bool {
        let Some(spec)=self.entities[i].stats.leap.clone() else {return false;};
        let Some(mut state)=self.entities[i].leap.take() else {return false;};
        if state.phase=="idle" && !state.consumed {self.entities[i].leap=Some(state);return false;}
        self.entities[i].moving=false;
        if state.phase=="airborne" {
            state.progress+=50.0;
            if let Some((x,y))=state.destination {
                let duration=state.duration.round_ties_even().max(1.0) as i64;
                let elapsed=state.progress.round_ties_even().min(duration as f64) as i64;
                let e=&mut self.entities[i];
                e.x=(units(state.origin.0)+(units(x)-units(state.origin.0))*elapsed/duration) as f64/1000.0;
                e.y=(units(state.origin.1)+(units(y)-units(state.origin.1))*elapsed/duration) as f64/1000.0;
            }
            if state.progress>=state.duration.max(1.0) {
                self.entities[i].leap=Some(state.clone());
                self.leap_slam(i,spec.radius,spec.damage,spec.push);
                let e=&mut self.entities[i];
                if e.stats.ordinary && e.clock_projection_ms()!=e.stats.interval {e.clock_reseed=Some(e.stats.interval);}
                e.cooldown=e.stats.interval as f64/1000.0;
                state.progress=0.0;state.duration=0.0;
                state.phase=if spec.landing>0 {"landing".into()} else {"idle".into()};
                if state.phase=="idle" {state.target=None;state.destination=None;}
            }
        } else if state.phase=="landing" {
            state.progress+=50.0;
            if state.progress+1e-9>=spec.landing as f64 {
                state.phase="idle".into();state.target=None;state.destination=None;state.progress=0.0;state.duration=0.0;
            }
        }
        state.consumed=false;self.entities[i].leap=Some(state);self.apply_external(i,external);true
    }
}
