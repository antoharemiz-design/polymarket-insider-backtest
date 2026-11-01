"""Step 4: score every candidate alert with the rule fixed BEFORE seeing data
(the weights from the earlier write-up, minus the funding-cluster signal we did
not collect) and measure what following it would have returned.

One alert = the first qualifying trade of a wallet on a market outcome; later
fills of the same position are not new alerts.
ROI is per $1 placed at the insider's own fill price (an upper bound for a
follower); follow.py re-prices it with a realistic delay.
"""
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

from pm import dump, load

INFO_CATS = {"geopolitics", "politics", "business", "culture"}


def iso_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def score(r):
    s = 0
    s += 3 if r["usd"] >= 20000 else 2 if r["usd"] >= 5000 else 0
    s += 2 if r["price"] <= 0.15 else 1 if r["price"] <= 0.30 else 0
    s += 3 if r["age_days"] < 3 else 1 if r["age_days"] < 14 else 0
    if r["prior_trades"] is not None and r["prior_trades"] <= 3:
        s += 1
    if r["prior_trades"] == 0 or (r["share_here"] is not None and r["share_here"] >= 0.8):
        s += 1
    if r["category"] in INFO_CATS:
        s += 1
    if 0 <= r["days_to_end"] <= 7:
        s += 1
    return s


def alerts():
    markets = {m["conditionId"]: m for m in load("markets.json")}
    rows = load("features.json")
    rows.sort(key=lambda r: r["ts"])
    seen, out = set(), []
    for r in rows:
        m = markets.get(r["cid"])
        if not m or r["orig_side"] != "BUY":  # a SELL is someone exiting, not a bet
            continue
        key = (r["wallet"], r["cid"], r["outcome"])
        if key in seen:
            continue
        seen.add(key)
        r = dict(r)
        q = (m["question"] or "").lower()
        r["category"] = ("weather" if "temperature" in q else
                         "tweets" if "tweets" in q or "post " in q and "times" in q else m["category"])
        r["event"] = m["eventSlug"] or m["slug"]
        r["question"] = m["question"]
        r["token"] = m["tokens"][r["outcome"]]
        r["won"] = int(r["outcome"] == m["winner"])
        r["roi"] = r["won"] / r["price"] - 1 if r["price"] > 0 else 0
        r["days_to_end"] = (iso_ts(m["endDate"]) - r["ts"]) / 86400 if m.get("endDate") else 999
        r["month"] = datetime.fromtimestamp(r["ts"], timezone.utc).strftime("%Y-%m")
        r["score"] = score(r)
        out.append(r)
    return out


def boot_ci(rows, key="roi", iters=2000, seed=1):
    """95% CI of the mean, resampling whole events (trades in one event are correlated)."""
    by_ev = defaultdict(list)
    for r in rows:
        by_ev[r["event"]].append(r[key])
    evs = list(by_ev.values())
    if len(evs) < 5:
        return None, None
    rnd = random.Random(seed)
    means = []
    for _ in range(iters):
        s = n = 0
        for _ in range(len(evs)):
            e = evs[rnd.randrange(len(evs))]
            s += sum(e)
            n += len(e)
        means.append(s / n)
    means.sort()
    return means[int(0.025 * iters)], means[int(0.975 * iters)]


def stats(rows):
    if not rows:
        return None
    n = len(rows)
    win = sum(r["won"] for r in rows) / n
    px = sum(r["price"] for r in rows) / n
    roi = sum(r["roi"] for r in rows) / n
    lo, hi = boot_ci(rows)
    return {"n": n, "events": len({r["event"] for r in rows}), "win": win, "avg_price": px,
            "edge": win - px, "roi": roi, "roi_lo": lo, "roi_hi": hi}


def fmt(name, s):
    if not s:
        return f"| {name} | 0 | | | | | | |"
    ci = f"{s['roi_lo']*100:+.0f}…{s['roi_hi']*100:+.0f}%" if s["roi_lo"] is not None else "n/a"
    return (f"| {name} | {s['n']} | {s['events']} | {s['win']*100:.1f}% | {s['avg_price']:.3f} | "
            f"{s['edge']*100:+.1f} pp | {s['roi']*100:+.1f}% | {ci} |")


HEAD = "| group | alerts | events | win rate | avg price | edge | ROI/$ | 95% CI (by event) |\n|---|---|---|---|---|---|---|---|"


def table(title, groups):
    lines = [f"\n### {title}\n", HEAD]
    for name, rows in groups:
        lines.append(fmt(name, stats(rows)))
    return "\n".join(lines)


def main():
    A = alerts()
    dump(A, "alerts.json")
    rep = [f"# Backtest: insider-pattern alerts on Polymarket\n\nAlerts (deduplicated wallet×market×outcome, taker BUY, price ≤ 0.60, ≥ $2k): {len(A)}"]

    rep.append(table("By score (rule fixed in advance)", [
        ("score ≥ 10", [r for r in A if r["score"] >= 10]),
        ("score 8–9", [r for r in A if 8 <= r["score"] <= 9]),
        ("score 5–7", [r for r in A if 5 <= r["score"] <= 7]),
        ("score ≤ 4", [r for r in A if r["score"] <= 4]),
        ("ALL (baseline)", A),
    ]))
    rep.append(table("Wallet age at trade", [
        ("< 1 day", [r for r in A if r["age_days"] < 1]),
        ("1–3 days", [r for r in A if 1 <= r["age_days"] < 3]),
        ("3–14 days", [r for r in A if 3 <= r["age_days"] < 14]),
        ("14–90 days", [r for r in A if 14 <= r["age_days"] < 90]),
        ("> 90 days", [r for r in A if r["age_days"] >= 90]),
    ]))
    rep.append(table("Fresh wallet (< 3 days) by price", [
        (f"fresh, price ≤ {b}", [r for r in A if r["age_days"] < 3 and a < r["price"] <= b])
        for a, b in ((0, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 0.60))
    ] + [
        (f"old, price ≤ {b}", [r for r in A if r["age_days"] >= 14 and a < r["price"] <= b])
        for a, b in ((0, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 0.60))
    ]))
    rep.append(table("Size", [
        ("$2–5k", [r for r in A if r["usd"] < 5000]),
        ("$5–20k", [r for r in A if 5000 <= r["usd"] < 20000]),
        ("$20–100k", [r for r in A if 20000 <= r["usd"] < 100000]),
        ("≥ $100k", [r for r in A if r["usd"] >= 100000]),
    ]))
    cats = sorted({r["category"] for r in A})
    rep.append(table("Category, score ≥ 8", [(c, [r for r in A if r["category"] == c and r["score"] >= 8]) for c in cats]))
    rep.append(table("Category, all", [(c, [r for r in A if r["category"] == c]) for c in cats]))
    months = sorted({r["month"] for r in A})
    rep.append(table("Stability by month, score ≥ 8", [(mo, [r for r in A if r["month"] == mo and r["score"] >= 8]) for mo in months]))

    top = sorted([r for r in A if r["score"] >= 8], key=lambda r: -r["usd"] * (r["roi"]))[:15]
    rep.append("\n### Biggest winners among score ≥ 8\n\n| date | market | price | $ | age d | won |\n|---|---|---|---|---|---|")
    for r in top:
        rep.append(f"| {datetime.fromtimestamp(r['ts'], timezone.utc):%Y-%m-%d} | {r['question'][:70]} | {r['price']:.3f} | {r['usd']:,.0f} | {r['age_days']:.1f} | {r['won']} |")

    text = "\n".join(rep)
    open(sys.argv[1] if len(sys.argv) > 1 else "report_raw.md", "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
