"""Evidence checks. Each check returns a small dict:

    {"code": ..., "level": "hard" | "medium" | "good" | "info", "detail": ...}

hard   -> on its own, enough to call the message fake
medium -> suspicious; two of these together also make it fake
good   -> positive evidence that the message really came from the bank
info   -> shown in the trace, does not change the verdict
"""
import re

from .registry import get_bank, official_bank_for_host, host_is_official, banks, load_keywords

SUSPICIOUS_WORDS_IN_HOST = ["kyc", "update", "verify", "secure", "login", "reward", "refund", "support", "help", "block", "account"]


def _edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _looks_like_bank(host):
    """Return a bank id if the host borrows a bank's name without being its domain."""
    label = host.replace("-", "").replace(".", "")
    for b in banks():
        for d in b["domains"]:
            core = d.split(".")[0]
            if len(core) < 3:
                continue
            if core in label:
                return b["id"]
            first = host.split(".")[0].replace("-", "")
            if len(first) >= 4 and _edit_distance(first, core) <= 2:
                return b["id"]
    return None


def _has_any(text_low, words):
    return [w for w in words if w in text_low]


def check_secrets(ex, kw):
    low = ex["text"].lower()
    real_hits = []
    for word in kw["asks_secret"]:
        for m in re.finditer(re.escape(word), low):
            # "do not share your OTP / never share CVV" is what real banks write.
            window = low[max(0, m.start() - 30): m.end()]
            if not any(s in window for s in kw["secret_safe_phrases"]):
                real_hits.append(word)
                break
    if not real_hits:
        return None
    return {"code": "asks_secret", "level": "hard", "detail": {"matched": real_hits[:3]}}


def check_remote_app(ex, kw):
    hits = _has_any(ex["text"].lower(), kw["remote_apps"])
    if hits:
        return {"code": "remote_app", "level": "hard", "detail": {"matched": hits[:3]}}
    return None


def check_links(ex, kw):
    out = []
    claimed = get_bank(ex["bank"]) if ex["bank"] else None
    for link in ex["links"]:
        host = link["host"]
        if link["is_apk"]:
            out.append({"code": "apk_file", "level": "hard", "detail": {"link": link["text"]}})
            continue
        if host in kw["shorteners"] or any(host.endswith("." + s) for s in kw["shorteners"]):
            out.append({"code": "shortener", "level": "medium", "detail": {"link": link["text"]}})
            continue
        owner = official_bank_for_host(host)
        if owner and (claimed is None or owner["id"] == claimed["id"]):
            out.append({"code": "link_official", "level": "good", "detail": {"link": link["text"], "bank": owner["name"], "source": owner["sources"][0]}})
            continue
        if owner and claimed and owner["id"] != claimed["id"]:
            out.append({"code": "link_other_bank", "level": "medium", "detail": {"link": link["text"], "owner": owner["name"]}})
            continue
        lookalike = _looks_like_bank(host)
        if lookalike:
            out.append({"code": "lookalike_link", "level": "hard", "detail": {"link": link["text"], "imitates": get_bank(lookalike)["name"]}})
            continue
        if claimed:
            out.append({"code": "link_not_official", "level": "hard", "detail": {"link": link["text"], "bank": claimed["name"], "official": claimed["domains"][:2]}})
            continue
        words = [w for w in SUSPICIOUS_WORDS_IN_HOST if w in host]
        if words:
            out.append({"code": "suspicious_link", "level": "medium", "detail": {"link": link["text"], "words": words}})
        else:
            out.append({"code": "unknown_link", "level": "info", "detail": {"link": link["text"]}})
    return out


def check_sender(ex):
    s = ex["sender"]
    claimed = get_bank(ex["bank"]) if ex["bank"] else None
    if s["kind"] == "none":
        return {"code": "no_sender", "level": "info", "detail": {}}
    if s["kind"] == "phone":
        if claimed or ex["type"] in ("rekyc", "card_blocked", "mandate_fail", "payment_due"):
            return {"code": "personal_number_sender", "level": "hard", "detail": {"sender": s["raw"]}}
        return {"code": "personal_number_sender", "level": "medium", "detail": {"sender": s["raw"]}}
    if s["kind"] == "header":
        if s.get("suffix") == "P" and ex["type"] in ("rekyc", "card_blocked"):
            return {"code": "promo_header", "level": "medium", "detail": {"sender": s["raw"]}}
        for b in banks():
            if s["code"] in b["sender_codes"]:
                if claimed and b["id"] != claimed["id"]:
                    return {"code": "sender_other_bank", "level": "medium", "detail": {"sender": s["raw"], "owner": b["name"]}}
                return {"code": "sender_known", "level": "good", "detail": {"sender": s["raw"], "bank": b["name"]}}
        return {"code": "sender_unknown", "level": "medium" if claimed else "info", "detail": {"sender": s["raw"]}}
    return {"code": "sender_unknown", "level": "info", "detail": {"sender": s["raw"]}}


def check_call_numbers(ex, kw):
    """Scams often say 'call 98xxxxxxxx to avoid blocking'. Banks give toll free numbers."""
    claimed = get_bank(ex["bank"]) if ex["bank"] else None
    if not ex["phones"] or ex["type"] == "otp_info":
        return None
    low = ex["text"].lower()
    if not any(w in low for w in kw["call_words"]):
        return None
    allowed = set()
    if claimed:
        for ch in claimed.get("procedures", {}).get("rekyc", {}).get("channels", []):
            if ch.get("type") == "sms":
                allowed.add(ch["to"])
    unknown = [p for p in ex["phones"] if p not in allowed]
    if unknown:
        return {"code": "call_mobile_number", "level": "medium", "detail": {"numbers": unknown[:2]}}
    return None


def check_urgency(ex, kw):
    hits = _has_any(ex["text"].lower(), kw["urgency"])
    # a plain "today" in a debit alert is normal, so only count threats
    threat = [h for h in hits if h not in ("today", "aaj", "tonight")]
    if threat or (hits and ex["type"] in ("rekyc", "card_blocked")):
        return {"code": "urgency", "level": "medium", "detail": {"matched": (threat or hits)[:3]}}
    return None


def check_reward(ex):
    if ex["type"] == "reward":
        return {"code": "reward_bait", "level": "medium", "detail": {}}
    return None


def run_checks(ex, source="text"):
    kw = load_keywords()
    results = []
    bank = get_bank(ex["bank"]) if ex["bank"] else None
    results.append({"code": "bank", "level": "info", "detail": {"bank": bank["name"] if bank else None}})
    for fn in (check_secrets, check_remote_app, check_urgency):
        r = fn(ex, kw)
        if r:
            results.append(r)
    results.extend(check_links(ex, kw))
    for r in (check_sender(ex), check_call_numbers(ex, kw), check_reward(ex)):
        if r:
            results.append(r)
    if source == "voice" and ex["links"]:
        results.append({"code": "link_from_voice", "level": "info", "detail": {}})
    return results
