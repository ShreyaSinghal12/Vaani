# Training data

| File | What | Rows | Where from | Used for |
|---|---|---|---|---|
| `smishing_5971.csv` | SMS Phishing Dataset for Machine Learning and Pattern Recognition (Mishra & Soni, 2022). Labels: ham / spam / smishing | 5,971 | Kaggle / Mendeley Data `f45bkkt8pr`; this copy from a public GitHub mirror | train + test |
| `uci_sms.tsv` | UCI SMS Spam Collection. Labels: ham / spam | 5,574 | Kaggle `uciml/sms-spam-collection-dataset`; this copy from a public GitHub mirror | train + test (most rows are duplicates of the file above and get dropped) |
| `india_synthetic.csv` | Indian bank alerts and scams made from templates by `ml/augment_india.py` | ~1,000 | generated | **train only**, never test |
| `india_real.csv` | *(you add this)* real messages from your own phones, `text,label` with label `ham` or `scam`. Mask account numbers. | | your team | train + test |
| `kaggle_extra/*.csv` | *(optional)* anything `ml/get_kaggle.sh` downloads | | Kaggle | train + test |

Check each dataset's licence on its source page before redistributing.
