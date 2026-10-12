#!/usr/bin/env python3
"""crisis-etf-radar numeric helpers. Python 3.8+, standard library only.

Subcommands
  ews       Early-warning indicators (rolling variance, lag-1 autocorrelation,
            skewness) with Kendall-tau trends after optional detrending.
            Scheffer et al. 2009 (Nature); Dakos et al. 2012 (PLoS ONE).
  trend     Returns over 1/3/6/12/24 months, realized volatility and its regime,
            ATR proxy, drawdowns, months of positive 12-month trend
            (Moskowitz-Ooi-Pedersen), the Greenwood-Shleifer-You run-up bucket,
            and suggested volatility-width stops.
  doubling  Growth rate and doubling time from counts (cases, outbreaks, events).
  bayes     Posterior probability from a prior and likelihood ratios, capped.
  size      Position size from risk budget, stop distance, volatility cap,
            fractional Kelly and the crisis-book cap.
  brier     Brier score, skill score and calibration table from a forecast log.

Input series CSVs: a date column (YYYY-MM-DD) and a numeric column. A header row
is skipped automatically. Use --col to pick the numeric column (0-based;
default 1). If dates don't parse, the row index is used instead.

Examples
  python signals.py ews freight.csv --detrend gauss --window 0.5 --perm 199
  python signals.py trend prices.csv --k 3
  python signals.py doubling cases.csv --cumulative --last 14
  python signals.py bayes --prior 0.25 --lr 2.5 1.6 0.7 --half 1.6
  python signals.py size --capital 100000 --entry 50 --stop 44 --vol 45 --p 0.55 --target 65
  python signals.py brier log.csv
"""

import argparse
import bisect
import csv
import datetime as dt
import math
import random
import statistics
import sys

# ----------------------------------------------------------------------------- io


def read_series(path, col=1):
    """Return (dates_or_None, values). Skips rows whose value doesn't parse."""
    dates, vals = [], []
    with open(path, newline='', encoding='utf-8-sig') as fh:
        for row in csv.reader(fh):
            if not row or len(row) <= col:
                continue
            try:
                v = float(row[col].replace(',', '').strip())
            except ValueError:
                continue  # header or junk
            d = None
            if col != 0:
                try:
                    d = dt.date.fromisoformat(row[0].strip()[:10])
                except ValueError:
                    d = None
            dates.append(d)
            vals.append(v)
    if not vals:
        sys.exit(f'No numeric data found in column {col} of {path}')
    if any(d is None for d in dates):
        dates = None
    else:
        order = sorted(range(len(vals)), key=lambda i: dates[i])
        dates = [dates[i] for i in order]
        vals = [vals[i] for i in order]
    return dates, vals


def fmt_pct(x, nd=1):
    return 'n/a' if x is None else f'{x * 100:.{nd}f}%'


# ----------------------------------------------------------------------------- stats


def kendall_tau(y):
    """Kendall tau-b of y against its index (time)."""
    n = len(y)
    if n < 3:
        return float('nan')
    conc = disc = ties_y = 0
    for i in range(n - 1):
        yi = y[i]
        for j in range(i + 1, n):
            d = y[j] - yi
            if d > 0:
                conc += 1
            elif d < 0:
                disc += 1
            else:
                ties_y += 1
    n0 = n * (n - 1) / 2
    denom = math.sqrt(n0 * (n0 - ties_y))
    return (conc - disc) / denom if denom else float('nan')


def detrend(x, method, bw):
    n = len(x)
    if method == 'none':
        return list(x)
    if method == 'diff':
        return [x[i] - x[i - 1] for i in range(1, n)]
    if method == 'logdiff':
        if min(x) <= 0:
            sys.exit('logdiff needs strictly positive values')
        return [math.log(x[i]) - math.log(x[i - 1]) for i in range(1, n)]
    if method == 'ma':
        h = max(1, int(bw))
        out = []
        for i in range(n):
            lo, hi = max(0, i - h), min(n, i + h + 1)
            out.append(x[i] - sum(x[lo:hi]) / (hi - lo))
        return out
    if method == 'gauss':
        h = max(1.0, float(bw))
        cut = int(4 * h)
        out = []
        for i in range(n):
            lo, hi = max(0, i - cut), min(n, i + cut + 1)
            wsum = vsum = 0.0
            for j in range(lo, hi):
                w = math.exp(-0.5 * ((i - j) / h) ** 2)
                wsum += w
                vsum += w * x[j]
            out.append(x[i] - vsum / wsum)
        return out
    sys.exit(f'unknown detrend method {method}')


def rolling_indicators(r, w):
    """Rolling variance, AC1 and skewness via prefix sums (O(n)). Returns 3 lists."""
    n = len(r)
    mu = sum(r) / n
    sd = statistics.pstdev(r) or 1.0
    z = [
        (v - mu) / sd for v in r
    ]  # scale for numerical stability; trends unaffected
    p1, p2, p3, pab = [0.0], [0.0], [0.0], [0.0]
    for i, v in enumerate(z):
        p1.append(p1[-1] + v)
        p2.append(p2[-1] + v * v)
        p3.append(p3[-1] + v * v * v)
        pab.append(pab[-1] + (v * z[i + 1] if i + 1 < n else 0.0))
    var_l, ac1_l, skew_l = [], [], []
    for i in range(0, n - w + 1):
        s1 = p1[i + w] - p1[i]
        s2 = p2[i + w] - p2[i]
        s3 = p3[i + w] - p3[i]
        m = s1 / w
        m2 = s2 / w - m * m
        m3 = s3 / w - 3 * m * s2 / w + 2 * m**3
        var_l.append(m2 * w / (w - 1) * sd * sd)
        skew_l.append(m3 / m2**1.5 if m2 > 1e-12 else 0.0)
        k = w - 1  # number of lag pairs in the window
        sa = p1[i + w - 1] - p1[i]
        sb = p1[i + w] - p1[i + 1]
        saa = p2[i + w - 1] - p2[i]
        sbb = p2[i + w] - p2[i + 1]
        sab = pab[i + w - 1] - pab[i]
        cov = sab - sa * sb / k
        va = saa - sa * sa / k
        vb = sbb - sb * sb / k
        ac1_l.append(
            cov / math.sqrt(va * vb) if va > 1e-12 and vb > 1e-12 else 0.0
        )
    return var_l, ac1_l, skew_l


# ----------------------------------------------------------------------------- ews


def cmd_ews(a):
    dates, x = read_series(a.file, a.col)
    if a.log:
        if min(x) <= 0:
            sys.exit('--log needs strictly positive values')
        x = [math.log(v) for v in x]
    bw = a.bw if a.bw else max(3, round(0.1 * len(x)))
    r = detrend(x, a.detrend, bw)
    n = len(r)
    w = int(a.window * n) if a.window <= 1 else int(a.window)
    if w < 10 or w > n - 5:
        sys.exit(
            f'window {w} unsuitable for n={n}; need 10 <= w <= n-5 (try more data or another --window)'
        )
    var_l, ac1_l, skew_l = rolling_indicators(r, w)
    taus = {
        'variance': kendall_tau(var_l),
        'ac1': kendall_tau(ac1_l),
        'skewness': kendall_tau(skew_l),
    }
    pvals = {}
    if a.perm > 0:
        rng = random.Random(a.seed)
        exceed = {k: 0 for k in taus}
        for _ in range(a.perm):
            s = r[:]
            rng.shuffle(s)
            vl, al, sl = rolling_indicators(s, w)
            for key, ser in (('variance', vl), ('ac1', al), ('skewness', sl)):
                t = kendall_tau(ser)
                if key == 'skewness':
                    if abs(t) >= abs(taus[key]):
                        exceed[key] += 1
                elif t >= taus[key]:
                    exceed[key] += 1
        pvals = {k: (exceed[k] + 1) / (a.perm + 1) for k in taus}

    span = (
        f'{dates[0]} .. {dates[-1]}' if dates else f'index 0 .. {len(x) - 1}'
    )
    print(f'Early-warning indicators: {a.file}')
    print(
        f'  n={len(x)} ({span}), detrend={a.detrend}'
        + (f' bw={bw}' if a.detrend in ('ma', 'gauss') else '')
        + f', window={w} points, log={a.log}'
    )
    print(
        f'  {"indicator":<10} {"first":>10} {"last":>10} {"Kendall tau":>12}'
        + ('  p(perm)' if pvals else '')
    )
    for key, ser in (
        ('variance', var_l),
        ('ac1', ac1_l),
        ('skewness', skew_l),
    ):
        line = (
            f'  {key:<10} {ser[0]:>10.4g} {ser[-1]:>10.4g} {taus[key]:>12.2f}'
        )
        if pvals:
            line += f'  {pvals[key]:.3f}'
        print(line)
    rising = [
        k
        for k in ('variance', 'ac1')
        if taus[k] > 0.5 and (not pvals or pvals[k] < 0.1)
    ]
    print('\nRead:')
    if len(rising) == 2:
        print(
            '  Variance AND AC1 rising strongly: consistent with critical slowing down. '
            'Use as a moderate signal at most (LR ~1.6), and only if the mechanism fits a slow push '
            'toward a threshold.'
        )
    elif rising:
        print(
            f'  Only {rising[0]} rising strongly: weak signal (LR ~1.2) at most.'
        )
    else:
        print(
            '  No strong rising trend in variance/AC1: no early-warning evidence (LR 1.0). '
            'This does NOT rule out a sudden external shock.'
        )
    if abs(taus['skewness']) > 0.5:
        print(
            f'  Skewness trending ({"up" if taus["skewness"] > 0 else "down"}): flickering or asymmetry '
            'toward an alternative state is possible; check which tail is growing.'
        )
    if not pvals:
        print(
            '  (No permutation test run; add --perm 199 for a rough significance check.)'
        )


# ----------------------------------------------------------------------------- trend


def _value_at_or_before(dates, vals, target):
    i = bisect.bisect_right(dates, target) - 1
    return (dates[i], vals[i]) if i >= 0 else (None, None)


def cmd_trend(a):
    dates, p = read_series(a.file, a.col)
    n = len(p)
    if n < 30:
        sys.exit('need at least 30 observations')
    if min(p) <= 0:
        sys.exit('prices must be positive')
    if dates:
        gaps = sorted((dates[i] - dates[i - 1]).days for i in range(1, n))
        med_gap = gaps[len(gaps) // 2] or 1
    else:
        med_gap = 1
        base = dt.date(2000, 1, 1)
        dates = [
            base + dt.timedelta(days=round(i * 365.25 / 252)) for i in range(n)
        ]
    ppy = 252 if med_gap <= 3 else (52 if med_gap <= 10 else 12)
    last_d, last_p = dates[-1], p[-1]

    print(
        f'Trend report: {a.file}  (last {last_d} = {last_p:g}; ~{ppy} obs/year)'
    )
    print('  Returns:')
    rets = {}
    for m in (1, 3, 6, 12, 24):
        d0, p0 = _value_at_or_before(
            dates, p, last_d - dt.timedelta(days=round(m * 30.44))
        )
        rets[m] = (last_p / p0 - 1) if p0 else None
        print(
            f'    {m:>2}m: {fmt_pct(rets[m]):>9}'
            + (f'  (from {d0} = {p0:g})' if p0 else '  (insufficient history)')
        )

    lr = [math.log(p[i] / p[i - 1]) for i in range(1, n)]
    win_s = {252: 20, 52: 8, 12: 6}[ppy]
    win_l = {252: 60, 52: 26, 12: 12}[ppy]

    def ann_vol(seq):
        return statistics.stdev(seq) * math.sqrt(ppy) if len(seq) > 2 else None

    v_s, v_l = ann_vol(lr[-win_s:]), ann_vol(lr[-win_l:])
    roll = [ann_vol(lr[i - win_s : i]) for i in range(win_s, len(lr) + 1)]
    roll_1y = [v for v in roll[-ppy:] if v is not None]
    med_1y = statistics.median(roll_1y) if roll_1y else None
    regime = (v_s / med_1y) if (v_s and med_1y) else None
    print(
        f'  Realized vol (annualized): short {fmt_pct(v_s)}, long {fmt_pct(v_l)}, '
        f'1y median of short {fmt_pct(med_1y)}, regime ratio {regime:.2f}'
        if regime
        else f'  Realized vol (annualized): short {fmt_pct(v_s)}, long {fmt_pct(v_l)}'
    )

    abs_moves = [abs(p[i] - p[i - 1]) for i in range(max(1, n - win_s), n)]
    atr = sum(abs_moves) / len(abs_moves)
    print(
        f'  ATR proxy (mean |close-to-close| over last {len(abs_moves)} obs): {atr:.4g} '
        f'= {atr / last_p * 100:.2f}% of price'
    )

    peak = max(p)
    hi_52_d, hi_52 = None, None
    for d, v in zip(dates, p):
        if d >= last_d - dt.timedelta(days=365) and (
            hi_52 is None or v > hi_52
        ):
            hi_52_d, hi_52 = d, v
    print(
        f'  Drawdown from all-sample high {peak:g}: {fmt_pct(last_p / peak - 1)}; '
        f'from 52w high {hi_52:g} ({hi_52_d}): {fmt_pct(last_p / hi_52 - 1)}'
    )

    # months of consecutive positive 12m return, counted back from the end
    start_run = None
    for i in range(n - 1, -1, -1):
        d0, p0 = _value_at_or_before(
            dates, p, dates[i] - dt.timedelta(days=365)
        )
        if p0 is None or p[i] / p0 - 1 <= 0:
            break
        start_run = dates[i]
    run_months = ((last_d - start_run).days / 30.44) if start_run else 0.0
    sign = 'positive' if (rets[12] or 0) > 0 else 'negative/flat'
    print(
        f'  12m trend sign: {sign}; positive-12m run length: {run_months:.1f} months'
    )

    r24 = rets[24]
    if r24 is None:
        gsy = 'insufficient history for the 2-year run-up'
    elif r24 >= 1.5:
        gsy = 'run-up >=150%: GSY crash (-40% in 2y) probability ~80%'
    elif r24 >= 1.0:
        gsy = 'run-up >=100%: GSY crash probability ~53%'
    elif r24 >= 0.5:
        gsy = 'run-up >=50%: GSY crash probability ~20%'
    else:
        gsy = 'run-up <50%: below GSY bubble thresholds'
    accel = None
    if rets[12] is not None and r24 is not None:
        prior12 = (1 + r24) / (1 + rets[12]) - 1
        accel = rets[12] > prior12 > -1 and rets[12] > 0
        gsy += (
            f'; last 12m {fmt_pct(rets[12])} vs prior 12m {fmt_pct(prior12)}'
            + (' (accelerating)' if accel else '')
        )
    print(
        f'  Greenwood-Shleifer-You (industry-level evidence; use as an analogue for ETFs): {gsy}'
    )

    k = a.k
    hi_since = max(
        v
        for d, v in zip(dates, p)
        if (a.since is None or d >= dt.date.fromisoformat(a.since))
    )
    print(f'  Suggested vol-width stops (k={k} x ATR, close basis):')
    print(
        f'    initial from last close: {last_p - k * atr:.4g} ({-k * atr / last_p * 100:.1f}%)'
    )
    print(
        f'    trailing from highest close{" since " + a.since if a.since else ""} {hi_since:g}: '
        f'{hi_since - k * atr:.4g}'
    )

    print('  Timing-table hints:')
    if run_months == 0:
        r10 = (
            'L (12m trend broken or negative)' if (rets[12] or 0) <= 0 else 'N'
        )
    elif run_months <= 6:
        r10 = 'E (1-6 months into a positive 12m trend)'
    elif run_months <= 12:
        r10 = 'N (6-12 months)'
    else:
        r10 = 'L (>12 months: TSMOM partial-reversal zone)'
    if regime is None:
        r11 = 'n/a'
    elif regime > 2:
        r11 = 'L (short-term vol >2x its 1y median)'
    elif regime >= 1.2:
        r11 = 'E (vol rising from base)'
    elif v_l and v_s and v_s < 0.7 * v_l and med_1y and v_l > 1.5 * med_1y:
        r11 = 'L (vol collapsing after a spike)'
    else:
        r11 = 'N'
    print(f'    row 10 trend age: {r10}')
    print(f'    row 11 vol regime: {r11}')


# ----------------------------------------------------------------------------- doubling


def cmd_doubling(a):
    dates, y = read_series(a.file, a.col)
    if not a.cumulative:
        # smooth daily new counts with a trailing 7-observation sum
        k = min(7, len(y))
        y = [sum(y[max(0, i - k + 1) : i + 1]) for i in range(len(y))]
    t = [(d - dates[0]).days for d in dates] if dates else list(range(len(y)))
    pts = [(ti, math.log(yi)) for ti, yi in zip(t, y) if yi > 0][-a.last :]
    if len(pts) < 4:
        sys.exit('need at least 4 positive observations in the fitting window')
    xs, ls = zip(*pts)
    mx, ml = sum(xs) / len(xs), sum(ls) / len(ls)
    sxx = sum((x - mx) ** 2 for x in xs)
    r = sum((x - mx) * (l - ml) for x, l in zip(xs, ls)) / sxx
    ss_tot = sum((l - ml) ** 2 for l in ls)
    ss_res = sum((l - (ml + r * (x - mx))) ** 2 for x, l in zip(xs, ls))
    r2 = 1 - ss_res / ss_tot if ss_tot else float('nan')
    unit = 'day' if dates else 'step'
    print(
        f'Growth fit on last {len(pts)} points ({"cumulative" if a.cumulative else "7-obs rolling sum of new"} counts)'
    )
    print(
        f'  growth rate r = {r:.4f} per {unit} ({(math.exp(r) - 1) * 100:.1f}% per {unit}), R^2 = {r2:.2f}'
    )
    if r > 0:
        print(f'  doubling time = {math.log(2) / r:.1f} {unit}s')
    elif r < 0:
        print(f'  halving time = {math.log(2) / -r:.1f} {unit}s (declining)')
    last = math.exp(ml + r * (xs[-1] - mx))
    for h in (7, 14, 28):
        print(
            f'  if the trend holds, +{h} {unit}s: ~{last * math.exp(r * h):,.0f} (from fitted {last:,.0f})'
        )
    print(
        '  Note: reporting lags and testing changes distort counts; exported cases abroad are a cross-check.'
    )


# ----------------------------------------------------------------------------- bayes


def cmd_bayes(a):
    if not 0 < a.prior < 1:
        sys.exit('prior must be strictly between 0 and 1')
    lrs = list(a.lr or [])
    half = list(a.half or [])
    eff = [x for x in lrs] + [math.sqrt(x) for x in half]
    if any(x <= 0 for x in eff):
        sys.exit('likelihood ratios must be > 0')
    prod = math.prod(eff) if eff else 1.0
    capped = min(max(prod, 1 / a.cap), a.cap)
    odds0 = a.prior / (1 - a.prior)
    odds1 = odds0 * capped
    post = odds1 / (1 + odds1)
    print(f'Prior p = {a.prior:.3f} (odds {odds0:.3f})')
    if lrs:
        print('  full-weight LRs: ' + ', '.join(f'x{x:g}' for x in lrs))
    if half:
        print(
            '  half-weight (single-source) LRs: '
            + ', '.join(f'x{x:g} -> x{math.sqrt(x):.2f}' for x in half)
        )
    print(
        f'  combined LR x{prod:.2f}'
        + (f' capped to x{capped:.2f}' if capped != prod else '')
    )
    print(f'Posterior p = {post:.3f}')
    if post > 0.7:
        print(
            '  Check: >70% needs hard, multi-source evidence and a clear reason the market is missing it.'
        )


# ----------------------------------------------------------------------------- size


def cmd_size(a):
    entry = a.entry
    if a.stop is not None:
        stop = a.stop
    elif a.stop_pct is not None:
        stop = entry * (1 - a.stop_pct / 100)
    elif a.atr is not None:
        stop = entry - a.k * a.atr
    else:
        sys.exit('give --stop, --stop-pct, or --atr (with --k)')
    dist = abs(entry - stop) / entry
    if dist <= 0:
        sys.exit('stop distance must be > 0')
    side = 'long' if stop < entry else 'short'
    risk_frac = a.risk_pct / 100
    rows = []
    pos_risk = a.capital * risk_frac / dist
    rows.append(
        (
            'risk budget',
            pos_risk,
            f'{a.risk_pct}% of capital / {dist * 100:.1f}% stop distance',
        )
    )
    if a.vol:
        pos_vol = a.capital * (a.vol_budget / 100) / (a.vol / 100)
        rows.append(
            (
                'vol cap',
                pos_vol,
                f'{a.vol_budget}% idea vol budget / {a.vol}% instrument vol',
            )
        )
    kelly_note = None
    if a.p is not None and a.target is not None:
        b = abs(a.target - entry) / abs(entry - stop)
        f_star = a.p - (1 - a.p) / b
        ev_r = a.p * b - (1 - a.p)
        kelly_note = (b, f_star, ev_r)
        if f_star <= 0:
            rows.append(
                (
                    'Kelly cap',
                    0.0,
                    f'f* = {f_star:.3f} <= 0 -> no edge at these odds',
                )
            )
        else:
            pos_kelly = a.capital * a.kelly_frac * f_star / dist
            rows.append(
                (
                    'Kelly cap',
                    pos_kelly,
                    f'{a.kelly_frac} x f*={f_star:.3f} of capital at risk / stop dist',
                )
            )
    book_left = a.capital * max(0.0, a.book_cap - a.book_used) / 100
    rows.append(
        (
            'crisis-book cap',
            book_left,
            f'{a.book_cap}% cap - {a.book_used}% already used',
        )
    )
    binding = min(rows, key=lambda r: r[1])
    pos = binding[1]
    units = pos / entry if a.fractional else math.floor(pos / entry)
    pos_eff = units * entry
    print(
        f'Sizing ({side}): entry {entry:g}, stop {stop:.4g} ({dist * 100:.1f}% away), capital {a.capital:,.0f}'
    )
    for name, val, why in rows:
        mark = '  <- binding' if (name, val, why) == binding else ''
        print(f'  {name:<16} {val:>14,.0f}   {why}{mark}')
    print(
        f'Position: {units:,.{4 if a.fractional else 0}f} units = {pos_eff:,.0f} '
        f'({pos_eff / a.capital * 100:.2f}% of capital); risk at stop {pos_eff * dist:,.0f} '
        f'({pos_eff * dist / a.capital * 100:.2f}% of capital)'
    )
    if a.tranches > 1 and units:
        per = units / a.tranches
        print(
            f'  In {a.tranches} tranches: ~{per:,.{4 if a.fractional else 0}f} units each '
            '(add only on the stated confirmations; never after a thesis-break fact)'
        )
    if kelly_note:
        b, f_star, ev_r = kelly_note
        print(
            f'Edge: payoff ratio b = {b:.2f}, p = {a.p}, EV per unit risk = {ev_r:+.2f}R'
            + ('  (thin: prefer > +0.3R)' if 0 < ev_r < 0.3 else '')
            + ('  (negative: no trade)' if ev_r <= 0 else '')
        )
    if binding[0] in ('vol cap', 'Kelly cap') and binding[1] < 0.5 * pos_risk:
        print(
            'Note: the binding cap is well below the risk budget; the instrument is very volatile or the edge thin.'
        )


# ----------------------------------------------------------------------------- brier


def cmd_brier(a):
    with open(a.file, newline='', encoding='utf-8-sig') as fh:
        rows = list(csv.reader(fh))
    if not rows:
        sys.exit('empty file')
    header = [h.strip().lower() for h in rows[0]]
    pc, oc = a.pcol, a.ocol
    body = rows
    if pc is None or oc is None:
        if 'p' in header and 'outcome' in header:
            pc, oc = header.index('p'), header.index('outcome')
            body = rows[1:]
        else:
            sys.exit(
                "could not find 'p' and 'outcome' headers; pass --pcol and --ocol"
            )
    pairs = []
    for r in body:
        try:
            p = float(r[pc])
            o = r[oc].strip().lower()
        except (ValueError, IndexError):
            continue
        if o in ('', 'na', 'open', 'pending'):
            continue
        o = (
            1.0
            if o in ('1', 'yes', 'true', 'y')
            else 0.0
            if o in ('0', 'no', 'false', 'n')
            else None
        )
        if o is None:
            continue
        pairs.append((p, o))
    if not pairs:
        sys.exit('no resolved forecasts found')
    n = len(pairs)
    brier = sum((p - o) ** 2 for p, o in pairs) / n
    base = sum(o for _, o in pairs) / n
    ref = base * (1 - base)
    print(f"Resolved forecasts: {n}; base rate of 'yes': {base:.2f}")
    print(f'Brier score: {brier:.3f}  (0 = perfect, 0.25 = always saying 50%)')
    if ref > 0:
        print(
            f'Brier skill vs always forecasting the base rate: {1 - brier / ref:+.2f}  (>0 = adds value)'
        )
    print('Calibration (bin: n, mean forecast, observed frequency):')
    bins = {}
    for p, o in pairs:
        bins.setdefault(min(max(int(p * 10 + 1e-9), 0), 9), []).append((p, o))
    for k in sorted(bins):
        b = bins[k]
        print(
            f'  {k / 10:.1f}-{(k + 1) / 10:.1f}: n={len(b):>3}, forecast {sum(p for p, _ in b) / len(b):.2f}, '
            f'observed {sum(o for _, o in b) / len(b):.2f}'
        )
    if n < 20:
        print(
            'Note: fewer than 20 resolved forecasts; calibration is noise at this sample size.'
        )


# ----------------------------------------------------------------------------- cli


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest='cmd', required=True)

    e = sub.add_parser(
        'ews', help='early-warning indicators with Kendall tau trends'
    )
    e.add_argument('file')
    e.add_argument('--col', type=int, default=1)
    e.add_argument(
        '--detrend',
        choices=['none', 'diff', 'logdiff', 'ma', 'gauss'],
        default='gauss',
    )
    e.add_argument(
        '--bw',
        type=float,
        default=None,
        help='bandwidth for ma/gauss (points; default 10%% of n)',
    )
    e.add_argument(
        '--window',
        type=float,
        default=0.5,
        help='rolling window: fraction of n (<=1) or points',
    )
    e.add_argument(
        '--log', action='store_true', help='take logs before detrending'
    )
    e.add_argument(
        '--perm', type=int, default=0, help='permutation-test reps (e.g. 199)'
    )
    e.add_argument('--seed', type=int, default=7)
    e.set_defaults(func=cmd_ews)

    t = sub.add_parser(
        'trend',
        help='returns, vol, ATR, drawdown, trend age, GSY bucket, stops',
    )
    t.add_argument('file')
    t.add_argument('--col', type=int, default=1)
    t.add_argument(
        '--k', type=float, default=3.0, help='ATR multiple for stops'
    )
    t.add_argument(
        '--since',
        default=None,
        help='entry date YYYY-MM-DD for the trailing-stop high',
    )
    t.set_defaults(func=cmd_trend)

    d = sub.add_parser(
        'doubling', help='growth rate and doubling time from counts'
    )
    d.add_argument('file')
    d.add_argument('--col', type=int, default=1)
    d.add_argument(
        '--cumulative',
        action='store_true',
        help='counts are cumulative (default: new per period)',
    )
    d.add_argument(
        '--last', type=int, default=14, help='fit on the last N points'
    )
    d.set_defaults(func=cmd_doubling)

    b = sub.add_parser(
        'bayes', help='posterior from prior and likelihood ratios'
    )
    b.add_argument('--prior', type=float, required=True)
    b.add_argument(
        '--lr', type=float, nargs='*', help='full-weight likelihood ratios'
    )
    b.add_argument(
        '--half',
        type=float,
        nargs='*',
        help='single-source LRs (square-rooted)',
    )
    b.add_argument('--cap', type=float, default=10.0)
    b.set_defaults(func=cmd_bayes)

    s = sub.add_parser(
        'size',
        help='position size from risk budget, vol cap, Kelly and book cap',
    )
    s.add_argument(
        '--capital', type=float, required=True, help='portfolio value'
    )
    s.add_argument('--entry', type=float, required=True)
    s.add_argument('--stop', type=float)
    s.add_argument('--stop-pct', type=float, help='stop distance in %% (long)')
    s.add_argument(
        '--atr', type=float, help='ATR in price units (stop = entry - k*ATR)'
    )
    s.add_argument('--k', type=float, default=3.0)
    s.add_argument(
        '--risk-pct',
        type=float,
        default=0.75,
        help='%% of capital lost if stop hits',
    )
    s.add_argument('--vol', type=float, help='instrument annualized vol in %%')
    s.add_argument(
        '--vol-budget',
        type=float,
        default=2.0,
        help='idea vol budget, %% of capital annualized',
    )
    s.add_argument(
        '--p', type=float, help='probability thesis pays (for Kelly)'
    )
    s.add_argument(
        '--target', type=float, help='target price (for Kelly payoff ratio)'
    )
    s.add_argument('--kelly-frac', type=float, default=0.25)
    s.add_argument(
        '--book-cap',
        type=float,
        default=10.0,
        help='crisis-book cap, %% of capital',
    )
    s.add_argument(
        '--book-used',
        type=float,
        default=0.0,
        help='%% of capital already in crisis trades',
    )
    s.add_argument('--tranches', type=int, default=3)
    s.add_argument(
        '--fractional', action='store_true', help='allow fractional units'
    )
    s.set_defaults(func=cmd_size)

    r = sub.add_parser(
        'brier',
        help='Brier score and calibration from a log CSV with p,outcome columns',
    )
    r.add_argument('file')
    r.add_argument('--pcol', type=int)
    r.add_argument('--ocol', type=int)
    r.set_defaults(func=cmd_brier)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
