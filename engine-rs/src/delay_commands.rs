//! Opt-in command channels for exploratory delay rollouts. Legacy rollout is untouched.
use super::*;

pub(super) type CommandInput = (i64, usize, String, f64);
pub(super) type CommandEvent = (String, i64, usize, usize, bool, String);
#[derive(Clone)]
struct Command { due: i64, action: usize, card: String, cost: f64 }

impl NativeScripts {
    fn reserved_choice(&self, sim: &mut BattleState, actor: usize,
        style: &str, queue: &[Command]) -> PyResult<usize> {
        // Shadow only the acting player's exact reservations. Restore before
        // any physical step: execution performs the sole engine debit/cycle.
        let physical = sim.players[actor].clone();
        for c in queue {
            sim.players[actor].elixir -= c.cost;
            sim.players[actor].hand[c.action / 576] = None;
            sim.players[actor].cycle.push_back(c.card.clone());
        }
        let result = self.select_action(sim, actor, style);
        sim.players[actor] = physical;
        result
    }

    pub(super) fn command_simulation(&self, battle: &BattleState, seat: usize,
        action: usize, own_pending: Vec<CommandInput>, opponent: &str,
        delay: i64, opponent_delay: i64, capacity: usize, opponent_capacity: usize,
        horizon: usize, own_interval: usize, opponent_interval: usize,
        continue_own: bool, endpoint: bool, trace: bool,
    ) -> PyResult<(BattleState, Vec<CommandEvent>)> {
        if seat > 1 || delay < 0 || opponent_delay < 0 || capacity == 0
            || opponent_capacity == 0 || own_interval == 0 || opponent_interval == 0
            || action > 2304 || !["balanced", "pressure", "defense"].contains(&opponent) {
            return Err(PyValueError::new_err("invalid delayed rollout configuration"));
        }
        let mut sim = battle.clone();
        let mut queues: [Vec<Command>; 2] = [vec![], vec![]];
        for (due, a, card, cost) in own_pending {
            if a >= 2304 || due < sim.tick || !cost.is_finite() || cost < 0.
                || queues[seat].iter().any(|c| c.action / 576 == a / 576)
                || sim.players[seat].hand[a / 576].as_ref() != Some(&card)
                || self.meta.cards.get(&card).is_none_or(|m| (m.cost-cost).abs() > 1e-9) {
                return Err(PyValueError::new_err("invalid own pending reservation"));
            }
            queues[seat].push(Command { due, action: a, card, cost });
        }
        if queues[seat].len() > capacity {
            return Err(PyValueError::new_err("pending capacity exceeded"));
        }
        let mut events = vec![];
        let origin = sim.tick;
        let submit = |s: &BattleState, actor: usize, a: usize, lead: i64,
            queue: &mut Vec<Command>, cap: usize, events: &mut Vec<CommandEvent>| -> PyResult<()> {
            if a == 2304 { return Ok(()); }
            if queue.len() >= cap || a >= 2304
                || queue.iter().any(|c| c.action / 576 == a / 576) {
                return Err(PyValueError::new_err("duplicate slot or full command channel"));
            }
            let card = s.players[actor].hand[a / 576].clone()
                .ok_or_else(|| PyValueError::new_err("empty submitted slot"))?;
            let cost = self.meta.cards[&card].cost;
            let reserved: f64 = queue.iter().map(|c| c.cost).sum();
            if cost > s.players[actor].elixir-reserved+1e-6 {
                return Err(PyValueError::new_err("unaffordable pending reservation"));
            }
            if trace { events.push(("submit".into(), s.tick, actor, a, true, card.clone())); }
            queue.push(Command { due: s.tick+lead, action: a, card, cost });
            Ok(())
        };
        submit(&sim, seat, action, delay, &mut queues[seat], capacity, &mut events)?;
        let other = self.reserved_choice(&mut sim, 1-seat, opponent, &queues[1-seat])?;
        submit(&sim, 1-seat, other, opponent_delay, &mut queues[1-seat], opponent_capacity, &mut events)?;
        for tick in 0..=horizon {
            if tick == horizon && !endpoint { break; }
            if sim.game_over { break; }
            // Preserve S6's cadence-before-execution tie rule for own rollout.
            if tick > 0 && tick < horizon {
                for actor in [seat, 1-seat] {
                    let (interval, cap, lead, style) = if actor == seat {
                        (own_interval, capacity, delay, "balanced")
                    } else { (opponent_interval, opponent_capacity, opponent_delay, opponent) };
                    if (actor != seat || continue_own) && tick % interval == 0 && queues[actor].len() < cap {
                        let a = self.reserved_choice(&mut sim, actor, style, &queues[actor])?;
                        submit(&sim, actor, a, lead, &mut queues[actor], cap, &mut events)?;
                    }
                }
            }
            for actor in [seat, 1-seat] {
                let mut i = 0;
                while i < queues[actor].len() {
                    if queues[actor][i].due <= origin+tick as i64 {
                        let c = queues[actor].remove(i);
                        // Never execute a different card that later refilled this slot.
                        let accepted = sim.players[actor].hand[c.action / 576].as_ref() == Some(&c.card)
                            && self.apply_discrete(&mut sim, actor, c.action)?;
                        if trace { events.push(("execute".into(), sim.tick, actor, c.action, accepted, c.card)); }
                    } else { i += 1; }
                }
            }
            if tick < horizon { sim.tick_once(false); }
        }
        Ok((sim, events))
    }
}
