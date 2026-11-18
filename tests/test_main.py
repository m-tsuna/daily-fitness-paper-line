"""main.py の流れのテスト（通信しない。PubMed・AI・LINE を作りものに差し替える）。"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import config
import history
import line_send
import main
import pubmed
import summarize

NOW = datetime(2026, 11, 19, 7, 17, tzinfo=ZoneInfo("Asia/Tokyo"))  # 木曜
PAPER = {"pmid": "1", "title": "t", "abstract": "a", "journal": "", "year": "", "types": []}
GOOD = {"title_ja": "題", "conclusion": "c", "study": "s", "results": "r", "training": "a", "coaching": "b", "treatment": "c"}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """鍵と記録の場所を差し替え、送った文を集める。"""
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "l")
    monkeypatch.setattr(config, "SENT_FILE", tmp_path / "sent.json")
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "no.env")
    sent = []
    monkeypatch.setattr(line_send, "send", lambda token, text: sent.append(text))
    monkeypatch.setattr(pubmed, "candidates", lambda topic, pmids, log: iter([PAPER, dict(PAPER, pmid="2")]))
    return sent


def test_送れたら記録し_同じ日の予備の実行では送らない(env, monkeypatch):
    monkeypatch.setattr(summarize, "summarize", lambda *a, **k: GOOD)
    assert main.main([], now=NOW) == 0
    assert len(env) == 1 and env[0].startswith("【題】")
    assert main.main([], now=NOW) == 0
    assert len(env) == 1
    assert history.load(config.SENT_FILE)[0]["topic"] == "ボディビル"


def test_AI_が駄目なら送らず_番号1で終わる(env, monkeypatch):
    monkeypatch.setattr(summarize, "summarize", lambda *a, **k: None)
    with pytest.raises(SystemExit) as e:
        main.main([], now=NOW)
    assert e.value.code == 1 and env == []
    assert history.load(config.SENT_FILE) == []


def test_使えない論文は飛ばして次の論文を送る(env, monkeypatch):
    na = dict(GOOD, useful=False)
    replies = [na, GOOD]
    monkeypatch.setattr(summarize, "summarize", lambda *a, **k: replies.pop(0))
    assert main.main([], now=NOW) == 0
    records = history.load(config.SENT_FILE)
    assert [(r["pmid"], r.get("skipped", False)) for r in records] == [("1", True), ("2", False)]


def test_LINE_のトークンが無ければ日本語で知らせて終わる(env, monkeypatch, capsys):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN")
    with pytest.raises(SystemExit):
        main.main([], now=NOW)
    assert "LINE_CHANNEL_ACCESS_TOKEN）がありません" in capsys.readouterr().out
