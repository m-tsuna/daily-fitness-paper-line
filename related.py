"""関連する別の研究を探して、対応策を短く添える（通信する）。

今日の論文に具体的なやり方（食事・トレーニング・サプリ）が書かれていない日だけ動く
（2026-11-26、ご主人の「結果に対する対応策の部分が欲しい」から。遺伝子の研究などで起きる）。

流れ：
  1. Gemini に「探したい対応策」と PubMed の検索の言葉を作ってもらう
  2. PubMed で、信頼性の高い研究（メタ分析・ランダム化比較試験など）を探す
  3. Gemini に、対応策に答えている1本を選んでもらい、その要旨にあることだけで2〜3文を書いてもらう

どこかで駄目なら None を返す（呼ぶ側は、関連する研究を添えずに今日の論文だけを送る。送るのは止めない）。
止めるときは config.RELATED_STUDY = False。
"""

import json
import time

import config
import pubmed
import summarize

QUERY_PROMPT = """次の論文は、食事・トレーニング・サプリの具体的なやり方が書かれていない研究です。
トレーナーが「では、実際にどうすればいいか」を知るために、同じテーマで具体的なやり方を比べた研究を PubMed で探します。
- need：探したい対応策を日本語で1文（例：減量中に筋力を落とさない食事やトレーニングの方法）
- query：PubMed の検索の言葉（英語。2〜4個の言葉を AND でつなぐ。遺伝子の名前など、この論文だけの細かい言葉は入れない）
論文：
"""

PICK_PROMPT = """柔道整復師でパーソナルトレーナー（自分もボディビルの大会に出る）に、ある論文の「対応策」を補うため、
関連する論文を1本選び、その要旨に書いてある対応策を短く書きます。自分のトレーニングにも、お客さんへの説明にも使います。

探したい対応策：{need}
今日の論文の対象：{target}

守ること：
- 候補の中から、探したい対応策に具体的に答えている論文を1本だけ選ぶ。どれも答えていなければ pmid を空にする
- text は、選んだ論文の要旨に書いてあることだけで、2〜3文（200文字以内）。数字は要旨にあるものだけ使う
- 書き出しは「〜を調べた別の研究（メタ分析など、研究の種類）では、」の形にする
- 選んだ論文の対象が今日の論文の対象と違うとき（肥満の人・高齢者・アスリートなど）は、「太りぎみの人の研究ですが、」のように対象をはっきり書く
- 何をどれくらいしたら、何がどれだけ変わったか（平均〇kg 多く残った など）を、要旨にある主な数字1〜2個で書く
- 割合は意味が分かる言葉にする（例：落ちる量の半分近く（45.7%）を防ぎました）
- 統計の言葉（有意・信頼区間・効果量・P スコア・探索的など）は使わない。効果量の数字は書かない
- やさしい日本語で、文末は「です」「ます」「ました」「でした」で終える

候補：
"""

QUERY_SCHEMA = {
    "type": "object",
    "properties": {"need": {"type": "string"}, "query": {"type": "string"}},
    "required": ["need", "query"],
}
PICK_SCHEMA = {
    "type": "object",
    "properties": {"pmid": {"type": "string"}, "text": {"type": "string"}},
    "required": ["pmid", "text"],
}


def needed(summary):
    """関連する研究を探すか（スイッチが入っていて、今日の論文に具体的なやり方が書かれていないとき）。"""
    return config.RELATED_STUDY and summary.get("no_method", False)


def _ask(api_key, prompt, schema, log, sleep):
    """Gemini に頼んで、返事（辞書）を返す。混雑なら待ってやり直し、駄目なら次のモデル。全部駄目なら None。"""
    for model in config.GEMINI_MODELS:
        model = model.strip()
        if not model or model in summarize.unavailable:
            continue
        for attempt in range(len(config.GEMINI_RETRY_WAITS) + 1):
            status, text = summarize._post(api_key, model, prompt, schema)
            if text is not None:
                try:
                    data = json.loads(text)
                except ValueError:
                    break  # 次のモデルへ
                return data if isinstance(data, dict) else None
            if status in summarize.RETRY_STATUS and attempt < len(config.GEMINI_RETRY_WAITS):
                sleep(config.GEMINI_RETRY_WAITS[attempt])
                continue
            break  # 次のモデルへ
    return None


def find(api_key, paper, summary, log=print, sleep=time.sleep):
    """関連する研究を1本探して {"pmid", "title", "text"} を返す。見つからなければ None。"""
    try:
        # 1. 探したい対応策と検索の言葉
        q = _ask(api_key, QUERY_PROMPT + f"タイトル：{paper['title']}\n要旨：\n{paper['abstract']}", QUERY_SCHEMA, log, sleep)
        if not q or not str(q.get("query", "")).strip():
            log("  関連する研究：AI が検索の言葉を作れなかったので、添えずに送ります")
            return None
        log(f"  関連する研究を探します：{q.get('need', '')}（検索：{q['query']}）")

        # 2. PubMed で探す（今日の論文と同じ条件で、病気の治療・動物の研究などを除く）
        term = f"({q['query']}) AND {config.COMMON_FILTER} AND {config.STRONG_TYPES}"
        ids = [i for i in pubmed.search(term, config.RELATED_DAYS) if i != paper["pmid"]][:config.RELATED_MAX]
        candidates = [c for c in pubmed.fetch(ids) if len(c["abstract"]) >= 300]
        if not candidates:
            log("  関連する研究：見つからなかったので、添えずに送ります")
            return None

        # 3. 1本選んで、対応策を短く書く
        listing = "\n\n".join(f"PMID：{c['pmid']}\nタイトル：{c['title']}\n要旨：\n{c['abstract']}" for c in candidates)
        prompt = PICK_PROMPT.format(need=q.get("need", ""), target=summary.get("study", "")) + listing
        pick = _ask(api_key, prompt, PICK_SCHEMA, log, sleep)
    except pubmed.PubMedError as e:
        log(f"  関連する研究：{e}。添えずに送ります")
        return None

    chosen = {c["pmid"]: c for c in candidates}.get(str((pick or {}).get("pmid", "")).strip())
    text = str((pick or {}).get("text", "")).strip()
    # 候補に無い番号（AI の作り話）や、日本語でない文は使わない
    if not chosen or not summarize.JAPANESE.search(text):
        log("  関連する研究：対応策に答える論文が無かったので、添えずに送ります")
        return None
    log(f"  関連する研究を添えます：PMID {chosen['pmid']}「{chosen['title'][:60]}…」")
    return {"pmid": chosen["pmid"], "title": chosen["title"], "abstract": chosen["abstract"], "text": text}
