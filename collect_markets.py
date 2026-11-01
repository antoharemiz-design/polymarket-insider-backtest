"""Step 1: closed, cleanly resolved binary markets with volume >= $100k.

Window: markets whose scheduled endDate is on/after 2026-03-01 and that closed
before 2026-10-25 (so every outcome is final).
"""
import json

from pm import GAMMA, dump, get

MIN_VOL = 100_000
CLOSED_BEFORE = "2026-10-25"

# Short-horizon price markets (crypto/stocks up-down, price brackets): no
# private information can exist there, so they only add noise.
PRICE_MARKERS = ("up-or-down", "updown", "-above-", "-below-", "price-of",
                 "-reach-", "what-price", "-dip-to-", "hit-price", "close-above",
                 "-between-")


def category(tags, slug):
    s = {t.get("slug") for t in (tags or [])}
    if s & {"crypto", "crypto-prices", "bitcoin", "ethereum", "solana"} or any(m in slug for m in PRICE_MARKERS):
        return "price"
    if s & {"esports"}:
        return "esports"
    if s & {"sports", "soccer", "nba", "nfl", "mlb", "nhl", "tennis", "ufc", "golf", "f1", "cricket", "boxing"}:
        return "sports"
    if s & {"geopolitics", "middle-east", "ukraine", "war", "military", "world-affairs", "israel", "iran", "china"}:
        return "geopolitics"
    if s & {"politics", "elections", "global-elections", "us-politics", "trump"}:
        return "politics"
    if s & {"business", "tech", "ai", "companies", "big-tech", "earnings", "economy", "fed", "finance"}:
        return "business"
    if s & {"culture", "pop-culture", "awards", "movies", "music", "entertainment", "celebrities", "mentions", "tweet-markets"}:
        return "culture"
    return "other"


def main():
    from datetime import datetime, timedelta

    def fetch_window(lo, hi):
        """All markets with endDate in [lo, hi); split the window on offset caps."""
        res, off = [], 0
        while True:
            page = get(GAMMA, "/markets", {
                "closed": "true", "limit": 100, "offset": off,
                "volume_num_min": MIN_VOL, "include_tag": "true",
                "end_date_min": lo.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_date_max": hi.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            if isinstance(page, dict) or page is None:
                break
            res += page
            if len(page) < 100:
                return res
            off += 100
            if off >= 1500:
                break
        if hi - lo < timedelta(hours=2):
            print("window too dense, keeping partial", lo, len(res))
            return res
        mid = lo + (hi - lo) / 2
        return fetch_window(lo, mid) + fetch_window(mid, hi)

    from concurrent.futures import ThreadPoolExecutor
    windows, lo = [], datetime(2026, 3, 1)
    end = datetime(2028, 1, 1)
    while lo < end:
        step = timedelta(days=1) if lo < datetime(2026, 11, 1) else timedelta(days=30)
        windows.append((lo, min(lo + step, end)))
        lo += step
    out = []
    with ThreadPoolExecutor(8) as ex:
        for i, res in enumerate(ex.map(lambda w: fetch_window(*w), windows)):
            out += res
            if i % 20 == 0:
                print("window", i, "/", len(windows), "markets", len(out), flush=True)
    seen = set()
    out = [m for m in out if not (m["conditionId"] in seen or seen.add(m["conditionId"]))]

    keep = []
    for m in out:
        try:
            prices = json.loads(m.get("outcomePrices") or "[]")
            tokens = json.loads(m.get("clobTokenIds") or "[]")
        except Exception:
            continue
        if sorted(prices) != ["0", "1"] or len(tokens) != 2:
            continue  # not cleanly resolved binary
        closed = (m.get("closedTime") or "")[:10]
        if not closed or closed >= CLOSED_BEFORE:
            continue
        keep.append({
            "conditionId": m["conditionId"],
            "question": m.get("question"),
            "slug": m.get("slug"),
            "eventSlug": (m.get("events") or [{}])[0].get("slug"),
            "category": category(m.get("tags"), m.get("slug") or ""),
            "endDate": m.get("endDate"),
            "closedTime": m.get("closedTime"),
            "startDate": m.get("startDate"),
            "volume": float(m.get("volumeNum") or 0),
            "winner": prices.index("1"),
            "tokens": tokens,
            "negRisk": m.get("negRisk"),
        })
    dump(keep, "markets.json")
    from collections import Counter
    print("raw", len(out), "kept", len(keep))
    print(Counter(k["category"] for k in keep).most_common())


if __name__ == "__main__":
    main()
