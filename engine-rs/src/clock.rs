//! Port of clasher.attack_clock. All work is integer milliseconds.
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct Clock {
    pub interval: i64,
    pub load: i64,
    pub timeline: i64,
    pub remaining: i64,
    pub finish: i64,
}
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
    pub fn stop(&mut self) {
        self.timeline = 0;
        self.finish = 0;
    }
    pub fn removed(&mut self) {
        if self.timeline != 0 {
            self.finish = 1;
        } else {
            self.timeline = 0;
        }
    }
}
