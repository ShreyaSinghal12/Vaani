#!/usr/bin/env bash
# Pull the training data straight from Kaggle instead of the copies in ml/data/.
# One-time setup: kaggle.com > Settings > API > Create New Token, save it as ~/.kaggle/kaggle.json
set -e
cd "$(dirname "$0")"
pip install -q kaggle

# UCI SMS Spam Collection (5,574 messages)
kaggle datasets download -d uciml/sms-spam-collection-dataset -p data/kaggle_raw --unzip

# Indian SMS spam (real Indian messages) - more Indian data is the single best improvement
kaggle datasets download -d junioralive/india-spam-sms-classification -p data/kaggle_raw --unzip || true

mkdir -p data/kaggle_extra
python - <<'PY'
import glob, pandas as pd
for f in glob.glob("data/kaggle_raw/*.csv"):
    df = pd.read_csv(f, encoding_errors="replace")
    cols = {c.lower().strip(): c for c in df.columns}
    text = next((cols[c] for c in ("text", "message", "msg", "sms", "v2") if c in cols), None)
    label = next((cols[c] for c in ("label", "category", "class", "v1", "type") if c in cols), None)
    if not text or not label:
        print("skip (columns not recognised):", f, list(df.columns)); continue
    out = pd.DataFrame({"text": df[text].astype(str), "label": df[label].astype(str).str.lower()})
    name = f.split("/")[-1]
    out.to_csv("data/kaggle_extra/" + name, index=False)
    print("ready:", name, len(out), out["label"].value_counts().to_dict())
PY
echo "Now run: python -m ml.train"
