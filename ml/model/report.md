# Scam SMS classifier

Trained on 4840 real public messages + 1042 synthetic Indian templates.
Tested on 1211 held-out real messages ({'kaggle_mishra_soni_smishing': 1160, 'kaggle_uci_sms_spam': 51}). No synthetic rows in the test set.

## Held-out test (real messages)

```
              precision    recall  f1-score   support

     genuine      0.992     0.997     0.995       998
        scam      0.986     0.962     0.974       213

    accuracy                          0.991      1211
   macro avg      0.989     0.980     0.984      1211
weighted avg      0.991     0.991     0.991      1211

```

- ROC AUC: 0.9968   (without Indian templates: 0.9971)
- F1: 0.9739   (without Indian templates: 0.974)
- Recall on smishing messages only: 0.9829
- Confusion: {'tn': 995, 'fp': 3, 'fn': 8, 'tp': 205}

## On Vaani's Indian bank message set (eval/messages.csv), model alone

| | scams flagged | genuine alerts wrongly flagged |
|---|---|---|
| Kaggle data only | 24/26 | 18/20 |
| Kaggle data + Indian templates | 25/26 | 3/20 |

Trained only on Kaggle data, the model calls most genuine Indian bank alerts spam,
because those datasets contain almost none. That is why Vaani uses the model as one
warning sign next to the registry checks, never as the verdict. The Indian set above
was written by us, so treat those numbers as a sanity check, not a result.