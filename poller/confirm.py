"""Double-check a live reading before anyone gets pinged.

A first-hand source calls confirm(read) with a function that returns (status, extra).
If the first read says in stock / preorder / low, it waits and reads again; only a
second live reading counts. Otherwise the second reading is used (or "unknown").
"""
import time

LIVE = {"in_stock", "preorder_live", "low"}


def confirm(read, wait=20):
    first = read()
    if first[0] not in LIVE:
        return first[0], first[1], None
    time.sleep(wait)
    try:
        second = read()
    except Exception as e:  # second look failed: don't trust the first
        return "unknown", first[1], f"first read {first[0]}, re-check failed ({type(e).__name__})"
    if second[0] in LIVE:
        return second[0], second[1], "confirmed on a second read"
    return second[0], second[1], f"first read {first[0]}, second read {second[0]}"
