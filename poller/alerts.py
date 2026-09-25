"""Send alerts to Discord (webhook) and Slack (incoming webhook)."""
import os
import time

import requests


def _chunks(lines, limit):
    buf = ""
    for line in lines:
        piece = line + "\n"
        if len(buf) + len(piece) > limit and buf:
            yield buf.rstrip()
            buf = ""
        buf += piece
    if buf.strip():
        yield buf.rstrip()


def discord(lines):
    """Post lines to the Discord alert webhook, split under the 2,000-character cap."""
    url = os.environ.get("DISCORD_WEBHOOK")
    if not url or not lines:
        return 0
    sent = 0
    for part in _chunks(lines, 1900):
        requests.post(url, json={"content": part}, timeout=20).raise_for_status()
        sent += 1
        time.sleep(1)
    return sent


def slack(text):
    url = os.environ.get("SLACK_WEBHOOK")
    if not url or not text:
        return 0
    requests.post(url, json={"text": text}, timeout=20).raise_for_status()
    return 1
