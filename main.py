"""筋トレ論文デイリー要約：全体の流れ。

毎朝 GitHub Actions が動かす（手元では `python main.py`）。
  今日もう送った？ → PubMed で探す → Gemini で日本語に要約 → LINE で送る → 記録する

使い方：
  python main.py               ふつうに動かす（LINE に送る）
  python main.py --dry-run     LINE に送らず、送る文を画面に出すだけ（記録もしない）
  python main.py --weekday 3   曜日のテーマを指定する（0=月 … 6=日。テスト用）

終わりの番号：0＝送れた／今日はもう送ってあった、1＝送れなかった（GitHub Actions では赤い×になる）
"""

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

import config
import history
import line_send
import message
import pubmed
import summarize

WEEKDAYS = "月火水木金土日"


def log(text):
    """途中経過を出す（GitHub Actions の記録にも残る）。すぐ表示されるよう flush する。"""
    print(text, flush=True)


def fail(text):
    """送れなかった理由を出して、番号1で終わる。"""
    log(f"❌ {text}")
    sys.exit(1)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="筋トレ論文を1本、日本語で要約して LINE で送る")
    p.add_argument("--dry-run", action="store_true", help="LINE に送らず、送る文を画面に出す")
    p.add_argument("--weekday", type=int, choices=range(7), help="曜日のテーマ（0=月 … 6=日）")
    return p.parse_args(argv)


def main(argv=None, now=None, sleep=None):
    args = parse_args(argv)
    load_dotenv(config.ENV_FILE)  # 手元の .env を読む（GitHub Actions では Secrets から環境変数に入る）

    now = now or datetime.now(ZoneInfo(config.TIMEZONE))
    today = now.strftime("%Y-%m-%d")
    weekday = now.weekday() if args.weekday is None else args.weekday
    topic = config.TOPICS[weekday]
    log(f"📅 {today}（{WEEKDAYS[now.weekday()]}）テーマ：{topic['name']}" + ("　※送らない試し" if args.dry_run else ""))

    records = history.load(config.SENT_FILE)
    if not args.dry_run and history.sent_today(records, today):
        log("✅ 今日の論文はもう送ってあります（予備の実行なので、何もせず終わります）")
        return 0

    # 鍵を確かめる（中身は表示しない）
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not gemini_key:
        fail("Gemini の鍵（GEMINI_API_KEY）がありません → Google AI Studio で鍵を作り、.env（GitHub では Secrets）に入れてください")
    if not line_token and not args.dry_run:
        fail("LINE のトークン（LINE_CHANNEL_ACCESS_TOKEN）がありません → LINE Developers で発行し、.env（GitHub では Secrets）に入れてください")

    # 1. 論文を探す → 2. 日本語に要約する
    #    現場で使えない論文（3つの用途とも「言えません」）は飛ばして次へ。AI が駄目なら英語のまま送らない
    kwargs = {"sleep": sleep} if sleep else {}
    paper = summary = None
    tried = 0
    try:
        for candidate in pubmed.candidates(topic, history.sent_pmids(records), log):
            log(f"📄 候補：PMID {candidate['pmid']}「{candidate['title'][:60]}…」")
            result = summarize.summarize(gemini_key, candidate, log, **kwargs)
            if result is None:
                fail("AI（Gemini）が混んでいて、日本語の要約を作れませんでした。英語のままでは送りません"
                     " → 10時17分の予備の実行でもう一度試します（手で試すなら、少し時間をおいて動かしてください）")
            tried += 1
            if summarize.is_useful(result):
                paper, summary = candidate, result
                break
            log("  → トレーニング・指導・施術のどれにも使えない論文なので、飛ばします")
            if not args.dry_run:
                history.add(config.SENT_FILE, records, today, topic["name"], candidate, skipped=True)
            if tried >= config.MAX_SUMMARIES:
                break
    except pubmed.PubMedError as e:
        fail(str(e))
    if paper is None:
        fail(f"「{topic['name']}」で、現場に使える新しい論文が見つかりませんでした"
             " → config.py の検索の言葉か、探す期間（SEARCH_STEPS）を広げてください")

    text = message.build(paper, summary)
    if args.dry_run:
        log("----- 送る文（送っていません） -----")
        log(text)
        log(f"----- {len(text)}文字 -----")
        return 0

    # 3. LINE で送り、記録する
    try:
        line_send.send(line_token, text)
    except line_send.LineError as e:
        fail(str(e))
    history.add(config.SENT_FILE, records, today, topic["name"], paper)
    log(f"✅ LINE に送りました（{len(text)}文字）。記録：{config.SENT_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
