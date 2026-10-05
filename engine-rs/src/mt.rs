//! CPython-compatible MT19937 state import and bit extraction.
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Mt {
    pub state: Vec<u32>,
    pub index: usize,
}
impl Mt {
    pub fn next(&mut self) -> u32 {
        if self.index >= 624 {
            for i in 0..624 {
                let y = (self.state[i] & 0x80000000) | (self.state[(i + 1) % 624] & 0x7fffffff);
                self.state[i] = self.state[(i + 397) % 624]
                    ^ (y >> 1)
                    ^ if y & 1 != 0 { 0x9908b0df } else { 0 };
            }
            self.index = 0;
        }
        let mut y = self.state[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c5680;
        y ^= (y << 15) & 0xefc60000;
        y ^ (y >> 18)
    }
    pub fn random(&mut self) -> f64 {
        let a = self.next() >> 5;
        let b = self.next() >> 6;
        (a as f64 * 67108864.0 + b as f64) / 9007199254740992.0
    }
    pub fn below(&mut self, n: u32) -> u32 {
        let k = 32 - n.leading_zeros();
        loop {
            let r = self.next() >> (32 - k);
            if r < n {
                return r;
            }
        }
    }
}
