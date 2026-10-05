//! Skeleton King soul collection and shared active/death swarm spawning.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Spec {
    radius: f64,
    maximum: i64,
}

impl BattleState {
    pub(super) fn collect_souls(&mut self, i: usize) {
        let actor = &self.entities[i];
        let Some(spec) = &actor.stats.souls else { return; };
        let count = self.entities.iter().filter(|e| {
            e.owner != actor.owner && !e.alive
                && ((actor.x-e.x).powi(2)+(actor.y-e.y).powi(2)).sqrt() <= spec.radius
        }).count() as i64;
        self.entities[i].souls_collected = (actor.souls_collected + count).min(spec.maximum);
    }

    pub(super) fn drop_souls(&mut self, source: &Entity) {
        let count = (source.souls_collected / 2).min(10).max(0) as usize;
        if count == 0 { return; }
        let offsets = self.config.soul_offsets[count-1].clone();
        self.spawn_soul_groups(source, offsets);
    }

    pub(super) fn spawn_soul_groups(&mut self, source: &Entity, offsets: Vec<(f64, f64)>) {
        for (dx,dy) in offsets {
            let (x,y) = (source.x+dx,source.y+dy);
            let templates = self.config.soul_skeletons[source.owner as usize][usize::from(x>9.0)].clone();
            for mut child in templates {
            child.id = self.next_id as i32;
            self.next_id += 1;
            child.x = units((x + child.x).clamp(0.25,17.75)) as f64 / 1000.0;
            child.y = units((y + child.y).clamp(0.25,31.75)) as f64 / 1000.0;
            child.owner = source.owner;
            child.facing = (0,if source.owner == 0 { 1000 } else { -1000 });
            child.lane = if child.x < 9.0 { 1 } else { 2 };
            child.birth = self.tick;
            self.entities.push(child);
            }
        }
    }
}
