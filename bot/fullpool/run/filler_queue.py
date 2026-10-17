"""Write a bot/exit/filler.sh queue for one host (full-pool owner's filler content, BOT LEAD 2026-10-17).

    python3 bot/fullpool/run/filler_queue.py --host 04 --tree T --root R --pins P --resume 15:400,19:600 \
        --new 23,27,31 --leaf-start 3000000 > STATE/queue      (or >> to extend)

Order: (a) K1 blocks of the paused shards (--resume SHARD:CASES; done keys are skipped, so finished ranges end fast),
then (a) new K1 shards (600 cases each, round-robin over shards) with one (b) leaf/value data block per two K1 blocks (bot.value.gen with the vn0b
teacher, strong-opponent pool, out $J/leafgen3/x<host>-s<start>). Each block: 12 workers; K1 16 cases x 3 opponents,
leaf 36 games (~15-30 min). Groups: one K1 shard dir at a time ("k1s<shard>"); leaf blocks are independent.
Levels: our engine, every card L11 (switch to L16 when the native levels option lands; Sam's max-level rule).
"""
import argparse

J = '/mpac/sdicks02/jobs/clasher/bot-fullpool'
TEACHER = f'{J}/vnet/vn0b-t1/value-best.pt'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', required=True)
    ap.add_argument('--tree', required=True)
    ap.add_argument('--root', required=True)
    ap.add_argument('--pins', default='live16402c')
    ap.add_argument('--resume', default='')
    ap.add_argument('--new', default='')
    ap.add_argument('--leaf-start', type=int, required=True)
    ap.add_argument('--k1-block', type=int, default=16)
    ap.add_argument('--leaf-games', type=int, default=36)
    ap.add_argument('--workers', type=int, default=12)
    a = ap.parse_args()
    env = f'cd {a.tree} && ROOT={a.root} PINS={a.pins} W={a.workers}'

    def k1(shard, cases):
        for off in range(0, cases, a.k1_block):
            yield f'{a.workers} k1s{shard} {env} OFFSET={off} bot/fullpool/run/k1.sh {shard} {min(a.k1_block, cases - off)}'
    out = []

    def rr(specs):   # round-robin over shards, so several shard groups run at once
        gens = [k1(s, c) for s, c in specs]
        while gens:
            for g in list(gens):
                line = next(g, None)
                if line is None:
                    gens.remove(g)
                else:
                    yield line
    out += list(rr([tuple(map(int, x.split(':'))) for x in filter(None, a.resume.split(','))]))
    leaf, news = a.leaf_start, [(int(x), 600) for x in filter(None, a.new.split(','))]
    for i, line in enumerate(rr(news)):
        out.append(line)
        if i % 2 == 1:   # one leaf block per two K1 blocks
            out.append(f'{a.workers} leaf{leaf} {env} OUT=leafgen3/x{a.host}-s{leaf} BOT_VN_TEACHER={TEACHER} '
                       f'bot/fullpool/run/leafgen.sh {leaf} {a.leaf_games}')
            leaf += a.leaf_games
    print('\n'.join(out))


if __name__ == '__main__':
    main()
