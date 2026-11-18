"""まとめテスト：各曜日の論文を何本か、LINE に送らずに要約して、自動でチェックする（通信する）。

使い方：python evaluate.py [1曜日あたりの本数（ふつうは2）]
結果は test_data/eval_日付.json に保存する（要旨と要約を並べて、人が照らし合わせるため）。

自動チェック：
- 数字：要約に出てくる数字が、要旨にもあるか（要旨に無い数字を作っていないか）
- 言ってはいけない言い方：「明記されていません」「安静にしてください」など
- 長さ：LINE で読める長さか
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import config
import history
import message
import pubmed
import summarize

OUT_DIR = Path(__file__).parent / "test_data"
NG_WORDS = ["明記されていません", "不明です", "安静にしてください", "医師に相談", "である。"]
PLAIN_END = re.compile(r"(?<![まで])(した|った|る)。")  # です・ます で終わっていない文（「ました。」「でした。」は除く）
MAX_CHARS = 1200  # これより長いと、LINE で読むのが大変


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def words_to_digits(text):
    """英語で書かれた数（Fifty-six・Eleven など）を数字に直す。要旨は文の頭の数を英語で書くため。"""
    def tens(m):
        return str(TENS[m.group(1).lower()] + (ONES.index(m.group(2).lower()) if m.group(2) else 0))
    text = re.sub(r"\b(" + "|".join(TENS) + r")(?:-(" + "|".join(ONES[1:10]) + r"))?\b", tens, text, flags=re.I)
    return re.sub(r"\b(" + "|".join(ONES) + r")\b", lambda m: str(ONES.index(m.group(1).lower())), text, flags=re.I)


def numbers(text):
    """文の中の数字を取り出す（7.40 と 7.4 を同じに扱う）。"""
    text = words_to_digits(text)
    found = set()
    for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", "")):
        found.add(n.rstrip("0").rstrip(".") if "." in n else n)
    return found


def check(paper, summary, text):
    """自動チェックの結果を、問題のリストで返す（空なら問題なし）。"""
    problems = []
    body = " ".join(summary[k] for k in summarize.FIELDS if k != "title_ja")
    source = numbers(paper["abstract"] + " " + paper["title"])
    extra = sorted(n for n in numbers(body) - source if len(n) > 1 or n not in "123456789")
    if extra:
        problems.append(f"要旨に無い数字：{', '.join(extra)}")
    for w in NG_WORDS:
        if w in body:
            problems.append(f"言ってはいけない言い方：「{w}」")
    if PLAIN_END.search(body):
        problems.append(f"です・ます でない文：「…{PLAIN_END.search(body).group(0)}」")
    if len(text) > MAX_CHARS:
        problems.append(f"長すぎる：{len(text)}文字")
    return problems


def main():
    per_topic = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    load_dotenv(config.ENV_FILE)
    key = os.environ["GEMINI_API_KEY"]
    sent = history.sent_pmids(history.load(config.SENT_FILE))
    results = []
    for weekday, topic in config.TOPICS.items():
        print(f"== {'月火水木金土日'[weekday]}：{topic['name']}", flush=True)
        got = tried = 0
        for paper in pubmed.candidates(topic, sent, log=lambda *_: None):
            if got >= per_topic or tried >= per_topic + 3:
                break
            tried += 1
            sent.add(paper["pmid"])  # ほかの曜日で同じ論文を選ばない
            summary = summarize.summarize(key, paper, log=lambda *_: None)
            time.sleep(3)  # 無料枠の「1分あたりの回数」を超えないよう、少しあける
            if summary is None:
                print(f"  {paper['pmid']} AI が使えませんでした", flush=True)
                continue
            if not summarize.is_useful(summary):
                print(f"  {paper['pmid']} 飛ばす（役に立たない）：{paper['title'][:60]}", flush=True)
                results.append({"topic": topic["name"], "pmid": paper["pmid"], "skipped": True, "title": paper["title"]})
                continue
            text = message.build(paper, summary)
            problems = check(paper, summary, text)
            got += 1
            print(f"  {paper['pmid']} {'OK' if not problems else '要確認：' + ' ／ '.join(problems)}", flush=True)
            results.append({"topic": topic["name"], "pmid": paper["pmid"], "problems": problems,
                            "abstract": paper["abstract"], "message": text})
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"eval_{datetime.now():%Y%m%d_%H%M}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"保存しました：{out}")


if __name__ == "__main__":
    main()
