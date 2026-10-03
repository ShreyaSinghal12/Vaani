"""Runs every message in eval/messages.csv through Vaani and the keyword baseline.

    python -m eval.run_eval              # rules only (what the demo uses without keys)
    python -m eval.run_eval --llm        # also let Claude fill in bank/type

Writes:
    eval/results/report.md     the numbers for the PPT
    eval/results/traces.jsonl  step-by-step trace of every message
    eval/results/failures.csv  every message we got wrong, with the rule that fired
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from app import classifier
from app.pipeline import check_message
from eval.baseline import baseline_verdict

HERE = Path(__file__).parent
OUT = HERE / "results"


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(HERE / "messages.csv"))
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    rows = list(csv.DictReader(open(args.file, encoding="utf-8")))

    ours, base, clf = Counter(), Counter(), Counter()
    bank_ok = type_ok = typed = 0
    failures = []
    with open(OUT / "traces.jsonl", "w", encoding="utf-8") as tf:
        for r in rows:
            res = check_message(r["text"], r["sender"], use_llm=args.llm)
            v, b = res["verdict"], baseline_verdict(r["text"])
            ours[(r["label"], v)] += 1
            base[(r["label"], b)] += 1
            score = classifier.score(r["text"])
            if score is not None:
                clf[(r["label"], "fake" if score >= 0.5 else "real")] += 1

            want_bank = None if r["bank"] in ("", "unknown") else r["bank"]
            bank_ok += res["extracted"]["bank"] == want_bank
            if r["type"]:
                typed += 1
                type_ok += res["extracted"]["type"] == r["type"]

            tf.write(json.dumps({"id": r["id"], "label": r["label"], "verdict": v, "trace": res["trace"]}, ensure_ascii=False) + "\n")

            wrong = (r["label"] == "fake" and v == "real") or (r["label"] == "real" and v == "fake")
            if wrong or (r["label"] == "real" and v == "not_sure"):
                failures.append({"id": r["id"], "label": r["label"], "verdict": v, "rule": res["rule"], "text": r["text"], "notes": r["notes"]})

    n_fake = sum(1 for r in rows if r["label"] == "fake")
    n_real = len(rows) - n_fake

    def block(c, name):
        missed = c[("fake", "real")]
        caught = c[("fake", "fake")]
        unsure_fake = c[("fake", "not_sure")]
        false_alarm = c[("real", "fake")]
        unsure_real = c[("real", "not_sure")]
        return [
            f"### {name}",
            "",
            "| | count | rate |",
            "|---|---|---|",
            f"| Scams called **Fake** | {caught} / {n_fake} | {pct(caught, n_fake)} |",
            f"| Scams called **Not sure** (user told not to click) | {unsure_fake} / {n_fake} | {pct(unsure_fake, n_fake)} |",
            f"| Scams **missed** (called Real) | {missed} / {n_fake} | {pct(missed, n_fake)} |",
            f"| Real messages wrongly called **Fake** | {false_alarm} / {n_real} | {pct(false_alarm, n_real)} |",
            f"| Real messages called **Not sure** | {unsure_real} / {n_real} | {pct(unsure_real, n_real)} |",
            "",
        ]

    lines = [
        "# Vaani evaluation",
        "",
        f"Messages: {len(rows)} ({n_fake} scam, {n_real} genuine). Source file: `{Path(args.file).name}`.",
        f"Language model used: {'yes' if args.llm else 'no (rules only)'}.",
        "",
    ]
    lines += block(ours, "Vaani")
    lines += block(base, "Baseline: keyword spam filter")
    if sum(clf.values()):
        lines += block(clf, "Baseline: our Kaggle-trained classifier on its own (score >= 0.5 = fake)")
    lines += [
        "### Reading the message",
        "",
        f"- Bank identified correctly: {bank_ok} / {len(rows)} ({pct(bank_ok, len(rows))})",
        f"- Message type identified correctly: {type_ok} / {typed} ({pct(type_ok, typed)})",
        "",
        f"Failures and 'not sure' on genuine messages: {len(failures)} (see failures.csv)",
    ]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")

    with open(OUT / "failures.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "label", "verdict", "rule", "text", "notes"])
        w.writeheader()
        w.writerows(failures)

    print("\n".join(lines))


if __name__ == "__main__":
    main()
