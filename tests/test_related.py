"""related.py の単体テスト（通信しない。AI と PubMed を作りものに差し替える）。"""
import json

import pytest

import config
import message
import pubmed
import related
import summarize

PAPER = {"pmid": "1", "title": "Genes of strength", "abstract": "a" * 300, "journal": "J", "year": "2026", "types": []}
SUMMARY = {"title_ja": "題", "conclusion": "c", "study": "肥満でない大人42人", "results": "r",
           "training": "具体的なやり方はこの論文には書かれていません。", "coaching": "b", "treatment": "c",
           "useful": True, "no_method": True}
CAND = {"pmid": "9", "title": "Exercise during calorie restriction", "abstract": "b" * 300, "journal": "", "year": "", "types": []}
QUERY = {"need": "減量中に筋力を保つ方法", "query": "calorie restriction AND exercise"}
PICK = {"pmid": "9", "text": "太りぎみの人の研究ですが、運動を足すと除脂肪量が平均0.87kg多く残りました。"}


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    summarize.unavailable.clear()
    monkeypatch.setattr(config, "GEMINI_MODELS", ["light", "big"])
    monkeypatch.setattr(config, "RELATED_STUDY", True)
    monkeypatch.setattr(pubmed, "search", lambda term, days: ["1", "9"])  # 今日の論文（1）は候補から外す
    monkeypatch.setattr(pubmed, "fetch", lambda ids: [CAND] if ids == ["9"] else [])


def ai(monkeypatch, replies):
    """AI の返事を順番に返す作りもの。頼まれた返事の形（schema）を集めて返す。"""
    schemas = []

    def fake_post(key, model, prompt, schema=None):
        schemas.append(schema)
        return replies.pop(0)

    monkeypatch.setattr(summarize, "_post", fake_post)
    return schemas


def find():
    return related.find("key", PAPER, SUMMARY, log=lambda *_: None, sleep=lambda _: None)


def test_やり方が書かれていない日だけ探す_スイッチで止められる(monkeypatch):
    assert related.needed(SUMMARY)
    assert not related.needed(dict(SUMMARY, no_method=False))
    monkeypatch.setattr(config, "RELATED_STUDY", False)
    assert not related.needed(SUMMARY)


def test_検索の言葉を作り_1本選んで対応策を返す(monkeypatch):
    schemas = ai(monkeypatch, [(200, json.dumps(QUERY)), (200, json.dumps(PICK))])
    result = find()
    assert result["pmid"] == "9" and "0.87kg" in result["text"]
    assert schemas == [related.QUERY_SCHEMA, related.PICK_SCHEMA]


def test_混雑なら待ってやり直す(monkeypatch):
    ai(monkeypatch, [(503, None), (200, json.dumps(QUERY)), (200, json.dumps(PICK))])
    assert find()["pmid"] == "9"


def test_候補に無い番号を選んだら添えない(monkeypatch):
    ai(monkeypatch, [(200, json.dumps(QUERY)), (200, json.dumps(dict(PICK, pmid="12345")))])
    assert find() is None


def test_どれも答えていなければ添えない(monkeypatch):
    ai(monkeypatch, [(200, json.dumps(QUERY)), (200, json.dumps({"pmid": "", "text": ""}))])
    assert find() is None


def test_候補が見つからなければ添えない(monkeypatch):
    monkeypatch.setattr(pubmed, "search", lambda term, days: ["1"])
    ai(monkeypatch, [(200, json.dumps(QUERY))])
    assert find() is None


def test_AI_が全部駄目なら添えない(monkeypatch):
    ai(monkeypatch, [(503, None)] * 3 + [(404, None)])
    assert find() is None


def test_PubMed_につながらなくても止めずに添えない(monkeypatch):
    def broken(term, days):
        raise pubmed.PubMedError("つながりませんでした")
    monkeypatch.setattr(pubmed, "search", broken)
    ai(monkeypatch, [(200, json.dumps(QUERY))])
    assert find() is None


def test_LINE_の文では別の見出しで_今日の論文の前に添える():
    rel = {"pmid": "9", "title": "t", "abstract": "", "text": "別の研究では…"}
    text = message.build(PAPER, SUMMARY, rel)
    assert "■ 関連する別の研究から（参考）\n別の研究では…\n参考にした論文：https://pubmed.ncbi.nlm.nih.gov/9/" in text
    assert text.index("関連する別の研究") < text.index("掲載：J")
    assert text.endswith("https://pubmed.ncbi.nlm.nih.gov/1/")  # 最後の行は今日の論文のリンクのまま
    assert "関連する別の研究" not in message.build(PAPER, SUMMARY)


def test_やり方が書かれていないかは_ご主人が読む文で決める():
    base = {"title_ja": "題", "conclusion": "c", "study": "s", "results": "r", "training": "週3回、1RMの70%で行います",
            "coaching": "使えます", "treatment": "c", "useful": True}
    assert not summarize.check_summary(dict(base, no_method=True))["no_method"]  # 欄だけ true でも、文にやり方があれば付けない
    assert summarize.check_summary(dict(base, training="具体的な食事のやり方はこの論文には書かれていません。"))["no_method"]


def test_長すぎる文や統計の言葉が入った文は添えない(monkeypatch):
    ai(monkeypatch, [(200, json.dumps(QUERY)), (200, json.dumps(dict(PICK, text="あ" * 251)))])
    assert find() is None
    ai(monkeypatch, [(200, json.dumps(QUERY)), (200, json.dumps(dict(PICK, text="有意に増えました（95%信頼区間）。")))])
    assert find() is None


def test_もう送った論文は候補にしない(monkeypatch):
    ai(monkeypatch, [(200, json.dumps(QUERY))])
    assert related.find("key", PAPER, SUMMARY, log=lambda *_: None, sleep=lambda _: None, exclude={"9"}) is None


def test_使えなかったモデルは次の呼び出しで試さず_ログに理由を残す(monkeypatch):
    logs, models = [], []

    def fake_post(key, model, prompt, schema=None):
        models.append(model)
        return (404, None) if model == "light" else (200, json.dumps(QUERY if schema is related.QUERY_SCHEMA else PICK))

    monkeypatch.setattr(summarize, "_post", fake_post)
    assert related.find("key", PAPER, SUMMARY, log=logs.append, sleep=lambda _: None)["pmid"] == "9"
    assert models == ["light", "big", "big"]
    assert any("HTTP 404" in t for t in logs)
