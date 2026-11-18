"""summarize.py の単体テスト（通信しない。AI の返事は作りものに差し替える）。"""
import json

import pytest

import config
import summarize

PAPER = {"pmid": "1", "title": "t", "abstract": "a", "journal": "", "year": "", "types": []}
GOOD = {"title_ja": "題", "conclusion": "結論です。", "study": "10人", "results": "伸びた", "training": "使えます",
        "coaching": "使えます", "treatment": summarize.NOT_APPLICABLE}


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    summarize.unavailable.clear()
    monkeypatch.setattr(config, "GEMINI_MODELS", ["light", "big"])


def run(monkeypatch, replies):
    """replies：呼ばれるたびに返す (HTTP の番号, 文) の順番。呼ばれたモデルと待った秒数を返す。"""
    models, waits = [], []

    def fake_post(key, model, prompt):
        models.append(model)
        return replies.pop(0)

    monkeypatch.setattr(summarize, "_post", fake_post)
    result = summarize.summarize("key", PAPER, log=lambda *_: None, sleep=waits.append)
    return result, models, waits


def test_ふつうに要約できる(monkeypatch):
    result, models, _ = run(monkeypatch, [(200, json.dumps(GOOD))])
    assert result["title_ja"] == "題" and models == ["light"]


def test_混雑なら待ってやり直し_駄目なら次のモデル(monkeypatch):
    result, models, waits = run(monkeypatch, [(503, None), (503, None), (503, None), (200, json.dumps(GOOD))])
    assert result is not None
    assert models == ["light", "light", "light", "big"]
    assert waits == config.GEMINI_RETRY_WAITS


def test_全部駄目なら_None_英語のまま送らない(monkeypatch):
    result, _, _ = run(monkeypatch, [(503, None)] * 3 + [(404, None)])
    assert result is None


def test_項目が欠けた返事は使わない(monkeypatch):
    bad = dict(GOOD, study="")
    result, models, _ = run(monkeypatch, [(200, json.dumps(bad)), (200, "形が壊れた返事")])
    assert result is None and models == ["light", "big"]


def test_役に立つかは_AI_のはい_いいえで決める():
    assert summarize.is_useful(summarize.check_summary(dict(GOOD, useful=True)))
    assert not summarize.is_useful(summarize.check_summary(dict(GOOD, useful=False)))
