"""Step 5: what a subscriber would actually get.

For every alert with score >= MIN_SCORE we pull the minute price history of
the outcome token and re-price the entry at +1/+5/+15/+60 minutes after the
insider's fill, plus 1 cent of slippage. ROI is per $1, equal stake per alert.
"""
import sys
from concurrent.futures import ThreadPoolExecutor

from backtest import boot_ci
from pm import CLOB, dump, get, load

MIN_SCORE = int(sys.argv[1]) if len(sys.argv) > 1 else 8
DELAYS = (60, 300, 900, 3600)
SLIP = 0.01


def history(a):
    h = get(CLOB, "/prices-history", {
        "market": a["token"], "startTs": a["ts"], "endTs": a["ts"] + 4 * 3600, "fidelity": 1,
    })
    pts = h.get("history", []) if isinstance(h, dict) else []
    return a, [(p["t"], p["p"]) for p in pts]


def main():
    A = [a for a in load("alerts.json") if a["score"] >= MIN_SCORE]
    print("alerts", len(A), flush=True)
    res = []
    with ThreadPoolExecutor(12) as ex:
        for a, pts in ex.map(history, A):
            row = {k: a[k] for k in ("event", "question", "ts", "price", "usd", "won", "score", "category", "age_days")}
            for d in DELAYS:
                p = next((p for t, p in pts if t >= a["ts"] + d), None)
                if p is None:
                    row[f"p{d}"] = None
                    continue
                p = min(0.99, p + SLIP)
                row[f"p{d}"] = p
                row[f"roi{d}"] = a["won"] / p - 1
            res.append(row)
    dump(res, f"follow_s{MIN_SCORE}.json")

    print(f"\n### Follower entry with delay (score ≥ {MIN_SCORE}, +{SLIP*100:.0f}¢ slippage)\n")
    print("| entry | alerts priced | avg entry | win rate | ROI/$ | 95% CI (by event) |\n|---|---|---|---|---|---|")
    base = [r for r in res]
    n = len(base)
    print(f"| insider fill | {n} | {sum(r['price'] for r in base)/n:.3f} | {sum(r['won'] for r in base)/n*100:.1f}% | "
          f"{sum(r['won']/r['price']-1 for r in base)/n*100:+.1f}% | |")
    for d in DELAYS:
        rows = [dict(r, roi=r[f"roi{d}"]) for r in res if r.get(f"p{d}") is not None]
        if not rows:
            continue
        lo, hi = boot_ci(rows)
        k = len(rows)
        print(f"| +{d//60} min | {k} | {sum(r[f'p{d}'] for r in rows)/k:.3f} | {sum(r['won'] for r in rows)/k*100:.1f}% | "
              f"{sum(r['roi'] for r in rows)/k*100:+.1f}% | {lo*100:+.0f}…{hi*100:+.0f}% |")


if __name__ == "__main__":
    main()
