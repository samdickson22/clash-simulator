//! Opt-in public geometry. No hidden hand/order, RNG or combat clocks.
use super::*;

impl NativeScripts {
    pub(super) fn placement_mask_v2(&self, b: &BattleState, seat: usize,
        name: &str, m: &CardMeta, view: &View, zone: &[bool]) -> Vec<bool> {
        let quantize = |x: f64| (x * 1000.0).round_ties_even() / 1000.0;
        let buildings: Vec<_> = view.bodies.iter().filter(|e| e.building).map(|e| {
            let radius = self.meta.building_radii.get(&e.token).copied()
                .unwrap_or((e.blocker_radius * 10000.0).round_ties_even() / 10000.0);
            (quantize(e.x), quantize(e.y), if radius == 0.0 { 1.0 } else { radius },
             ((2.0 * radius).ceil() + 1.0).max(1.0) / 2.0, e.crown,
             self.meta.bodies.get("KingTower").is_some_and(|k| k.token == e.token))
        }).collect();
        // TimedExplosive's visible kind disambiguates the source-body token.
        // Its radius comes from the public catalog, never its runtime timer.
        let payloads: Vec<_> = b.entities.iter().filter(|e| e.alive && e.class == "TimedExplosive")
            .filter_map(|e| {
                let token = self.meta.bodies.get(&e.stats.name)?.token;
                let radius = *self.meta.payload_radii.get(&token)?;
                let (x,y) = if seat == 1 { (18.0-e.x,32.0-e.y) } else { (e.x,e.y) };
                Some((quantize(f32clip(x/18.0)*18.0),quantize(f32clip(y/32.0)*32.0),radius))
            }).collect();
        let crown_blocked = |x: f64, y: f64| buildings.iter().any(|&(bx,by,_,_,crown,king)| {
            let h = if king { 2.0 } else { 1.5 };
            crown && (x-bx).abs() <= h+1e-9 && (y-by).abs() <= h+1e-9
        });
        let footprint = |x: f64, y: f64, h: f64| buildings.iter().any(|&(bx,by,_,bh,_,_)|
            (x-bx).abs() < h+bh && (y-by).abs() < h+bh);
        let payload = |x: f64, y: f64, half: Option<f64>| payloads.iter().any(|&(px,py,pr)| {
            let (dx,dy,r) = match half {
                Some(h) => (((x-px).abs()-h).max(0.0),((y-py).abs()-h).max(0.0),pr),
                None => (x-px,y-py,pr+m.radius),
            };
            dx*dx+dy*dy <= (r+1e-9).powi(2)
        });
        let anywhere = !m.spell && m.unrestricted;
        let unrestricted = anywhere || (m.spell && !m.requires_territory);
        let world = |i: usize| if seat == 1 { 575-i } else { i };
        let xy = |i: usize| ((i%18) as f64+0.5,(i/18) as f64+0.5);
        let ground: Vec<_> = if !m.spell && !m.building && !m.air {
            (0..576).filter(|&i| {
                let (x,y)=xy(i); let j=world(i);
                !b.config.blocked_tiles[j] && b.config.walkable[j] && b.config.spawn_clear[j]
                    && (anywhere || (zone[i] && !crown_blocked(x,y)))
                    && !footprint(x,y,0.5) && !payload(x,y,None)
            }).collect()
        } else { Vec::new() };
        (0..576).map(|i| {
            let (x,y)=xy(i); let j=world(i);
            if b.config.blocked_tiles[j] || (!unrestricted && !zone[i])
                || x < m.margin as f64 || x >= 18.0-m.margin as f64 { return false; }
            if m.spell { return !m.requires_walkable || b.config.walkable[j]; }
            if crown_blocked(x,y) { return false; }
            if m.building {
                let c=&b.config.cards[name];
                let (wx,wy)=if seat == 1 { (18.0-x,32.0-y) } else { (x,y) };
                let offset=if c.footprint%2==1 { 0.5 } else { 0.0 };
                let initial=(wx.floor()+offset,wy.floor()+offset);
                let anchor=if c.anchors.contains(&initial) { initial } else {
                    *c.anchors.iter().min_by(|a,z|
                        ((a.0-wx).powi(2)+(a.1-wy).powi(2))
                            .total_cmp(&((z.0-wx).powi(2)+(z.1-wy).powi(2)))
                            .then(z.0.total_cmp(&a.0)).then(z.1.total_cmp(&a.1))).unwrap()
                };
                let (ax,ay)=if seat == 1 { (18.0-anchor.0,32.0-anchor.1) } else { anchor };
                let h=c.footprint as f64/2.0;
                return !footprint(ax,ay,h) && !payload(ax,ay,Some(h));
            }
            if payload(x,y,None) { return false; }
            if m.air {
                return !buildings.iter().any(|&(bx,by,br,_,_,_)|
                    units(x-bx).pow(2)+units(y-by).pow(2) < units(m.radius+br).pow(2));
            }
            ground.iter().any(|&k| { let (gx,gy)=xy(k); (x-gx).abs()<=30.0 && (y-gy).abs()<=30.0 })
        }).collect()
    }
}
