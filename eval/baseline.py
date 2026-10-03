"""The thing we have to beat: a plain keyword spam filter.

This is roughly how most "scam checker" apps start: look for scary words and
links, flag the message if any show up. No idea which websites are real.
"""
import re

SCAM_WORDS = [
    "kyc", "blocked", "suspended", "urgent", "immediately", "click", "verify",
    "update", "reward", "won", "lottery", "refund", "otp", "expire", "deactivat",
]
LINK = re.compile(r"https?://|www\.|\.[a-z]{2,6}/|\.(com|in|xyz|top|site|online|link|info|app)\b", re.I)


def baseline_verdict(text):
    low = text.lower()
    hits = sum(1 for w in SCAM_WORDS if w in low)
    if LINK.search(low) and hits:
        return "fake"
    if hits >= 2:
        return "fake"
    return "real"
