"""Step 3: wallet history as of each candidate trade (no look-ahead).

For every wallet behind a candidate trade we pull its first 500 activities
(ascending). Everything computed from them uses only events strictly before
the trade, so the features are what a live bot would have known.
"""
import bisect
from concurrent.futures import ThreadPoolExecutor

from pm import DATA_API, dump, get, load

MAX_PRICE = 0.6   # the insider pattern is money on the unlikely side
FIRST_N = 500
WORKERS = 12


def first_activity(wallet):
    page = get(DATA_API, "/activity", {
        "user": wallet, "limit": FIRST_N, "sortBy": "TIMESTAMP", "sortDirection": "ASC",
    })
    if not isinstance(page, list):
        return wallet, None
    return wallet, [(int(a["timestamp"]), a["type"], a.get("conditionId"), float(a.get("usdcSize") or 0)) for a in page]


def main():
    trades = load("trades.json")
    cand = [t for t in trades if t["price"] <= MAX_PRICE]
    wallets = sorted({t["wallet"] for t in cand})
    print("candidate trades", len(cand), "wallets", len(wallets), flush=True)

    hist, done = {}, 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for w, h in ex.map(first_activity, wallets):
            hist[w] = h
            done += 1
            if done % 2000 == 0:
                print(done, "wallets", flush=True)

    rows = []
    for t in cand:
        h = hist.get(t["wallet"])
        if not h:
            continue
        ts_list = [a[0] for a in h]
        before = h[:bisect.bisect_left(ts_list, t["ts"])]
        full = len(h) == FIRST_N and len(before) == len(h)  # history longer than we fetched
        trades_before = [a for a in before if a[1] == "TRADE"]
        vol_before = sum(a[3] for a in trades_before)
        vol_here = sum(a[3] for a in trades_before if a[2] == t["cid"])
        rows.append({
            **t,
            "age_days": (t["ts"] - h[0][0]) / 86400,
            "prior_trades": None if full else len(trades_before),
            "prior_markets": None if full else len({a[2] for a in trades_before}),
            "share_here": None if full or vol_before == 0 else vol_here / vol_before,
        })
    dump(rows, "features.json")
    print("feature rows", len(rows))


if __name__ == "__main__":
    main()
