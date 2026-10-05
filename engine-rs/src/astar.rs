// Engine-speed micro-port: exact port of clasher.pathfinding._native_grid_route
// (weighted octile A*, priority-only binary heap checking right child before left,
// decrease-key by sift-up, no reopen of closed nodes). Verifies routes against the
// Python engine's output and times both on the same cases.

struct Grid {
    w: i32,
    h: i32,
}

fn heuristic(cx: i32, cy: i32, gx: i32, gy: i32) -> i64 {
    let dx = (gx - cx).abs() as i64;
    let dy = (gy - cy).abs() as i64;
    5 * (10 * dx.max(dy) + 4 * dx.min(dy))
}

fn route(
    g: &Grid,
    nb: &[(i32, i32, i64)],
    cost: &[i64],
    start: (i32, i32),
    goal: (i32, i32),
    pri: &mut Vec<i64>,
    trav: &mut Vec<i64>,
    par: &mut Vec<i32>,
    closed: &mut Vec<bool>,
    pos: &mut Vec<i32>,
    heap: &mut Vec<i32>,
) -> Option<Vec<i32>> {
    let n = (g.w * g.h) as usize;
    for i in 0..n {
        pri[i] = i64::MIN;
        trav[i] = 0;
        par[i] = -1;
        closed[i] = false;
        pos[i] = -1;
    }
    heap.clear();
    let idx = |x: i32, y: i32| (y * g.w + x) as usize;
    let s = idx(start.0, start.1);
    let gl = idx(goal.0, goal.1) as i32;
    pri[s] = 0;
    trav[s] = 0;
    heap.push(s as i32);
    pos[s] = 0;
    let mut found = false;
    while !heap.is_empty() {
        // pop
        let root = heap[0];
        pos[root as usize] = -1;
        let last = heap.pop().unwrap();
        if !heap.is_empty() {
            heap[0] = last;
            pos[last as usize] = 0;
            let mut index = 0usize;
            let len = heap.len();
            loop {
                let mut chosen = index;
                let right = index * 2 + 2;
                if right < len && pri[heap[right] as usize] < pri[heap[chosen] as usize] {
                    chosen = right;
                }
                let left = index * 2 + 1;
                if left < len && pri[heap[left] as usize] < pri[heap[chosen] as usize] {
                    chosen = left;
                }
                if chosen == index {
                    break;
                }
                heap.swap(index, chosen);
                pos[heap[index] as usize] = index as i32;
                pos[heap[chosen] as usize] = chosen as i32;
                index = chosen;
            }
        }
        let cur = root as usize;
        closed[cur] = true;
        if root == gl {
            found = true;
            break;
        }
        let (cx, cy) = ((root % g.w), (root / g.w));
        for &(dx, dy, step) in nb {
            let (nx, ny) = (cx + dx, cy + dy);
            if nx < 0 || ny < 0 || nx >= g.w || ny >= g.h {
                continue;
            }
            let ni = idx(nx, ny);
            if closed[ni] {
                continue;
            }
            let t = trav[cur] + step * cost[ni];
            let p = t + heuristic(nx, ny, goal.0, goal.1);
            if pri[ni] != i64::MIN && p >= pri[ni] {
                continue;
            }
            par[ni] = cur as i32;
            trav[ni] = t;
            pri[ni] = p;
            // push (sift-up from existing position or append)
            let mut index = if pos[ni] >= 0 {
                pos[ni] as usize
            } else {
                heap.push(ni as i32);
                heap.len() - 1
            };
            while index > 0 {
                let pi = (index - 1) / 2;
                let parent = heap[pi];
                if pri[parent as usize] <= p {
                    break;
                }
                heap[index] = parent;
                pos[parent as usize] = index as i32;
                index = pi;
            }
            heap[index] = ni as i32;
            pos[ni] = index as i32;
        }
    }
    if !found {
        return None;
    }
    let mut r = vec![gl];
    while *r.last().unwrap() != s as i32 {
        let p = par[*r.last().unwrap() as usize];
        if p < 0 {
            return None;
        }
        r.push(p);
    }
    r.reverse();
    Some(r)
}

pub fn find(cost: &[i64], start: (i32, i32), goal: (i32, i32)) -> Option<Vec<(i32, i32)>> {
    let n = 36 * 64;
    let nb = [
        (0, -1, 10),
        (0, 1, 10),
        (-1, 0, 10),
        (1, 0, 10),
        (-1, -1, 14),
        (-1, 1, 14),
        (1, 1, 14),
        (1, -1, 14),
    ];
    let (mut pri, mut trav, mut par, mut closed, mut pos, mut heap) = (
        vec![0; n],
        vec![0; n],
        vec![0; n],
        vec![false; n],
        vec![0; n],
        Vec::with_capacity(n),
    );
    route(
        &Grid { w: 36, h: 64 },
        &nb,
        cost,
        start,
        goal,
        &mut pri,
        &mut trav,
        &mut par,
        &mut closed,
        &mut pos,
        &mut heap,
    )
    .map(|r| r.into_iter().map(|v| (v % 36, v / 36)).collect())
}
