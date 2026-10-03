from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import classifier, llm, replies, speech, store
from .config import ANTHROPIC_CHAT_MODEL, ANTHROPIC_MODEL, STATIC_DIR
from .pipeline import check_message, detect_intent
from .registry import banks, national

app = FastAPI(title="Vaani", docs_url="/api/docs", redoc_url=None)


class CheckIn(BaseModel):
    text: str = ""
    sender: str = ""
    dialect: str = replies.DEFAULT_DIALECT
    source: str = "text"          # text | screenshot | voice
    question: str = ""            # what the person asked out loud, if anything
    cif: str = ""                 # optional, only used to fill the re-KYC SMS
    listen_engine: str = ""       # which speech engine produced `question`
    read_engine: str = ""         # which engine read the screenshot


class AskIn(BaseModel):
    question: str
    text: str
    sender: str = ""
    dialect: str = replies.DEFAULT_DIALECT


class TtsIn(BaseModel):
    text: str
    dialect: str = replies.DEFAULT_DIALECT


class FeedbackIn(BaseModel):
    check_id: str
    note: str = ""


def models_in_use():
    return {
        "speech_to_text": "Sarvam saarika:v2.5" if speech.enabled() else "browser speech recognition",
        "text_to_speech": "Sarvam bulbul:v2" if speech.enabled() else "phone's built-in voice",
        "reading_and_screenshots": ANTHROPIC_MODEL if llm.enabled() else "rules + Tesseract in the browser",
        "follow_up_answers": ANTHROPIC_CHAT_MODEL if llm.enabled() else "glossary only",
        "scam_classifier": classifier.info(),
        "verdict": "fixed rules against the bank registry (app/verdict.py)",
    }


@app.get("/api/health")
def health():
    return {"ok": True, "speech_api": speech.enabled(), "llm": llm.enabled(), "classifier": classifier.enabled()}


@app.get("/api/models")
def models():
    return models_in_use()


@app.get("/api/dialects")
def dialects():
    return replies.dialect_list()


@app.get("/api/ui/{dialect}")
def ui_text(dialect: str):
    data = replies.load(dialect)
    return {"ui": data["ui"], "meta": data["meta"], "glossary": data["glossary"]}


@app.get("/api/banks")
def bank_list():
    # shown on the "sources" page so anyone can see what we check against
    return {
        "banks": [
            {k: b[k] for k in ("id", "name", "domains", "sender_codes", "helpline", "helpline_verified", "sources", "checked_on")}
            for b in banks()
        ],
        "national": national(),
    }


@app.post("/api/check")
def check(body: CheckIn):
    text = (body.text or "").strip()
    intent = detect_intent(body.question)

    if not text and body.source == "voice" and body.question and intent == "check":
        # no message pasted, the person read it out. Treat the words as the message.
        text = body.question
    if not text and intent != "clicked":
        raise HTTPException(400, "empty message")

    result = None
    if text:
        result = check_message(text, body.sender, body.source, transcript=body.question or None,
                               listen_engine=body.listen_engine or None, read_engine=body.read_engine or None)
    out = {"intent": intent}
    if result:
        reply = replies.build(result, body.dialect, cif=body.cif.strip() or None)
        voice = "recorded clip if present, else " + models_in_use()["text_to_speech"]
        result["trace"].append({"step": "reply", "detail": {"dialect": body.dialect, "template": f"verdict.{result['verdict']}", "voice": voice}})
        out.update({
            "id": store.save_check(result, body.dialect, body.source),
            "verdict": result["verdict"],
            "rule": result["rule"],
            "bank": result["extracted"]["bank"],
            "type": result["extracted"]["type"],
            "reply": reply,
            "trace": result["trace"],
        })
    if intent == "clicked":
        out["clicked"] = replies.clicked_help(body.dialect, result["extracted"]["bank"] if result else None)
    return out


@app.post("/api/ask")
def ask(body: AskIn):
    """Follow-up question about a message that was already checked."""
    if detect_intent(body.question) == "clicked":
        return {"clicked": replies.clicked_help(body.dialect)}
    if not body.text.strip() or not body.question.strip():
        raise HTTPException(400, "need the message and the question")
    # re-run the check (rules only, fast) so the answer is built from the same facts the user saw
    result = check_message(body.text, body.sender, use_llm=False)
    return replies.followup(body.question, result, body.dialect)


@app.get("/api/clicked")
def clicked(dialect: str = replies.DEFAULT_DIALECT, bank: str = ""):
    return replies.clicked_help(dialect, bank or None)


@app.post("/api/ocr")
async def ocr(image: UploadFile = File(...)):
    data = await image.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "image too large")
    if not llm.enabled():
        # the browser will read it with Tesseract instead
        return JSONResponse({"engine": "none"}, status_code=501)
    got = llm.read_screenshot(data, image.content_type or "image/jpeg")
    if not got or not got.get("text"):
        return JSONResponse({"engine": ANTHROPIC_MODEL, "error": "could not read"}, status_code=422)
    return {"engine": ANTHROPIC_MODEL, "text": got.get("text", ""), "sender": got.get("sender", "")}


@app.post("/api/stt")
async def stt(audio: UploadFile = File(...), dialect: str = Form(replies.DEFAULT_DIALECT)):
    if not speech.enabled():
        return JSONResponse({"engine": "none"}, status_code=501)
    lang = replies.load(dialect)["meta"]["speech_lang"]
    try:
        text = speech.transcribe(await audio.read(), audio.filename or "voice.webm", lang)
    except Exception as e:  # network / quota problems: let the browser fall back
        return JSONResponse({"engine": "sarvam", "error": str(e)[:200]}, status_code=502)
    return {"engine": "Sarvam saarika:v2.5 (" + lang + ")", "text": text}


@app.post("/api/tts")
def tts(body: TtsIn):
    if not speech.enabled():
        return JSONResponse({"engine": "none"}, status_code=501)
    lang = replies.load(body.dialect)["meta"]["tts_lang"]
    try:
        audio = speech.speak(body.text, lang)
    except Exception as e:
        return JSONResponse({"engine": "sarvam", "error": str(e)[:200]}, status_code=502)
    return Response(audio, media_type="audio/wav")


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    store.save_feedback(body.check_id, body.note)
    return {"ok": True}


@app.get("/api/feedback")
def feedback_list():
    return store.recent_feedback()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/sw.js")
def service_worker():
    # served from the root so it can control the whole app
    return FileResponse(STATIC_DIR / "sw.js", media_type="text/javascript")


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
