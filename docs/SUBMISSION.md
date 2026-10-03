# Final submission kit

## Project title

Vaani: a voice assistant that checks bank messages in Indian languages and dialects

## Project description + why we created it

Vaani tells people, in their own dialect, whether a bank message is real or fake and what to do next. You paste the SMS, send a photo of it, or just ask out loud in Malwai Punjabi, Haryanvi, Punjabi, Hindi or English. Vaani answers Real, Fake or Not sure, explains why, reads it aloud, and then answers follow-up questions like "what is CIF?" in the same dialect.

Under the hood: Sarvam's Indian-language models listen and speak; Claude reads messy Hinglish messages and screenshots and answers follow-up questions; and a scam-SMS classifier we trained on real Kaggle data (F1 0.974 on 1,211 held-out messages) adds a second opinion. The final call doesn't come from any of them. Vaani checks the message against each bank's official websites (including the new .bank.in domains), SMS sender names, helplines and procedures, and fixed rules decide. That way a well-written scam can't talk its way to "Real", and every answer shows exactly how it was reached. For genuine alerts it goes further: for an Indian Bank re-KYC message it opens the SMS app with the exact reply the bank expects. If you've already clicked a bad link or shared an OTP, one button walks you through the first few minutes.

Why we built it: bank alerts come in English jargon, and scammers copy the same words. For someone who speaks only their local dialect, a real re-KYC notice and a fake one look identical. Ignoring the real one means a frozen account or penalty; trusting the fake one can empty the account. Today they ask a relative or the local cyber cafe, or guess. We wanted something they could ask the way they talk at home.

## Links to fill in

- GitHub: https://github.com/<your-username>/vaani
- Deployed: https://vaani-xxxx.onrender.com (set ANTHROPIC_API_KEY and SARVAM_API_KEY there)
- Demo video: (YouTube unlisted or Google Drive, "anyone with the link")
- PPT: (PDF export)

## Demo video script (about 3 minutes)

Record on a real Android phone with screen recording, voice on, keys set on the server.

1. **0:00-0:15 The problem.** Two SMS side by side: a real Indian Bank re-KYC alert and a fake one with `indianbank-kyc.in`. "These look the same. For my grandmother, who speaks Malwai, they are the same."
2. **0:15-0:25 Pick dialect.** Tap the speaker next to each dialect (Sarvam voice), pick Malwai.
3. **0:25-0:55 Fake message by voice.** Share the fake SMS into Vaani from the Messages app, hold the mic and ask "ਆਹ ਮੈਸਜ ਅਸਲੀ ਆ?". It answers **Fake** aloud in Malwai. Point at the reason: the link copies Indian Bank's name but isn't on its list.
4. **0:55-1:25 Real message.** Paste the genuine one with sender `AD-INDBNK-S`. **Real**; type the CIF, tap "SMS ready, send": the SMS app opens with `REKYC NOCHANGE 12345678` to 9677633000.
5. **1:25-1:45 Follow-up.** Hold the mic: "CIF ki hunda?" Claude answers in Malwai from the facts on screen.
6. **1:45-2:00 Screenshot.** Upload a screenshot of a scam; Claude reads it, Vaani says Fake.
7. **2:00-2:10 Only the link changes.** HDFC bill message with `hdfc.bank.in`: Real. Change the link to `hdfc-rewardz.com`: Fake.
8. **2:10-2:20 Already clicked.** The red button: flight mode, remove AnyDesk, call the bank, call 1930.
9. **2:20-2:40 How we checked.** Open the trace: which model read it, every check, the classifier score, the rule that decided. Then `/sources.html`: the models in use and the bank records with sources.
10. **2:40-3:00 Numbers.** Classifier report (F1 0.974 on real held-out data, and the 18-of-20 to 3-of-20 Indian false alarm fix), then the eval report on your real message set next to the keyword baseline, including what went wrong.

## What to add to the final PPT

- Title slide with the deployed and GitHub links.
- A "Models" slide: the table from the README (Sarvam saarika / bulbul, Claude Haiku / Sonnet, our classifier, fixed-rule verdict).
- A "We trained a model" slide: data (Mishra & Soni smishing set + UCI SMS spam from Kaggle), held-out F1 0.974 / ROC AUC 0.997, and the honest finding: trained only on Kaggle data it flagged 18 of 20 genuine Indian alerts, so we added Indian templates and kept it as a warning sign instead of the judge.
- Screenshots: dialect picker, a Fake result, a Real result with the SMS button, a follow-up answer, the "already clicked" panel, the trace.
- The eval results **on your real message set** next to both baselines. Replace the old targets with measured numbers.
- WER per dialect from `python -m eval.wer`.
- One slide of failures from `failures.csv`: what went wrong and what you changed.
