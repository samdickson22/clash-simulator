//! Fisherman wind-up and character-object flight/drag.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Spec {
    minimum:f64,maximum:f64,windup:f64,speed:i64,drag:i64,self_drag:i64,attractor:bool,margin:f64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct State {
    pub phase:String,pub target:Option<i32>,remaining:f64,position:Option<(f64,f64)>,consumed:bool,
}
impl Entity {
    pub(super) fn hook_active(&self)->bool { self.hook.as_ref().is_some_and(|s|s.phase!="idle" || s.consumed) }
}
impl BattleState {
    fn hook_finish(&mut self,i:usize,state:&mut State,cancel:bool) {
        if let Some(j)=state.target.and_then(|id|self.index(id)) {self.entities[j].forced_active=false;}
        state.phase="idle".into();state.target=None;state.remaining=0.0;state.position=None;state.consumed=true;
        if cancel {self.entities[i].target=None;}
    }
    pub(super) fn hook_cancel(&mut self,i:usize) {
        if let Some(mut s)=self.entities[i].hook.take() {
            self.hook_finish(i,&mut s,true);self.entities[i].hook=Some(s);
        }
    }
    fn hook_range(&self,i:usize,j:usize,spec:&Spec)->bool {
        let a=&self.entities[i];let b=&self.entities[j];
        if !b.alive || b.owner==a.owner || b.spirit || b.hidden || b.underground
           || b.stagger>1e-9 || b.death_immunity.is_some() || b.stealth_until>self.tick*50
           || !(b.class=="Troop" || b.class=="Building") || !a.can_hit_plane(b) {return false;}
        let distance=((a.x-b.x).powi(2)+(a.y-b.y).powi(2)).sqrt();
        distance>spec.minimum+1e-9 && distance<=spec.maximum+b.stats.radius+1e-9
    }
    fn hook_candidate(&self,i:usize,spec:&Spec)->Option<usize> {
        let a=&self.entities[i];let sign=if a.owner==0 {1.0} else {-1.0};
        let candidates:Vec<(usize,f64)>=self.entities.iter().enumerate().filter(|(j,_)|self.hook_range(i,*j,spec))
            .map(|(j,b)|(j,((a.x-b.x).powi(2)+(a.y-b.y).powi(2)).sqrt())).collect();
        let minimum=candidates.iter().map(|(_,d)|*d).fold(f64::INFINITY,f64::min);
        candidates.iter().filter(|(_,d)|*d<=minimum+1e-9).map(|(j,_)|*j).min_by(|&j,&k| {
            let b=&self.entities[j];let c=&self.entities[k];
            (sign*(b.x-9.0)).total_cmp(&(sign*(c.x-9.0)))
                .then((sign*(b.y-16.0)).total_cmp(&(sign*(c.y-16.0))))
                .then(b.id.cmp(&c.id))
        })
    }
    pub(super) fn hook_combat(&mut self,i:usize)->bool {
        let Some(spec)=self.entities[i].stats.hook.clone() else {return false;};
        let Some(mut state)=self.entities[i].hook.take() else {return false;};
        if self.entities[i].stun>0.0 {self.entities[i].hook=Some(state);return false;}
        if state.phase=="idle" {
            if let Some(j)=self.hook_candidate(i,&spec) {
                state.phase="windup".into();state.target=Some(self.entities[j].id);state.remaining=spec.windup;
                self.entities[i].target=state.target;
            }
        } else if let Some(j)=state.target.and_then(|id|self.index(id)).filter(|&j|self.entities[j].alive) {
            if state.phase=="windup" {
                if !self.hook_range(i,j,&spec) {self.hook_finish(i,&mut state,true);}
                else {
                    let work=self.entities[i].attack_work() as f64;
                    if work+1e-9<state.remaining {state.remaining-=work;}
                    else {
                        state.remaining=0.0;state.phase="flight".into();
                        let a=&self.entities[i];let b=&self.entities[j];
                        let (mx,my)=norm(units(b.x-a.x),units(b.y-a.y),units(a.stats.muzzle));
                        state.position=Some(((units(a.x)+mx) as f64/1000.0,
                            (units(a.y)+my+units(a.stats.muzzle_y)*if a.owner==0 {1} else {-1}) as f64/1000.0));
                    }
                }
            }
        } else {self.hook_finish(i,&mut state,true);}
        let active=state.phase!="idle" || state.consumed;
        if state.consumed {state.consumed=false;}
        self.entities[i].hook=Some(state);active
    }
    pub(super) fn hook_stop_movement(&mut self,i:usize,external:(i64,i64))->bool {
        let Some(state)=&mut self.entities[i].hook else {return false;};
        if state.phase=="idle" && !state.consumed {return false;}
        state.consumed=false;self.entities[i].moving=false;self.apply_external(i,external);true
    }
    fn hook_move_valid(&self,i:usize,x:f64,y:f64)->bool {
        if x<0.25-1e-9 || x>17.75+1e-9 || y<0.25-1e-9 || y>31.75+1e-9 {return false;}
        let radius=self.entities[i].stats.radius.min(0.5);
        !self.entities.iter().any(|b|b.alive && b.class=="Building" && {
            let (dx,dy,r)=(units(x-b.x),units(y-b.y),units(radius+b.stats.radius));dx*dx+dy*dy<r*r
        })
    }
    fn hook_interrupt(&mut self,j:usize) {
        let e=&mut self.entities[j];e.forced_active=true;
        e.clock.finish=0;e.windup=false;e.started=false;
        if e.charge>=10000 {
            e.consume_clock_reseed();
            e.charge=0;e.force_due=false;e.clock.stop();e.clock.remaining=0;e.preload_blocked=false;
        } else {
            if e.stats.ordinary && e.clock_projection_ms()!=e.stats.interval {e.clock_reseed=Some(e.stats.interval);}
            e.cooldown=e.cooldown.max(e.stats.interval as f64/1000.0);e.preload_blocked=true;
        }
        e.cancel_dash_for_hook();e.cancel_leap_for_hook();
    }
    pub(super) fn hook_object_tick(&mut self,i:usize) {
        let Some(spec)=self.entities[i].stats.hook.clone() else {return;};
        let Some(mut state)=self.entities[i].hook.take() else {return;};
        if state.phase!="flight" && state.phase!="drag" {self.entities[i].hook=Some(state);return;}
        let target=state.target.and_then(|id|self.index(id)).filter(|&j|self.entities[j].alive);
        let Some(j)=target else {self.hook_finish(i,&mut state,true);self.entities[i].hook=Some(state);return;};
        if state.phase=="flight" {
            if !self.entities[i].can_hit_plane(&self.entities[j]) || state.position.is_none() {
                self.hook_finish(i,&mut state,true);
            } else {
                let (x,y)=state.position.unwrap();let b=&self.entities[j];
                let (dx,dy)=(units(b.x-x),units(b.y-y));let length=isqrt(dx*dx+dy*dy).max(1);
                if length as f64/spec.speed.max(1) as f64>1.0+2e-11 {
                    let (mx,my)=if spec.speed>=length {(dx,dy)} else {norm(dx,dy,spec.speed)};
                    state.position=Some(((units(x)+mx) as f64/1000.0,(units(y)+my) as f64/1000.0));
                } else {
                    state.position=Some((b.x,b.y));
                    if b.spirit || b.underground || b.stagger>1e-9 || b.hidden || b.death_immunity.is_some() {
                        self.hook_finish(i,&mut state,true);
                    } else {
                        if b.class!="Building" {self.hook_interrupt(j);}
                        state.phase="drag".into();
                    }
                }
            }
        } else {
            let a=&self.entities[i];let b=&self.entities[j];
            let (dx,dy)=(units(a.x-b.x),units(a.y-b.y));let length=isqrt(dx*dx+dy*dy);
            let desired=units(a.stats.radius+b.stats.radius+spec.margin);
            let remaining=(length-desired).max(0);
            if remaining==0 || length==0 {self.hook_finish(i,&mut state,false);}
            else {
                let pulls_self=spec.attractor && b.class=="Building";
                let speed=if pulls_self {spec.self_drag} else {spec.drag};let work=remaining.min(speed);
                let moved=if pulls_self {i} else {j};
                let (mx,my)=norm(if pulls_self {-dx} else {dx},if pulls_self {-dy} else {dy},work);
                let body=&self.entities[moved];let x=(units(body.x)+mx) as f64/1000.0;let y=(units(body.y)+my) as f64/1000.0;
                if self.hook_move_valid(moved,x,y) {
                    self.entities[moved].x=x;self.entities[moved].y=y;
                    let a=&self.entities[i];let b=&self.entities[j];let (dx,dy)=(units(a.x-b.x),units(a.y-b.y));
                    if isqrt(dx*dx+dy*dy)<=desired {self.hook_finish(i,&mut state,false);}
                } else {self.hook_finish(i,&mut state,false);}
            }
        }
        self.entities[i].hook=Some(state);
    }
}
