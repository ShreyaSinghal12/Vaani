"""Listen -> Read -> Check -> Decide. Reply happens in replies.py.

check_message() returns everything the UI needs plus a trace: the
step-by-step record of what ran, which model did it, and why we decided.
The trace is shown under "How we checked" and saved by the eval script.
"""
from . import classifier, llm
from .checks import run_checks
from .config import ANTHROPIC_MODEL
from .extract import extract
from .registry import load_keywords
from .verdict import decide


def detect_intent(question):
    q = (question or "").lower()
    if not q:
        return "check"
    intents = load_keywords()["intents"]
    for name in ("clicked", "repeat"):
        if any(w in q for w in intents[name]):
            return name
    return "check"


def check_message(text, sender="", source="text", use_llm=True, transcript=None,
                  listen_engine=None, read_engine=None):
    trace = []
    if source == "voice":
        trace.append({"step": "listen", "detail": {"transcript": transcript or text, "engine": listen_engine or "browser speech recognition"}})
    if source == "screenshot":
        trace.append({"step": "photo", "detail": {"engine": read_engine or "tesseract (in browser)"}})

    ex = extract(text, sender)
    llm_note = None
    engines = ["rules"]
    if use_llm and llm.enabled():
        extra = llm.read_message(ex["text"])
        if extra:
            engines.append(ANTHROPIC_MODEL)
            if ex["bank"] is None and extra.get("bank"):
                ex["bank"] = extra["bank"]
            if ex["type"] is None and extra.get("type"):
                ex["type"] = extra["type"]
            llm_note = {"claude_says_asks_for_secret": bool(extra.get("asks_for_secret"))}
    ex["filled_by"] = " + ".join(engines)

    trace.append({"step": "read", "detail": {
        "bank": ex["bank"], "type": ex["type"], "links": [l["text"] for l in ex["links"]],
        "amount": ex["amount"], "deadline": ex["deadline"], "sender": ex["sender"]["raw"] or None,
        "phones": ex["phones"], "filled_by": ex["filled_by"], **(llm_note or {}),
    }})

    checks = run_checks(ex, source)
    # Claude can point at an OTP request our keywords missed, but only as a warning, never alone as proof
    if llm_note and llm_note["claude_says_asks_for_secret"] and not any(c["code"] == "asks_secret" for c in checks):
        checks.append({"code": "asks_secret_llm", "level": "medium", "detail": {"model": ANTHROPIC_MODEL}})
    model_check = classifier.as_check(ex["text"], checks)
    if model_check:
        checks.append(model_check)
    trace.append({"step": "check", "detail": [{"code": c["code"], "level": c["level"], **c.get("detail", {})} for c in checks]})

    verdict, rule = decide(ex, checks, source)
    trace.append({"step": "decide", "detail": {"verdict": verdict, "rule": rule, "engine": "fixed rules (app/verdict.py)"}})

    return {"extracted": ex, "checks": checks, "verdict": verdict, "rule": rule, "trace": trace}
