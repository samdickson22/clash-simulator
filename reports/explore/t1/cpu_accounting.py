"""Generation-bound CPU deltas with credit for previously observed child CPU.

An observed child is charged while alive. Its already charged subtree credit
then follows wait/reaping up the observed parent tree, reducing later cutime
increments. Unobserved short-lived child CPU remains chargeable.
"""

RULE='OP-7-observed-child-credit-v2'

def generation(row):
    return row['pid'], row['start_ticks']

def snapshot(rows):
    return {generation(row): {k: row.get(k, 0) for k in
            ('pid', 'ppid', 'start_ticks', 'cpu_ticks', 'child_cpu_ticks')}
            for row in rows}

class Accounting:
    def __init__(self, rows, born_since_ticks, budget_key, sample_baseline=False, baseline_all=False):
        self.last = snapshot(rows)
        self.born = born_since_ticks
        self.key = budget_key
        self.credit = {}
        self.debt = {}
        self.debt_lots = {}
        self.scan = 0
        # A standalone one-sample comparison discounts all already-observed
        # budgeted child CPU. Production samples use a persistent tracker.
        if sample_baseline or baseline_all:
            self.credit = {generation(r): r['cpu_ticks'] + r.get('child_cpu_ticks', 0)
                           for r in rows if baseline_all or r.get(budget_key)}

    def update(self, rows):
        self.scan += 1
        # Each credit lot expires independently. Fresh exits cannot renew an
        # older orphan credit and mask unrelated short-lived child CPU forever.
        for key,lots in list(self.debt_lots.items()):
            self.debt_lots[key]=[(amount,end) for amount,end in lots if end>self.scan]
            self.debt[key]=sum(amount for amount,end in self.debt_lots[key])
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
            self.debt_lots.pop(key, None)
            p = parent(key)
            if p is not None and amount:
                self.debt_lots.setdefault(p, []).append((amount,self.scan+3))
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
            remaining=discount;lots=[]
            for amount,end in self.debt_lots.get(key, []):
                paid=min(amount,remaining);remaining-=paid
                if amount>paid:lots.append((amount-paid,end))
            self.debt_lots[key]=lots
            self.debt[key] = self.debt.get(key, 0) - discount
            delta = own + reaped - discount
            deltas[key] = delta
            self.credit[key] = self.credit.get(key, 0) + delta
        self.last = current
        return deltas
