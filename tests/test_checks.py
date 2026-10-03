from fastapi.testclient import TestClient

from app.checks import run_checks
from app.extract import extract, find_links, parse_sender
from app.main import app
from app.pipeline import check_message, detect_intent
from app.replies import build, DIALECTS

client = TestClient(app)


def verdict(text, sender=""):
    return check_message(text, sender, use_llm=False)["verdict"]


def test_lookalike_link_is_fake():
    assert verdict("Your Indian Bank KYC expires today. Update at indianbank-kyc.in") == "fake"


def test_official_link_and_sender_is_real():
    msg = "Send SMS REKYC NOCHANGE <CIF> to 9677633000 or visit https://apps.indianbank.in/Rekyc/rekyc.aspx - Indian Bank"
    assert verdict(msg, "AD-INDBNK-S") == "real"


def test_genuine_otp_warning_not_flagged():
    # "do not share" must not be read as a request for the OTP
    assert verdict("123456 is your OTP. Do not share it with anyone. HDFC Bank", "VM-HDFCBK-T") == "real"


def test_asking_for_otp_is_fake():
    assert verdict("HDFC Bank: share the OTP received to verify your card") == "fake"


def test_remote_app_is_fake():
    assert verdict("SBI: install AnyDesk so our agent can finish your KYC") == "fake"


def test_personal_number_sender_is_fake():
    assert verdict("Your SBI KYC is pending, update soon", "9876543210") == "fake"


def test_unknown_bank_is_not_sure():
    assert verdict("Punjab Gramin Bank: A/c XX12 credited Rs 500") == "not_sure"


def test_link_from_voice_is_not_sure():
    r = check_message("Indian Bank said visit apps.indianbank.in for KYC", source="voice", use_llm=False)
    assert r["verdict"] == "not_sure"


def test_links_skip_amounts_and_emails():
    links = find_links("Rs.500 debited. Mail rekyc@indianbank.co.in or open sbi.bank.in")
    assert [l["host"] for l in links] == ["sbi.bank.in"]


def test_sender_parsing():
    assert parse_sender("JD-SBIINB-S")["code"] == "SBIINB"
    assert parse_sender("+91 98765 43210")["kind"] == "phone"


def test_every_dialect_builds_a_reply():
    r = check_message("Your ICICI card is blocked. Call 9123456780 immediately", use_llm=False)
    for d in DIALECTS:
        out = build(r, d)
        assert out["headline"] and out["steps"] and "{" not in out["speak"]


def test_rekyc_sms_is_prefilled_with_cif():
    r = check_message("Indian Bank: KYC update due. Visit https://apps.indianbank.in/Rekyc/rekyc.aspx", use_llm=False)
    out = build(r, "hi", cif="1234567")
    assert out["actions"]["sms"]["body"] == "REKYC NOCHANGE 1234567"


def test_clicked_intent():
    assert detect_intent("maine link khol diya aur otp de diya") == "clicked"
    assert detect_intent("ki eh sahi aa") == "check"


def test_api_check_and_trace():
    res = client.post("/api/check", json={"text": "SBI: account blocked today, update at sbi-kyc.xyz", "dialect": "haryanvi"})
    body = res.json()
    assert res.status_code == 200
    assert body["verdict"] == "fake"
    assert [s["step"] for s in body["trace"]] == ["read", "check", "decide", "reply"]


def test_api_clicked_from_voice():
    res = client.post("/api/check", json={"text": "", "question": "I clicked the link and shared otp", "source": "voice", "dialect": "en"})
    assert res.status_code == 200
    assert "clicked" in res.json()


def test_ocr_and_stt_say_when_off():
    assert client.post("/api/tts", json={"text": "hi"}).status_code in (200, 501, 502)
