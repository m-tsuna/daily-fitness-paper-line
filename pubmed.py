"""PubMed（医学・スポーツ科学の論文のデータベース）で論文を探す（通信する）。

使う API：E-utilities（無料・鍵なし）
- esearch：検索の言葉から、論文の番号（PMID）の一覧をもらう
- efetch：番号から、タイトル・要旨・雑誌名などを XML（入れ子の箱の形のデータ）でもらう
"""

import time
import xml.etree.ElementTree as ET

import requests

import config


# 最後に問い合わせた時刻（続けて問い合わせるときに間をあけるため）
_last_call = 0.0


class PubMedError(Exception):
    """PubMed につながらなかったときのエラー（利用者に見せる日本語のメッセージを持つ）。"""


def _get(endpoint, params):
    """PubMed に1回問い合わせて、返事（requests の Response）を返す。"""
    global _last_call
    params = {**params, "db": "pubmed", "tool": config.PUBMED_TOOL}
    wait = config.PUBMED_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)  # 鍵なしは1秒に3回まで（超えると HTTP 429）
    _last_call = time.monotonic()
    try:
        r = requests.get(config.PUBMED_URL + endpoint, params=params, timeout=config.HTTP_TIMEOUT)
    except requests.exceptions.RequestException as e:
        raise PubMedError(
            f"PubMed（論文のデータベース）につながりませんでした（{type(e).__name__}）"
            " → インターネットの接続を確かめて、もう一度動かしてください"
        )
    if r.status_code != 200:
        raise PubMedError(f"PubMed から返事がありませんでした（HTTP {r.status_code}） → 少し時間をおいて、もう一度動かしてください")
    return r


def build_term(topic, strong_only):
    """検索の言葉を組み立てる。strong_only=True なら、信頼性の高い研究の種類だけに絞る。"""
    term = f"{topic['query']} AND {config.COMMON_FILTER}"
    if strong_only:
        term += f" AND {config.STRONG_TYPES}"
    return term


def search(term, days):
    """直近 days 日に PubMed に載った論文の番号（PMID）を、関係の深い順に返す。"""
    r = _get("esearch.fcgi", {
        "term": term,
        "reldate": days,        # 何日前まで
        "datetype": "edat",     # PubMed に載った日で数える
        "retmax": config.SEARCH_MAX,
        "sort": "relevance",
        "retmode": "json",
    })
    try:
        # 返事の形：esearchresult → idlist → ["12345678", ...]
        return r.json()["esearchresult"]["idlist"]
    except (ValueError, KeyError):
        raise PubMedError("PubMed の返事の形が読めませんでした → 少し時間をおいて、もう一度動かしてください")


def _text(element):
    """XML の要素の中の文字を、斜体などのタグも含めて全部つなげて返す。"""
    return "".join(element.itertext()).strip() if element is not None else ""


def parse_articles(xml_text):
    """efetch の XML から、論文ごとの情報を辞書のリストにして返す。"""
    root = ET.fromstring(xml_text)
    articles = []
    for item in root.findall(".//PubmedArticle"):
        art = item.find(".//Article")
        if art is None:
            continue
        # 要旨は「背景」「方法」などの見出し（Label）ごとに分かれていることがある
        parts = []
        for ab in art.findall("./Abstract/AbstractText"):
            label = ab.get("Label")
            body = _text(ab)
            if body:
                parts.append(f"{label}: {body}" if label else body)
        year = _text(art.find("./Journal/JournalIssue/PubDate/Year")) or _text(
            art.find("./Journal/JournalIssue/PubDate/MedlineDate"))[:4]
        articles.append({
            "pmid": _text(item.find(".//MedlineCitation/PMID")),
            "title": _text(art.find("./ArticleTitle")),
            "abstract": "\n".join(parts),
            "journal": _text(art.find("./Journal/Title")),
            "year": year,
            "types": [_text(t) for t in art.findall("./PublicationTypeList/PublicationType")],
        })
    return articles


def fetch(pmids):
    """番号のリストから、論文の情報（タイトル・要旨など）を返す。"""
    if not pmids:
        return []
    r = _get("efetch.fcgi", {"id": ",".join(pmids), "retmode": "xml"})
    try:
        return parse_articles(r.text)
    except ET.ParseError:
        raise PubMedError("PubMed の返事の形が読めませんでした → 少し時間をおいて、もう一度動かしてください")


def candidates(topic, sent_pmids, log=print):
    """テーマに合う、まだ送っていない論文を、よい順に1本ずつ渡す（ジェネレーター）。

    最近の・信頼性の高い研究から探し、見つからなければ期間を広げる（テーマの steps か config.SEARCH_STEPS の順）。
    呼ぶ側が「この論文は現場で使えない」と判断したら、次の1本を取り出せる。
    """
    seen = set(sent_pmids)
    for days, strong_only in topic.get("steps", config.SEARCH_STEPS):
        ids = [i for i in search(build_term(topic, strong_only), days) if i not in seen]
        kind = "信頼性の高い研究" if strong_only else "すべての研究"
        log(f"  PubMed：直近{days}日・{kind}で、まだ見ていない論文 {len(ids)}本")
        for paper in fetch(ids[:5]):
            seen.add(paper["pmid"])
            if len(paper["abstract"]) >= 300:  # 要旨が短すぎると、実験の内容が書けない
                yield paper
