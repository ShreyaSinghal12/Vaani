"""Word error rate (WER) for dialect speech recognition.

Record short questions from native speakers, put the files in eval/clips/ and
list them in eval/clips.csv:

    file,dialect,reference
    malwai_01.webm,malwai,<exactly what the speaker said, in Gurmukhi>
    (see eval/clips.csv for two real examples)

Then:
    python -m eval.wer                   # sends each clip to Sarvam (needs SARVAM_API_KEY)
    python -m eval.wer --hyp-column hyp  # or score transcripts you already have in a 'hyp' column

WER = (substitutions + deletions + insertions) / words in the reference.
Lower is better. 0.25 means one word in four was wrong.
"""
import argparse
import csv
import re
from pathlib import Path

HERE = Path(__file__).parent


def words(s):
    # only strip punctuation; \w would also eat Devanagari/Gurmukhi vowel signs
    s = re.sub(r"[.,!?;:'\"()\[\]\u0964\u0965-]", " ", s.lower())
    return s.split()


def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    if not r:
        return 0.0
    prev = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        cur = [i] + [0] * len(h)
        for j in range(1, len(h) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r[i - 1] != h[j - 1]))
        prev = cur
    return prev[-1] / len(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(HERE / "clips.csv"))
    ap.add_argument("--hyp-column", default="")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.file, encoding="utf-8")))
    if not args.hyp_column:
        from app import speech
        from app.replies import load
        if not speech.enabled():
            raise SystemExit("Set SARVAM_API_KEY, or pass --hyp-column with your own transcripts.")

    per_dialect = {}
    for r in rows:
        if args.hyp_column:
            hyp = r.get(args.hyp_column, "")
        else:
            audio = (HERE / "clips" / r["file"]).read_bytes()
            hyp = speech.transcribe(audio, r["file"], load(r["dialect"])["meta"]["speech_lang"])
        score = wer(r["reference"], hyp)
        per_dialect.setdefault(r["dialect"], []).append(score)
        print(f"{r['file']:24} WER {score:.2f}   heard: {hyp}")

    print()
    for d, scores in per_dialect.items():
        print(f"{d:10} clips={len(scores):3}  mean WER={sum(scores) / len(scores):.2f}")


if __name__ == "__main__":
    main()
