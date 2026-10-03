# Vaani

**Is this bank message real? Ask in your own dialect.**

Vaani is a small web app for people in villages who get bank SMS they can't fully read. You paste the message (or send a photo of it, or just ask out loud), and Vaani tells you in Malwai Punjabi, Haryanvi, Punjabi, Hindi or English whether it is **Real**, **Fake** or **Not sure**, why, and what to do next. Then you can ask follow-up questions ("what is CIF?", "which papers?") by voice and get an answer in the same dialect.

Built by TEAM404 (Shreya Singhal, Ishika Jain) for the Build Fast with AI Hackathon 2026, PS-06: AI for Bharat in Indian Languages.

---

## Why we built it

Bank alerts arrive in English jargon: "re-KYC", "NACH mandate failed", "auto-debit". Scam messages copy exactly the same words. For someone who speaks Malwai or Haryanvi at home and reads little English, the two look identical. So they either ignore a real alert (frozen account, bounced EMI, penalty) or trust a fake one (one tapped link or one shared OTP and the savings are gone). Most people end up asking a son, a neighbour or the local cyber cafe.

Scam-checker apps exist, but they guess from word patterns, so a real bank link can get flagged too, and they only warn you; they don't help you finish a genuine task. Chatbots explain nicely but can't confirm who sent a message, and sometimes make up phone numbers.

## What makes it different

1. **It checks against the bank's own records, not word patterns.** Every bank in `data/banks.json` has its official websites (including the new `.bank.in` domains RBI asked banks to move to), SMS sender names, helpline and, where we have it, the real procedure, each with a source link and the date we checked it. Anyone can see this list at `/sources.html`.
2. **It helps with real messages too.** For a genuine Indian Bank re-KYC alert it shows the bank's actual options and opens your SMS app with `REKYC NOCHANGE <your CIF>` already typed out to 9677633000.
3. **It speaks your dialect, both ways.** Ask by voice in your own words; the answer is read back in your dialect.
4. **AI where it helps, rules where it matters.** Models listen, read, speak, add warning signs and answer follow-ups. The verdict itself comes from fixed, explainable rules, so a well-written scam can't talk its way to "Real".

## The models

| Job | Model | Notes |
|---|---|---|
| Speech to text in Punjabi / Hindi | **Sarvam saarika:v2.5** | Falls back to Chrome's own recogniser without a key |
| Voice replies | **Sarvam bulbul:v2** | Recorded native-speaker clips play first if present |
| Reading messy / Hinglish messages | **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) | Fills in bank and message type, flags hidden OTP requests. Never gives the verdict |
| Reading screenshots | **Claude Haiku 4.5** (vision) | Copies the SMS and sender exactly. Falls back to Tesseract in the browser |
| Follow-up questions in dialect | **Claude Sonnet 5.5** (`claude-sonnet-5-5`) | Answers only from the facts we pass it; a guard blocks any phone number, website or OTP request it wasn't given |
| Scam-SMS classifier | **TF-IDF + logistic regression, trained by us** (`ml/`) | Trained on real public Kaggle data + Indian templates. One warning sign, can't overrule the registry |
| Verdict | **Fixed rules** (`app/verdict.py`) | Explainable; shown step by step under "How we checked" |

All of these are listed live at `/api/models` and on `/sources.html`.

### The classifier we trained

`python -m ml.train` trains it; results are in `ml/model/report.md`.

- **Data:** the *SMS Phishing Dataset* (Mishra & Soni, 2022; 5,971 messages labelled ham / spam / smishing) and the *UCI SMS Spam Collection* (5,574 messages), both on Kaggle. Most UCI messages are already inside the first set, so after removing duplicates we have 6,051 real messages.
- **Held-out test** (1,211 real messages, never seen in training): **F1 0.974, ROC AUC 0.997**, 205 of 213 scams caught, 3 of 998 normal messages flagged.
- **The catch we found:** trained only on Kaggle data, the model called **18 of 20** genuine Indian bank alerts spam, because those datasets contain almost no Indian bank alerts. So we added ~1,000 template-generated Indian alerts and scams (`ml/augment_india.py`, training only). That brought it to **3 of 20**, with no change on the real test set. Those Indian numbers come from messages we wrote ourselves, so they're a sanity check, not proof.
- **How Vaani uses it:** a score of 0.9 or more becomes one warning sign, unless the message already has an official link or a known sender. One warning alone gives "Not sure"; together with another warning it gives "Fake".
- **To make it better:** put real messages from your phones in `ml/data/india_real.csv` (`text,label`, label `ham` or `scam`), or run `ml/get_kaggle.sh` to pull more Kaggle data (including a real Indian spam SMS set), then retrain. Both are picked up automatically.

## How a message flows

```
 voice note / SMS / screenshot
          |
   1 LISTEN   Sarvam saarika (or the browser)                         app/speech.py
   2 READ     regex rules + Claude Haiku: bank, request, links,        app/extract.py, app/llm.py
              amount, deadline, sender
   3 CHECK    bank registry + red-flag rules + our classifier          app/checks.py, app/classifier.py
   4 DECIDE   fixed rules -> Real / Fake / Not sure                     app/verdict.py
   5 REPLY    dialect lines, filled in, spoken by Sarvam bulbul         app/replies.py
   6 ASK      follow-up questions answered by Claude Sonnet, guarded    app/replies.py (followup, guard)
```

Every answer has a **"How we checked"** section showing this trace: what was read and by which model, every check with its result and the classifier score, the rule that decided, and how the reply was voiced.

### The rules in one screen

| Check | Level |
|---|---|
| Asks you to share or enter OTP / PIN / CVV / password (but "do not share your OTP" is fine) | hard |
| Asks you to install AnyDesk, TeamViewer, QuickSupport, screen share | hard |
| Link to an `.apk` file | hard |
| Link uses a bank's name but isn't its domain (`indianbank-kyc.in`, `sbi-kyc.xyz`) | hard |
| Message names a bank, link isn't one of that bank's domains | hard |
| Sent from an ordinary mobile number while claiming to be a bank | hard |
| Short link (bit.ly, tinyurl...) | warning |
| Asks you to call a mobile number | warning |
| Threat or rush ("blocked today", "within 24 hours") | warning |
| Prize / refund / cashback bait | warning |
| Unknown sender name | warning |
| Classifier score of 0.9 or more, and no official link or known sender | warning |
| Claude says it asks for a secret but our keywords missed it | warning |
| Link is on the bank's official list | good |
| Sender name is one the bank uses | good |

Any hard flag, or two warnings, means **Fake**. One warning, an unknown bank, or a link we can't place means **Not sure** ("don't click, call the number on your card"). No flags plus positive evidence (or a normal alert with no link) means **Real**.

### Who decides what

- **The system decides alone:** clear matches or mismatches with the registry.
- **A person decides:** "Not sure" sends you to the bank's official helpline. Anything sent to the bank (like the re-KYC SMS) is prepared by Vaani but sent by you. Vaani never sends anything itself and never asks for an OTP or PIN.
- **Why:** a wrong "Real" can cost someone their savings, so when in doubt we say "Not sure".

---

## Run it locally

Needs Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # put your keys in here
uvicorn app.main:app --reload
```

Open http://localhost:8000 in Chrome. On a phone, voice needs HTTPS, so test voice on the deployed link.

### API keys

| Key | Get it from | Turns on |
|---|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com | Claude reading, screenshots, follow-up answers |
| `SARVAM_API_KEY` | https://dashboard.sarvam.ai | Sarvam speech to text and voices |

Set both on the deployed app. Without them the app still runs (rules + our classifier still check every message), but the judges won't see Claude or Sarvam working.

### Tests

```bash
pytest -q
```

29 tests, including the Claude parts (with Claude's replies faked so no credits are used): it fills in the bank, its secret flag stays a warning, and the guard blocks an invented phone number or website.

---

## Deploy (free) on Render

1. Push this folder to a GitHub repo.
2. On https://render.com: **New > Blueprint**, pick the repo. `render.yaml` sets everything up.
3. Under Environment, add `ANTHROPIC_API_KEY` and `SARVAM_API_KEY`.
4. Open the `.onrender.com` link on your phone. In Chrome, **Add to Home screen**; after that Vaani shows up in Android's **Share** menu, so you can share an SMS straight into it.

Also works with Railway (`Procfile`) or any Docker host (`Dockerfile`). The free Render instance sleeps after 15 minutes idle; open it once a minute before the demo.

---

## Evaluation

```bash
python -m eval.run_eval          # rules + classifier
python -m eval.run_eval --llm    # also Claude reading (needs the key)
```

Runs every message in `eval/messages.csv` through Vaani, a plain keyword spam filter, and our classifier on its own, and writes:

- `eval/results/report.md`: scams caught / missed, real messages wrongly flagged, "not sure" rates, bank and type reading accuracy, all three side by side
- `eval/results/traces.jsonl`: the full step-by-step trace of every message
- `eval/results/failures.csv`: every wrong answer and the rule that fired

**Be honest about the numbers.** The 46 messages in `eval/messages.csv` were written by us while building the rules, so Vaani scores almost perfectly on them. That's not a real result. The real test is the real bank SMS from our families plus public scam samples. Put them in a file with the same columns (`id,label,source,sender,bank,type,text,notes`), mask account numbers, and run:

```bash
python -m eval.run_eval --file eval/real_messages.csv
```

The classifier's own numbers (`ml/model/report.md`) are on real held-out Kaggle messages and can be quoted as they are.

### Speech accuracy (WER)

Record short questions from native speakers into `eval/clips/`, list them in `eval/clips.csv`, then:

```bash
python -m eval.wer                     # sends clips to Sarvam
python -m eval.wer --hyp-column hyp    # or score transcripts you already have
```

### Wrong answers in the app

"This answer looks wrong" on every result saves the check ID and a note. See them at `/api/feedback`.

---

## Things the team still has to do

- **Get the dialect lines checked by a native speaker.** `data/replies/malwai.json` and `haryanvi.json` are drafts; each has `"review": "needs native speaker review"` in `meta`.
- **Record the key lines** in each dialect into `static/audio/<dialect>/` (see the README there).
- **Confirm the registry.** Indian Bank was checked on its own page; the other four banks' helplines and sender codes are marked `helpline_verified: false` until you confirm them.
- **Collect real messages**, add them to `ml/data/india_real.csv` and `eval/real_messages.csv`, retrain and re-run the evaluation.

## Project layout

```
app/
  main.py         FastAPI routes (/api/check, /api/ask, /api/models, ...)
  pipeline.py     listen -> read -> check -> decide, builds the trace
  extract.py      regex/keyword reading of the message
  checks.py       evidence checks against the registry
  classifier.py   loads our trained scam-SMS model
  verdict.py      the fixed decision rules
  replies.py      dialect lines, follow-up answers and their guard
  llm.py          Claude: reading, screenshots, follow-ups
  speech.py       Sarvam speech to text / text to speech
  registry.py     loads data/banks.json
  store.py        SQLite log + feedback
data/             bank registry, keywords, one reply file per dialect
ml/               training data, augment_india.py, train.py, get_kaggle.sh, the trained model
static/           the web app (plain HTML/CSS/JS, installable, share target)
eval/             test messages, baselines, eval script, WER script
tests/            pytest
```

## Limits

- Five banks for now: SBI, PNB, HDFC, ICICI, Indian Bank. Anything else gets "Not sure".
- A link read out loud can't be checked letter by letter, so voice-only links get "Not sure".
- The classifier has seen few real Indian messages; real data from your phones is the biggest single improvement.
- This is a helper, not a guarantee. When in doubt, call the number printed on your card.
