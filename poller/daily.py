"""Daily 6 AM PT preorder check: re-run every stock source now (poller half of guide §12)."""
import os
import sys

from .main import STOCK_SOURCES, run
from .timefmt import now_pt


def main():
    if now_pt().hour != 6 and os.environ.get("FORCE") != "true":
        print("not 6 AM PT; the other scheduled run will handle it")
        return 0
    run(only=list(STOCK_SOURCES), force=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
