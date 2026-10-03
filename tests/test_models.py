"""Tests for the model parts. Claude is replaced with canned replies so these run
without an API key and without spending credits."""
import json

from fastapi.testclient import TestClient

from app import classifier, llm, replies
from app.main import app
from app.pipeline import check_message

client = TestClient(app)


def fake_claude(monkeypatch, reply):
    monkeypatch.setattr(llm, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_call", lambda *a, **k: reply)


def test_classifier_loads_and_scores():
    assert classifier.enabled()
    scam = classifier.score("Your SBI KYC expired. Update now at sbi-kyc.xyz or account blocked today")
    normal = classifier.score("Rs 499.00 debited from A/c XX1234 on 12-09-26 for UPI/AMAZON. Not you? Call 1800 1234 - SBI")
    assert scam > 0.9
    assert normal < scam


def test_classifier_cannot_overrule_registry():
    # high scam score, but official link + known sender: model only adds an info line
    r = check_message("Indian Bank: KYC due. Update at https://apps.indianbank.in/Rekyc/rekyc.aspx or your account will be blocked",
                      "AD-INDBNK-S", use_llm=False)
    model = [c for c in r["checks"] if c["code"].startswith("model_")]
    assert model and model[0]["level"] == "info"


def test_classifier_shows_in_trace():
    r = check_message("Part time job, earn Rs 3000 daily from home. WhatsApp 9876543210", use_llm=False)
    codes = [c["code"] for c in r["trace"][1]["detail"]]
    assert "model_scam" in codes
    assert r["verdict"] == "fake"


def test_claude_fills_bank_and_type(monkeypatch):
    fake_claude(monkeypatch, json.dumps({"bank": "pnb", "type": "rekyc", "asks_for_secret": False, "deadline": None}))
    r = check_message("bhai tera kyc wala kaam pending hai punjab wale bank me", use_llm=True)
    assert r["extracted"]["bank"] == "pnb"
    assert "claude" in r["extracted"]["filled_by"]


def test_claude_secret_flag_is_only_a_warning(monkeypatch):
    fake_claude(monkeypatch, json.dumps({"bank": None, "type": None, "asks_for_secret": True, "deadline": None}))
    r = check_message("hello ji, woh number bhej do jo abhi aaya", use_llm=True)
    flag = [c for c in r["checks"] if c["code"] == "asks_secret_llm"]
    assert flag and flag[0]["level"] == "medium"


def test_followup_answer_passes_guard(monkeypatch):
    fake_claude(monkeypatch, "CIF tuhadi passbook de pehle panne te likhya hunda hai. Indian Bank nu 1800 4250 0000 te phone karo.")
    res = client.post("/api/ask", json={"question": "CIF ki hunda?", "dialect": "malwai",
                                       "text": "Indian Bank: KYC due. Visit https://apps.indianbank.in/Rekyc/rekyc.aspx"})
    body = res.json()
    assert body["guard"] == "passed"
    assert "1800 4250 0000" in body["answer"]


def test_followup_blocks_made_up_number(monkeypatch):
    fake_claude(monkeypatch, "Call our officer on 9811122233 to finish it quickly.")
    res = client.post("/api/ask", json={"question": "who do I call?", "dialect": "en",
                                       "text": "Indian Bank: KYC due. Visit https://apps.indianbank.in/Rekyc/rekyc.aspx"})
    body = res.json()
    assert body["guard"] == "replaced"
    assert "9811122233" not in body["answer"]


def test_followup_blocks_made_up_website(monkeypatch):
    fake_claude(monkeypatch, "Just open indian-bank-help.com and fill the form.")
    res = client.post("/api/ask", json={"question": "where?", "dialect": "hi",
                                       "text": "Indian Bank: KYC due. Visit https://apps.indianbank.in/Rekyc/rekyc.aspx"})
    assert res.json()["guard"] == "replaced"


def test_followup_without_key_uses_glossary(monkeypatch):
    monkeypatch.setattr(llm, "ANTHROPIC_API_KEY", "")
    res = client.post("/api/ask", json={"question": "what is KYC", "dialect": "en", "text": "SBI: your KYC is pending"})
    assert res.json()["engine"] == "glossary"


def test_followup_clicked_goes_to_emergency():
    res = client.post("/api/ask", json={"question": "I already clicked the link", "dialect": "en", "text": "x"})
    assert "clicked" in res.json()


def test_models_endpoint_lists_classifier():
    m = client.get("/api/models").json()
    assert m["scam_classifier"]["held_out_f1"] > 0.9
    assert "fixed rules" in m["verdict"]


def test_screenshot_with_claude(monkeypatch):
    fake_claude(monkeypatch, json.dumps({"sender": "AD-INDBNK-S", "text": "Indian Bank KYC due"}))
    res = client.post("/api/ocr", files={"image": ("s.png", b"\x89PNG fake", "image/png")})
    assert res.status_code == 200
    assert res.json()["sender"] == "AD-INDBNK-S"


def test_reasons_exist_for_every_check_code():
    for d in replies.DIALECTS:
        r = replies.load(d)["reasons"]
        for code in ("model_scam", "asks_secret_llm", "lookalike_link", "link_official"):
            assert code in r
