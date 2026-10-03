"""Pull facts out of a bank message: bank, type, links, amount, deadline, numbers.

Everything here is plain rules. If an Anthropic key is set, llm.py can fill in
the bank / message type for messy text, but links and phone numbers always come
from these regexes, because a model can quietly "fix" a fake link while copying it.
"""
import re
from urllib.parse import urlparse

from .registry import banks, load_keywords

TLDS = (
    "bank.in|co.in|org.in|net.in|gov.in|in|com|net|org|co|info|xyz|top|site|online|"
    "live|link|ly|me|io|app|club|icu|cc|tk|ml|ga|cf|gq|buzz|shop|sbi|gl|at|gg|id|vip"
)
URL_RE = re.compile(
    r"(?:https?://[^\s<>\"']+)"
    r"|(?:www\.[^\s<>\"']+)"
    r"|(?:\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:" + TLDS + r")\b(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(r"(?:rs\.?|inr|\u20b9)\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(\d{1,2}[-/.]\d{1,2}(?:[-/.]\d{2,4})?|\d{1,2}[- ](?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:[- ]\d{2,4})?)\b",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(?<![\d])(?:\+?91[\s-]?)?([6-9]\d{9})(?![\d])")
TOLLFREE_RE = re.compile(r"\b(1800[\s-]?\d{3,4}[\s-]?\d{3,4}|1860[\s-]?\d{3}[\s-]?\d{4})\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# TRAI style header: two letter prefix, 6 char brand code, optional -S/-T/-P/-G
HEADER_RE = re.compile(r"^([A-Z]{2})-([A-Z0-9]{6})(?:-([STPG]))?$", re.IGNORECASE)

TYPE_ORDER = ["otp_info", "rekyc", "mandate_fail", "card_blocked", "payment_due", "reward", "transaction"]


def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def find_links(text):
    found = []
    for m in URL_RE.finditer(text or ""):
        raw = m.group(0).rstrip(".,);:!?'\"")
        # skip e-mail domains and things like "Rs.500"
        start = m.start()
        if start > 0 and text[start - 1] == "@":
            continue
        if re.fullmatch(r"(?i)rs\.?\d.*", raw):
            continue
        url = raw if raw.lower().startswith("http") else "http://" + raw
        host = (urlparse(url).hostname or "").lower()
        if not host or "." not in host:
            continue
        found.append({"text": raw, "host": host, "is_apk": raw.lower().split("?")[0].endswith(".apk")})
    # de-duplicate, keep order
    seen, out = set(), []
    for item in found:
        if item["text"] not in seen:
            seen.add(item["text"])
            out.append(item)
    return out


def find_bank(text):
    low = text.lower()
    native = load_keywords()["bank_aliases_native"]
    for b in banks():
        for alias in b["aliases"]:
            if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low):
                return b["id"]
        for alias in native.get(b["id"], []):
            if alias in text:
                return b["id"]
    return None


def find_type(text):
    low = text.lower()
    kw = load_keywords()["message_types"]
    for t in TYPE_ORDER:
        for word in kw.get(t, []):
            if word in low:
                return t
    return None


def find_deadline(text):
    low = text.lower()
    for phrase in ["within 24 hours", "within 24 hrs", "in 24 hours", "today", "tonight", "tomorrow"]:
        if phrase in low:
            return phrase
    m = re.search(r"(?:by|before|on or before|till|until)\s+([0-9a-z/ .-]{4,20})", low)
    if m:
        d = DATE_RE.search(m.group(1))
        if d:
            return d.group(1)
    return None


def parse_sender(sender):
    """Returns dict with kind: header | phone | other | none."""
    s = (sender or "").strip()
    if not s:
        return {"kind": "none", "raw": ""}
    compact = re.sub(r"[\s]", "", s)
    if re.fullmatch(r"\+?\d{10,13}", compact):
        return {"kind": "phone", "raw": s}
    m = HEADER_RE.match(compact.upper())
    if m:
        return {"kind": "header", "raw": s, "code": m.group(2).upper(), "suffix": (m.group(3) or "").upper()}
    if re.fullmatch(r"[A-Za-z0-9]{6}", compact):
        return {"kind": "header", "raw": s, "code": compact.upper(), "suffix": ""}
    return {"kind": "other", "raw": s}


def extract(text, sender=""):
    text = _norm(text)
    phones = [p for p in PHONE_RE.findall(text)]
    return {
        "text": text,
        "bank": find_bank(text),
        "type": find_type(text),
        "links": find_links(text),
        "amount": (AMOUNT_RE.search(text).group(1) if AMOUNT_RE.search(text) else None),
        "deadline": find_deadline(text),
        "phones": phones,
        "tollfree": [re.sub(r"[\s-]", "", t) for t in TOLLFREE_RE.findall(text)],
        "emails": EMAIL_RE.findall(text),
        "sender": parse_sender(sender),
        "filled_by": "rules",
    }
