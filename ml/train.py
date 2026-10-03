"""Train Vaani's scam-SMS classifier.

Real, public data (both on Kaggle; ml/data/ has copies from public GitHub mirrors):
  1. SMS Phishing Dataset for Machine Learning and Pattern Recognition
     (Mishra & Soni, 2022), 5,971 messages: ham / spam / smishing.
     https://data.mendeley.com/datasets/f45bkkt8pr/1
  2. UCI SMS Spam Collection, 5,574 messages: ham / spam.
     https://www.kaggle.com/datasets/uciml/sms-spam-collection-dataset
     (most of these are already inside dataset 1, so few survive de-duplication)

Indian data:
  3. ml/data/india_synthetic.csv  - template messages from ml/augment_india.py.
     TRAINING ONLY. Never in the test set.
  4. ml/data/india_real.csv       - optional. Real messages you collect
     (columns: text,label with label ham or scam). Split 80/20 like the
     Kaggle data, so they count in the test numbers.
  5. Any extra Kaggle CSV you download into ml/data/kaggle_extra/ with
     columns text,label (see ml/get_kaggle.sh).

Model: TF-IDF on words (1-2 grams) + characters (3-5 grams) -> logistic regression.

    python -m ml.augment_india
    python -m ml.train
"""
import json
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

HERE = Path(__file__).parent
DATA = HERE / "data"
OUT = HERE / "model"
ROOT = HERE.parent

SCAM_WORDS = {"spam", "smishing", "scam", "fraud", "phishing", "1"}


def _simple(path, source):
    df = pd.read_csv(path, encoding_errors="replace")
    cols = {c.lower(): c for c in df.columns}
    text = cols.get("text") or cols.get("message") or cols.get("sms")
    label = cols.get("label") or cols.get("category") or cols.get("class")
    return pd.DataFrame({
        "text": df[text].astype(str),
        "scam": df[label].astype(str).str.strip().str.lower().isin(SCAM_WORDS).astype(int),
        "smishing": 0,
        "source": source,
    })


def load_public():
    smish = pd.read_csv(DATA / "smishing_5971.csv", encoding_errors="replace")
    smish = pd.DataFrame({
        "text": smish["TEXT"].astype(str),
        "scam": smish["LABEL"].str.lower().isin(["spam", "smishing"]).astype(int),
        "smishing": (smish["LABEL"].str.lower() == "smishing").astype(int),
        "source": "kaggle_mishra_soni_smishing",
    })
    uci = pd.read_csv(DATA / "uci_sms.tsv", sep="\t", header=None, names=["label", "text"], encoding_errors="replace")
    uci = pd.DataFrame({
        "text": uci["text"].astype(str),
        "scam": (uci["label"] == "spam").astype(int),
        "smishing": 0,
        "source": "kaggle_uci_sms_spam",
    })
    parts = [smish, uci]
    if (DATA / "india_real.csv").exists():
        parts.append(_simple(DATA / "india_real.csv", "india_real"))
    for extra in sorted((DATA / "kaggle_extra").glob("*.csv")) if (DATA / "kaggle_extra").exists() else []:
        parts.append(_simple(extra, "kaggle_" + extra.stem))
    return parts


def clean(df):
    df = df.copy()
    df["text"] = df["text"].str.replace("\ufffd", " ", regex=False).str.strip()
    df = df[df["text"].str.len() > 3]
    return df.drop_duplicates(subset="text").reset_index(drop=True)


def build():
    features = FeatureUnion([
        ("words", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("chars", TfidfVectorizer(lowercase=True, analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True)),
    ])
    return Pipeline([
        ("features", features),
        ("clf", LogisticRegression(max_iter=3000, C=8.0, class_weight="balanced")),
    ])


def scores(model, test):
    proba = model.predict_proba(test["text"])[:, 1]
    pred = (proba >= 0.5).astype(int)
    p, r, f1, _ = precision_recall_fscore_support(test["scam"], pred, average="binary", zero_division=0)
    tn, fp, fn, tp = confusion_matrix(test["scam"], pred, labels=[0, 1]).ravel()
    return proba, pred, {
        "precision": round(float(p), 4), "recall": round(float(r), 4), "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc_score(test["scam"], proba)), 4) if test["scam"].nunique() > 1 else None,
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def vaani_set(model):
    """How the model alone does on eval/messages.csv (Indian bank messages we wrote by hand)."""
    path = ROOT / "eval" / "messages.csv"
    if not path.exists():
        return None
    ev = pd.read_csv(path)
    proba = model.predict_proba(ev["text"])[:, 1]
    fake = ev["label"] == "fake"
    return {
        "messages": int(len(ev)),
        "scams_flagged": f"{int(((proba >= 0.5) & fake).sum())}/{int(fake.sum())}",
        "genuine_flagged": f"{int(((proba >= 0.5) & ~fake).sum())}/{int((~fake).sum())}",
    }


def main():
    public = clean(pd.concat(load_public(), ignore_index=True))
    train, test = train_test_split(public, test_size=0.2, random_state=42, stratify=public["scam"])

    synth_path = DATA / "india_synthetic.csv"
    synth = clean(_simple(synth_path, "india_synthetic")) if synth_path.exists() else public.iloc[:0]
    synth = synth[~synth["text"].isin(test["text"])]
    train_all = pd.concat([train, synth], ignore_index=True)

    # same model, with and without the Indian templates, so we can show what they change
    plain = build().fit(train["text"], train["scam"])
    model = build().fit(train_all["text"], train_all["scam"])

    _, pred, m_test = scores(model, test)
    _, _, m_plain = scores(plain, test)
    smish = test[test["smishing"] == 1]
    smish_recall = float((model.predict_proba(smish["text"])[:, 1] >= 0.5).mean()) if len(smish) else None

    metrics = {
        "trained_at": time.strftime("%Y-%m-%d"),
        "train_rows": {"public": int(len(train)), "india_synthetic": int(len(synth))},
        "test_rows": int(len(test)),
        "test_sources": test["source"].value_counts().to_dict(),
        "held_out_test": m_test,
        "held_out_test_without_india_templates": m_plain,
        "smishing_recall": round(smish_recall, 4) if smish_recall is not None else None,
        "vaani_eval_set_model_only": vaani_set(model),
        "vaani_eval_set_model_only_without_india_templates": vaani_set(plain),
    }

    final = build().fit(pd.concat([public, synth], ignore_index=True)["text"],
                        pd.concat([public, synth], ignore_index=True)["scam"])
    OUT.mkdir(exist_ok=True)
    joblib.dump({"model": final, "metrics": metrics, "version": metrics["trained_at"]},
                OUT / "sms_scam_clf.joblib", compress=3)
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))

    report = classification_report(test["scam"], pred, target_names=["genuine", "scam"], digits=3)
    ve, vp = metrics["vaani_eval_set_model_only"], metrics["vaani_eval_set_model_only_without_india_templates"]
    lines = [
        "# Scam SMS classifier",
        "",
        f"Trained on {len(train)} real public messages + {len(synth)} synthetic Indian templates.",
        f"Tested on {len(test)} held-out real messages ({metrics['test_sources']}). No synthetic rows in the test set.",
        "",
        "## Held-out test (real messages)",
        "",
        "```",
        report,
        "```",
        "",
        f"- ROC AUC: {m_test['roc_auc']}   (without Indian templates: {m_plain['roc_auc']})",
        f"- F1: {m_test['f1']}   (without Indian templates: {m_plain['f1']})",
        f"- Recall on smishing messages only: {metrics['smishing_recall']}",
        f"- Confusion: {m_test['confusion']}",
        "",
        "## On Vaani's Indian bank message set (eval/messages.csv), model alone",
        "",
        "| | scams flagged | genuine alerts wrongly flagged |",
        "|---|---|---|",
        f"| Kaggle data only | {vp['scams_flagged'] if vp else '-'} | {vp['genuine_flagged'] if vp else '-'} |",
        f"| Kaggle data + Indian templates | {ve['scams_flagged'] if ve else '-'} | {ve['genuine_flagged'] if ve else '-'} |",
        "",
        "Trained only on Kaggle data, the model calls most genuine Indian bank alerts spam,",
        "because those datasets contain almost none. That is why Vaani uses the model as one",
        "warning sign next to the registry checks, never as the verdict. The Indian set above",
        "was written by us, so treat those numbers as a sanity check, not a result.",
    ]
    (OUT / "report.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
