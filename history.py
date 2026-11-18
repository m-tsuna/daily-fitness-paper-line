"""送った論文の記録（sent.json）を読み書きする（通信しない）。

記録の形：[{"date": "2026-11-19", "pmid": "12345678", "topic": "ボディビル", "title": "..."}, ...]
- 同じ論文を2回送らないため（pmid を見る。"skipped": true は、使えないので飛ばした論文）
- 同じ日に2回送らないため（date を見る。7時17分に送れた日は、10時17分の予備の実行では送らない）
"""

import json


def load(path):
    """記録を読む。ファイルが無ければ空のリスト。"""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise SystemExit(f"記録のファイル（{path.name}）の形が壊れています → GitHub の履歴から前の版に戻してください")
    return data if isinstance(data, list) else []


def sent_today(records, today):
    """今日もう送ったか。today は "2026-11-19" の形の文字。"""
    return any(r.get("date") == today and not r.get("skipped") for r in records)


def sent_pmids(records):
    """これまでに送った論文の番号の集まり。"""
    return {r.get("pmid") for r in records}


def add(path, records, today, topic, paper, skipped=False):
    """送った論文を記録に足して保存する。

    skipped=True は「AI が現場で使えないと判断して送らなかった論文」。次からは候補にしない。
    """
    row = {"date": today, "pmid": paper["pmid"], "topic": topic, "title": paper["title"]}
    if skipped:
        row["skipped"] = True
    records.append(row)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
