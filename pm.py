"""Shared helpers for the Polymarket backtest: HTTP with retries, paths."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)

GAMMA = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def get(base, path, params=None, retries=6):
    url = f"{base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    delay = 1.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                body = e.read().decode(errors="ignore")[:200]
                return {"_error": e.code, "body": body}
            if attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay = min(delay * 2, 20)


def path(name):
    return os.path.join(DATA, name)


def dump(obj, name):
    with open(path(name), "w") as f:
        json.dump(obj, f)


def load(name):
    with open(path(name)) as f:
        return json.load(f)
