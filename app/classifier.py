"""Loads the scam-SMS classifier trained by ml/train.py.

The model gives a 0-1 score for "this reads like a scam". Vaani uses it as one
more warning sign. It can push a doubtful message towards Fake, but it can never
overrule the registry: a message with an official link or a known sender is not
flagged by the model alone.
"""
from functools import lru_cache

from .config import ROOT

MODEL_PATH = ROOT / "ml" / "model" / "sms_scam_clf.joblib"
FLAG_AT = 0.9


@lru_cache
def _bundle():
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib
        return joblib.load(MODEL_PATH)
    except Exception:
        return None


def enabled():
    return _bundle() is not None


def info():
    b = _bundle()
    if not b:
        return None
    m = b["metrics"]
    return {
        "name": "TF-IDF + logistic regression",
        "version": b["version"],
        "trained_on": m["train_rows"],
        "held_out_f1": m["held_out_test"]["f1"],
        "held_out_roc_auc": m["held_out_test"]["roc_auc"],
        "test_rows": m["test_rows"],
    }


def score(text):
    b = _bundle()
    if not b or not text:
        return None
    return round(float(b["model"].predict_proba([text])[0][1]), 3)


def as_check(text, checks):
    p = score(text)
    if p is None:
        return None
    has_proof = any(c["level"] == "good" for c in checks)
    level = "medium" if p >= FLAG_AT and not has_proof else "info"
    return {"code": "model_scam" if level == "medium" else "model_score", "level": level,
            "detail": {"score": p, "model": "sms_scam_clf " + _bundle()["version"]}}
