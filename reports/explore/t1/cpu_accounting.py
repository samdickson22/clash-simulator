"""Generation-bound CPU deltas with credit for previously observed child CPU.

An observed child is charged while alive. Its already charged subtree credit
then follows wait/reaping up the observed parent tree, reducing later cutime
increments. Unobserved short-lived child CPU remains chargeable.
"""

def generation(row):
    return row['pid'], row['start_ticks']

def snapshot(rows):
    return {generation(row): {k: row.get(k, 0) for k in
            ('pid', 'ppid', 'start_ticks', 'cpu_ticks', 'child_cpu_ticks')}
            for row in rows}

class Accounting:
    def __init__(self, rows, born_since_ticks, budget_key, sample_baseline=False):
        self.last = snapshot(rows)
        self.born = born_since_ticks
        self.key = budget_key
        self.credit = {}
        self.debt = {}
        # A standalone one-sample comparison discounts all already-observed
        # budgeted child CPU. Production samples use a persistent tracker.
        if sample_baseline:
            self.credit = {generation(r): r['cpu_ticks'] + r.get('child_cpu_ticks', 0)
                           for r in rows if r.get(budget_key)}

    def update(self, rows):
        current = snapshot(rows)
        bypid = {r['pid']: key for key, r in self.last.items()}
        gone = set(self.last) - set(current)

        def parent(key):
            p = bypid.get(self.last[key]['ppid'])
            return p if p != key and p is not None and p[1] <= key[1] else None

        # Children disappear with their parent when a whole nested tree is
        # reaped between scans. Transfer deepest credits first, exactly once.
        def depth(key):
            seen = set()
            while key in gone and key not in seen:
                seen.add(key)
                key = parent(key)
            return len(seen)

        for key in sorted(gone, key=depth, reverse=True):
            amount = self.credit.pop(key, 0)
            self.debt.pop(key, None)
            p = parent(key)
            if p is not None and amount:
                self.debt[p] = self.debt.get(p, 0) + amount
                self.credit[p] = self.credit.get(p, 0) + amount

        deltas = {}
        for row in rows:
            if not row.get(self.key):
                continue
            key = generation(row)
            previous = self.last.get(key)
            if previous is not None:
                own = max(0, row['cpu_ticks'] - previous['cpu_ticks'])
                reaped = max(0, row.get('child_cpu_ticks', 0) - previous['child_cpu_ticks'])
            elif row['start_ticks'] >= self.born:
                own, reaped = row['cpu_ticks'], row.get('child_cpu_ticks', 0)
            else:
                own = reaped = 0
            discount = min(reaped, self.debt.get(key, 0))
            self.debt[key] = self.debt.get(key, 0) - discount
            delta = own + reaped - discount
            deltas[key] = delta
            self.credit[key] = self.credit.get(key, 0) + delta
        self.last = current
        return deltas
