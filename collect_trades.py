"""Step 2: large taker trades (>= $2k) in every sampled market.

A SELL of outcome i at price p is treated as a BUY of the other outcome at
1 - p, so every row is "someone put money on outcome X at price P".
"""
import random
from concurrent.futures import ThreadPoolExecutor

from pm import DATA_API, dump, get, load

MIN_CASH = 2000
MAX_SPORTS = 3000  # sports/esports markets are sampled, everything else is kept
WORKERS = 10


def fetch(m):
    rows, off = [], 0
    while off <= 10000:
        page = get(DATA_API, "/trades", {
            "market": m["conditionId"], "filterType": "CASH", "filterAmount": MIN_CASH,
            "takerOnly": "true", "limit": 1000, "offset": off,
        })
        if not isinstance(page, list) or not page:
            break
        rows += page
        if len(page) < 1000:
            break
        off += 1000
    out = []
    for t in rows:
        p, idx = float(t["price"]), int(t["outcomeIndex"])
        if t["side"] == "SELL":
            p, idx = 1 - p, 1 - idx
        out.append({
            "cid": m["conditionId"], "wallet": t["proxyWallet"], "ts": int(t["timestamp"]),
            "price": round(p, 4), "outcome": idx, "usd": float(t["size"]) * float(t["price"]),
            "orig_side": t["side"], "tx": t.get("transactionHash"),
        })
    return out, len(rows) >= 10000


def main():
    markets = [m for m in load("markets.json") if m["category"] != "price"]
    random.seed(7)
    sports = [m for m in markets if m["category"] in ("sports", "esports")]
    other = [m for m in markets if m["category"] not in ("sports", "esports")]
    sample = other + random.sample(sports, min(MAX_SPORTS, len(sports)))
    print("markets", len(markets), "sampled", len(sample), "non-sports", len(other))

    trades, capped, done = [], 0, 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for rows, cap in ex.map(fetch, sample):
            trades += rows
            capped += cap
            done += 1
            if done % 500 == 0:
                print(done, "markets,", len(trades), "trades", flush=True)
    dump(trades, "trades.json")
    print("trades", len(trades), "markets hitting offset cap", capped)


if __name__ == "__main__":
    main()
