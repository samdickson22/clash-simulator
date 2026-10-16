//! Port of clasher.attack_clock. All work is integer milliseconds.
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct Clock {
    pub interval: i64,
    pub load: i64,
    pub timeline: i64,
    pub remaining: i64,
    pub finish: i64,
    /// Batch C1 LoadFirstHit leave refund (attack_clock.py `refund_on_leave`); 0 = off, omitted.
    #[serde(default, skip_serializing_if = "is_zero")]
    pub refund: i64,
}
fn is_zero(x: &i64) -> bool { *x == 0 }
impl Clock {
    pub fn advance(&mut self, elapsed: i64, work: i64, engaged: bool) -> i64 {
        self.advance_with_load(elapsed,work,engaged,elapsed)
    }
    pub fn advance_with_load(&mut self, elapsed: i64, work: i64, engaged: bool, load_work: i64) -> i64 {
        self.remaining = (self.remaining - load_work).max(0);
        if self.finish != 0 {
            self.finish += elapsed;
            if self.finish >= 250 {
                self.finish = 0;
                self.timeline = 0;
            }
            return 0;
        }
        if !engaged {
            return 0;
        }
        let previous = self.timeline / self.interval;
        if self.timeline == 0 {
            self.timeline = (self.load - self.remaining).max(0);
            self.remaining = self.load;
        }
        self.timeline += work;
        let hits = self.timeline / self.interval - previous;
        if hits > 0 {
            self.remaining = self.load;
        }
        hits
    }
    fn refund_now(&mut self) {
        if self.refund != 0 && 0 < self.timeline && self.timeline < self.interval {
            self.remaining = (self.load - self.timeline).max(0);
        }
    }
    pub fn stop(&mut self) {
        self.refund_now();
        self.timeline = 0;
        self.finish = 0;
    }
    pub fn removed(&mut self) {
        if self.refund != 0 {
            self.refund_now();
            self.timeline = 0;
        } else if self.timeline != 0 {
            self.finish = 1;
        } else {
            self.timeline = 0;
        }
    }
}
