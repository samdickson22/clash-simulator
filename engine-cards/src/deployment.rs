//! Royal Recruits' reference-specific tower avoidance and child placement.
use super::*;

impl BattleState {
    pub(super) fn prepare_placement_mask(&mut self, size: i64) {
        let signature: Vec<i32> = self.entities.iter().filter(|e| e.alive && e.class == "Building").map(|e| e.id).collect();
        if signature != self.placement_signature {
            self.placement_signature = signature;
            self.placement_masks.clear();
        }
        if self.placement_masks.contains_key(&size) { return; }
        let offset = if size % 2 == 1 { 0.5 } else { 0.0 };
        let half = size as f64 / 2.0;
        // battle.py:651-693 caches float32 bounds by live building membership.
        // Moving an existing underground building does not invalidate it.
        let bounds: Vec<_> = self.entities.iter().filter(|e| e.alive && e.class == "Building").map(|e| {
            let h = ((e.stats.radius * 2.0).ceil() + 1.0) / 2.0;
            ((e.x-h) as f32 as f64,(e.x+h) as f32 as f64,
             (e.y-h) as f32 as f64,(e.y+h) as f32 as f64)
        }).collect();
        let mut mask = Vec::with_capacity(576);
        for y in 0..32 { for x in 0..18 {
            let (x,y) = (x as f64+offset,y as f64+offset);
            mask.push(bounds.iter().any(|&(x1,x2,y1,y2)| x-half<x2 && x+half>x1 && y-half<y2 && y+half>y1));
        } }
        self.placement_masks.insert(size,mask);
    }

    fn child_position_clear(&self, x: f64, y: f64) -> bool {
        let touching = |v: f64, limit: i64| {
            let n = v.round_ties_even();
            if (v-n).abs() <= 1e-9_f64.max(1e-9*n.abs()) {
                vec![n as i64-1,n as i64].into_iter().filter(|i| *i>=0 && *i<limit).collect::<Vec<_>>()
            } else { vec![v.floor() as i64] }
        };
        (0.25 - 1e-9..=17.75 + 1e-9).contains(&x)
            && (0.25 - 1e-9..=31.75 + 1e-9).contains(&y)
            && self.can_deploy_anywhere(x, y)
            && !touching(x,18).iter().any(|tx| touching(y,32).iter().any(|ty| self.config.blocked_tiles[(ty*18+tx) as usize]))
            && (!(15.0..=17.0).contains(&y) || (2.0..=5.0).contains(&x) || (13.0..=16.0).contains(&x))
            && !self.entities.iter().any(|e| {
                e.alive && e.class == "Building"
                    && units(x - e.x).pow(2) + units(y - e.y).pow(2)
                        < units(e.stats.radius + 0.5).pow(2)
            })
    }

    pub(super) fn snap_child(&self, x: f64, y: f64, owner: usize) -> (f64, f64) {
        if self.child_position_clear(x, y) { return (x, y); }
        if (15.0..=17.0).contains(&y) && !(2.0..=5.0).contains(&x) && !(13.0..=16.0).contains(&x) {
            let bank = if owner == 0 { 14.5 } else { 17.5 };
            if self.child_position_clear(x, bank) { return (x, bank); }
        }
        let mut best = (x, y);
        let mut distance = f64::INFINITY;
        let sign = if owner == 0 { 1.0 } else { -1.0 };
        for dx in -3..=3 {
            for dy in -3..=3 {
                let p = (x + dx as f64 * 0.5 * sign, y + dy as f64 * 0.5 * sign);
                if self.child_position_clear(p.0, p.1) {
                    let d = ((x - p.0).powi(2) + (y - p.1).powi(2)).sqrt();
                    if d < distance - 1e-9 { best = p; distance = d; }
                }
            }
        }
        if distance.is_infinite() {
            let p = (x.clamp(0.5, 17.5), y.clamp(0.5, 31.5));
            if self.child_position_clear(p.0, p.1) { return p; }
            for step in [0.5, 1.0, 1.5, 2.0] {
                let q = (p.0 + (9.0 - p.0) * step * 0.1, p.1 + (16.0 - p.1) * step * 0.1);
                if self.child_position_clear(q.0, q.1) { return q; }
            }
        }
        best
    }

    pub(super) fn recruit_positions(&self, x: f64, y: f64, owner: usize, count: usize) -> Vec<(f64, f64)> {
        let blocked: Vec<(f64, f64)> = self.entities.iter().filter_map(|e| {
            let r = if e.king { 2.0 } else { 1.5 };
            (e.alive && e.class == "Building" && (e.king || e.stats.name == "Tower")
                && (y - e.y).abs() <= r + 1e-9).then_some((e.x-r,e.x+r))
        }).collect();
        let mut positions: Vec<f64> = (0..count).map(|i| x - (count-1) as f64 * 2.5 / 2.0 + i as f64 * 2.5).collect();
        if positions.iter().any(|p| blocked.iter().any(|(lo,hi)| lo <= p && p <= hi)) {
            let mut blocked_halves = Vec::new();
            for &(lo,hi) in &blocked {
                let mut p = lo;
                while p <= hi { blocked_halves.push((p*2.0).round_ties_even() as i64); p += 0.5; }
            }
            let safe: Vec<f64> = (1..36).filter(|i| !blocked_halves.contains(i)).map(|i| i as f64 / 2.0).collect();
            if safe.len() >= count {
                let near: Vec<f64> = safe.iter().copied().filter(|p| (p-x).abs() <= 1.0).collect();
                let candidates = if near.is_empty() { &safe } else { &near };
                let center = *candidates.iter().min_by(|a,b| (**a-x).abs().total_cmp(&(**b-x).abs())).unwrap();
                positions = vec![center];
                while positions.len() < count {
                    let next = safe.iter().copied().filter(|p| !positions.contains(p)).min_by(|a,b| {
                        let score = |p: f64| positions.iter().map(|v| ((p-v).abs()-2.5).abs()).fold(f64::INFINITY,f64::min);
                        score(*a).total_cmp(&score(*b))
                    }).unwrap();
                    positions.push(next);
                }
            } else { positions = safe.into_iter().take(count).collect(); }
            while positions.len() < count {
                for p in [0.5,1.0,17.0,17.5,16.5,16.0] {
                    if !positions.contains(&p) && !blocked_halves.contains(&((p*2.0) as i64)) {
                        positions.push(p); if positions.len() >= count { break; }
                    }
                }
            }
            positions.sort_by(f64::total_cmp);
            positions.truncate(count);
        }
        positions.into_iter().map(|p| self.snap_child(p.clamp(0.5,17.5), y, owner)).collect()
    }
}
