"""Turns the list of checks into Real / Fake / Not sure.

Fixed rules only. The language model never gets a vote here. Each branch
returns the rule name so the trace can show exactly why we decided.
"""

REAL, FAKE, NOT_SURE = "real", "fake", "not_sure"


def decide(ex, checks, source="text"):
    hard = [c for c in checks if c["level"] == "hard"]
    medium = [c for c in checks if c["level"] == "medium"]
    good = [c for c in checks if c["level"] == "good"]

    if hard:
        return FAKE, "a hard red flag: " + ", ".join(c["code"] for c in hard)
    if len(medium) >= 2:
        return FAKE, "two or more warning signs: " + ", ".join(c["code"] for c in medium)
    if medium:
        return NOT_SURE, "one warning sign: " + medium[0]["code"]

    if not ex["text"] or len(ex["text"]) < 12:
        return NOT_SURE, "too little text to check"
    if source == "voice" and ex["links"]:
        # a link read out loud can't be matched letter by letter
        return NOT_SURE, "link came from voice, cannot match it exactly"
    if not ex["bank"]:
        return NOT_SURE, "bank not in our registry"

    unknown_links = [c for c in checks if c["code"] == "unknown_link"]
    if unknown_links:
        return NOT_SURE, "link we cannot place"
    if good:
        return REAL, "matches the bank's official records: " + ", ".join(c["code"] for c in good)
    if ex["type"] in ("transaction", "otp_info", "mandate_fail", "payment_due", "card_blocked", "rekyc") and not ex["links"]:
        return REAL, "no red flags, no links, normal wording for this kind of alert"
    return NOT_SURE, "no red flags but nothing that proves it came from the bank"
