"""Builds the answer the user sees and hears.

The verdict lines live in data/replies/<dialect>.json. They are written once,
ahead of time, and checked by a native speaker; nothing in the verdict is
generated per request. This file picks the right lines and fills in the blanks
(bank name, helpline, amount, link...). Only follow-up questions go to Claude,
and its answer is checked by guard() before the user sees it.
"""
import json
import re
from functools import lru_cache

from .config import DATA_DIR
from .registry import get_bank, national

DIALECTS = ["malwai", "haryanvi", "pa", "hi", "en"]
DEFAULT_DIALECT = "hi"


@lru_cache
def load(dialect):
    if dialect not in DIALECTS:
        dialect = DEFAULT_DIALECT
    with open(DATA_DIR / "replies" / f"{dialect}.json", encoding="utf-8") as f:
        return json.load(f)


class _Blank(dict):
    # leave unknown placeholders empty instead of crashing
    def __missing__(self, key):
        return ""


def fill(template, **values):
    return template.format_map(_Blank(values))


def dialect_list():
    out = []
    for d in DIALECTS:
        meta = load(d)["meta"]
        out.append({
            "id": d,
            "name": meta["name"],
            "native_name": meta["native_name"],
            "greeting": meta["greeting"],
            "speech_lang": meta["speech_lang"],
            "review": meta.get("review", ""),
        })
    return out


def _values(ex, T, cif=None):
    bank = get_bank(ex["bank"]) if ex["bank"] else None
    bits = T["bits"]
    helpline = bank["helpline"] if bank else ""
    amount = ex.get("amount")
    deadline = ex.get("deadline")
    return {
        "bank": bank["name"] if bank else "",
        "helpline": helpline,
        "bank_or_your_bank": bank["name"] if bank else bits["your_bank"],
        "helpline_or_card": helpline if bank and bank.get("helpline_verified") else bits["card_number"],
        "amount": amount or "",
        "amount_part": fill(bits["amount_part"], amount=amount) if amount else "",
        "amount_or_enough": ("Rs " + amount) if amount else bits["enough"],
        "deadline_part": fill(bits["deadline_part"], deadline=deadline) if deadline else "",
        "cif": cif or "<CIF>",
    }


def _reason_lines(checks, T, vals, verdict):
    lines = []
    for c in checks:
        if c["level"] not in ("hard", "medium", "good"):
            if c["code"] == "link_from_voice":
                lines.append({"level": "info", "code": c["code"], "text": T["reasons"]["link_from_voice"]})
            continue
        tpl = T["reasons"].get(c["code"])
        if not tpl:
            continue
        d = dict(vals)
        for k, v in c.get("detail", {}).items():
            d[k] = ", ".join(v) if isinstance(v, list) else (v or "")
        lines.append({"level": c["level"], "code": c["code"], "text": fill(tpl, **d)})
    if verdict == "real" and not any(l["level"] == "good" for l in lines):
        lines.append({"level": "good", "code": "clean", "text": fill(T["reasons"]["clean"], **vals)})
    if verdict == "not_sure" and not vals["bank"]:
        lines.append({"level": "info", "code": "no_bank", "text": T["reasons"]["no_bank"]})
    order = {"hard": 0, "medium": 1, "good": 2, "info": 3}
    lines.sort(key=lambda l: order[l["level"]])
    return lines


def _real_steps(ex, T, vals):
    """Steps + ready-made actions for a genuine message."""
    steps, actions = [], {}
    bank = get_bank(ex["bank"]) if ex["bank"] else None
    mtype = ex["type"] or "generic_real"

    if mtype == "rekyc" and bank:
        proc = bank.get("procedures", {}).get("rekyc")
        steps += [fill(s, **vals) for s in T["steps"]["rekyc"]]
        if proc:
            if proc.get("note") and ex.get("_dialect") == "en":
                steps.append(proc["note"])
            for ch in proc["channels"]:
                tpl = T["channels"].get(ch["type"])
                if not tpl:
                    continue
                d = dict(vals)
                d.update({k: fill(v, **vals) if isinstance(v, str) else v for k, v in ch.items()})
                steps.append(fill(tpl, **d))
                if ch["type"] == "sms":
                    actions["sms"] = {"to": ch["to"], "body": fill(ch["body"], **vals), "needs_cif": "{cif}" in ch["body"]}
                elif ch["type"] == "email":
                    actions["email"] = {"to": ch["to"], "subject": fill(ch["subject"], **vals)}
                elif ch["type"] == "portal":
                    actions["portal"] = ch["url"]
            if not proc.get("verified"):
                actions["not_verified"] = True
        else:
            steps += [fill(s, **vals) for s in T["steps"]["rekyc_branch_only"]]
    else:
        key = mtype if mtype in T["steps"] else "generic_real"
        steps += [fill(s, **vals) for s in T["steps"][key]]
    return steps, actions


def build(result, dialect, cif=None):
    T = load(dialect)
    ex = dict(result["extracted"])
    ex["_dialect"] = dialect
    verdict = result["verdict"]
    vals = _values(ex, T, cif)
    bank = get_bank(ex["bank"]) if ex["bank"] else None

    head = T["verdict"][verdict]
    reasons = _reason_lines(result["checks"], T, vals, verdict)

    actions = {}
    if verdict == "fake":
        steps = [fill(s, **vals) for s in T["steps"]["fake"]]
        actions["report"] = national()["report_fraud_sms"]
    elif verdict == "not_sure":
        steps = [fill(s, **vals) for s in T["steps"]["not_sure"]]
    else:
        steps, actions = _real_steps(ex, T, vals)

    if bank:
        actions["call"] = {"number": bank["helpline"], "label": fill(T["ui"]["call_bank"], bank=bank["name"]), "verified": bank.get("helpline_verified", False)}

    # what we read out: verdict line, the strongest reason, then the first steps
    spoken = [fill(head["say"], **vals)]
    strongest = [r for r in reasons if r["level"] == "hard"] or [r for r in reasons if r["level"] in ("medium", "good")]
    if strongest:
        spoken.append(strongest[0]["text"])
    spoken += steps[:2]

    return {
        "dialect": dialect,
        "headline": head["headline"],
        "summary": fill(head["say"], **vals),
        "reasons": reasons,
        "steps": steps,
        "actions": actions,
        "speak": " ".join(spoken),
        # recorded clips (static/audio/<dialect>/<clip>.mp3) are played instead of TTS when present
        "clip": f"verdict_{verdict}",
    }


def facts_for(result, dialect):
    """Everything the follow-up model is allowed to use. Nothing else."""
    ex = result["extracted"]
    bank = get_bank(ex["bank"]) if ex["bank"] else None
    reply = build(result, dialect)
    facts = {
        "verdict": result["verdict"],
        "verdict_in_their_words": reply["summary"],
        "why": [r["text"] for r in reply["reasons"]],
        "what_to_do": reply["steps"],
        "message_type": ex["type"],
        "amount": ex["amount"],
        "deadline": ex["deadline"],
        "links_in_message": [l["text"] for l in ex["links"]],
        "meanings": load(dialect)["glossary"],
        "cyber_crime_helpline": national()["cyber_helpline"],
        "cyber_crime_portal": national()["cyber_portal"],
        "cif_meaning": "CIF is the customer ID number printed on the first page of the passbook.",
    }
    if bank:
        facts["bank"] = {
            "name": bank["name"],
            "official_websites": bank["domains"],
            "helpline": bank["helpline"],
            "rekyc_procedure": bank.get("procedures", {}).get("rekyc"),
        }
    return facts


def _numbers(s):
    return {d for d in re.findall(r"\d[\d ]{3,}\d", s or "") for d in [d.replace(" ", "")]}


def _hosts(s):
    return set(re.findall(r"(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", (s or "").lower()))


def guard(answer_text, facts):
    """Reject an answer that brings in a number or website we did not give it."""
    flat = json.dumps(facts, ensure_ascii=False)
    allowed_numbers = _numbers(flat)
    allowed_hosts = _hosts(flat)
    bad_numbers = [n for n in _numbers(answer_text) if n not in allowed_numbers]
    bad_hosts = [h for h in _hosts(answer_text) if not any(h == a or h.endswith("." + a) or a.endswith("." + h) for a in allowed_hosts)]
    asks_secret = re.search(r"(share|send|tell|bata|dass|de do).{0,15}(otp|pin|cvv|password)", answer_text.lower())
    return not bad_numbers and not bad_hosts and not asks_secret, {"bad_numbers": bad_numbers, "bad_hosts": bad_hosts}


def followup(question, result, dialect):
    from . import llm  # local import keeps replies.py usable without httpx in tests
    T = load(dialect)
    facts = facts_for(result, dialect)
    helpline = facts.get("bank", {}).get("helpline") or T["bits"]["card_number"]

    text = llm.answer(question, facts, T["meta"])
    if text:
        ok, problems = guard(text, facts)
        if ok:
            return {"answer": text, "engine": llm.ANTHROPIC_CHAT_MODEL, "guard": "passed"}
        fallback = fill(T["ui"]["ask_fallback"], helpline=helpline)
        return {"answer": fallback, "engine": llm.ANTHROPIC_CHAT_MODEL, "guard": "replaced", "guard_detail": problems}

    # no key: answer simple "what does X mean" questions from the glossary
    q = question.lower()
    for term, meaning in T["glossary"].items():
        if term.lower() in q:
            return {"answer": f"{term}: {meaning}", "engine": "glossary", "guard": "n/a"}
    if "cif" in q:
        return {"answer": "CIF: " + T["ui"]["cif_prompt"], "engine": "glossary", "guard": "n/a"}
    return {"answer": fill(T["ui"]["ask_fallback"], helpline=helpline), "engine": "fallback", "guard": "n/a"}


def clicked_help(dialect, bank_id=None):
    T = load(dialect)
    bank = get_bank(bank_id) if bank_id else None
    helpline = bank["helpline"] if bank else T["bits"]["card_number"]
    steps = [fill(s, helpline=helpline) for s in T["clicked"]["steps"]]
    return {
        "title": T["clicked"]["title"],
        "steps": steps,
        "speak": " ".join(steps[:4]),
        "call": {"cyber": national()["cyber_helpline"], "bank": bank["helpline"] if bank else None},
        "portal": national()["cyber_portal"],
        "clip": "clicked",
    }
