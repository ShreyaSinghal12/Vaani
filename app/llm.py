"""Claude helpers (Anthropic API).

1. read_message()    fills in bank / message type for messy or Hinglish text and
                     says whether the message asks for a secret. Never the verdict.
2. read_screenshot() copies the SMS text and sender out of a phone screenshot.
3. answer()          answers a follow-up question in the person's dialect, using
                     only the facts we hand it (registry entry, what we read, the verdict).

Without ANTHROPIC_API_KEY these return None and the app falls back to rules,
Tesseract in the browser, and the glossary.
"""
import base64
import json
import re

import httpx

from .config import ANTHROPIC_API_KEY, ANTHROPIC_CHAT_MODEL, ANTHROPIC_MODEL

API_URL = "https://api.anthropic.com/v1/messages"
BANK_IDS = ["sbi", "pnb", "hdfc", "icici", "indianbank"]
TYPES = ["rekyc", "mandate_fail", "card_blocked", "payment_due", "transaction", "otp_info", "reward"]


def enabled():
    return bool(ANTHROPIC_API_KEY)


def _call(content, max_tokens=400, model=None, system=None):
    payload = {
        "model": model or ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        payload["system"] = system
    r = httpx.post(
        API_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=40,
    )
    r.raise_for_status()
    parts = r.json().get("content", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def _json_from(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def read_message(text):
    if not enabled():
        return None
    prompt = (
        "You read Indian bank SMS messages. The message may be in English, Hindi, Punjabi or a mix.\n"
        "Return only JSON with these keys:\n"
        f'  "bank": one of {BANK_IDS} or null,\n'
        f'  "type": one of {TYPES} or null,\n'
        '  "asks_for_secret": true only if it asks the reader to share or enter an OTP, PIN, CVV or password '
        '(a warning like "do not share your OTP" is false),\n'
        '  "deadline": short text or null.\n'
        "Do not judge whether the message is genuine.\n\nMessage:\n" + text
    )
    try:
        data = _json_from(_call(prompt))
    except httpx.HTTPError:
        return None
    if not data:
        return None
    if data.get("bank") not in BANK_IDS:
        data["bank"] = None
    if data.get("type") not in TYPES:
        data["type"] = None
    return data


def read_screenshot(image_bytes, media_type="image/jpeg"):
    if not enabled():
        return None
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(image_bytes).decode()}},
        {"type": "text", "text": (
            "This is a phone screenshot of an SMS or WhatsApp message. Copy the message body exactly, "
            "character for character, including any links. Also copy the sender name or number shown at the top. "
            'Return only JSON: {"sender": "...", "text": "..."}. If you cannot read part of a link, put [unclear] there.'
        )},
    ]
    try:
        return _json_from(_call(content, max_tokens=800))
    except httpx.HTTPError:
        return None


ANSWER_RULES = """You are Vaani, a helper for people in Indian villages who are unsure about a bank message.
Answer the person's follow-up question.

Rules:
- Reply in {dialect_name} ({native_name}), written in {script} script. Use the everyday words people in
  that area use, not formal or bookish language. Keep English bank words like OTP, KYC, PIN, UPI as they are.
- 2 to 4 short sentences. Simple words. No lists, no markdown.
- Use ONLY the facts below. Do not add any phone number, website, amount or date that is not in the facts.
  If the answer needs something that is not in the facts, say you are not sure and tell them to ask at
  their bank branch or call the helpline from the facts.
- Never change the verdict. Never say a Fake or Not sure message is safe.
- Never ask for, or tell them to share, an OTP, PIN, password or CVV with anyone.
- If they say they already clicked a link, shared an OTP or lost money, tell them to call 1930 now.

Facts (JSON):
{facts}"""


def answer(question, facts, meta):
    if not enabled():
        return None
    system = ANSWER_RULES.format(
        dialect_name=meta["name"], native_name=meta["native_name"], script=meta["script"],
        facts=json.dumps(facts, ensure_ascii=False, indent=1),
    )
    try:
        return _call(question, max_tokens=350, model=ANTHROPIC_CHAT_MODEL, system=system).strip()
    except httpx.HTTPError:
        return None
